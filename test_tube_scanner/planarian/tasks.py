# tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger

from django.conf import settings
from asgiref.sync import async_to_sync
from modules.planarian_metrics import ReductStoreClient
from scanner.models import SessionExperiment
from .models import ExperimentConfig


logger = get_task_logger(__name__)

def _get_reduct_client() -> ReductStoreClient:
    """Instancie le client ReductStore depuis les settings Django."""
    return ReductStoreClient(url=settings.REDUCTSTORE_URL, token=settings.REDUCTSTORE_TOKEN)


@shared_task
def export_experiment_metrics(experiment):
    
    @async_to_sync
    async def _do_export(well, planarian, record_type):
        client = _get_reduct_client()
        
        await client.connect()
        try:
            f, n = await client.export_csv(
                experiment  = experiment.identifier,
                well        = well,
                planarian   = planarian,
                record_type = record_type,
                output_dir  = settings.CSV_EXPORT_DIR,
            )
            logger.warning(f"Export CSV {settings.CSV_EXPORT_DIR}/{f} done, {n} lignes")            
        except Exception as e:
            logger.error(f"Erreur export CSV: {e}")
            
    experiment_configs = ExperimentConfig.objects.filter(experiment_key_id=experiment.id).order_by('well').all()
    for conf in experiment_configs:
        well = conf.well
        count = conf.planarian_count
        
        for record_type in ["frame", "summary"]:
            for planarian in range(count):
                _do_export(well, planarian, record_type)
            
@shared_task
def export_session_metrics(session):
    experiments = SessionExperiment.experiment_by_session(session.id)
    for experiment in experiments:
        export_experiment_metrics(experiment)

    