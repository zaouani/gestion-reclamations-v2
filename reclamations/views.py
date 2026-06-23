import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import logging
from django.conf import settings 
from django.utils import timezone
from .models import (Reclamation, Client, Produit, LigneReclamation, NonConformite, UAP, Site, ObjectifsAnnuel, 
    Programme, SiteClient, Livraison, HuitD, Participant8D, ArticleFAI, HistoriqueImportFAI, CauseIshikawa, 
    VRS, FacteurVRS, CauseCinqP, FacteurHumain, 
    EvaluationFacteurHumain, Action8D, Alteration8D, Evidence8D, CinqW2H,
       )
from django.http import JsonResponse
from accounts.decorators import role_required, permission_required
from django.db.models import Count, Q, F, Avg,Max, Sum, Prefetch
from django.db.models.functions import TruncMonth, ExtractMonth
from datetime import timedelta, datetime
import json
from django.db import connection
from decimal import Decimal
from .utils import PPMCalculator, AMDEC_calculator
from .dashboard_stats import DashboardStats
import io
import xlsxwriter
from django.http import HttpResponse
from django.template.loader import get_template
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import pandas as pd
from .notifications import NotificationService
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from .services.ai_service import AIService
from .services.chatbot_service import ChatbotService
from io import BytesIO
from typing import Generator
from .services.ollama_service import OllamaService
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from urllib.parse import unquote
from .services.fai_service import FAIService
from django.core.cache import cache
from django.template.loader import render_to_string


# CONFIGURATION LOGGER
logger = logging.getLogger(__name__)
ollama_service = OllamaService(model="phi3:mini") 
moyenne_reactivite=100 
ollama_service = OllamaService(model="llama3.2:3b")

