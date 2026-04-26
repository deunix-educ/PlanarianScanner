'''
Created on 19 janv. 2026

@author: denis
'''
from django.core.management.base import BaseCommand
#from django.conf import settings
from scanner.models import MultiWell
    
class Command(BaseCommand):
    help = "Recalculer les positions de tous les puits d'un multi-puits"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--all", type=bool, help=f"Tous les puits de tous les multi-puits", default=False)
        parser.add_argument("--position", type=str, help=f"Multiwel position: HD, HG, BD, BG", default="HD")

    def handle(self, *args, **options):  # @UnusedVariable
        try:
            position = options.get('position')
            _all = options.get('all')
            
            multiwells = [m for m in MultiWell.objects.filter(active=True).all() ]
            for m in multiwells:
                if m.position==position and not _all:
                    m.well_position=False
                    m.save()
                    print("Reset multi-puits position", position)
                    break
                m.well_position=False
                m.save()
                print("Reset multi-puits position", position)        

        except Exception as e:
            print(self.help, 'erreur', e)

