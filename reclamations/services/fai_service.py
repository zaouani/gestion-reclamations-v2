# reclamations/services/fai_service.py
import pandas as pd
from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from io import BytesIO
import xlsxwriter
from ..models import ArticleFAI, Produit, HistoriqueImportFAI
import logging
from django.core.mail import EmailMessage, EmailMultiAlternatives

logger = logging.getLogger(__name__)


class FAIService:
    """Service de gestion FAI (First Article Inspection)"""
    
    # Nouveaux seuils en années
    SEUILS = {
        'INFO': 1.5,      # Moins de 1.5 an (18 mois)
        'ALERTE': 1.5,    # Entre 1.5 et 1.8 ans (18-21.6 mois)
        'URGENT': 1.8,    # Entre 1.8 et 2 ans (21.6-24 mois)
        'CRITIQUE': 2.0,  # Plus de 2 ans (24 mois)
    }
    
    def __init__(self):
        self.today = date.today()
    
    def calculer_statut(self, derniere_production):
        """
        Calcule le statut FAI en fonction de la date de dernière production
        
        Règles:
        - CRITIQUE: plus de 2 ans sans production (> 730 jours)
        - URGENT: entre 1.8 et 2 ans (657 - 730 jours)
        - ALERTE: entre 1.5 et 1.8 ans (547 - 657 jours)
        - INFO: moins de 1.5 an (< 547 jours)
        """
        if not derniere_production:
            return 'CRITIQUE'
        
        jours_ecoules = (self.today - derniere_production).days
        annees_ecoules = jours_ecoules / 365.25  # Conversion précise en années
        
        if annees_ecoules >= self.SEUILS['CRITIQUE']:  # >= 2 ans
            return 'CRITIQUE'
        elif annees_ecoules >= self.SEUILS['URGENT']:  # 1.8 - 2 ans
            return 'URGENT'
        elif annees_ecoules >= self.SEUILS['ALERTE']:  # 1.5 - 1.8 ans
            return 'ALERTE'
        else:  # < 1.5 an
            return 'INFO'
    
    def get_annees_ecoules(self, derniere_production):
        """Retourne le nombre d'années écoulées depuis la dernière production"""
        if not derniere_production:
            return None
        jours_ecoules = (self.today - derniere_production).days
        return round(jours_ecoules / 365.25, 2)
    
    def importer_fichier_excel(self, fichier, nom_fichier):
        """Importe un fichier Excel depuis l'ERP et met à jour les données"""
        
        try:
            # Lire le fichier Excel
            df = pd.read_excel(fichier)
            
            # Vérifier les colonnes
            colonnes_attendues = ['PN', 'OF', 'DATE_DERNIERE_PRODUCTION']
            colonnes_manquantes = [c for c in colonnes_attendues if c not in df.columns]
            
            if colonnes_manquantes:
                return {
                    'success': False,
                    'error': f"Colonnes manquantes: {', '.join(colonnes_manquantes)}"
                }
            
            # Statistiques
            lignes_importees = 0
            lignes_modifiees = 0
            erreurs = []
            
            for index, row in df.iterrows():
                try:
                    product_number = str(row['PN']).strip()
                    numero_of = str(row['OF']).strip()
                    date_production = pd.to_datetime(row['DATE_DERNIERE_PRODUCTION']).date()
                    
                    # Trouver ou créer le produit
                    produit, created = Produit.objects.get_or_create(
                        product_number=product_number,
                        defaults={'designation': f"Produit {product_number}"}
                    )
                    
                    # Calculer le statut avec les nouveaux seuils
                    statut = self.calculer_statut(date_production)
                    
                    # Mettre à jour ou créer l'article FAI
                    article, updated = ArticleFAI.objects.update_or_create(
                        produit=produit,
                        defaults={
                            'numero_of': numero_of,
                            'derniere_production': date_production,
                            'statut': statut
                        }
                    )
                    
                    lignes_importees += 1
                    if not created:
                        lignes_modifiees += 1
                    
                except Exception as e:
                    erreurs.append(f"Ligne {index + 2}: {str(e)}")
            
            # Enregistrer l'historique
            HistoriqueImportFAI.objects.create(
                fichier_nom=nom_fichier,
                lignes_importees=lignes_importees,
                lignes_modifiees=lignes_modifiees,
                erreurs="\n".join(erreurs[:10])
            )
            
            return {
                'success': True,
                'importees': lignes_importees,
                'modifiees': lignes_modifiees,
                'erreurs': erreurs
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def mettre_a_jour_depuis_chemin(self, chemin_fichier):
        """Met à jour les données à partir d'un fichier Excel sur le disque"""
        import os
        if not os.path.exists(chemin_fichier):
            return {'success': False, 'error': f"Fichier non trouvé: {chemin_fichier}"}
        
        with open(chemin_fichier, 'rb') as f:
            return self.importer_fichier_excel(f, os.path.basename(chemin_fichier))
    
    def get_articles_a_alerter(self):
        """Récupère les articles FAI qui nécessitent une alerte (URGENT et CRITIQUE)"""
        articles_critiques = ArticleFAI.objects.filter(statut__in=['URGENT', 'CRITIQUE'])
        return articles_critiques
    
    def exporter_alertes_excel(self):
        """Exporte les alertes FAI vers un fichier Excel"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        urgent_format = workbook.add_format({'bg_color': '#FFC000'})
        critique_format = workbook.add_format({'bg_color': '#FF0000', 'font_color': 'white'})
        
        # Feuille 1: Alertes
        worksheet = workbook.add_worksheet("Alertes FAI")
        
        headers = ['PN', 'Désignation', 'N° OF', 'Dernière production', 'Années écoulées', 'Statut']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        row = 1
        for article in self.get_articles_a_alerter():
            annees = self.get_annees_ecoules(article.derniere_production) if article.derniere_production else 0
            
            format_ligne = critique_format if article.statut == 'CRITIQUE' else urgent_format
            
            worksheet.write(row, 0, article.produit.product_number, format_ligne)
            worksheet.write(row, 1, article.produit.designation or '-', format_ligne)
            worksheet.write(row, 2, article.numero_of or '-', format_ligne)
            worksheet.write(row, 3, article.derniere_production.strftime('%d/%m/%Y') if article.derniere_production else '-', format_ligne)
            worksheet.write(row, 4, f"{annees} ans" if annees else '-', format_ligne)
            worksheet.write(row, 5, article.get_statut_display(), format_ligne)
            row += 1
        
        # Ajuster les colonnes
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 12)
        
        # Feuille 2: Synthèse
        worksheet_synth = workbook.add_worksheet("Synthèse")
        
        stats = self.get_statistiques()
        synth_headers = ['Statut', 'Nombre', 'Seuil']
        for col, header in enumerate(synth_headers):
            worksheet_synth.write(0, col, header, header_format)
        
        seuils_desc = {
            'CRITIQUE': '> 2 ans',
            'URGENT': '1.8 - 2 ans',
            'ALERTE': '1.5 - 1.8 ans',
            'INFO': '< 1.5 an'
        }
        
        row = 1
        for statut, count in stats.items():
            worksheet_synth.write(row, 0, statut)
            worksheet_synth.write(row, 1, count)
            worksheet_synth.write(row, 2, seuils_desc.get(statut, '-'))
            row += 1
        
        workbook.close()
        output.seek(0)
        
        return output
    
    def envoyer_alertes_email(self, destinataires=None):
        """Envoie un email avec fichier Excel des alertes"""
        if not destinataires:
            destinataires = [settings.NOTIFICATION_RESPONSABLE_EMAIL]
        
        articles_critiques = ArticleFAI.objects.filter(statut='CRITIQUE')
        articles_urgents = ArticleFAI.objects.filter(statut='URGENT')
        
        nb_critique = articles_critiques.count()
        nb_urgent = articles_urgents.count()
        
        if nb_critique == 0 and nb_urgent == 0:
            return {'success': True, 'message': 'Aucune alerte à envoyer'}
        
        # Générer le fichier Excel
        excel_file = self.exporter_alertes_excel()
        
        # Préparer l'email
        sujet = f"[FAI] Alerte stocks - {nb_critique} critique(s), {nb_urgent} urgent(s)"
        
        message = f"""
        ALERTE FAI - First Article Inspection
        =====================================

        Date: {date.today()}

        Résumé:
        - {nb_critique} article(s) en statut CRITIQUE (> 2 ans sans production)
        - {nb_urgent} article(s) en statut URGENT (1.8 - 2 ans sans production)

        Actions recommandées:
        - CRITIQUE: Production immédiate requise
        - URGENT: Planifier production sous 2 semaines

        Consultez le fichier Excel joint pour la liste détaillée des articles.

        Accéder au tableau de bord: {settings.SITE_URL}/fai/liste/

        ---
        Cet email est généré automatiquement par le système FAI.
            """
            
        # Créer l'email avec pièce jointe
        email = EmailMessage(
            subject=sujet,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=destinataires
        )
        
        # Ajouter la pièce jointe
        email.attach(
            filename='alertes_fai.xlsx',
            content=excel_file.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        try:
            email.send(fail_silently=False)
            return {'success': True, 'message': f'Email envoyé à {", ".join(destinataires)}'}
            
        except Exception as e:
            logger.error(f"Erreur envoi email FAI: {e}")
            return {'success': False, 'error': str(e)}

    def get_statistiques(self):
        """Retourne les statistiques des articles FAI"""
        stats = {}
        for statut, _ in ArticleFAI.STATUT_CHOICES:
            stats[statut] = ArticleFAI.objects.filter(statut=statut).count()
        return stats
    
    def get_articles_par_statut(self):
        """Retourne les articles groupés par statut"""
        resultats = {}
        for statut_code, statut_label in ArticleFAI.STATUT_CHOICES:
            resultats[statut_code] = ArticleFAI.objects.filter(statut=statut_code).select_related('produit').order_by('-derniere_production')
        return resultats
    def get_articles_par_statut(self, limit=20):
        """Retourne les articles groupés par statut avec limite"""
        resultats = {}
        for statut_code, statut_label in ArticleFAI.STATUT_CHOICES:
            resultats[statut_code] = ArticleFAI.objects.filter(
                statut=statut_code
            ).select_related('produit').order_by('-derniere_production')[:limit]
        return resultats
    
    def get_articles_par_statut_pagine(self, statut=None, page=1, per_page=20):
        """Retourne les articles paginés par statut"""
        queryset = ArticleFAI.objects.select_related('produit')
        
        if statut and statut != 'TOUS':
            queryset = queryset.filter(statut=statut)
        
        queryset = queryset.order_by('-derniere_production')
        
        paginator = Paginator(queryset, per_page)
        try:
            articles = paginator.page(page)
        except PageNotAnInteger:
            articles = paginator.page(1)
        except EmptyPage:
            articles = paginator.page(paginator.num_pages)
        
        return articles
    
    def rechercher_par_pn(self, pn, page=1, per_page=20):
        """Recherche un produit par son PN (Product Number)"""
        queryset = ArticleFAI.objects.select_related('produit').filter(
            Q(produit__product_number__icontains=pn)
        ).order_by('-derniere_production')
        
        paginator = Paginator(queryset, per_page)
        try:
            articles = paginator.page(page)
        except PageNotAnInteger:
            articles = paginator.page(1)
        except EmptyPage:
            articles = paginator.page(paginator.num_pages)
        
        return articles
    
    def get_total_count_par_statut(self):
        """Retourne le nombre total d'articles par statut"""
        stats = {}
        for statut_code, _ in ArticleFAI.STATUT_CHOICES:
            stats[statut_code] = ArticleFAI.objects.filter(statut=statut_code).count()
        return stats