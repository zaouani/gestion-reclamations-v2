from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q, Count
from ..models import OrdreFabrication, LigneOF, Produit, AlerteFAI
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class FAIAlertService:
    """Service intelligent de vérification FAI par OF"""
    
    # Délais pour FAI (en jours)
    DELAI_FAI_JOURS = 365  # 1 an par défaut
    ALERTE_JOURS = 30  # Alerter 30 jours avant expiration
    
    def __init__(self):
        self.today = date.today()
    
    def verifier_of_non_fermes(self):
        """Vérifie tous les OF non fermés et génère les alertes"""
        # Récupérer les OF non terminés
        ofs_non_fermes = OrdreFabrication.objects.exclude(
            statut__in=['TERMINE', 'CLOTURE', 'ANNULE']
        ).order_by('-priorite', '-date_creation')
        
        resultats = []
        
        for of in ofs_non_fermes:
            # Vérifier chaque ligne de l'OF
            alertes_of = self.verifier_lignes_of(of)
            if alertes_of:
                resultats.append({
                    'of': of,
                    'alertes': alertes_of,
                    'nb_alertes': len(alertes_of)
                })
        
        return resultats
    
    def verifier_lignes_of(self, of):
        """Vérifie les lignes d'un OF et génère les alertes"""
        lignes = of.lignes.select_related('produit').all()
        alertes_generees = []
        
        for ligne in lignes:
            alerte = self.verifier_produit(of, ligne.produit)
            if alerte:
                alertes_generees.append(alerte)
        
        return alertes_generees
    
    def verifier_produit(self, of, produit):
        """Vérifie un produit spécifique pour un OF"""
        
        # Récupérer la dernière date de production pour ce produit
        derniere_production = self.get_derniere_production(produit)
        
        if not derniere_production:
            return self.creer_alerte(of, produit, 'INFO', 
                f"Première production pour {produit.product_number}. FAI requis avant la première livraison.")
        
        # Calculer la date d'expiration FAI
        date_expiration = self.calculer_date_expiration(derniere_production)
        
        # Vérifier si une alerte existe déjà
        alerte_existante = AlerteFAI.objects.filter(
            ordre_fabrication=of,
            produit=produit,
            statut__in=['NOUVELLE', 'EN_COURS']
        ).first()
        
        # Déterminer le niveau d'alerte
        niveau, message = self.determiner_niveau_alerte(date_expiration)
        
        if niveau:
            if alerte_existante:
                # Mettre à jour l'alerte existante
                alerte_existante.niveau = niveau
                alerte_existante.message = message
                alerte_existante.date_expiration = date_expiration
                alerte_existante.save()
                return alerte_existante
            else:
                # Créer une nouvelle alerte
                return self.creer_alerte(of, produit, niveau, message, 
                                        derniere_production, date_expiration)
        
        # Si pas d'alerte et qu'une alerte existe, la fermer
        if alerte_existante:
            alerte_existante.statut = 'TRAITEE'
            alerte_existante.save()
        
        return None
    
    def get_derniere_production(self, produit):
        """Récupère la dernière date de production pour un produit"""
        # Chercher dans les OF terminés
        dernier_of = LigneOF.objects.filter(
            produit=produit,
            ordre_fabrication__statut='TERMINE',
            date_fin__isnull=False
        ).order_by('-date_fin').first()
        
        if dernier_of and dernier_of.date_fin:
            return dernier_of.date_fin
        
        return None
    
    def calculer_date_expiration(self, date_production):
        """Calcule la date d'expiration FAI"""
        from dateutil.relativedelta import relativedelta
        return date_production + relativedelta(months=12)  # 1 an
    
    def determiner_niveau_alerte(self, date_expiration):
        """Détermine le niveau d'alerte en fonction de la date d'expiration"""
        jours_restants = (date_expiration - self.today).days
        
        if jours_restants < 0:
            return 'CRITIQUE', f"FAI expiré depuis {-jours_restants} jours. Inspection requise immédiatement."
        elif jours_restants <= 7:
            return 'URGENT', f"FAI expire dans {jours_restants} jours (URGENT). Planifier inspection."
        elif jours_restants <= self.ALERTE_JOURS:
            return 'ALERTE', f"FAI expire dans {jours_restants} jours. Préparer inspection."
        
        return None, None
    
    def creer_alerte(self, of, produit, niveau, message, derniere_production=None, date_expiration=None):
        """Crée une nouvelle alerte"""
        alerte = AlerteFAI.objects.create(
            ordre_fabrication=of,
            produit=produit,
            niveau=niveau,
            statut='NOUVELLE',
            message=message,
            derniere_production=derniere_production,
            date_expiration=date_expiration
        )
        return alerte
    
    def envoyer_alertes_groupes(self):
        """Envoie les alertes groupées par OF et par responsable"""
        # Récupérer les alertes non traitées
        alertes = AlerteFAI.objects.filter(
            statut__in=['NOUVELLE', 'EN_COURS']
        ).select_related('ordre_fabrication', 'produit').order_by('ordre_fabrication')
        
        # Grouper par OF
        alertes_par_of = defaultdict(list)
        for alerte in alertes:
            alertes_par_of[alerte.ordre_fabrication].append(alerte)
        
        alertes_envoyees = []
        
        for of, alertes_of in alertes_par_of.items():
            # Déterminer le destinataire
            destinataires = self.get_destinataires(of)
            
            if not destinataires:
                continue
            
            # Préparer et envoyer l'email groupé
            sujet, message_html, message_texte = self.preparer_email_groupe(of, alertes_of)
            
            try:
                send_mail(
                    subject=sujet,
                    message=message_texte,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=destinataires,
                    html_message=message_html,
                    fail_silently=False
                )
                
                # Marquer les alertes comme envoyées
                for alerte in alertes_of:
                    alerte.statut = 'EN_COURS'
                    alerte.save()
                
                alertes_envoyees.append({
                    'of': of,
                    'nb_alertes': len(alertes_of),
                    'destinataires': destinataires
                })
                
                logger.info(f"Alertes FAI envoyées pour OF {of.numero_of}: {len(alertes_of)} alertes")
                
            except Exception as e:
                logger.error(f"Erreur envoi alertes pour OF {of.id}: {e}")
        
        return alertes_envoyees
    
    def get_destinataires(self, of):
        """Récupère les destinataires pour un OF"""
        destinataires = []
        
        if of.responsable and '@' in of.responsable:
            destinataires.append(of.responsable)
        
        # Responsable qualité par défaut
        if hasattr(settings, 'QUALITY_MANAGER_EMAIL'):
            destinataires.append(settings.QUALITY_MANAGER_EMAIL)
        
        return list(set(destinataires))
    
    def preparer_email_groupe(self, of, alertes):
        """Prépare l'email groupé pour un OF"""
        niveaux = {'CRITIQUE': 0, 'URGENT': 0, 'ALERTE': 0, 'INFO': 0}
        for alerte in alertes:
            niveaux[alerte.niveau] += 1
        
        sujet = f"[FAI] OF {of.numero_of} - {niveaux['CRITIQUE']} critique(s), {niveaux['URGENT']} urgent(s)"
        
        message_html = render_to_string('reclamations/emails/fai_alerte_groupe.html', {
            'of': of,
            'alertes': alertes,
            'niveaux': niveaux,
            'site_url': settings.SITE_URL
        })
        
        message_texte = self.generer_message_texte(of, alertes, niveaux)
        
        return sujet, message_html, message_texte
    
    def generer_message_texte(self, of, alertes, niveaux):
        """Génère la version texte de l'email"""
        message = f"""
ALERTES FAI - Ordre de Fabrication {of.numero_of}
{'='*50}

Résumé:
- Critique: {niveaux['CRITIQUE']}
- Urgent: {niveaux['URGENT']}
- Alerte: {niveaux['ALERTE']}
- Information: {niveaux['INFO']}

Détails des produits nécessitant une attention:
"""
        for alerte in alertes:
            message += f"""
[{alerte.get_niveau_display()}] {alerte.produit.product_number}
   {alerte.message}
   Dernière production: {alerte.derniere_production}
   Expiration: {alerte.date_expiration}
"""
        
        message += f"""
Actions recommandées:
1. Vérifier les produits en statut CRITIQUE immédiatement
2. Planifier les inspections FAI pour les produits URGENT
3. Préparer les documents pour les alertes

Lien: {settings.SITE_URL}/fai/alertes/par-of/{of.id}/
        """
        return message