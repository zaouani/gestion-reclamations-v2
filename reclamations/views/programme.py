from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from reclamations.models import Client, Programme

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

