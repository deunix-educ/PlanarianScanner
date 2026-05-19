
import logging
import asyncio

from asgiref.sync import async_to_sync
from django.conf import settings
from modules.planarian_metrics import ReductStoreClient

logger = logging.getLogger(__name__)


def _get_reduct_client() -> ReductStoreClient:
    """Instancie le client ReductStore depuis les settings Django."""
    return ReductStoreClient(url=settings.REDUCTSTORE_URL, token=settings.REDUCTSTORE_TOKEN)


def export_csv_sync(
    *,
    experiment,
    well,
    uuid,
    planarian,
    record_type,
    start=None,
    stop=None,
):
    #@async_to_sync
    async def _run():
        client = _get_reduct_client()

        await client.connect()
        return await client.export_csv_response(
            experiment=experiment,
            well=well,
            uuid=uuid,
            planarian=planarian,
            record_type=record_type,
            start=start,
            stop=stop,
        )
    #return _run()
    return asyncio.run(_run())

def export_csv_file_sync(
    *,
    experiment,
    well,
    uuid,
    planarian,
    record_type,
):
    async def _run():
        client = _get_reduct_client()

        await client.connect()
        try:
            return await client.export_csv(
                experiment=experiment,
                well=well,
                uuid=uuid,
                planarian=planarian,
                record_type=record_type,
                output_dir=settings.CSV_EXPORT_DIR,
            )
        finally:
            await client.close()
    return asyncio.run(_run())

