# reclamations/dashboard_stats.py
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
import json
from .models import Reclamation, Client, UAP, Produit, ObjectifsAnnuel, LigneReclamation
from .utils import PPMCalculator
from collections import defaultdict


class DashboardStats:
    """Classe pour calculer toutes les statistiques du dashboard"""
    
    def __init__(self):
        self.annee_courante = timezone.now().year
        self.today = timezone.now().date()
        self.date_limite_30j = self.today - timedelta(days=30)
        self.date_debut_12m = self.today - timedelta(days=365)
    
    def get_global_stats(self):
        """Statistiques globales"""
        total = Reclamation.objects.count()
        ouvertes = Reclamation.objects.filter(cloture=False).count()
        cloturees = Reclamation.objects.filter(cloture=True).count()
        
        # Taux de clôture
        taux_cloture = (cloturees / total * 100) if total > 0 else 0
        
        # Taux de réactivité (clôturées dans les 30 jours)
        reactives = Reclamation.objects.filter(
            cloture=True,
            date_cloture__gte=self.date_limite_30j,
            date_cloture__lte=self.today
        ).count()
        taux_reactivite = (reactives / cloturees * 100) if cloturees > 0 else 0
        
        return {
            'total': total,
            'ouvertes': ouvertes,
            'cloturees': cloturees,
            'taux_cloture': round(taux_cloture, 1),
            'taux_reactivite': round(taux_reactivite, 1)
        }
    
    def get_reclamations_par_client(self):
        """Répartition des réclamations par client (Top 10)"""
        clients = Client.objects.filter(actif=True).annotate(
            nb_reclamations=Count('reclamations')
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:10]
        
        return {
            'labels': [c.nom for c in clients],
            'data': [c.nb_reclamations for c in clients]
        }
    
    def get_reclamations_par_uap(self):
        """Répartition des réclamations par UAP"""
        uaps = UAP.objects.annotate(
            nb_reclamations=Count('lignes_reclamation__reclamation', distinct=True)
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')
        
        return {
            'labels': [u.nom for u in uaps],
            'data': [u.nb_reclamations for u in uaps]
        }
    
    def get_reclamations_par_mois(self):
        """Évolution mensuelle des réclamations (12 derniers mois)"""
        mois_data = Reclamation.objects.filter(
            date_reclamation__gte=self.date_debut_12m
        ).annotate(
            mois=TruncMonth('date_reclamation')
        ).values('mois').annotate(
            total=Count('id')
        ).order_by('mois')
        
        labels = []
        data = []
        for item in mois_data:
            if item['mois']:
                labels.append(item['mois'].strftime('%B %Y').capitalize())
                data.append(item['total'])
        
        return {'labels': labels, 'data': data}
    
    def get_typologie_par_mois(self):
        """Typologie des réclamations par mois"""
        type_nc_list = [type[0] for type in Reclamation.TYPE_NC_CHOICES]
        type_nc_labels = [type[1] for type in Reclamation.TYPE_NC_CHOICES]
        
        # Récupérer d'abord tous les mois
        reclamations_par_mois = Reclamation.objects.filter(
            date_reclamation__gte=self.date_debut_12m
        ).annotate(
            mois=TruncMonth('date_reclamation')
        ).values('mois').annotate(
            total=Count('id')
        ).order_by('mois')
        
        typologie = []
        for i, type_nc in enumerate(type_nc_list):
            data_par_mois = Reclamation.objects.filter(
                date_reclamation__gte=self.date_debut_12m,
                type_nc=type_nc
            ).annotate(
                mois=TruncMonth('date_reclamation')
            ).values('mois').annotate(
                total=Count('id')
            ).order_by('mois')
            
            data_dict = {}
            for item in data_par_mois:
                if item['mois']:
                    mois_key = item['mois'].strftime('%Y-%m')
                    data_dict[mois_key] = item['total']
            
            mois_data_type = []
            for item in reclamations_par_mois:
                if item['mois']:
                    mois_key = item['mois'].strftime('%Y-%m')
                    mois_data_type.append(data_dict.get(mois_key, 0))
                else:
                    mois_data_type.append(0)
            
            typologie.append({
                'label': type_nc_labels[i],
                'data': mois_data_type
            })
        
        return typologie
    
    def get_repartition_imputation(self):
            """Répartition par imputation"""
            imputations = Reclamation.objects.values('imputation').annotate(
                total=Count('id')
            ).order_by('-total')
            
            labels = []
            data = []
            for item in imputations:
                if item['imputation']:
                    label = dict(Reclamation.IMPUTATION_CHOICES).get(item['imputation'], item['imputation'])
                    labels.append(label)
                    data.append(item['total'])
            
            print(f"Nombre d'imputations: {len(labels)}")
            
            return {'labels': labels, 'data': data}
    
    def get_delai_moyen_cloture(self):
        """Délai moyen de clôture en jours"""
        reclamations_closes = Reclamation.objects.filter(
            cloture=True,
            date_cloture__isnull=False,
            date_reclamation__isnull=False
        )
        
        total_jours = 0
        count = 0
        for rec in reclamations_closes:
            delta = rec.date_cloture - rec.date_reclamation
            total_jours += delta.days
            count += 1
        
        return round(total_jours / count, 1) if count > 0 else 0
    
    def get_type_nc_stats(self):
        """Statistiques par type de NC"""
        types = Reclamation.objects.values('type_nc').annotate(
            total=Count('id')
        ).order_by('-total')
        
        stats = []
        for item in types:
            if item['type_nc']:
                label = dict(Reclamation.TYPE_NC_CHOICES).get(item['type_nc'], item['type_nc'])
                stats.append({'label': label, 'total': item['total']})
        
        return stats
    
    def get_ppm_stats(self):
        """Statistiques PPM"""
        ppm_calculator = PPMCalculator(annee=self.annee_courante)
        
        ppm_global_data = ppm_calculator.get_ppm_global()
        ppm_clients = ppm_calculator.get_all_clients_ppm()
        ppm_evolution = ppm_calculator.get_ppm_mensuel()
        
        # Données pour les graphiques
        ppm_labels = [client['client'] for client in ppm_clients[:10]]
        ppm_data = [client['ppm'] for client in ppm_clients[:10]]
        
        return {
            'global': ppm_global_data['ppm'],
            'clients': ppm_clients[:10],
            'evolution': ppm_evolution,
            'labels': ppm_labels,
            'data': ppm_data
        }
    
    def get_objectifs_annee(self):
        """Objectifs de l'année courante"""
        objectifs = ObjectifsAnnuel.objects.filter(
            annee=self.annee_courante
        ).select_related('site__uap').order_by('site__nom')
        
        if objectifs.exists():
            moyennes = {
                'rebut': objectifs.aggregate(Avg('objectif_rebut'))['objectif_rebut__avg'] or 0,
                'ppm': objectifs.aggregate(Avg('objectif_ppm_externe'))['objectif_ppm_externe__avg'] or 0,
                'rework': objectifs.aggregate(Avg('objectif_rework'))['objectif_rework__avg'] or 0,
            }
        else:
            moyennes = {'rebut': 0, 'ppm': 0, 'rework': 0}
        
        return {
            'objectifs': objectifs,
            'moyennes': moyennes
        }
   
    def get_nqc_par_mois(self):
        """
        Calcul du NQC (Non-Quality Cost) par mois
        Somme des coûts NQC des réclamations pour chaque mois
        """
        nqc_par_mois = Reclamation.objects.filter(
            date_reclamation__gte=self.date_debut_12m
        ).annotate(
            mois=TruncMonth('date_reclamation')
        ).values('mois').annotate(
            nombre=Count('id'),                    # Nombre de réclamations
            cout_total=Sum('nqc'),                 # Somme des coûts NQC
            cout_moyen=Avg('nqc')                  # Coût moyen par réclamation
        ).order_by('mois')
        
        labels = []
        data_nombre = []
        data_cout = []
        data_cout_moyen = []
        
        for item in nqc_par_mois:
            if item['mois']:
                labels.append(item['mois'].strftime('%B %Y').capitalize())
                data_nombre.append(item['nombre'])
                
                # Convertir en float si nécessaire
                cout_val = float(item['cout_total']) if item['cout_total'] else 0
                data_cout.append(cout_val)
                
                cout_moyen_val = float(item['cout_moyen']) if item['cout_moyen'] else 0
                data_cout_moyen.append(cout_moyen_val)
        
        # Calculer les totaux
        total_nqc = sum(data_cout)
        total_reclamations = sum(data_nombre)
        
        return {
            'labels': labels,
            'data_nombre': data_nombre,           # Nombre de réclamations par mois
            'data_cout': data_cout,               # Coût NQC total par mois
            'data_cout_moyen': data_cout_moyen,   # Coût NQC moyen par mois
            'total_nqc': total_nqc,               # Coût NQC total
            'total_reclamations': total_reclamations,
            'cout_moyen_global': total_nqc / total_reclamations if total_reclamations > 0 else 0
        }
    
    def get_nqc_par_client(self):
        """
        Calcul du NQC par client (Top 10)
        """
        nqc_client = Reclamation.objects.filter(
            date_reclamation__year=self.annee_courante
        ).values('client__nom').annotate(
            nombre=Count('id'),
            cout_total=Sum('nqc'),
            cout_moyen=Avg('nqc')
        ).order_by('-cout_total')[:10]
        
        return list(nqc_client)
    
    def get_nqc_par_type(self):
        """
        Calcul du NQC par type de NC
        """
        nqc_type = Reclamation.objects.filter(
            date_reclamation__year=self.annee_courante
        ).values('type_nc').annotate(
            nombre=Count('id'),
            cout_total=Sum('nqc')
        ).order_by('-cout_total')
        
        stats = []
        for item in nqc_type:
            if item['type_nc']:
                label = dict(Reclamation.TYPE_NC_CHOICES).get(item['type_nc'], item['type_nc'])
                stats.append({
                    'label': label,
                    'nombre': item['nombre'],
                    'cout': float(item['cout_total']) if item['cout_total'] else 0
                })
        
        return stats
    
    def get_taux_recurrence_produits(self, top_n=10):
        """
        Calcule le taux de récurrence des défauts par produit
        Retourne les produits les plus récurrents avec leurs statistiques
        """
        # Compter le nombre de réclamations par produit
        produits_stats = Produit.objects.annotate(
            nb_reclamations=Count('lignes_reclamation', distinct=True),
            quantite_totale=Sum('lignes_reclamation__quantite'),
            nb_lignes=Count('lignes_reclamation')
        ).filter(
            nb_reclamations__gt=0
        ).order_by('-nb_reclamations')[:top_n]
        
        # Nombre total de réclamations
        total_reclamations = Reclamation.objects.count()
        
        # Préparer les données
        resultats = []
        for produit in produits_stats:
            taux = (produit.nb_reclamations / total_reclamations * 100) if total_reclamations > 0 else 0
            
            resultats.append({
                'produit_id': produit.id,
                'product_number': produit.product_number,
                'designation': produit.designation,
                'nb_reclamations': produit.nb_reclamations,
                'quantite_totale': produit.quantite_totale or 0,
                'nb_lignes': produit.nb_lignes,
                'taux_recurrence': round(taux, 2)
            })
        
        return resultats
    
    def get_top_produits_recurrents(self, top_n=5):
        """Récupère les produits les plus récurrents"""
        # Compter les réclamations par produit
        produits = Produit.objects.annotate(
            nb_reclamations=Count('lignes_reclamation__reclamation', distinct=True),
            quantite_totale=Sum('lignes_reclamation__quantite')
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:top_n]
        
        total_reclamations = Reclamation.objects.count()
        
        resultats = []
        for produit in produits:
            taux = (produit.nb_reclamations / total_reclamations * 100) if total_reclamations > 0 else 0
            resultats.append({
                'id': produit.id,
                'product_number': produit.product_number,
                'designation': produit.designation,
                'nb_reclamations': produit.nb_reclamations,
                'quantite_totale': produit.quantite_totale or 0,
                'taux_recurrence': round(taux, 2)
            })
        
        return resultats
    
    def get_taux_recurrence_produits_par_periode(self):
        """Calcule l'évolution du taux de récurrence par période"""
        from django.db.models.functions import TruncMonth
        
        # Récupérer les 12 derniers mois
        date_debut = self.date_debut_12m
        
        # Compter les réclamations par produit et par mois
        data = LigneReclamation.objects.filter(
            reclamation__date_reclamation__gte=date_debut
        ).annotate(
            mois=TruncMonth('reclamation__date_reclamation')
        ).values('produit__product_number', 'mois').annotate(
            nb_reclamations=Count('reclamation', distinct=True)
        ).order_by('mois', '-nb_reclamations')
        
        # Organiser les données par produit
        evolution = {}
        for item in data:
            if item['mois']:
                produit = item['produit__product_number']
                mois_key = item['mois'].strftime('%B %Y').capitalize()
                
                if produit not in evolution:
                    evolution[produit] = []
                
                evolution[produit].append({
                    'periode': mois_key,
                    'taux_recurrence': item['nb_reclamations']
                })
        
        return evolution
 
    def get_all_stats(self):
        """Récupère toutes les statistiques"""
        return {
            'global': self.get_global_stats(),
            'clients': self.get_reclamations_par_client(),
            'uap': self.get_reclamations_par_uap(),
            'mois': self.get_reclamations_par_mois(),
            'typologie': self.get_typologie_par_mois(),
            'imputation': self.get_repartition_imputation(),
            'delai_moyen': self.get_delai_moyen_cloture(),
            'type_nc': self.get_type_nc_stats(),
            'ppm': self.get_ppm_stats(),
            'objectifs': self.get_objectifs_annee(),
            'nqc': {
                'mois': self.get_nqc_par_mois(),
                'par_client': self.get_nqc_par_client(),
                'par_type': self.get_nqc_par_type()
            },
            'recurrence_produits': self.get_taux_recurrence_produits(),
            'top_produits_recurrents': self.get_top_produits_recurrents(),
        }