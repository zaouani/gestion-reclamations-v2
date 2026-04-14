from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import logging
from django.utils import timezone
from .models import (Reclamation, Client, Produit, LigneReclamation, NonConformite, UAP, Site, ObjectifsAnnuel, Programme, SiteClient, Livraison, HuitD, OrdreFabrication, LigneOF, AlerteFAI)
from django.http import JsonResponse
from django.db.models import Count, Q, F, Avg, Sum, Prefetch
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
from .services.fai_alert_service import FAIAlertService
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from urllib.parse import unquote


# CONFIGURATION LOGGER
logger = logging.getLogger(__name__)
ollama_service = OllamaService(model="phi3:mini") 
moyenne_reactivite=100 
ollama_service = OllamaService(model="llama3.2:3b")

# ================ EXPORT PDF  ================
@login_required
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
def detail_recurrence_produit(request, product_id):
    """Détail de la récurrence pour un produit spécifique"""
    from django.db import models
    
    produit = get_object_or_404(Produit, pk=product_id)
    
    # Récupérer toutes les lignes de réclamation pour ce produit
    lignes = LigneReclamation.objects.filter(
        produit=produit
    ).select_related(
        'reclamation', 
        'reclamation__client', 
        'uap_concernee'
    ).order_by('-reclamation__date_reclamation')
    
    # Nombre de réclamations distinctes
    nb_reclamations = lignes.values('reclamation').distinct().count()
    
    # Analyser les descriptions de non-conformité
    descriptions = lignes.values('description_non_conformite').annotate(
        nb_occurences=models.Count('id'),
        quantite_totale=models.Sum('quantite')
    ).order_by('-nb_occurences')
    
    defauts_data = []
    for desc in descriptions:
        if nb_reclamations > 0:
            taux = (desc['nb_occurences'] / nb_reclamations) * 100
        else:
            taux = 0
        
        defauts_data.append({
            'description': desc['description_non_conformite'] or "Non spécifié",
            'nb_occurences': desc['nb_occurences'],
            'quantite_totale': desc['quantite_totale'] or 0,
            'taux': round(taux, 2)
        })
    
    context = {
        'produit': produit,
        'nb_reclamations': nb_reclamations,
        'defauts': defauts_data,
        'lignes': lignes[:20],  # Dernières 20 réclamations
    }
    
    return render(request, 'reclamations/produit/recurrence_detail.html', context)

@login_required
def taux_recurrence_nc(request):
    """
    Calcule le taux de récurrence des descriptions de non-conformité (NC)
    Taux de récurrence = Nombre de réclamations contenant au moins un produit avec le défaut / Nombre total de réclamations
    UNIQUEMENT pour les réclamations avec imputation CIM
    """
    
    # Total des réclamations CIM (dénominateur)
    total_reclamations_cim = Reclamation.objects.filter(
        imputation='CIM'
    ).count()
    
    # Récupérer toutes les descriptions de NC distinctes pour les CIM
    descriptions = NonConformite.objects.filter(
        ligne_reclamation__reclamation__imputation='CIM'
    ).values('description').annotate(
        nb_occurences=Count('id'),  # Nombre total d'occurrences de la NC
        quantite_totale=Sum('quantite'),  # Quantité totale concernée
        nb_produits=Count('ligne_reclamation__produit', distinct=True),  # Nombre de produits différents
        # Nouveau : nombre de réclamations DISTINCTES contenant cette NC
        nb_reclamations_concernees=Count('ligne_reclamation__reclamation', distinct=True)
    ).filter(
        description__isnull=False
    ).exclude(
        description=''
    ).order_by('-nb_reclamations_concernees')  # Tri par nombre de réclamations concernées
    
    resultats = []
    for desc in descriptions:
        description = desc['description']
        nb_reclamations_concernees = desc['nb_reclamations_concernees']
        
        # Calcul du taux de récurrence selon la nouvelle définition
        # Taux = (réclamations avec le défaut / total réclamations) * 100
        taux = (nb_reclamations_concernees / total_reclamations_cim * 100) if total_reclamations_cim > 0 else 0
        
        # Produits concernés (uniquement pour les CIM)
        produits_concernes = Produit.objects.filter(
            lignes_reclamation__non_conformites__description=description,
            lignes_reclamation__reclamation__imputation='CIM'
        ).distinct().values_list('product_number', flat=True)[:10]
        
        # Récupérer les IDs des réclamations concernées (pour référence)
        reclamations_ids = NonConformite.objects.filter(
            description=description,
            ligne_reclamation__reclamation__imputation='CIM'
        ).values_list('ligne_reclamation__reclamation_id', flat=True).distinct()
        
        resultats.append({
            'description': description,
            'nb_occurences': desc['nb_occurences'],  # Nombre total d'occurrences
            'quantite_totale': desc['quantite_totale'] or 0,
            'nb_produits': desc['nb_produits'],
            'nb_reclamations': nb_reclamations_concernees,  # Nombre de réclamations distinctes
            'taux_recurrence': round(taux, 2),
            'produits_concernes': list(produits_concernes),
            'reclamations_ids': list(reclamations_ids)  # Pour des liens éventuels
        })
    
    # Statistiques globales
    total_nc_distinctes = len(resultats)
    total_occurences_nc = sum(r['nb_occurences'] for r in resultats)
    
    context = {
        'descriptions': resultats,
        'total_reclamations_cim': total_reclamations_cim,
        'total_nc_distinctes': total_nc_distinctes,
        'total_occurences_nc': total_occurences_nc,
        'date_analyse': timezone.now(),
        'filtre_imputation': 'CIM'
    }
    
    return render(request, 'reclamations/produit/recurrence_nc.html', context)

