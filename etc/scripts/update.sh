#!/bin/bash
# Mise à jour sur le Raspberry (appelée par `make update`) :
#   sauvegarde BDD -> git pull (sauf --no-git) -> pip -> migrate -> collectstatic -> restart
# Fonctionne en local ou via ssh (LAN ou tunnel WireGuard) : `make remote-update TARGET=user@hote`.
# En cas d'échec après le pull : revenir avec `git reset --hard <commit affiché>` + make update --no-git.
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/test_tube_scanner"
PY="$ROOT/.venv/bin/python"
NOGIT=0; BRANCH=""
for a in "$@"; do case "$a" in --no-git) NOGIT=1 ;; *) BRANCH="$a" ;; esac; done
cd "$ROOT"
[ -f "$APP/.env" ] || { echo "pas de .env"; exit 1; }
envget() { grep -E "^$1=" "$APP/.env" | tail -1 | cut -d= -f2-; }

echo "== commit actuel : $(git rev-parse --short HEAD 2>/dev/null || echo inconnu)"

if [ "$(envget MARIADB)" = "default" ]; then
    D="$(envget BACKUP_DIR)"; mkdir -p "$D"
    F="$D/pre-update-$(date +%Y%m%d-%H%M%S).sql.gz"
    echo "== sauvegarde BDD -> $F"
    MYSQL_PWD="$(envget DATABASE_PASSWORD)" mysqldump -u "$(envget DATABASE_USER)" \
        "$(envget DATABASE_NAME)" | gzip > "$F" || echo "(!) sauvegarde impossible, on continue"
fi

if [ $NOGIT = 0 ]; then
    echo "== git pull"
    git diff --quiet || { echo "modifications locales non commitées : abandon"; git status --short; exit 1; }
    git fetch --prune
    [ -n "$BRANCH" ] && git checkout "$BRANCH"
    git pull --ff-only
fi

echo "== dépendances"
"$ROOT/.venv/bin/pip" install -q -r "$ROOT/etc/requirements.txt"

cd "$APP"
echo "== migrations / statiques / traductions"
"$PY" manage.py migrate --noinput
"$PY" manage.py collectstatic --noinput -v0
"$PY" manage.py compilemessages -v0 2>/dev/null || true

if command -v supervisorctl >/dev/null && sudo -n supervisorctl status test_tube:* >/dev/null 2>&1; then
    echo "== redémarrage"
    sudo supervisorctl restart test_tube:*
elif [ -x "$ROOT/etc/scripts/dev.sh" ] && [ -f "$ROOT/datas/run/web.pid" ]; then
    "$ROOT/etc/scripts/dev.sh" stop; "$ROOT/etc/scripts/dev.sh" start
else
    echo "(!) aucun service à redémarrer"
fi
echo "== OK : $(cd "$ROOT"; git rev-parse --short HEAD 2>/dev/null)"
