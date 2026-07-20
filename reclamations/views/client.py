import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from reclamations.models import Client, SiteClient


logger = logging.getLogger(__name__)

# ================ GESTION DES CLIENTS ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
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
@role_required(['admin', 'quality_manager', 'quality_engineer'])
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
            logger.error(f"Erreur création client: {str(e)}")
            return render(request, 'reclamations/client/creer.html', {
                'anciennes_valeurs': request.POST
            })
    
    # GET : afficher le formulaire
    return render(request, 'reclamations/client/creer.html')

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
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
            messages.error(request, f"Erreur : {e}")
            logger.exception(
                "Erreur lors de la modification du client %s",
                client.pk
            )

    
    return render(request, 'reclamations/client/modifier.html', {
        'client': client,
        'sites_client': client.sites_client.all().order_by('nom')
    })

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
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
