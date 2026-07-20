from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from reclamations.models import Produit

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
