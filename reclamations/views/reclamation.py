import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.utils.dashboard_stats import DashboardStats
from reclamations.models import (
    Client,
    LigneReclamation,
    NonConformite,
    Produit,
    Programme,
    Reclamation,
    Site,
    SiteClient,
    UAP,
)


logger = logging.getLogger(__name__)

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
            logger.exception(    "Erreur lors de la création de la réclamation")

            
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
            logger.exception(  "Erreur lors de la modification de la réclamation %s", pk,)

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
def api_reclamations_client_mois(request):
    """API pour récupérer les données de réclamations par mois pour un client"""
    client_id = request.GET.get('client_id')
    
    stats = DashboardStats()
    
    if client_id and client_id != 'all':
        data = stats.get_reclamations_par_client_mois(client_id=int(client_id))
    else:
        data = stats.get_reclamations_par_client_mois()
    
    return JsonResponse(data)