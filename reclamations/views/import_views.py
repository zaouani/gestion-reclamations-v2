from datetime import datetime
from decimal import Decimal

import pandas as pd

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import role_required
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

# ================ IMPORT PRODUITS DEPUIS EXCEL ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_produits_excel(request):
    """Importe des produits depuis un fichier Excel"""
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        # Vérifier l'extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
            return redirect('reclamations:import_produits')
        
        try:
            # Lire le fichier Excel
            df = pd.read_excel(excel_file)
            
            # Vérifier les colonnes requises
            required_columns = ['product_number', 'designation', 'actif']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f"Colonnes manquantes: {', '.join(missing_columns)}")
                return redirect('reclamations:import_produits')
            
            # Statistiques d'import
            total = 0
            crees = 0
            mis_a_jour = 0
            erreurs = []
            
            for index, row in df.iterrows():
                try:
                    product_number = str(row['product_number']).strip()
                    designation = str(row.get('designation', '')).strip() if pd.notna(row.get('designation')) else ''
                    
                    # Déterminer le statut actif
                    actif = True
                    if 'actif' in row and pd.notna(row['actif']):
                        if isinstance(row['actif'], bool):
                            actif = row['actif']
                        elif isinstance(row['actif'], str):
                            actif = row['actif'].lower() in ['oui', 'true', '1', 'actif']
                        else:
                            actif = bool(row['actif'])
                    
                    # Vérifier si le produit existe déjà
                    produit, created = Produit.objects.update_or_create(
                        product_number=product_number,
                        defaults={
                            'designation': designation,
                            'actif': actif
                        }
                    )
                    
                    if created:
                        crees += 1
                    else:
                        mis_a_jour += 1
                    
                    total += 1
                    
                except Exception as e:
                    erreurs.append(f"Ligne {index + 2}: {str(e)}")
            
            # Message de résultat
            if erreurs:
                messages.warning(request, f"Import terminé avec {len(erreurs)} erreur(s).")
                for erreur in erreurs[:5]:  # Afficher les 5 premières erreurs
                    messages.error(request, erreur)
            else:
                messages.success(
                    request, 
                    f"Import réussi ! {crees} produit(s) créé(s), {mis_a_jour} mis à jour."
                )
            
            return redirect('reclamations:liste_produits')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier: {str(e)}")
            return redirect('reclamations:import_produits')
    
    return render(request, 'reclamations/import/produits.html')

# ================ IMPORT CLIENTS DEPUIS EXCEL ================
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_clients_excel(request):
    """Importe des clients depuis un fichier Excel"""
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
            return redirect('reclamations:import_clients')
        
        try:
            df = pd.read_excel(excel_file)
            
            # Vérifier les colonnes requises
            required_columns = ['nom', 'email', 'telephone', 'actif']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f"Colonnes manquantes: {', '.join(missing_columns)}")
                return redirect('reclamations:import_clients')
            
            total = 0
            crees = 0
            mis_a_jour = 0
            erreurs = []
            
            for index, row in df.iterrows():
                try:
                    nom = str(row['nom']).strip()
                    email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else ''
                    telephone = str(row.get('telephone', '')).strip() if pd.notna(row.get('telephone')) else ''
                    
                    actif = True
                    if 'actif' in row and pd.notna(row['actif']):
                        if isinstance(row['actif'], bool):
                            actif = row['actif']
                        else:
                            actif = str(row['actif']).lower() in ['oui', 'true', '1', 'actif']
                    
                    client, created = Client.objects.update_or_create(
                        nom=nom,
                        defaults={
                            'email': email,
                            'telephone': telephone,
                            'actif': actif
                        }
                    )
                    
                    if created:
                        crees += 1
                    else:
                        mis_a_jour += 1
                    
                    total += 1
                    
                except Exception as e:
                    erreurs.append(f"Ligne {index + 2}: {str(e)}")
            
            if erreurs:
                messages.warning(request, f"Import terminé avec {len(erreurs)} erreur(s).")
            else:
                messages.success(request, f"Import réussi ! {crees} client(s) créé(s), {mis_a_jour} mis à jour.")
            
            return redirect('reclamations:liste_clients')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('reclamations:import_clients')
    
    return render(request, 'reclamations/import/clients.html')

