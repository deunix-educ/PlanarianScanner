#!/bin/bash
# Chien de garde caméra : redémarre test_tube:services si plus aucune frame n'a été capturée
# depuis STALE_S secondes.
#
# Contexte : un défaut matériel intermittent (ex. ruban CSI qui perd le contact pendant un
# déplacement du bras CNC) peut figer l'appel Picamera2 à l'intérieur de capture_frame() sans
# jamais lever d'exception Python (voir REPRISE.md) — le thread de capture reste bloqué
# indéfiniment, rien ne le détecte depuis l'intérieur du process Celery.
#
# Ce script tourne HORS de ce process (timer systemd camera-watchdog.timer, voir
# etc/templates/camera-watchdog.*.in), donc il n'est jamais lui-même concerné par le blocage.
# Il s'appuie sur le fichier de battement touché à chaque frame par capture_interface.py
# (VideoCaptureInterface.HEARTBEAT_PATH) : absent = capture jamais démarrée ou arrêtée
# proprement (rien à faire) ; trop vieux = blocage réel -> redémarrage.
#
# usage : camera_watchdog.sh   (root via systemd ; sudo en exécution manuelle)
set -u
HEARTBEAT=/tmp/planarian_camera_heartbeat
STALE_S=25

[ -f "$HEARTBEAT" ] || exit 0

now=$(date +%s)
mtime=$(stat -c %Y "$HEARTBEAT" 2>/dev/null) || exit 0
age=$(( now - mtime ))

[ "$age" -gt "$STALE_S" ] || exit 0

logger -t camera-watchdog "aucune frame caméra depuis ${age}s (seuil ${STALE_S}s) — redémarrage de test_tube:services"
supervisorctl restart test_tube:services
