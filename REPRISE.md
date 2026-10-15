# Reprise de session — PlanarianScanner

Note de passage entre postes. Le contexte technique est dans `CONTEXT.md`, les pièges et
l'architecture dans `CLAUDE.md` : les lire d'abord, ce fichier ne contient que l'état du travail.

État au **2026-10-15** — branche `video-plate-calibration` (dernier commit : voir `git log`).

**Fonctionnement vérifié** après les modifications du 2026-10-15 (conflit de merge `views.py`, recréation
supervisor/nginx, nettoyage page calibration, champs hauteur/largeur plaque, bras virtuel en GRBL réel) :
`manage.py check` OK, pages `calibration` et `scanning` rendues (HTTP 200) via le client de test Django en
simulation et en GRBL réel simulé (`override_settings(GRBL_SIMULATION=False)`), `supervisorctl status` tous
`RUNNING`, `nginx -t` OK.

## Fait

- **Plaques partielles** (`rows` > lettres de `row_def`, ex. HD_6 : `B,A`) : plus d'`IndexError`
  (`serpentine_names`, `uuid_from_session`, `multiwell_buttons`, `multiwell_cards`).
- **Erreurs worker visibles** : une exception dans `_listen_to_redis` envoie `state='error'` à l'UI ; le JS de
  réordonnancement affiche `Erreur serveur : HTTP <code>`.
- **Page calibration** : boutons de déplacement en croix (+Y haut, -X / Sauver / +X, -Y bas) ; grille des puits
  A en haut → D en bas avec les flèches du serpentin.
- **Vue isométrique du bras CNC** (simulation PC) : voir « Vue isométrique » dans `CONTEXT.md`. Caméra sous un
  plateau transparent, objectif vers le haut, éclairage au-dessus ; animation des déplacements (événement `move`
  du simulateur) ; zoom et agrandissement dans la page ; seules les plaques **actives** sont posées.
- **Liste déroulante de la calibration** : seuls les multi-puits `active=True` sont proposés.
- **Téléchargement de vidéo depuis le replay** (bouton vidéo) : `shm_download_video` ne créait jamais le
  `VideoWriter` (`video = None` avant `'video' not in locals()`) et le navigateur enregistrait le JSON d'erreur
  comme « vidéo » ; corrigé (fichier unique par téléchargement, erreurs en HTTP 500, alerte côté page). L'export
  par lot (`export_videos`) n'était pas concerné.
- **Vue CNC sur la page balayage multi-puits** : même composant ; la plaque suivie vient du champ `position` des
  messages du worker (`process.py`, `multiwell.py`) ; boutons zoom / agrandir partagés (`bindControls`).
- `CONTEXT.md` : Django 6.0, règle d'implantation des plaques, vue CNC.
- **Conflit de merge non résolu commité** (`views.py::scanning_view`, marqueurs `Updated upstream` /
  `Stashed changes`) : résolu en gardant la branche qui définit `context`/`capture_type` (utilisés juste après),
  `manage.py check` + `py_compile` OK, commit amendé et re-poussé en force.
- **Mise à jour du RPi4 (prod)** effectuée ; a fait perdre les configs supervisor/nginx (voir Pièges) — recréées
  via `make services` / `make nginx`.
- **Page calibration** : retrait de la case « Simulation (dry-run) » et du bouton « Réordonner les puits » (plus
  leur JS mort associé) ; bouton ARRET déplacé sous « Tester le circuit ».
- **`MultiWell`** : ajout `plate_height` (85.48 mm) et `plate_width` (127.76 mm), placés dans le fieldset
  « Géométrie » de l'admin ; migration `0014_multiwell_plate_height_multiwell_plate_width`.
- **Bras virtuel disponible en GRBL réel** (pas seulement en simulation/vidéo) : le message websocket `xy`
  (position faisant foi) est déjà envoyé sans condition par le worker, donc pas de coût supplémentaire ; seule
  l'animation du déplacement (événement `move`) reste propre au simulateur (le bras réel « saute » directement à
  la position). Case à cocher « Bras virtuel » sur calibration et balayage, état mémorisé en `localStorage`
  (`cnc.visible`), par défaut coché si déjà en simulation/vidéo, décoché sinon.