@login_required
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
    
    # Formater les lignes pour l'affichage
    lignes_data = []
    for nc in non_conformites[:50]:
        reclamation = nc.ligne_reclamation.reclamation
        lignes_data.append({
            'reclamation': reclamation,
            'produit': nc.ligne_reclamation.produit,
            'quantite': nc.quantite,
            'description_nc': nc.description,
            'uap_concernee': nc.ligne_reclamation.uap_concernee,
            'commentaire': nc.ligne_reclamation.commentaire
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
        'filtre_imputation': 'CIM'
    }
    
    return render(request, 'reclamations/produit/detail_recurrence_nc.html', context)

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

# ================ GESTION DES RECLAMATIONS ================
@login_required
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
                etat_4d='OUVERT',
                etat_8d='OUVERT',
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
def detail_reclamation(request, pk):
    """Voir le détail d'une réclamation"""
    reclamation = get_object_or_404(
        Reclamation.objects.prefetch_related(
            'lignes__produit', 
            'lignes__site',
            'lignes__uap_concernee'
        ).select_related(
            'client',      # Client
            'programme',   # Programme
            'createur'     # Créateur
        ),
        pk=pk
    )
    return render(request, 'reclamations/detail.html', {'reclamation': reclamation})

@login_required
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
def ajouter_ligne(request, pk):
    """Ajouter une ligne à une réclamation existante"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    if request.method == 'POST':
        produit_id = request.POST.get('produit')
        quantite = request.POST.get('quantite')
        
        if produit_id and quantite:
            LigneReclamation.objects.create(
                reclamation=reclamation,
                produit_id=produit_id,
                quantite=quantite,
                description_non_conformite=request.POST.get('description', ''),
                commentaire=request.POST.get('commentaire', ''),
                temps_rework=request.POST.get('temps_rework') or None
            )
            messages.success(request, "Ligne ajoutée avec succès!")
        
        return redirect('reclamations:detail_reclamation', pk=reclamation.id)
    
    context = {
        'reclamation': reclamation,
        'produits': Produit.objects.filter(actif=True),
    }
    return render(request, 'reclamations/ajouter_ligne.html', context)

@login_required
def modifier_reclamation(request, pk):
    """Modifier une réclamation complète avec gestion des multiples NC"""
    reclamation = get_object_or_404(
        Reclamation.objects.prefetch_related(
            'lignes__produit', 
            'lignes__uap_concernee',
            'lignes__non_conformites'
        ),
        pk=pk
    )
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Mettre à jour les champs de la réclamation
                reclamation.numero_reclamation = request.POST.get('numero_reclamation')
                
                # Gestion de la date
                date_raw = request.POST.get('date_reclamation', '').strip()
                if date_raw and date_raw != '  ':
                    try:
                        reclamation.date_reclamation = date_raw
                    except:
                        reclamation.date_reclamation = timezone.now().date()
                
                reclamation.client_id = request.POST.get('client')
                reclamation.site_id = request.POST.get('site')
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
                
                # Gestion sécurisée du NQC (Decimal)
                nqc_value = request.POST.get('nqc', '0')
                if nqc_value == '' or nqc_value is None:
                    nqc_value = '0'
                nqc_value = str(nqc_value).strip().replace(',', '.')
                import re
                nqc_value = re.sub(r'[^0-9.-]', '', nqc_value)
                if nqc_value == '' or nqc_value == '-':
                    nqc_value = '0'
                
                try:
                    reclamation.nqc = Decimal(nqc_value)
                except (InvalidOperation, ValueError, TypeError):
                    reclamation.nqc = Decimal('0')
                    messages.warning(request, "La valeur NQC était invalide, elle a été mise à 0.")
                
                reclamation.save()
                
                # ========== TRAITEMENT DES LIGNES AVEC NC MULTIPLES ==========
                # Récupérer les IDs des lignes existantes
                lignes_ids = request.POST.getlist('ligne_id[]')
                produits = request.POST.getlist('produit[]')
                quantites = request.POST.getlist('quantite[]')  # Quantité totale
                commentaires = request.POST.getlist('commentaire[]')
                uaps = request.POST.getlist('uap_concernee[]')
                
                # Récupérer les données des NC
                nc_ids = request.POST.getlist('nc_id[]')
                nc_descriptions = request.POST.getlist('nc_description[]')
                nc_quantites = request.POST.getlist('nc_quantite[]')
                nc_ligne_refs = request.POST.getlist('nc_ligne_ref[]')
                
                # Regrouper les NC par ligne
                nc_par_ligne = {}
                for idx in range(len(nc_ids)):
                    ligne_ref = nc_ligne_refs[idx] if idx < len(nc_ligne_refs) else ''
                    if ligne_ref not in nc_par_ligne:
                        nc_par_ligne[ligne_ref] = []
                    nc_par_ligne[ligne_ref].append({
                        'id': nc_ids[idx],
                        'description': nc_descriptions[idx] if idx < len(nc_descriptions) else '',
                        'quantite': nc_quantites[idx] if idx < len(nc_quantites) else '1'
                    })
                
                lignes_a_conserver = []
                
                for i in range(len(produits)):
                    if not produits[i]:
                        continue
                    
                    quantite_totale = int(quantites[i]) if quantites[i] else 1
                    ligne_id = lignes_ids[i] if i < len(lignes_ids) else None
                    
                    if ligne_id and ligne_id.startswith('new_'):
                        # Créer nouvelle ligne
                        ligne = LigneReclamation.objects.create(
                            reclamation=reclamation,
                            produit_id=produits[i],
                            quantite=quantite_totale,
                            uap_concernee_id=uaps[i] if i < len(uaps) else None,
                            commentaire=commentaires[i] if i < len(commentaires) else ''
                        )
                        lignes_a_conserver.append(ligne.id)
                        ligne_ref = str(ligne.id)
                        
                    elif ligne_id and ligne_id.isdigit():
                        # Modifier ligne existante
                        ligne = LigneReclamation.objects.get(id=ligne_id, reclamation=reclamation)
                        ligne.produit_id = produits[i]
                        ligne.quantite = quantite_totale
                        ligne.uap_concernee_id = uaps[i] if i < len(uaps) else None
                        ligne.commentaire = commentaires[i] if i < len(commentaires) else ''
                        ligne.save()
                        lignes_a_conserver.append(ligne.id)
                        ligne_ref = ligne_id
                    else:
                        continue
                    
                    # Traiter les NC pour cette ligne
                    ncs_a_conserver = []
                    for nc_data in nc_par_ligne.get(ligne_ref, []):
                        description = nc_data['description']
                        quantite_nc = int(nc_data['quantite']) if nc_data['quantite'] else 1
                        
                        if not description:
                            continue
                        
                        if nc_data['id'].startswith('new_'):
                            NonConformite.objects.create(
                                ligne_reclamation=ligne,
                                description=description,
                                quantite=quantite_nc
                            )
                        elif nc_data['id'].isdigit():
                            nc = NonConformite.objects.get(id=nc_data['id'], ligne_reclamation=ligne)
                            nc.description = description
                            nc.quantite = quantite_nc
                            nc.save()
                            ncs_a_conserver.append(nc.id)
                    
                    # Supprimer les NC orphelines
                    ligne.non_conformites.exclude(id__in=ncs_a_conserver).delete()
                
                # Supprimer les lignes orphelines
                reclamation.lignes.exclude(id__in=lignes_a_conserver).delete()
                
                messages.success(request, f"Réclamation {reclamation.numero_reclamation} modifiée avec succès!")
                return redirect('reclamations:detail_reclamation', pk=reclamation.id)
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # GET: afficher le formulaire
    clients = Client.objects.filter(actif=True).order_by('nom')
    sites_usine = Site.objects.all().select_related('uap').order_by('nom')
    sites_client = SiteClient.objects.filter(client=reclamation.client, actif=True).order_by('nom') if reclamation.client else []
    programmes = Programme.objects.filter(clients=reclamation.client, actif=True).order_by('nom') if reclamation.client else []
    produits = Produit.objects.filter(actif=True).order_by('product_number')
    uaps = UAP.objects.all().order_by('nom')
    
    context = {
        'reclamation': reclamation,
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
def liste_sites(request):
    """Liste des sites"""
    sites = Site.objects.all().select_related('uap').order_by('nom')
    return render(request, 'reclamations/site/liste.html', {'sites': sites})

@login_required
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
def liste_programmes(request):
    """Liste des programmes"""
    programmes = Programme.objects.all().prefetch_related('clients').order_by('nom')
    return render(request, 'reclamations/programme/liste.html', {'programmes': programmes})

@login_required
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
def get_programmes_by_client(request):
    """Endpoint AJAX pour récupérer les programmes d'un client"""
    client_id = request.GET.get('client_id')
    if client_id:
        programmes = Programme.objects.filter(client_id=client_id, actif=True).values('id', 'nom')
        return JsonResponse(list(programmes), safe=False)
    return JsonResponse([], safe=False)

@login_required
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
def api_reclamations_client_mois(request):
    """API pour récupérer les données de réclamations par mois pour un client"""
    client_id = request.GET.get('client_id')
    
    stats = DashboardStats()
    
    if client_id and client_id != 'all':
        data = stats.get_reclamations_par_client_mois(client_id=int(client_id))
    else:
        data = stats.get_reclamations_par_client_mois()
    
    return JsonResponse(data)

#============AMDEC==========
@login_required
def amdec_produit(request, produit_id=None):
    """Génère une AMDEC pour un produit spécifique ou pour les produits les plus critiques"""
    
    context = AMDEC_calculator.AMDEC()
    
    return render(request, 'reclamations/amdec/amdec_template.html', context)

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False
    print("⚠️ xhtml2pdf n'est pas installé. Installez-le avec: pip install xhtml2pdf")
@login_required
def amdec_export_pdf(request, produit_id=None):
    """Exporte l'AMDEC en PDF"""
    
    if not XHTML2PDF_AVAILABLE:
        return HttpResponse(
            "La bibliothèque xhtml2pdf n'est pas installée. "
            "Installez-la avec: pip install xhtml2pdf", 
            status=500
        )
    
    # Récupérer les données
    context=AMDEC_calculator.AMDEC()
    
    # Générer le PDF
    template = get_template('reclamations/amdec/amdec_pdf.html')
    html = template.render(context)
    
    # Créer la réponse PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="AMDEC_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
    
    # Convertir HTML en PDF
    result = pisa.CreatePDF(io.BytesIO(html.encode('UTF-8')), dest=response)
    
    if result.err:
        return HttpResponse('Erreur lors de la génération du PDF: ' + str(result.err), status=500)
    
    return response

@login_required
def amdec_export_excel(request, produit_id=None):
    """Exporte l'AMDEC en Excel"""

    context=AMDEC_calculator.AMDEC()
    amdec_data=context['amdec_data']
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    subheader_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D9E1F2',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    center_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    fillable_format = workbook.add_format({
        'border': 1,
        'bg_color': '#FEF9E6',
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Créer une feuille par produit
    for data in amdec_data:
        produit = data['produit']
        worksheet = workbook.add_worksheet(f"{produit.product_number}"[:31])  # Limiter à 31 caractères
        
        # Titre
        worksheet.merge_range('A1:H1', f"AMDEC - Produit: {produit.product_number}", title_format)
        if produit.designation:
            worksheet.merge_range('A2:H2', f"Désignation: {produit.designation}", title_format)
        worksheet.merge_range('A3:H3', f"Date d'analyse: {data['date_analyse'].strftime('%d/%m/%Y')}", title_format)
        
        row = 4
        
        # Synthèse
        worksheet.merge_range(f'A{row+1}:H{row+1}', f"Synthèse: {data['total_defauts']} Réclamation(s) analysée(s)", cell_format)
        row += 2
        
        # En-tête du tableau principal
        headers = ['#', 'Mode de défaillance', 'Effets potentiels', 'G', 'Causes potentielles', 'O', 'D', 'CRIT']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        # Largeurs des colonnes
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 35)
        worksheet.set_column('C:C', 30)
        worksheet.set_column('D:D', 5)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:F', 5)
        worksheet.set_column('G:G', 5)
        worksheet.set_column('H:H', 8)
        
        row += 1
        
        # Données des défauts
        for idx, defaut in enumerate(data['defauts'], 1):
            worksheet.write(row, 0, idx, center_format)
            worksheet.write(row, 1, defaut['description'], cell_format)
            worksheet.write(row, 2, "", fillable_format)
            worksheet.write(row, 3, "", center_format)
            worksheet.write(row, 4, "", fillable_format)
            worksheet.write(row, 5, "", center_format)
            worksheet.write(row, 6, "", center_format)
            worksheet.write(row, 7, "", center_format)
            row += 1
        
        row += 1
        
        # Tableau des actions
        worksheet.merge_range(f'A{row}:E{row}', "ACTIONS RECOMMANDÉES", header_format)
        row += 1
        
        actions_headers = ['#', 'Actions préventives / correctives', 'Responsable', 'Délai', 'Suivi / Commentaires']
        for col, header in enumerate(actions_headers):
            worksheet.write(row, col, header, subheader_format)
        
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 30)
        
        row += 1
        
        # Lignes d'actions (une par défaut + 2 supplémentaires)
        for idx in range(1, len(data['defauts']) + 3):
            worksheet.write(row, 0, idx, center_format)
            worksheet.write(row, 1, "", fillable_format)
            worksheet.write(row, 2, "", fillable_format)
            worksheet.write(row, 3, "", fillable_format)
            worksheet.write(row, 4, "", fillable_format)
            row += 1
        
        row += 1
        
        # Tableau de validation
        validation_data = [
            ['Criticité maximale (CRIT max) :', '', 'Seuil d\'action :', ''],
            ['Approbateur :', '', 'Date :', ''],
            ['Animateur :', '', 'Date prochaine revue :', ''],
            ['Méthode de calcul :', 'G × O × D (Gravité × Occurrence × Détection)', '', '']
        ]
        
        for v_row, v_data in enumerate(validation_data):
            worksheet.write(row + v_row, 0, v_data[0], subheader_format)
            worksheet.write(row + v_row, 1, v_data[1], fillable_format)
            worksheet.write(row + v_row, 2, v_data[2], subheader_format)
            worksheet.write(row + v_row, 3, v_data[3], fillable_format)
        
        # Ajuster la hauteur des lignes
        worksheet.set_default_row(30)
    
    # Ajouter une feuille de synthèse
    worksheet_synth = workbook.add_worksheet("Synthèse")
    
    # En-tête synthèse
    synth_headers = ['Produit', 'Total défauts', 'Défaut principal', 'Occurrences', 'Quantité', 'Pourcentage']
    for col, header in enumerate(synth_headers):
        worksheet_synth.write(0, col, header, header_format)
    
    worksheet_synth.set_column('A:A', 20)
    worksheet_synth.set_column('B:B', 12)
    worksheet_synth.set_column('C:C', 35)
    worksheet_synth.set_column('D:D', 12)
    worksheet_synth.set_column('E:E', 12)
    worksheet_synth.set_column('F:F', 12)
    
    row = 1
    for data in amdec_data:
        produit = data['produit']
        defauts = data['defauts']
        if defauts:
            principal = defauts[0]
            worksheet_synth.write(row, 0, produit.product_number, cell_format)
            worksheet_synth.write(row, 1, data['total_defauts'], center_format)
            worksheet_synth.write(row, 2, principal['description'], cell_format)
            worksheet_synth.write(row, 3, principal['nb_occurences'], center_format)
            worksheet_synth.write(row, 4, principal['quantite_totale'], center_format)
            worksheet_synth.write(row, 5, f"{principal['pourcentage']}%", center_format)
            row += 1
    
    # Ajouter une feuille de légende
    worksheet_legend = workbook.add_worksheet("Légende")
    worksheet_legend.write(0, 0, "LÉGENDE AMDEC", title_format)
    
    legend_data = [
        ["Gravité (G)", "1-5", "1: Mineur, 5: Critique (sécurité, non-conformité majeure)"],
        ["Occurrence (O)", "1-5", "1: Très rare, 5: Très fréquent"],
        ["Détection (D)", "1-5", "1: Très facile à détecter, 5: Impossible à détecter"],
        ["CRIT", "G × O × D", "Criticité = Gravité × Occurrence × Détection"],
        ["", "", "Seuil d'action recommandé: > 50"]
    ]
    
    for i, data in enumerate(legend_data, 1):
        worksheet_legend.write(i, 0, data[0], subheader_format)
        worksheet_legend.write(i, 1, data[1], cell_format)
        worksheet_legend.write(i, 2, data[2], cell_format)
    
    worksheet_legend.set_column('A:A', 15)
    worksheet_legend.set_column('B:B', 10)
    worksheet_legend.set_column('C:C', 50)
    
    workbook.close()
    output.seek(0)
    
    # Créer la réponse
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="AMDEC_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    
    return response

