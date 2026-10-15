#
import os
from asgiref.sync import async_to_sync
import base64, json
from django.shortcuts import render #, redirect
from django.http import JsonResponse, FileResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.utils import timezone

from reduct.time import unix_timestamp_to_iso
from modules.system_stats import get_cached_stats, start_background_updater
from modules import reductstore

from .tasks import download_video, export_all_images, export_all_videos
from .process import CameraRecordManager, cameraDB
from . import models
from .constants import ScannerConstants
from .busy import get_busy

record_manager = CameraRecordManager(cameraDB)
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


def global_context(request, **ctx):
    default_multiwell = models.MultiWell.objects.filter(default=True).first()
    conf = ScannerConstants().get()
    return dict(
        app_title=settings.APP_TITLE,
        app_sub_title=settings.APP_SUB_TITLE,
        domain_server=settings.DOMAIN_SERVER,
        local_ip_server=settings.LOCAL_IP_SERVER,
        host_port=settings.SERVER_HOST_PORT,
        conf=conf,
        default_position = default_multiwell.position or 'HD',
        export_destination=settings.EXPORT_DESTINATIONS,
        **ctx
    )

@login_required
@user_passes_test(is_staff_or_admin)
def admin_view(request):
    return render(request, "scanner/iframe.html", context=global_context(request, link='/admin/'))


@login_required
def admin_session_view(request):
    return render(request, "scanner/iframe.html", context=global_context(request, link='/admin/scanner/session/'))


@login_required
def admin_experiment_view(request):
    return render(request, "scanner/iframe.html", context=global_context(request, link='/admin/scanner/experiment/'))

@login_required
def admin_experimentconfig_view(request):
    return render(request, "scanner/iframe.html", context=global_context(request, link='/admin/planarian/experimentconfig/'))


@login_required
def admin_periodictask_view(request):
    return render(request, "scanner/iframe.html", context=global_context(request, link='/admin/django_celery_beat/periodictask/'))


@login_required
@user_passes_test(is_staff_or_admin)
def reductstore_view(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}:8383/'))


@login_required
@user_passes_test(is_staff_or_admin)
def adminer_view(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}/adminer/'))

@login_required
@user_passes_test(is_staff_or_admin)
def portainer_view(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}:9000/'))


@login_required
@user_passes_test(is_staff_or_admin)
def supervisor_view(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}:9001/'))


@login_required
@user_passes_test(is_staff_or_admin)
def supervisor_worker(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}:9001/logtail/test_tube:services'))


@login_required
@user_passes_test(is_staff_or_admin)
def supervisor_scheduler(request):
    return render(request, "scanner/redirection.html", context=global_context(request, link=f'http://{settings.DOMAIN_SERVER}:9001/logtail/test_tube:planification'))


def documentation(request, template=None):
    ctx = dict(
        choice_title=_("Documentation")
    )
    return render(request, f"docs/{template}.html", context=global_context(request, **ctx))


## Mainboard
@login_required
def scanning_view(request):
    cursid = 0
    if request.method == 'POST':
        cursid = request.POST.get('_session', 0)
    if not cursid:
        current_session = models.Session.objects.filter(active=True).first()
        cursid = current_session.pk if current_session else 0

    context = global_context(request)
    capture_type = context['conf'].capture_type
    ctx = dict(
        ws_route=settings.SCANNER_WEBSOCKET_ROUTE,
        cursid=int(cursid),
        sessions=models.Session.objects.filter(active=True).all(),
        choice_title=_("Balayage multi-puits")
    )
    ctx.update(cnc_context(table_multiwells(capture_type), context['conf'], capture_type))
    if ctx['simulation']:
        # plaque de la session choisie, sinon celle par défaut (la suite est suivie par le message
        # `position` du worker pendant le balayage)
        experiments = models.SessionExperiment.experiment_by_session(int(cursid)) if cursid else []
        active = experiments[0].multiwell.position if experiments and experiments[0].multiwell else context['default_position']
        positions = [p['position'] for p in ctx['cnc_geometry']['plates']]
        ctx['cnc_active'] = active if active in positions else (positions[0] if positions else '')
    context.update(ctx)
    return render(request, "scanner/scanning.html", context=context)

## Calibration
@login_required
def calibration_view(request):
    context = global_context(request)
    # seuls les multi-puits actifs sont proposés (liste déroulante et table CNC)
    wells = models.MultiWell.objects.filter(capture_video=False, active=True).all()
    capture_type = context['conf'].capture_type
    config = ScannerConstants.get_config()
    
    if capture_type == 'video':
        mw = models.MultiWell.objects.filter(default=True, capture_video=True, active=True).first()
        if mw:
            context['conf'].default_position = mw.position
            wells = models.MultiWell.objects.filter(capture_video=True, active=True).all()

    # le multi-puits « défaut » est peut-être inactif : on présélectionne alors le premier actif
    positions = [w.position for w in wells]
    if positions and context['default_position'] not in positions:
        context['default_position'] = positions[0]

    ctx = dict(
        ws_route=settings.SCANNER_WEBSOCKET_ROUTE,
        choice_title=f'{str(_("Calibration"))} {config.get_capture_type_display()}',
        wells = wells,
        capture_type=capture_type,
    )
    ctx.update(cnc_context(wells, context['conf'], capture_type, js='scanner/js/calibration.js'))
    context.update(ctx)
    return render(request, "scanner/calibration.html", context=context)


