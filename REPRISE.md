# Reprise de session — PlanarianScanner

Note de passage entre postes. Le contexte technique est dans `CONTEXT.md`, les pièges et
l'architecture dans `CLAUDE.md` : les lire d'abord, ce fichier ne contient que l'état du travail.

État au **2026-10-13** — branche `video-plate-calibration`, dernier commit poussé `7af6015`.

## Fait

- **Plaques partielles** (`rows` > nombre de lettres de `row_def`, ex. HD_6 : `B,A`) : ne lèvent plus
  `IndexError` (`serpentine_names`, `uuid_from_session`, `multiwell_buttons`, `multiwell_cards`).
  Symptômes d'origine : boutons de puits figés en calibration, réordonnancement en HTTP 500.
- **Erreurs worker visibles** : une exception dans `_listen_to_redis` envoie `state='error'` à l'UI.
  Le JS de réordonnancement affiche `Erreur serveur : HTTP <code>` au lieu d'un échec de parsing JSON.
- **Page calibration** : boutons de déplacement en croix (+Y haut, -X / Sauver / +X, -Y bas, flèches
  dans leur direction). Les ids (`_up`, `_down`, `_left`, `_right`) et les commandes n'ont pas changé.
- **Grille des puits** (calibration et scanning) : A en haut → D en bas, colonnes 1 → N ; flèches du
  serpentin dans les marges (`→`/`←` première ligne lue, `↱`/`↰` ensuite), lues depuis
  `WellPosition.order`. CSS : classe `.well-dir`, grille `auto repeat(cols,1fr) auto`.
- `CONTEXT.md` : Django 6.0.

## À faire / non vérifié

- **Mise à jour du RPi4 (prod) en ssh 4G** : annoncée, non confirmée.
  `git pull --ff-only` puis `make update` (détaché : `nohup make update > ~/update.log 2>&1 &`).
  Pas pendant un balayage (le restart interrompt les workers). Voir « Mise à jour » dans `CONTEXT.md`.
- **Vérification physique** après mise à jour : l'ordre 0 est le puits D1 (origine `xbase/ybase`). Les
  anciennes plaques avaient A1 comme origine : le premier déplacement ira vers un autre bout de plaque.
  Lancer `manage.py reorder_well_positions --dry-run`, puis par plaque avec `--realign-base`.
- **Sens des flèches de déplacement** : elles suivent les libellés (+X → droite, etc.). Si l'image
  caméra est tournée par rapport aux axes CNC, le sens visuel peut différer du mouvement réel.
- Balayage avec une `Session` réelle : jamais exercé (la base dev n'en a aucune).
- Idée non faite : valider `rows == len(row_def.split(','))` dans `MultiWell.clean()` pour ne plus
  créer d'incohérence en admin (le code la tolère maintenant).
- Mineur : `payload.current >= 0` dans `static/scanner/js/calibration.js` est vrai pour `null`
  (`null >= 0`) ; sans effet visible aujourd'hui.

## Pièges rencontrés cette session

- La base « dev » de ce poste est **MariaDB** (`MARIADB=default` dans `.env`, base `test_tube`), pas
  sqlite. `datas/db.sqlite3` est un reliquat périmé (migration 0001 seule) : ne pas s'y fier.
  Interroger via `manage.py shell` (Redis et ReductStore doivent tourner).
- `DEBUG=False` : les statiques sont servis depuis `test_tube_scanner/staticfiles/`. Après un
  changement de CSS/JS : `manage.py collectstatic --noinput` (fait par `make update`).
- Les workers Celery gardent le code en mémoire : redémarrer (`make dev-stop && make dev`) après un
  changement dans `process.py`, `multiwell.py`, `models.py`. Le HTML de `multiwell_buttons()` est
  généré côté worker, pas par le template.

## Reprendre sur un autre poste

```bash
git pull --ff-only          # branche video-plate-calibration
make dev                    # redis + reductstore + web + celery (ou make install-dev la 1re fois)
```

Puis lire `CONTEXT.md` et `CLAUDE.md`. Ce fichier peut être supprimé une fois les points ci-dessus traités.