#=============8D=============================================
@login_required
def huitd_detail(request, pk):
    """Affiche la fiche 8D d'une réclamation"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    huitd, created = HuitD.objects.get_or_create(reclamation=reclamation)
    
    if not huitd.numero_8d:
        huitd.numero_8d = f"8D-{reclamation.numero_reclamation}"
        huitd.save()
    
    context = {
        'reclamation': reclamation,
        'huitd': huitd,
    }
    return render(request, 'reclamations/huitd/huitd_template.html', context)

@login_required
def huitd_modifier(request, pk):
    """Modifie la fiche 8D"""
    huitd = get_object_or_404(HuitD, pk=pk)
    
    if request.method == 'POST':
        # D0
        huitd.d0_date = request.POST.get('d0_date') or None
        huitd.d0_equipe = request.POST.get('d0_equipe', '')
        
        # D1
        huitd.d1_leader = request.POST.get('d1_leader', '')
        huitd.d1_membres = request.POST.get('d1_membres', '')
        huitd.d1_competences = request.POST.get('d1_competences', '')
        
        # D2
        huitd.d2_description = request.POST.get('d2_description', '')
        huitd.d2_impact = request.POST.get('d2_impact', '')
        huitd.d2_quantification = request.POST.get('d2_quantification', '')
        huitd.d2_historique = request.POST.get('d2_historique', '')
        
        # D3
        huitd.d3_actions = request.POST.get('d3_actions', '')
        huitd.d3_responsable = request.POST.get('d3_responsable', '')
        huitd.d3_date = request.POST.get('d3_date') or None
        huitd.d3_efficacite = request.POST.get('d3_efficacite', '')
        
        # D4
        huitd.d4_causes = request.POST.get('d4_causes', '')
        huitd.d4_methodes = request.POST.get('d4_methodes', '')
        huitd.d4_validation = request.POST.get('d4_validation', '')
        
        # D5
        huitd.d5_actions = request.POST.get('d5_actions', '')
        huitd.d5_responsable = request.POST.get('d5_responsable', '')
        huitd.d5_date_prevue = request.POST.get('d5_date_prevue') or None
        huitd.d5_date_reelle = request.POST.get('d5_date_reelle') or None
        huitd.d5_validation = request.POST.get('d5_validation', '')
        
        # D6
        huitd.d6_actions = request.POST.get('d6_actions', '')
        huitd.d6_responsable = request.POST.get('d6_responsable', '')
        huitd.d6_date = request.POST.get('d6_date') or None
        huitd.d6_standardisation = request.POST.get('d6_standardisation', '')
        
        # D7
        huitd.d7_actions = request.POST.get('d7_actions', '')
        huitd.d7_documentation = request.POST.get('d7_documentation', '')
        huitd.d7_formation = request.POST.get('d7_formation', '')
        
        # D8
        huitd.d8_equipe = request.POST.get('d8_equipe', '')
        huitd.d8_retour = request.POST.get('d8_retour', '')
        huitd.d8_amelioration = request.POST.get('d8_amelioration', '')
        
        # Validation
        huitd.etat = request.POST.get('etat', 'EN_COURS')
        if huitd.etat == 'CLOTURE':
            huitd.date_validation = timezone.now().date()
        huitd.valide_par = request.POST.get('valide_par', '')
        
        huitd.save()
        messages.success(request, "Fiche 8D enregistrée avec succès!")
        return redirect('reclamations:huitd_detail', pk=huitd.reclamation.id)
    
    context = {
        'huitd': huitd,
        'reclamation': huitd.reclamation,
        'etat_choices': HuitD.ETAT_CHOICES,
    }
    return render(request, 'reclamations/huitd/huitd_edit.html', context)

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
 
#=========FAI Service====================

@login_required
def verifier_alertes_fai(request):
    """Vérification manuelle des alertes FAI"""
    service = FAIAlertService()
    
    # Lancer la vérification
    resultats = service.verifier_of_non_fermes()
    
    # Compter les alertes par niveau
    stats = {'CRITIQUE': 0, 'URGENT': 0, 'ALERTE': 0, 'INFO': 0, 'TOTAL': 0}
    for resultat in resultats:
        for alerte in resultat['alertes']:
            stats[alerte.niveau] += 1
            stats['TOTAL'] += 1
    
    context = {
        'resultats': resultats,
        'stats': stats,
        'date_verification': timezone.now()
    }
    return render(request, 'reclamations/fai/verification_resultat.html', context)

@login_required
def liste_alertes_fai(request):
    """Liste des alertes FAI"""
    alertes = AlerteFAI.objects.select_related('ordre_fabrication', 'produit').all()
    
    # Filtres
    statut = request.GET.get('statut', '')
    niveau = request.GET.get('niveau', '')
    of_id = request.GET.get('of', '')
    
    if statut:
        alertes = alertes.filter(statut=statut)
    if niveau:
        alertes = alertes.filter(niveau=niveau)
    if of_id:
        alertes = alertes.filter(ordre_fabrication_id=of_id)
    
    context = {
        'alertes': alertes,
        'statut_choices': AlerteFAI.STATUT_CHOICES,
        'niveau_choices': AlerteFAI.NIVEAU_CHOICES,
    }
    return render(request, 'reclamations/fai/liste_alertes.html', context)

@login_required
def traiter_alerte_fai(request, pk):
    """Traiter manuellement une alerte FAI"""
    alerte = get_object_or_404(AlerteFAI, pk=pk)
    
    if request.method == 'POST':
        alerte.statut = request.POST.get('statut')
        alerte.commentaire = request.POST.get('commentaire', '')
        alerte.traite_par = request.user.get_full_name() or request.user.username
        alerte.date_traitement = timezone.now()
        alerte.save()
        
        messages.success(request, f"Alerte {alerte.get_niveau_display()} traitée")
        return redirect('reclamations:liste_alertes_fai')
    
    context = {'alerte': alerte}
    return render(request, 'reclamations/fai/traiter_alerte.html', context)

@login_required
def alertes_par_of(request, of_id):
    """Alertes pour un OF spécifique"""
    of = get_object_or_404(OrdreFabrication, pk=of_id)
    alertes = AlerteFAI.objects.filter(ordre_fabrication=of).select_related('produit')
    
    context = {
        'of': of,
        'alertes': alertes
    }
    return render(request, 'reclamations/fai/alertes_par_of.html', context)

@login_required
def importer_of_erp(request):
    """Import des OF depuis l'ERP (simulation)"""
    if request.method == 'POST':
        # Simulation d'import
        data = request.POST.get('data')
        # Traitement...
        
        messages.success(request, "Import des OF terminé")
        return redirect('reclamations:verifier_alertes_fai')
    
    return render(request, 'reclamations/fai/importer_of.html')