def table_multiwells(capture_type):
    """Multi-puits actifs posés sur la table : ceux de la capture vidéo en mode vidéo (s'il y en a), sinon les autres."""
    qs = models.MultiWell.objects.filter(active=True)
    if capture_type == 'video' and qs.filter(capture_video=True, default=True).exists():
        return qs.filter(capture_video=True)
    return qs.filter(capture_video=False)


def cnc_context(multiwells, conf, capture_type, js='scanner/js/scanning.js'):
    """Contexte de la vue isométrique du bras : affichée par défaut en simulation (le mode vidéo
    force le simulateur GRBL) ; disponible aussi en GRBL réel via la case à cocher côté page (la
    position affichée reste exacte, seule l'animation du déplacement est propre au simulateur)."""
    simulation = bool(settings.GRBL_SIMULATION or capture_type == 'video')
    ctx = dict(simulation=simulation,
               cnc_geometry=cnc_geometry(multiwells, conf),
               asset_v=asset_version(js, 'scanner/js/cnc_view.js', 'scanner/css/cnc_view.css'))
    return ctx


def asset_version(*paths):
    """Date de modification la plus récente des fichiers statiques servis (anti-cache `?v=`)."""
    versions = []
    for p in paths:
        try:
            versions.append(int(os.path.getmtime(os.path.join(settings.STATIC_ROOT, p))))
        except OSError:
            pass
    return max(versions, default=0)


def cnc_geometry(multiwells, conf):
    """Plateau et plaques (coordonnées CNC en mm) pour la vue isométrique du bras, en simulation."""
    plates = []
    for mw in multiwells:
        # La plaque est placée par son origine : le puits de la 1re ligne de row_def (D1) est en
        # (xbase, ybase) ; les colonnes vont vers +X (dx) et les lignes vers +Y (dy), D -> A.
        letters = (mw.row_def or '').split(',')[:mw.rows]
        order = {name: i for i, name in enumerate(mw.serpentine_names())}
        wells = [dict(name=f'{letter}{c + 1}', order=order.get(f'{letter}{c + 1}', 0),
                      x=round(mw.xbase + c * mw.dx, 3), y=round(mw.ybase + r * mw.dy, 3))
                 for r, letter in enumerate(letters) for c in range(mw.cols)]
        # positions enregistrées (celles que le bras visite) en retard sur l'origine ?
        origin = models.WellPosition.objects.filter(multiwell=mw, well__name=f'{letters[0]}1').first() if letters else None
        stale = origin is None or abs(origin.x - mw.xbase) > 0.5 or abs(origin.y - mw.ybase) > 0.5
        plates.append(dict(position=mw.position, label=mw.label, diameter=mw.diameter, wells=wells, stale=stale))
    return dict(bed=dict(x=conf.grbl_xmax, y=conf.grbl_ymax), plates=plates)

def get_not_active_experiments(session, expid=None) -> tuple[list, "models.Experiment | None"]:
    if session:
        experiments = models.SessionExperiment.experiment_by_session(session.pk, active=False) or []
        if experiments and not expid:
            return experiments, experiments[0]
        for e in experiments:
            if expid == str(e.pk):
                return experiments, e
    return [], None
    
## images
def get_images(uuid):
    oldest, latest, n, images = 0, 0, 0, []

    filters = record_manager.set_filters(test=False)
    queries = record_manager.query(uuid, filters=filters)
    while True:
        try:
            record, content = async_to_sync(record_manager.record_content)(queries)
            if n<1:
                oldest = record.timestamp
            latest = record.timestamp
            msg = {
                "uuid": uuid,
                "ts": unix_timestamp_to_iso(latest),
                "content": f'data:image/jpeg;base64,{base64.b64encode(content).decode()}',
                "index": n,
            }
            images.append(msg)
            n+=1
        except:
            break
    return int((latest-oldest)/1_000_000), images


@login_required
def images_view(request):
    cursid, expid, duration, uuid, images = 0, None, 0, "", []    
    if request.method == 'POST':
        cursid = request.POST.get('_sid')
        expid = request.POST.get('_expid')
        uuid = request.POST.get('_multiwell')
        duration, images = get_images(uuid)

    current_session = models.Session.get_session(cursid)
    experiments, current_experiment = get_not_active_experiments(current_session, expid)
    ctx = dict(
        choice_title=_("Gestionnaire d'images"),
        sessions=models.Session.objects.filter(active=False).all(),
        experiments=experiments or [],
        current_session=current_session,
        current_experiment=current_experiment,
        images=images,
        uuid=uuid,
        duration=duration,
    )
    return render(request, "scanner/images.html", context=global_context(request, **ctx))

