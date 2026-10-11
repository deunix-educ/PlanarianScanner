# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Le contexte technique complet (matériel, stack, modèles, modules, mode vidéo plaque, déploiement) est dans @CONTEXT.md : le lire d'abord, il n'est pas dupliqué ici. Ce fichier ne contient que ce qui n'y figure pas.

## Commandes

Tout passe par le `Makefile` (`make help`). En dev (RPi5, sqlite, caméra = fichier vidéo, GRBL simulé) :

```bash
make install-dev      # apt, venv, .env, ReductStore, db, fixtures, vidéos de simulation
make dev / dev-stop   # redis + reductstore + web + celery
make dev-deps         # redis + reductstore seuls
make test-sim         # test de bout en bout : balayage de 3 puits, frames vérifiées dans ReductStore
```

Il n'y a pas de linter configuré. Les fichiers `tests.py` (`scanner`, `planarian`) sont vides ; le seul test existant est `etc/scripts/test_sim.py` (via `make test-sim`). Pas de test unitaire unique à lancer.

Commandes Django : depuis `test_tube_scanner/`, avec `../.venv/bin/python manage.py …`. Les commandes de management du projet sont dans `home/management/commands/` (pas dans `scanner/`), par ex. `init_data`, `reorder_well_positions`, `reset_all_well_position`, `start_workers`.

## Pièges

- **Django installé : 6.0** (CONTEXT.md dit 5.1). `ADMINS`/`MANAGERS` doivent être des listes d'emails ; les identifiants du superuser initial sont dans `settings.INITIAL_USERS`.
- **Redis et ReductStore doivent tourner avant tout `manage.py`** (`migrate`, `shell`, `check`…) : `scanner/process.py` s'y connecte à l'import. Un `manage.py` qui échoue à l'import vient presque toujours de là.
- **URLs préfixées par la langue** : `/fr-fr/scanner/calibration/`. Un test avec `Client` sans préfixe renvoie 302. Les URLs de `scanner/urls.py` sont dans le namespace `scanner:` (`{% url 'scanner:reorder_wells_api' %}`).
- `.env` est ignoré par git et contient des secrets : ne jamais le lire en entier ni le commiter. Il est généré par `etc/scripts/mkenv.py`.

## Architecture : deux processus qui ne partagent pas la mémoire

- **Process web** (daphne/ASGI) : vues Django (`scanner/views.py`) et consumers WebSocket (`scanner/consumers.py`, route `ws/scanner`).
- **Process worker** (tâches Celery lancées par `start_workers`) : `scanner/process.py` (`ScannerProcess`) possède la caméra, le contrôleur GRBL et le `MultiWellManager` (`scanner/multiwell.py`), qui gère les threads `scan_thread`/`test_thread`.

Conséquences :
- Le web ne peut pas lire l'état du manager directement. Les commandes d'UI (calibration, balayage) passent par le WebSocket puis Redis pub/sub (`_listen_to_redis` dans `process.py`) ; l'état partagé simple passe par Redis (voir `scanner/busy.py` : clé à TTL « balayage en cours », lue par les vues).
- Un changement de `WellPosition`/`MultiWell` en base n'est vu par le manager qu'après un changement de position (`set_multiwell` → `init_manager_values`), car il garde une liste en mémoire (`WellIterator`).
- Après modification de code worker, redémarrer les workers (`make update` ou supervisor).

## Ordre de lecture des puits

L'ordre de balayage est `WellPosition.order`, généré par le signal `create_well_position` (`scanner/models.py`) en **serpentin** selon `MultiWell.row_def` (ex. `D,C,B,A` → D1..D6, C6..C1, B1..B6, A6..A1). `x = xbase + col*dx` suit la colonne physique ; l'ordre 0 doit être le puits d'origine `xbase/ybase`. Le signal ne tourne que si `well_position=False` et **réécrit alors x/y** (perd la calibration). Pour ne changer que l'ordre : `manage.py reorder_well_positions [--position XX] [--realign-base] [--dry-run]`, ou le bouton « Réordonner les puits » de la page calibration (refusé pendant un balayage/test).

## Données de simulation

Capture simulée : `Configuration.capture_type='file'` (`media/simulation/<puit>.mp4`) ou `'video'` (plaque entière, crop dynamique, voir CONTEXT.md). `VideoPlate.px_per_mm` (~15) et `WellPosition.px_per_mm` (~50) sont deux échelles différentes ; ne pas les confondre.
