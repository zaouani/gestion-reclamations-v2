import logging
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Reclamation

logger = logging.getLogger(__name__)


class NotificationService:
    """Service de gestion des notifications"""
    
    # Délais en jours ouvrés
    DELAI_4D = 2  # 2 jours ouvrés
    DELAI_8D = 10  # 10 jours ouvrés
    
    @staticmethod
    def est_jour_ouvre(date):
        """Vérifie si une date est un jour ouvré (lundi à vendredi)"""
        return date.weekday() < 5  # 0 = lundi, 4 = vendredi
    
    @staticmethod
    def calculer_date_limite(date_debut, jours):
        """
        Calcule la date limite en jours ouvrés
        Ne compte pas les week-ends
        """
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
            
            # Vérifier 4D
            if rec.etat_4d != 'CLOTURE':
                date_creation = rec.date_reclamation
                date_limite_4d = NotificationService.calculer_date_limite(date_creation, NotificationService.DELAI_4D)
                
                if date_limite_4d <= aujourdhui:
                    notifications.append({
                        'type': '4D',
                        'date_limite': date_limite_4d,
                        'delai': NotificationService.DELAI_4D
                    })
            
            # Vérifier 8D
            if rec.etat_8d != 'CLOTURE':
                date_creation = rec.date_reclamation
                date_limite_8d = NotificationService.calculer_date_limite(date_creation, NotificationService.DELAI_8D)
                
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
            
            # Vérifier 4D
            if rec.etat_4d != 'CLOTURE':
                date_limite_4d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_4D)
                jours_restants = (date_limite_4d - aujourdhui).days
                
                if 0 < jours_restants <= 1:  # Alerte 1 jour avant
                    alertes.append({
                        'type': '4D',
                        'date_limite': date_limite_4d,
                        'jours_restants': jours_restants
                    })
            
            # Vérifier 8D
            if rec.etat_8d != 'CLOTURE':
                date_limite_8d = NotificationService.calculer_date_limite(rec.date_reclamation, NotificationService.DELAI_8D)
                jours_restants = (date_limite_8d - aujourdhui).days
                
                if 0 < jours_restants <= 2:  # Alerte 2 jours avant
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
    
    @staticmethod
    def envoyer_notifications():
        """Envoie toutes les notifications nécessaires"""
        reclamations_a_notifier = NotificationService.get_reclamations_a_notifier()
        reclamations_en_alerte = NotificationService.get_reclamations_en_alerte()
        
        notifications_envoyees = 0
        alertes_envoyees = 0
        
        # Envoyer les notifications pour les réclamations en retard
        for item in reclamations_a_notifier:
            rec = item['reclamation']
            notifications = item['notifications']
            
            destinataires = []
            if rec.createur and rec.createur.email:
                destinataires.append(rec.createur.email)
            
            # Ajouter un email de responsable (à configurer)
            if settings.NOTIFICATION_RESPONSABLE_EMAIL:
                destinataires.append(settings.NOTIFICATION_RESPONSABLE_EMAIL)
            
            if destinataires:
                try:
                    sujet = f"[URGENT] Réclamation {rec.numero_reclamation} - Délai dépassé"
                    html_message = render_to_string('reclamations/emails/notification_retard.html', {
                        'reclamation': rec,
                        'notifications': notifications,
                        'site_url': settings.SITE_URL
                    })
                    text_message = f"""
                    Réclamation {rec.numero_reclamation} - Délai dépassé
                    
                    Client: {rec.client.nom}
                    Date de création: {rec.date_reclamation.strftime('%d/%m/%Y')}
                    
                    États à clôturer:
                    {''.join([f"- {n['type']}: à clôturer avant le {n['date_limite'].strftime('%d/%m/%Y')}\n" for n in notifications])}
                    
                    Consultez la réclamation: {settings.SITE_URL}/reclamations/{rec.id}/
                    """
                    
                    send_mail(
                        sujet,
                        text_message,
                        settings.DEFAULT_FROM_EMAIL,
                        destinataires,
                        html_message=html_message,
                        fail_silently=False
                    )
                    notifications_envoyees += 1
                    logger.info(f"Notification envoyée pour réclamation {rec.numero_reclamation}")
                    
                except Exception as e:
                    logger.error(f"Erreur envoi notification pour {rec.numero_reclamation}: {e}")
        
        # Envoyer les alertes pour les réclamations proches de l'échéance
        for item in reclamations_en_alerte:
            rec = item['reclamation']
            alertes = item['alertes']
            
            destinataires = []
            if rec.createur and rec.createur.email:
                destinataires.append(rec.createur.email)
            
            if settings.NOTIFICATION_RESPONSABLE_EMAIL:
                destinataires.append(settings.NOTIFICATION_RESPONSABLE_EMAIL)
            
            if destinataires:
                try:
                    sujet = f"[ALERTE] Réclamation {rec.numero_reclamation} - Échéance proche"
                    html_message = render_to_string('reclamations/emails/notification_alerte.html', {
                        'reclamation': rec,
                        'alertes': alertes,
                        'site_url': settings.SITE_URL
                    })
                    text_message = f"""
                    ALERTE - Réclamation {rec.numero_reclamation} - Échéance proche
                    
                    Client: {rec.client.nom}
                    Date de création: {rec.date_reclamation.strftime('%d/%m/%Y')}
                    
                    États à clôturer prochainement:
                    {''.join([f"- {a['type']}: à clôturer dans {a['jours_restants']} jour(s) (avant le {a['date_limite'].strftime('%d/%m/%Y')})\n" for a in alertes])}
                    
                    Consultez la réclamation: {settings.SITE_URL}/reclamations/{rec.id}/
                    """
                    
                    send_mail(
                        sujet,
                        text_message,
                        settings.DEFAULT_FROM_EMAIL,
                        destinataires,
                        html_message=html_message,
                        fail_silently=False
                    )
                    alertes_envoyees += 1
                    logger.info(f"Alerte envoyée pour réclamation {rec.numero_reclamation}")
                    
                except Exception as e:
                    logger.error(f"Erreur envoi alerte pour {rec.numero_reclamation}: {e}")
        
        return {
            'notifications_envoyees': notifications_envoyees,
            'alertes_envoyees': alertes_envoyees,
            'total_reclamations_retard': len(reclamations_a_notifier),
            'total_reclamations_alerte': len(reclamations_en_alerte)
        }