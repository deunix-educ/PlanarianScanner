# planarian/views.py

#import asyncio
import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect    #, render
from django.utils.translation import gettext_lazy as _

from django.shortcuts import render #, redirect
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test

from django.views import View
from django.views.generic import FormView, ListView


from .forms import CsvImportForm, ExperimentConfigForm, ExportCsvForm
from .models import ExperimentConfig

from modules.planarian_metrics import ExperimentParams, ReductStoreClient
from modules.system_stats import get_cached_stats, start_background_updater
from scanner.constants import ScannerConstants
from scanner import models


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
        conf=conf,
        **ctx
    )


def get_active_experiments(session, expid=None):
    if session:
        experiments = models.SessionExperiment.experiment_by_session(session.id, active=True) or []
        eid = [str(e.id) for e in experiments]
        
        print(f"Found {eid} active experiments for session {session.id}")
        
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
            print(f"Export CSV: export_csv_response done, {n} lignes, content size={len(csv_content)}, {csv_content}")
        except Exception as e:
            logger.error(f"Erreur export CSV: {e}")
            messages.error(request, _("Erreur lors de l'export CSV: %(error)s") % {"error": str(e)})
            return None, 0
        return csv_content, n

    csv_content, n = _do_export()

    logger.info(f"Export CSV: {n} lignes, content size={len(csv_content)}")
    if not csv_content:
        messages.warning(request, _("Aucune donnée trouvée."))
        return None

    filename = (
        f"{d['experiment']}_{d['well']}_planaire{d['planarian']}"
        f"_{d['record_type']}.csv"
    )
    response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'       
    messages.success(request, _("%(n)d lignes exportées.") % {"n": n})
    return response


@login_required
def export_csv_view(request, session_id=None, experiment_id=None):   
    session_context = get_active_session(request, session_id, experiment_id)
    
    if request.method == 'POST':
        valid = request.POST.get('valid')
        if valid == 'ok':
            export_csv(request)

    ctx = {
        'choice_title': _("Export vers un fichier CSV depuis ReductStore"), 
        'well': 'A1',
        'planarian': "0",
        'record_type': 'frame',        
        **session_context
    }

    return render(request, "planarian/export_csv.html", context=global_context(request, **ctx))


# ---------------------------------------------------------------------------
# Vue : import CSV de paramètres
# ---------------------------------------------------------------------------
@login_required
def import_csv_view(request, session_id=None, experiment_id=None):  
    """
    Import de configurations d'expérience depuis un fichier CSV.
    Une ligne CSV = un puits = un ExperimentConfig.

    Colonnes CSV obligatoires : experiment, well, px_per_mm, fps
    Toutes les autres colonnes correspondent aux champs du modèle.
    """
    
    
    
    ctx = {
        'choice_title': _("Importer des configurations depuis un fichier CSV"),  
    }
    return render(request, "planarian/import_params.html", context=global_context(request, **ctx))    


class ImportParamsView(FormView):
    """
    Import de configurations d'expérience depuis un fichier CSV.
    Une ligne CSV = un puits = un ExperimentConfig.

    Colonnes CSV obligatoires : experiment, well, px_per_mm, fps
    Toutes les autres colonnes correspondent aux champs du modèle.
    """

    template_name = "planarian/import_params.html"
    form_class    = CsvImportForm
    
    
    def form_valid(self, form):
        rows      = form.csv_rows
        overwrite = form.cleaned_data["overwrite"]
        created   = 0
        updated   = 0
        errors    = 0

        for row in rows:
            try:
                params = ExperimentParams.from_csv_row(row)
                d      = params.to_dict()

                obj, is_new = ExperimentConfig.objects.get_or_create(
                    experiment = d["experiment"],
                    well       = d["well"],
                )

                if is_new or overwrite:
                    for k, v in d.items():
                        if k not in ("experiment", "well") and hasattr(obj, k):
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
            self.request,
            _("Import terminé : %(c)d créés, %(u)d mis à jour, %(e)d erreurs.")
            % {"c": created, "u": updated, "e": errors},
        )
        return redirect("planarian:experiment-list")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return global_context(self.request, choice_title=_("Importer des configurations depuis un fichier CSV"), **context)
       

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
    
