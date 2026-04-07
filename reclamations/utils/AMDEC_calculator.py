from reclamations.models import Reclamation, Client, Produit, LigneReclamation
from django.db.models import Count, Q, F, Avg, Sum, Prefetch
from datetime import timedelta, datetime

def AMDEC(produit_id=None):
    if produit_id:
            produit = get_object_or_404(Produit, pk=produit_id)
            produits = [produit]
    else:
        # Sinon, prendre les 5 produits les plus réclamés
        produits = Produit.objects.filter(lignes_reclamation__reclamation__imputation__in=['CIM']).annotate( nb_reclamations=Count('lignes_reclamation__reclamation', distinct=True)).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:5]
    
        # Analyser les défauts pour chaque produit
        amdec_data = []
        
        for produit in produits:
            # Récupérer toutes les lignes de réclamation pour ce produit
            lignes = LigneReclamation.objects.filter(produit=produit, reclamation__imputation__in=['CIM']).select_related('reclamation')
            if not lignes.exists():
                continue
            # Compter les occurrences de chaque type de défaut
            defauts = lignes.values('description_non_conformite').annotate(
                nb_occurences=Count('id'),
                quantite_totale=Sum('quantite')
            ).order_by('-nb_occurences')
            
            # Analyser chaque défaut
            defauts_analyses = []
            for defaut in defauts:
                description = defaut['description_non_conformite'] or "Défaut non spécifié"
                
                # Récupérer les réclamations associées à ce défaut
                reclamations_defaut = lignes.filter(description_non_conformite=description).values_list('reclamation__numero_reclamation', flat=True).distinct()
                clients_defaut = lignes.filter(description_non_conformite=description).values_list('reclamation__client__nom', flat=True).distinct()
                Programmes = lignes.filter(description_non_conformite=description).values_list('reclamation__programme__nom', flat=True).distinct()
                Programmes = [p for p in Programmes if p] 

                defauts_analyses.append({
                    'description': description,
                    'nb_occurences': defaut['nb_occurences'],
                    'quantite_totale': defaut['quantite_totale'] or 0,
                    'reclamations': list(reclamations_defaut)[:5],  # Limiter à 5 
                    'pourcentage': round(defaut['nb_occurences'] / lignes.count() * 100, 1) if lignes.count() > 0 else 0,
                    'clients':clients_defaut,
                    'Programmes':Programmes
                })
            
            amdec_data.append({
                'produit': produit,
                'total_defauts': lignes.count(),
                'defauts': defauts_analyses,
                'date_analyse': datetime.now()
            })
        
        context = {
            'amdec_data': amdec_data,
            'date_analyse': datetime.now(),
            'produit_unique': produit_id is not None
        }
        return context
