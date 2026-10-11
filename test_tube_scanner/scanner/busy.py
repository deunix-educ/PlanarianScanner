'''
scanner/busy.py
    Indicateur « balayage / test de calibration en cours » partagé via Redis.

    Le MultiWellManager vit dans le process worker, les vues dans le process web :
    le worker publie un battement (clé avec TTL) tant qu'un thread scan/test tourne,
    les vues le lisent. Si le worker meurt, la clé expire seule.
'''
from threading import Thread
import time

from django.conf import settings
from redis import Redis

KEY = "scanner:busy"
TTL = 30       # secondes
BEAT = 5       # secondes entre deux battements

_redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)


def get_busy() -> str | None:
    """'scan', 'test' ou None."""
    try:
        return _redis.get(KEY)
    except Exception:
        return None


def start_heartbeat(get_kind) -> None:
    """Lance un thread qui publie get_kind() ('scan'/'test'/None) tant qu'il n'est pas None."""
    def _beat():
        try:
            while True:
                kind = get_kind()
                if not kind:
                    break
                _redis.set(KEY, kind, ex=TTL)
                time.sleep(BEAT)
        except Exception:
            pass
        finally:
            try:
                _redis.delete(KEY)
            except Exception:
                pass
    Thread(target=_beat, daemon=True).start()