## À faire / non vérifié

- **Positions des puits en retard sur les origines (⚠ sur les 4 plaques en dev)** : les bases ont été posées à
  HG (160;25), HD (25;25), BG (160;120), BD (25;120) mais les `WellPosition` datent d'avant. Régénérer en admin :
  décocher « Positions » du multi-puits puis enregistrer (D1 à la base, A vers +Y ; perd la calibration par puits).
  À refaire à la main sur le RPi4.
- **Mise à jour du RPi4 (prod) en ssh 4G** : annoncée, non confirmée. `git pull --ff-only` puis `make update`
  (détaché : `nohup make update > ~/update.log 2>&1 &`), jamais pendant un balayage.
- **Vérification physique** de l'origine D1 après mise à jour (le premier déplacement peut aller vers un autre bout
  de plaque si les bases ne sont pas celles de la règle).
- **Sens des flèches de déplacement** : elles suivent les libellés ; si l'image caméra est tournée par rapport aux
  axes CNC, le sens visuel peut différer du mouvement réel.
- Balayage avec une `Session` réelle : jamais exercé (la base dev n'en a aucune).
- **Vue CNC en balayage** : le suivi de plaque pendant un balayage (`position` envoyé par le worker) n'a été vérifié
  que côté navigateur avec des messages simulés ; à valider avec une vraie `Session` après redémarrage des workers.
- Idées non faites : valider `rows == len(row_def.split(','))` dans `MultiWell.clean()` ;
  `payload.current >= 0` dans `calibration.js` est vrai pour `null` (sans effet visible).
- `HD_6` (plaque 2×3) est **inactive** en base : elle n'apparaît ni dans la liste ni sur la table.

## Pièges rencontrés

- La base « dev » de ce poste est **MariaDB** (`MARIADB=default`, base `test_tube`), pas sqlite ;
  `datas/db.sqlite3` est un reliquat périmé. Interroger via `manage.py shell` (Redis et ReductStore tournent).
- `DEBUG=False` : statiques servis depuis `test_tube_scanner/staticfiles/` (`collectstatic` après un changement de
  CSS/JS) **et gabarits mis en cache par processus** : redémarrer le web pour voir un changement de template.
- Les workers Celery gardent le code en mémoire : redémarrer (`make dev-stop && make dev`) après un changement dans
  `process.py`, `multiwell.py`, `models.py`, `grbl_simulator.py`.
- `reorder_well_positions --realign-base` écrase `xbase/ybase` : à ne pas lancer si les bases ont été posées à
  la main (incident du 2026-10-13, restauré depuis une sauvegarde JSON ; voir `datas/backup/mariadb/`).
- Tests navigateur en local : une instance `daphne` de test laissée sur un autre port garde l'ancien gabarit en
  cache et fausse les essais ; la couper par son port, pas avec `pkill -f` (motif présent dans la commande).
- **`make update` peut faire perdre les configs supervisor/nginx** (`/etc/supervisor/conf.d/`,
  `/etc/nginx/sites-available/`) : après mise à jour, vérifier `sudo supervisorctl status` et `sudo nginx -t` ;
  recréer avec `make services` / `make nginx` si besoin. Repéré aussi un symlink nginx fantôme hérité d'un ancien
  montage manuel (`etc/nginx_service.conf`, avant le passage aux templates) pointant vers un fichier inexistant :
  supprimé. `reductstore` peut aussi rester en `FATAL` si `/usr/local/bin/reductstore` (binaire précompilé attendu,
  voir `CONTEXT.md`) est absent et qu'une ancienne install cargo existe ailleurs (`~/.cargo/bin/reductstore`) :
  soit installer le binaire officiel (`make reductstore`), soit relancer `make services REDUCT_BIN=<chemin>`.

## Reprendre sur un autre poste

```bash
git pull --ff-only          # branche video-plate-calibration
make dev                    # redis + reductstore + web + celery (ou make install-dev la 1re fois)
```

Puis lire `CONTEXT.md` et `CLAUDE.md`. Ce fichier peut être supprimé une fois les points ci-dessus traités.