# ================ IMPORT RÉCLAMATIONS DEPUIS EXCEL ================
def extraire_produits(produits_raw):
    """Extrait la liste des produits à partir d'une chaîne"""
    if not produits_raw or produits_raw == 'nan':
        return []
    
    # Remplacer les séparateurs courants
    produits_raw = str(produits_raw).replace('\n', ',').replace('\r', ',').replace(';', ',').replace('|', ',')
    
    # Séparer par virgule
    produits = [p.strip() for p in produits_raw.split(',')]
    
    # Filtrer les valeurs vides
    produits = [p for p in produits if p and p != 'nan']
    
    return produits

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def import_reclamations_excel(request):
    """Importe des réclamations depuis un fichier Excel"""
    step = request.POST.get('step', '1')
    
    if request.method == 'POST':
        if step == '1' and request.FILES.get('excel_file'):
            excel_file = request.FILES['excel_file']
            
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "Veuillez uploader un fichier Excel (.xlsx ou .xls)")
                return redirect('reclamations:import_reclamations')
            
            try:
                # Lire le fichier Excel
                df = pd.read_excel(excel_file)
                
                # Convertir les données pour éviter les problèmes de sérialisation
                preview_data = []
                for index, row in df.iterrows():
                    # Convertir chaque ligne en dictionnaire sérialisable
                    row_dict = {}
                    for col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            row_dict[col] = None
                        elif isinstance(value, (pd.Timestamp, datetime)):
                            row_dict[col] = value.strftime('%Y-%m-%d')
                        elif isinstance(value, Decimal):
                            row_dict[col] = float(value)
                        else:
                            row_dict[col] = value
                    
                    # Traiter les produits
                    produits_raw = str(row_dict.get('produit', '')).strip()
                    produits_list = extraire_produits(produits_raw)
                    
                    # Traiter les descriptions de non-conformités (séparées par +)
                    description_raw = str(row_dict.get('description_non_conformite', '')).strip()
                    nc_list = extraire_non_conformites(description_raw)
                    
                    # Construire les données de prévisualisation
                    row_data = {
                        'ligne': index + 2,
                        'numero_reclamation': str(row_dict.get('numero_reclamation', '')).strip(),
                        'date_reclamation': row_dict.get('date_reclamation', ''),
                        'client_nom': str(row_dict.get('client', '')).strip(),
                        'site_nom': str(row_dict.get('site', '')).strip(),
                        'site_client_nom': str(row_dict.get('site_client', '')).strip() if row_dict.get('site_client') else '',
                        'programme_nom': str(row_dict.get('programme', '')).strip() if row_dict.get('programme') else '',
                        'type_nc': str(row_dict.get('type_nc', 'TECHNIQUE')).strip().upper(),
                        'imputation': str(row_dict.get('imputation', 'CIM')).strip().upper(),
                        'etat_4d': str(row_dict.get('etat_4d', 'OUVERT')).strip().upper(),
                        'etat_8d': str(row_dict.get('etat_8d', 'OUVERT')).strip().upper(),
                        'evidence': str(row_dict.get('evidence', '')).strip() if row_dict.get('evidence') else '',
                        'me': bool(row_dict.get('me', False)) if row_dict.get('me') else False,
                        'cloture': bool(row_dict.get('cloture', False)) if row_dict.get('cloture') else False,
                        'date_cloture': row_dict.get('date_cloture', ''),
                        'date_cloture_4d': row_dict.get('date_cloture_4d', ''),
                        'date_cloture_8d': row_dict.get('date_cloture_8d', ''),
                        'decision': str(row_dict.get('decision', '')).strip() if row_dict.get('decision') else '',
                        'nqc': float(row_dict.get('nqc', 0)) if row_dict.get('nqc') else 0,
                        'numero_4d': str(row_dict.get('numero_4d', '')).strip() if row_dict.get('numero_4d') else '',
                        'numero_8d': str(row_dict.get('numero_8d', '')).strip() if row_dict.get('numero_8d') else '',
                        'produits': produits_list,
                        'quantite': int(row_dict.get('quantite', 1)) if row_dict.get('quantite') else 1,
                        'non_conformites': nc_list,  # Liste des NC
                        'commentaire': str(row_dict.get('commentaire', '')).strip() if row_dict.get('commentaire') else '',
                        'uap_nom': str(row_dict.get('uap_concernee', '')).strip() if row_dict.get('uap_concernee') else '',
                        'erreurs': []
                    }
                    
                    # Valider la ligne
                    valider_ligne_import(row_data)
                    preview_data.append(row_data)
                
                # Stocker les données en session pour l'import final
                request.session['import_preview_data'] = preview_data
                
                return render(request, 'reclamations/import/reclamations.html', {
                    'step': 2,
                    'preview_data': preview_data,
                    'total_lignes': len(preview_data)
                })
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la lecture du fichier: {str(e)}")
                return redirect('reclamations:import_reclamations')
        
        elif step == '2' and request.POST.get('confirm_import'):
            # Récupérer les données de prévisualisation
            preview_data = request.session.get('import_preview_data', [])
            
            if not preview_data:
                messages.error(request, "Aucune donnée à importer")
                return redirect('reclamations:import_reclamations')
            
            resultat = {
                'total': len(preview_data),
                'crees': 0,
                'erreurs': [],
                'skips': 0,
                'produits_importes': 0,
                'nc_importes': 0
            }
            
            # Traitement ligne par ligne sans transaction atomique globale
            for row_data in preview_data:
                # Ignorer les lignes avec erreurs
                if row_data.get('erreurs'):
                    resultat['skips'] += 1
                    for err in row_data['erreurs']:
                        resultat['erreurs'].append(f"Ligne {row_data['ligne']}: {err}")
                    continue
                
                try:
                    # Démarrer une transaction pour chaque ligne
                    with transaction.atomic():
                        # Récupérer le client
                        client = Client.objects.filter(nom=row_data['client_nom']).first()
                        if not client:
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Client '{row_data['client_nom']}' non trouvé")
                            resultat['skips'] += 1
                            continue
                        
                        # Récupérer le site client (optionnel)
                        site_client = None
                        if row_data['site_client_nom']:
                            site_client = SiteClient.objects.filter(
                                client=client, 
                                nom=row_data['site_client_nom']
                            ).first()
                        
                        # Récupérer le programme (optionnel)
                        programme = None
                        if row_data['programme_nom']:
                            programme = Programme.objects.filter(
                                clients=client, 
                                nom=row_data['programme_nom']
                            ).first()
                        
                        # Vérifier si la réclamation existe déjà
                        if Reclamation.objects.filter(numero_reclamation=row_data['numero_reclamation']).exists():
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Réclamation {row_data['numero_reclamation']} existe déjà")
                            resultat['skips'] += 1
                            continue
                        
                        # Créer la réclamation
                        reclamation = Reclamation.objects.create(
                            numero_reclamation=row_data['numero_reclamation'],
                            date_reclamation=datetime.strptime(row_data['date_reclamation'], '%Y-%m-%d').date() if row_data['date_reclamation'] else timezone.now().date(),
                            client=client,
                            site_client=site_client,
                            programme=programme,
                            imputation=row_data['imputation'],
                            type_nc=row_data['type_nc'],
                            etat_4d=row_data['etat_4d'],
                            etat_8d=row_data['etat_8d'],
                            evidence=row_data['evidence'],
                            me=row_data['me'],
                            cloture=row_data['cloture'],
                            date_cloture=datetime.strptime(row_data['date_cloture'], '%Y-%m-%d').date() if row_data['date_cloture'] else None,
                            date_cloture_4d=datetime.strptime(row_data['date_cloture_4d'], '%Y-%m-%d').date() if row_data['date_cloture_4d'] else None,
                            date_cloture_8d=datetime.strptime(row_data['date_cloture_8d'], '%Y-%m-%d').date() if row_data['date_cloture_8d'] else None,
                            decision=row_data['decision'],
                            nqc=row_data['nqc'],
                            numero_4d=row_data['numero_4d'],
                            numero_8d=row_data['numero_8d'],
                            createur=request.user
                        )
                        resultat['crees'] += 1
                        
                        # Récupérer le site de production
                        site = Site.objects.filter(nom=row_data['site_nom']).first()
                        if not site:
                            resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Site '{row_data['site_nom']}' non trouvé")
                            resultat['skips'] += 1
                            continue
                        
                        # Récupérer l'UAP (optionnel)
                        uap = None
                        if row_data['uap_nom']:
                            uap = UAP.objects.filter(nom=row_data['uap_nom']).first()
                        
                        # Si pas d'UAP spécifiée mais site trouvé, utiliser l'UAP du site
                        if not uap and site and site.uap:
                            uap = site.uap
                        
                        # Créer les lignes de réclamation pour chaque produit
                        produits_uniques = set(row_data['produits'])
                        for produit_pn in produits_uniques:
                            produit = Produit.objects.filter(product_number=produit_pn).first()
                            if produit:
                                # Vérifier si cette ligne existe déjà
                                ligne_existante = LigneReclamation.objects.filter(
                                    reclamation=reclamation,
                                    produit=produit
                                ).first()
                                
                                if ligne_existante:
                                    # Si la ligne existe déjà, mettre à jour la quantité
                                    ligne_existante.quantite += row_data['quantite']
                                    ligne_existante.save()
                                    
                                    # Ajouter les NC à la ligne existante
                                    for nc_desc in row_data['non_conformites']:
                                        if nc_desc:
                                            NonConformite.objects.create(
                                                ligne_reclamation=ligne_existante,
                                                description=nc_desc,
                                                quantite=row_data['quantite']
                                            )
                                            resultat['nc_importes'] += 1
                                    
                                    resultat['produits_importes'] += 1
                                else:
                                    # Créer une nouvelle ligne
                                    ligne = LigneReclamation.objects.create(
                                        reclamation=reclamation,
                                        produit=produit,
                                        quantite=row_data['quantite'],
                                        description_non_conformite=" | ".join(row_data['non_conformites']) if row_data['non_conformites'] else "",
                                        commentaire=row_data['commentaire'],
                                        site=site,
                                        uap_concernee=uap
                                    )
                                    
                                    # Créer les non-conformités individuelles
                                    for nc_desc in row_data['non_conformites']:
                                        if nc_desc:
                                            NonConformite.objects.create(
                                                ligne_reclamation=ligne,
                                                description=nc_desc,
                                                quantite=row_data['quantite']
                                            )
                                            resultat['nc_importes'] += 1
                                    
                                    resultat['produits_importes'] += 1
                            else:
                                resultat['erreurs'].append(f"Ligne {row_data['ligne']}: Produit '{produit_pn}' non trouvé")
                
                except Exception as e:
                    resultat['erreurs'].append(f"Ligne {row_data.get('ligne', '?')}: {str(e)}")
                    resultat['skips'] += 1
            
            # Nettoyer la session
            request.session.pop('import_preview_data', None)
            
            messages.success(
                request, 
                f"Import terminé! {resultat['crees']} réclamations créées, "
                f"{resultat['produits_importes']} produits importés, "
                f"{resultat['nc_importes']} non-conformités créées."
            )
            
            if resultat['erreurs']:
                messages.warning(request, f"{len(resultat['erreurs'])} erreur(s) rencontrée(s)")
            
            return render(request, 'reclamations/import/reclamations.html', {
                'step': 3,
                'resultat': resultat
            })
    
    return render(request, 'reclamations/import/reclamations.html', {'step': 1})


