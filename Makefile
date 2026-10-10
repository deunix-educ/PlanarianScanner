# PlanarianScanner — installation, développement (RPi5) et production (RPi4)
# `make help` pour la liste des cibles.

ROOT          := $(CURDIR)
APP           := $(ROOT)/test_tube_scanner
VENV          := $(ROOT)/.venv
PY            := $(VENV)/bin/python
PIP           := $(VENV)/bin/pip
MANAGE        := cd $(APP) && $(PY) manage.py
S             := $(ROOT)/etc/scripts

export APP_USER         ?= $(shell id -un)
export ROOT
PYTHON3 := python3
export SCANNER_HOSTNAME ?= scanner
export REDUCT_DATA      ?= $(ROOT)/datas/reduct-media
export REDUCT_BIN       ?= /usr/local/bin/reductstore
export SUP_BIND         ?= 0.0.0.0
TARGET ?=

APT_COMMON := build-essential openssl git pkg-config python3-dev python3-pip python3-venv \
              libpq-dev libmariadb-dev default-libmysqlclient-dev gettext curl rsync \
              python3-picamera2 samba-common cifs-utils smbclient
APT_PROD   := redis-server supervisor nginx mariadb-server avahi-daemon avahi-utils libnss-mdns
APT_DEV    := redis-server sqlite3

.DEFAULT_GOAL := help
.PHONY: help deps-dev deps-prod venv env-dev env-prod reductstore db fixtures sim-videos \
        install-dev sim-config dev-deps dev dev-stop dev-status dev-logs test-sim \
        install-prod mariadb services nginx adminer hostname hostname-check wireguard wg-up wg-down wireguard-status \
        update remote-update deploy status clean-dev

help:  ## cette aide
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- commun
deps-dev:  ## paquets apt de développement (RPi5)
	sudo apt-get update && sudo apt-get install -y $(APT_COMMON) $(APT_DEV)

deps-prod:  ## paquets apt de production (RPi4)
	sudo apt-get update && sudo apt-get install -y $(APT_COMMON) $(APT_PROD)

venv: $(VENV)/.ok  ## virtualenv + requirements (system-site-packages pour picamera2)
$(VENV)/.ok: etc/requirements.txt
	test -d $(VENV) || python3 -m venv --system-site-packages $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install -r etc/requirements.txt
	touch $@

env-dev:  ## crée test_tube_scanner/.env (sqlite, simulation GRBL) si absent
	$(PYTHON3) $(S)/mkenv.py dev
env-prod:  ## crée test_tube_scanner/.env (MariaDB, matériel réel) si absent
	$(PYTHON3) $(S)/mkenv.py prod --hostname $(SCANNER_HOSTNAME)

reductstore:  ## binaire ReductStore précompilé (pas de compilation cargo)
	sudo $(S)/reductstore.sh

db:  ## migrations + superuser + planification
	mkdir -p $(ROOT)/datas $(APP)/logs $(APP)/media/images $(APP)/media/simulation
	touch $(APP)/logs/celery.log $(APP)/logs/test_tube.log
	$(MANAGE) makemigrations scanner planarian --noinput
	$(MANAGE) migrate --noinput
	$(MANAGE) init_data

fixtures: db  ## configuration, puits, multiwell
	$(MANAGE) loaddata $(ROOT)/etc/db/configuration.json $(ROOT)/etc/db/well.json $(ROOT)/etc/db/multiwell.json
	$(MANAGE) reset_all_well_position --all True

sim-videos:  ## 1 vidéo de simulation par défaut (make sim-videos ALL=1 pour les 24 puits)
	cd $(APP) && OUT_DIR=$(APP)/media/simulation PATH=$(VENV)/bin:$$PATH ./make_videos.sh $(if $(ALL),all)

# ---------------------------------------------------------------- développement (RPi5)
sim-config:  ## capture = fichier vidéo (caméra simulée) ; GRBL simulé via .env
	$(MANAGE) shell -c "from scanner.models import Configuration as C; C.objects.filter(active=True).update(capture_type='file', tracking=False)"

install-dev: deps-dev venv env-dev reductstore dev-deps fixtures sim-config sim-videos  ## tout installer en dev
	$(MANAGE) collectstatic --noinput -v0
	@echo "OK -> make dev"

dev-deps:  ## redis + reductstore seuls (requis même pour migrate : le code s'y connecte à l'import)
	$(S)/dev.sh deps
dev:  ## démarre redis, reductstore, web, celery (sans sudo ni supervisor)
	$(S)/dev.sh start
dev-stop:  ## arrête la pile de dev
	$(S)/dev.sh stop
dev-status:
	$(S)/dev.sh status
