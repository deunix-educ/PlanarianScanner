# tasks.py
import asyncio
import json
from celery import shared_task, group, chord, chain
from celery.utils.log import get_task_logger
from django.utils import timezone

from .process import ScannerProcess, ReplayProcess, redisDB
from .export_tasks import shm_download_video, export_images_zip, export_video_mp4
from .constants import ScannerConstants
from . import models

logger = get_task_logger(__name__)


@shared_task
def scanner_start():
    scanner = ScannerProcess()        
    scanner.start()     
    return f"Scanner démarré."

@shared_task
def replay_start():
    replay = ReplayProcess(latency=5.0)
    replay.start()    
    return f"Replay démarré."

@shared_task
def download_video(uuid, start_ts, end_ts, frame_rate=10, opencv_fourcc_format='mp4v', opencv_video_type='mp4'):
    try:
        return asyncio.run(shm_download_video(uuid, start_ts, end_ts, frame_rate, opencv_fourcc_format, opencv_video_type))
    except Exception as e:
        logger.error(f"download_video: {e}")

@shared_task
def export_images(
        uuid: str, 
        start_ts: float | None = None, 
        end_ts: float | None = None, 
        jpeg_quality: int = 90,
        max_zip_size_mb: int = 0, 
        max_image_width: int = 0,  
        max_image_height: int = 0 ):
    try:
        return asyncio.run(export_images_zip(uuid, start_ts, end_ts, jpeg_quality, max_zip_size_mb, max_image_width, max_image_height))
    except Exception as e:
        logger.error(f"export_images: {e}")
        
@shared_task
def export_all_images(session_id=None):
    try:
        conf = ScannerConstants().get()
        
        if session_id is None:
            sessions = [s.id for s in models.Session.objects.filter(active=False)]
        else:
            sessions = [session_id]
            
        for session_id in sessions:      
            uuid_list = models.SessionExperiment.uuid_from_session(session_id)
            job_zip = []
            for uuid in uuid_list:
                
                job = export_images.delay(  # @UndefinedVariable
                    uuid, 
                    start_ts=None,
                    end_ts=None,
                    jpeg_quality=conf.video_jpeg_quality,   # Qualité JPEG
                )
                job_zip.append(job.id)        
        
        return job_zip
    except Exception as e:
        logger.error(f"export_images: {e}")       

@shared_task
def export_videos(uuid: str, 
        start_ts: float | None = None, 
        end_ts: float | None = None, 
        frame_rate: int = 5,
        opencv_fourcc_format='mp4v', 
        opencv_video_type='mp4',
        max_video_size_mb: int = 0, 
        max_width: int = 0,
        max_height: int = 0, ):
    try:
        return asyncio.run(export_video_mp4(uuid, start_ts, end_ts, frame_rate, opencv_fourcc_format, opencv_video_type, max_video_size_mb, max_width, max_height))
    except Exception as e:
        logger.error(f"export_videos: {e}")


@shared_task
def export_all_videos(session_id=None):
    try:
        conf = ScannerConstants().get()
        if session_id is None:
            sessions = [s.id for s in models.Session.objects.filter(active=False)]
        else:
            sessions = [session_id]
            
        for session_id in sessions:
            uuid_list = models.SessionExperiment.uuid_from_session(session_id)  
            job_mp4 = []
            for uuid in uuid_list:
                
                job = export_videos.delay(  # @UndefinedVariable
                    uuid, 
                    start_ts=None,
                    end_ts=None,
                    frame_rate=conf.video_frame_rate,                  # Frame rate de la vidéo exportée
                    opencv_fourcc_format=conf.opencv_fourcc_format,    # Format de compression vidéo (ex: 'mp4v' pour MP4),
                    opencv_video_type=conf.opencv_video_type,          # Type de vidéo exportée (ex: 'mp4', 'avi', 'mkv'),    
                )
                job_mp4.append(job.id)
              
        return job_mp4
    except Exception as e:
        logger.error(f"export_all_videos: {e}")


@shared_task(bind=True)
def run_session_exports(self, session_id: str):
    """
    Orchestre l'export images + vidéo en parallèle via chord.
    Lance en parallèle l'export images et l'export vidéo de la session.
    Le callback on_exports_done est appelé quand les 2 sont terminés.
    """
    try:
        session = models.Session.objects.get(pk=session_id)
    except models.Session.DoesNotExist:
        logger.error("run_session_exports: session %s introuvable", session_id)
        return {"status": "error", "message": "Session introuvable"}

    session.status = models.Session.Status.RUNNING
    session.save(update_fields=["export_status"])
    logger.info(f"run_session_exports [{session_id}]: export démarré")
    chord(
        group(
            export_all_images.s(session_id),
            export_all_videos.s(session_id),
        ),
        on_exports_done.s(session_id=session_id)
    ).apply_async()


@shared_task
def on_exports_done(results: list, session_id: str):
    """
    Callback appelé par chord quand export_all_images ET export_all_videos
    sont tous les deux terminés.
    results = [résultat_images, résultat_vidéo]
    """
    session = models.Session.objects.get(pk=session_id)

    errors = [r for r in results if isinstance(r, dict) and r.get("export_status") == "error"]
    if errors:
        session.export_status = models.Session.Status.ERROR
        logger.error(f"on_exports_done [{session_id}]: échec avec {len(errors)} erreurs")
    else:
        session.export_status = models.Session.Status.DONE
        logger.warning(f"on_exports_done [{session_id}]: succès export terminé")
    
    session.export_exported_at = timezone.now()
    session.save(update_fields=["export_status", "export_exported_at"])
    return {"status": session.export_status}


@shared_task
def scanning(session_id: str):
    """
    Scanning différé.
    """    
    try:
        logger.warning("==== scanning session %s start", session_id)
        group = 'scanner_proc'
        data = { "type": "scanner", "topic": "scan", "session": session_id }
        redisDB.publish(group, json.dumps(data))
    except Exception as e:
        logger.error(f"scanning session: {session_id} error {e}")
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def run_scanning(self, session_id: str):   
    try:
        session = models.Session.objects.get(pk=session_id)
        if not session.active:
            raise Exception("La session n'est plus active")
    except models.Session.DoesNotExist:
        logger.error("run_session_exports: session %s introuvable", session_id)
        return {"status": "error", "message": "Session introuvable"}

    session.scanning_status = models.Session.Status.RUNNING
    session.save(update_fields=["scanning_status"])
    chain(
        scanning.s(session_id), 
        on_scanning_done.s(session_id=session_id),
    ).apply_async()

    
@shared_task
def on_scanning_done(result: dict, session_id: str):
    """
    Callback appelé automatiquement à la fin de scanning().
    Met à jour scanning_status en base — détectable par polling.
    """
    try:
        session = models.Session.objects.get(pk=session_id)
    except models.Session.DoesNotExist:
        logger.error("on_scanning_done: session %s introuvable", session_id)
        return

    session.scanning_status = models.Session.Status.ERROR if result.get("status") == "error" else models.Session.Status.DONE
    session.scanning_finished_at = timezone.now()
    session.save(update_fields=["scanning_status", "scanning_finished_at"])
    
    logger.info("==== Scanning done: session %s", session_id)
    