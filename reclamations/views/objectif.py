from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.models import ObjectifsAnnuel, Site



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
