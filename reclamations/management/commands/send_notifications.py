# reclamations/management/commands/send_notifications.py
from django.core.management.base import BaseCommand
from reclamations.notifications import NotificationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envoie les notifications groupées pour les réclamations en retard ou proches de l\'échéance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simule l\'envoi des notifications sans les envoyer réellement',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(self.style.SUCCESS('ENVOI DES NOTIFICATIONS GROUPÉES'))
        self.stdout.write(self.style.SUCCESS('='*50))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  Mode DRY RUN - Aucun email ne sera envoyé ⚠️\n'))
        
        # Récupérer les notifications groupées
        notifications_grouped = NotificationService.get_notifications_grouped()
        
        total_retard = sum(len(data['retard']) for data in notifications_grouped.values())
        total_alerte = sum(len(data['alerte']) for data in notifications_grouped.values())
        total_destinataires = len(notifications_grouped)
        
        self.stdout.write(f"\n📊 STATISTIQUES:")
        self.stdout.write(f"   - Réclamations en retard: {total_retard}")
        self.stdout.write(f"   - Réclamations en alerte: {total_alerte}")
        self.stdout.write(f"   - Destinataires concernés: {total_destinataires}")
        
        if total_retard == 0 and total_alerte == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Aucune notification à envoyer. Tout est dans les délais!'))
            return
        
        if not dry_run:
            # Afficher les détails des emails qui vont être envoyés
            self.stdout.write("\n📧 DESTINATAIRES:")
            for destinataire, data in notifications_grouped.items():
                self.stdout.write(f"   - {destinataire}: {len(data['retard'])} retard(s), {len(data['alerte'])} alerte(s)")
            
            # Demander confirmation
            confirm = input("\nVoulez-vous vraiment envoyer ces notifications ? (o/n): ")
            
            if confirm.lower() != 'o':
                self.stdout.write(self.style.WARNING('\n❌ Envoi annulé'))
                return
            
            # Envoyer les notifications groupées
            self.stdout.write("\n📧 ENVOI EN COURS...")
            resultats = NotificationService.envoyer_notifications_groupes()
            
            self.stdout.write("\n" + "="*50)
            self.stdout.write(self.style.SUCCESS('📧 RÉSULTATS DE L\'ENVOI'))
            self.stdout.write("="*50)
            self.stdout.write(f"   - Emails envoyés: {resultats['emails_envoyes']}")
            self.stdout.write(f"   - Notifications de retard: {resultats['notifications_envoyees']}")
            self.stdout.write(f"   - Alertes d'échéance: {resultats['alertes_envoyees']}")
        else:
            # Mode dry-run: afficher les détails
            self.stdout.write(self.style.WARNING("\n📧 EMAILS QUI SERAIENT ENVOYÉS:"))
            for destinataire, data in notifications_grouped.items():
                self.stdout.write(f"\n   📧 À: {destinataire}")
                self.stdout.write(f"      - {len(data['retard'])} réclamation(s) en retard")
                self.stdout.write(f"      - {len(data['alerte'])} réclamation(s) en alerte")
                
                for item in data['retard'][:3]:  # Afficher max 3 exemples
                    rec = item['reclamation']
                    self.stdout.write(f"        * {rec.numero_reclamation} - {rec.client.nom}")
                if len(data['retard']) > 3:
                    self.stdout.write(f"        ... et {len(data['retard'])-3} autre(s)")
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('FIN DES NOTIFICATIONS'))
        self.stdout.write(self.style.SUCCESS('='*50))