@csrf_exempt
@require_http_methods(["POST"])
def api_importer_of(request):
    """API pour importer des OF depuis l'ERP"""
    try:
        data = json.loads(request.body)
        ofs_data = data.get('ofs', [])
        
        service = FAIAlertService()
        resultats = service.importer_donnees_erp(ofs_data)
        
        return JsonResponse({
            'success': True,
            'message': f"{resultats['crees']} OF créés, {resultats['mis_a_jour']} mis à jour",
            'details': resultats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def api_statut_of(request):
    """API pour obtenir le statut des OF"""
    of_id = request.GET.get('of_id')
    numero_of = request.GET.get('numero_of')
    
    try:
        if of_id:
            of = OrdreFabrication.objects.get(id=of_id)
        elif numero_of:
            of = OrdreFabrication.objects.get(numero_of=numero_of)
        else:
            return JsonResponse({
                'success': False,
                'error': "Paramètre of_id ou numero_of requis"
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'of': {
                'id': of.id,
                'numero_of': of.numero_of,
                'statut': of.statut,
                'statut_display': of.get_statut_display(),
                'date_creation': of.date_creation.strftime('%Y-%m-%d'),
                'date_previsionnelle': of.date_previsionnelle.strftime('%Y-%m-%d') if of.date_previsionnelle else None,
                'date_reelle_fin': of.date_reelle_fin.strftime('%Y-%m-%d') if of.date_reelle_fin else None,
                'responsable': of.responsable,
                'atelier': of.atelier,
                'priorite': of.priorite
            }
        })
        
    except OrdreFabrication.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': "OF non trouvé"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def liste_of(request):
    """Liste des ordres de fabrication"""
    ofs = OrdreFabrication.objects.all().order_by('-date_creation')
    
    # Filtres
    statut = request.GET.get('statut', '')
    if statut:
        ofs = ofs.filter(statut=statut)
    
    context = {
        'ofs': ofs,
        'statut_choices': OrdreFabrication.STATUT_CHOICES
    }
    return render(request, 'reclamations/fai/liste_of.html', context)

@login_required
def detail_of(request, pk):
    """Détail d'un ordre de fabrication"""
    of = get_object_or_404(OrdreFabrication.objects.prefetch_related('lignes__produit'), pk=pk)
    alertes = AlerteFAI.objects.filter(ordre_fabrication=of).select_related('produit')
    
    context = {
        'of': of,
        'alertes': alertes
    }
    return render(request, 'reclamations/fai/detail_of.html', context)


@login_required
def fermer_of(request, pk):
    """Fermer manuellement un OF"""
    of = get_object_or_404(OrdreFabrication, pk=pk)
    
    if request.method == 'POST':
        of.statut = 'CLOTURE'
        of.date_reelle_fin = timezone.now().date()
        of.save()
        
        messages.success(request, f"OF {of.numero_of} clôturé avec succès")
        return redirect('reclamations:liste_of')
    
    context = {'of': of}
    return render(request, 'reclamations/fai/fermer_of.html', context)


@login_required
def envoyer_alertes_fai(request):
    """Envoyer manuellement les alertes FAI groupées"""
    if request.method == 'POST':
        service = FAIAlertService()
        alertes_envoyees = service.envoyer_alertes_groupes()
        
        messages.success(request, f"{len(alertes_envoyees)} alerte(s) groupée(s) envoyée(s)")
        return redirect('reclamations:liste_alertes_fai')
    
    # GET: afficher confirmation avec statistiques calculées
    service = FAIAlertService()
    resultats = service.verifier_of_non_fermes()
    
    # Calculer les statistiques par OF
    resultats_detail = []
    for resultat in resultats:
        nb_critique = sum(1 for a in resultat['alertes'] if a.niveau == 'CRITIQUE')
        nb_urgent = sum(1 for a in resultat['alertes'] if a.niveau == 'URGENT')
        nb_alerte = sum(1 for a in resultat['alertes'] if a.niveau == 'ALERTE')
        
        resultats_detail.append({
            'of': resultat['of'],
            'nb_alertes': len(resultat['alertes']),
            'nb_critique': nb_critique,
            'nb_urgent': nb_urgent,
            'nb_alerte': nb_alerte
        })
    
    nb_alertes_total = sum(r['nb_alertes'] for r in resultats_detail)
    
    context = {
        'nb_of': len(resultats_detail),
        'nb_alertes': nb_alertes_total,
        'resultats': resultats_detail
    }
    return render(request, 'reclamations/fai/confirmation_envoi.html', context)

@login_required
def liste_produits_fai(request):
    """Liste des produits avec suivi FAI"""
    produits = Produit.objects.filter(
        lignes_of__isnull=False
    ).distinct().annotate(
        nb_of=Count('lignes_of'),
        derniere_production=Max('lignes_of__date_fin')
    ).order_by('-derniere_production')
    
    context = {
        'produits': produits
    }
    return render(request, 'reclamations/fai/liste_produits_fai.html', context)

@login_required
def detail_produit_fai(request, pk):
    """Détail FAI d'un produit"""
    produit = get_object_or_404(Produit, pk=pk)
    alertes = AlerteFAI.objects.filter(produit=produit).select_related('ordre_fabrication')
    historique_productions = LigneOF.objects.filter(produit=produit).select_related('ordre_fabrication').order_by('-date_fin')
    
    context = {
        'produit': produit,
        'alertes': alertes,
        'historique_productions': historique_productions
    }
    return render(request, 'reclamations/fai/detail_produit_fai.html', context)


@login_required
def enregistrer_inspection_fai(request, pk):
    """Enregistrer une inspection FAI réalisée"""
    produit = get_object_or_404(Produit, pk=pk)
    
    if request.method == 'POST':
        date_inspection = request.POST.get('date_inspection')
        commentaire = request.POST.get('commentaire', '')
        
        # Mettre à jour ou créer l'article FAI
        article, created = Article.objects.update_or_create(
            produit=produit,
            defaults={
                'dernier_controle': date_inspection,
                'statut': 'VALIDE',
                'observations': commentaire
            }
        )
        
        # Mettre à jour les alertes associées
        AlerteFAI.objects.filter(
            produit=produit,
            statut__in=['NOUVELLE', 'EN_COURS']
        ).update(statut='TRAITEE', date_traitement=timezone.now())
        
        messages.success(request, f"Inspection FAI enregistrée pour {produit.product_number}")
        return redirect('reclamations:detail_produit_fai', pk=produit.id)
    
    context = {
        'produit': produit,
        'today': timezone.now().date()
    }
    return render(request, 'reclamations/fai/enregistrer_inspection.html', context)

@login_required
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