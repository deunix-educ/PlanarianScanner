# planarian/views.py

#import asyncio
import logging
import csv
import io
import json
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render #, redirect
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.views import View

from modules.planarian_metrics import ExperimentParams, ReductStoreClient
from modules.system_stats import get_cached_stats, start_background_updater
from scanner.constants import ScannerConstants
from .tasks import export_experiment_metrics, export_session_metrics
from scanner import models
from .models import ExperimentConfig


logger = logging.getLogger(__name__)
start_background_updater()


def is_staff_or_admin(user):
    return user.is_staff or user.is_superuser   


@require_GET
def stats_view(request):
    """
    Retourne tout le cache (shm, cpu_info, memory_info, disk_info, updated_at)
    """
    try:
        data = get_cached_stats()
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def _get_reduct_client() -> ReductStoreClient:
    """Instancie le client ReductStore depuis les settings Django."""
    return ReductStoreClient(url=settings.REDUCTSTORE_URL, token=settings.REDUCTSTORE_TOKEN)


def global_context(request, **ctx):
    conf = ScannerConstants().get()
    return dict(
        app_title=settings.APP_TITLE,
        app_sub_title=settings.APP_SUB_TITLE,
        domain_server=settings.DOMAIN_SERVER,
        local_ip_server=settings.LOCAL_IP_SERVER,
        host_port=settings.SERVER_HOST_PORT,
        export_csv_destination=settings.CSV_EXPORT_DIR,
        conf=conf,
        **ctx
    )


def get_active_experiments(session, expid=None):
    if session:
        experiments = models.SessionExperiment.experiment_by_session(session.id, active=True) or []
        eid = [str(e.id) for e in experiments]        
        if experiments and not expid or expid not in eid:
            return experiments, experiments[0]
        
        for e in experiments:
            if expid == str(e.id):
                return experiments, e
    return [], None


def get_active_session(request, session_id=None, experiment_id=None):
    cursid = session_id or request.POST.get('_sid')
    expid = experiment_id or request.POST.get('_expid')

    current_session = models.Session.get_session(cursid)
    experiments, current_experiment = get_active_experiments(current_session, expid) 
    context = dict(
        current_session = current_session,
        current_experiment = current_experiment,
        experiments=experiments or [],
        sessions=models.Session.objects.filter(active=True).all(),
        well_choices=models.Well.objects.order_by('name').all(),
    )
    return context    
    
# ---------------------------------------------------------------------------
# Vue :Export CSV depuis ReductStore
# ---------------------------------------------------------------------------

@login_required
@csrf_exempt
def export_metrics(request):   
    data = json.loads(request.body.decode() or "{}")
    action = data.get("action")
    pid = data.get("pid")
    if action=='experiment_csv':    
        experiment = models.Experiment.objects.filter(pk=pid).first()
        if experiment:
            export_experiment_metrics(experiment)
            return JsonResponse({"state":  True})
    if action=='session_csv':   
        session = models.Session.objects.filter(pk=pid).first()
        if session:
            export_session_metrics(session)
            return JsonResponse({"state":  True})
    return JsonResponse({"state":  False})
 
 
def export_csv(request):
    d = request.POST
    
    @async_to_sync
    async def _do_export():
        client = _get_reduct_client()
        await client.connect()
        try:
            csv_content, n = await client.export_csv_response(
                experiment  = d.get("experiment"),
                well        = d.get("well"),
                planarian   = d.get("planarian"),
                record_type = d.get("record_type"),
                start       = d.get("start_dt"),
                stop        = d.get("stop_dt"),
            )          
            print(f"Export CSV: export_csv_response done, {n} lignes, content size={len(csv_content)}")
        except Exception as e:
            logger.error(f"Erreur export CSV: {e}")
            messages.error(request, _("Erreur lors de l'export CSV: %(error)s") % {"error": str(e)})
            return None, 0
        return csv_content, n

    csv_content, n = _do_export()
    logger.info(f"Export CSV: {n} lignes, content size={len(csv_content)}")
    filename = (
        f"{d['experiment']}_{d['well']}-planaire{d['planarian']}"
        f"_{d['record_type']}.csv"
    )
    return csv_content, filename


