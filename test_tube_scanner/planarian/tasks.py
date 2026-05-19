# tasks.py
from celery import shared_task, group
from celery.utils.log import get_task_logger

from scanner.models import SessionExperiment, get_uuid_from_session, Experiment
from .models import ExperimentConfig
from .export_service import export_csv_file_sync

logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3},)
def export_single_metric(self, *, experiment, well, uuid, planarian, record_type,):
    """
    Exporte UN fichier CSV.
    """
    logger.info( f"Export start {experiment} {well} {planarian} {record_type}")
    f, n = export_csv_file_sync(
        experiment=experiment,
        well=well,
        uuid=uuid,
        planarian=planarian,
        record_type=record_type,
    )
    logger.info( f"Export done {f} ({n} rows)" )
    return {"file": f, "rows": n, }


@shared_task
def export_experiment_metrics_task(experiment_id):
    experiment = Experiment.objects.filter(pk=experiment_id).first()
    if not experiment:
        return
    
    jobs = []
    configs = (ExperimentConfig.objects.filter(experiment_key_id=experiment.id).order_by("well"))
    for conf in configs:
        well = conf.well
        count = conf.planarian_count
        session = conf.get_session()
        uuid = get_uuid_from_session(session.id, conf.experiment_key.multiwell.position, well, )

        for record_type in ["frame", "summary"]:
            for planarian in range(count):
                '''
                jobs.append(
                    export_single_metric.s(
                        experiment=experiment.identifier,
                        well=well,
                        uuid=uuid,
                        planarian=planarian,
                        record_type=record_type,
                    )
                )
                     
                '''
                try:
                    f, n = export_csv_file_sync(
                        experiment=experiment.identifier,
                        well=well,
                        uuid=uuid,
                        planarian=planarian,
                        record_type=record_type,
                    )
                    logger.info( f"Export done {f} ({n} rows)" )
                except Exception as e:
                    logger.exception(e)
        '''      
        result = group(jobs).apply_async()
        logger.info(f"{len(jobs)} exports launched group_id={result.id}")        
        return {"group_id": result.id,"jobs": len(jobs), }'''
    
 
@shared_task
def export_session_metrics_task(session_id):
    experiments = SessionExperiment.experiment_by_session(session_id, active=False)
    for experiment in experiments:
        export_experiment_metrics_task.delay(experiment.id)

    