def extraire_non_conformites(description_raw):
    """
    Extrait les non-conformités d'une chaîne de caractères.
    Les NC peuvent être séparées par '+' ou '|'
    """
    if not description_raw:
        return []
    
    # Remplacer les séparateurs par un séparateur unique
    description_raw = description_raw.replace('|', '+')
    
    # Séparer et nettoyer
    nc_list = []
    for nc in description_raw.split('+'):
        nc_clean = nc.strip()
        if nc_clean:
            nc_list.append(nc_clean)
    
    return nc_list


def valider_ligne_import(row_data):
    """Valide une ligne d'import et ajoute les erreurs dans row_data['erreurs']"""
    erreurs = []
    
    # Validation des champs obligatoires
    if not row_data.get('numero_reclamation'):
        erreurs.append("Numéro de réclamation obligatoire")
    
    if not row_data.get('date_reclamation'):
        erreurs.append("Date de réclamation obligatoire")
    elif row_data.get('date_reclamation'):
        try:
            datetime.strptime(row_data['date_reclamation'], '%Y-%m-%d')
        except ValueError:
            erreurs.append("Format de date invalide (attendu: YYYY-MM-DD)")
    
    if not row_data.get('client_nom'):
        erreurs.append("Client obligatoire")
    
    if not row_data.get('site_nom'):
        erreurs.append("Site obligatoire")
    
    if not row_data.get('produits'):
        erreurs.append("Au moins un produit obligatoire")
    
    # Validation des choix
    type_nc_valid = [choice[0] for choice in Reclamation.TYPE_NC_CHOICES]
    if row_data.get('type_nc') not in type_nc_valid:
        #print(row_data.get('type_nc'))
        erreurs.append(f"Type NC invalide. Valeurs acceptées: {', '.join(type_nc_valid)}")
    
    imputation_valid = [choice[0] for choice in Reclamation.IMPUTATION_CHOICES]
    if row_data.get('imputation') not in imputation_valid:
        erreurs.append(f"Imputation invalide. Valeurs acceptées: {', '.join(imputation_valid)}")
    
    etat_valid = [choice[0] for choice in Reclamation.ETAT_CHOICES]
    if row_data.get('etat_4d') not in etat_valid:
        erreurs.append(f"État 4D invalide. Valeurs acceptées: {', '.join(etat_valid)}")
    
    if row_data.get('etat_8d') not in etat_valid:
        erreurs.append(f"État 8D invalide. Valeurs acceptées: {', '.join(etat_valid)}")
    
    row_data['erreurs'] = erreurs
    return len(erreurs) == 0




