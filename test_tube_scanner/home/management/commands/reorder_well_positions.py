'''
Réordonne les WellPosition en serpentin selon MultiWell.row_def, sans toucher aux x/y calibrés.

Ex. row_def=D,C,B,A, 6 colonnes : D1..D6, C6..C1, B1..B6, A6..A1
'''
from django.core.management.base import BaseCommand, CommandError
from scanner.models import MultiWell


class Command(BaseCommand):
    help = "Recalcule WellPosition.order en serpentin (x/y calibrés conservés)"

    def add_arguments(self, parser):
        parser.add_argument("--position", type=str, default=None,
                            help="Position du multi-puits (HD, HG, BD, BG). Défaut : tous les multi-puits actifs")
        parser.add_argument("--realign-base", action="store_true",
                            help="Aligne xbase/ybase du multi-puits sur le puits d'ordre 0")
        parser.add_argument("--dry-run", action="store_true", help="Affiche sans modifier la base")

    def handle(self, *args, **options):
        position = options["position"]
        multiwells = MultiWell.objects.filter(active=True)
        if position:
            multiwells = multiwells.filter(position=position)
        if not multiwells:
            raise CommandError(f"Aucun multi-puits actif trouvé (position={position})")

        for mw in multiwells:
            r = mw.reorder_well_positions(realign_base=options["realign_base"], dry_run=options["dry_run"])
            if r["error"]:
                self.stdout.write(self.style.WARNING(
                    f"{mw.position}: ignoré — {r['error']}. Vérifier row_def/rows/cols puis regénérer les positions."))
                continue
            o = r["origin"]
            self.stdout.write(f"{mw.position}: {' '.join(r['names'])}")
            self.stdout.write(f"  {r['changed']} ordre(s) modifié(s), origine (ordre 0) = {o['name']} ({o['x']}, {o['y']}), "
                              f"xbase/ybase = ({r['xbase']}, {r['ybase']})")
        if options["dry_run"]:
            self.stdout.write("dry-run : rien n'a été modifié")
