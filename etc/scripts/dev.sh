#!/bin/bash
# Pile de développement sans sudo ni supervisor : redis, reductstore, web, celery worker + beat.
# usage: dev.sh deps|start|stop|status|logs
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/test_tube_scanner"
RUN="$ROOT/datas/run"
PY="$ROOT/.venv/bin/python"
mkdir -p "$RUN" "$ROOT/datas/reduct-media" "$APP/logs"

envget() { grep -E "^$1=" "$APP/.env" | tail -1 | cut -d= -f2-; }

running() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

launch() {  # launch nom commande...
    local n=$1; shift
    if running "$n"; then echo "  $n déjà démarré"; return; fi
    cd "$APP"
    setsid nohup "$@" >> "$RUN/$n.log" 2>&1 < /dev/null &
    echo $! > "$RUN/$n.pid"
    echo "  $n démarré (pid $!)"
}

case "$1" in
deps|start)
    [ -f "$APP/.env" ] || { echo "pas de .env : make env-dev"; exit 1; }
    echo "== services"
    command -v redis-server >/dev/null || { echo "redis-server absent: make deps-dev"; exit 1; }
    if redis-cli -p "$(envget REDIS_PORT)" ping >/dev/null 2>&1; then
        echo "  redis déjà actif (service système)"
    else
        launch redis redis-server --port "$(envget REDIS_PORT)" --bind 127.0.0.1 --dir "$RUN" --save ""
    fi
    RSBIN=$(command -v reductstore)
    [ -n "$RSBIN" ] || { echo "reductstore absent: make reductstore"; exit 1; }
    RS_DATA_PATH="$ROOT/datas/reduct-media" RS_API_TOKEN="$(envget REDUCTSTORE_TOKEN)" RS_PORT="$(envget REDUCTSTORE_PORT)" \
        launch reductstore "$RSBIN"
    sleep 2
    [ "$1" = deps ] && exit 0
    echo "== application"
    launch web "$PY" manage.py runserver 0.0.0.0:"$(envget SERVER_HOST_PORT)"
    FRESH=1; running worker && FRESH=0
    launch worker "$ROOT/.venv/bin/celery" -A home worker -l info
    launch beat "$ROOT/.venv/bin/celery" -A home beat -l info \
        --schedule "$RUN/celerybeat-schedule"
    if [ $FRESH = 1 ]; then   # une seule instance de ScannerProcess par worker
        sleep 6
        (cd "$APP" && "$PY" manage.py start_workers >> "$RUN/start_workers.log" 2>&1)
    fi
    echo "UI : http://localhost:$(envget SERVER_HOST_PORT)   (logs: make dev-logs)"
    ;;
stop)
    for n in beat worker web reductstore redis; do
        if running $n; then kill "$(cat "$RUN/$n.pid")" && echo "  $n arrêté"; fi
        rm -f "$RUN/$n.pid"
    done
    # celery fork des enfants
    pkill -f "celery -A home" 2>/dev/null || true
    ;;
status)
    redis-cli -p "$(envget REDIS_PORT)" ping >/dev/null 2>&1 && echo "  redis : actif" || echo "  redis : arrêté"
    for n in reductstore web worker beat; do
        running $n && echo "  $n : actif (pid $(cat "$RUN/$n.pid"))" || echo "  $n : arrêté"
    done
    ;;
logs)
    tail -n 40 -F "$RUN"/web.log "$RUN"/worker.log "$RUN"/beat.log "$RUN"/reductstore.log
    ;;
*) echo "usage: $0 deps|start|stop|status|logs"; exit 1 ;;
esac
