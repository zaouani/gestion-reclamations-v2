import json
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.decorators import role_required
from reclamations.utils.dashboard_stats import DashboardStats
from reclamations.models import Action8D, Client, Reclamation, UAP

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer','viewer'])
def dashboard(request):
    """Tableau de bord avec toutes les statistiques"""
    
    # Initialiser le calculateur de statistiques
    stats = DashboardStats(request.GET)
    
    # Récupérer toutes les statistiques
    data = stats.get_all_stats()

    # Extraire les données NQC
    nqc_data = data.get('nqc', {}).get('mois', {})

    # Récupérer les données pour le graphique par site client
    site_client_data = data.get('reclamations_par_site_client', {})

    # Récupérer tous les clients pour le filtre
    clients = Client.objects.filter(actif=True).order_by('nom')
    years = Reclamation.objects.dates('date_reclamation', 'year', order='DESC')
    uaps = UAP.objects.all().order_by('nom')

    imputations = [
        {'id': key, 'nom': value}
        for key, value in Reclamation.IMPUTATION_CHOICES
    ]

    selected_client = request.GET.get('client', '')
    selected_year = request.GET.get('year', '')
    selected_uap = request.GET.get('uap', '')
    selected_imputation = request.GET.get('imputation', '')

    selected_client_name = None
    if selected_client:
        client_obj = Client.objects.filter(id=selected_client).first()
        selected_client_name = client_obj.nom if client_obj else None

    selected_uap_name = None
    if selected_uap:
        uap_obj = UAP.objects.filter(id=selected_uap).first()
        selected_uap_name = uap_obj.nom if uap_obj else None

    selected_imputation_name = None
    if selected_imputation:
        selected_imputation_name = dict(Reclamation.IMPUTATION_CHOICES).get(
            selected_imputation,
            selected_imputation
        )

    has_filters = any([
        selected_client,
        selected_year,
        selected_uap,
        selected_imputation
    ])
    
    # Convertir les Decimal en float pour NQC par client
    nqc_par_client_raw = data.get('nqc', {}).get('par_client', [])
    nqc_par_client = []
    for item in nqc_par_client_raw:
        nqc_par_client.append({
            'client__nom': item.get('client__nom', item.get('client_nom', 'Client inconnu')),
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
        
    # Récupérer les données de réactivité par UAP
    reactivite_uap_data = data.get('taux_reactivite_par_uap', {})

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
        'moyenne_reactivite': round(data.get('taux_reactivite', 0), 1),
        
        # Filtres dashboard
        'clients': clients,
        'years': years,
        'uaps': uaps,
        'imputations': imputations,

        'selected_client': selected_client,
        'selected_year': selected_year,
        'selected_uap': selected_uap,
        'selected_imputation': selected_imputation,

        'selected_client_name': selected_client_name,
        'selected_uap_name': selected_uap_name,
        'selected_imputation_name': selected_imputation_name,
        'has_filters': has_filters,

    }
    
    return render(request, 'reclamations/dashboard.html', context)

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

def mini_kpi_stats(request):
    """Calcule les KPI avec variations pour le dashboard"""
    dashboard_stats = DashboardStats()
    today = timezone.now().date()

    # ========== STATISTIQUES GLOBALES ==========
    date_limite_12m = datetime.now().date() - timedelta(days=365)
    
    total_reclamations = Reclamation.objects.filter(date_reclamation__gte=date_limite_12m).count()
    ouvertes = Reclamation.objects.filter(cloture=False).count()
    cloturees = Reclamation.objects.filter(cloture=True).count()
    taux_cloture = (cloturees / total_reclamations * 100) if total_reclamations > 0 else 0
    reclamations_sans_8d = Reclamation.objects.filter(cloture=False, huitd_non_applicable=False, imputation='CIM').exclude(huitd__isnull=False).count()
    
    # Réclamations ouvertes AVEC 8D en cours
    reclamations_avec_8d = Reclamation.objects.filter(cloture=False, huitd__isnull=False, huitd_non_applicable=False).exclude(huitd__etat='CLOTURE').count()
    SECURISATION_EN_COURS = Reclamation.objects.filter(cloture=False, etat_4d='EN_COURS').count()

    # Taux de réactivité (clôturées dans les 30 jours)
    reactivite_uap_data, _ = dashboard_stats.get_taux_reactivite_par_uap()
    
    mois_prec = today.replace(day=1) - relativedelta(months=1)

    label_courant = dashboard_stats._get_mois_nom(today.month, today.year)
    label_precedent = dashboard_stats._get_mois_nom(mois_prec.month, mois_prec.year)

    data_courant = reactivite_uap_data.get(today.year, {}).get('data', {}).get(label_courant, {})
    data_precedent = reactivite_uap_data.get(mois_prec.year, {}).get('data', {}).get(label_precedent, {})

    taux_courant = round(sum(data_courant.values()) / len(data_courant), 1) if data_courant else 0
    taux_precedent = round(sum(data_precedent.values()) / len(data_precedent), 1) if data_precedent else 0


    actions_encours = Action8D.objects.select_related(
            'huitd__reclamation__client',
        ).filter(
            statut__in=['PLANIFIE', 'EN_COURS']
        ).count()
    # Délai moyen de clôtureS
    delai_moyen = dashboard_stats.get_delai_moyen_cloture()
    
    
    # Taux de récurrence
    recurrence_data = dashboard_stats.get_taux_recurrence_globale()
    taux_recurrence = recurrence_data.get('taux', 0)
    
    # ========== VARIATIONS ==========
    
    # Variation Total Réclamations (vs hier)
    variation_total = Reclamation.objects.filter(date_creation__date=today).count()
    
    # Variation Ouvertes (vs hier)
    variation_ouvertes = Reclamation.objects.filter(cloture=False, date_creation__date=today).count()
    
    # Variation Taux Réactivité (vs mois dernier)

    variation_reactivite = taux_courant-taux_precedent 
    
    # Variation Délai Moyen (évolution en pourcentage)
    delai_precedent = 10  # Valeur par défaut, à ajuster selon historique

    variation_delai = ((delai_moyen - delai_precedent) / delai_precedent * 100) if delai_precedent > 0 else 0
    
   
    # Variation Taux Récurrence (vs mois dernier)
    taux_recurrence_precedent = 0  # Valeur par défaut, à ajuster
    
    variation_recurrence = taux_recurrence - taux_recurrence_precedent
    
    stats = {
        'total_reclamations': total_reclamations,
        'ouvertes': ouvertes,
        'taux_cloture': round(taux_cloture, 1),
        'taux_reactivite': taux_courant,
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
    
    # Récupérer les KPI
    kpi_data = mini_kpi_stats(request)
    
    context = {
        'kpi_stats': kpi_data['stats'],
        'kpi_variation': kpi_data['variation'],
        'current_year': kpi_data['current_year'],
        'now': timezone.now()
    }
    return render(request, 'reclamations/dashboard/big_screen_dashboard.html', context)

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