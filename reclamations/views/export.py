import io

import xlsxwriter

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from accounts.decorators import role_required
from reclamations.utils.dashboard_stats import DashboardStats
from reclamations.models import (
    LigneReclamation,
    NonConformite,
    Reclamation,
)

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
        ['Taux de réactivité', f"{data['taux_reactivite']}%"],
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
    """
    Exporte toutes les réclamations en Excel avec :
    - les réclamations ;
    - les lignes de réclamation ;
    - les non-conformités ;
    - les statistiques générales.
    """

    output = io.BytesIO()

    workbook = xlsxwriter.Workbook(
        output,
        {
            'in_memory': True,
        }
    )

    # ============================================================
    # FORMATS
    # ============================================================

    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4CAF50',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })

    header_blue_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2196F3',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })

    header_orange_format = workbook.add_format({
        'bold': True,
        'bg_color': '#FF9800',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })

    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True,
    })

    cell_center_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
    })

    number_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '#,##0.00',
    })

    integer_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '#,##0',
    })

    date_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy',
    })

    datetime_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy hh:mm',
    })

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'font_color': '#2196F3',
    })

    stat_label_format = workbook.add_format({
        'bold': True,
        'bg_color': '#E3F2FD',
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
    })

    stat_value_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
    })

    # ============================================================
    # CHARGEMENT OPTIMISÉ DES DONNÉES
    # ============================================================

    non_conformites_queryset = (
        NonConformite.objects
        .only(
            'id',
            'ligne_reclamation_id',
            'description',
            'quantite',
            'date_creation',
        )
        .order_by('-date_creation')
    )

    lignes_queryset = (
        LigneReclamation.objects
        .select_related(
            'produit',
            'site',
            'site__uap',
            'uap_concernee',
        )
        .prefetch_related(
            Prefetch(
                'non_conformites',
                queryset=non_conformites_queryset,
            )
        )
        .order_by('id')
    )

    reclamations_queryset = (
        Reclamation.objects
        .select_related(
            'client',
            'site_client',
            'programme',
            'createur',
        )
        .prefetch_related(
            Prefetch(
                'lignes',
                queryset=lignes_queryset,
            )
        )
        .order_by('-date_reclamation', '-id')
    )

    # Évaluation unique du QuerySet.
    # Les objets et les relations préchargées seront réutilisés
    # dans les trois feuilles.
    reclamations = list(reclamations_queryset)

    total_reclamations = len(reclamations)

    # ============================================================
    # FEUILLE 1 : RÉCLAMATIONS
    # ============================================================

    worksheet_reclamations = workbook.add_worksheet(
        'Réclamations'
    )

    worksheet_reclamations.hide_gridlines(2)
    worksheet_reclamations.freeze_panes(1, 0)
    worksheet_reclamations.set_row(0, 35)

    headers = [
        'N° Réclamation',
        'Date réclamation',
        'Client',
        'Site client',
        'Programme',
        'Type NC',
        'Imputation',
        'N° 4D',
        'N° 8D',
        'État 4D',
        'État 8D',
        '8D non applicable',
        '4DP nécessaire',
        'Clôturé',
        'Date clôture',
        'Date clôture 4D',
        'Date clôture 8D',
        'Evidence',
        'ME',
        'Décision',
        'NQC (MAD)',
        'Créateur',
        'Date création',
    ]

    for col, header in enumerate(headers):
        worksheet_reclamations.write(
            0,
            col,
            header,
            header_format,
        )

    row = 1

    for rec in reclamations:
        # Sécuriser le nom du créateur.
        if rec.createur:
            createur_nom = rec.createur.get_full_name()

            if not createur_nom:
                createur_nom = rec.createur.username
        else:
            createur_nom = '-'

        col = 0

        worksheet_reclamations.write(
            row,
            col,
            rec.numero_reclamation or '-',
            cell_format,
        )
        col += 1

        if rec.date_reclamation:
            worksheet_reclamations.write_datetime(
                row,
                col,
                rec.date_reclamation,
                date_format,
            )
        else:
            worksheet_reclamations.write(
                row,
                col,
                '-',
                cell_center_format,
            )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.client.nom if rec.client else '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.site_client.nom if rec.site_client else '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.programme.nom if rec.programme else '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.get_type_nc_display(),
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.get_imputation_display(),
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.numero_4d or '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.numero_8d or '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.get_etat_4d_display(),
            cell_center_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.get_etat_8d_display(),
            cell_center_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            'Oui' if rec.huitd_non_applicable else 'Non',
            cell_center_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            'Oui' if rec.besoin_4dp else 'Non',
            cell_center_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            'Oui' if rec.cloture else 'Non',
            cell_center_format,
        )
        col += 1

        if rec.date_cloture:
            worksheet_reclamations.write_datetime(
                row,
                col,
                rec.date_cloture,
                date_format,
            )
        else:
            worksheet_reclamations.write(
                row,
                col,
                '-',
                cell_center_format,
            )
        col += 1

        if rec.date_cloture_4d:
            worksheet_reclamations.write_datetime(
                row,
                col,
                rec.date_cloture_4d,
                date_format,
            )
        else:
            worksheet_reclamations.write(
                row,
                col,
                '-',
                cell_center_format,
            )
        col += 1

        if rec.date_cloture_8d:
            worksheet_reclamations.write_datetime(
                row,
                col,
                rec.date_cloture_8d,
                date_format,
            )
        else:
            worksheet_reclamations.write(
                row,
                col,
                '-',
                cell_center_format,
            )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.evidence or '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            'Oui' if rec.me else 'Non',
            cell_center_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            rec.decision or '-',
            cell_format,
        )
        col += 1

        worksheet_reclamations.write_number(
            row,
            col,
            float(rec.nqc or 0),
            number_format,
        )
        col += 1

        worksheet_reclamations.write(
            row,
            col,
            createur_nom,
            cell_format,
        )
        col += 1

        if rec.date_creation:
            # Les datetimes Django peuvent contenir un fuseau horaire.
            # XlsxWriter attend un datetime sans tzinfo.
            date_creation_sans_timezone = timezone.localtime(
                rec.date_creation
            ).replace(tzinfo=None)

            worksheet_reclamations.write_datetime(
                row,
                col,
                date_creation_sans_timezone,
                datetime_format,
            )
        else:
            worksheet_reclamations.write(
                row,
                col,
                '-',
                cell_center_format,
            )

        row += 1

    column_widths = [
        18,
        14,
        22,
        18,
        18,
        14,
        14,
        15,
        15,
        12,
        12,
        16,
        15,
        10,
        14,
        16,
        16,
        30,
        8,
        30,
        14,
        22,
        18,
    ]

    for col, width in enumerate(column_widths):
        worksheet_reclamations.set_column(
            col,
            col,
            width,
        )

    if total_reclamations > 0:
        worksheet_reclamations.autofilter(
            0,
            0,
            row - 1,
            len(headers) - 1,
        )

    # ============================================================
    # FEUILLE 2 : LIGNES DE RÉCLAMATION
    # ============================================================

    worksheet_lignes = workbook.add_worksheet(
        'Lignes de réclamation'
    )

    worksheet_lignes.hide_gridlines(2)
    worksheet_lignes.freeze_panes(1, 0)
    worksheet_lignes.set_row(0, 35)

    headers_lignes = [
        'N° Réclamation',
        'Date',
        'Client',
        'Site production',
        'UAP',
        'Produit',
        'Désignation',
        'Quantité',
        'Description NC',
        'Quantité totale NC',
        'Commentaire',
    ]

    for col, header in enumerate(headers_lignes):
        worksheet_lignes.write(
            0,
            col,
            header,
            header_blue_format,
        )

    row = 1

    for rec in reclamations:
        # Utilise les lignes préchargées par Prefetch.
        for ligne in rec.lignes.all():
            non_conformites = list(
                ligne.non_conformites.all()
            )

            # Le champ description_non_conformite n'existe pas
            # dans LigneReclamation. On récupère les descriptions
            # depuis le modèle NonConformite.
            descriptions_nc = [
                nc.description.strip()
                for nc in non_conformites
                if nc.description
            ]

            description_nc = (
                ' | '.join(descriptions_nc)
                if descriptions_nc
                else '-'
            )

            quantite_totale_nc = sum(
                nc.quantite or 0
                for nc in non_conformites
            )

            # Priorité à l'UAP directement enregistrée dans la ligne.
            if ligne.uap_concernee:
                uap_nom = ligne.uap_concernee.nom
            elif ligne.site and ligne.site.uap:
                uap_nom = ligne.site.uap.nom
            else:
                uap_nom = '-'

            col = 0

            worksheet_lignes.write(
                row,
                col,
                rec.numero_reclamation or '-',
                cell_format,
            )
            col += 1

            if rec.date_reclamation:
                worksheet_lignes.write_datetime(
                    row,
                    col,
                    rec.date_reclamation,
                    date_format,
                )
            else:
                worksheet_lignes.write(
                    row,
                    col,
                    '-',
                    cell_center_format,
                )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                rec.client.nom if rec.client else '-',
                cell_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                ligne.site.nom if ligne.site else '-',
                cell_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                uap_nom,
                cell_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                str(ligne.produit.product_number or '-'),
                cell_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                ligne.produit.designation or '-',
                cell_format,
            )
            col += 1

            worksheet_lignes.write_number(
                row,
                col,
                ligne.quantite or 0,
                integer_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                description_nc,
                cell_format,
            )
            col += 1

            worksheet_lignes.write_number(
                row,
                col,
                quantite_totale_nc,
                integer_format,
            )
            col += 1

            worksheet_lignes.write(
                row,
                col,
                ligne.commentaire or '-',
                cell_format,
            )

            row += 1

    column_widths_lignes = [
        18,
        12,
        22,
        18,
        15,
        15,
        30,
        10,
        50,
        18,
        30,
    ]

    for col, width in enumerate(column_widths_lignes):
        worksheet_lignes.set_column(
            col,
            col,
            width,
        )

    if row > 1:
        worksheet_lignes.autofilter(
            0,
            0,
            row - 1,
            len(headers_lignes) - 1,
        )

    # ============================================================
    # FEUILLE 3 : NON-CONFORMITÉS
    # ============================================================

    worksheet_nc = workbook.add_worksheet(
        'Non-conformités'
    )

    worksheet_nc.hide_gridlines(2)
    worksheet_nc.freeze_panes(1, 0)
    worksheet_nc.set_row(0, 35)

    headers_nc = [
        'N° Réclamation',
        'Date',
        'Client',
        'Site',
        'UAP',
        'Produit',
        'Quantité ligne',
        'Description NC',
        'Quantité NC',
        'Date création NC',
    ]

    for col, header in enumerate(headers_nc):
        worksheet_nc.write(
            0,
            col,
            header,
            header_orange_format,
        )

    row = 1

    for rec in reclamations:
        for ligne in rec.lignes.all():
            if ligne.uap_concernee:
                uap_nom = ligne.uap_concernee.nom
            elif ligne.site and ligne.site.uap:
                uap_nom = ligne.site.uap.nom
            else:
                uap_nom = '-'

            for nc in ligne.non_conformites.all():
                col = 0

                worksheet_nc.write(
                    row,
                    col,
                    rec.numero_reclamation or '-',
                    cell_format,
                )
                col += 1

                if rec.date_reclamation:
                    worksheet_nc.write_datetime(
                        row,
                        col,
                        rec.date_reclamation,
                        date_format,
                    )
                else:
                    worksheet_nc.write(
                        row,
                        col,
                        '-',
                        cell_center_format,
                    )
                col += 1

                worksheet_nc.write(
                    row,
                    col,
                    rec.client.nom if rec.client else '-',
                    cell_format,
                )
                col += 1

                worksheet_nc.write(
                    row,
                    col,
                    ligne.site.nom if ligne.site else '-',
                    cell_format,
                )
                col += 1

                worksheet_nc.write(
                    row,
                    col,
                    uap_nom,
                    cell_format,
                )
                col += 1

                worksheet_nc.write(
                    row,
                    col,
                    str(ligne.produit.product_number or '-'),
                    cell_format,
                )
                col += 1

                worksheet_nc.write_number(
                    row,
                    col,
                    ligne.quantite or 0,
                    integer_format,
                )
                col += 1

                worksheet_nc.write(
                    row,
                    col,
                    nc.description or '-',
                    cell_format,
                )
                col += 1

                worksheet_nc.write_number(
                    row,
                    col,
                    nc.quantite or 0,
                    integer_format,
                )
                col += 1

                if nc.date_creation:
                    date_nc_sans_timezone = timezone.localtime(
                        nc.date_creation
                    ).replace(tzinfo=None)

                    worksheet_nc.write_datetime(
                        row,
                        col,
                        date_nc_sans_timezone,
                        datetime_format,
                    )
                else:
                    worksheet_nc.write(
                        row,
                        col,
                        '-',
                        cell_center_format,
                    )

                row += 1

    column_widths_nc = [
        18,
        12,
        22,
        18,
        15,
        15,
        14,
        45,
        14,
        19,
    ]

    for col, width in enumerate(column_widths_nc):
        worksheet_nc.set_column(
            col,
            col,
            width,
        )

    if row > 1:
        worksheet_nc.autofilter(
            0,
            0,
            row - 1,
            len(headers_nc) - 1,
        )

    # ============================================================
    # FEUILLE 4 : STATISTIQUES
    # ============================================================

    worksheet_stats = workbook.add_worksheet(
        'Statistiques'
    )

    worksheet_stats.hide_gridlines(2)

    worksheet_stats.write(
        0,
        0,
        'RÉSUMÉ DES RÉCLAMATIONS',
        title_format,
    )

    date_export = timezone.localtime().strftime(
        '%d/%m/%Y à %H:%M'
    )

    worksheet_stats.write(
        1,
        0,
        f'Export réalisé le {date_export}',
        cell_format,
    )

    # Ces statistiques sont calculées directement en base.
    statistiques_generales = Reclamation.objects.aggregate(
        total=Count('id'),
        ouvertes=Count(
            'id',
            filter=Q(cloture=False),
        ),
        cloturees=Count(
            'id',
            filter=Q(cloture=True),
        ),
    )

    row = 3

    stats = [
        (
            'Total réclamations',
            statistiques_generales['total'] or 0,
        ),
        (
            'Réclamations ouvertes',
            statistiques_generales['ouvertes'] or 0,
        ),
        (
            'Réclamations clôturées',
            statistiques_generales['cloturees'] or 0,
        ),
        (
            '',
            '',
        ),
        (
            'Par type de NC',
            '',
        ),
    ]

    for label, value in stats:
        worksheet_stats.write(
            row,
            0,
            label,
            stat_label_format,
        )

        worksheet_stats.write(
            row,
            1,
            value,
            stat_value_format,
        )

        row += 1

    type_stats = (
        Reclamation.objects
        .values('type_nc')
        .annotate(total=Count('id'))
        .order_by('type_nc')
    )

    types_nc = dict(Reclamation.TYPE_NC_CHOICES)

    for stat in type_stats:
        type_display = types_nc.get(
            stat['type_nc'],
            stat['type_nc'],
        )

        worksheet_stats.write(
            row,
            0,
            f'  - {type_display}',
            stat_label_format,
        )

        worksheet_stats.write(
            row,
            1,
            stat['total'],
            stat_value_format,
        )

        row += 1

    row += 1

    worksheet_stats.write(
        row,
        0,
        'Par imputation',
        stat_label_format,
    )

    worksheet_stats.write(
        row,
        1,
        '',
        stat_value_format,
    )

    row += 1

    imputation_stats = (
        Reclamation.objects
        .values('imputation')
        .annotate(total=Count('id'))
        .order_by('imputation')
    )

    imputations = dict(Reclamation.IMPUTATION_CHOICES)

    for stat in imputation_stats:
        imputation_display = imputations.get(
            stat['imputation'],
            stat['imputation'],
        )

        worksheet_stats.write(
            row,
            0,
            f'  - {imputation_display}',
            stat_label_format,
        )

        worksheet_stats.write(
            row,
            1,
            stat['total'],
            stat_value_format,
        )

        row += 1

    worksheet_stats.set_column(0, 0, 40)
    worksheet_stats.set_column(1, 1, 18)

    # ============================================================
    # FINALISATION
    # ============================================================

    workbook.close()

    fichier_excel = output.getvalue()
    output.close()

    date_nom_fichier = timezone.localtime().strftime(
        '%Y%m%d_%H%M%S'
    )

    nom_fichier = (
        f'reclamations_export_{date_nom_fichier}.xlsx'
    )

    response = HttpResponse(
        fichier_excel,
        content_type=(
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet'
        ),
    )

    response['Content-Disposition'] = (
        f'attachment; filename="{nom_fichier}"'
    )

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
        ['Taux de réactivité', f"{data['taux_reactivite']}%"],
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
