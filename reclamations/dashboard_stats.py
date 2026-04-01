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
 
    def get_reclamations_par_site_client(self):
        """Nombre de réclamations par site client (Top 10)"""
        from .models import SiteClient, LigneReclamation
        
        # Compter les réclamations par site client
        sites_client = SiteClient.objects.filter(actif=True).annotate(
            nb_reclamations=Count('reclamations')
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:10]
        
        labels = []
        data = []
        
        for site in sites_client:
            labels.append(f"{site.nom} ({site.client.nom})")
            data.append(site.nb_reclamations)
        
        return {
            'labels': labels,
            'data': data
        }

    def _est_jour_ouvre(self, date):
        """Vérifie si une date est un jour ouvré"""
        return date.weekday() < 5  # 0=lundi, 4=vendredi

    def _calculer_date_limite(self, date_debut, jours_ouvres):
        """Calcule la date limite en jours ouvrés à partir de la date de réclamation"""
        from datetime import timedelta
        
        # Commencer à compter à partir du jour suivant la date de réclamation
        date_courante = date_debut
        jours_restants = jours_ouvres
        
        while jours_restants > 0:
            date_courante += timedelta(days=1)
            if date_courante.weekday() < 5:  # Lundi à vendredi
                jours_restants -= 1
        
        return date_courante

    def get_taux_reactivite_par_uap(self):
        """
        Calcule le taux de réactivité par UAP par mois
        """
        
        # Récupérer toutes les données
        lignes = LigneReclamation.objects.filter(
            uap_concernee__isnull=False
        ).select_related('reclamation', 'uap_concernee').values(
            'reclamation__id',
            'reclamation__numero_reclamation',
            'reclamation__date_reclamation',
            'reclamation__etat_4d',
            'reclamation__date_cloture_4d',
            'reclamation__etat_8d',
            'reclamation__date_cloture_8d',
            'uap_concernee__nom'
        )
        
        print(f"Nombre de lignes trouvées: {len(lignes)}")
        
        # Structure
        stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
            'total_reclamations': 0,
            'cloture_4d_delai': 0,
            'cloture_8d_delai': 0,
            'details': []  # Pour le débogage
        })))
        
        reclamations_traitees = set()
        
        for ligne in lignes:
            rec_id = ligne['reclamation__id']
            rec_num = ligne['reclamation__numero_reclamation']
            rec_date = ligne['reclamation__date_reclamation']
            uap = ligne['uap_concernee__nom']
            if not rec_date:
                continue
                
            annee = rec_date.year
            mois = rec_date.month
            
            key = (annee, mois, uap, rec_id)
            
            if key not in reclamations_traitees:
                reclamations_traitees.add(key)
                
                
                # Vérifier état 4D
                est_reactif_4d = False
                if ligne['reclamation__etat_4d'] == 'CLOTURE' and ligne['reclamation__date_cloture_4d']:
                    date_limite = self._calculer_date_limite(rec_date, 2)
                    if ligne['reclamation__date_cloture_4d'] <= date_limite:
                        stats[annee][mois][uap]['cloture_4d_delai'] += 1
                        stats[annee][mois][uap]['total_reclamations'] += 1
                        est_reactif_4d = True
                else: 
                    date_limite = self._calculer_date_limite(rec_date, 2)
                    date_actuelle = timezone.now().date()
                    if date_limite<date_actuelle:
                        stats[annee][mois][uap]['total_reclamations'] += 1
                
                
                # Vérifier état 8D
                est_reactif_8d = False
                if ligne['reclamation__etat_8d'] == 'CLOTURE' and ligne['reclamation__date_cloture_8d']:
                    date_limite = self._calculer_date_limite(rec_date, 10)
                    if ligne['reclamation__date_cloture_8d'] <= date_limite:
                        stats[annee][mois][uap]['cloture_8d_delai'] += 1
                        stats[annee][mois][uap]['total_reclamations'] += 1
                        est_reactif_8d = True
                    else: 
                        date_limite = self._calculer_date_limite(rec_date, 2)
                        date_actuelle = timezone.now().date()
                        if date_limite<date_actuelle:
                            stats[annee][mois][uap]['total_reclamations'] += 1
                
                       
        # Construire le résultat final
        resultats_par_annee = {}
        
        for annee in sorted(stats.keys(), reverse=True):
            mois_data = stats[annee]
            mois_labels = []
            data_mensuelle = {}
            uap_noms_set = set()
            
            for mois in sorted(mois_data.keys()):
                mois_nom = self._get_mois_nom(mois, annee)
                mois_labels.append(mois_nom)
                
                donnees_uap = {}
                
                for uap, valeurs in mois_data[mois].items():
                    uap_noms_set.add(uap)
                    
                    total_reclamations = valeurs['total_reclamations']
                    cloture_4d = valeurs['cloture_4d_delai']
                    cloture_8d = valeurs['cloture_8d_delai']
                    
                    total_etats = total_reclamations
                    reactif_etats = cloture_4d + cloture_8d
                    
                    if total_etats > 0:
                        taux = (reactif_etats / total_etats) * 100
                    else:
                        taux = 100
                    
                    donnees_uap[uap] = round(taux, 1)
                
                data_mensuelle[mois_nom] = donnees_uap
            
            uap_noms = sorted(uap_noms_set)
            
            for mois_nom in mois_labels:
                if mois_nom not in data_mensuelle:
                    data_mensuelle[mois_nom] = {uap: 0 for uap in uap_noms}
                else:
                    for uap in uap_noms:
                        if uap not in data_mensuelle[mois_nom]:
                            taux=100
                            data_mensuelle[mois_nom][uap] = round(taux, 1)
            
            resultats_par_annee[annee] = {
                'mois_labels': mois_labels,
                'uap_noms': uap_noms,
                'data': data_mensuelle
            }
        
        return resultats_par_annee

    def _get_mois_nom(self, mois_num, annee):
        """
        Retourne le nom du mois
        """
        import calendar
        return f"{calendar.month_name[mois_num]} {annee}"
    
    def get_reclamations_par_client_mois(self, client_id=None):
        """
        Calcule le nombre de réclamations par mois pour un client spécifique
        Si client_id est None, retourne les données pour tous les clients
        """
        
        # Filtrer par client si spécifié
        queryset = Reclamation.objects.all()
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        # Grouper par mois
        data = queryset.annotate(
            mois=TruncMonth('date_reclamation')
        ).values('mois').annotate(
            total=Count('id')
        ).order_by('mois')
        
        # Préparer les données
        mois_labels = []
        mois_data = []
        
        for item in data:
            if item['mois']:
                mois_labels.append(item['mois'].strftime('%B %Y').capitalize())
                mois_data.append(item['total'])
        
        # Si un client spécifique est sélectionné, récupérer son nom
        client_nom = None
        if client_id:
            client = Client.objects.filter(id=client_id).first()
            client_nom = client.nom if client else None
        
        return {
            'labels': mois_labels,
            'data': mois_data,
            'client_nom': client_nom,
            'client_id': client_id
        }

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
            'reclamations_par_site_client': self.get_reclamations_par_site_client(),
            'taux_reactivite_par_uap': self.get_taux_reactivite_par_uap(),
            'reclamations_par_client_mois': self.get_reclamations_par_client_mois(),
        }