# reclamations/notifications.py
import logging
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from collections import defaultdict
from .models import Reclamation

logger = logging.getLogger(__name__)


class NotificationService:
    """Service de gestion des notifications groupées"""
    
    DELAI_4D = 2
    DELAI_8D = 10
    
    @staticmethod
    def est_jour_ouvre(date):
        return date.weekday() < 5
    
    @staticmethod
    def calculer_date_limite(date_debut, jours):
        date_limite = date_debut
        jours_restants = jours
        
        while jours_restants > 0:
            date_limite += timedelta(days=1)
            if NotificationService.est_jour_ouvre(date_limite):
                jours_restants -= 1
        
        return date_limite
    
    @staticmethod
    def get_reclamations_a_notifier():
        """Récupère les réclamations qui nécessitent une notification"""
        aujourdhui = timezone.now().date()
        reclamations_a_notifier = []
        
        for rec in Reclamation.objects.filter(cloture=False).select_related('client', 'createur'):
            notifications = []
            
            if rec.etat_4d != 'CLOTURE':
                date_limite_4d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_4D)
                if date_limite_4d <= aujourdhui:
                    notifications.append({
                        'type': '4D',
                        'date_limite': date_limite_4d,
                        'delai': NotificationService.DELAI_4D
                    })
            
            if rec.etat_8d != 'CLOTURE':
                date_limite_8d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_8D)
                if date_limite_8d <= aujourdhui:
                    notifications.append({
                        'type': '8D',
                        'date_limite': date_limite_8d,
                        'delai': NotificationService.DELAI_8D
                    })
            if notifications:
                reclamations_a_notifier.append({
                    'reclamation': rec,
                    'notifications': notifications
                })
        
        return reclamations_a_notifier
    
    @staticmethod
    def get_reclamations_en_alerte():
        """Récupère les réclamations en alerte (délai proche)"""
        aujourdhui = timezone.now().date()
        reclamations_alerte = []
        
        for rec in Reclamation.objects.filter(cloture=False).select_related('client', 'createur'):
            alertes = []
            
            if rec.etat_4d != 'CLOTURE':
                date_limite_4d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_4D)
                jours_restants = (date_limite_4d - aujourdhui).days
                if 0 < jours_restants <= 2:
                    alertes.append({
                        'type': '4D',
                        'date_limite': date_limite_4d,
                        'jours_restants': jours_restants
                    })
            
            if rec.etat_8d != 'CLOTURE':
                date_limite_8d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_8D)
                jours_restants = (date_limite_8d - aujourdhui).days
                if 0 < jours_restants <= 3:
                    alertes.append({
                        'type': '8D',
                        'date_limite': date_limite_8d,
                        'jours_restants': jours_restants
                    })
            
            if alertes:
                reclamations_alerte.append({
                    'reclamation': rec,
                    'alertes': alertes
                })
        
        return reclamations_alerte
    
    # reclamations/notifications.py

    @staticmethod
    def get_notifications_grouped():
        """Récupère les notifications groupées UNIQUEMENT pour le responsable qualité"""
        
        reclamations_retard = NotificationService.get_reclamations_a_notifier()
        reclamations_alerte = NotificationService.get_reclamations_en_alerte()
        
        # ⚠️ MODIFICATION ICI : On ne groupe que pour le responsable qualité
        notifications_grouped = {}
        
        # Ajouter le responsable qualité comme seul destinataire
        if settings.NOTIFICATION_RESPONSABLE_EMAIL:
            notifications_grouped['quality'] = {
                'retard': [],
                'alerte': [],
                'destinataires': {settings.NOTIFICATION_RESPONSABLE_EMAIL}
            }
            
            # Ajouter toutes les réclamations en retard
            for item in reclamations_retard:
                notifications_grouped['quality']['retard'].append(item)
            
            # Ajouter toutes les réclamations en alerte
            for item in reclamations_alerte:
                notifications_grouped['quality']['alerte'].append(item)
        
        return notifications_grouped
    
    @staticmethod
    def envoyer_notifications_groupes():
        """Envoie les notifications groupées par destinataire"""
        notifications_grouped = NotificationService.get_notifications_grouped()
        
        notifications_envoyees = 0
        alertes_envoyees = 0
        
        for destinataire_key, data in notifications_grouped.items():
            retard_list = data['retard']
            alerte_list = data['alerte']
            destinataires = list(data['destinataires'])
            
            if not destinataires:
                continue
            
            # Déterminer le nom du destinataire pour l'affichage
            if destinataire_key == 'quality':
                nom_destinataire = "Responsable Qualité"
            else:
                nom_destinataire = destinataire_key
            
            # Préparer le contenu de l'email groupé
            sujet, message_html, message_texte = NotificationService._preparer_email_groupe(
                retard_list, alerte_list, nom_destinataire
            )
            
            try:
                send_mail(
                    sujet,
                    message_texte,
                    settings.DEFAULT_FROM_EMAIL,
                    destinataires,
                    html_message=message_html,
                    fail_silently=False
                )
                notifications_envoyees += len(retard_list)
                alertes_envoyees += len(alerte_list)
                logger.info(f"Email groupé envoyé à {', '.join(destinataires)}: {len(retard_list)} retards, {len(alerte_list)} alertes")
                
            except Exception as e:
                logger.error(f"Erreur envoi email groupé à {destinataires}: {e}")
        
        return {
            'notifications_envoyees': notifications_envoyees,
            'alertes_envoyees': alertes_envoyees,
            'total_reclamations_retard': sum(len(data['retard']) for data in notifications_grouped.values()),
            'total_reclamations_alerte': sum(len(data['alerte']) for data in notifications_grouped.values()),
            'emails_envoyes': len(notifications_grouped)
        }
    
    @staticmethod
    def _preparer_email_groupe(retard_list, alerte_list, destinataire_nom):
        """Prépare l'email groupé"""
        
        total_retard = len(retard_list)
        total_alerte = len(alerte_list)
        
        if total_retard > 0:
            sujet = f"[URGENT] {total_retard} réclamation(s) en retard - {total_alerte} alerte(s)"
        else:
            sujet = f"[ALERTE] {total_alerte} réclamation(s) proche(s) de l'échéance"
        
        message_html = render_to_string('reclamations/emails/notification_groupe.html', {
            'retard_list': retard_list,
            'alerte_list': alerte_list,
            'total_retard': total_retard,
            'total_alerte': total_alerte,
            'destinataire_nom': destinataire_nom,
            'date_aujourdhui': timezone.now().date(),
            'site_url': settings.SITE_URL
        })
        
        message_texte = NotificationService._generer_message_texte_groupe(
            retard_list, alerte_list, destinataire_nom
        )
        
        return sujet, message_html, message_texte
    
    @staticmethod
    def _generer_message_texte_groupe(retard_list, alerte_list, destinataire_nom):
        """Génère la version texte de l'email groupé"""
        message = f"""
                {'='*60}
                RAPPORT QUOTIDIEN DES RÉCLAMATIONS
                {'='*60}

                Bonjour {destinataire_nom},

                Voici le récapitulatif des réclamations nécessitant votre attention.

                📊 RÉSUMÉ:
                - Réclamations en retard: {len(retard_list)}
                - Réclamations en alerte: {len(alerte_list)}

                """
        
        if retard_list:
            message += """
                        🔴 RÉCLAMATIONS EN RETARD (URGENT):
                        """
            for item in retard_list:
                rec = item['reclamation']
                notifications = item['notifications']
                message += f"""
                            📋 {rec.numero_reclamation} - {rec.client.nom}
                                Créée le: {rec.date_reclamation.strftime('%d/%m/%Y')}
                                États en retard: {', '.join([n['type'] for n in notifications])}
                            """
        
        if alerte_list:
            message += """
                        🟡 RÉCLAMATIONS EN ALERTE (Échéance proche):
                        """
            for item in alerte_list:
                rec = item['reclamation']
                alertes = item['alertes']
                message += f"""
                            📋 {rec.numero_reclamation} - {rec.client.nom}
                                Créée le: {rec.date_reclamation.strftime('%d/%m/%Y')}
                                Échéances: {', '.join([f"{a['type']} (J-{a['jours_restants']})" for a in alertes])}
                            """
        
        message += f"""
                📝 Actions recommandées:
                1. Traiter en priorité les réclamations en retard
                2. Planifier le traitement des réclamations en alerte

                🔗 Accès rapide: {settings.SITE_URL}/reclamations/notifications/

                Cet email est généré automatiquement. Merci de ne pas y répondre.
                """
        return message