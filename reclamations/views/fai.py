import logging
from datetime import date
from io import BytesIO

import xlsxwriter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.models import ArticleFAI
from reclamations.services.fai_service import FAIService


logger = logging.getLogger(__name__)

#=========FAI Service===============

@login_required
@role_required(['admin', 'quality_manager', 'quality_coordinator'])
def importer_fai(request):
    """Importe un fichier Excel FAI depuis l'ERP"""
    if request.method == 'POST':
        fichier = request.FILES.get('excel_file')
        if not fichier:
            messages.error(request, "Veuillez sélectionner un fichier")
            return redirect('reclamations:importer_fai')
        
        service = FAIService()
        resultat = service.importer_fichier_excel(fichier, fichier.name)
        
        if resultat['success']:
            messages.success(request, f"Import réussi! {resultat['importees']} lignes traitées, {resultat['modifiees']} mises à jour")
            if resultat['erreurs']:
                messages.warning(request, f"{len(resultat['erreurs'])} erreurs rencontrées")
        else:
            messages.error(request, f"Erreur: {resultat.get('error', 'Erreur inconnue')}")
        
        return redirect('reclamations:liste_fai')
    
    return render(request, 'reclamations/fai/importer.html')

@login_required
@role_required(['admin', 'quality_manager'])
def configurer_chemin_fai(request):
    """Configure le chemin d'accès au fichier Excel ERP"""
    if request.method == 'POST':
        chemin = request.POST.get('chemin_fichier')
        if chemin:
            request.session['fai_chemin_fichier'] = chemin
            messages.success(request, f"Chemin configuré: {chemin}")
        return redirect('reclamations:liste_fai')
    
    chemin_actuel = request.session.get('fai_chemin_fichier', '')
    return render(request, 'reclamations/fai/configurer_chemin.html', {'chemin_actuel': chemin_actuel})

@login_required
def synchroniser_fai(request):
    """Synchronise les données depuis le chemin configuré"""
    chemin = request.session.get('fai_chemin_fichier')
    if not chemin:
        messages.error(request, "Veuillez d'abord configurer le chemin du fichier")
        return redirect('reclamations:configurer_chemin_fai')
    
    service = FAIService()
    resultat = service.mettre_a_jour_depuis_chemin(chemin)
    
    if resultat['success']:
        messages.success(request, f"Synchronisation réussie! {resultat['importees']} lignes traitées")
    else:
        messages.error(request, f"Erreur: {resultat.get('error', 'Erreur inconnue')}")
    
    return redirect('reclamations:liste_fai')

@login_required
@role_required(['admin', 'quality_manager', 'quality_coordinator', 'production_manager'])
def liste_fai(request):
    """Liste des articles FAI avec pagination, recherche et filtre par statut"""
    
    # Récupération des paramètres - Assurez-vous que 'statut' est bien récupéré
    recherche_pn = request.GET.get('recherche_pn', '').strip()
    statut_filtre = request.GET.get('statut', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 20))
    
    # DEBUG: Afficher dans la console pour vérifier
    print(f"Filtre statut reçu: '{statut_filtre}'")
    print(f"Recherche PN: '{recherche_pn}'")
    
    # Construction de la requête de base
    queryset = ArticleFAI.objects.select_related('produit')
    
    # Application des filtres
    if recherche_pn:
        queryset = queryset.filter(produit__product_number__icontains=recherche_pn)
    
    if statut_filtre and statut_filtre != '':
        queryset = queryset.filter(statut=statut_filtre)
    
    # Tri
    queryset = queryset.order_by('-derniere_production')
    
    # Pagination
    paginator = Paginator(queryset, per_page)
    try:
        articles_pagines = paginator.page(page)
    except PageNotAnInteger:
        articles_pagines = paginator.page(1)
    except EmptyPage:
        articles_pagines = paginator.page(paginator.num_pages)
    
    # Statistiques pour les cartes
    statistiques = {
        'CRITIQUE': ArticleFAI.objects.filter(statut='CRITIQUE').count(),
        'URGENT': ArticleFAI.objects.filter(statut='URGENT').count(),
        'ALERTE': ArticleFAI.objects.filter(statut='ALERTE').count(),
        'INFO': ArticleFAI.objects.filter(statut='INFO').count(),
    }
    
    context = {
        'articles_pagines': articles_pagines,
        'statistiques': statistiques,
        'date_analyse': timezone.now().date(),
        'statut_actuel': statut_filtre,  # Passer le statut actuel au template
        'recherche_actuelle': recherche_pn,  # Passer la recherche actuelle
    }
    return render(request, 'reclamations/fai/liste.html', context)

