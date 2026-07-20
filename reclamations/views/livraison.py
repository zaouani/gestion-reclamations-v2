from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from reclamations.models import Client, Livraison


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