# ================ EXPORT PDF  ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def export_dashboard_pdf(request):
    """Exporte le tableau de bord en PDF avec ReportLab"""
    
    stats = DashboardStats()
    data = stats.get_all_stats()
    
    # Créer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="dashboard_{timezone.now().date()}.pdf"'
    
    # Créer le document PDF
    doc = SimpleDocTemplate(response, pagesize=A4, 
                           topMargin=1*cm, bottomMargin=1*cm,
                           leftMargin=1.5*cm, rightMargin=1.5*cm)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # Centré
        spaceAfter=20,
        textColor=colors.HexColor('#4CAF50')
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=10,
        spaceBefore=15,
        textColor=colors.HexColor('#333333')
    )
    
    normal_style = styles['Normal']
    
    # Liste des éléments à ajouter
    elements = []
    
    # Titre
    elements.append(Paragraph("Tableau de bord - Gestion des Réclamations", title_style))
    elements.append(Paragraph(f"Exporté le : {timezone.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # KPIs
    elements.append(Paragraph("Indicateurs clés", heading_style))
    
    kpis_data = [
        ['Indicateur', 'Valeur'],
        ['Total réclamations', str(data['global']['total'])],
        ['Réclamations ouvertes', str(data['global']['ouvertes'])],
        ['Réclamations clôturées', str(data['global']['cloturees'])],
        ['Taux de clôture', f"{data['global']['taux_cloture']}%"],
        ['Délai moyen de clôture', f"{data['delai_moyen']} jours"],
        ['Taux de réactivité', f"{data['global']['taux_reactivite']}%"],
        ['PPM Global', f"{data['ppm']['global']:.0f}"],
    ]
    
    kpis_table = Table(kpis_data, colWidths=[6*cm, 4*cm])
    kpis_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(kpis_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Top clients
    elements.append(Paragraph("Top 10 clients", heading_style))
    
    clients_data = [['Client', 'Nombre de réclamations']]
    for label, value in zip(data['clients']['labels'], data['clients']['data']):
        clients_data.append([label, str(value)])
    
    clients_table = Table(clients_data, colWidths=[9*cm, 3*cm])
    clients_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(clients_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Évolution mensuelle
    elements.append(Paragraph("Évolution mensuelle", heading_style))
    
    mois_data = [['Mois', 'Nombre de réclamations']]
    for label, value in zip(data['mois']['labels'], data['mois']['data']):
        mois_data.append([label, str(value)])
    
    mois_table = Table(mois_data, colWidths=[7*cm, 5*cm])
    mois_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(mois_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Types de NC
    elements.append(Paragraph("Répartition par type de NC", heading_style))
    
    type_data = [['Type', 'Nombre']]
    for type_item in data['type_nc']:
        type_data.append([type_item['label'], str(type_item['total'])])
    
    type_table = Table(type_data, colWidths=[9*cm, 3*cm])
    type_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(type_table)
    
    # Construire le PDF
    doc.build(elements)
    
    return response

# ================ EXPORT EXCEL ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def export_reclamations_excel(request):
    """Exporte toutes les réclamations en Excel avec les non-conformités"""
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4CAF50',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    header_blue_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2196F3',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    header_orange_format = workbook.add_format({
        'bold': True,
        'bg_color': '#FF9800',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    cell_center_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    number_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    date_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy'
    })
    
    datetime_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy hh:mm'
    })
    
    # Récupérer toutes les réclamations avec les relations nécessaires
    reclamations = Reclamation.objects.select_related(
        'client', 
        'site_client', 
        'programme', 
        'createur'
    ).prefetch_related(
        Prefetch('lignes', queryset=LigneReclamation.objects.select_related(
            'produit', 'site', 'site__uap', 'uap_concernee'
        ).prefetch_related('non_conformites'))
    ).order_by('-date_reclamation')
    
    # ==================== FEUILLE 1: RÉCLAMATIONS ====================
    worksheet_reclamations = workbook.add_worksheet('Réclamations')
    
    headers = [
        'N° Réclamation', 'Date réclamation', 'Client', 'Site client', 'Programme',
        'Type NC', 'Imputation', 'N° 4D', 'N° 8D', 'État 4D', 'État 8D', 
        'Clôturé', 'Date clôture', 'Date clôture 4D', 'Date clôture 8D',
        'Evidence', 'ME', 'Décision', 'NQC (MAD)', 'Créateur', 'Date création'
    ]
    
    for col, header in enumerate(headers):
        worksheet_reclamations.write(0, col, header, header_format)
    
    row = 1
    for rec in reclamations:
        col = 0
        worksheet_reclamations.write(row, col, rec.numero_reclamation, cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.date_reclamation.strftime('%d/%m/%Y') if rec.date_reclamation else '-', date_format); col += 1
        worksheet_reclamations.write(row, col, rec.client.nom, cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.site_client.nom if rec.site_client else '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.programme.nom if rec.programme else '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.get_type_nc_display(), cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.get_imputation_display(), cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.numero_4d or '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.numero_8d or '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.get_etat_4d_display(), cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.get_etat_8d_display(), cell_format); col += 1
        worksheet_reclamations.write(row, col, 'Oui' if rec.cloture else 'Non', cell_center_format); col += 1
        worksheet_reclamations.write(row, col, rec.date_cloture.strftime('%d/%m/%Y') if rec.date_cloture else '-', date_format); col += 1
        worksheet_reclamations.write(row, col, rec.date_cloture_4d.strftime('%d/%m/%Y') if rec.date_cloture_4d else '-', date_format); col += 1
        worksheet_reclamations.write(row, col, rec.date_cloture_8d.strftime('%d/%m/%Y') if rec.date_cloture_8d else '-', date_format); col += 1
        worksheet_reclamations.write(row, col, rec.evidence or '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, 'Oui' if rec.me else 'Non', cell_center_format); col += 1
        worksheet_reclamations.write(row, col, rec.decision or '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, float(rec.nqc) if rec.nqc else 0, number_format); col += 1
        worksheet_reclamations.write(row, col, rec.createur.get_full_name() or rec.createur.username if rec.createur else '-', cell_format); col += 1
        worksheet_reclamations.write(row, col, rec.date_creation.strftime('%d/%m/%Y %H:%M'), datetime_format); col += 1
        row += 1
    
    # Ajuster les colonnes
    column_widths = [18, 14, 22, 18, 18, 14, 12, 15, 15, 12, 12, 10, 14, 14, 14, 30, 8, 30, 12, 20, 18]
    for col, width in enumerate(column_widths):
        worksheet_reclamations.set_column(col, col, width)
    
    # Ajouter un filtre
    worksheet_reclamations.autofilter(0, 0, row - 1, len(headers) - 1)
    
    # ==================== FEUILLE 2: LIGNES DE RÉCLAMATION ====================
    worksheet_lignes = workbook.add_worksheet('Lignes de réclamation')
    
    headers_lignes = [
        'N° Réclamation', 'Date', 'Client', 'Site production', 'UAP', 
        'Produit', 'Désignation', 'Quantité', 'Description NC', 'Commentaire'
    ]
    
    for col, header in enumerate(headers_lignes):
        worksheet_lignes.write(0, col, header, header_blue_format)
    
    row = 1
    for rec in reclamations:
        for ligne in rec.lignes.all():
            col = 0
            worksheet_lignes.write(row, col, rec.numero_reclamation, cell_format); col += 1
            worksheet_lignes.write(row, col, rec.date_reclamation.strftime('%d/%m/%Y') if rec.date_reclamation else '-', date_format); col += 1
            worksheet_lignes.write(row, col, rec.client.nom, cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.site.nom if ligne.site else '-', cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.uap_concernee.nom if ligne.uap_concernee else (ligne.site.uap.nom if ligne.site and ligne.site.uap else '-'), cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.produit.product_number, cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.produit.designation or '-', cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.quantite, number_format); col += 1
            worksheet_lignes.write(row, col, ligne.description_non_conformite or '-', cell_format); col += 1
            worksheet_lignes.write(row, col, ligne.commentaire or '-', cell_format); col += 1
            row += 1
    
    column_widths_lignes = [18, 12, 22, 18, 15, 15, 30, 10, 40, 30]
    for col, width in enumerate(column_widths_lignes):
        worksheet_lignes.set_column(col, col, width)
    
    if row > 1:
        worksheet_lignes.autofilter(0, 0, row - 1, len(headers_lignes) - 1)
    
    # ==================== FEUILLE 3: NON-CONFORMITÉS ====================
    worksheet_nc = workbook.add_worksheet('Non-conformités')
    
    headers_nc = [
        'N° Réclamation', 'Date', 'Client', 'Site', 'Produit', 
        'Quantité ligne', 'Description NC', 'Quantité NC', 'Date création NC'
    ]
    
    for col, header in enumerate(headers_nc):
        worksheet_nc.write(0, col, header, header_orange_format)
    
    row = 1
    for rec in reclamations:
        for ligne in rec.lignes.all():
            for nc in ligne.non_conformites.all():
                col = 0
                worksheet_nc.write(row, col, rec.numero_reclamation, cell_format); col += 1
                worksheet_nc.write(row, col, rec.date_reclamation.strftime('%d/%m/%Y') if rec.date_reclamation else '-', date_format); col += 1
                worksheet_nc.write(row, col, rec.client.nom, cell_format); col += 1
                worksheet_nc.write(row, col, ligne.site.nom if ligne.site else '-', cell_format); col += 1
                worksheet_nc.write(row, col, ligne.produit.product_number, cell_format); col += 1
                worksheet_nc.write(row, col, ligne.quantite, number_format); col += 1
                worksheet_nc.write(row, col, nc.description, cell_format); col += 1
                worksheet_nc.write(row, col, nc.quantite, number_format); col += 1
                worksheet_nc.write(row, col, nc.date_creation.strftime('%d/%m/%Y %H:%M'), datetime_format); col += 1
                row += 1
    
    column_widths_nc = [18, 12, 22, 18, 15, 12, 45, 12, 18]
    for col, width in enumerate(column_widths_nc):
        worksheet_nc.set_column(col, col, width)
    
    if row > 1:
        worksheet_nc.autofilter(0, 0, row - 1, len(headers_nc) - 1)
    
    # ==================== FEUILLE 4: RÉSUMÉ STATISTIQUE ====================
    worksheet_stats = workbook.add_worksheet('Statistiques')
    
    # Titre
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'font_color': '#2196F3'
    })
    
    stat_label_format = workbook.add_format({
        'bold': True,
        'bg_color': '#E3F2FD',
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    stat_value_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    worksheet_stats.write(0, 0, 'RÉSUMÉ DES RÉCLAMATIONS', title_format)
    worksheet_stats.write(1, 0, f'Export réalisé le {timezone.now().strftime("%d/%m/%Y à %H:%M")}', cell_format)
    
    # Statistiques générales
    row = 3
    stats = [
        ('Total réclamations', reclamations.count()),
        ('Réclamations ouvertes', reclamations.filter(cloture=False).count()),
        ('Réclamations clôturées', reclamations.filter(cloture=True).count()),
        ('', ''),
        ('Par type de NC', ''),
    ]
    
    for label, value in stats:
        worksheet_stats.write(row, 0, label, stat_label_format)
        worksheet_stats.write(row, 1, value, stat_value_format)
        row += 1
    
    # Statistiques par type de NC
    from django.db.models import Count
    type_stats = reclamations.values('type_nc').annotate(count=Count('id'))
    
    for stat in type_stats:
        type_display = dict(Reclamation.TYPE_NC_CHOICES).get(stat['type_nc'], stat['type_nc'])
        worksheet_stats.write(row, 0, f"  - {type_display}", stat_label_format)
        worksheet_stats.write(row, 1, stat['count'], stat_value_format)
        row += 1
    
    row += 1
    worksheet_stats.write(row, 0, 'Par imputation', stat_label_format)
    row += 1
    
    # Statistiques par imputation
    imp_stats = reclamations.values('imputation').annotate(count=Count('id'))
    for stat in imp_stats:
        imp_display = dict(Reclamation.IMPUTATION_CHOICES).get(stat['imputation'], stat['imputation'])
        worksheet_stats.write(row, 0, f"  - {imp_display}", stat_label_format)
        worksheet_stats.write(row, 1, stat['count'], stat_value_format)
        row += 1
    
    worksheet_stats.set_column(0, 0, 30)
    worksheet_stats.set_column(1, 1, 15)
    
    # ==================== FINALISATION ====================
    workbook.close()
    
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reclamations_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    return response

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def export_dashboard_excel(request):
    """Exporte les données du dashboard en Excel"""
    
    stats = DashboardStats()
    data = stats.get_all_stats()
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4CAF50',
        'font_color': 'white',
        'border': 1,
        'align': 'center'
    })
    
    cell_format = workbook.add_format({'border': 1})
    number_format = workbook.add_format({'border': 1, 'align': 'right'})
    
    # KPIs
    worksheet_kpi = workbook.add_worksheet('KPIs')
    kpis = [
        ['Indicateur', 'Valeur'],
        ['Total réclamations', data['global']['total']],
        ['Réclamations ouvertes', data['global']['ouvertes']],
        ['Réclamations clôturées', data['global']['cloturees']],
        ['Taux de clôture', f"{data['global']['taux_cloture']}%"],
        ['Délai moyen de clôture', f"{data['delai_moyen']} jours"],
        ['Taux de réactivité', f"{data['global']['taux_reactivite']}%"],
        ['PPM Global', f"{data['ppm']['global']:.0f}"],
    ]
    
    for row, row_data in enumerate(kpis):
        for col, value in enumerate(row_data):
            if row == 0:
                worksheet_kpi.write(row, col, value, header_format)
            else:
                worksheet_kpi.write(row, col, value, cell_format)
    
    worksheet_kpi.set_column(0, 0, 25)
    worksheet_kpi.set_column(1, 1, 20)
    
    # Top clients
    worksheet_clients = workbook.add_worksheet('Top clients')
    worksheet_clients.write(0, 0, 'Client', header_format)
    worksheet_clients.write(0, 1, 'Nombre', header_format)
    
    for row, (label, value) in enumerate(zip(data['clients']['labels'], data['clients']['data']), 1):
        worksheet_clients.write(row, 0, label, cell_format)
        worksheet_clients.write(row, 1, value, number_format)
    
    worksheet_clients.set_column(0, 0, 30)
    worksheet_clients.set_column(1, 1, 15)
    
    # Évolution mensuelle
    worksheet_mois = workbook.add_worksheet('Évolution mensuelle')
    worksheet_mois.write(0, 0, 'Mois', header_format)
    worksheet_mois.write(0, 1, 'Nombre', header_format)
    
    for row, (label, value) in enumerate(zip(data['mois']['labels'], data['mois']['data']), 1):
        worksheet_mois.write(row, 0, label, cell_format)
        worksheet_mois.write(row, 1, value, number_format)
    
    worksheet_mois.set_column(0, 0, 20)
    worksheet_mois.set_column(1, 1, 15)
    
    workbook.close()
    
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="dashboard_{timezone.now().date()}.xlsx"'
    
    return response

# ================ GESTION DES KPIs ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer','viewer'])
def dashboard(request):
    """Tableau de bord avec toutes les statistiques"""
    
    # Initialiser le calculateur de statistiques
    stats = DashboardStats()
    
    # Récupérer toutes les statistiques
    data = stats.get_all_stats()

    # Extraire les données NQC
    nqc_data = data.get('nqc', {}).get('mois', {})

    # Récupérer les données pour le graphique par site client
    site_client_data = data.get('reclamations_par_site_client', {})

    # Récupérer tous les clients pour le filtre
    clients = Client.objects.filter(actif=True).order_by('nom')
    
    # Convertir les Decimal en float pour NQC par client
    nqc_par_client_raw = data.get('nqc', {}).get('par_client', [])
    nqc_par_client = []
    for item in nqc_par_client_raw:
        nqc_par_client.append({
            'client__nom': item.get('client__nom', item.get('client_nom', 'Client inconnu')),
            'client_nom': item.get('client__nom', item.get('client_nom', 'Client inconnu')),
            'cout_total': float(item.get('cout_total', 0)) if item.get('cout_total') else 0,
            'nombre': int(item.get('nombre', 0))
        })
    
    # Convertir les Decimal en float pour NQC par type
    nqc_par_type_raw = data.get('nqc', {}).get('par_type', [])
    nqc_par_type = []
    for item in nqc_par_type_raw:
        nqc_par_type.append({
            'label': item.get('label', ''),
            'cout': float(item.get('cout', 0)) if item.get('cout') else 0,
            'nombre': int(item.get('nombre', 0))
        })
    
    # Récupérer les données de réactivité par UAP
    reactivite_uap_data = data.get('taux_reactivite_par_uap', {})
    # Récupérer les top défauts récurrents
    top_defauts_recurrents = data.get('top_defauts_recurrents', [])
    # Récupérer le taux de récurrence globale
    taux_recurrence_globale = data.get('taux_recurrence_globale', {})
    # Convertir les Decimal pour PPM evolution
    ppm_evolution_raw = data.get('ppm', {}).get('evolution', [])
    ppm_evolution = []
    for item in ppm_evolution_raw:
        ppm_evolution.append({
            'mois_nom': item.get('mois_nom', ''),
            'ppm': float(item.get('ppm', 0)) if item.get('ppm') else 0
        })

    # Calculer la moyenne des taux de réactivité par UAP pour l'année courante
    moyenne_reactivite = 0
    annee_courante = timezone.now().year
    
    if reactivite_uap_data and annee_courante in reactivite_uap_data:
        annees_data = reactivite_uap_data.get(annee_courante, {})
        data_mensuelle = annees_data.get('data', {})
        
        # Récupérer tous les taux
        tous_les_taux = []
        for mois, uap_data in data_mensuelle.items():
            for uap, taux in uap_data.items():
                if taux > 0:  # Ne compter que les UAP avec des données
                    tous_les_taux.append(taux)
        
        # Calculer la moyenne
        if tous_les_taux:
            moyenne_reactivite = sum(tous_les_taux) / len(tous_les_taux)
    
    # Calculer aussi la moyenne pour 2025 (ou autre année)
    moyenne_reactivite_2025 = 0
    if reactivite_uap_data and 2025 in reactivite_uap_data:
        annees_data = reactivite_uap_data.get(2025, {})
        data_mensuelle = annees_data.get('data', {})
        
        tous_les_taux = []
        for mois, uap_data in data_mensuelle.items():
            for uap, taux in uap_data.items():
                if taux > 0:
                    tous_les_taux.append(taux)
        
        if tous_les_taux:
            moyenne_reactivite_2025 = sum(tous_les_taux) / len(tous_les_taux)

    
    
    # Préparer le contexte avec les données JSON
    context = {
        # Stats globales
        'total_reclamations': data.get('global', {}).get('total', 0),
        'reclamations_ouvertes': data.get('global', {}).get('ouvertes', 0),
        'reclamations_cloturees': data.get('global', {}).get('cloturees', 0),
        'taux_cloture': data.get('global', {}).get('taux_cloture', 0),
        'taux_reactivite': data.get('global', {}).get('taux_reactivite', 0),
        'duree_moyenne': data.get('delai_moyen', 0),
        
        # Données pour les graphiques
        'clients_labels': json.dumps(data.get('clients', {}).get('labels', []), ensure_ascii=False),
        'clients_data': json.dumps(data.get('clients', {}).get('data', [])),
        
        'uap_labels': json.dumps(data.get('uap', {}).get('labels', []), ensure_ascii=False),
        'uap_data': json.dumps(data.get('uap', {}).get('data', [])),
        
        'mois_labels': json.dumps(data.get('mois', {}).get('labels', []), ensure_ascii=False),
        'mois_data': json.dumps(data.get('mois', {}).get('data', [])),
        
        'typologie_par_mois': json.dumps(data.get('typologie', []), ensure_ascii=False),
        'type_nc_labels': json.dumps([t.get('label', '') for t in data.get('typologie', [])], ensure_ascii=False),
        
        'imputation_labels': json.dumps(data.get('imputation', {}).get('labels', []), ensure_ascii=False),
        'imputation_data': json.dumps(data.get('imputation', {}).get('data', [])),

        # NQC (converti)
        'nqc_mois_labels': json.dumps(nqc_data.get('labels', []), ensure_ascii=False),
        'nqc_mois_nombre': json.dumps(nqc_data.get('data_nombre', [])),
        'nqc_mois_cout': json.dumps(nqc_data.get('data_cout', [])),
        'nqc_total': float(nqc_data.get('total_nqc', 0)),
        'nqc_total_reclamations': nqc_data.get('total_reclamations', 0),
        'nqc_cout_moyen': float(nqc_data.get('cout_moyen_global', 0)),
        'nqc_par_client': nqc_par_client,
        'nqc_par_type': nqc_par_type,
        
        # Stats supplémentaires
        'type_nc_stats': data.get('type_nc', []),
        
        # Données PPM (converti)
        'ppm_clients': data.get('ppm', {}).get('clients', []),
        'ppm_labels': json.dumps(data.get('ppm', {}).get('labels', []), ensure_ascii=False),
        'ppm_data': json.dumps(data.get('ppm', {}).get('data', [])),
        'ppm_evolution': json.dumps(ppm_evolution, ensure_ascii=False),
        'ppm_global': float(data.get('ppm', {}).get('global', 0)),
        
        # Objectifs
        'objectifs_par_site': data.get('objectifs', {}).get('objectifs', []),
        'objectifs_moyennes': data.get('objectifs', {}).get('moyennes', {}),
        'annee_courante': stats.annee_courante,
        
        # Taux de récurrence (converti)
        'top_produits_recurrents': data.get('top_produits_recurrents', []),
        'top_defauts_recurrents': top_defauts_recurrents,
        'taux_recurrence_globale': taux_recurrence_globale,

        # Données pour le graphique par site client
        'site_client_labels': json.dumps(site_client_data.get('labels', []), ensure_ascii=False),
        'site_client_data': json.dumps(site_client_data.get('data', [])),

        # Données pour le graphique de réactivité par UAP (toutes années)
        'reactivite_uap_par_annee': reactivite_uap_data,
        'reactivite_uap_annees': list(reactivite_uap_data.keys()),

        # Taux de réactivité moyens
        'moyenne_reactivite': round(moyenne_reactivite, 1),
        'moyenne_reactivite_2025': round(moyenne_reactivite_2025, 1),
        'clients': clients,

    }
    
    return render(request, 'reclamations/dashboard.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def taux_recurrence_produits(request):
    """Calcule le taux de récurrence des défauts par produit"""
    
    # Récupérer tous les produits actifs
    produits = Produit.objects.filter(actif=True).order_by('product_number')
    
    # Nombre total de réclamations
    total_reclamations = Reclamation.objects.count()
    
    produits_data = []
    
    for produit in produits:
        # Récupérer les lignes de réclamation pour ce produit
        lignes = LigneReclamation.objects.filter(produit=produit, reclamation__imputation__in=['CIM', 'ALERTE'])
        
        if not lignes.exists():
            continue
        
        # Compter le nombre de réclamations distinctes pour ce produit
        nb_reclamations = lignes.values('reclamation').distinct().count()
        
        # Calculer le taux de récurrence
        if total_reclamations > 0:
            taux = (nb_reclamations / total_reclamations) * 100
        else:
            taux = 0
        
        # Ajouter à la liste des données
        produits_data.append({
            'produit': produit,  # ← L'objet produit complet avec son ID
            'nb_reclamations': nb_reclamations,
            'taux_recurrence': round(taux, 2)
        })
    
    # Trier par taux de récurrence décroissant
    produits_data.sort(key=lambda x: x['taux_recurrence'], reverse=True)
    
    context = {
        'produits_data': produits_data,
        'total_reclamations': total_reclamations,
    }
    
    return render(request, 'reclamations/produit/recurrence.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def detail_recurrence_produit(request, product_id):
    """Détail de la récurrence pour un produit spécifique"""
    
    produit = get_object_or_404(Produit, pk=product_id)
    
    # Récupérer toutes les lignes de réclamation pour ce produit
    lignes = LigneReclamation.objects.filter(
        produit=produit
    ).select_related(
        'reclamation', 
        'reclamation__client', 
        'uap_concernee'
    ).prefetch_related(
        'non_conformites'  # ← Précharger les non-conformités
    ).order_by('-reclamation__date_reclamation')
    
    # Nombre de réclamations distinctes
    nb_reclamations = lignes.values('reclamation').distinct().count()
    
    # CORRECTION : Utiliser NonConformite pour les descriptions
    non_conformites = NonConformite.objects.filter(
        ligne_reclamation__produit=produit
    )
    
    # Analyser les descriptions de non-conformité
    descriptions = non_conformites.values('description').annotate(
        nb_occurences=Count('id'),
        quantite_totale=Sum('quantite'),
        nb_reclamations=Count('ligne_reclamation__reclamation', distinct=True)
    ).order_by('-nb_occurences')
    
    defauts_data = []
    total_nc = non_conformites.count()
    
    for desc in descriptions:
        # Calcul du taux basé sur le nombre total de NC
        if total_nc > 0:
            taux = (desc['nb_occurences'] / total_nc) * 100
        else:
            taux = 0
        
        defauts_data.append({
            'description': desc['description'] or "Non spécifié",
            'nb_occurences': desc['nb_occurences'],
            'quantite_totale': desc['quantite_totale'] or 0,
            'nb_reclamations': desc['nb_reclamations'],
            'taux': round(taux, 2)
        })
    
    # Statistiques supplémentaires
    stats = {
        'total_nc': total_nc,
        'total_quantite': non_conformites.aggregate(total=Sum('quantite'))['total'] or 0,
        'nb_reclamations': nb_reclamations,
        'nb_lignes': lignes.count(),
        'nb_defauts_distincts': descriptions.count(),
    }
    
    context = {
        'produit': produit,
        'nb_reclamations': nb_reclamations,
        'defauts': defauts_data,
        'lignes': lignes[:20],  # Dernières 20 réclamations
        'stats': stats,
        'non_conformites': non_conformites[:50],  # Dernières 50 NC
    }
    
    return render(request, 'reclamations/produit/recurrence_detail.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def taux_recurrence_nc(request):
    """
    Calcule le taux de récurrence des descriptions de non-conformité (NC)
    Taux de récurrence = Nombre de réclamations contenant au moins un produit avec le défaut / Nombre total de réclamations
    """
    
    # Récupérer les filtres
    search = request.GET.get('search', '')
    imputation = request.GET.get('imputation', 'CIM')
    
    # Filtre de base des réclamations
    reclamations_filter = Reclamation.objects.all()
    if imputation:
        reclamations_filter = reclamations_filter.filter(imputation=imputation)
    
    # Total des réclamations pour le filtre choisi (dénominateur)
    total_reclamations = reclamations_filter.count()
    
    # Filtre des non-conformités
    nc_filter = NonConformite.objects.filter(
        ligne_reclamation__reclamation__imputation=imputation if imputation else None
    )
    
    # Appliquer la recherche si présente
    if search:
        nc_filter = nc_filter.filter(description__icontains=search)
    
    # Récupérer toutes les descriptions de NC distinctes
    descriptions = nc_filter.values('description').annotate(
        nb_occurences=Count('id'),
        quantite_totale=Sum('quantite'),
        nb_produits=Count('ligne_reclamation__produit', distinct=True),
        nb_reclamations_concernees=Count('ligne_reclamation__reclamation', distinct=True)
    ).filter(
        description__isnull=False
    ).exclude(
        description=''
    ).order_by('-nb_reclamations_concernees')
    
    resultats = []
    for desc in descriptions:
        description = desc['description']
        nb_reclamations_concernees = desc['nb_reclamations_concernees']
        
        # Calcul du taux de récurrence
        taux = (nb_reclamations_concernees / total_reclamations * 100) if total_reclamations > 0 else 0
        
        # Produits concernés
        produits_concernes = Produit.objects.filter(
            lignes_reclamation__non_conformites__description=description,
            lignes_reclamation__reclamation__imputation=imputation if imputation else None
        ).distinct().values_list('product_number', flat=True)[:10]
        
        resultats.append({
            'description': description,
            'nb_occurences': nb_reclamations_concernees,
            'quantite_totale': desc['quantite_totale'] or 0,
            'nb_produits': desc['nb_produits'],
            'nb_reclamations': nb_reclamations_concernees,
            'taux_recurrence': round(taux, 2),
            'produits_concernes': list(produits_concernes),
        })
    
    # Statistiques globales
    total_nc_distinctes = len(resultats)
    total_occurences_nc = sum(r['nb_occurences'] for r in resultats)
    
    context = {
        'descriptions': resultats,
        'total_reclamations_cim': total_reclamations,
        'total_nc_distinctes': total_nc_distinctes,
        'total_occurences_nc': total_occurences_nc,
        'date_analyse': timezone.now(),
        'filtre_imputation': imputation,
        'search': search,
        'imputation_choices': Reclamation.IMPUTATION_CHOICES,
        'imputation_label': dict(Reclamation.IMPUTATION_CHOICES).get(imputation, 'Toutes') if imputation else 'Toutes',
    }
    
    return render(request, 'reclamations/produit/recurrence_nc.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def detail_recurrence_nc(request, description):
    """
    Détail de la récurrence pour une description de non-conformité spécifique
    UNIQUEMENT pour les réclamations avec imputation CIM
    """
    
    description = unquote(description)
    
    # Récupérer tous les produits concernés (CIM uniquement)
    produits = Produit.objects.filter(
        lignes_reclamation__non_conformites__description=description,
        lignes_reclamation__reclamation__imputation='CIM'
    ).distinct().annotate(
        nb_occurences=Count('lignes_reclamation__non_conformites'),
        quantite_totale=Sum('lignes_reclamation__non_conformites__quantite')
    ).order_by('-nb_occurences')
    
    # Récupérer toutes les non-conformités (CIM uniquement)
    non_conformites = NonConformite.objects.filter(
        description=description,
        ligne_reclamation__reclamation__imputation='CIM'
    ).select_related(
        'ligne_reclamation__reclamation',
        'ligne_reclamation__reclamation__client',
        'ligne_reclamation__produit',
        'ligne_reclamation__uap_concernee'
    ).order_by('-ligne_reclamation__reclamation__date_reclamation')
    
    nb_reclamations = non_conformites.values('ligne_reclamation__reclamation').distinct().count()
    
    # Produits data
    produits_data = []
    for produit in produits:
        produits_data.append({
            'produit': produit,
            'nb_occurences': produit.nb_occurences,
            'quantite_totale': produit.quantite_totale or 0,
            'taux': round(produit.nb_occurences / non_conformites.count() * 100, 1) if non_conformites.count() > 0 else 0
        })
    
    # Clients data (CIM uniquement)
    clients_data = non_conformites.values('ligne_reclamation__reclamation__client__nom').annotate(
        nb_occurences=Count('id'),
        quantite_totale=Sum('quantite')
    ).order_by('-nb_occurences')[:10]
    
    # Évolution (CIM uniquement)
    evolution = non_conformites.annotate(
        mois=TruncMonth('ligne_reclamation__reclamation__date_reclamation')
    ).values('mois').annotate(
        nb_occurences=Count('id')
    ).order_by('mois')
    
    evolution_data = []
    for item in evolution:
        if item['mois']:
            evolution_data.append({
                'mois': item['mois'].strftime('%B %Y').capitalize(),
                'nb_occurences': item['nb_occurences']
            })
    
    # ========== SECTION ANALYSE : Causes racines à partir d'Ishikawa ==========
    # Récupérer les réclamations CIM concernées
    reclamations_cim = Reclamation.objects.filter(
        imputation='CIM',
        lignes__non_conformites__description=description
    ).distinct()
    
    # Récupérer les causes Ishikawa liées à ces réclamations
    causes_ishikawa = CauseIshikawa.objects.filter(
        huitd__reclamation__in=reclamations_cim
    ).select_related(
        'huitd__reclamation'
    )
    
    # Causes racines distinctes (occurrence et non détection)
    causes_racines = []
    
    # Ajouter les causes Ishikawa
    for cause in causes_ishikawa:
        causes_racines.append({
            'cause': cause.cause,
            'categorie': cause.get_categorie_display(),
            'type': cause.get_type_cause_display(),
            'methode': 'Ishikawa (6M)',
            'reclamation': cause.huitd.reclamation,
            'produit': None,
            'statut': 'Analyse'
        })
    
    # Ajouter également les causes 5P
    causes_5p = CauseCinqP.objects.filter(
        huitd__reclamation__in=reclamations_cim
    ).select_related(
        'huitd__reclamation'
    )
    
    for cause in causes_5p:
        causes_racines.append({
            'cause': f"5P - Facteur: {cause.facteur_prouve}",
            'categorie': cause.get_type_cause_display(),
            'type': cause.get_type_cause_display(),
            'methode': '5 Pourquoi',
            'reclamation': cause.huitd.reclamation,
            'produit': None,
            'statut': 'Analyse'
        })
    
    # Regrouper les causes par type
    causes_par_type = {}
    for cause in causes_racines:
        type_cause = cause.get('type', 'Général')
        if type_cause not in causes_par_type:
            causes_par_type[type_cause] = []
        causes_par_type[type_cause].append(cause)
    
    # ========== SECTION ACTIONS : Plan d'actions 8D ==========
    # Récupérer les actions 8D liées aux réclamations CIM
    actions_8d = Action8D.objects.filter(
        huitd__reclamation__in=reclamations_cim
    ).select_related(
        'huitd__reclamation'
    ).order_by('statut', '-date_prevue')
    
    actions_par_statut = {
        'PLANIFIE': actions_8d.filter(statut='PLANIFIE'),
        'EN_COURS': actions_8d.filter(statut='EN_COURS'),
        'REALISE': actions_8d.filter(statut='REALISE'),
        'ABANDONNE': actions_8d.filter(statut='ABANDONNE'),
    }
    
    actions_stats = {
        'total': actions_8d.count(),
        'planifiees': actions_8d.filter(statut='PLANIFIE').count(),
        'en_cours': actions_8d.filter(statut='EN_COURS').count(),
        'realisees': actions_8d.filter(statut='REALISE').count(),
        'abandonnees': actions_8d.filter(statut='ABANDONNE').count(),
        'efficaces': actions_8d.filter(efficacite='100').count(),
    }
    
    # Actions par type
    actions_par_type = {
        'CORRECTIVE': actions_8d.filter(type_action='CORRECTIVE'),
        'PREVENTIVE': actions_8d.filter(type_action='PREVENTIVE'),
    }
    
    # Calculer le taux de réalisation
    taux_realisation = 0
    if actions_stats['total'] > 0:
        taux_realisation = round((actions_stats['realisees'] / actions_stats['total']) * 100, 1)
    
    # Formater les lignes pour l'affichage
    lignes_data = []
    
    for nc in non_conformites[:50]:
        reclamation = nc.ligne_reclamation.reclamation
        
        # Récupérer les actions 8D pour cette réclamation
        actions_reclamation = actions_8d.filter(huitd__reclamation=reclamation)
        
        lignes_data.append({
            'reclamation': reclamation,
            'produit': nc.ligne_reclamation.produit,
            'quantite': nc.quantite,
            'description_nc': nc.description,
            'uap_concernee': nc.ligne_reclamation.uap_concernee,
            'commentaire': nc.ligne_reclamation.commentaire,
            'actions': actions_reclamation,
            'nb_actions': actions_reclamation.count(),
        })
    
    context = {
        'description': description,
        'nb_reclamations': nb_reclamations,
        'total_occurences': non_conformites.count(),
        'quantite_totale': non_conformites.aggregate(Sum('quantite'))['quantite__sum'] or 0,
        'produits': produits_data,
        'clients': list(clients_data),
        'evolution': evolution_data,
        'lignes': lignes_data,
        'filtre_imputation': 'CIM',
        'causes_racines': causes_racines,
        'causes_par_type': causes_par_type,
        'actions_8d': actions_8d,
        'actions_par_statut': actions_par_statut,
        'actions_par_type': actions_par_type,
        'actions_stats': actions_stats,
        'taux_realisation': taux_realisation,
    }
    
    return render(request, 'reclamations/produit/detail_recurrence_nc.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def exporter_recurrence_nc_excel(request):
    """
    Exporte les données de taux de récurrence NC vers un fichier Excel
    """
    # Même logique que taux_recurrence_nc
    total_reclamations_cim = Reclamation.objects.filter(
        imputation='CIM'
    ).count()
    
    descriptions = NonConformite.objects.filter(
        ligne_reclamation__reclamation__imputation='CIM'
    ).values('description').annotate(
        nb_occurences=Count('id'),
        quantite_totale=Sum('quantite'),
        nb_produits=Count('ligne_reclamation__produit', distinct=True),
        nb_reclamations_concernees=Count('ligne_reclamation__reclamation', distinct=True)
    ).filter(
        description__isnull=False
    ).exclude(
        description=''
    ).order_by('-nb_reclamations_concernees')
    
    # Création du fichier Excel
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'bg_color': '#D9E1F2',
        'border': 1
    })
    
    cell_format = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    number_format = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter'})
    percent_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '0.00%', 'valign': 'vcenter'})
    
    # ============ FEUILLE 1 : Récapitulatif ============
    worksheet_summary = workbook.add_worksheet("Récapitulatif")
    
    # Titre
    worksheet_summary.merge_range('A1:D1', "STATISTIQUES GLOBALES - RÉCURRENCE NC", title_format)
    
    # En-têtes
    headers_summary = ['Indicateur', 'Valeur', '', '']
    for col, header in enumerate(headers_summary[:2]):
        worksheet_summary.write(1, col, header, header_format)
    
    # Données
    summary_data = [
        ['Total réclamations CIM', total_reclamations_cim],
        ['Nombre de descriptions NC distinctes', descriptions.count()],
        ['Total occurrences NC', sum(d['nb_occurences'] for d in descriptions)],
        ['Taux moyen de récurrence', f"{sum(d['nb_reclamations_concernees'] for d in descriptions) / total_reclamations_cim * 100:.2f}%" if total_reclamations_cim > 0 else "0%"],
    ]
    
    row = 2
    for data in summary_data:
        worksheet_summary.write(row, 0, data[0], cell_format)
        worksheet_summary.write(row, 1, data[1], number_format if isinstance(data[1], int) else cell_format)
        row += 1
    
    worksheet_summary.set_column('A:A', 30)
    worksheet_summary.set_column('B:B', 20)
    
    # ============ FEUILLE 2 : Détail des NC ============
    worksheet_details = workbook.add_worksheet("Détail des NC")
    
    # En-têtes
    headers_details = [
        'Description NC',
        'Nb réclamations concernées',
        'Taux de récurrence',
        'Nb occurrences',
        'Quantité totale',
        'Nb produits distincts',
        'Produits concernés (échantillon)'
    ]
    
    for col, header in enumerate(headers_details):
        worksheet_details.write(0, col, header, header_format)
    
    # Données
    row = 1
    for desc in descriptions:
        nb_reclamations = desc['nb_reclamations_concernees']
        taux = (nb_reclamations / total_reclamations_cim) if total_reclamations_cim > 0 else 0
        
        # Récupérer les produits concernés (max 5)
        produits_concernes = Produit.objects.filter(
            lignes_reclamation__non_conformites__description=desc['description'],
            lignes_reclamation__reclamation__imputation='CIM'
        ).distinct().values_list('product_number', flat=True)[:5]
        
        worksheet_details.write(row, 0, desc['description'], cell_format)
        worksheet_details.write(row, 1, nb_reclamations, number_format)
        worksheet_details.write(row, 2, taux, percent_format)
        worksheet_details.write(row, 3, desc['nb_occurences'], number_format)
        worksheet_details.write(row, 4, desc['quantite_totale'] or 0, number_format)
        worksheet_details.write(row, 5, desc['nb_produits'], number_format)
        worksheet_details.write(row, 6, ', '.join(produits_concernes), cell_format)
        row += 1
    
    # Ajuster les colonnes
    worksheet_details.set_column('A:A', 50)
    worksheet_details.set_column('B:B', 22)
    worksheet_details.set_column('C:C', 18)
    worksheet_details.set_column('D:D', 18)
    worksheet_details.set_column('E:E', 15)
    worksheet_details.set_column('F:F', 18)
    worksheet_details.set_column('G:G', 40)
    
    # ============ FEUILLE 3 : Top 20 des NC ============
    worksheet_top = workbook.add_worksheet("Top 20 NC")
    
    headers_top = ['Rang', 'Description NC', 'Nb réclamations', 'Taux de récurrence']
    for col, header in enumerate(headers_top):
        worksheet_top.write(0, col, header, header_format)
    
    top_descriptions = descriptions.order_by('-nb_reclamations_concernees')[:20]
    row = 1
    for idx, desc in enumerate(top_descriptions, 1):
        nb_reclamations = desc['nb_reclamations_concernees']
        taux = (nb_reclamations / total_reclamations_cim) if total_reclamations_cim > 0 else 0
        
        worksheet_top.write(row, 0, idx, number_format)
        worksheet_top.write(row, 1, desc['description'], cell_format)
        worksheet_top.write(row, 2, nb_reclamations, number_format)
        worksheet_top.write(row, 3, taux, percent_format)
        row += 1
    
    worksheet_top.set_column('A:A', 8)
    worksheet_top.set_column('B:B', 60)
    worksheet_top.set_column('C:C', 18)
    worksheet_top.set_column('D:D', 18)
    
    workbook.close()
    output.seek(0)
    
    # Création de la réponse HTTP
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="recurrence_nc_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    return response

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def export_recurrence_produits_excel(request):
    """Exporte les données de récurrence des produits en Excel"""
    
    import io
    import xlsxwriter
    from django.utils import timezone
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # ==================== FORMATS ====================
    
    # Format titre principal
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'font_color': '#1a5276',
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Format sous-titre
    subtitle_format = workbook.add_format({
        'font_size': 11,
        'font_color': '#666666',
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Format en-tête de tableau
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2E86C1',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    # Format en-tête secondaire
    header_secondary_format = workbook.add_format({
        'bold': True,
        'bg_color': '#5DADE2',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    # Format cellule standard
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    # Format cellule centrée
    cell_center_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Format nombre
    number_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    # Format pourcentage
    percent_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%'
    })
    
    # Format pour les taux élevés (rouge)
    high_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#FADBD8',
        'font_color': '#922B21'
    })
    
    # Format pour les taux moyens (orange)
    medium_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#FDEBD0',
        'font_color': '#D35400'
    })
    
    # Format pour les taux faibles (vert)
    low_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#D5F5E3',
        'font_color': '#1E8449'
    })
    
    # Format date
    date_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'font_color': '#666666'
    })
    
    # ==================== COLLECTE DES DONNÉES ====================
    
    produits = Produit.objects.filter(actif=True).order_by('product_number')
    total_reclamations = Reclamation.objects.filter(imputation__in=['CIM', 'ALERTE']).count()
    
    produits_data = []
    
    for produit in produits:
        lignes = LigneReclamation.objects.filter(
            produit=produit, 
            reclamation__imputation__in=['CIM', 'ALERTE']
        ).select_related('reclamation', 'produit')
        
        if not lignes.exists():
            continue
        
        nb_reclamations = lignes.values('reclamation').distinct().count()
        nb_lignes = lignes.count()
        quantite_totale = lignes.aggregate(Sum('quantite'))['quantite__sum'] or 0
        
        # Récupérer les non-conformités associées
        nc_count = NonConformite.objects.filter(
            ligne_reclamation__in=lignes
        ).count()
        
        nc_distinctes = NonConformite.objects.filter(
            ligne_reclamation__in=lignes
        ).values('description').distinct().count()
        
        if total_reclamations > 0:
            taux = (nb_reclamations / total_reclamations) * 100
        else:
            taux = 0
        
        # Déterminer le niveau de criticité
        if taux >= 5:
            criticite = 'CRITIQUE'
        elif taux >= 2:
            criticite = 'SURVEILLANCE'
        else:
            criticite = 'FAIBLE'
        
        produits_data.append({
            'produit': produit,
            'nb_reclamations': nb_reclamations,
            'nb_lignes': nb_lignes,
            'quantite_totale': quantite_totale,
            'nc_count': nc_count,
            'nc_distinctes': nc_distinctes,
            'taux_recurrence': round(taux, 2),
            'criticite': criticite
        })
    
    produits_data.sort(key=lambda x: x['taux_recurrence'], reverse=True)
    
    # ==================== FEUILLE 1 : SYNTHÈSE PRODUITS ====================
    
    worksheet = workbook.add_worksheet('Récurrence Produits')
    
    # Titres
    worksheet.merge_range('A1:K1', 'ANALYSE DE RÉCURRENCE DES DÉFAUTS PAR PRODUIT', title_format)
    worksheet.merge_range('A2:K2', f'Export généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}', subtitle_format)
    worksheet.merge_range('A3:K3', f'Périmètre : Imputations CIM et ALERTE | Total réclamations : {total_reclamations}', subtitle_format)
    
    # En-têtes du tableau
    headers = [
        'Rang', 'N° Produit', 'Désignation',
        'Nb Réclamations', 'Nb Lignes', 'Quantité Totale',
        'Nb NC', 'NC Distinctes', 'Taux Récurrence',
        'Criticité', 'Actions Recommandées'
    ]
    
    row = 4
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, header_format)
    
    # Données
    row = 5
    for idx, data in enumerate(produits_data, 1):
        taux = data['taux_recurrence']
        
        # Choisir le format selon le taux
        if taux >= 5:
            taux_format = high_rate_format
        elif taux >= 2:
            taux_format = medium_rate_format
        else:
            taux_format = low_rate_format
        
        # Actions recommandées selon criticité
        if data['criticite'] == 'CRITIQUE':
            actions = '⚠️ 8D Urgent - Analyse causes racines'
        elif data['criticite'] == 'SURVEILLANCE':
            actions = '📊 Suivi mensuel - Contrôle renforcé'
        else:
            actions = '✅ Surveillance normale'
        
        worksheet.write(row, 0, idx, cell_center_format)
        worksheet.write(row, 1, data['produit'].product_number, cell_format)
        worksheet.write(row, 2, data['produit'].designation or '-', cell_format)
        worksheet.write(row, 3, data['nb_reclamations'], number_format)
        worksheet.write(row, 4, data['nb_lignes'], number_format)
        worksheet.write(row, 5, data['quantite_totale'], number_format)
        worksheet.write(row, 6, data['nc_count'], number_format)
        worksheet.write(row, 7, data['nc_distinctes'], number_format)
        worksheet.write(row, 8, taux / 100, taux_format)
        
        # Criticité avec couleur
        if data['criticite'] == 'CRITIQUE':
            worksheet.write(row, 9, data['criticite'], high_rate_format)
        elif data['criticite'] == 'SURVEILLANCE':
            worksheet.write(row, 9, data['criticite'], medium_rate_format)
        else:
            worksheet.write(row, 9, data['criticite'], low_rate_format)
        
        worksheet.write(row, 10, actions, cell_format)
        row += 1
    
    # Ajuster les colonnes
    column_widths = [6, 15, 30, 14, 12, 14, 10, 12, 14, 14, 35]
    for col, width in enumerate(column_widths):
        worksheet.set_column(col, col, width)
    
    # Ajouter un filtre automatique
    worksheet.autofilter(4, 0, row - 1, len(headers) - 1)
    
    # Figer les volets
    worksheet.freeze_panes(5, 0)
    
    # ==================== FEUILLE 2 : TOP 10 PRODUITS ====================
    
    worksheet_top = workbook.add_worksheet('Top 10 Produits')
    
    worksheet_top.merge_range('A1:E1', 'TOP 10 PRODUITS - TAUX DE RÉCURRENCE', title_format)
    worksheet_top.merge_range('A2:E2', f'Export généré le {timezone.now().strftime("%d/%m/%Y")}', subtitle_format)
    
    headers_top = ['Rang', 'Produit', 'Nb Réclamations', 'Taux Récurrence', 'Recommandation']
    
    row = 3
    for col, header in enumerate(headers_top):
        worksheet_top.write(row, col, header, header_secondary_format)
    
    row = 4
    for idx, data in enumerate(produits_data[:10], 1):
        worksheet_top.write(row, 0, idx, cell_center_format)
        worksheet_top.write(row, 1, f"{data['produit'].product_number} - {data['produit'].designation[:30]}", cell_format)
        worksheet_top.write(row, 2, data['nb_reclamations'], number_format)
        worksheet_top.write(row, 3, data['taux_recurrence'] / 100, percent_format)
        worksheet_top.write(row, 4, f"Plan d'action {data['criticite'].lower()}", cell_format)
        row += 1
    
    worksheet_top.set_column(0, 0, 6)
    worksheet_top.set_column(1, 1, 40)
    worksheet_top.set_column(2, 2, 15)
    worksheet_top.set_column(3, 3, 15)
    worksheet_top.set_column(4, 4, 25)
    
    # ==================== FEUILLE 3 : DÉTAIL PAR PRODUIT ====================
    
    worksheet_detail = workbook.add_worksheet('Détail Non-Conformités')
    
    worksheet_detail.merge_range('A1:F1', 'DÉTAIL DES NON-CONFORMITÉS PAR PRODUIT', title_format)
    
    headers_detail = ['Produit', 'Description NC', 'Nb Occurrences', 'Quantité Totale', 'Dernière Occurrence', 'Statut']
    
    row = 2
    for col, header in enumerate(headers_detail):
        worksheet_detail.write(row, col, header, header_secondary_format)
    
    row = 3
    for data in produits_data[:30]:  # Limiter aux 30 premiers pour la lisibilité
        produit = data['produit']
        
        # Récupérer les NC pour ce produit
        ncs = NonConformite.objects.filter(
            ligne_reclamation__produit=produit,
            ligne_reclamation__reclamation__imputation__in=['CIM', 'ALERTE']
        ).values('description').annotate(
            nb_occurences=Count('id'),
            quantite_totale=Sum('quantite'),
            derniere_date=Max('ligne_reclamation__reclamation__date_reclamation')
        ).order_by('-nb_occurences')[:5]
        
        for nc in ncs:
            worksheet_detail.write(row, 0, produit.product_number, cell_format)
            worksheet_detail.write(row, 1, nc['description'][:50], cell_format)
            worksheet_detail.write(row, 2, nc['nb_occurences'], number_format)
            worksheet_detail.write(row, 3, nc['quantite_totale'] or 0, number_format)
            
            if nc['derniere_date']:
                worksheet_detail.write(row, 4, nc['derniere_date'].strftime('%d/%m/%Y'), date_format)
            else:
                worksheet_detail.write(row, 4, '-', cell_center_format)
            
            if nc['nb_occurences'] >= 5:
                worksheet_detail.write(row, 5, '⚠️ Critique', high_rate_format)
            else:
                worksheet_detail.write(row, 5, 'À surveiller', medium_rate_format)
            
            row += 1
    
    worksheet_detail.set_column(0, 0, 15)
    worksheet_detail.set_column(1, 1, 45)
    worksheet_detail.set_column(2, 2, 12)
    worksheet_detail.set_column(3, 3, 14)
    worksheet_detail.set_column(4, 4, 14)
    worksheet_detail.set_column(5, 5, 12)
    
    # ==================== FEUILLE 4 : STATISTIQUES GLOBALES ====================
    
    worksheet_stats = workbook.add_worksheet('Statistiques')
    
    worksheet_stats.merge_range('A1:C1', 'STATISTIQUES GLOBALES', title_format)
    
    stats_label_format = workbook.add_format({
        'bold': True,
        'bg_color': '#EBF5FB',
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    stats_value_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    row = 3
    
    # Calculer les statistiques
    total_produits_impactes = len(produits_data)
    total_produits = Produit.objects.filter(actif=True).count()
    pourcentage_impactes = (total_produits_impactes / total_produits * 100) if total_produits > 0 else 0
    
    produits_critiques = sum(1 for d in produits_data if d['criticite'] == 'CRITIQUE')
    produits_surveillance = sum(1 for d in produits_data if d['criticite'] == 'SURVEILLANCE')
    
    stats = [
        ('Total réclamations (CIM + ALERTE)', total_reclamations),
        ('Total produits actifs', total_produits),
        ('Produits impactés', total_produits_impactes),
        ('Pourcentage produits impactés', f"{round(pourcentage_impactes, 1)}%"),
        ('', ''),
        ('Produits CRITIQUES (taux ≥ 5%)', produits_critiques),
        ('Produits en SURVEILLANCE (taux 2-5%)', produits_surveillance),
        ('Produits FAIBLES (taux < 2%)', total_produits_impactes - produits_critiques - produits_surveillance),
    ]
    
    for label, value in stats:
        worksheet_stats.write(row, 0, label, stats_label_format)
        worksheet_stats.write(row, 1, value, stats_value_format)
        row += 1
    
    worksheet_stats.set_column(0, 0, 35)
    worksheet_stats.set_column(1, 1, 15)
    
    # ==================== FINALISATION ====================
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="recurrence_produits_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    
    return response

def calculer_duree_moyenne_sql():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT AVG(
                julianday(date_cloture) - julianday(date_reclamation)
            ) 
            FROM reclamations_reclamation 
            WHERE cloture = 1 
                AND date_cloture IS NOT NULL 
                AND date_reclamation IS NOT NULL
        """)
        result = cursor.fetchone()
        return round(result[0], 1) if result and result[0] else 0

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def ppm_detail_client(request, client_id):
    """Détail PPM pour un client spécifique"""
    annee = request.GET.get('annee', datetime.now().year)
    ppm_calculator = PPMCalculator(annee=annee)
    
    client = get_object_or_404(Client, id=client_id)
    ppm_data = ppm_calculator.get_ppm_client(client)
    evolution = ppm_calculator.get_tendance_ppm(client_id)
    
    context = {
        'client': client,
        'ppm_data': ppm_data,
        'evolution': evolution,
        'statut': ppm_calculator.get_statut_ppm(ppm_data['ppm'])
    }
    
    return render(request, 'reclamations/kpi/ppm_detail.html', context)

def mini_kpi_stats(request):
    """Calcule les KPI avec variations pour le dashboard"""
    dashboard_stats = DashboardStats()
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_month = today - timedelta(days=30)
    month_before = today - timedelta(days=60)

    # ========== STATISTIQUES GLOBALES ==========
    total_reclamations = Reclamation.objects.count()
    ouvertes = Reclamation.objects.filter(cloture=False).count()
    cloturees = Reclamation.objects.filter(cloture=True).count()
    taux_cloture = (cloturees / total_reclamations * 100) if total_reclamations > 0 else 0
    reclamations_sans_8d = Reclamation.objects.filter(cloture=False, huitd_non_applicable=False).exclude(huitd__isnull=False).count()
    print(f"Reclamations sans 8D : {reclamations_sans_8d}")
    # Réclamations ouvertes AVEC 8D en cours
    reclamations_avec_8d = Reclamation.objects.filter(cloture=False, huitd__isnull=False, huitd_non_applicable=False).exclude(huitd__etat='CLOTURE').count()
    SECURISATION_EN_COURS = Reclamation.objects.filter(cloture=False, etat_4d='EN_COURS').count()
    # Taux de réactivité (clôturées dans les 30 jours)
    reactivite_uap_data = dashboard_stats.get_taux_reactivite_par_uap()
    taux_reactivite = 0
    annee_courante = timezone.now().year
    
    if reactivite_uap_data and annee_courante in reactivite_uap_data:
        annees_data = reactivite_uap_data.get(annee_courante, {})
        data_mensuelle = annees_data.get('data', {})
        
        # Récupérer tous les taux
        tous_les_taux = []
        for mois, uap_data in data_mensuelle.items():
            for uap, taux in uap_data.items():
                if taux > 0:  # Ne compter que les UAP avec des données
                    tous_les_taux.append(taux)
        
        # Calculer la moyenne
        if tous_les_taux:
            taux_reactivite = sum(tous_les_taux) / len(tous_les_taux)

    actions_encours = Action8D.objects.select_related(
            'huitd__reclamation__client',
        ).filter(
            statut__in=['PLANIFIE', 'EN_COURS']
        ).count()
    # Délai moyen de clôture
    reclamations_closes = Reclamation.objects.filter(
        cloture=True,
        date_cloture__isnull=False,
        date_reclamation__isnull=False
    )
    total_jours = 0
    count = 0
    for rec in reclamations_closes:
        delta = rec.date_cloture - rec.date_reclamation
        total_jours += delta.days
        count += 1
    delai_moyen = round(total_jours / count, 1) if count > 0 else 0
    
    
    # Taux de récurrence
    dashboard_stats = DashboardStats()
    recurrence_data = dashboard_stats.get_taux_recurrence_globale()
    taux_recurrence = recurrence_data.get('taux', 0)
    
    # ========== VARIATIONS ==========
    
    # Variation Total Réclamations (vs hier)
    total_today = Reclamation.objects.filter(date_creation__date=today).count()
    total_yesterday = Reclamation.objects.filter(date_creation__date=yesterday).count()
    variation_total = ((total_today - total_yesterday) / total_yesterday * 100) if total_yesterday > 0 else 0
    
    # Variation Ouvertes (vs hier)
    ouvertes_today = Reclamation.objects.filter(cloture=False, date_creation__date=today).count()
    ouvertes_yesterday = Reclamation.objects.filter(cloture=False, date_creation__date=yesterday).count()
    variation_ouvertes = ((ouvertes_today - ouvertes_yesterday) / ouvertes_yesterday * 100) if ouvertes_yesterday > 0 else 0
    
    # Variation Taux Réactivité (vs mois dernier)
    reactives_last_month = Reclamation.objects.filter(
        cloture=True,
        date_cloture__gte=month_before,
        date_cloture__lt=last_month
    ).count()
    total_cloturees_last_month = Reclamation.objects.filter(
        cloture=True,
        date_cloture__gte=month_before,
        date_cloture__lt=last_month
    ).count()
    taux_reactivite_last = (reactives_last_month / total_cloturees_last_month * 100) if total_cloturees_last_month > 0 else 0
    variation_reactivite = taux_reactivite - taux_reactivite_last
    
    # Variation Délai Moyen (évolution en pourcentage)
    delai_precedent = 15  # Valeur par défaut, à ajuster selon historique
    variation_delai = ((delai_moyen - delai_precedent) / delai_precedent * 100) if delai_precedent > 0 else 0
    
   
    # Variation Taux Récurrence (vs mois dernier)
    taux_recurrence_precedent = 15  # Valeur par défaut, à ajuster
    variation_recurrence = taux_recurrence - taux_recurrence_precedent
    
    stats = {
        'total_reclamations': total_reclamations,
        'ouvertes': ouvertes,
        'taux_cloture': round(taux_cloture, 1),
        'taux_reactivite': round(taux_reactivite, 1),
        'delai_moyen': delai_moyen,
        'taux_recurrence': round(taux_recurrence, 1),
        'actions_encours': actions_encours,
        'reclamations_sans_8d': reclamations_sans_8d,
        'reclamations_avec_8d': reclamations_avec_8d,
        'securisation_en_cours': SECURISATION_EN_COURS
    }
    
    variation = {
        'total_reclamations': round(variation_total, 1),
        'ouvertes': round(variation_ouvertes, 1),
        'taux_reactivite': round(variation_reactivite, 1),
        'delai_moyen': round(variation_delai, 1),
        'taux_recurrence': round(variation_recurrence, 1),
    }
    
    return {
        'stats': stats,
        'variation': variation,
        'current_year': timezone.now().year
    }

@csrf_exempt
def api_dashboard_data(request):
    """API pour récupérer les données du dashboard en temps réel"""
    # Récupérer les KPI
    kpi_data = mini_kpi_stats(request)
    stats = kpi_data['stats']
    variations = kpi_data['variation']
    
    return JsonResponse({
        'total_reclamations': stats.get('total_reclamations', 0),
        'ouvertes': stats.get('ouvertes', 0),
        'securisation_en_cours': stats.get('securisation_en_cours', 0),
        'reclamations_sans_8d': stats.get('reclamations_sans_8d', 0),
        'reclamations_avec_8d': stats.get('reclamations_avec_8d', 0),
        'actions_encours': stats.get('actions_encours', 0),
        'taux_cloture': stats.get('taux_cloture', 0),
        'taux_reactivite': stats.get('taux_reactivite', 0),
        'delai_moyen': stats.get('delai_moyen', 0),
        'cout_nqc_total': stats.get('cout_nqc_total', 0),
        'taux_recurrence': stats.get('taux_recurrence', 0),
        'variations': variations,
        'timestamp': timezone.now().isoformat()
    })
    
def big_screen_dashboard(request):
    """Dashboard grand écran pour le responsable"""
    
    from reclamations.models import Reclamation, HuitD
    
    # Récupérer les KPI
    kpi_data = mini_kpi_stats(request)
    
    # Réclamations ouvertes SANS 8D
    reclamations_sans_8d = Reclamation.objects.filter(
        cloture=False,
        huitd_non_applicable=False
    ).exclude(
        huitd__isnull=False
    ).select_related('client').order_by('-date_reclamation')
    
    # Réclamations ouvertes AVEC 8D en cours
    reclamations_avec_8d = Reclamation.objects.filter(
        cloture=False,
        huitd__isnull=False,
        huitd_non_applicable=False
    ).exclude(
        huitd__etat='CLOTURE'
    ).select_related('client', 'huitd').order_by('-date_reclamation')
    
    context = {
        'kpi_stats': kpi_data['stats'],
        'kpi_variation': kpi_data['variation'],
        'current_year': kpi_data['current_year'],
        'reclamations_sans_8d': reclamations_sans_8d.count(),
        'reclamations_avec_8d': reclamations_avec_8d.count(),
        'now': timezone.now()
    }
    return render(request, 'reclamations/dashboard/big_screen_dashboard.html', context)
# ================ GESTION DES RECLAMATIONS ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_reclamations(request):
    """Liste des réclamations avec pagination et recherche"""
    
    # Récupérer tous les filtres
    search = request.GET.get('search', '')
    statut = request.GET.get('statut', '')
    client_id = request.GET.get('client', '')
    mois = request.GET.get('mois', '')
    annee = request.GET.get('annee', '')
    imputation = request.GET.get('imputation', '')
    
    # Requête de base avec sélection des relations et des produits
    reclamations = Reclamation.objects.select_related(
        'client', 'programme', 'site_client', 'createur'
    ).prefetch_related(
        Prefetch('lignes', queryset=LigneReclamation.objects.select_related(
            'produit', 'site', 'site__uap', 'uap_concernee'
        ).prefetch_related('non_conformites'))
    ).order_by('-date_reclamation')
    
    # Filtre par recherche (numéro réclamation, client, programme ou produit)
    if search:
        reclamations = reclamations.filter(
            Q(numero_reclamation__icontains=search) |
            Q(client__nom__icontains=search) |
            Q(programme__nom__icontains=search) |
            Q(lignes__produit__product_number__icontains=search) |
            Q(lignes__non_conformites__description__icontains=search)
        ).distinct()
    
    # Filtre par statut
    if statut:
        if statut == 'ouvert':
            reclamations = reclamations.filter(cloture=False)
        elif statut == 'cloture':
            reclamations = reclamations.filter(cloture=True)
    
    # Filtre par client
    if client_id:
        reclamations = reclamations.filter(client_id=client_id)
    
    # Filtre par mois et année
    if mois and annee:
        try:
            mois_int = int(mois)
            annee_int = int(annee)
            reclamations = reclamations.filter(
                date_reclamation__month=mois_int,
                date_reclamation__year=annee_int
            )
        except ValueError:
            pass
    elif annee:  # Si seulement l'année est spécifiée
        try:
            annee_int = int(annee)
            reclamations = reclamations.filter(date_reclamation__year=annee_int)
        except ValueError:
            pass
    elif mois:  # Si seulement le mois est spécifié (toutes les années)
        try:
            mois_int = int(mois)
            reclamations = reclamations.filter(date_reclamation__month=mois_int)
        except ValueError:
            pass
    
    # Filtre par imputation
    if imputation:
        reclamations = reclamations.filter(imputation=imputation)
    
    # Pagination (20 par page)
    paginator = Paginator(reclamations, 20)
    page = request.GET.get('page', 1)
    
    try:
        reclamations_page = paginator.page(page)
    except PageNotAnInteger:
        reclamations_page = paginator.page(1)
    except EmptyPage:
        reclamations_page = paginator.page(paginator.num_pages)
    
    # Récupérer les données pour les filtres
    clients = Client.objects.filter(actif=True).order_by('nom')
    imputation_choices = Reclamation.IMPUTATION_CHOICES
    
    # Générer la liste des mois pour le filtre
    mois_choices = [
        (1, 'Janvier'),
        (2, 'Février'),
        (3, 'Mars'),
        (4, 'Avril'),
        (5, 'Mai'),
        (6, 'Juin'),
        (7, 'Juillet'),
        (8, 'Août'),
        (9, 'Septembre'),
        (10, 'Octobre'),
        (11, 'Novembre'),
        (12, 'Décembre'),
    ]
    
    # Générer la liste des années disponibles (années où il y a des réclamations)
    annees_disponibles = Reclamation.objects.dates('date_reclamation', 'year')
    annees_choices = [(annee.year, annee.year) for annee in annees_disponibles]
    
    # Si aucune année n'est trouvée, mettre l'année courante
    if not annees_choices:
        annee_courante = datetime.now().year
        annees_choices = [(annee_courante, annee_courante)]
    
    context = {
        'reclamations': reclamations_page,
        'clients': clients,
        'mois_choices': mois_choices,
        'annees_choices': annees_choices,
        'imputation_choices': imputation_choices,
        'search': search,
        'statut_filter': statut,
        'client_filter': client_id,
        'mois_filter': mois,
        'annee_filter': annee,
        'imputation_filter': imputation,
        'total_reclamations': paginator.count,
        'page_obj': reclamations_page,
    }
    
    return render(request, 'reclamations/liste.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_reclamation(request):
    """Créer une nouvelle réclamation avec gestion des multiples NC par ligne"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            client_id = request.POST.get('client')
            site_client_id = request.POST.get('site_client')
            programme_id = request.POST.get('programme')
            numero_reclamation = request.POST.get('numero_reclamation', '').strip()
            date_reclamation = request.POST.get('date_reclamation')
            imputation = request.POST.get('imputation', 'CIM')
            type_nc = request.POST.get('type_nc', 'TECHNIQUE')
            besoin_4dp = request.POST.get('besoin_4dp') == 'on'
            # Validation des champs obligatoires
            erreurs = []
            
            if not numero_reclamation:
                erreurs.append("Le numéro de réclamation est requis.")
            
            if not client_id:
                erreurs.append("Le client est requis.")
            
            # Vérifier si le numéro de réclamation existe déjà
            if numero_reclamation and Reclamation.objects.filter(numero_reclamation=numero_reclamation).exists():
                erreurs.append(f"Le numéro de réclamation '{numero_reclamation}' existe déjà.")
            
            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
                return render(request, 'reclamations/creer.html', {
                    'clients': Client.objects.filter(actif=True).order_by('nom'),
                    'produits': Produit.objects.filter(actif=True).order_by('product_number'),
                    'sites_usine': Site.objects.all().select_related('uap').order_by('nom'),
                    'type_nc_choices': Reclamation.TYPE_NC_CHOICES,
                    'imputation_choices': Reclamation.IMPUTATION_CHOICES,
                    'etat_choices': Reclamation.ETAT_CHOICES,
                    'today': timezone.now().date(),
                    'anciennes_valeurs': request.POST
                })
            
            # Créer la réclamation principale (sans site usine, car il est dans les lignes)
            reclamation = Reclamation.objects.create(
                numero_reclamation=numero_reclamation,
                date_reclamation=date_reclamation or timezone.now().date(),
                client_id=client_id,
                site_client_id=site_client_id if site_client_id else None,
                programme_id=programme_id if programme_id else None,
                imputation=imputation,
                type_nc=type_nc,
                besoin_4dp=besoin_4dp,
                etat_4d='EN_COURS',
                etat_8d='EN_COURS',
                cloture=False,
                createur=request.user
            )
            
            # Traiter les lignes de réclamation
            produits = request.POST.getlist('produit[]')
            quantites = request.POST.getlist('quantite[]')
            sites = request.POST.getlist('site[]')  # Site usine pour chaque ligne
            commentaires = request.POST.getlist('commentaire[]')
            
            # Récupérer les données des NC
            nc_descriptions = request.POST.getlist('nc_description[]')
            nc_quantites = request.POST.getlist('nc_quantite[]')
            nc_ligne_refs = request.POST.getlist('nc_ligne_ref[]')
            
            # Regrouper les NC par ligne
            nc_par_ligne = {}
            for idx in range(len(nc_descriptions)):
                ligne_ref = nc_ligne_refs[idx] if idx < len(nc_ligne_refs) else str(idx)
                if ligne_ref not in nc_par_ligne:
                    nc_par_ligne[ligne_ref] = []
                nc_par_ligne[ligne_ref].append({
                    'description': nc_descriptions[idx],
                    'quantite': int(nc_quantites[idx]) if idx < len(nc_quantites) and nc_quantites[idx] else 1
                })
            
            lignes_crees = 0
            
            for i in range(len(produits)):
                if not produits[i]:
                    continue
                
                # Quantité totale
                quantite_totale = int(quantites[i]) if quantites[i] else 1
                site_id = sites[i] if i < len(sites) and sites[i] else None
                commentaire = commentaires[i] if i < len(commentaires) else ''
                
                # Créer la ligne de réclamation (l'UAP sera automatiquement définie par le save)
                ligne = LigneReclamation.objects.create(
                    reclamation=reclamation,
                    produit_id=produits[i],
                    quantite=quantite_totale,
                    site_id=site_id,
                    commentaire=commentaire
                )
                
                # L'UAP est automatiquement définie par la méthode save() de LigneReclamation
                # à partir du site sélectionné
                
                # Ajouter les non-conformités pour cette ligne
                ligne_ref = str(i)  # Référence de la ligne
                ncs_ajoutees = 0
                
                for nc_data in nc_par_ligne.get(ligne_ref, []):
                    if nc_data['description'].strip():
                        NonConformite.objects.create(
                            ligne_reclamation=ligne,
                            description=nc_data['description'],
                            quantite=nc_data['quantite']
                        )
                        ncs_ajoutees += 1
                
                # Si aucune NC n'a été ajoutée pour cette ligne, la supprimer
                if ncs_ajoutees == 0:
                    ligne.delete()
                else:
                    lignes_crees += 1
            
            if lignes_crees == 0:
                # Si aucune ligne n'a été créée, supprimer la réclamation
                reclamation.delete()
                messages.error(request, "Vous devez ajouter au moins un produit avec une non-conformité valide.")
                return redirect('reclamations:creer')
            
            messages.success(
                request, 
                f"Réclamation {reclamation.numero_reclamation} créée avec succès avec {lignes_crees} produit(s) !"
            )
            return redirect('reclamations:detail_reclamation', pk=reclamation.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur création réclamation: {str(e)}", exc_info=True)
            
            return render(request, 'reclamations/creer.html', {
                'clients': Client.objects.filter(actif=True).order_by('nom'),
                'produits': Produit.objects.filter(actif=True).order_by('product_number'),
                'sites_usine': Site.objects.all().select_related('uap').order_by('nom'),
                'type_nc_choices': Reclamation.TYPE_NC_CHOICES,
                'imputation_choices': Reclamation.IMPUTATION_CHOICES,
                'etat_choices': Reclamation.ETAT_CHOICES,
                'today': timezone.now().date(),
                'anciennes_valeurs': request.POST
            })
    
    # GET : afficher le formulaire
    context = {
        'clients': Client.objects.filter(actif=True).order_by('nom'),
        'produits': Produit.objects.filter(actif=True).order_by('product_number'),
        'sites_usine': Site.objects.all().select_related('uap').order_by('nom'),
        'type_nc_choices': Reclamation.TYPE_NC_CHOICES,
        'imputation_choices': Reclamation.IMPUTATION_CHOICES,
        'etat_choices': Reclamation.ETAT_CHOICES,
        'today': timezone.now().date(),
    }
    return render(request, 'reclamations/creer.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def rechercher_descriptions_nc(request):
    """Recherche les descriptions de NC existantes pour autocomplétion"""
    term = request.GET.get('term', '')
    
    if len(term) < 2:
        return JsonResponse([], safe=False)
    
    # Chercher les descriptions similaires
    descriptions = NonConformite.objects.filter(
        description__icontains=term
    ).values('description').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    results = [{'value': d['description'], 'count': d['count']} for d in descriptions]
    
    return JsonResponse(results, safe=False)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def programmes_par_client(request):
    """Endpoint AJAX pour récupérer les programmes d'un client (ManyToMany)"""
    client_id = request.GET.get('client_id')
    
    print(f"=== PROGRAMMES PAR CLIENT ===")
    print(f"Client ID reçu: {client_id}")
    
    if not client_id:
        return JsonResponse([], safe=False)
    
    try:
        # Pour ManyToMany, on utilise clients__id (deux underscores)
        programmes = Programme.objects.filter(
            clients__id=client_id,  # ← clients est le champ ManyToMany
            actif=True
        ).values('id', 'nom').order_by('nom').distinct()
        
        programmes_list = list(programmes)
        print(f"Programmes trouvés: {programmes_list}")
        
        return JsonResponse(programmes_list, safe=False)
        
    except Exception as e:
        print(f"Erreur chargement programmes: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def sites_client_par_client(request):
    """Endpoint AJAX pour récupérer les sites client d'un client"""
    client_id = request.GET.get('client_id')
    if client_id:
        sites = SiteClient.objects.filter(
            client_id=client_id, 
            actif=True
        ).values('id', 'nom', 'ville').order_by('nom')
        return JsonResponse(list(sites), safe=False)
    return JsonResponse([], safe=False)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'production_manager'])
def detail_reclamation(request, pk):
    """Voir le détail d'une réclamation avec analyse NC intégrée"""
    reclamation = get_object_or_404(
        Reclamation.objects.prefetch_related(
            'lignes__produit',
            'lignes__site',
            'lignes__uap_concernee',
            'huitd__actions',  # ← AJOUT : précharger les actions 8D
            'huitd__participants',  # ← AJOUT : précharger les participants
            'huitd__causes_ishikawa',  # si vous avez ce modèle
            'huitd__causes_5p',  # si vous avez ce modèle
        ).select_related(
            'client',
            'site_client',
            'programme',
            'createur',
            'huitd',  # ← AJOUT : charger le 8D associé
        ),
        pk=pk
    )
    return render(request, 'reclamations/detail.html', {'reclamation': reclamation})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_etats(request, pk):
    """Mettre à jour les états d'une réclamation"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    if request.method == 'POST':
        try:
            # Mise à jour des états
            reclamation.etat_4d = request.POST.get('etat_4d', reclamation.etat_4d)
            reclamation.etat_8d = request.POST.get('etat_8d', reclamation.etat_8d)
            reclamation.cloture = request.POST.get('cloture') == 'on'
            
            # Numéros 4D et 8D (liens externes)
            reclamation.numero_4d = request.POST.get('numero_4d', '')
            reclamation.numero_8d = request.POST.get('numero_8d', '')
            
            # Dates de clôture
            date_cloture_4d = request.POST.get('date_cloture_4d')
            if date_cloture_4d:
                reclamation.date_cloture_4d = date_cloture_4d
                
            date_cloture_8d = request.POST.get('date_cloture_8d')
            if date_cloture_8d:
                reclamation.date_cloture_8d = date_cloture_8d
            
            # Autres champs modifiables
            reclamation.decision = request.POST.get('decision', reclamation.decision)
            nqc = request.POST.get('nqc')
            if nqc:
                reclamation.nqc = nqc
            
            # Sauvegarde (les dates de clôture sont gérées automatiquement dans le modèle)
            reclamation.save()
            
            messages.success(request, "États mis à jour avec succès!")
            return redirect('reclamations:detail_reclamation', pk=reclamation.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")
    
    # GET : afficher le formulaire
    context = {
        'reclamation': reclamation,
        'etat_choices': Reclamation.ETAT_CHOICES,
    }
    return render(request, 'reclamations/modifier_etats.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])

@login_required
def modifier_reclamation(request, pk):
    """Modifier une réclamation complète avec gestion des multiples NC - Version optimisée"""
    
    # Utiliser only() pour charger uniquement les champs nécessaires
    reclamation = get_object_or_404(
        Reclamation.objects.only(
            'id', 'numero_reclamation', 'date_reclamation', 'client_id', 
            'site_client_id', 'programme_id', 'imputation', 'type_nc',
            'numero_4d', 'numero_8d', 'etat_4d', 'etat_8d', 'evidence', 
            'me', 'cloture', 'decision', 'nqc','besoin_4dp'
        ),
        pk=pk
    )
    
    # Précharger les lignes avec select_related et only (optimisé)
    lignes = LigneReclamation.objects.filter(reclamation=reclamation).select_related(
        'produit', 'site', 'uap_concernee'
    ).only(
        'id', 'produit_id', 'quantite', 'site_id', 'uap_concernee_id', 'commentaire'
    ).prefetch_related(
        'non_conformites'
    )
    
    # Mettre en cache les données qui ne changent pas souvent (10 minutes)
    cache_key_clients = 'clients_actifs'
    cache_key_produits = 'produits_actifs'
    cache_key_sites_usine = 'sites_usine'
    
    clients = cache.get(cache_key_clients)
    if clients is None:
        clients = list(Client.objects.filter(actif=True).only('id', 'nom').order_by('nom'))
        cache.set(cache_key_clients, clients, 600)
    
    produits = cache.get(cache_key_produits)
    if produits is None:
        # Limiter à 500 produits et paginer
        produits = list(Produit.objects.filter(actif=True).only('id', 'product_number', 'designation').order_by('product_number')[:500])
        cache.set(cache_key_produits, produits, 600)
    
    sites_usine = cache.get(cache_key_sites_usine)
    if sites_usine is None:
        sites_usine = list(Site.objects.all().select_related('uap').only('id', 'nom', 'uap__id', 'uap__nom').order_by('nom'))
        cache.set(cache_key_sites_usine, sites_usine, 600)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Mettre à jour les champs de la réclamation (uniquement les champs modifiés)
                reclamation.numero_reclamation = request.POST.get('numero_reclamation')
                
                date_raw = request.POST.get('date_reclamation', '').strip()
                if date_raw:
                    try:
                        reclamation.date_reclamation = datetime.strptime(date_raw, '%Y-%m-%d').date()
                    except ValueError:
                        reclamation.date_reclamation = timezone.now().date()
                
                # Mettre à jour uniquement si les valeurs ont changé
                reclamation.client_id = request.POST.get('client')
                reclamation.site_client_id = request.POST.get('site_client') or None
                reclamation.programme_id = request.POST.get('programme') or None
                reclamation.imputation = request.POST.get('imputation')
                reclamation.type_nc = request.POST.get('type_nc')
                reclamation.numero_4d = request.POST.get('numero_4d', '')
                reclamation.numero_8d = request.POST.get('numero_8d', '')
                reclamation.etat_4d = request.POST.get('etat_4d')
                reclamation.etat_8d = request.POST.get('etat_8d')
                reclamation.evidence = request.POST.get('evidence', '')
                reclamation.me = request.POST.get('me') == 'on'
                reclamation.cloture = request.POST.get('cloture') == 'on'
                reclamation.decision = request.POST.get('decision', '')
                reclamation.besoin_4dp = request.POST.get('besoin_4dp') == 'on'
                nqc_value = request.POST.get('nqc', '0').strip()
                if nqc_value:
                    nqc_value = nqc_value.replace(',', '.')
                    try:
                        reclamation.nqc = Decimal(nqc_value)
                    except (InvalidOperation, ValueError):
                        reclamation.nqc = Decimal('0')
                else:
                    reclamation.nqc = Decimal('0')
                
                # Utiliser update_fields pour sauvegarder uniquement les champs modifiés
                reclamation.save(update_fields=[
                    'numero_reclamation', 'date_reclamation', 'client_id', 'site_client_id',
                    'programme_id', 'imputation', 'type_nc', 'numero_4d', 'numero_8d',
                    'etat_4d', 'etat_8d', 'evidence', 'me', 'cloture', 'decision', 'nqc','besoin_4dp'
                ])
                
                # ========== TRAITEMENT DES LIGNES OPTIMISÉ ==========
                produits_list = request.POST.getlist('produit[]')
                if not produits_list:
                    messages.error(request, "Au moins une ligne de produit est requise")
                    return redirect('reclamations:modifier_reclamation', pk=pk)
                
                # Récupérer les IDs des lignes existantes
                lignes_ids_existants = set()
                lignes_ids_POST = request.POST.getlist('ligne_id[]')
                
                # Compter le nombre de lignes valides
                nb_lignes = 0
                for i, produit_id in enumerate(produits_list):
                    if produit_id:
                        nb_lignes += 1
                
                if nb_lignes == 0:
                    messages.error(request, "Au moins une ligne de produit est requise")
                    return redirect('reclamations:modifier_reclamation', pk=pk)
                
                # Utiliser bulk_create et bulk_update pour les performances
                lignes_a_conserver = []
                
                for i in range(len(produits_list)):
                    produit_id = produits_list[i]
                    if not produit_id:
                        continue
                    
                    quantite_totale = int(request.POST.getlist('quantite[]')[i]) if i < len(request.POST.getlist('quantite[]')) else 1
                    ligne_id_str = lignes_ids_POST[i] if i < len(lignes_ids_POST) else ''
                    site_id = request.POST.getlist('site[]')[i] if i < len(request.POST.getlist('site[]')) else None
                    commentaire = request.POST.getlist('commentaire[]')[i] if i < len(request.POST.getlist('commentaire[]')) else ''
                    
                    # Gérer la ligne
                    if ligne_id_str and ligne_id_str.isdigit():
                        try:
                            ligne = LigneReclamation.objects.get(id=int(ligne_id_str), reclamation=reclamation)
                            ligne.produit_id = int(produit_id)
                            ligne.quantite = quantite_totale
                            ligne.site_id = int(site_id) if site_id and site_id.isdigit() else None
                            ligne.commentaire = commentaire
                            ligne.save(update_fields=['produit_id', 'quantite', 'site_id', 'commentaire'])
                            lignes_a_conserver.append(ligne.id)
                            lignes_ids_existants.add(ligne.id)
                        except LigneReclamation.DoesNotExist:
                            ligne = LigneReclamation.objects.create(
                                reclamation=reclamation,
                                produit_id=int(produit_id),
                                quantite=quantite_totale,
                                site_id=int(site_id) if site_id and site_id.isdigit() else None,
                                commentaire=commentaire
                            )
                            lignes_a_conserver.append(ligne.id)
                    else:
                        ligne = LigneReclamation.objects.create(
                            reclamation=reclamation,
                            produit_id=int(produit_id),
                            quantite=quantite_totale,
                            site_id=int(site_id) if site_id and site_id.isdigit() else None,
                            commentaire=commentaire
                        )
                        lignes_a_conserver.append(ligne.id)
                
                # Supprimer les lignes orphelines en une seule requête
                reclamation.lignes.exclude(id__in=lignes_a_conserver).delete()
                
                messages.success(request, f"Réclamation {reclamation.numero_reclamation} modifiée avec succès!")
                return redirect('reclamations:detail_reclamation', pk=reclamation.id)
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # GET: afficher le formulaire - avec chargement optimisé et paginé
    sites_client = []
    programmes = []
    
    if reclamation.client:
        sites_client = SiteClient.objects.filter(client=reclamation.client, actif=True).only('id', 'nom').order_by('nom')
        programmes = Programme.objects.filter(clients=reclamation.client, actif=True).only('id', 'nom').order_by('nom')
    
    uaps = UAP.objects.all().only('id', 'nom').order_by('nom')
    
    context = {
        'reclamation': reclamation,
        'lignes': lignes,  # Utiliser la queryset préchargée
        'clients': clients,
        'sites_usine': sites_usine,
        'sites_client': sites_client,
        'programmes': programmes,
        'produits': produits,
        'uaps': uaps,
        'type_nc_choices': Reclamation.TYPE_NC_CHOICES,
        'imputation_choices': Reclamation.IMPUTATION_CHOICES,
        'etat_choices': Reclamation.ETAT_CHOICES,
    }
    return render(request, 'reclamations/modifier_reclamation.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_reclamation(request, pk):
    """Supprimer une réclamation"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    if request.method == 'POST':
        try:
            # Récupérer le numéro pour le message
            numero = reclamation.numero_reclamation
            
            # Supprimer la réclamation (les lignes seront supprimées automatiquement grâce à on_delete=CASCADE)
            reclamation.delete()
            
            messages.success(request, f"Réclamation '{numero}' supprimée avec succès!")
            return redirect('reclamations:liste')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:detail_reclamation', pk=pk)
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/supprimer.html', {'reclamation': reclamation})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def reclamations_en_retard(request):
    """Affiche les réclamations en retard"""
    reclamations_retard = NotificationService.get_reclamations_a_notifier()
    reclamations_alerte = NotificationService.get_reclamations_en_alerte()
    total_a_traiter = len(reclamations_retard) + len(reclamations_alerte)
    context = {
        'reclamations_retard': reclamations_retard,
        'reclamations_alerte': reclamations_alerte,
        'total_a_traiter': total_a_traiter,
    }
    return render(request, 'reclamations/notifications/liste.html', context)

# ================ GESTION DES UAP ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_uap(request):
    """Liste des UAP avec statistiques"""
    uaps = UAP.objects.all().order_by('nom')
    
    # Calculer les statistiques pour chaque UAP
    uaps_data = []
    for uap in uaps:
        # Compter le nombre de sites
        nb_sites = uap.sites.count()
        
        nb_reclamations = Reclamation.objects.filter(
            lignes__uap_concernee=uap
        ).distinct().count()
        
        uaps_data.append({
            'uap': uap,
            'nb_sites': nb_sites,
            'nb_reclamations': nb_reclamations
        })
    
    return render(request, 'reclamations/uap/liste.html', {'uaps_data': uaps_data})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_uap(request):
    """Créer une nouvelle UAP"""
    if request.method == 'POST':
        nom = request.POST.get('nom')
        if nom:
            UAP.objects.create(nom=nom)
            messages.success(request, f"UAP '{nom}' créée avec succès!")
            return redirect('reclamations:liste_uap')
        else:
            messages.error(request, "Le nom de l'UAP est requis.")
    
    return render(request, 'reclamations/uap/creer.html')

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_uap(request, pk):
    """Modifier une UAP"""
    uap = get_object_or_404(UAP, pk=pk)
    
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        
        if not nom:
            messages.error(request, "Le nom de l'UAP est requis.")
        else:
            # Vérifier si le nom existe déjà pour une autre UAP
            if UAP.objects.filter(nom=nom).exclude(pk=pk).exists():
                messages.error(request, f"Une autre UAP avec le nom '{nom}' existe déjà.")
            else:
                uap.nom = nom
                uap.save()
                messages.success(request, f"UAP '{nom}' modifiée avec succès!")
                return redirect('reclamations:liste_uap')
    
    return render(request, 'reclamations/uap/modifier.html', {'uap': uap})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_uap(request, pk):
    """Supprimer une UAP"""
    uap = get_object_or_404(UAP, pk=pk)
    
    if request.method == 'POST':
        try:
            # Vérifier si l'UAP a des sites associés
            if uap.sites.exists():
                messages.error(
                    request, 
                    f"Impossible de supprimer l'UAP '{uap.nom}' car elle a {uap.sites.count()} site(s) associé(s)."
                )
                return redirect('reclamations:liste_uap')
            
            nom = uap.nom
            uap.delete()
            messages.success(request, f"UAP '{nom}' supprimée avec succès!")
            return redirect('reclamations:liste_uap')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:liste_uap')
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/uap/supprimer.html', {'uap': uap})
    """Supprimer une UAP"""
    uap = get_object_or_404(UAP, pk=pk)
    
    if request.method == 'POST':
        if uap.sites.exists():
            messages.error(request, f"Impossible de supprimer l'UAP '{uap.nom}' car elle contient des sites.")
        else:
            uap.delete()
            messages.success(request, f"UAP '{uap.nom}' supprimée avec succès!")
        return redirect('reclamations:liste_uap')
    
    return render(request, 'reclamations/uap/supprimer.html', {'uap': uap})

# ================ GESTION DES SITES ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_sites(request):
    """Liste des sites"""
    sites = Site.objects.all().select_related('uap').order_by('nom')
    return render(request, 'reclamations/site/liste.html', {'sites': sites})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_site(request):
    """Créer un nouveau site"""
    if request.method == 'POST':
        nom = request.POST.get('nom')
        uap_id = request.POST.get('uap')
        
        if nom and uap_id:
            uap = get_object_or_404(UAP, pk=uap_id)
            Site.objects.create(nom=nom, uap=uap)
            messages.success(request, f"Site '{nom}' créé avec succès!")
            return redirect('reclamations:liste_sites')
        else:
            messages.error(request, "Le nom du site et l'UAP sont requis.")
    
    uaps = UAP.objects.all().order_by('nom')
    return render(request, 'reclamations/site/creer.html', {'uaps': uaps})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_site(request, pk):
    """Modifier un site"""
    site = get_object_or_404(Site, pk=pk)
    
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        uap_id = request.POST.get('uap')
        
        if not nom:
            messages.error(request, "Le nom du site est requis.")
        elif not uap_id:
            messages.error(request, "L'UAP est requise.")
        else:
            # Vérifier si le nom existe déjà pour un autre site
            if Site.objects.filter(nom=nom).exclude(pk=pk).exists():
                messages.error(request, f"Un autre site avec le nom '{nom}' existe déjà.")
            else:
                site.nom = nom
                site.uap_id = uap_id
                site.save()
                messages.success(request, f"Site '{nom}' modifié avec succès!")
                return redirect('reclamations:liste_sites')
    
    uaps = UAP.objects.all().order_by('nom')
    return render(request, 'reclamations/site/modifier.html', {
        'site': site,
        'uaps': uaps
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_site(request, pk):
    """Supprimer un site"""
    site = get_object_or_404(Site, pk=pk)
    
    if request.method == 'POST':
        try:
            # Vérifier si le site a des clients ou des réclamations associées
            if site.clients.exists():
                messages.error(
                    request, 
                    f"Impossible de supprimer le site '{site.nom}' car il a {site.clients.count()} client(s) associé(s)."
                )
                return redirect('reclamations:liste_sites')
            
            nom = site.nom
            site.delete()
            messages.success(request, f"Site '{nom}' supprimé avec succès!")
            return redirect('reclamations:liste_sites')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:liste_sites')
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/site/supprimer.html', {'site': site})

# ================ GESTION DES CLIENTS ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_clients(request):
    """Liste des clients"""
    # CORRECTION : Enlever select_related('site') car Client n'a pas de champ site
    clients = Client.objects.all().prefetch_related(
        'programmes', 
        'sites_client', 
        'reclamations'
    ).order_by('nom')
    
    # Calculer les statistiques
    clients_actifs = clients.filter(actif=True).count()
    total_sites_client = SiteClient.objects.count()
    
    context = {
        'clients': clients,
        'clients_actifs': clients_actifs,
        'total_sites_client': total_sites_client,
    }
    return render(request, 'reclamations/client/liste.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_client(request):
    """Créer un nouveau client avec ses sites"""
    if request.method == 'POST':
        try:
            # Récupérer les informations du client
            nom = request.POST.get('nom')
            email = request.POST.get('email', '')
            telephone = request.POST.get('telephone', '')
            actif = request.POST.get('actif') == 'on'
            
            # Validation
            if not nom:
                messages.error(request, "Le nom du client est requis.")
                # Re-afficher le formulaire avec les données saisies
                return render(request, 'reclamations/client/creer.html', {
                    'anciennes_valeurs': request.POST
                })
            
            # Créer le client (sans site usine car Client n'a pas ce champ)
            client = Client.objects.create(
                nom=nom,
                email=email,
                telephone=telephone,
                actif=actif
            )
            
            # Ajouter les sites client
            sites_noms = request.POST.getlist('site_client_nom[]')
            sites_adresses = request.POST.getlist('site_client_adresse[]')
            sites_villes = request.POST.getlist('site_client_ville[]')
            sites_cp = request.POST.getlist('site_client_cp[]')
            sites_pays = request.POST.getlist('site_client_pays[]')
            sites_contacts = request.POST.getlist('site_client_contact[]')
            sites_tel = request.POST.getlist('site_client_telephone[]')
            sites_email = request.POST.getlist('site_client_email[]')
            sites_actifs = request.POST.getlist('site_client_actif[]')
            
            sites_crees = 0
            for i in range(len(sites_noms)):
                if sites_noms[i].strip():  # Si le nom du site n'est pas vide
                    # Déterminer si le site est actif
                    site_actif = True
                    if i < len(sites_actifs):
                        # Les checkboxes non cochées ne sont pas envoyées
                        # Donc si l'index existe dans sites_actifs, c'est que c'est coché
                        site_actif = True
                    
                    SiteClient.objects.create(
                        nom=sites_noms[i].strip(),
                        client=client,
                        adresse=sites_adresses[i] if i < len(sites_adresses) else '',
                        ville=sites_villes[i] if i < len(sites_villes) else '',
                        code_postal=sites_cp[i] if i < len(sites_cp) else '',
                        pays=sites_pays[i] if i < len(sites_pays) else 'France',
                        contact_principal=sites_contacts[i] if i < len(sites_contacts) else '',
                        telephone=sites_tel[i] if i < len(sites_tel) else '',
                        email=sites_email[i] if i < len(sites_email) else '',
                        actif=site_actif
                    )
                    sites_crees += 1
            
            # Message de succès
            if sites_crees > 0:
                messages.success(
                    request, 
                    f"Client '{nom}' créé avec succès avec {sites_crees} site(s) client."
                )
            else:
                messages.success(
                    request, 
                    f"Client '{nom}' créé avec succès (aucun site client ajouté)."
                )
            
            return redirect('reclamations:liste_clients')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            # Log l'erreur pour le débogage
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur création client: {str(e)}")
            return render(request, 'reclamations/client/creer.html', {
                'anciennes_valeurs': request.POST
            })
    
    # GET : afficher le formulaire
    return render(request, 'reclamations/client/creer.html')

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_client(request, pk):
    """Modifier un client et ses sites"""
    client = get_object_or_404(Client.objects.prefetch_related('sites_client'), pk=pk)
    
    if request.method == 'POST':
        try:
            # Debug: Afficher les données POST
            print("=== DONNÉES POST REÇUES ===")
            for key, value in request.POST.items():
                if not key.startswith('csrf'):  # Éviter d'afficher le token CSRF
                    print(f"{key}: {value}")
            print("==========================")
            
            # Mettre à jour les informations du client
            client.nom = request.POST.get('nom', client.nom)
            client.email = request.POST.get('email', '')
            client.telephone = request.POST.get('telephone', '')
            client.actif = request.POST.get('actif') == 'on'
            client.save()
            
            # Traiter les sites client
            site_ids = request.POST.getlist('site_client_id[]')
            site_noms = request.POST.getlist('site_client_nom[]')
            site_adresses = request.POST.getlist('site_client_adresse[]')
            site_villes = request.POST.getlist('site_client_ville[]')
            site_cp = request.POST.getlist('site_client_cp[]')
            site_pays = request.POST.getlist('site_client_pays[]')
            site_contacts = request.POST.getlist('site_client_contact[]')
            site_tels = request.POST.getlist('site_client_telephone[]')
            site_emails = request.POST.getlist('site_client_email[]')
            
            # Récupérer les IDs des sites actifs (méthode avec nom unique)
            site_actifs_ids = []
            for key in request.POST:
                if key.startswith('site_client_actif_'):
                    # Extraire l'ID du nom du champ
                    site_id = key.replace('site_client_actif_', '')
                    site_actifs_ids.append(site_id)
            
            print(f"Sites actifs IDs reçus: {site_actifs_ids}")
            
            sites_conserves = []
            
            for i in range(len(site_ids)):
                if i >= len(site_noms):
                    continue
                    
                site_id = site_ids[i]
                site_nom = site_noms[i].strip()
                
                if not site_nom:
                    continue
                
                # Déterminer si le site est actif
                is_active = str(site_id) in site_actifs_ids
                print(f"Site {site_id} - {site_nom}: actif = {is_active}")
                
                if site_id.startswith('new_'):  # Nouveau site
                    site = SiteClient.objects.create(
                        nom=site_nom,
                        client=client,
                        adresse=site_adresses[i] if i < len(site_adresses) else '',
                        ville=site_villes[i] if i < len(site_villes) else '',
                        code_postal=site_cp[i] if i < len(site_cp) else '',
                        pays=site_pays[i] if i < len(site_pays) else 'France',
                        contact_principal=site_contacts[i] if i < len(site_contacts) else '',
                        telephone=site_tels[i] if i < len(site_tels) else '',
                        email=site_emails[i] if i < len(site_emails) else '',
                        actif=is_active
                    )
                    sites_conserves.append(site.id)
                else:  # Site existant
                    try:
                        site = SiteClient.objects.get(id=site_id, client=client)
                        site.nom = site_nom
                        site.adresse = site_adresses[i] if i < len(site_adresses) else ''
                        site.ville = site_villes[i] if i < len(site_villes) else ''
                        site.code_postal = site_cp[i] if i < len(site_cp) else ''
                        site.pays = site_pays[i] if i < len(site_pays) else 'France'
                        site.contact_principal = site_contacts[i] if i < len(site_contacts) else ''
                        site.telephone = site_tels[i] if i < len(site_tels) else ''
                        site.email = site_emails[i] if i < len(site_emails) else ''
                        site.actif = is_active
                        site.save()
                        sites_conserves.append(site.id)
                    except SiteClient.DoesNotExist:
                        continue
            
            # Supprimer les sites qui ne sont plus dans la liste
            supprimes = client.sites_client.exclude(id__in=sites_conserves).delete()
            print(f"Sites supprimés: {supprimes}")
            
            messages.success(request, f"Client '{client.nom}' modifié avec succès!")
            return redirect('reclamations:liste_clients')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            print(f"Erreur modification client: {e}")
            import traceback
            traceback.print_exc()
    
    return render(request, 'reclamations/client/modifier.html', {
        'client': client,
        'sites_client': client.sites_client.all().order_by('nom')
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_client(request, pk):
    """Supprimer un client"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        try:
            # Vérifier si le client a des réclamations
            if client.reclamations.exists():
                messages.error(
                    request, 
                    f"Impossible de supprimer le client '{client.nom}' car il a {client.reclamations.count()} réclamation(s) associée(s)."
                )
                return redirect('reclamations:liste_clients')
            
            # Récupérer le nom pour le message
            nom = client.nom
            
            # Supprimer le client
            client.delete()
            
            messages.success(request, f"Client '{nom}' supprimé avec succès!")
            return redirect('reclamations:liste_clients')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:liste_clients')
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/client/supprimer.html', {'client': client})

# ================ GESTION DES PRODUITS ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_produits(request):
    """Liste des produits avec pagination et recherche"""
    
    # Requête de base
    produits = Produit.objects.annotate(
        nb_reclamations=Count('lignes_reclamation')
    )
    
    # Recherche
    search = request.GET.get('search', '')
    if search:
        produits = produits.filter(
            Q(product_number__icontains=search) |
            Q(designation__icontains=search)
        )
    
    # Tri
    produits = produits.order_by('product_number')
    
    # Pagination
    paginator = Paginator(produits, 20)  # 20 produits par page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'produits': page_obj,
        'page_obj': page_obj,
        'search': search,
        'total_produits': paginator.count,
    }
    
    return render(request, 'reclamations/produit/liste.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_produit(request):
    """Créer un nouveau produit"""
    if request.method == 'POST':
        product_number = request.POST.get('product_number')
        designation = request.POST.get('designation', '')
        actif = request.POST.get('actif') == 'on'
        
        if product_number:
            # Vérifier si le produit existe déjà
            if Produit.objects.filter(product_number=product_number).exists():
                messages.error(request, f"Un produit avec le numéro '{product_number}' existe déjà.")
            else:
                Produit.objects.create(
                    product_number=product_number,
                    designation=designation,
                    actif=actif
                )
                messages.success(request, f"Produit '{product_number}' créé avec succès!")
                return redirect('reclamations:liste_produits')
        else:
            messages.error(request, "Le numéro produit est requis.")
    
    return render(request, 'reclamations/produit/creer.html')

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_produit(request, pk):
    """Modifier un produit"""
    produit = get_object_or_404(Produit, pk=pk)
    
    if request.method == 'POST':
        product_number = request.POST.get('product_number', '').strip()
        designation = request.POST.get('designation', '')
        actif = request.POST.get('actif') == 'on'
        
        if not product_number:
            messages.error(request, "Le numéro de produit est requis.")
        else:
            # Vérifier si le numéro existe déjà pour un autre produit
            if Produit.objects.filter(product_number=product_number).exclude(pk=pk).exists():
                messages.error(request, f"Un autre produit avec le numéro '{product_number}' existe déjà.")
            else:
                produit.product_number = product_number
                produit.designation = designation
                produit.actif = actif
                produit.save()
                messages.success(request, f"Produit '{product_number}' modifié avec succès!")
                return redirect('reclamations:liste_produits')
    
    return render(request, 'reclamations/produit/modifier.html', {'produit': produit})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_produit(request, pk):
    """Supprimer un produit"""
    produit = get_object_or_404(Produit, pk=pk)
    
    if request.method == 'POST':
        try:
            # Vérifier si le produit est utilisé dans des réclamations
            if produit.lignes_reclamation.exists():
                messages.error(
                    request, 
                    f"Impossible de supprimer le produit '{produit.product_number}' car il est utilisé dans {produit.lignes_reclamation.count()} réclamation(s)."
                )
                return redirect('reclamations:liste_produits')
            
            product_number = produit.product_number
            produit.delete()
            messages.success(request, f"Produit '{product_number}' supprimé avec succès!")
            return redirect('reclamations:liste_produits')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:liste_produits')
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/produit/supprimer.html', {'produit': produit})

# ================ GESTION DES OBJECTIFS ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_objectifs(request):
    """Liste des objectifs par année avec moyennes"""
    # Récupérer toutes les années distinctes
    annees = ObjectifsAnnuel.objects.values_list('annee', flat=True).distinct().order_by('-annee')
    
    objectifs_par_annee = []
    
    for annee in annees:
        # Récupérer les objectifs pour cette année
        objectifs = ObjectifsAnnuel.objects.filter(annee=annee).select_related('site__uap')
        
        # Calculer les moyennes
        nb_sites = objectifs.count()
        if nb_sites > 0:
            # Calcul manuel des moyennes
            total_rebut = 0
            total_ppm = 0
            total_rework = 0
            
            for obj in objectifs:
                total_rebut += obj.objectif_rebut
                total_ppm += obj.objectif_ppm_externe
                total_rework += obj.objectif_rework
            
            moy_rebut = total_rebut / nb_sites
            moy_ppm = total_ppm / nb_sites
            moy_rework = total_rework / nb_sites
        else:
            moy_rebut = 0
            moy_ppm = 0
            moy_rework = 0
        
        objectifs_par_annee.append({
            'annee': annee,
            'objectifs': objectifs,
            'moyenne_rebut': moy_rebut,
            'moyenne_ppm': moy_ppm,
            'moyenne_rework': moy_rework
        })
    
    return render(request, 'reclamations/objectifs/liste.html', {
        'objectifs_par_annee': objectifs_par_annee
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_objectifs_annee(request):
    """Créer des objectifs pour une année (tous les sites)"""
    if request.method == 'POST':
        annee = request.POST.get('annee')
        
        try:
            annee = int(annee)
        except ValueError:
            messages.error(request, "L'année doit être un nombre.")
            return redirect('reclamations:creer_objectifs_annee')
        
        # Vérifier si des objectifs existent déjà pour cette année
        if ObjectifsAnnuel.objects.filter(annee=annee).exists():
            messages.error(request, f"Des objectifs pour l'année {annee} existent déjà.")
            return redirect('reclamations:liste_objectifs')
        
        # Récupérer tous les sites
        sites = Site.objects.all()
        
        # Créer les objectifs pour chaque site
        objectifs_crees = 0
        for site in sites:
            objectif_rebut = request.POST.get(f'rebut_{site.id}', '0')
            objectif_ppm = request.POST.get(f'ppm_{site.id}', '0')
            objectif_rework = request.POST.get(f'rework_{site.id}', '0')
            
            try:
                ObjectifsAnnuel.objects.create(
                    annee=annee,
                    site=site,
                    objectif_rebut=Decimal(str(objectif_rebut)),
                    objectif_ppm_externe=int(objectif_ppm),
                    objectif_rework=Decimal(str(objectif_rework))
                )
                objectifs_crees += 1
            except Exception as e:
                messages.error(request, f"Erreur pour le site {site.nom}: {str(e)}")
        
        if objectifs_crees > 0:
            messages.success(request, f"Objectifs pour l'année {annee} créés avec succès pour {objectifs_crees} site(s)!")
            return redirect('reclamations:liste_objectifs')
    
    # GET : afficher le formulaire
    current_year = timezone.now().year
    annees_disponibles = range(current_year - 5, current_year + 6)
    sites = Site.objects.all().select_related('uap').order_by('nom')
    
    return render(request, 'reclamations/objectifs/creer.html', {
        'annees_disponibles': annees_disponibles,
        'sites': sites
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_objectifs_annee(request, annee):
    """Modifier les objectifs pour une année"""
    objectifs = ObjectifsAnnuel.objects.filter(annee=annee).select_related('site')
    
    if not objectifs.exists():
        messages.error(request, f"Aucun objectif trouvé pour l'année {annee}.")
        return redirect('reclamations:liste_objectifs')
    
    if request.method == 'POST':
        try:
            for obj in objectifs:
                objectif_rebut = request.POST.get(f'rebut_{obj.site.id}', obj.objectif_rebut)
                objectif_ppm = request.POST.get(f'ppm_{obj.site.id}', obj.objectif_ppm_externe)
                objectif_rework = request.POST.get(f'rework_{obj.site.id}', obj.objectif_rework)
                
                obj.objectif_rebut = Decimal(str(objectif_rebut))
                obj.objectif_ppm_externe = int(objectif_ppm)
                obj.objectif_rework = Decimal(str(objectif_rework))
                obj.save()
            
            messages.success(request, f"Objectifs pour l'année {annee} modifiés avec succès!")
            return redirect('reclamations:liste_objectifs')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
    
    return render(request, 'reclamations/objectifs/modifier_annee.html', {
        'annee': annee,
        'objectifs': objectifs
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_objectifs_annee(request, annee):
    """Supprimer tous les objectifs d'une année"""
    objectifs = ObjectifsAnnuel.objects.filter(annee=annee)
    
    if request.method == 'POST':
        try:
            nb_supprimes = objectifs.count()
            objectifs.delete()
            messages.success(request, f"Objectifs pour l'année {annee} supprimés avec succès ({nb_supprimes} site(s)).")
            return redirect('reclamations:liste_objectifs')
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
    return render(request, 'reclamations/objectifs/supprimer_annee.html', {
        'annee': annee,
        'objectifs': objectifs
    })

# ================ GESTION DES PROGRAMMES ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_programmes(request):
    """Liste des programmes"""
    programmes = Programme.objects.all().prefetch_related('clients').order_by('nom')
    return render(request, 'reclamations/programme/liste.html', {'programmes': programmes})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def creer_programme(request):
    """Créer un nouveau programme"""
    if request.method == 'POST':
        nom = request.POST.get('nom')
        clients_ids = request.POST.getlist('clients')  # Liste des IDs clients
        description = request.POST.get('description', '')
        actif = request.POST.get('actif') == 'on'
        
        if nom and clients_ids:
            # Vérifier si le programme existe déjà
            if Programme.objects.filter(nom=nom).exists():
                messages.error(request, f"Un programme avec le nom '{nom}' existe déjà.")
            else:
                programme = Programme.objects.create(
                    nom=nom,
                    description=description,
                    actif=actif
                )
                # Ajouter les clients sélectionnés
                programme.clients.set(clients_ids)
                messages.success(request, f"Programme '{nom}' créé avec succès avec {len(clients_ids)} client(s)!")
                return redirect('reclamations:liste_programmes')
        else:
            messages.error(request, "Le nom du programme et au moins un client sont requis.")
    
    clients = Client.objects.filter(actif=True).order_by('nom')
    return render(request, 'reclamations/programme/creer.html', {'clients': clients})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_programme(request, pk):
    """Modifier un programme"""
    programme = get_object_or_404(Programme, pk=pk)
    
    if request.method == 'POST':
        nom = request.POST.get('nom')
        clients_ids = request.POST.getlist('clients')
        description = request.POST.get('description', '')
        actif = request.POST.get('actif') == 'on'
        
        if nom and clients_ids:
            # Vérifier si le nom existe déjà pour un autre programme
            if Programme.objects.filter(nom=nom).exclude(pk=pk).exists():
                messages.error(request, f"Un autre programme avec le nom '{nom}' existe déjà.")
            else:
                programme.nom = nom
                programme.description = description
                programme.actif = actif
                programme.save()
                # Mettre à jour les clients
                programme.clients.set(clients_ids)
                messages.success(request, f"Programme '{nom}' modifié avec succès!")
                return redirect('reclamations:liste_programmes')
        else:
            messages.error(request, "Le nom du programme et au moins un client sont requis.")
    
    clients = Client.objects.filter(actif=True).order_by('nom')
    return render(request, 'reclamations/programme/modifier.html', {
        'programme': programme,
        'clients': clients
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_programme(request, pk):
    """Supprimer un programme"""
    programme = get_object_or_404(Programme, pk=pk)
    
    if request.method == 'POST':
        try:
            # Vérifier si le programme a des réclamations associées
            if programme.reclamations.exists():
                messages.error(
                    request, 
                    f"Impossible de supprimer le programme '{programme.nom}' car il est utilisé dans {programme.reclamations.count()} réclamation(s)."
                )
                return redirect('reclamations:liste_programmes')
            
            nom = programme.nom
            programme.delete()
            messages.success(request, f"Programme '{nom}' supprimé avec succès!")
            return redirect('reclamations:liste_programmes')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
            return redirect('reclamations:liste_programmes')
    
    # GET: afficher la page de confirmation
    return render(request, 'reclamations/programme/supprimer.html', {'programme': programme})

# API pour charger les programmes d'un client en AJAX
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def get_programmes_by_client(request):
    """Endpoint AJAX pour récupérer les programmes d'un client"""
    client_id = request.GET.get('client_id')
    if client_id:
        programmes = Programme.objects.filter(client_id=client_id, actif=True).values('id', 'nom')
        return JsonResponse(list(programmes), safe=False)
    return JsonResponse([], safe=False)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def liste_livraisons(request):
    """Liste des livraisons"""
    livraisons = Livraison.objects.all().select_related('client').order_by('-date_livraison')
    
    # Calculer les totaux pour l'affichage
    total_quantite = livraisons.aggregate(total=Sum('quantite_livree'))['total'] or 0
    
    context = {
        'livraisons': livraisons,
        'total_quantite': total_quantite,
        'total_livraisons': livraisons.count()
    }
    return render(request, 'reclamations/livraison/liste.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def ajouter_livraison(request):
    """Ajouter une livraison"""
    if request.method == 'POST':
        client_id = request.POST.get('client')
        date_livraison = request.POST.get('date_livraison')
        quantite_livree = request.POST.get('quantite_livree')
        numero_bon_livraison = request.POST.get('numero_bon_livraison', '')
        reference_commande = request.POST.get('reference_commande', '')
        remarques = request.POST.get('remarques', '')
        
        # Validation
        erreurs = []
        if not client_id:
            erreurs.append("Le client est requis.")
        if not date_livraison:
            erreurs.append("La date de livraison est requise.")
        if not quantite_livree:
            erreurs.append("La quantité livrée est requise.")
        elif int(quantite_livree) <= 0:
            erreurs.append("La quantité livrée doit être positive.")
        
        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
        else:
            try:
                Livraison.objects.create(
                    client_id=client_id,
                    date_livraison=date_livraison,
                    quantite_livree=quantite_livree,
                    numero_bon_livraison=numero_bon_livraison,
                    reference_commande=reference_commande,
                    remarques=remarques
                )
                messages.success(request, "Livraison ajoutée avec succès!")
                return redirect('reclamations:liste_livraisons')
            except Exception as e:
                messages.error(request, f"Erreur: {str(e)}")
    
    clients = Client.objects.filter(actif=True).order_by('nom')
    return render(request, 'reclamations/livraison/ajouter.html', {'clients': clients})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def modifier_livraison(request, pk):
    """Modifier une livraison"""
    livraison = get_object_or_404(Livraison, pk=pk)
    
    if request.method == 'POST':
        client_id = request.POST.get('client')
        date_livraison = request.POST.get('date_livraison')
        quantite_livree = request.POST.get('quantite_livree')
        numero_bon_livraison = request.POST.get('numero_bon_livraison', '')
        reference_commande = request.POST.get('reference_commande', '')
        remarques = request.POST.get('remarques', '')
        
        # Validation
        erreurs = []
        if not client_id:
            erreurs.append("Le client est requis.")
        if not date_livraison:
            erreurs.append("La date de livraison est requise.")
        if not quantite_livree:
            erreurs.append("La quantité livrée est requise.")
        elif int(quantite_livree) <= 0:
            erreurs.append("La quantité livrée doit être positive.")
        
        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
        else:
            try:
                livraison.client_id = client_id
                livraison.date_livraison = date_livraison
                livraison.quantite_livree = quantite_livree
                livraison.numero_bon_livraison = numero_bon_livraison
                livraison.reference_commande = reference_commande
                livraison.remarques = remarques
                livraison.save()
                messages.success(request, "Livraison modifiée avec succès!")
                return redirect('reclamations:liste_livraisons')
            except Exception as e:
                messages.error(request, f"Erreur: {str(e)}")
    
    clients = Client.objects.filter(actif=True).order_by('nom')
    return render(request, 'reclamations/livraison/modifier.html', {
        'livraison': livraison,
        'clients': clients
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def supprimer_livraison(request, pk):
    """Supprimer une livraison"""
    livraison = get_object_or_404(Livraison, pk=pk)
    
    if request.method == 'POST':
        try:
            livraison.delete()
            messages.success(request, "Livraison supprimée avec succès!")
            return redirect('reclamations:liste_livraisons')
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
    
    return render(request, 'reclamations/livraison/supprimer.html', {'livraison': livraison})

# ================ IMPORT PRODUITS DEPUIS EXCEL ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_produits_excel(request):
    """Importe des produits depuis un fichier Excel"""
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        # Vérifier l'extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
            return redirect('reclamations:import_produits')
        
        try:
            # Lire le fichier Excel
            df = pd.read_excel(excel_file)
            
            # Vérifier les colonnes requises
            required_columns = ['product_number', 'designation', 'actif']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f"Colonnes manquantes: {', '.join(missing_columns)}")
                return redirect('reclamations:import_produits')
            
            # Statistiques d'import
            total = 0
            crees = 0
            mis_a_jour = 0
            erreurs = []
            
            for index, row in df.iterrows():
                try:
                    product_number = str(row['product_number']).strip()
                    designation = str(row.get('designation', '')).strip() if pd.notna(row.get('designation')) else ''
                    
                    # Déterminer le statut actif
                    actif = True
                    if 'actif' in row and pd.notna(row['actif']):
                        if isinstance(row['actif'], bool):
                            actif = row['actif']
                        elif isinstance(row['actif'], str):
                            actif = row['actif'].lower() in ['oui', 'true', '1', 'actif']
                        else:
                            actif = bool(row['actif'])
                    
                    # Vérifier si le produit existe déjà
                    produit, created = Produit.objects.update_or_create(
                        product_number=product_number,
                        defaults={
                            'designation': designation,
                            'actif': actif
                        }
                    )
                    
                    if created:
                        crees += 1
                    else:
                        mis_a_jour += 1
                    
                    total += 1
                    
                except Exception as e:
                    erreurs.append(f"Ligne {index + 2}: {str(e)}")
            
            # Message de résultat
            if erreurs:
                messages.warning(request, f"Import terminé avec {len(erreurs)} erreur(s).")
                for erreur in erreurs[:5]:  # Afficher les 5 premières erreurs
                    messages.error(request, erreur)
            else:
                messages.success(
                    request, 
                    f"Import réussi ! {crees} produit(s) créé(s), {mis_a_jour} mis à jour."
                )
            
            return redirect('reclamations:liste_produits')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier: {str(e)}")
            return redirect('reclamations:import_produits')
    
    return render(request, 'reclamations/import/produits.html')

# ================ IMPORT CLIENTS DEPUIS EXCEL ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_clients_excel(request):
    """Importe des clients depuis un fichier Excel"""
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
            return redirect('reclamations:import_clients')
        
        try:
            df = pd.read_excel(excel_file)
            
            # Vérifier les colonnes requises
            required_columns = ['nom', 'email', 'telephone', 'actif']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f"Colonnes manquantes: {', '.join(missing_columns)}")
                return redirect('reclamations:import_clients')
            
            total = 0
            crees = 0
            mis_a_jour = 0
            erreurs = []
            
            for index, row in df.iterrows():
                try:
                    nom = str(row['nom']).strip()
                    email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else ''
                    telephone = str(row.get('telephone', '')).strip() if pd.notna(row.get('telephone')) else ''
                    
                    actif = True
                    if 'actif' in row and pd.notna(row['actif']):
                        if isinstance(row['actif'], bool):
                            actif = row['actif']
                        else:
                            actif = str(row['actif']).lower() in ['oui', 'true', '1', 'actif']
                    
                    client, created = Client.objects.update_or_create(
                        nom=nom,
                        defaults={
                            'email': email,
                            'telephone': telephone,
                            'actif': actif
                        }
                    )
                    
                    if created:
                        crees += 1
                    else:
                        mis_a_jour += 1
                    
                    total += 1
                    
                except Exception as e:
                    erreurs.append(f"Ligne {index + 2}: {str(e)}")
            
            if erreurs:
                messages.warning(request, f"Import terminé avec {len(erreurs)} erreur(s).")
            else:
                messages.success(request, f"Import réussi ! {crees} client(s) créé(s), {mis_a_jour} mis à jour.")
            
            return redirect('reclamations:liste_clients')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('reclamations:import_clients')
    
    return render(request, 'reclamations/import/clients.html')

# ================ IMPORT RÉCLAMATIONS DEPUIS EXCEL ================
def extraire_produits(produits_raw):
    """Extrait la liste des produits à partir d'une chaîne"""
    if not produits_raw or produits_raw == 'nan':
        return []
    
    # Remplacer les séparateurs courants
    produits_raw = str(produits_raw).replace('\n', ',').replace('\r', ',').replace(';', ',').replace('|', ',')
    
    # Séparer par virgule
    produits = [p.strip() for p in produits_raw.split(',')]
    
    # Filtrer les valeurs vides
    produits = [p for p in produits if p and p != 'nan']
    
    return produits

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_reclamations_excel(request):
    """Importe des réclamations depuis un fichier Excel"""
    step = request.POST.get('step', '1')
    
    if request.method == 'POST':
        if step == '1' and request.FILES.get('excel_file'):
            excel_file = request.FILES['excel_file']
            
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
                return redirect('reclamations:import_reclamations')
            
            try:
                # Lire le fichier Excel
                df = pd.read_excel(excel_file)
                
                # Convertir les données pour éviter les problèmes de sérialisation
                preview_data = []
                for index, row in df.iterrows():
                    # Convertir chaque ligne en dictionnaire sérialisable
                    row_dict = {}
                    for col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            row_dict[col] = None
                        elif isinstance(value, (pd.Timestamp, datetime)):
                            row_dict[col] = value.strftime('%Y-%m-%d')
                        elif isinstance(value, Decimal):
                            row_dict[col] = float(value)
                        else:
                            row_dict[col] = value
                    
                    # Traiter les produits
                    produits_raw = str(row_dict.get('produit', '')).strip()
                    produits_list = extraire_produits(produits_raw)
                    
                    # Traiter les descriptions de non-conformités (séparées par +)
                    description_raw = str(row_dict.get('description_non_conformite', '')).strip()
                    nc_list = extraire_non_conformites(description_raw)
                    
                    # Construire les données de prévisualisation
                    row_data = {
                        'ligne': index + 2,
                        'numero_reclamation': str(row_dict.get('numero_reclamation', '')).strip(),
                        'date_reclamation': row_dict.get('date_reclamation', ''),
                        'client_nom': str(row_dict.get('client', '')).strip(),
                        'site_nom': str(row_dict.get('site', '')).strip(),
                        'site_client_nom': str(row_dict.get('site_client', '')).strip() if row_dict.get('site_client') else '',
                        'programme_nom': str(row_dict.get('programme', '')).strip() if row_dict.get('programme') else '',
                        'type_nc': str(row_dict.get('type_nc', 'TECHNIQUE')).strip().upper(),
                        'imputation': str(row_dict.get('imputation', 'CIM')).strip().upper(),
                        'etat_4d': str(row_dict.get('etat_4d', 'OUVERT')).strip().upper(),
                        'etat_8d': str(row_dict.get('etat_8d', 'OUVERT')).strip().upper(),
                        'evidence': str(row_dict.get('evidence', '')).strip() if row_dict.get('evidence') else '',
                        'me': bool(row_dict.get('me', False)) if row_dict.get('me') else False,
                        'cloture': bool(row_dict.get('cloture', False)) if row_dict.get('cloture') else False,
                        'date_cloture': row_dict.get('date_cloture', ''),
                        'date_cloture_4d': row_dict.get('date_cloture_4d', ''),
                        'date_cloture_8d': row_dict.get('date_cloture_8d', ''),
                        'decision': str(row_dict.get('decision', '')).strip() if row_dict.get('decision') else '',
                        'nqc': float(row_dict.get('nqc', 0)) if row_dict.get('nqc') else 0,
                        'numero_4d': str(row_dict.get('numero_4d', '')).strip() if row_dict.get('numero_4d') else '',
                        'numero_8d': str(row_dict.get('numero_8d', '')).strip() if row_dict.get('numero_8d') else '',
                        'produits': produits_list,
                        'quantite': int(row_dict.get('quantite', 1)) if row_dict.get('quantite') else 1,
                        'non_conformites': nc_list,  # Liste des NC
                        'commentaire': str(row_dict.get('commentaire', '')).strip() if row_dict.get('commentaire') else '',
                        'uap_nom': str(row_dict.get('uap_concernee', '')).strip() if row_dict.get('uap_concernee') else '',
                        'erreurs': []
                    }
                    
                    # Valider la ligne
                    valider_ligne_import(row_data)
                    preview_data.append(row_data)
                
                # Stocker les données en session pour l'import final
                request.session['import_preview_data'] = preview_data
                
                return render(request, 'reclamations/import/reclamations.html', {
                    'step': 2,
                    'preview_data': preview_data,
                    'total_lignes': len(preview_data)
                })
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la lecture du fichier: {str(e)}")
                return redirect('reclamations:import_reclamations')
        
        elif step == '2' and request.POST.get('confirm_import'):
            # Récupérer les données de prévisualisation
            preview_data = request.session.get('import_preview_data', [])
            
            if not preview_data:
                messages.error(request, "Aucune donnée à importer")
                return redirect('reclamations:import_reclamations')
            
            resultat = {
                'total': len(preview_data),
                'crees': 0,
                'erreurs': [],
                'skips': 0,
                'produits_importes': 0,
                'nc_importes': 0
            }
            
            # Traitement ligne par ligne sans transaction atomique globale
            for row_data in preview_data:
                # Ignorer les lignes avec erreurs
                if row_data.get('erreurs'):
                    resultat['skips'] += 1
                    for err in row_data['erreurs']:
                        resultat['erreurs'].append(f"Ligne {row_data['ligne']}: {err}")
                    continue
                
                try:
                    # Démarrer une transaction pour chaque ligne
                    with transaction.atomic():
                        # Récupérer le client
                        client = Client.objects.filter(nom=row_data['client_nom']).first()
                        if not client:
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Client '{row_data['client_nom']}' non trouvé")
                            resultat['skips'] += 1
                            continue
                        
                        # Récupérer le site client (optionnel)
                        site_client = None
                        if row_data['site_client_nom']:
                            site_client = SiteClient.objects.filter(
                                client=client, 
                                nom=row_data['site_client_nom']
                            ).first()
                        
                        # Récupérer le programme (optionnel)
                        programme = None
                        if row_data['programme_nom']:
                            programme = Programme.objects.filter(
                                clients=client, 
                                nom=row_data['programme_nom']
                            ).first()
                        
                        # Vérifier si la réclamation existe déjà
                        if Reclamation.objects.filter(numero_reclamation=row_data['numero_reclamation']).exists():
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Réclamation {row_data['numero_reclamation']} existe déjà")
                            resultat['skips'] += 1
                            continue
                        
                        # Créer la réclamation
                        reclamation = Reclamation.objects.create(
                            numero_reclamation=row_data['numero_reclamation'],
                            date_reclamation=datetime.strptime(row_data['date_reclamation'], '%Y-%m-%d').date() if row_data['date_reclamation'] else timezone.now().date(),
                            client=client,
                            site_client=site_client,
                            programme=programme,
                            imputation=row_data['imputation'],
                            type_nc=row_data['type_nc'],
                            etat_4d=row_data['etat_4d'],
                            etat_8d=row_data['etat_8d'],
                            evidence=row_data['evidence'],
                            me=row_data['me'],
                            cloture=row_data['cloture'],
                            date_cloture=datetime.strptime(row_data['date_cloture'], '%Y-%m-%d').date() if row_data['date_cloture'] else None,
                            date_cloture_4d=datetime.strptime(row_data['date_cloture_4d'], '%Y-%m-%d').date() if row_data['date_cloture_4d'] else None,
                            date_cloture_8d=datetime.strptime(row_data['date_cloture_8d'], '%Y-%m-%d').date() if row_data['date_cloture_8d'] else None,
                            decision=row_data['decision'],
                            nqc=row_data['nqc'],
                            numero_4d=row_data['numero_4d'],
                            numero_8d=row_data['numero_8d'],
                            createur=request.user
                        )
                        resultat['crees'] += 1
                        
                        # Récupérer le site de production
                        site = Site.objects.filter(nom=row_data['site_nom']).first()
                        if not site:
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Site '{row_data['site_nom']}' non trouvé")
                            resultat['skips'] += 1
                            continue
                        
                        # Récupérer l'UAP (optionnel)
                        uap = None
                        if row_data['uap_nom']:
                            uap = UAP.objects.filter(nom=row_data['uap_nom']).first()
                        
                        # Si pas d'UAP spécifiée mais site trouvé, utiliser l'UAP du site
                        if not uap and site and site.uap:
                            uap = site.uap
                        
                        # Créer les lignes de réclamation pour chaque produit
                        produits_uniques = set(row_data['produits'])
                        for produit_pn in produits_uniques:
                            produit = Produit.objects.filter(product_number=produit_pn).first()
                            if produit:
                                # Vérifier si cette ligne existe déjà
                                ligne_existante = LigneReclamation.objects.filter(
                                    reclamation=reclamation,
                                    produit=produit
                                ).first()
                                
                                if ligne_existante:
                                    # Si la ligne existe déjà, mettre à jour la quantité
                                    ligne_existante.quantite += row_data['quantite']
                                    ligne_existante.save()
                                    
                                    # Ajouter les NC à la ligne existante
                                    for nc_desc in row_data['non_conformites']:
                                        if nc_desc:
                                            NonConformite.objects.create(
                                                ligne_reclamation=ligne_existante,
                                                description=nc_desc,
                                                quantite=row_data['quantite']
                                            )
                                            resultat['nc_importes'] += 1
                                    
                                    resultat['produits_importes'] += 1
                                else:
                                    # Créer une nouvelle ligne
                                    ligne = LigneReclamation.objects.create(
                                        reclamation=reclamation,
                                        produit=produit,
                                        quantite=row_data['quantite'],
                                        description_non_conformite=" | ".join(row_data['non_conformites']) if row_data['non_conformites'] else "",
                                        commentaire=row_data['commentaire'],
                                        site=site,
                                        uap_concernee=uap
                                    )
                                    
                                    # Créer les non-conformités individuelles
                                    for nc_desc in row_data['non_conformites']:
                                        if nc_desc:
                                            NonConformite.objects.create(
                                                ligne_reclamation=ligne,
                                                description=nc_desc,
                                                quantite=row_data['quantite']
                                            )
                                            resultat['nc_importes'] += 1
                                    
                                    resultat['produits_importes'] += 1
                            else:
                                resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Produit '{produit_pn}' non trouvé")
                
                except Exception as e:
                    resultat['erreurs'].append(f"Ligne {row_data.get('ligne', '?')}: {str(e)}")
                    resultat['skips'] += 1
            
            # Nettoyer la session
            request.session.pop('import_preview_data', None)
            
            messages.success(
                request, 
                f"Import terminé! {resultat['crees']} réclamations créées, "
                f"{resultat['produits_importes']} produits importés, "
                f"{resultat['nc_importes']} non-conformités créées."
            )
            
            if resultat['erreurs']:
                messages.warning(request, f"{len(resultat['erreurs'])} erreur(s) rencontrée(s)")
            
            return render(request, 'reclamations/import/reclamations.html', {
                'step': 3,
                'resultat': resultat
            })
    
    return render(request, 'reclamations/import/reclamations.html', {'step': 1})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def extraire_non_conformites(description_raw):
    """
    Extrait les non-conformités d'une chaîne de caractères.
    Les NC peuvent être séparées par '+' ou '|'
    """
    if not description_raw:
        return []
    
    # Remplacer les séparateurs par un séparateur unique
    description_raw = description_raw.replace('|', '+')
    
    # Séparer et nettoyer
    nc_list = []
    for nc in description_raw.split('+'):
        nc_clean = nc.strip()
        if nc_clean:
            nc_list.append(nc_clean)
    
    return nc_list

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def valider_ligne_import(row_data):
    """Valide une ligne d'import et ajoute les erreurs dans row_data['erreurs']"""
    erreurs = []
    
    # Validation des champs obligatoires
    if not row_data.get('numero_reclamation'):
        erreurs.append("Numéro de réclamation obligatoire")
    
    if not row_data.get('date_reclamation'):
        erreurs.append("Date de réclamation obligatoire")
    elif row_data.get('date_reclamation'):
        try:
            datetime.strptime(row_data['date_reclamation'], '%Y-%m-%d')
        except ValueError:
            erreurs.append("Format de date invalide (attendu: YYYY-MM-DD)")
    
    if not row_data.get('client_nom'):
        erreurs.append("Client obligatoire")
    
    if not row_data.get('site_nom'):
        erreurs.append("Site obligatoire")
    
    if not row_data.get('produits'):
        erreurs.append("Au moins un produit obligatoire")
    
    # Validation des choix
    type_nc_valid = [choice[0] for choice in Reclamation.TYPE_NC_CHOICES]
    if row_data.get('type_nc') not in type_nc_valid:
        #print(row_data.get('type_nc'))
        erreurs.append(f"Type NC invalide. Valeurs acceptées: {', '.join(type_nc_valid)}")
    
    imputation_valid = [choice[0] for choice in Reclamation.IMPUTATION_CHOICES]
    if row_data.get('imputation') not in imputation_valid:
        erreurs.append(f"Imputation invalide. Valeurs acceptées: {', '.join(imputation_valid)}")
    
    etat_valid = [choice[0] for choice in Reclamation.ETAT_CHOICES]
    if row_data.get('etat_4d') not in etat_valid:
        erreurs.append(f"État 4D invalide. Valeurs acceptées: {', '.join(etat_valid)}")
    
    if row_data.get('etat_8d') not in etat_valid:
        erreurs.append(f"État 8D invalide. Valeurs acceptées: {', '.join(etat_valid)}")
    
    row_data['erreurs'] = erreurs
    return len(erreurs) == 0

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def recherche_produits(request):
    """Endpoint AJAX pour rechercher des produits"""
    term = request.GET.get('term', '')
    page = int(request.GET.get('page', 1))
    page_size = 20
    
    print(f"Terme recherché: {term}")  # Debug
    
    if term and len(term) >= 2:
        # Recherche par numéro produit OU par désignation
        produits = Produit.objects.filter(
            Q(product_number__icontains=term) |
            Q(designation__icontains=term)
        ).filter(actif=True).order_by('product_number')
    else:
        # Sans recherche, retourner les 20 premiers
        produits = Produit.objects.filter(actif=True).order_by('product_number')[:page_size]
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    produits_page = produits[start:end]
    
    results = [{
        'id': p.id,
        'text': f"{p.product_number} - {p.designation}" if p.designation else p.product_number
    } for p in produits_page]
    
    has_more = produits.count() > end
    
    print(f"Nombre de résultats: {len(results)}")  # Debug
    
    return JsonResponse({
        'results': results,
        'pagination': {
            'more': has_more
        }
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def recherche_produits_ajax(request):
    """Recherche de produits avec pagination via AJAX"""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    # Filtrer les produits
    produits = Produit.objects.all()
    
    # Filtre de recherche
    if search:
        produits = produits.filter(
            Q(product_number__icontains=search) |
            Q(designation__icontains=search)
        )
    
    # Filtre de statut
    if status == 'actif':
        produits = produits.filter(actif=True)
    elif status == 'inactif':
        produits = produits.filter(actif=False)
    
    # Annoter avec le nombre de réclamations
    produits = produits.annotate(
        nb_reclamations=Count('lignes_reclamation')
    ).order_by('product_number')
    
    # Pagination
    paginator = Paginator(produits, per_page)
    produits_page = paginator.get_page(page)
    
    # Préparer les données pour JSON
    products_data = []
    for produit in produits_page:
        products_data.append({
            'id': produit.id,
            'product_number': produit.product_number,
            'designation': produit.designation,
            'actif': produit.actif,
            'nb_reclamations': produit.nb_reclamations,
            'date_creation': produit.date_creation.strftime('%d/%m/%Y')
        })
    
    return JsonResponse({
        'products': products_data,
        'total': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': page,
        'has_next': produits_page.has_next(),
        'has_previous': produits_page.has_previous()
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def api_reclamations_client_mois(request):
    """API pour récupérer les données de réclamations par mois pour un client"""
    client_id = request.GET.get('client_id')
    
    stats = DashboardStats()
    
    if client_id and client_id != 'all':
        data = stats.get_reclamations_par_client_mois(client_id=int(client_id))
    else:
        data = stats.get_reclamations_par_client_mois()
    
    return JsonResponse(data)

#=============8D=============================================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def dashboard_pdca(request):
    """Dashboard centralisé des actions PDCA (basé sur Action8D)
    Optimisé : n'affiche que les actions non réalisées par défaut
    """
    
    # Filtres
    statut = request.GET.get('statut', '')
    type_action = request.GET.get('type_action', '')
    pilote = request.GET.get('pilote', '')
    search = request.GET.get('search', '')
    en_retard_only = request.GET.get('en_retard', '')
    
    # Par défaut, exclure les actions réalisées et abandonnées (sauf si filtre explicite)
    if not statut:
        # Par défaut : seulement les actions en cours ou planifiées
        actions = Action8D.objects.select_related(
            'huitd__reclamation__client',
        ).filter(
            statut__in=['PLANIFIE', 'EN_COURS']
        )
    else:
        actions = Action8D.objects.select_related(
            'huitd__reclamation__client',
        ).all()
    
    # Filtres
    if statut:
        actions = actions.filter(statut=statut)
    if type_action:
        actions = actions.filter(type_action=type_action)
    if pilote:
        actions = actions.filter(pilote__icontains=pilote)
    if search:
        actions = actions.filter(
            Q(action__icontains=search) |
            Q(pilote__icontains=search) |
            Q(verification_efficacite__icontains=search) |
            Q(remarque__icontains=search)
        )
    
    # Actions en retard (date prévue dépassée, non réalisée)
    if en_retard_only:
        actions = actions.filter(
            date_prevue__lt=timezone.now().date(),
            date_realisee__isnull=True
        ).exclude(statut='ABANDONNE')
    
    # Limiter le nombre d'actions affichées (pagination)
    actions = actions.order_by('statut', 'date_prevue')
    
    # Pagination (50 actions par page)
    paginator = Paginator(actions, 50)
    page_number = request.GET.get('page', 1)
    actions_page = paginator.get_page(page_number)
    
    # ========== STATISTIQUES (optimisées) ==========
    # Utiliser des agrégations pour éviter de charger tous les objets
    from django.db.models import Q, Avg, Count, Sum
    
    # Statistiques sur les actions NON réalisées (le cœur du dashboard)
    actions_non_realisees = Action8D.objects.filter(
        statut__in=['PLANIFIE', 'EN_COURS']
    )
    
    stats = {
        'total': actions_non_realisees.count(),
        'planifies': actions_non_realisees.filter(statut='PLANIFIE').count(),
        'en_cours': actions_non_realisees.filter(statut='EN_COURS').count(),
        'realises': Action8D.objects.filter(statut='REALISE').count(),
        'efficaces': Action8D.objects.filter(statut='EFFICACE').count(),
        'abandonnes': Action8D.objects.filter(statut='ABANDONNE').count(),
        'en_retard': actions_non_realisees.filter(
            date_prevue__lt=timezone.now().date(),
            date_realisee__isnull=True
        ).count(),
        'taux_efficacite': 0,
        'taux_avancement_moyen': round(actions_non_realisees.aggregate(
            Avg('avancement'))['avancement__avg'] or 0, 1),
    }
    
    # Taux d'efficacité (uniquement sur les actions réalisées)
    actions_realisees = Action8D.objects.filter(statut='REALISE')
    if actions_realisees.exists():
        efficacite_moyenne = actions_realisees.aggregate(
            avg_efficacite=Avg('efficacite')
        )['avg_efficacite'] or 0
        stats['taux_efficacite'] = efficacite_moyenne
    
    # Regroupement par type (seulement sur les actions non réalisées)
    type_stats = actions_non_realisees.values('type_action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Actions critiques (en retard) - limitées à 20
    actions_critiques = actions_non_realisees.filter(
        date_prevue__lt=timezone.now().date(),
        date_realisee__isnull=True
    )[:20]
    
    # Top pilotes avec le plus d'actions en cours
    top_pilotes = actions_non_realisees.values('pilote').filter(
        pilote__isnull=False,
        pilote__gt=''
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Évolution des actions (dernier mois)
    date_limite = timezone.now() - timedelta(days=30)
    evolution = Action8D.objects.filter(
        date_creation__gte=date_limite
    ).values('date_creation__date').annotate(
        count=Count('id')
    ).order_by('date_creation__date')[:30]
    
    context = {
        'actions': actions_page,  # Page courante (max 50)
        'stats': stats,
        'type_stats': type_stats,
        'actions_critiques': actions_critiques,
        'top_pilotes': top_pilotes,
        'evolution': evolution,
        'statut_choices': Action8D.STATUT_CHOICES,
        'type_choices': Action8D.TYPE_CHOICES,
        'filtres': {
            'statut': statut,
            'type_action': type_action,
            'pilote': pilote,
            'search': search,
            'en_retard': en_retard_only,
        },
        'afficher_historique': request.GET.get('historique', False),
    }
    
    return render(request, 'reclamations/pdca/dashboard.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def pdca_modifier(request, pk):
    """Modifier une action PDCA (Action8D)"""
    action = get_object_or_404(
        Action8D.objects.select_related(
            'huitd__reclamation__client'
        ),
        pk=pk
    )
    
    if request.method == 'POST':
        # Identification
        action.type_action = request.POST.get('type_action', 'CORRECTIVE')
        action.numero_cause = request.POST.get('numero_cause', '')
        action.action = request.POST.get('action', '')
        action.pilote = request.POST.get('pilote', '')
        
        # Planification
        action.date_prevue = request.POST.get('date_prevue') or None
        action.delai_semaines = request.POST.get('delai_semaines', '')
        
        # Suivi
        action.date_realisee = request.POST.get('date_realisee') or None
        
        # Vérification
        action.efficacite = request.POST.get('efficacite', '0')  # ← CORRIGÉ
        action.comment_verification = request.POST.get('comment_verification', '')
        
        # Statut
        action.statut = request.POST.get('statut', 'PLANIFIE')
        action.avancement = 100 if action.statut == 'REALISE' else  int(request.POST.get('avancement', 0))
        # Remarque et déploiement
        action.remarque = request.POST.get('remarque', '')
        action.deploiement = request.POST.get('deploiement', '')
        
        # Si statut passé à REALISE et pas de date, mettre la date du jour
        if action.statut == 'REALISE' and not action.date_realisee:
            action.date_realisee = timezone.now().date()
        
        action.save()
        reclamation = action.huitd.reclamation
        if reclamation.verifier_et_cloturer():
            messages.success(request, "✅ Action mise à jour - Réclamation clôturée automatiquement (toutes les actions sont terminées)")
        else:
            messages.success(request, "✅ Action PDCA mise à jour avec succès !")
        
        return redirect('reclamations:dashboard_pdca')
        return redirect('reclamations:dashboard_pdca')
    
    context = {
        'action': action,
        'statut_choices': Action8D.STATUT_CHOICES,
        'type_choices': Action8D.TYPE_CHOICES,
    }
    return render(request, 'reclamations/pdca/pdca_edit.html', context)

# ====================== CHATBOT VIEWS ======================
 
@login_required
def chatbot_ollama_status(request):
    """Vérifie si Ollama est disponible"""
    try:
        is_connected = ollama_service.test_connection()
        models = ollama_service.list_models() if is_connected else []
       
        return JsonResponse({
            'ollama_available': is_connected,
            'models': models,
            'current_model': ollama_service.model,
            'status': 'OK' if is_connected else 'Ollama non démarré'
        })
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return JsonResponse({
            'ollama_available': False,
            'error': str(e)
        }, status=500)

# API Chatbot 
@login_required
def api_chatbot(request):
    """Endpoint non-streaming (alternative au streaming)"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        historique = data.get('historique', [])
 
        if not user_message:
            return JsonResponse({'error': 'Message vide'}, status=400)
 
        # Utilise Ollama si disponible, sinon fallback
        if ollama_service.test_connection():
            result = ollama_service.get_response(user_message, historique)
            reponse = result.get('reponse', '')
            suggestions = result.get('suggestions', [])
        else:
            reponse = traiter_message_chatbot(user_message, historique)
            suggestions = generer_suggestions(user_message)
 
        return JsonResponse({
            'reponse': reponse,
            'suggestions': suggestions
        })
 
    except Exception as e:
        logger.exception("Error in api_chatbot")
        return JsonResponse({'error': 'Erreur interne'}, status=500)

@login_required
def chat_stream(request):
    """Endpoint principal pour le streaming du chatbot"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        historique = data.get('historique', [])
 
        if not user_message:
            return JsonResponse({'error': 'Message vide'}, status=400)
 
        response = StreamingHttpResponse(
            stream_generator(user_message, historique),
            content_type='text/event-stream',
        )
       
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
       
        return response
 
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    except Exception as e:
        logger.exception("Error in chat_stream")
        return JsonResponse({'error': 'Erreur interne du serveur'}, status=500)
 
def stream_generator(message: str, historique: list) -> Generator:
    """Streaming optimisé - plus rapide et plus naturel"""
    try:
        if ollama_service.test_connection():
            result = ollama_service.get_response(message, historique)
            reponse_complete = result.get('reponse', '')
        else:
            reponse_complete = traiter_message_chatbot(message, historique)
    except Exception as e:
        logger.warning(f"Ollama failed: {e}")
        reponse_complete = traiter_message_chatbot(message, historique)
 
    # Version améliorée : on envoie par mots au lieu de caractère par caractère
    words = reponse_complete.split(' ')
    for i, word in enumerate(words):
        yield (word + ' ').encode('utf-8')
        # Pause variable : plus courte pour les mots courts
        time.sleep(0.1 if len(word) > 8 else 0.04)
 
    # Petit délai final pour que le dernier mot s’affiche bien
    time.sleep(1)
 
def traiter_message_chatbot(message: str, historique: list = None) -> str:
    """Fallback manuel quand Ollama n'est pas disponible"""
    if historique is None:
        historique = []
   
    message_lower = message.lower().strip()
 
    if any(word in message_lower for word in ['bonjour', 'salut', 'coucou', 'hello', 'hi']):
        return "Bonjour ! Je suis votre assistant qualité. Comment puis-je vous aider aujourd'hui ?"
 
    elif any(word in message_lower for word in ['réclamation', 'reclamation']):
        if any(word in message_lower for word in ['créer', 'nouvelle', 'ajouter']):
            return "Pour créer une nouvelle réclamation, cliquez sur 'Nouvelle réclamation' dans le menu. Renseignez le client, le produit et décrivez le problème."
        elif any(word in message_lower for word in ['statut', 'suivi']):
            return "Pour voir le statut d'une réclamation, allez dans 'Liste des réclamations' et recherchez par numéro ou client."
        else:
            return "Les réclamations sont accessibles via le menu 'Réclamations'. Vous pouvez les lister, les filtrer et exporter les données."
 
    elif any(word in message_lower for word in ['délai', 'retard', 'échéance']):
        return "Les échéances et réclamations en retard sont visibles dans l'onglet 'Échéances' du menu principal."
 
    elif 'dashboard' in message_lower or 'tableau' in message_lower or 'kpi' in message_lower:
        return "Le Dashboard affiche les indicateurs clés : nombre de réclamations, taux de clôture, PPM, etc. Accédez-y depuis le menu principal."
 
    elif 'ppm' in message_lower:
        return "Le PPM mesure la qualité fournisseur. Vous pouvez le consulter par client dans la section dédiée.\nObjectif général : < 1000 PPM."
 
    elif any(word in message_lower for word in ['8d', '4d']):
        return "La méthode 8D est utilisée pour résoudre les problèmes qualité. Chaque réclamation importante dispose d'une fiche 8D dédiée."
 
    elif 'aide' in message_lower or 'help' in message_lower:
        return ("Je peux vous aider sur :\n"
                "• Créer ou suivre une réclamation\n"
                "• Consulter le dashboard et les statistiques\n"
                "• Comprendre le PPM et la méthode 8D\n"
                "• Gestion des produits et clients\n\n"
                "Que souhaitez-vous faire ?")
 
    else:
        return ("Je n'ai pas bien compris votre demande.\n\n"
                "Essayez de me parler de :\n"
                "• Réclamations\n"
                "• Dashboard\n"
                "• PPM\n"
                "• 8D\n\n"
                "Ou tapez 'aide'.")
 
def generer_suggestions(message: str) -> list:
    """Génère des suggestions contextuelles pour le frontend"""
    message_lower = message.lower().strip()
   
    if any(k in message_lower for k in ['dashboard', 'statistique', 'kpi']):
        return ['Voir le dashboard', 'Export Excel', 'Graphiques PPM']
   
    elif any(k in message_lower for k in ['réclamation', 'reclamation']):
        return ['Créer une réclamation', 'Liste des réclamations', 'Réclamations en retard']
   
    elif 'ppm' in message_lower:
        return ['PPM par client', 'Tendance PPM', 'Objectifs qualité']
   
    elif any(k in message_lower for k in ['8d', '4d']):
        return ['Voir fiche 8D', 'Modifier états', 'Actions correctives']
   
    else:
        return ['Dashboard', 'Liste des réclamations', 'Créer réclamation', 'Aide']
 
# ====================== CHATBOT SUGGESTIONS ======================
 
# Suggestions that will always be shown to the user (quick start ideas)
CHATBOT_SUGGESTIONS = [
    "Créer une nouvelle réclamation",
    "Liste des réclamations",
    "Consulter le PPM",
    "Réclamations en retard",
    "Comment utiliser la méthode 8D ?",
    "Voir les statistiques qualité",
    "Aide"
]

@login_required
def get_chatbot_suggestions(request):
    """Return static suggestions for the chatbot interface"""
    return JsonResponse({
        'suggestions': CHATBOT_SUGGESTIONS
    })

@login_required
def api_analyse_kpis(request):
    """API pour analyser les KPIs avec IA - déclenchée à la demande"""
    from .dashboard_stats import DashboardStats
    from .services.ai_service import AIService
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        # Récupérer les données
        stats = DashboardStats()
        data = stats.get_all_stats()
        # Récupérer les données de réactivité par UAP
        reactivite_uap_data = data.get('taux_reactivite_par_uap', {})
                # Calculer la moyenne des taux de réactivité par UAP pour l'année courante
        moyenne_reactivite = 0
        annee_courante = timezone.now().year
    
        if reactivite_uap_data and annee_courante in reactivite_uap_data:
            annees_data = reactivite_uap_data.get(annee_courante, {})
            data_mensuelle = annees_data.get('data', {})
            
            # Récupérer tous les taux
            tous_les_taux = []
            for mois, uap_data in data_mensuelle.items():
                for uap, taux in uap_data.items():
                    if taux > 0:  # Ne compter que les UAP avec des données
                        tous_les_taux.append(taux)
            
            # Calculer la moyenne
            if tous_les_taux:
                moyenne_reactivite = sum(tous_les_taux) / len(tous_les_taux)
        
        # Préparer les données pour l'IA
        kpis_data = {
            'total_reclamations': data.get('global', {}).get('total', 0),
            'taux_cloture': data.get('global', {}).get('taux_cloture', 0),
            'taux_reactivite': round(moyenne_reactivite, 1),
            'duree_moyenne': data.get('delai_moyen', 0),
            'ppm_global': data.get('ppm', {}).get('global', 0),
            'nqc_total': data.get('nqc', {}).get('mois', {}).get('total_nqc', 0),
            'top_clients_nqc': data.get('nqc', {}).get('par_client', [])[:5],
            'uap_risque': []
        }
        
        # Analyser avec IA
        ai_service = AIService()
        analyse = ai_service.analyser_kpis(kpis_data)
        
        return JsonResponse(analyse)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'diagnostic': "Erreur d'analyse",
            'actions_prioritaires': [],
            'recommandations': []
        }, status=500)

@login_required
@role_required(['admin', 'quality_manager', 'quality_coordinator'])
def envoyer_notifications(request):
    """Envoyer les notifications groupées"""
    if request.method == 'POST':
        service = NotificationService()
        resultats = service.envoyer_notifications_groupes()
        
        messages.success(
            request, 
            f"{resultats['emails_envoyes']} email(s) envoyé(s) - "
            f"{resultats['notifications_envoyees']} notification(s) de retard, "
            f"{resultats['alertes_envoyees']} alerte(s)"
        )
        return redirect('reclamations:dashboard')
    
    # GET: afficher la confirmation
    notifications_grouped = NotificationService.get_notifications_grouped()
    total_retard = sum(len(data['retard']) for data in notifications_grouped.values())
    total_alerte = sum(len(data['alerte']) for data in notifications_grouped.values())
    
    context = {
        'total_retard': total_retard,
        'total_alerte': total_alerte,
        'destinataires': len(notifications_grouped),
        'notifications_grouped': notifications_grouped
    }
    return render(request, 'reclamations/notifications/confirmation_envoi.html', context)

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

#Gestion des 8d
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_creer(request, reclamation_id):
    """Créer une fiche 8D avec toutes les méthodes initialisées"""
    reclamation = get_object_or_404(Reclamation, pk=reclamation_id)

    if HuitD.objects.filter(reclamation=reclamation).exists():
        huitd = HuitD.objects.get(reclamation=reclamation)
        messages.warning(request, "⚠️ Un 8D existe déjà")
        return redirect('reclamations:huitd_modifier', pk=huitd.id)

    try:
        with transaction.atomic():
            huitd = HuitD.objects.create(
                reclamation=reclamation,
                ref=f"8D-{reclamation.numero_reclamation}",
                date_ouverture=timezone.now().date(),
                client=reclamation.client.nom,
                designation_piece=reclamation.lignes.first().produit.designation if reclamation.lignes.exists() else '',
                decision_8d='OUI',
                etat='EN_COURS'
            )

            # 5W2H
            CinqW2H.objects.create(huitd=huitd)

            # VRS + facteurs
            vrs = VRS.objects.create(huitd=huitd)
            for cat in ['A', 'B', 'C', 'E', 'F']:
                FacteurVRS.objects.create(vrs=vrs, categorie=cat)

            # Facteur Humain + 19 critères
            fh = FacteurHumain.objects.create(huitd=huitd)
            _init_evaluations_fh(fh)

            # 5P par défaut
            CauseCinqP.objects.create(huitd=huitd, type_cause='OCCURRENCE', facteur_prouve='A')
            messages.success(request, f"✅ Fiche 8D créée pour {reclamation.numero_reclamation}")
            return redirect('reclamations:huitd_modifier', pk=huitd.id)

    except Exception as e:
        messages.error(request, f"❌ Erreur : {str(e)}")
        return redirect('reclamations:detail_reclamation', pk=reclamation.id)

def _init_evaluations_fh(fh):
    """Initialise les 19 critères du facteur humain"""
    criteres = [
        ('1', '1.1', '1.1 Are the references worked on the same as those previously planned?'),
        ('1', '1.2', '1.2 Are the tools used those requested in the GP/FI?'),
        ('1', '1.3', '1.3 Is there a problem caused by a defective tool?'),
        ('1', '1.4', '1.4 Are there any blind operations not described in the GP/FI?'),
        ('1', '1.5', '1.5 Are there any components handled that represent quality problems?'),
        ('2', '2.1', '2.1 Are temperature, lighting, noise and cleaning appropriate?'),
        ('2', '2.2', '2.2 Are the PPE suitable for the job?'),
        ('2', '2.3', '2.3 Is the layout adequate for all the operations?'),
        ('2', '2.4', '2.4 Does the operator encounter any ergonomic problems?'),
        ('2', '2.5', '2.5 Is the flow of incoming and outgoing parts well defined?'),
        ('3', '3.1', '3.1 Is the operator overloaded?'),
        ('3', '3.2', '3.2 Is the operator stressed?'),
        ('3', '3.3', '3.3 Is the operator motivated?'),
        ('3', '3.4', '3.4 Is the operator tired?'),
        ('3', '3.5', '3.5 Is the operator in good health?'),
        ('3', '3.6', '3.6 Is the operator suitable for this job?'),
        ('3', '3.7', '3.7 Has the operator worked last 6 months in this position?'),
        ('3', '3.8', '3.8 Is the operator aware of the consequences of this error?'),
        ('3', '3.9', '3.9 Does the operator have any other problems?'),
    ]
    for cat, num, critere in criteres:
        EvaluationFacteurHumain.objects.create(
            facteur_humain=fh, categorie=cat, numero_critere=num, critere=critere
        )

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_detail(request, pk):
    """Afficher la fiche 8D"""
    huitd = get_object_or_404(
        HuitD.objects.select_related(
            'reclamation__client', 'cinq_w2h', 'vrs', 'facteur_humain'
        ).prefetch_related(
            'participants', 'causes_ishikawa', 'vrs__facteurs',
            'causes_5p', 'facteur_humain__evaluations',
            'actions', 'alterations', 'evidences',
        ),
        pk=pk
    )
    return render(request, 'reclamations/huitd/huitd_detail.html', {'huitd': huitd})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_modifier(request, pk):
    """Modifier la fiche 8D - dispatch selon section"""
    huitd = get_object_or_404(
        HuitD.objects.select_related('cinq_w2h', 'vrs', 'facteur_humain').prefetch_related(
            'participants', 'causes_ishikawa', 'vrs__facteurs',
            'causes_5p', 'facteur_humain__evaluations', 'actions', 'alterations','evidences'
        ),
        pk=pk
    )

    if request.method == 'POST':
        section = request.POST.get('section', '')

        try:
            with transaction.atomic():
                if section == 'general': return _save_general(request, huitd)
                if section == 'd1': return _save_d1(request, huitd)
                if section == 'd2': return _save_d2(request, huitd)
                if section == 'd3': return _save_d3(request, huitd)
                if section == 'd4': return _save_d4(request, huitd)
                if section == 'd5': return _save_d5(request, huitd)
                if section == 'd6': return _save_d6(request, huitd)
                if section == 'd7': return _save_d7(request, huitd)
                if section == 'd8': return _save_d8(request, huitd)
                if section == 'decision': return _save_decision(request, huitd)
                if section == '5w2h': return _save_5w2h(request, huitd)
                if section == 'ishikawa': return _save_ishikawa(request, huitd)
                if section == 'vrs': return _save_vrs(request, huitd)
                if section == '5p': return _save_5p(request, huitd)
                if section == 'fh': return _save_fh(request, huitd)
                if section == 'evidences': 
                    return _save_evidences(request, huitd)

        except Exception as e:
            messages.error(request, f"❌ Erreur : {str(e)}")
            import traceback
            traceback.print_exc()

    # Préparer les choix pour les rôles
    role_choices = Participant8D.ROLE_CHOICES
    vrs_data = []
    if huitd.vrs:
        for f in huitd.vrs.facteurs.all():
            vrs_data.append({
                'id': f.id,
                'categorie': f.categorie,
                'facteur_probable': f.facteur_probable,
                'parametre_mesurable': f.parametre_mesurable,
                'standard_exigence': f.standard_exigence,
                'donnees_bonnes': f.donnees_bonnes,
                'donnees_mauvaises': f.donnees_mauvaises,
                'standard_suivi': f.standard_suivi,
                'standard_approprie': f.standard_approprie,
                'lien_prouve': f.lien_prouve,
                'facteur_prouve': f.facteur_prouve,
                  })
    
    context = {
        'huitd': huitd,
        'role_choices': role_choices,
        'vrs_data': json.dumps(vrs_data),
    }

    return render(request, 'reclamations/huitd/huitd_formulaire.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_supprimer_evidence(request, pk):
    evidence = get_object_or_404(Evidence8D, pk=pk)
    huitd_id = evidence.huitd.id
    evidence.delete()
    messages.success(request, "✅ Évidence supprimée")
    return redirect('reclamations:huitd_modifier', pk=huitd_id)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def qualite_dashboard(request):
    """
    Dashboard pour l'équipe Qualité Produit
    Affiche les réclamations ouvertes sans 8D
    """
    # Réclamations ouvertes SANS 8D
    reclamations_sans_8d = Reclamation.objects.filter(
        cloture=False,
        huitd_non_applicable=False
    ).exclude(
        huitd__isnull=False
    ).select_related(
        'client', 'programme', 'site_client'
    ).prefetch_related(
        'lignes__produit',
        'lignes__non_conformites'
    ).order_by('-date_reclamation')
    
    # Réclamations ouvertes AVEC 8D en cours
    reclamations_avec_8d = Reclamation.objects.filter(
        cloture=False,
        huitd__isnull=False,
        huitd_non_applicable=False
    ).exclude(
        huitd__etat='CLOTURE'
    ).select_related(
        'client', 'huitd'
    ).order_by('-date_reclamation')
    
    # Réclamations ouvertes marquées 8D non applicable
    reclamations_na_8d = Reclamation.objects.filter(
        cloture=False,
        huitd_non_applicable=True
    ).select_related('client').order_by('-date_reclamation')[:15]
    # Statistiques
    stats = {
        'total_ouvertes': Reclamation.objects.filter(cloture=False).count(),
        'sans_8d': reclamations_sans_8d.count(),
        'avec_8d': reclamations_avec_8d.count(),
        'na_8d': Reclamation.objects.filter(cloture=False, huitd_non_applicable=True).count(),
    }
    
    context = {
        'reclamations_sans_8d': reclamations_sans_8d,
        'reclamations_avec_8d': reclamations_avec_8d,
        'reclamations_na_8d': reclamations_na_8d,
        'stats': stats,
    }
    return render(request, 'reclamations/qualite/dashboard.html', context)

@login_required
def marquer_8d_non_applicable(request, pk):
    """Marque une réclamation comme 8D non applicable"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    reclamation.huitd_non_applicable = True
     # Passer l'état 8D à CLOTURE
    reclamation.etat_8d = 'CLOTURE'
    
    # Si une date de clôture est nécessaire
    if not reclamation.date_cloture_8d:
        reclamation.date_cloture_8d = timezone.now().date()
    reclamation.save()
    
    messages.success(request, f"✅ La réclamation {reclamation.numero_reclamation} a été marquée comme 8D non applicable et l'état 8D est passé à CLOTURE.")
    return redirect('reclamations:qualite_dashboard')

@login_required
def annuler_8d_non_applicable(request, pk):
    """Annule la mention 8D non applicable"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    reclamation.huitd_non_applicable = False
    # Remettre l'état 8D à OUVERT (ou EN_COURS selon votre besoin)
    reclamation.etat_8d = 'EN_COURS'
    
    # Effacer la date de clôture
    reclamation.date_cloture_8d = None
    reclamation.save()
    
    messages.success(request, f"✅ La mention 8D non applicable a été annulée pour {reclamation.numero_reclamation}. Un 8D est maintenant requis.")
    return redirect('reclamations:qualite_dashboard')

def _save_general(request, huitd):
    huitd.numero_of = request.POST.get('numero_of', '')
    huitd.date_ouverture = request.POST.get('date_ouverture') or None
    huitd.designation_piece = request.POST.get('designation_piece', '')
    huitd.numero_article = request.POST.get('numero_article', '')
    huitd.numero_nc = request.POST.get('numero_nc', '')
    huitd.client = request.POST.get('client', '')
    huitd.lieu_detection = request.POST.get('lieu_detection', 'QUALITE')
    huitd.interne = request.POST.get('interne', '')
    huitd.etat = request.POST.get('huitd_etat')
    huitd.numero_8d = request.POST.get('numero_8d', '')
    huitd.save()
    messages.success(request, "✅ Infos générales enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d1(request, huitd):
    """Sauvegarde la section D1 - 5W2H avec gestion des images"""
    
    # Sauvegarde des champs texte D1
    huitd.d1_qui = request.POST.get('d1_qui', '')
    huitd.d1_quoi = request.POST.get('d1_quoi', '')
    huitd.d1_ou = request.POST.get('d1_ou', '')
    huitd.d1_quand = request.POST.get('d1_quand', '')
    huitd.d1_comment = request.POST.get('d1_comment', '')
    huitd.d1_combien = request.POST.get('d1_combien', '')
    huitd.d1_pourquoi = request.POST.get('d1_pourquoi', '')
    huitd.d1_caracterisation = request.POST.get('d1_caracterisation', '')
    huitd.d1_probleme_connu = request.POST.get('d1_probleme_connu') == 'on'
    huitd.d1_risque = request.POST.get('d1_risque') == 'on'
    huitd.d1_risque_detail = request.POST.get('d1_risque_detail', '')
    
    # ========== GESTION DES IMAGES ==========
    
    # Vérifier si l'utilateur veut supprimer l'image défectueuse
    if request.POST.get('supprimer_defectueux') == '1':
        if huitd.d1_illustration_defectueux:
            # Supprimer le fichier physique
            if os.path.isfile(huitd.d1_illustration_defectueux.path):
                os.remove(huitd.d1_illustration_defectueux.path)
            huitd.d1_illustration_defectueux = None
    
    # Vérifier si l'utilisateur veut supprimer l'image conforme
    if request.POST.get('supprimer_conforme') == '1':
        if huitd.d1_illustration_conforme:
            # Supprimer le fichier physique
            if os.path.isfile(huitd.d1_illustration_conforme.path):
                os.remove(huitd.d1_illustration_conforme.path)
            huitd.d1_illustration_conforme = None
    
    # Gérer la nouvelle image défectueuse (remplace l'ancienne si existante)
    if 'illustration_defectueux' in request.FILES:
        # Supprimer l'ancienne image si elle existe
        if huitd.d1_illustration_defectueux and not request.POST.get('supprimer_defectueux'):
            if os.path.isfile(huitd.d1_illustration_defectueux.path):
                os.remove(huitd.d1_illustration_defectueux.path)
        huitd.d1_illustration_defectueux = request.FILES['illustration_defectueux']
    
    # Gérer la nouvelle image conforme
    if 'illustration_conforme' in request.FILES:
        # Supprimer l'ancienne image si elle existe
        if huitd.d1_illustration_conforme and not request.POST.get('supprimer_conforme'):
            if os.path.isfile(huitd.d1_illustration_conforme.path):
                os.remove(huitd.d1_illustration_conforme.path)
        huitd.d1_illustration_conforme = request.FILES['illustration_conforme']
    
    huitd.save()
    
    messages.success(request, "✅ D1 - 5W2H enregistré avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d2(request, huitd):
    huitd.d2_date = request.POST.get('d2_date') or None
    huitd.d2_actions = request.POST.get('d2_actions', '')
    huitd.d2_tri = request.POST.get('d2_tri') == 'oui'
    huitd.d2_of_concernes = request.POST.get('of_concernes', '')
    huitd.d2_quantite_rebutee = request.POST.get('quantite_rebutee', 'N/A')
    huitd.d2_quantite_retoucher = request.POST.get('quantite_retoucher', 'N/A')
    huitd.save()
    messages.success(request, "✅ D2 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d3(request, huitd):
    """Sauvegarde la section D3 - Équipe 8D avec participants"""
    
    # Sauvegarde des champs D3 existants dans HuitD
    huitd.d3_date = request.POST.get('d3_date') or None
    huitd.pilote = request.POST.get('pilote', '')
    huitd.pilote_fonction = request.POST.get('pilote_fonction', '')
    huitd.animateur = request.POST.get('animateur', '')
    huitd.animateur_fonction = request.POST.get('animateur_fonction', '')
    huitd.save()
    
    # ========== GESTION DES PARTICIPANTS (uniquement les participants supplémentaires) ==========
    # Récupérer toutes les données des participants
    participant_ids = request.POST.getlist('participant_id[]')
    participant_noms = request.POST.getlist('participant_nom[]')
    participant_fonctions = request.POST.getlist('participant_fonction[]')
    participant_ordres = request.POST.getlist('participant_ordre[]')
    
    participants_a_conserver = []
    
    # Parcourir tous les participants
    for i in range(len(participant_noms)):
        nom = participant_noms[i].strip()
        if not nom:  # Ignorer les lignes vides
            continue
        
        fonction = participant_fonctions[i] if i < len(participant_fonctions) else ''
        ordre = int(participant_ordres[i]) if i < len(participant_ordres) and participant_ordres[i].isdigit() else i + 1
        participant_id = participant_ids[i] if i < len(participant_ids) else ''
        
        # Vérifier si c'est un participant existant ou nouveau
        if participant_id and participant_id != '' and participant_id.isdigit():
            # Modifier participant existant
            try:
                participant = Participant8D.objects.get(id=int(participant_id), huitd=huitd)
                participant.nom = nom
                participant.fonction = fonction
                participant.ordre = ordre
                participant.save()
                participants_a_conserver.append(participant.id)
            except Participant8D.DoesNotExist:
                # Créer nouveau participant
                participant = Participant8D.objects.create(
                    huitd=huitd,
                    nom=nom,
                    fonction=fonction,
                    ordre=ordre
                )
                participants_a_conserver.append(participant.id)
        elif participant_id and participant_id.startswith('new_'):
            # Créer nouveau participant
            participant = Participant8D.objects.create(
                huitd=huitd,
                nom=nom,
                fonction=fonction,
                ordre=ordre
            )
            participants_a_conserver.append(participant.id)
    
    # Supprimer les participants qui ne sont plus dans la liste
    if participants_a_conserver:
        huitd.participants.exclude(id__in=participants_a_conserver).delete()
    else:
        huitd.participants.all().delete()
    
    messages.success(request, "✅ D3 - Équipe 8D enregistrée avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d4(request, huitd):
    huitd.d4_date = request.POST.get('d4_date') or None
    huitd.d4_causes_apparition = request.POST.get('d4_causes_apparition', '')
    huitd.d4_causes_non_detection = request.POST.get('d4_causes_non_detection', '')
    huitd.decision_8d = request.POST.get('decision_8d', 'OUI')
    huitd.save()
    messages.success(request, "✅ D4 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d5(request, huitd):
    huitd.d5_causes_occurrence = request.POST.get('d5_causes_occurrence', "voir ishikawa et 5W2H see / Ishikawa and 5W2H")
    huitd.d5_causes_non_detection = request.POST.get('d5_causes_non_detection', "voir ishikawa et 5W2H / see Ishikawa and 5W2H")
    huitd.save()
    messages.success(request, "✅ D5 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d6(request, huitd):
    """Sauvegarde D6 - Plan d'actions et vérification clôture"""
    huitd.actions.all().delete()

    types_action = request.POST.getlist('action_type[]')
    causes = request.POST.getlist('action_cause[]')
    actions = request.POST.getlist('action_desc[]')
    pilotes = request.POST.getlist('action_pilote[]')
    dates_prevues = request.POST.getlist('action_date_prevue[]')
    delai_semaines = request.POST.getlist('action_delai[]')
    statuts = request.POST.getlist('action_statut[]')
    
    for i in range(len(actions)):
        if actions[i].strip():
            Action8D.objects.create(
                huitd=huitd,
                type_action=types_action[i] if i < len(types_action) else 'CORRECTIVE',
                numero_cause=causes[i] if i < len(causes) else '',
                action=actions[i],
                pilote=pilotes[i] if i < len(pilotes) else '',
                delai_semaines=delai_semaines[i] if i < len(delai_semaines) else '',
                statut=statuts[i] if i < len(statuts) else 'PLANIFIE',
                ordre=i+1
            )
    
    # Vérifier si la réclamation peut être clôturée
    reclamation = huitd.reclamation
    if reclamation.verifier_et_cloturer():
        messages.success(request, "✅ D6 enregistré - Réclamation clôturée automatiquement (toutes les actions sont terminées)")
    else:
        messages.success(request, "✅ D6 enregistré")
    
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d7(request, huitd):
    huitd.d7_verification = request.POST.get('d7_verification', '')
    huitd.d7_suffisant = request.POST.get('d7_suffisant', '')
    huitd.save()
    messages.success(request, "✅ D7 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d8(request, huitd):
    huitd.d8_transversalisation = request.POST.get('transversalisation', '')
    huitd.save()
    huitd.alterations.all().delete()
    docs = ['Inspection Sheet (PV)','Control Plan','Instruction Sheet (FI)','Maintenance Plan','Audit Frequency','Workstation Documents Updated','Process Improvement','PFMEA','Standardization of Tools and Equipment','Training Plan','Deploy to Similar Products/Processes (Other Program)','Deploy to Similar Products/Processes (Other APU)']
    for i, doc in enumerate(docs):
        r = request.POST.get(f'alt_remark_{i}', '')
        p = request.POST.get(f'alt_pilote_{i}', '')
        d = request.POST.get(f'alt_deadline_{i}') or None
        if r or p or d:
            Alteration8D.objects.create(huitd=huitd, type_document=doc, remarque=r, pilote=p, deadline=d, ordre=i+1)
    messages.success(request, "✅ D8 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_decision(request, huitd):
    huitd.huitd_accepte = request.POST.get('huitd_accepte') == 'oui'
    huitd.decision_hcim = request.POST.get('decision_hcim', '')
    huitd.fin_huitd = request.POST.get('fin_huitd') or None
    huitd.fin_huitd_signature = request.POST.get('fin_huitd_signature', '')
    huitd.save()
    messages.success(request, "✅ Décision enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_5w2h(request, huitd):
    w = huitd.cinq_w2h
    w.c_what_happened = request.POST.get('c_what_happened', '')
    w.c_who_detected = request.POST.get('c_who_detected', '')
    w.c_where_detected = request.POST.get('c_where_detected', '')
    w.c_when_detected = request.POST.get('c_when_detected', '')
    w.c_how_detected = request.POST.get('c_how_detected', '')
    w.c_how_many = request.POST.get('c_how_many', '')
    w.c_why_problem = request.POST.get('c_why_problem', '')
    w.c_logistic_impact = request.POST.get('c_logistic_impact', '')
    w.c_other_customers_delivered = request.POST.get('c_other_customers_delivered', '')
    w.c_other_customers_defect = request.POST.get('c_other_customers_defect', '')
    w.h_symptoms = request.POST.get('h_symptoms', '')
    w.h_defects_ruled_out = request.POST.get('h_defects_ruled_out', '')
    w.h_where_created = request.POST.get('h_where_created', '')
    w.h_when_generated = request.POST.get('h_when_generated', '')
    w.h_rework = request.POST.get('h_rework', '')
    w.h_detection_expected = request.POST.get('h_detection_expected', '')
    w.h_reinjection = request.POST.get('h_reinjection', '')
    w.h_known_problem = request.POST.get('h_known_problem', '')
    w.h_last_reported = request.POST.get('h_last_reported', '')
    w.save()
    messages.success(request, "✅ 5W2H enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_ishikawa(request, huitd):
    huitd.causes_ishikawa.all().delete()
    for cat in ['A','B','C','D','E','F']:
        causes = request.POST.getlist(f'ishikawa_{cat}_cause[]')
        for i, cause in enumerate(causes):
            if cause.strip():
                type_key = f'ishikawa_{cat}_type_{i}'
                type_cause = request.POST.get(type_key, 'OCCURRENCE')
                CauseIshikawa.objects.create(huitd=huitd, categorie=cat, cause=cause, type_cause=type_cause, ordre=i+1)
    messages.success(request, "✅ Ishikawa enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_vrs(request, huitd):
    """Sauvegarde du tableau VRS avec index numériques"""
    
    # Récupérer ou créer le VRS
    vrs, created = VRS.objects.get_or_create(huitd=huitd)
    
    # Supprimer toutes les anciennes entrées
    vrs.facteurs.all().delete()
    
    # Trouver tous les indices
    import re
    indices = set()
    for key in request.POST.keys():
        match = re.search(r'vrs_categorie_(\d+)', key)
        if match:
            indices.add(int(match.group(1)))
    
    # Ordre par catégorie
    ordre_par_categorie = {}
    
    for idx in sorted(indices):
        categorie = request.POST.get(f'vrs_categorie_{idx}', '')
        if not categorie or categorie == 'D':
            continue
        
        if categorie not in ordre_par_categorie:
            ordre_par_categorie[categorie] = 1
        
        FacteurVRS.objects.create(
            vrs=vrs,
            categorie=categorie,
            facteur_probable=request.POST.get(f'vrs_facteur_{idx}', ''),
            parametre_mesurable=request.POST.get(f'vrs_parametre_{idx}', ''),
            standard_exigence=request.POST.get(f'vrs_standard_{idx}', ''),
            donnees_bonnes=request.POST.get(f'vrs_bonnes_{idx}', ''),
            donnees_mauvaises=request.POST.get(f'vrs_mauvaises_{idx}', ''),
            standard_suivi=request.POST.get(f'vrs_suivi_{idx}') == '1',
            standard_approprie=request.POST.get(f'vrs_appro_{idx}') == '1',
            lien_prouve=request.POST.get(f'vrs_lien_{idx}') == '1',
            facteur_prouve=request.POST.get(f'vrs_prouve_{idx}') == '1',
            ordre=ordre_par_categorie[categorie]
        )
        
        ordre_par_categorie[categorie] += 1
    
    messages.success(request, "✅ VRS enregistré avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_5p(request, huitd):
    huitd.causes_5p.all().delete()
    types_cause = request.POST.getlist('5p_type[]')
    facteurs = request.POST.getlist('5p_facteur[]')
    p1s = request.POST.getlist('5p_p1[]')
    p2s = request.POST.getlist('5p_p2[]')
    p3s = request.POST.getlist('5p_p3[]')
    p4s = request.POST.getlist('5p_p4[]')
    p5s = request.POST.getlist('5p_p5[]')
    for i in range(len(types_cause)):
        if any([p1s[i].strip() if i < len(p1s) else '', p2s[i].strip() if i < len(p2s) else '', p3s[i].strip() if i < len(p3s) else '', p4s[i].strip() if i < len(p4s) else '', p5s[i].strip() if i < len(p5s) else '']):
            CauseCinqP.objects.create(
                huitd=huitd,
                type_cause=types_cause[i] if i < len(types_cause) else 'OCCURRENCE',
                facteur_prouve=facteurs[i] if i < len(facteurs) else '',
                pourquoi_1=p1s[i] if i < len(p1s) else '',
                pourquoi_2=p2s[i] if i < len(p2s) else '',
                pourquoi_3=p3s[i] if i < len(p3s) else '',
                pourquoi_4=p4s[i] if i < len(p4s) else '',
                pourquoi_5=p5s[i] if i < len(p5s) else '',
            )
    messages.success(request, "✅ 5P enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_fh(request, huitd):
    for ev in huitd.facteur_humain.evaluations.all():
        key = f'fh_eval_{ev.categorie}_{ev.numero_critere}'
        ev.evaluation = request.POST.get(key, '')
        ev.commentaire = request.POST.get(f'{key}_comment', '')
        ev.save()
    messages.success(request, "✅ Facteur Humain enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_evidences(request, huitd):
    """Sauvegarde la section des évidences"""
    
    # Récupérer toutes les données des évidences
    evidence_ids = request.POST.getlist('evidence_id[]')
    evidence_titres = request.POST.getlist('evidence_titre[]')
    evidence_descriptions = request.POST.getlist('evidence_description[]')
    evidence_fichiers = request.FILES.getlist('evidence_fichier[]')
    evidence_supprimer_fichier = request.POST.getlist('evidence_supprimer_fichier[]')
    
    evidences_a_conserver = []
    
    # Traiter les évidences existantes et nouvelles
    for i in range(len(evidence_titres)):
        titre = evidence_titres[i].strip()
        if not titre:
            continue
        
        description = evidence_descriptions[i] if i < len(evidence_descriptions) else ''
        evidence_id = evidence_ids[i] if i < len(evidence_ids) else ''
        fichier = evidence_fichiers[i] if i < len(evidence_fichiers) else None
        
        # Vérifier si l'utilisateur veut supprimer le fichier
        supprimer_fichier = False
        if i < len(evidence_supprimer_fichier):
            supprimer_fichier = evidence_supprimer_fichier[i] == '1'
        
        if evidence_id and evidence_id != '' and evidence_id.isdigit():
            # Modifier évidence existante
            try:
                evidence = Evidence8D.objects.get(id=int(evidence_id), huitd=huitd)
                evidence.titre = titre
                evidence.description = description
                
                # Supprimer l'ancien fichier si demandé
                if supprimer_fichier and evidence.fichier:
                    if os.path.isfile(evidence.fichier.path):
                        os.remove(evidence.fichier.path)
                    evidence.fichier = None
                
                # Remplacer le fichier si nouveau fourni
                if fichier:
                    if evidence.fichier and os.path.isfile(evidence.fichier.path):
                        os.remove(evidence.fichier.path)
                    evidence.fichier = fichier
                
                evidence.save()
                evidences_a_conserver.append(evidence.id)
            except Evidence8D.DoesNotExist:
                # Créer nouvelle évidence (cas rare)
                evidence = Evidence8D.objects.create(
                    huitd=huitd,
                    titre=titre,
                    description=description,
                    fichier=fichier if fichier else None
                )
                evidences_a_conserver.append(evidence.id)
        else:
            # Créer nouvelle évidence
            if not fichier:
                continue  # Une nouvelle évidence doit avoir un fichier
            evidence = Evidence8D.objects.create(
                huitd=huitd,
                titre=titre,
                description=description,
                fichier=fichier
            )
            evidences_a_conserver.append(evidence.id)
    
    # Supprimer les évidences qui ne sont plus dans la liste
    if evidences_a_conserver:
        # Supprimer physiquement les fichiers des évidences supprimées
        for evidence in huitd.evidences.exclude(id__in=evidences_a_conserver):
            if evidence.fichier and os.path.isfile(evidence.fichier.path):
                os.remove(evidence.fichier.path)
        huitd.evidences.exclude(id__in=evidences_a_conserver).delete()
    else:
        # Supprimer toutes les évidences
        for evidence in huitd.evidences.all():
            if evidence.fichier and os.path.isfile(evidence.fichier.path):
                os.remove(evidence.fichier.path)
        huitd.evidences.all().delete()
    
    # ========== CLÔTURE DU 8D ==========
    # Vérifier si le 8D a au moins une évidence
    if huitd.evidences.exists():
        # Changer l'état du 8D en CLOTURE
        huitd.etat = 'CLOTURE'
        huitd.fin_huitd = timezone.now().date()
        huitd.save()
        messages.success(request, "✅ Évidences enregistrées et 8D clôturé avec succès!")
    else:
        # Si plus d'évidence, on remet l'état à EN_COURS
        if huitd.etat == 'CLOTURE':
            huitd.etat = 'EN_COURS'
            huitd.fin_huitd = None
            huitd.save()
        messages.success(request, "✅ Évidences enregistrées avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)