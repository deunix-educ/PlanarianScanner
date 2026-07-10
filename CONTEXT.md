# PlanarianScanner — Contexte technique

Système d'imagerie automatisé pour le suivi comportemental de planaires (*Platyhelminthes*).
Développé par dd@linuxtarn.org pour le **Laboratoire de Biologie, Université Champollion, Albi**.

---

## Matériel cible

| Composant | Détail |
|---|---|
| Carte | Raspberry Pi 4 |
| Caméra | ArduCam haute définition (Picamera2) |
| Motorisation | Bras CNC L2544 piloté en GRBL via port série |
| Grille | 4 plaques multi-puits de 6×4 = 96 puits (Ø 16 mm) |
| Réseau | LAN — export Samba (CIFS) / rsync SSH |

---

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Django 5.1 + Django Channels (WebSocket) |
| Serveur ASGI | Daphne |
| Broker/cache | Redis |
| Tâches async | Celery + django-celery-beat (one-shot via ClockedSchedule) |
| Vision | OpenCV (headless) + Picamera2 |
| Stockage frames | ReductStore (base time série haute performance) |
| BDD | MariaDB (prod) — sqlite3 (dev) |
| Export distant | Samba client (CIFS) / rsync |
| Plateforme | Raspberry Pi 4, Debian 64-bit Trixie |
| Python | 3.13 — venv dans `.venv/` |

---

## Structure du dépôt

```
PlanarianScanner/
├── etc/                        # Scripts d'installation et configs système
│   ├── 1-install-sys.sh        # Dépendances système
│   ├── 2-cargo-reductstore-install.sh  # Build ReductStore (~15 min sur RPi4)
│   ├── 3-install-samba-client.sh
│   ├── 4-install_mariadb.sh
│   ├── 5-install_adminer.sh
│   ├── 6-install_django_app.sh # Init Django (migrations, fixtures, collectstatic)
│   ├── db/                     # Fixtures JSON initiales (configuration, multiwell, well)
│   ├── requirements.txt
│   ├── scanner_service.conf    # Supervisor : Django + Celery workers
│   ├── reductstore_service.conf
│   └── nginx_service.conf
├── datas/                      # Données hors Django (gitignored)
│   ├── medias/                 # Images et vidéos capturées
│   ├── exports/csv/            # Exports CSV EthoVision
│   ├── remote/exports/         # Dossier cible des transferts distants
│   └── backup/mariadb/         # Sauvegardes MariaDB
├── assets/                     # Logo, screenshots
├── test_tube_scanner/          # Racine du projet Django
│   ├── home/                   # Package projet (settings, urls, wsgi, asgi, celery)
│   ├── scanner/                # App scanner (CNC, multi-puits, sessions, exports)
│   ├── planarian/              # App suivi planaires (métriques, export CSV)
│   ├── modules/                # Modules partagés (capture, GRBL, tracker, metrics…)
│   ├── manage.py
│   ├── run-server.sh
│   ├── run-workers.sh
│   ├── planarian_sim.py        # Simulateur standalone (CLI)
│   └── .env / .env.example
└── browser.py                  # Ouverture navigateur local (utilitaire)
```

---

## Applications Django

### `scanner` — Pilotage CNC et acquisition

Modèles principaux :

| Modèle | Rôle |
|---|---|
| `Configuration` | Config globale active (caméra, GRBL, tracking, calibration) |
| `MultiWell` | Plaque multi-puits (position HG/HD/BG/BD, grille 6×4, pas XY, crop_radius) |
| `Well` | Puit individuel (nom Ai..Di) |
| `WellPosition` | Position XY mm d'un puit dans un MultiWell + px_per_mm (calibration optique caméra) |
| `VideoPlate` | Vidéo plaque entière associée à un MultiWell — champs : `px_per_mm` (échelle vidéo ~15 px/mm), `x_origin_mm` / `y_origin_mm` (origine CNC stable, indépendante de la calibration) |
| `Experiment` | Session de capture sur un MultiWell (durée, début/fin) |
| `Session` | Groupe d'expériences avec planification (ClockedSchedule one-shot) |
| `SessionExperiment` | Liaison Session ↔ Experiment |
| `ExperimentWell` | Liaison Experiment ↔ Well (puits actifs) |

Signaux Django :
- `post_save(MultiWell)` → génère automatiquement les `WellPosition` en serpentin
- `post_save(Session)` → crée les `PeriodicTask` Celery Beat (export + scanning)
- `post_delete(Session)` → supprime les `PeriodicTask` associées

Tâches Celery (`scanner/tasks.py`, `scanner/export_tasks.py`) :
- `run_scanning(session_id)` — parcours serpentin des puits (GRBL + capture)
- `run_session_exports(session_id)` — génération ZIP JPEG + MP4 + transfert distant

### `planarian` — Suivi multi-individus et métriques

Modèle `ExperimentConfig` : paramètres de tracking par puit (px_per_mm, fps, seuils).

---

## Modules partagés (`modules/`)