@login_required
def export_csv_view(request):   
    session_context = get_active_session(request)
    ctx = {
        'choice_title': _("Export vers un fichier CSV depuis ReductStore"), 
        'well': 'A1',
        'planarian': "0",
        'record_type': 'frame',        
        **session_context
    }    
    if request.method == 'POST':
        valid = request.POST.get('valid')
        if valid == 'ok':
            csv_content, filename = export_csv(request)
            if csv_content:
                response = FileResponse(csv_content, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response

            messages.warning(request, _("Aucune donnée trouvée."))
    return render(request, "planarian/export_csv.html", context=global_context(request, **ctx))


# ---------------------------------------------------------------------------
# Vue : import CSV de paramètres
# ---------------------------------------------------------------------------
def import_csv(request, current_experiment, rows, overwrite):
    created   = 0
    updated   = 0
    errors    = 0

    for row in rows:
        try:
            params = ExperimentParams.from_csv_row(row)
            d      = params.to_dict()
          
            obj, is_new = ExperimentConfig.objects.get_or_create(
                experiment = current_experiment.identifier,
                well       = d.get("well"),
            )

            if is_new or overwrite:
                for k, v in d.items():
                    if k not in ["well", "experiment", "author", "experiment_key", "active"] and hasattr(obj, k):
                        setattr(obj, k, v)              
                obj.save()
                if is_new:
                    created += 1
                else:
                    updated += 1
   
        except Exception as e:
            logger.warning(f"Ligne ignorée ({row}): {e}")
            errors += 1
    messages.success(
        request,
        _("Import terminé : %(c)d créés, %(u)d mis à jour, %(e)d erreurs.")
        % {"c": created, "u": updated, "e": errors},
    )

    return redirect("redirect_to_mainboard")
    
    
@login_required
def import_csv_view(request):  
    """
    Import de configurations d'expérience depuis un fichier CSV.
    Une ligne CSV = un puits = un ExperimentConfig.

    Colonnes CSV obligatoires: well, px_per_mm, fps
    Toutes les autres colonnes correspondent aux champs du modèle.
    """
    session_context = get_active_session(request)
    if request.method == 'POST':
        valid = request.POST.get('valid')
        current_experiment = session_context.get('current_experiment')
        
        if valid == 'ok' and current_experiment:
            try:
                f = request.FILES.get('csv_file')
                overwrite = request.POST.get("overwrite")
                try:
                    content = f.read().decode("utf-8-sig")
                    reader  = csv.DictReader(io.StringIO(content))
                    rows    = list(reader)
                except Exception as e:
                    msg = f'Fichier CSV invalide : {e}'
                    raise Exception(msg)

                required = {"well", "px_per_mm", "fps"}
                if rows:
                    missing = required - set(rows[0].keys())
                    if missing:
                        msg = _("Colonnes manquantes : %(cols)s") % {"cols": ", ".join(missing)}
                        raise Exception(msg)
            
                    return import_csv(request, current_experiment, rows, overwrite)
            except Exception as e:
                messages.error(request, msg)
                logger.error(msg) 
    ctx = { 'choice_title': _("Importer des configurations depuis un fichier CSV"), **session_context }
    return render(request, "planarian/import_params.html", context=global_context(request, **ctx))    

# ---------------------------------------------------------------------------
# Vue API JSON : données de tracking (pour polling front-end)
# ---------------------------------------------------------------------------
class TrackingDataView(View):
    """
    API JSON retournant les métriques de tracking d'un planaire.
    Utilisable pour un affichage temps réel ou un graphe front-end.

    GET /tracking-data/?experiment=X&well=Y&planarian=0&record_type=frame
    """

    def get(self, request):
        experiment  = request.GET.get("experiment", "")
        well        = request.GET.get("well", "")
        planarian   = int(request.GET.get("planarian", 0))
        record_type = request.GET.get("record_type", "frame")

        if not experiment or not well:
            return JsonResponse({"error": "experiment et well requis"}, status=400)

        @async_to_sync
        async def _fetch():
            client = _get_reduct_client()
            await client.connect()
            try:
                return await client.get_tracking_data(
                    experiment  = experiment,
                    well        = well,
                    planarian   = planarian,
                    record_type = record_type,
                )
            except Exception as e:
                logger.error(f"Erreur fetching tracking data: {e}")

        records = _fetch()
        return JsonResponse({"count": len(records), "records": records})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return global_context(self.request, choice_title=str(_("Métriques de tracking d'un planaire")), **context)
    
