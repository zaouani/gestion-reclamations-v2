from reclamations.models import (Reclamation, Client, Produit, LigneReclamation, NonConformite, UAP, Site, 
    Programme, HuitD, Participant8D, CauseIshikawa, CauseCinqP, 
    EvaluationFacteurHumain, Action8D, CinqW2H) 
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from accounts.decorators import role_required, permission_required
from urllib.parse import unquote
from django.db.models import Count, Q, F, Avg,Max, Sum, Prefetch
from django.db.models.functions import TruncMonth, ExtractMonth
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
import io
from io import BytesIO
import xlsxwriter
from django.http import HttpResponse
from collections import defaultdict

#taux de récurrence des produits
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def taux_recurrence_produits(request):
    """Calcule le taux de récurrence des défauts par produit."""

    # Nombre total de réclamations
    total_reclamations = Reclamation.objects.count()

    # Récupérer uniquement les produits présents dans les lignes
    # de réclamation CIM ou ALERTE.
    statistiques = list(
        LigneReclamation.objects
        .filter(
            produit__isnull=False,
            produit__actif=True,
            reclamation__imputation__in=['CIM', 'ALERTE'],
        )
        .values('produit_id')
        .annotate(
            nb_reclamations=Count(
                'reclamation_id',
                distinct=True,
            )
        )
        .order_by('-nb_reclamations')
    )

    # Récupérer les identifiants des produits concernés
    produit_ids = [
        stat['produit_id']
        for stat in statistiques
    ]

    # Charger uniquement les produits concernés
    produits_par_id = Produit.objects.in_bulk(produit_ids)

    produits_data = []

    for stat in statistiques:
        produit = produits_par_id.get(stat['produit_id'])

        if produit is None:
            continue

        nb_reclamations = stat['nb_reclamations']

        if total_reclamations > 0:
            taux = (
                nb_reclamations / total_reclamations
            ) * 100
        else:
            taux = 0

        produits_data.append({
            'produit': produit,
            'nb_reclamations': nb_reclamations,
            'taux_recurrence': round(taux, 2),
        })

    context = {
        'produits_data': produits_data,
        'total_reclamations': total_reclamations,
    }

    return render(
        request,
        'reclamations/produit/recurrence.html',
        context,
    )

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

#taux de récurrence des descriptions de non-conformité (NC)
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def taux_recurrence_nc(request):
    """
    Taux de récurrence des non-conformités

    Taux = Nombre de réclamations contenant le défaut
          / Nombre total de réclamations
          × 100
    """

    search = request.GET.get("search", "").strip()
    imputation = request.GET.get("imputation", "CIM")

    # ==========================
    # Réclamations (dénominateur)
    # ==========================
    reclamations_qs = Reclamation.objects.all()

    if imputation:
        reclamations_qs = reclamations_qs.filter(
            imputation=imputation
        )

    total_reclamations = reclamations_qs.count()

    # ==========================
    # Non-conformités
    # ==========================
    nc_qs = NonConformite.objects.filter(
        description__isnull=False
    ).exclude(
        description=""
    )

    if imputation:
        nc_qs = nc_qs.filter(
            ligne_reclamation__reclamation__imputation=imputation
        )

    if search:
        nc_qs = nc_qs.filter(
            description__icontains=search
        )

    # ==========================
    # Agrégation principale
    # ==========================
    descriptions = list(
        nc_qs.values("description")
        .annotate(
            quantite_totale=Sum("quantite"),
            nb_produits=Count(
                "ligne_reclamation__produit",
                distinct=True
            ),
            nb_reclamations_concernees=Count(
                "ligne_reclamation__reclamation",
                distinct=True
            ),
        )
        .order_by("-nb_reclamations_concernees")
    )


    # ==========================
    # Construction résultats
    # ==========================
    resultats = []

    total_occurences_nc = 0

    for desc in descriptions:

        nb_reclamations = desc["nb_reclamations_concernees"]

        taux = (
            round(
                (nb_reclamations / total_reclamations) * 100,
                2
            )
            if total_reclamations
            else 0
        )

        # couleur bootstrap
        if taux < 5:
            couleur = "success"
        elif taux < 15:
            couleur = "warning"
        else:
            couleur = "danger"

        total_occurences_nc += desc["nb_produits"]

        resultats.append({
            "description": desc["description"],
            "nb_occurences": nb_reclamations,
            "nb_reclamations": nb_reclamations,
            "quantite_totale": desc["quantite_totale"] or 0,
            "nb_produits": desc["nb_produits"],
            "taux_recurrence": taux,
            "couleur": couleur,
        })

    context = {
        "descriptions": resultats,
        "total_reclamations_cim": total_reclamations,
        "total_nc_distinctes": len(resultats),
        "total_occurences_nc": total_occurences_nc,
        "date_analyse": timezone.now(),
        "filtre_imputation": imputation,
        "search": search,
        "imputation_choices": Reclamation.IMPUTATION_CHOICES,
        "imputation_label": (
            dict(Reclamation.IMPUTATION_CHOICES).get(
                imputation,
                "Toutes"
            )
            if imputation
            else "Toutes"
        ),
    }

    return render(
        request,
        "reclamations/produit/recurrence_nc.html",
        context,
    )


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