@login_required
def export_medias(request):
    cursid = 0    
    if request.method == 'POST':
        cursid = request.POST.get('_sid')
        valid = request.POST.get('valid')
        if valid == 'ok':
            try:
                session = models.Session.objects.get(pk=cursid)
                session.expected_export = timezone.now()
                if not session.export_status == "running":
                    session.export_status = "running"
                    if session.export_task:
                        session.export_task.enabled = True
                        session.export_task.save()
                    session.save()

            except Exception as e:
                print("export_medias error", e)
        
    current_session = models.Session.get_session(cursid)
    ctx = dict(
        choice_title=_("Exporter les fichiers médias"),
        sessions=models.Session.objects.filter(active=False).all(),
        current_session=current_session,
        url=f'http://{settings.DOMAIN_SERVER}:9001/logtail/test_tube:services',
    )
    return render(request, "scanner/export_medias.html", context=global_context(request, **ctx))


@require_POST
def download_api(request):
    data = json.loads(request.body.decode() or "{}")
    try:
        action = data.get("action")
        if action=='download':
            uuid, dt_start, dt_stop, frame_rate = data.get("uuid"), data.get("dt_start"), data.get("dt_stop"), data.get("fps")
            task = download_video.delay(uuid, dt_start, dt_stop, frame_rate=frame_rate)  # @UndefinedVariable
            result = task.get(timeout=300)

            if result.get('success'):
                video_path = result.get('video_path')
                if not os.path.exists(video_path):
                    raise Exception(f"File not created: {video_path}")           
    
                response = FileResponse(open(video_path, 'rb'), content_type='video/mp4')
                response['Content-Disposition'] = f'attachment; filename="{video_path}"'
                response['Content-Length'] = os.path.getsize(video_path)
                os.remove(video_path)
                return response
            return JsonResponse(result, status=500)
    except Exception as e:
        print("download_api error",  e)
    return JsonResponse({"state":  False, "success":  False, "msg": str(_("Erreur d'exportation")), }, status=500)

    
def get_video(uuid):
    oldest, latest = async_to_sync(reductstore.old_last_dates)(cameraDB, entry_name=uuid)
    filters = record_manager.set_filters(test=False)
    image, _ =  record_manager.first_image(uuid, filters=filters)
    return oldest, latest, image


@login_required
def replay_view(request):
    cursid, expid, oldest, latest, uuid, image = 0, None, 0, 0, "", ""

    if request.method == 'POST':
        cursid = request.POST.get('_sid')
        expid = request.POST.get('_expid')
        uuid = request.POST.get('_multiwell')
        if uuid:
            oldest, latest, image = get_video(uuid)
            
    current_session = models.Session.get_session(cursid)
    experiments, current_experiment = get_not_active_experiments(current_session, expid)
            
    ctx = dict(
        choice_title=_("Gestionnaire de vidéos"),
        ws_route=settings.REPLAY_WEBSOCKET_ROUTE,
        sessions=models.Session.objects.filter(active=False).all(),
        experiments=experiments or [],
        current_session=current_session,
        current_experiment=current_experiment,      
        image=image,
        uuid=uuid,
        oldest=oldest,
        latest=latest,
    )
    return render(request, "scanner/replay.html", context=global_context(request, **ctx))


@require_POST
@login_required
@user_passes_test(is_staff_or_admin)
def reorder_wells_api(request):
    """Réordonne en serpentin les puits du multi-puits `position` (xbase/ybase réalignés sur l'ordre 0)."""
    data = json.loads(request.body.decode() or "{}")
    dry_run = bool(data.get("dry_run", True))
    mw = models.MultiWell.by_position(data.get("position"))
    if not mw:
        return JsonResponse({"success": False, "msg": str(_("Multi-puits absent"))})

    busy = None if dry_run else get_busy()
    if busy:
        kind = str(_("un balayage")) if busy == 'scan' else str(_("un test de calibration"))
        return JsonResponse({"success": False, "msg": f'{_("Refusé")} : {kind} {_("est en cours. Arrêter avant de réordonner les puits.")}'})

    r = mw.reorder_well_positions(realign_base=True, dry_run=dry_run)
    if r["error"]:
        return JsonResponse({"success": False, "msg": f"{mw.position}: {r['error']}"})
    o = r["origin"]
    prefix = str(_("Simulation")) if dry_run else str(_("Réordonné"))
    msg = f"{prefix} — {mw.position}: {r['changed']} ordre(s), origine {o['name']} ({o['x']}, {o['y']})"
    return JsonResponse({"success": True, "dry_run": dry_run, "msg": msg})


@require_POST
def export_api(request):
    data = json.loads(request.body.decode() or "{}")
    session_id = data.get("sid")
    action = data.get("action")
    try:
        if action == 'export_images':
            export_all_images(session_id)
            return JsonResponse({"success":  True,  "msg": str(_("Images en cours de téléchargement"))})
        elif action == 'export_videos':
            export_all_videos(session_id)
            return JsonResponse({"success":  True, "msg": str(_("Vidéos en cours de téléchargement"))})
    except:
        return JsonResponse({"state":  False, "success":  False, "msg": str(_("Erreur d'exportation")), })