@login_required
def exporter_alertes_fai(request):
    """Exporte les alertes FAI en Excel"""
    service = FAIService()
    excel_file = service.exporter_alertes_excel()
    
    response = HttpResponse(
        excel_file.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="alertes_fai_{timezone.now().date()}.xlsx"'
    return response

@login_required
def exporter_alertes_excel(self):
    """Exporte les alertes FAI vers un fichier Excel avec onglets séparés"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'font_color': 'white',
        'border': 1,
        'align': 'center'
    })
    
    urgent_format = workbook.add_format({'bg_color': '#FFC000', 'border': 1})
    critique_format = workbook.add_format({'bg_color': '#FF0000', 'font_color': 'white', 'border': 1})
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
    
    # ============ FEUILLE 1 : CRITIQUE (> 2 ans) ============
    worksheet_critique = workbook.add_worksheet("CRITIQUE (>2 ans)")
    
    headers = ['PN', 'Désignation', 'N° OF', 'Dernière production', 'Années écoulées', 'Statut']
    for col, header in enumerate(headers):
        worksheet_critique.write(0, col, header, header_format)
    
    articles_critiques = ArticleFAI.objects.filter(statut='CRITIQUE').select_related('produit').order_by('produit__product_number')
    
    row = 1
    for article in articles_critiques:
        annees = self.get_annees_ecoules(article.derniere_production) if article.derniere_production else 0
        
        worksheet_critique.write(row, 0, article.produit.product_number, critique_format)
        worksheet_critique.write(row, 1, article.produit.designation or '-', critique_format)
        worksheet_critique.write(row, 2, article.numero_of or '-', critique_format)
        worksheet_critique.write(row, 3, article.derniere_production if article.derniere_production else '-', date_format if article.derniere_production else critique_format)
        worksheet_critique.write(row, 4, f"{annees} ans" if annees else '-', critique_format)
        worksheet_critique.write(row, 5, 'CRITIQUE', critique_format)
        row += 1
    
    worksheet_critique.set_column('A:A', 20)
    worksheet_critique.set_column('B:B', 40)
    worksheet_critique.set_column('C:C', 15)
    worksheet_critique.set_column('D:D', 15)
    worksheet_critique.set_column('E:E', 15)
    worksheet_critique.set_column('F:F', 12)
    
    # ============ FEUILLE 2 : URGENT (1.8-2 ans) ============
    worksheet_urgent = workbook.add_worksheet("URGENT (1.8-2 ans)")
    
    for col, header in enumerate(headers):
        worksheet_urgent.write(0, col, header, header_format)
    
    articles_urgents = ArticleFAI.objects.filter(statut='URGENT').select_related('produit').order_by('produit__product_number')
    
    row = 1
    for article in articles_urgents:
        annees = self.get_annees_ecoules(article.derniere_production) if article.derniere_production else 0
        
        worksheet_urgent.write(row, 0, article.produit.product_number, urgent_format)
        worksheet_urgent.write(row, 1, article.produit.designation or '-', urgent_format)
        worksheet_urgent.write(row, 2, article.numero_of or '-', urgent_format)
        worksheet_urgent.write(row, 3, article.derniere_production if article.derniere_production else '-', date_format if article.derniere_production else urgent_format)
        worksheet_urgent.write(row, 4, f"{annees} ans" if annees else '-', urgent_format)
        worksheet_urgent.write(row, 5, 'URGENT', urgent_format)
        row += 1
    
    worksheet_urgent.set_column('A:A', 20)
    worksheet_urgent.set_column('B:B', 40)
    worksheet_urgent.set_column('C:C', 15)
    worksheet_urgent.set_column('D:D', 15)
    worksheet_urgent.set_column('E:E', 15)
    worksheet_urgent.set_column('F:F', 12)
    
    # ============ FEUILLE 3 : Synthèse ============
    worksheet_synth = workbook.add_worksheet("Synthèse")
    
    synth_headers = ['Statut', 'Nombre', 'Seuil', 'Action recommandée']
    for col, header in enumerate(synth_headers):
        worksheet_synth.write(0, col, header, header_format)
    
    stats = self.get_statistiques()
    seuils_desc = {
        'CRITIQUE': {'seuil': '> 2 ans', 'action': 'Production immédiate requise'},
        'URGENT': {'seuil': '1.8 - 2 ans', 'action': 'Planifier production sous 2 semaines'},
        'ALERTE': {'seuil': '1.5 - 1.8 ans', 'action': 'À surveiller, planifier prochainement'},
        'INFO': {'seuil': '< 1.5 an', 'action': 'OK - Production récente'}
    }
    
    row = 1
    for statut, count in stats.items():
        worksheet_synth.write(row, 0, statut)
        worksheet_synth.write(row, 1, count)
        worksheet_synth.write(row, 2, seuils_desc.get(statut, {}).get('seuil', '-'))
        worksheet_synth.write(row, 3, seuils_desc.get(statut, {}).get('action', '-'))
        row += 1
    
    worksheet_synth.set_column('A:A', 15)
    worksheet_synth.set_column('B:B', 10)
    worksheet_synth.set_column('C:C', 20)
    worksheet_synth.set_column('D:D', 35)
    
    workbook.close()
    output.seek(0)
    
    return output

@login_required
@role_required(['admin', 'quality_manager'])
def envoyer_alertes_email(self, destinataires=None):
    """Envoie un email avec fichier Excel des alertes (sans liste dans le corps)"""
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
    
    # Préparer l'email (corps court sans liste de PN)
    sujet = f"[FAI] Alerte stocks - {nb_critique} critique(s), {nb_urgent} urgent(s)"
    
    message_html = render_to_string('reclamations/emails/fai_alerte_email.html', {
        'nb_critique': nb_critique,
        'nb_urgent': nb_urgent,
        'date_analyse': date.today(),
        'site_url': settings.SITE_URL,
        'seuils': {
            'critique': '> 2 ans',
            'urgent': '1.8 - 2 ans',
            'alerte': '1.5 - 1.8 ans',
            'info': '< 1.5 an'
        }
    })
    
    message_texte = f"""
    ALERTE FAI - First Article Inspection
    
    Date: {date.today()}
    
    Résumé:
    - {nb_critique} article(s) en statut CRITIQUE (> 2 ans sans production)
    - {nb_urgent} article(s) en statut URGENT (1.8 - 2 ans sans production)
    
    Consultez le fichier Excel joint pour la liste détaillée.
    
    Accéder au tableau de bord: {settings.SITE_URL}/fai/liste/
    """
    
    try:
        send_mail(
            subject=sujet,
            message=message_texte,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinataires,
            html_message=message_html,
            fail_silently=False,
            attachments=[('alertes_fai.xlsx', excel_file.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]
        )
        return {'success': True, 'message': f'Email envoyé à {", ".join(destinataires)}'}
        
    except Exception as e:
        logger.error(f"Erreur envoi email FAI: {e}")
        return {'success': False, 'error': str(e)}
  
@login_required
@role_required(['admin', 'quality_manager'])
def envoyer_alertes_fai_email(request):
    """Envoie les alertes FAI par email"""
    if request.method == 'POST':
        destinataires = request.POST.getlist('destinataires')
        if not destinataires:
            destinataires = [settings.NOTIFICATION_RESPONSABLE_EMAIL]
        
        service = FAIService()
        resultat = service.envoyer_alertes_email(destinataires)
        
        if resultat['success']:
            messages.success(request, resultat['message'])
        else:
            messages.error(request, f"Erreur: {resultat.get('error', 'Erreur inconnue')}")
        
        return redirect('reclamations:liste_fai')
    
    service = FAIService()
    articles_alertes = service.get_articles_a_alerter()
    
    # Compter par statut pour l'affichage
    nb_critique = articles_alertes.filter(statut='CRITIQUE').count()
    nb_urgent = articles_alertes.filter(statut='URGENT').count()
    
    context = {
        'articles_alertes': articles_alertes,
        'destinataires_par_defaut': settings.NOTIFICATION_RESPONSABLE_EMAIL,
        'nb_critique': nb_critique,
        'nb_urgent': nb_urgent,
    }
    return render(request, 'reclamations/fai/envoyer_alertes.html', context)