dev-logs:
	$(S)/dev.sh logs

test-sim:  ## test de bout en bout en simulation caméra (fichier) + CNC GRBL simulée
	$(PY) $(S)/test_sim.py

clean-dev:  ## supprime base sqlite et données de dev (datas/)
	$(S)/dev.sh stop; rm -rf $(ROOT)/datas

# ---------------------------------------------------------------- production (RPi4)
install-prod: deps-prod hostname venv env-prod reductstore mariadb services fixtures sim-videos nginx adminer  ## installation complète RPi4
	$(MANAGE) collectstatic --noinput -v0
	sudo supervisorctl restart test_tube:*
	@echo "OK -> http://$(SCANNER_HOSTNAME).local"

mariadb:  ## MariaDB + base/utilisateur depuis .env
	$(S)/mariadb.sh

services:  ## supervisor : reductstore + group test_tube (webUI daphne, beat, workers)
	mkdir -p $(ROOT)/datas/reduct-media
	chmod +x $(APP)/run-*.sh
	WEB_CMD=run-daphne.sh $(S)/render.sh etc/templates/scanner_service.conf.in /tmp/scanner_service.conf
	RS_TOKEN=$$(grep -E "^REDUCTSTORE_TOKEN=" $(APP)/.env | cut -d= -f2-) $(S)/render.sh etc/templates/reductstore_service.conf.in /tmp/reductstore_service.conf
	$(S)/render.sh etc/templates/supervisor-inet_http.conf.in /tmp/supervisor-inet_http.conf
	sudo install -m 644 /tmp/scanner_service.conf /tmp/supervisor-inet_http.conf /etc/supervisor/conf.d/
	sudo install -m 600 /tmp/reductstore_service.conf /etc/supervisor/conf.d/   # contient le token
	rm -f /tmp/reductstore_service.conf
	sudo systemctl enable --now supervisor
	sudo supervisorctl reread && sudo supervisorctl update
	sleep 3

nginx:  ## reverse proxy port 80 -> daphne (+ static/media)
	$(S)/render.sh etc/templates/nginx_service.conf.in /tmp/scanner.nginx
	sudo install -m 644 /tmp/scanner.nginx /etc/nginx/sites-available/scanner
	sudo ln -sf /etc/nginx/sites-available/scanner /etc/nginx/sites-enabled/scanner
	sudo rm -f /etc/nginx/sites-enabled/default
	sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx

adminer:  ## Adminer (php-fpm) sur /adminer/ (nginx déjà configuré)
	sudo $(S)/adminer.sh

hostname:  ## scanner.local via Avahi/mDNS (SCANNER_HOSTNAME=nom pour changer)
	sudo $(S)/hostname.sh $(SCANNER_HOSTNAME)
hostname-check:  ## diagnostic de scanner.local
	$(S)/hostname.sh --check $(SCANNER_HOSTNAME)

wireguard:  ## client WireGuard, à la demande (WG_CONF=fichier.conf, sinon génère clés + modèle)
	sudo $(S)/wireguard.sh install $(WG_CONF)
wg-up:  ## monte le tunnel WireGuard (avant une mise à jour distante)
	sudo $(S)/wireguard.sh up
wg-down:  ## coupe le tunnel WireGuard
	sudo $(S)/wireguard.sh down
wireguard-status:  ## état du tunnel
	sudo $(S)/wireguard.sh status

# ---------------------------------------------------------------- mises à jour
update:  ## sur le Raspberry : sauvegarde BDD, git pull, pip, migrate, static, restart
	$(S)/update.sh $(UPDATE_ARGS)

remote-update:  ## depuis un poste (LAN ou VPN) : make remote-update TARGET=pi@10.8.0.10
	@test -n "$(TARGET)" || { echo "TARGET=user@hote requis"; exit 1; }
	ssh -t $(TARGET) 'cd PlanarianScanner && make update'

deploy:  ## sans accès git sur le RPi : rsync du code puis update --no-git (TARGET=user@hote)
	@test -n "$(TARGET)" || { echo "TARGET=user@hote requis"; exit 1; }
	rsync -az --delete --exclude .git --exclude .venv --exclude datas --exclude '.env' \
	  --exclude __pycache__ --exclude 'test_tube_scanner/media' --exclude 'test_tube_scanner/staticfiles' \
	  --exclude 'test_tube_scanner/logs' ./ $(TARGET):PlanarianScanner/
	ssh -t $(TARGET) 'cd PlanarianScanner && make update UPDATE_ARGS=--no-git'

status:  ## état des services (prod)
	-sudo supervisorctl status
	-systemctl is-active nginx mariadb redis-server avahi-daemon wg-quick@wg0
