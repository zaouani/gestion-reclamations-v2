# reclamations/dashboard_stats.py
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
import json
from reclamations.models import Reclamation, Client, UAP, Produit, ObjectifsAnnuel, LigneReclamation, NonConformite, SiteClient
from . import PPMCalculator
from collections import defaultdict
from dateutil.relativedelta import relativedelta

class DashboardStats:
    """Classe pour calculer toutes les statistiques du dashboard"""
    
    def __init__(self, filters=None):
        self.annee_courante = timezone.now().year
        self.today = timezone.now().date()
        self.date_limite_30j = self.today - timedelta(days=30)
        self.date_debut_12m = self.today - timedelta(days=365)

        # Filtres dashboard
        self.filters = filters or {}

        self.selected_client = self.filters.get('client') or ''
        self.selected_year = self.filters.get('year') or ''
        self.selected_uap = self.filters.get('uap') or ''
        self.selected_imputation = self.filters.get('imputation') or ''

    def _filter_reclamations(self, queryset):
        """
        Applique les filtres dashboard sur un queryset Reclamation.
        Ne modifie pas la logique des fonctions, filtre seulement les données source.
        """
        if self.selected_client:
            queryset = queryset.filter(client_id=self.selected_client)

        if self.selected_year:
            queryset = queryset.filter(date_reclamation__year=self.selected_year)
        else:
            # Par défaut, filtrer sur les 12 derniers mois
            queryset = queryset.filter(date_reclamation__gte=self.date_debut_12m)

        if self.selected_uap:
            queryset = queryset.filter(
                lignes__uap_concernee_id=self.selected_uap
            ).distinct()

        if self.selected_imputation:
            queryset = queryset.filter(imputation=self.selected_imputation)

        return queryset

    def _filter_lignes_reclamation(self, queryset):
        """
        Applique les filtres dashboard sur un queryset LigneReclamation.
        """
        if self.selected_client:
            queryset = queryset.filter(reclamation__client_id=self.selected_client)

        if self.selected_year:
            queryset = queryset.filter(reclamation__date_reclamation__year=self.selected_year)
        else:
            # Par défaut, filtrer sur les 12 derniers mois
            queryset = queryset.filter(reclamation__date_reclamation__gte=self.date_debut_12m)

        if self.selected_uap:
            queryset = queryset.filter(uap_concernee_id=self.selected_uap)

        if self.selected_imputation:
            queryset = queryset.filter(reclamation__imputation=self.selected_imputation)

        return queryset

    def _filter_non_conformites(self, queryset):
        """
        Applique les filtres dashboard sur un queryset NonConformite.
        """
        if self.selected_client:
            queryset = queryset.filter(ligne_reclamation__reclamation__client_id=self.selected_client)

        if self.selected_year:
            queryset = queryset.filter(ligne_reclamation__reclamation__date_reclamation__year=self.selected_year)
        else:
            # Par défaut, filtrer sur les 12 derniers mois
            queryset = queryset.filter(ligne_reclamation__reclamation__date_reclamation__gte=self.date_debut_12m)
        if self.selected_uap:
            queryset = queryset.filter(ligne_reclamation__uap_concernee_id=self.selected_uap)

        if self.selected_imputation:
            queryset = queryset.filter(ligne_reclamation__reclamation__imputation=self.selected_imputation)

        return queryset

    def get_global_stats(self):
        """Statistiques globales"""
        """Statistiques globales sur les 12 derniers mois"""

        # Filtrer les réclamations selon les filtres dashboard
        qs_base = self._filter_reclamations( Reclamation.objects.all() )
        total = qs_base.count()
        ouvertes = qs_base.filter(cloture=False).count()
        cloturees = qs_base.filter(cloture=True).count()
        
        # Taux de clôture
        taux_cloture = (cloturees / total * 100) if total > 0 else 0
        
        
        return {
            'total': total,
            'ouvertes': ouvertes,
            'cloturees': cloturees,
            'taux_cloture': round(taux_cloture, 1),
        }
    
    def get_reclamations_par_client(self):
        """Répartition des réclamations par client (Top 10)"""
        qs = self._filter_reclamations(Reclamation.objects.all())

        clients = Client.objects.filter(
            actif=True,
            reclamations__in=qs
        ).annotate(
            nb_reclamations=Count('reclamations', filter=Q(reclamations__in=qs), distinct=True)
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:10]
        
        return {
            'labels': [c.nom for c in clients],
            'data': [c.nb_reclamations for c in clients]
        }
    
    def get_reclamations_par_uap(self):
        """Répartition des réclamations par UAP"""
        lignes = self._filter_lignes_reclamation(LigneReclamation.objects.all())

        uaps = UAP.objects.filter(
            lignes_reclamation__in=lignes
        ).annotate(
            nb_reclamations=Count(
                'lignes_reclamation__reclamation',
                filter=Q(lignes_reclamation__in=lignes),
                distinct=True
            )
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')
        
        return {
            'labels': [u.nom for u in uaps],
            'data': [u.nb_reclamations for u in uaps]
        }
    
    def get_reclamations_par_mois(self):
        """Évolution mensuelle des réclamations"""
        mois_data = self._filter_reclamations(
            Reclamation.objects.all()
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
        reclamations_par_mois = self._filter_reclamations(
            Reclamation.objects.all()
        ).annotate(
            mois=TruncMonth('date_reclamation')
        ).values('mois').annotate(
            total=Count('id')
        ).order_by('mois')
        
        typologie = []
        for i, type_nc in enumerate(type_nc_list):
            data_par_mois = self._filter_reclamations(
                Reclamation.objects.filter(
                    date_reclamation__gte=self.date_debut_12m,
                    type_nc=type_nc
                )
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
            imputations = self._filter_reclamations(
                Reclamation.objects.all()
            ).values('imputation').annotate(
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

        # Filtrer sur les 12 derniers mois + appliquer les filtres dashboard
        qs_base = self._filter_reclamations(
            Reclamation.objects.all()
        )

        # Définir correctement les réclamations à traiter
        reclamations_closes = qs_base.filter(
            date_reclamation__isnull=False
        )

        total_jours = 0
        count = 0

        for rec in reclamations_closes:
            if rec.date_cloture and rec.date_reclamation:
                delta = rec.date_cloture - rec.date_reclamation
                total_jours += delta.days
                count += 1

            elif rec.date_reclamation and not rec.date_cloture:
                delta = datetime.now().date() - rec.date_reclamation
                total_jours += delta.days
                count += 1

        return round(total_jours / count, 1) if count > 0 else 0
    
    def get_type_nc_stats(self):
        """Statistiques par type de NC"""
        types = self._filter_reclamations(
            Reclamation.objects.all()
        ).values('type_nc').annotate(
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
        if self.selected_year:
            annee = self.selected_year
        else:
            annee = self.annee_courante
        ppm_calculator = PPMCalculator(annee=annee)
        
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
            annee=int(self.selected_year) if self.selected_year else self.annee_courante
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
        nqc_par_mois = self._filter_reclamations(
            Reclamation.objects.all()
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
        annee = self.selected_year if self.selected_year else self.annee_courante

        nqc_client = self._filter_reclamations(
            Reclamation.objects.filter(date_reclamation__year=annee)
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
        annee = self.selected_year if self.selected_year else self.annee_courante

        nqc_type = self._filter_reclamations(
            Reclamation.objects.filter(date_reclamation__year=annee)
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
    
    def get_top_produits_recurrents(self, top_n=5):
        """Récupère les produits les plus récurrents"""
        # Compter les réclamations par produit
        reclamations_qs = self._filter_reclamations(Reclamation.objects.all())

        produits = Produit.objects.filter(
            lignes_reclamation__reclamation__in=reclamations_qs
        ).annotate(
            nb_reclamations=Count(
                'lignes_reclamation__reclamation',
                filter=Q(lignes_reclamation__reclamation__in=reclamations_qs),
                distinct=True
            ),
            quantite_totale=Sum(
                'lignes_reclamation__quantite',
                filter=Q(lignes_reclamation__reclamation__in=reclamations_qs)
            )
        ).filter(nb_reclamations__gt=0).order_by('-nb_reclamations')[:top_n]

        total_reclamations = reclamations_qs.count()
        
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
        
        # Compter les réclamations par site client
        reclamations_qs = self._filter_reclamations(Reclamation.objects.all())

        sites_client = SiteClient.objects.filter(
            actif=True,
            reclamations__in=reclamations_qs
        ).annotate(
            nb_reclamations=Count(
                'reclamations',
                filter=Q(reclamations__in=reclamations_qs),
                distinct=True
            )
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
        Calcule le taux de réactivité par UAP par mois,
        """
 
        
        # Récupérer les lignes pour les réclamations des 12 derniers mois
        lignes = self._filter_lignes_reclamation(
                LigneReclamation.objects.filter(
                    uap_concernee__isnull=False,
                )
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
        
        # Structure : stats[année][mois][UAP] = { total, cloture_4d, cloture_8d }
        stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
            'total_reclamations': 0,
            'cloture_4d_delai': 0,
            'cloture_8d_delai': 0,
        })))
        
        reclamations_traitees = set()
        
        for ligne in lignes:
            rec_id = ligne['reclamation__id']
            rec_date = ligne['reclamation__date_reclamation']
            uap = ligne['uap_concernee__nom']
            if not rec_date:
                continue
            
            annee = rec_date.year
            mois = rec_date.month
            key = (annee, mois, uap, rec_id)
            
            if key in reclamations_traitees:
                continue
            reclamations_traitees.add(key)
            
            # --- Traitement 4D ---
            if ligne['reclamation__etat_4d'] == 'CLOTURE' and ligne['reclamation__date_cloture_4d']:
                date_limite_4d = self._calculer_date_limite(rec_date, 2)
                if ligne['reclamation__date_cloture_4d'] <= date_limite_4d:
                    stats[annee][mois][uap]['cloture_4d_delai'] += 1
                stats[annee][mois][uap]['total_reclamations'] += 1
            else:
                # Réclamation non clôturée ou clôturée hors délai
                date_limite_4d = self._calculer_date_limite(rec_date, 2)
                if date_limite_4d < self.today:
                    stats[annee][mois][uap]['total_reclamations'] += 1
            
            # --- Traitement 8D ---
            if ligne['reclamation__etat_8d'] == 'CLOTURE' and ligne['reclamation__date_cloture_8d']:
                date_limite_8d = self._calculer_date_limite(rec_date, 10)
                if ligne['reclamation__date_cloture_8d'] <= date_limite_8d:
                    stats[annee][mois][uap]['cloture_8d_delai'] += 1
                stats[annee][mois][uap]['total_reclamations'] += 1
            else:
                date_limite_8d = self._calculer_date_limite(rec_date, 10)
                if date_limite_8d < self.today:
                    stats[annee][mois][uap]['total_reclamations'] += 1
        
        # --- Construction du résultat ---
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
                    total = valeurs['total_reclamations']
                    cloture_4d = valeurs['cloture_4d_delai']
                    cloture_8d = valeurs['cloture_8d_delai']
                    
                    reactif = cloture_4d + cloture_8d
                    taux = (reactif / total * 100) if total > 0 else 100.0
                    donnees_uap[uap] = round(taux, 1)
                data_mensuelle[mois_nom] = donnees_uap
            uap_noms = sorted(uap_noms_set)
            # Compléter les UAP manquants pour chaque mois
            for mois_nom in mois_labels:
                if mois_nom not in data_mensuelle:
                    data_mensuelle[mois_nom] = {uap: 100.0 for uap in uap_noms}
                else:
                    for uap in uap_noms:
                        if uap not in data_mensuelle[mois_nom]:
                            data_mensuelle[mois_nom][uap] = 100.0
            
            resultats_par_annee[annee] = {
                'mois_labels': mois_labels,
                'uap_noms': uap_noms,
                'data': data_mensuelle
            }
        
        # --- Moyenne des taux sur les 12 derniers mois (tous les mois filtrés) ---
        tous_les_taux = []
        for annee, annee_data in resultats_par_annee.items():
            for mois, uap_data in annee_data['data'].items():
                for uap, taux in uap_data.items():
                    tous_les_taux.append(taux)
        
        moyenne_reactivite = sum(tous_les_taux) / len(tous_les_taux) if tous_les_taux else 100
        
        return resultats_par_annee, moyenne_reactivite

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
        queryset = self._filter_reclamations(Reclamation.objects.all())
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

    def get_top_defauts_recurrents(self, top_n=5, imputation=None):
        """
        Récupère les défauts (descriptions de non-conformité) les plus récurrents
        Taux de récurrence = Nombre de réclamations contenant le défaut / Nombre total de réclamations
        imputation: 'CIM', 'CIB', 'CLIENT', 'ALERTE' ou None pour tous
        """
        
        # Construire le filtre de base pour les réclamations
        reclamations_queryset = self._filter_reclamations(Reclamation.objects.all())
        if imputation:
            reclamations_queryset = reclamations_queryset.filter(imputation=imputation)
        
        # Total des réclamations (dénominateur pour le taux)
        total_reclamations = reclamations_queryset.count()
        
        # Si aucune réclamation, retourner liste vide
        if total_reclamations == 0:
            return []
        
        # Construire le filtre de base pour les non-conformités
        queryset = self._filter_non_conformites(NonConformite.objects.all())
        if imputation:
            queryset = queryset.filter(ligne_reclamation__reclamation__imputation=imputation)
        
        # Compter les occurrences et les réclamations concernées
        defauts = queryset.values('description').annotate(
            nb_occurences=Count('id'),  # Nombre total d'occurrences
            quantite_totale=Sum('quantite'),  # Quantité totale
            nb_reclamations=Count('ligne_reclamation__reclamation', distinct=True)  # Réclamations distinctes
        ).filter(
            description__isnull=False
        ).exclude(
            description=''
        ).order_by('-nb_reclamations')[:top_n]  # Tri par nombre de réclamations concernées
        
        # Total des non-conformités pour le même filtre (pour information)
        total_nc = queryset.count()
        
        resultats = []
        for defaut in defauts:
            description = defaut['description']
            nb_reclamations_concernees = defaut['nb_reclamations']
            
            # Nouveau calcul du taux de récurrence
            # Taux = (réclamations avec le défaut / total réclamations) * 100
            taux = (nb_reclamations_concernees / total_reclamations * 100) if total_reclamations > 0 else 0
            
            # Récupérer les produits concernés
            produits_base = Produit.objects.filter(
                lignes_reclamation__non_conformites__description=description
            )

            if imputation:
                produits_base = produits_base.filter(
                    lignes_reclamation__reclamation__imputation=imputation
                )

            if self.selected_client:
                produits_base = produits_base.filter(
                    lignes_reclamation__reclamation__client_id=self.selected_client
                )

            if self.selected_year:
                produits_base = produits_base.filter(
                    lignes_reclamation__reclamation__date_reclamation__year=self.selected_year
                )

            if self.selected_uap:
                produits_base = produits_base.filter(
                    lignes_reclamation__uap_concernee_id=self.selected_uap
                )

            produits_queryset = produits_base.distinct().values_list('product_number', flat=True)[:10]
            produits_concernes = produits_queryset.count()
            
            # Récupérer les IDs des réclamations concernées (pour référence)
            reclamations_ids = NonConformite.objects.filter(
                description=description
            )
            if imputation:
                reclamations_ids = reclamations_ids.filter(
                    ligne_reclamation__reclamation__imputation=imputation
                )
            reclamations_ids = list(reclamations_ids.values_list(
                'ligne_reclamation__reclamation_id', flat=True
            ).distinct())
            
            resultats.append({
                'description': description,
                'nb_occurences': defaut['nb_occurences'],
                'quantite_totale': defaut['quantite_totale'] or 0,
                'nb_reclamations': nb_reclamations_concernees,
                'nb_produits': produits_concernes,
                'taux_recurrence': round(taux, 2),
                'taux_recurrence_formatted': f"{round(taux, 2)}%",
                'total_reclamations_reference': total_reclamations,  # Pour information
                'reclamations_ids': reclamations_ids  # Pour des liens éventuels
            })
        
        return resultats

    def get_taux_recurrence_globale(self, imputation=None):
        """
        Calcule le taux de récurrence globale des défauts
        Taux = Nombre de défauts qui apparaissent dans PLUSIEURS RÉCLAMATIONS / Nombre total de défauts distincts × 100
        Un défaut est considéré comme récurrent s'il apparaît dans au moins 2 réclamations différentes
        """
        
        # Construire le filtre de base
        queryset = self._filter_non_conformites(NonConformite.objects.all())
        if imputation:
            queryset = queryset.filter(ligne_reclamation__reclamation__date_reclamation__gte=self.date_debut_12m, ligne_reclamation__reclamation__imputation=imputation)
        
        # Compter les défauts par description avec le nombre de RÉCLAMATIONS distinctes
        defauts_stats = queryset.values('description').annotate(
            nb_occurences=Count('id'),  # Nombre total d'occurrences du défaut
            nb_reclamations=Count('ligne_reclamation__reclamation', distinct=True)  # Nombre de réclamations distinctes
        ).filter(
            description__isnull=False
        ).exclude(
            description=''
        )
        
        # Nombre total de défauts distincts
        total_defauts = defauts_stats.count()
        
        # Nombre de défauts récurrents (apparaissent dans PLUSIEURS réclamations différentes)
        defauts_recurrents = defauts_stats.filter(nb_reclamations__gte=2).count()
        
        # Calcul du taux de récurrence
        if total_defauts > 0:
            taux_recurrence = (defauts_recurrents / total_defauts) * 100
        else:
            taux_recurrence = 0
        
        # Statistiques supplémentaires
        total_reclamations = self._filter_reclamations(Reclamation.objects.all())
        if imputation:
            total_reclamations = total_reclamations.filter(imputation=imputation)
        total_reclamations_count = total_reclamations.count()
        
        # Défauts par niveau de récurrence
        defauts_faible = defauts_stats.filter(nb_reclamations=1).count()
        defauts_moyen = defauts_stats.filter(nb_reclamations__gte=2, nb_reclamations__lte=5).count()
        defauts_eleve = defauts_stats.filter(nb_reclamations__gt=5).count()
        
        # Top 5 des défauts les plus récurrents
        top_defauts_recurrents = list(defauts_stats.filter(
            nb_reclamations__gte=2
        ).order_by('-nb_reclamations')[:5].values('description', 'nb_reclamations', 'nb_occurences'))
        
        return {
            'taux': round(taux_recurrence, 1),
            'taux_formatted': f"{round(taux_recurrence, 1)}%",
            'defauts_recurrents': defauts_recurrents,
            'total_defauts': total_defauts,
            'total_reclamations': total_reclamations_count,
            'total_occurences': queryset.count(),
            'imputation': imputation,
            'imputation_display': dict(Reclamation.IMPUTATION_CHOICES).get(imputation, imputation) if imputation else 'Toutes',
            # Répartition par niveau de récurrence
            'repartition': {
                'faible': defauts_faible,      # 1 réclamation
                'moyen': defauts_moyen,         # 2-5 réclamations
                'eleve': defauts_eleve          # >5 réclamations
            },
            'top_defauts_recurrents': top_defauts_recurrents,
            # Pourcentage de défauts récurrents
            'pourcentage_recurrents': round((defauts_recurrents / total_defauts * 100), 1) if total_defauts > 0 else 0
        }

    def get_all_stats(self):
        """Récupère toutes les statistiques"""
        taux_reactivite_par_uap, taux_reactivite = self.get_taux_reactivite_par_uap()
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
            'top_produits_recurrents': self.get_top_produits_recurrents(),
            'reclamations_par_site_client': self.get_reclamations_par_site_client(),
            'taux_reactivite_par_uap': taux_reactivite_par_uap,
            'taux_reactivite': taux_reactivite,
            'reclamations_par_client_mois': self.get_reclamations_par_client_mois(),
            'top_defauts_recurrents': self.get_top_defauts_recurrents(),
            'taux_recurrence_globale': self.get_taux_recurrence_globale(),
        }