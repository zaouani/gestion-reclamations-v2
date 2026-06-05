# management/commands/auto_cloturer_reclamations.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from reclamations.models import Reclamation
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clôture automatiquement les réclamations dont toutes les actions sont réalisées depuis plus de 3 mois'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les réclamations qui seraient clôturées sans les modifier',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Nombre de jours après la dernière action pour clôturer (défaut: 90)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        
        self.stdout.write(f"🔍 Recherche des réclamations à clôturer automatiquement (après {days} jours)...")
        
        # Récupérer les réclamations non clôturées avec un 8D
        reclamations = Reclamation.objects.filter(
            cloture=False,
            huitd__isnull=False
        ).select_related('huitd').prefetch_related('huitd__actions')
        
        count = 0
        reclamations_a_cloturer = []
        
        for reclamation in reclamations:
            # Vérifier si toutes les actions sont réalisées
            if not reclamation.toutes_actions_realisees():
                continue
            
            date_derniere_action = reclamation.get_date_derniere_action_realisee()
            if not date_derniere_action:
                continue
            
            # Calculer la date limite
            date_limite = date_derniere_action + timedelta(days=days)
            
            if timezone.now().date() >= date_limite:
                reclamations_a_cloturer.append({
                    'reclamation': reclamation,
                    'date_derniere_action': date_derniere_action,
                    'date_limite': date_limite,
                    'jours_ecoules': (timezone.now().date() - date_derniere_action).days
                })
                count += 1
                
                if not dry_run:
                    with transaction.atomic():
                        reclamation.auto_cloturer()
                        logger.info(
                            f"Réclamation {reclamation.numero_reclamation} clôturée automatiquement "
                            f"(dernière action le {date_derniere_action}, {date_limite})"
                        )
        
        # Affichage des résultats
        if dry_run:
            self.stdout.write(f"\n📋 {count} réclamation(s) seraient clôturées :")
            for item in reclamations_a_cloturer:
                rec = item['reclamation']
                self.stdout.write(
                    f"  - {rec.numero_reclamation} | "
                    f"Dernière action: {item['date_derniere_action']} | "
                    f"Date limite: {item['date_limite']} | "
                    f"Jours écoulés: {item['jours_ecoules']}"
                )
        else:
            if count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ {count} réclamation(s) clôturée(s) automatiquement")
                )
            else:
                self.stdout.write("Aucune réclamation à clôturer pour le moment.")