| Module | Rôle |
|---|---|
| `grbl.py` | Pilotage CNC via port série (G-code, homing, déplacement XY) |
| `grbl_simulator.py` | Simulateur GRBL pour dev sans matériel |
| `capture_interface.py` | Interface abstraite de capture — crop circulaire, edge enhance, debug overlay, tracking |
| `picamera2_capture.py` | Capture ArduCam via Picamera2 |
| `webcam_capture.py` | Capture webcam via OpenCV |
| `videofile_capture.py` | Lecture fichier vidéo (test/sim) |
| `videoplate_capture.py` | Capture par crop dynamique dans une vidéo plaque entière — position GRBL → région extraite, hot swap vidéo, plein cadre à l'origine |
| `planarian_tracker.py` | Tracking multi-individus : MOG2 + algorithme hongrois (`scipy`) |
| `planarian_metrics.py` | Métriques par frame et summary (mobilité, thigmo, photo, chemo, social) |
| `tube_aligner.py` | Détection HoughCircles + CLAHE, calibration optique, plage rayon configurable (`set_radius_range`) |
| `circular_crop.py` | Découpe circulaire des images de puit |
| `reductstore.py` | Interface ReductStore (stockage/lecture frames time série) |
| `system_stats.py` | Stats système (CPU, RAM, disque — affichage dashboard) |

---

## Métriques de tracking

**Par frame** : velocity, distance, moving, mobility_state, dist_to_wall_mm, near_wall,
dist_to_light_mm, heading_to_light_deg, fleeing_light, dist_to_food_mm, heading_to_food_deg,
approaching_food, in_food_zone, nearest_neighbour_mm, in_avoid_zone, in_aggreg_zone,
chem_repulsion_level.

**Summary** : totaux et pourcentages EthoVision-compatibles pour mobilité, thigmotactisme,
phototactisme, chimiotactisme, interactions sociales.

Export CSV compatible **EthoVision XT**.

---

## Configuration runtime

Fichier `.env` (python-decouple) dans `test_tube_scanner/` :

```
SECRET_KEY, DEBUG, DOMAIN_SERVER, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
APP_DATAS          # chemin relatif vers datas/ (ex: ../datas)
DJANGO_APP         # nom de l'app (home)
REDIS_URL          # ex: redis://localhost:6379/0
REDUCTSTORE_URL    # ex: http://localhost:8383
DB_*               # MariaDB credentials
```

---

## Démarrage des services

Tous gérés par **Supervisor** :

```bash
# Interface web Supervisor
http://root:toor@<ip>:9001

# CLI
sudo supervisorctl start|stop|restart reductstore
sudo supervisorctl start|stop|restart test_tube:*
```

En dev :
```bash
cd test_tube_scanner
./manage.py runserver 0.0.0.0:8000
# Workers Celery séparés :
./run-workers.sh
```

Accès réseau : ajouter `<ip-rpi4> scanner.local` dans `/etc/hosts` des clients.

---

## Simulateur standalone

`test_tube_scanner/planarian_sim.py` — simulation CLI d'une arène circulaire (Ø 16 mm, 500×500 px),
export CSV EthoVision par planaire.

```bash
python3 planarian_sim.py --count 5 --thigmotaxis 0.4
python3 planarian_sim.py --count 5 --photo-mode fixed --photo-x 0.2 --photo-y 0.2 --photo-strength 0.6
```

`test_tube_scanner/make_videos.sh` — génération de 24 vidéos de simulation (une par puit).

---

## Mode capture vidéo plaque (`capture_type == 'video'`)

Alternative à la caméra ArduCam : une **vidéo de la plaque entière** enregistrée une fois,
rejouée en boucle pendant les scans. Adapté aux labos sans Raspberry Pi ou pour tests hors matériel.

### Flux
```
VideoPlateCapture.capture_frame()
  → lit la frame courante de la vidéo
  → extrait un carré 2r×2r centré sur (GRBL_x, GRBL_y) converti en pixels
  → si GRBL à (0,0) : retourne la frame entière (vue plaque)
  → sinon          : retourne le crop du puit courant
→ process_frame()
  → edge_enhance (optionnel, CLAHE + Canny overlay vert)
  → TubeAligner.detect_tube() (optionnel, debug HoughCircles)
  → crop circulaire (optionnel)
```

### Calibration vidéo
- `VideoPlate.px_per_mm` : échelle de la vidéo (~15 px/mm) — **différent** de `WellPosition.px_per_mm` (~50 px/mm, optique caméra)
- `VideoPlate.x_origin_mm` / `y_origin_mm` : position CNC correspondant au pixel (0,0) de la vidéo — **stable**, jamais modifiée par la calibration des puits
- `MultiWell.crop_radius` : rayon du crop en pixels — contrôle la taille de la vue par puit

### Contrôles calibration UI (boutons)
| Bouton | Action |
|---|---|
| Debug | Active `TubeAligner.debug` — détection HoughCircles en continu |
| Overlay | Affiche/masque les annotations de détection sans couper la détection |
| Contours | Active edge enhance (CLAHE + Canny overlay vert) sur la frame propre |
| Recadrer | Active le crop circulaire + navigue vers la position Base (mode vidéo) |

### `TubeAligner.set_radius_range(min_ratio, max_ratio)`
Ajuste la plage de recherche HoughCircles en fraction de `min(w,h)` :
- Mode caméra : `0.26–0.37` (tube occupe ~30% du champ)
- Mode vidéo  : `0.38–0.47` (puit remplit le crop, ratio ~0.43–0.50)

---

## Déploiement réseau isolé (labo sans internet)

```
GitHub ←→ Portable (internet) ←→ Routeur OpenWrt ←→ Machine labo (SSH)
```

Mise à jour sans internet :
```bash
# Sur la machine labo (une fois)
git config receive.denyCurrentBranch updateInstead

# Sur le portable — ajouter le labo comme remote
git remote add labo ssh://user@<ip-labo>/chemin/PlanarianScanner

# Workflow répétable
git pull origin video-plate-calibration   # portable ← GitHub
git push labo video-plate-calibration     # labo ← portable
```

---

## Licence

GPL-3.0

