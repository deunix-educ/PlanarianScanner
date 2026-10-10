#!/usr/bin/env python3
"""Test de bout en bout en simulation : caméra = fichier vidéo, CNC = grbl_simulator.

Prérequis : make install-dev (puis make dev, ou ce script le démarre).
Scénario : config capture 'file' -> expérience sur le multi-puits HG (3 puits, 2 s chacun)
           -> session -> commande 'scan' via redis (comme l'interface web)
           -> attend la fin du balayage et vérifie les frames dans ReductStore.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "test_tube_scanner"
DEV = ROOT / "etc" / "scripts" / "dev.sh"
WELLS = ["A1", "A2", "A3"]
DURATION = 2
TIMEOUT = 120

sys.path.insert(0, str(APP))
os.chdir(APP)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "home.settings")

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"  [{'OK' if cond else 'ECHEC'}] {label} {extra}")
    ok &= bool(cond)
    return cond


def main():
    # dev.sh start ne touche pas aux services déjà lancés ; on sait si une config change
    import django
    django.setup()
    from django.conf import settings
    from django.utils import timezone
    from redis import Redis
    from reduct import Client
    from scanner import models

    print("== configuration")
    check("GRBL_SIMULATION actif (.env)", settings.GRBL_SIMULATION is True)
    check("vidéo de simulation présente", (settings.MEDIA_ROOT / "simulation" / "default_simulation.mp4").exists(),
          "(make sim-videos)")
    conf = models.Configuration.objects.filter(active=True).first()
    if not check("Configuration active en base", conf is not None, "(make fixtures)"):
        return 1
    changed = conf.capture_type != "file" or conf.tracking
    if changed:
        conf.capture_type, conf.tracking = "file", False
        conf.save()
        print("  capture_type=file : redémarrage de la pile dev")
        subprocess.run([str(DEV), "stop"], check=False)
        time.sleep(2)
    subprocess.run([str(DEV), "start"], check=True)
    time.sleep(8)  # ScannerProcess.start (celery) + GRBL simulé

    print("== interface web")
    port = settings.SERVER_HOST_PORT
    try:
        code = urllib.request.urlopen(f"http://127.0.0.1:{port}/login/", timeout=10).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = str(e)
    check("HTTP répond", code in (200, 301, 302, 403), f"({code})")

    print("== session de balayage")
    mw = models.MultiWell.objects.get(position="HG")
    exp = models.Experiment.objects.create(title="test-sim", multiwell=mw, duration=DURATION,
                                           created=timezone.now())
    models.ExperimentWell.objects.filter(experiment=exp).exclude(well__name__in=WELLS).update(active=False)
    sess = models.Session.objects.create(name="test-sim")
    models.SessionExperiment.objects.create(session=sess, experiment=exp)
    check("puits actifs", models.ExperimentWell.wellname_by_experiment(exp.id) == WELLS)

    r = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
    n = r.publish("scanner_proc", json.dumps({"type": "scanner", "topic": "scan", "session": str(sess.id)}))
    check("commande reçue par le worker (abonné redis)", n >= 1, f"({n} abonné)")

    t0 = time.time()
    while time.time() - t0 < TIMEOUT:
        sess.refresh_from_db()
        if not sess.active:
            break
        time.sleep(2)
    check("balayage terminé", not sess.active, f"({time.time() - t0:.0f}s)")

    print("== frames ReductStore")

    async def count():
        client = Client(settings.REDUCTSTORE_URL, api_token=settings.REDUCTSTORE_TOKEN)
        bucket = await client.get_bucket("camera")
        info = await bucket.get_full_info()
        names = {e.name: e.record_count for e in info.entries}
        return names
    try:
        entries = asyncio.run(count())
    except Exception as e:
        entries = {}
        print("  erreur reductstore:", e)
    for w in WELLS:
        uuid = f"{sess.id}-HG-{w}"
        check(f"frames {uuid}", entries.get(uuid, 0) > 0, f"({entries.get(uuid, 0)})")

    print("\nRESULTAT :", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
