from django.core.management.base import BaseCommand
from reclamations.services.fai_alert_service import FAIAlertService

class Command(BaseCommand):
    help = 'Vérifie les OF et envoie les alertes FAI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send',
            action='store_true',
            help='Envoyer les alertes par email'
        )

    def handle(self, *args, **options):
        service = FAIAlertService()
        
        self.stdout.write("Vérification des OF non fermés...")
        resultats = service.verifier_of_non_fermes()
        
        nb_alertes = sum(len(r['alertes']) for r in resultats)
        self.stdout.write(f"OF vérifiés: {len(resultats)}")
        self.stdout.write(f"Alertes générées: {nb_alertes}")
        
        if options['send'] and nb_alertes > 0:
            self.stdout.write("Envoi des alertes groupées...")
            envoyees = service.envoyer_alertes_groupes()
            self.stdout.write(self.style.SUCCESS(f"Alertes envoyées: {len(envoyees)} OF"))