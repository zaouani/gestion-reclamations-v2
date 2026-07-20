from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from reclamations.models import Reclamation, Site, UAP

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