#exporter les données de récurrence vers un fichier Excel
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
    """
    Exporte les données de récurrence des produits en Excel.

    Optimisations :
    - charge uniquement les produits présents dans les lignes de réclamation ;
    - agrège les statistiques directement en base de données ;
    - évite les requêtes dans les boucles ;
    - récupère toutes les non-conformités en une seule requête ;
    - récupère les détails NC des 30 premiers produits en une seule requête.
    """
    # ============================================================
    # PRÉPARATION
    # ============================================================

    maintenant = timezone.localtime()
    imputations = ['CIM', 'ALERTE']

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

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'font_color': '#1A5276',
        'align': 'center',
        'valign': 'vcenter',
    })

    subtitle_format = workbook.add_format({
        'font_size': 11,
        'font_color': '#666666',
        'align': 'center',
        'valign': 'vcenter',
    })

    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2E86C1',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })

    header_secondary_format = workbook.add_format({
        'bold': True,
        'bg_color': '#5DADE2',
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
        'num_format': '#,##0.##',
    })

    percent_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
    })

    high_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#FADBD8',
        'font_color': '#922B21',
    })

    medium_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#FDEBD0',
        'font_color': '#D35400',
    })

    low_rate_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': '0.00%',
        'bg_color': '#D5F5E3',
        'font_color': '#1E8449',
    })

    date_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'font_color': '#666666',
    })

    stats_label_format = workbook.add_format({
        'bold': True,
        'bg_color': '#EBF5FB',
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
    })

    stats_value_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
    })

    # ============================================================
    # COLLECTE OPTIMISÉE DES DONNÉES
    # ============================================================

    # Total des réclamations du périmètre CIM et ALERTE.
    total_reclamations = Reclamation.objects.filter(
        imputation__in=imputations
    ).count()

    # Nombre total de produits actifs.
    total_produits = Produit.objects.filter(
        actif=True
    ).count()

    # Une seule requête pour calculer les statistiques des lignes.
    #
    # Seuls les produits :
    # - actifs ;
    # - présents dans LigneReclamation ;
    # - liés à une réclamation CIM ou ALERTE
    # sont sélectionnés.
    statistiques_lignes = list(
        LigneReclamation.objects
        .filter(
            produit__isnull=False,
            produit__actif=True,
            reclamation__imputation__in=imputations,
        )
        .values('produit_id')
        .annotate(
            nb_reclamations=Count(
                'reclamation_id',
                distinct=True,
            ),
            nb_lignes=Count(
                'id',
                distinct=True,
            ),
            quantite_totale=Sum('quantite'),
        )
        .order_by('-nb_reclamations', 'produit_id')
    )

    produit_ids = [
        stat['produit_id']
        for stat in statistiques_lignes
    ]

    # Charger uniquement les objets Produit concernés.
    produits_par_id = Produit.objects.in_bulk(produit_ids)

    # Une seule requête pour calculer les statistiques des NC
    # de tous les produits concernés.
    statistiques_nc = (
        NonConformite.objects
        .filter(
            ligne_reclamation__produit_id__in=produit_ids,
            ligne_reclamation__produit__actif=True,
            ligne_reclamation__reclamation__imputation__in=imputations,
        )
        .values('ligne_reclamation__produit_id')
        .annotate(
            nc_count=Count('id'),
            nc_distinctes=Count(
                'description',
                distinct=True,
            ),
        )
    )

    # Dictionnaire :
    # {
    #     produit_id: {
    #         'nc_count': ...,
    #         'nc_distinctes': ...
    #     }
    # }
    statistiques_nc_par_produit = {
        stat['ligne_reclamation__produit_id']: stat
        for stat in statistiques_nc
    }

    produits_data = []

    for stat in statistiques_lignes:
        produit_id = stat['produit_id']
        produit = produits_par_id.get(produit_id)

        if produit is None:
            continue

        nb_reclamations = stat['nb_reclamations'] or 0
        nb_lignes = stat['nb_lignes'] or 0
        quantite_totale = stat['quantite_totale'] or 0

        donnees_nc = statistiques_nc_par_produit.get(
            produit_id,
            {}
        )

        nc_count = donnees_nc.get('nc_count', 0)
        nc_distinctes = donnees_nc.get('nc_distinctes', 0)

        if total_reclamations > 0:
            taux = (
                nb_reclamations / total_reclamations
            ) * 100
        else:
            taux = 0

        if taux >= 5:
            criticite = 'CRITIQUE'
        elif taux >= 2:
            criticite = 'SURVEILLANCE'
        else:
            criticite = 'FAIBLE'

        produits_data.append({
            'produit_id': produit_id,
            'produit': produit,
            'nb_reclamations': nb_reclamations,
            'nb_lignes': nb_lignes,
            'quantite_totale': quantite_totale,
            'nc_count': nc_count,
            'nc_distinctes': nc_distinctes,
            'taux_recurrence': round(taux, 2),
            'criticite': criticite,
        })

    # Trier d'abord par taux et ensuite par numéro de produit.
    produits_data.sort(
        key=lambda data: (
            -data['taux_recurrence'],
            str(data['produit'].product_number or ''),
        )
    )

    # ============================================================
    # FEUILLE 1 : SYNTHÈSE PRODUITS
    # ============================================================

    worksheet = workbook.add_worksheet('Récurrence Produits')

    worksheet.hide_gridlines(2)
    worksheet.set_row(0, 24)
    worksheet.set_row(4, 32)

    worksheet.merge_range(
        'A1:K1',
        'ANALYSE DE RÉCURRENCE DES DÉFAUTS PAR PRODUIT',
        title_format,
    )

    worksheet.merge_range(
        'A2:K2',
        (
            f'Export généré le '
            f'{maintenant.strftime("%d/%m/%Y à %H:%M")}'
        ),
        subtitle_format,
    )

    worksheet.merge_range(
        'A3:K3',
        (
            f'Périmètre : Imputations CIM et ALERTE | '
            f'Total réclamations : {total_reclamations}'
        ),
        subtitle_format,
    )

    headers = [
        'Rang',
        'N° Produit',
        'Désignation',
        'Nb Réclamations',
        'Nb Lignes',
        'Quantité Totale',
        'Nb NC',
        'NC Distinctes',
        'Taux Récurrence',
        'Criticité',
        'Actions Recommandées',
    ]

    header_row = 4

    for col, header in enumerate(headers):
        worksheet.write(
            header_row,
            col,
            header,
            header_format,
        )

    row = 5

    for idx, data in enumerate(produits_data, start=1):
        taux = data['taux_recurrence']
        produit = data['produit']

        if taux >= 5:
            taux_format = high_rate_format
        elif taux >= 2:
            taux_format = medium_rate_format
        else:
            taux_format = low_rate_format

        if data['criticite'] == 'CRITIQUE':
            actions = '8D urgent - Analyse des causes racines'
        elif data['criticite'] == 'SURVEILLANCE':
            actions = 'Suivi mensuel - Contrôle renforcé'
        else:
            actions = 'Surveillance normale'

        worksheet.write(
            row,
            0,
            idx,
            cell_center_format,
        )

        worksheet.write(
            row,
            1,
            str(produit.product_number or '-'),
            cell_format,
        )

        worksheet.write(
            row,
            2,
            produit.designation or '-',
            cell_format,
        )

        worksheet.write(
            row,
            3,
            data['nb_reclamations'],
            number_format,
        )

        worksheet.write(
            row,
            4,
            data['nb_lignes'],
            number_format,
        )

        # Conversion en float pour prendre en charge Decimal.
        worksheet.write(
            row,
            5,
            float(data['quantite_totale']),
            number_format,
        )

        worksheet.write(
            row,
            6,
            data['nc_count'],
            number_format,
        )

        worksheet.write(
            row,
            7,
            data['nc_distinctes'],
            number_format,
        )

        # Excel attend une valeur décimale :
        # 5 % doit être écrit sous la forme 0.05.
        worksheet.write(
            row,
            8,
            taux / 100,
            taux_format,
        )

        if data['criticite'] == 'CRITIQUE':
            criticite_format = high_rate_format
        elif data['criticite'] == 'SURVEILLANCE':
            criticite_format = medium_rate_format
        else:
            criticite_format = low_rate_format

        worksheet.write(
            row,
            9,
            data['criticite'],
            criticite_format,
        )

        worksheet.write(
            row,
            10,
            actions,
            cell_format,
        )

        row += 1

    column_widths = [
        6,
        15,
        30,
        14,
        12,
        14,
        10,
        12,
        14,
        14,
        35,
    ]

    for col, width in enumerate(column_widths):
        worksheet.set_column(col, col, width)

    if produits_data:
        worksheet.autofilter(
            header_row,
            0,
            row - 1,
            len(headers) - 1,
        )

    worksheet.freeze_panes(5, 0)

    # ============================================================
    # FEUILLE 2 : TOP 10 PRODUITS
    # ============================================================

    worksheet_top = workbook.add_worksheet('Top 10 Produits')

    worksheet_top.hide_gridlines(2)
    worksheet_top.set_row(0, 24)
    worksheet_top.set_row(3, 30)

    worksheet_top.merge_range(
        'A1:E1',
        'TOP 10 PRODUITS - TAUX DE RÉCURRENCE',
        title_format,
    )

    worksheet_top.merge_range(
        'A2:E2',
        f'Export généré le {maintenant.strftime("%d/%m/%Y")}',
        subtitle_format,
    )

    headers_top = [
        'Rang',
        'Produit',
        'Nb Réclamations',
        'Taux Récurrence',
        'Recommandation',
    ]

    top_header_row = 3

    for col, header in enumerate(headers_top):
        worksheet_top.write(
            top_header_row,
            col,
            header,
            header_secondary_format,
        )

    row = 4

    for idx, data in enumerate(produits_data[:10], start=1):
        produit = data['produit']
        designation = produit.designation or '-'

        produit_libelle = (
            f'{produit.product_number or "-"} - '
            f'{designation[:30]}'
        )

        if data['criticite'] == 'CRITIQUE':
            taux_format = high_rate_format
        elif data['criticite'] == 'SURVEILLANCE':
            taux_format = medium_rate_format
        else:
            taux_format = low_rate_format

        worksheet_top.write(
            row,
            0,
            idx,
            cell_center_format,
        )

        worksheet_top.write(
            row,
            1,
            produit_libelle,
            cell_format,
        )

        worksheet_top.write(
            row,
            2,
            data['nb_reclamations'],
            number_format,
        )

        worksheet_top.write(
            row,
            3,
            data['taux_recurrence'] / 100,
            taux_format,
        )

        worksheet_top.write(
            row,
            4,
            f"Plan d'action {data['criticite'].lower()}",
            cell_format,
        )

        row += 1

    worksheet_top.set_column(0, 0, 6)
    worksheet_top.set_column(1, 1, 40)
    worksheet_top.set_column(2, 2, 18)
    worksheet_top.set_column(3, 3, 18)
    worksheet_top.set_column(4, 4, 30)

    if produits_data:
        worksheet_top.autofilter(
            top_header_row,
            0,
            row - 1,
            len(headers_top) - 1,
        )

    worksheet_top.freeze_panes(4, 0)

    # ============================================================
    # PRÉPARATION OPTIMISÉE DES DÉTAILS NC
    # ============================================================

    # Conserver les 30 produits ayant les taux les plus élevés.
    top_30_data = produits_data[:30]

    top_30_ids = [
        data['produit_id']
        for data in top_30_data
    ]

    # Une seule requête pour récupérer toutes les NC des 30 produits.
    #
    # On ne fait plus une requête par produit.
    details_nc_query = (
        NonConformite.objects
        .filter(
            ligne_reclamation__produit_id__in=top_30_ids,
            ligne_reclamation__produit__actif=True,
            ligne_reclamation__reclamation__imputation__in=imputations,
        )
        .values(
            'ligne_reclamation__produit_id',
            'description',
        )
        .annotate(
            nb_occurences=Count('id'),
            quantite_totale=Sum('quantite'),
            derniere_date=Max(
                'ligne_reclamation__reclamation__date_reclamation'
            ),
        )
        .order_by(
            'ligne_reclamation__produit_id',
            '-nb_occurences',
            'description',
        )
    )

    # Regrouper en Python et garder uniquement les 5 premières NC
    # de chaque produit.
    details_nc_par_produit = defaultdict(list)

    for nc in details_nc_query.iterator(chunk_size=1000):
        produit_id = nc[
            'ligne_reclamation__produit_id'
        ]

        if len(details_nc_par_produit[produit_id]) < 5:
            details_nc_par_produit[produit_id].append(nc)

    # ============================================================
    # FEUILLE 3 : DÉTAIL DES NON-CONFORMITÉS
    # ============================================================

    worksheet_detail = workbook.add_worksheet(
        'Détail Non-Conformités'
    )

    worksheet_detail.hide_gridlines(2)
    worksheet_detail.set_row(0, 24)
    worksheet_detail.set_row(2, 30)

    worksheet_detail.merge_range(
        'A1:F1',
        'DÉTAIL DES NON-CONFORMITÉS PAR PRODUIT',
        title_format,
    )

    headers_detail = [
        'Produit',
        'Description NC',
        'Nb Occurrences',
        'Quantité Totale',
        'Dernière Occurrence',
        'Statut',
    ]

    detail_header_row = 2

    for col, header in enumerate(headers_detail):
        worksheet_detail.write(
            detail_header_row,
            col,
            header,
            header_secondary_format,
        )

    row = 3

    # Respecter l'ordre de classement des produits.
    for data in top_30_data:
        produit = data['produit']

        ncs_produit = details_nc_par_produit.get(
            data['produit_id'],
            [],
        )

        for nc in ncs_produit:
            description = nc['description'] or '-'
            derniere_date = nc['derniere_date']
            nb_occurences = nc['nb_occurences'] or 0
            quantite_totale = nc['quantite_totale'] or 0

            worksheet_detail.write(
                row,
                0,
                str(produit.product_number or '-'),
                cell_format,
            )

            worksheet_detail.write(
                row,
                1,
                description[:50],
                cell_format,
            )

            worksheet_detail.write(
                row,
                2,
                nb_occurences,
                number_format,
            )

            worksheet_detail.write(
                row,
                3,
                float(quantite_totale),
                number_format,
            )

            if derniere_date:
                worksheet_detail.write(
                    row,
                    4,
                    derniere_date.strftime('%d/%m/%Y'),
                    date_format,
                )
            else:
                worksheet_detail.write(
                    row,
                    4,
                    '-',
                    cell_center_format,
                )

            if nb_occurences >= 5:
                worksheet_detail.write(
                    row,
                    5,
                    'Critique',
                    high_rate_format,
                )
            else:
                worksheet_detail.write(
                    row,
                    5,
                    'À surveiller',
                    medium_rate_format,
                )

            row += 1

    worksheet_detail.set_column(0, 0, 15)
    worksheet_detail.set_column(1, 1, 45)
    worksheet_detail.set_column(2, 2, 15)
    worksheet_detail.set_column(3, 3, 16)
    worksheet_detail.set_column(4, 4, 18)
    worksheet_detail.set_column(5, 5, 15)

    if row > 3:
        worksheet_detail.autofilter(
            detail_header_row,
            0,
            row - 1,
            len(headers_detail) - 1,
        )

    worksheet_detail.freeze_panes(3, 0)

    # ============================================================
    # FEUILLE 4 : STATISTIQUES GLOBALES
    # ============================================================

    worksheet_stats = workbook.add_worksheet('Statistiques')

    worksheet_stats.hide_gridlines(2)
    worksheet_stats.set_row(0, 24)

    worksheet_stats.merge_range(
        'A1:C1',
        'STATISTIQUES GLOBALES',
        title_format,
    )

    total_produits_impactes = len(produits_data)

    if total_produits > 0:
        pourcentage_impactes = (
            total_produits_impactes / total_produits
        ) * 100
    else:
        pourcentage_impactes = 0

    produits_critiques = sum(
        1
        for data in produits_data
        if data['criticite'] == 'CRITIQUE'
    )

    produits_surveillance = sum(
        1
        for data in produits_data
        if data['criticite'] == 'SURVEILLANCE'
    )

    produits_faibles = (
        total_produits_impactes
        - produits_critiques
        - produits_surveillance
    )

    statistiques_globales = [
        (
            'Total réclamations (CIM + ALERTE)',
            total_reclamations,
        ),
        (
            'Total produits actifs',
            total_produits,
        ),
        (
            'Produits impactés',
            total_produits_impactes,
        ),
        (
            'Pourcentage produits impactés',
            f'{pourcentage_impactes:.1f}%',
        ),
        (
            '',
            '',
        ),
        (
            'Produits CRITIQUES (taux ≥ 5%)',
            produits_critiques,
        ),
        (
            'Produits en SURVEILLANCE (taux 2-5%)',
            produits_surveillance,
        ),
        (
            'Produits FAIBLES (taux < 2%)',
            produits_faibles,
        ),
    ]

    row = 3

    for label, value in statistiques_globales:
        worksheet_stats.write(
            row,
            0,
            label,
            stats_label_format,
        )

        worksheet_stats.write(
            row,
            1,
            value,
            stats_value_format,
        )

        row += 1

    worksheet_stats.set_column(0, 0, 42)
    worksheet_stats.set_column(1, 1, 18)
    worksheet_stats.set_column(2, 2, 5)

    # ============================================================
    # FINALISATION DU FICHIER
    # ============================================================

    workbook.close()

    # getvalue() évite un appel supplémentaire à seek() + read().
    fichier_excel = output.getvalue()
    output.close()

    nom_fichier = (
        'recurrence_produits_'
        f'{maintenant.strftime("%Y%m%d_%H%M")}.xlsx'
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