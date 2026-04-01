# reclamations/utils/ppm_calculator.py
from django.db.models import Sum
from datetime import datetime
from ..models import Livraison, LigneReclamation, Client

class PPMCalculator:
    """Classe pour calculer les indicateurs PPM"""
    
    def __init__(self, annee=None):
        self.annee = annee or datetime.now().year
    
    def get_quantites_client(self, client_id):
        """Récupère les quantités livrées et non conformes pour un client"""
        # Quantité livrée
        total_livre = Livraison.objects.filter(
            client_id=client_id,
            date_livraison__year=self.annee
        ).aggregate(total=Sum('quantite_livree'))['total'] or 0
        
        # Quantité non conforme (via les réclamations)
        total_non_conforme = LigneReclamation.objects.filter(
            reclamation__client_id=client_id,
            reclamation__date_reclamation__year=self.annee
        ).aggregate(total=Sum('quantite'))['total'] or 0
        
        return total_livre, total_non_conforme
    
    def calculer_ppm(self, quantite_livree, quantite_non_conforme):
        """Calcule le PPM à partir des quantités"""
        if quantite_livree > 0:
            return (quantite_non_conforme / quantite_livree) * 1000000
        return 0
    
    def get_ppm_client(self, client):
        """Calcule le PPM pour un client"""
        total_livre, total_non_conforme = self.get_quantites_client(client.id)
        ppm = self.calculer_ppm(total_livre, total_non_conforme)
        
        return {
            'client': client.nom,
            'client_id': client.id,
            'quantite_livree': total_livre,
            'quantite_non_conforme': total_non_conforme,
            'ppm': round(ppm, 2)
        }
    
    def get_all_clients_ppm(self):
        """Calcule le PPM pour tous les clients actifs"""
        clients = Client.objects.filter(actif=True)
        resultats = []
        
        for client in clients:
            ppm_data = self.get_ppm_client(client)
            if ppm_data['quantite_livree'] > 0 or ppm_data['quantite_non_conforme'] > 0:
                resultats.append(ppm_data)
        
        return sorted(resultats, key=lambda x: x['ppm'], reverse=True)
    
    def get_ppm_mensuel(self):
        """Calcule le PPM par mois"""
        mois_noms = {
            1: 'Jan', 2: 'Fév', 3: 'Mar', 4: 'Avr', 
            5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Aoû', 
            9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Déc'
        }
        
        evolution = []
        
        for mois in range(1, 13):
            total_livre = Livraison.objects.filter(
                date_livraison__year=self.annee,
                date_livraison__month=mois
            ).aggregate(total=Sum('quantite_livree'))['total'] or 0
            
            total_non_conforme = LigneReclamation.objects.filter(
                reclamation__date_reclamation__year=self.annee,
                reclamation__date_reclamation__month=mois
            ).aggregate(total=Sum('quantite'))['total'] or 0
            
            ppm = self.calculer_ppm(total_livre, total_non_conforme)
            
            evolution.append({
                'mois': mois,
                'mois_nom': mois_noms[mois],
                'ppm': round(ppm, 2),
                'quantite_livree': total_livre,
                'quantite_non_conforme': total_non_conforme
            })
        
        return evolution
    
    def get_ppm_global(self):
        """Calcule le PPM global de l'année"""
        total_livre = Livraison.objects.filter(
            date_livraison__year=self.annee
        ).aggregate(total=Sum('quantite_livree'))['total'] or 0
        
        total_non_conforme = LigneReclamation.objects.filter(
            reclamation__date_reclamation__year=self.annee
        ).aggregate(total=Sum('quantite'))['total'] or 0
        
        ppm = self.calculer_ppm(total_livre, total_non_conforme)
        
        return {
            'ppm': round(ppm, 2),
            'quantite_livree': total_livre,
            'quantite_non_conforme': total_non_conforme
        }
    def get_ppm_par_site(self):
        """Calcule le PPM par site (UAP)"""
        from ..models import Site
        
        sites = Site.objects.all()
        resultats = []
        
        for site in sites:
            total_livre = Livraison.objects.filter(
                client__site=site,
                date_livraison__year=self.annee
            ).aggregate(total=Sum('quantite_livree'))['total'] or 0
            
            total_non_conforme = LigneReclamation.objects.filter(
                reclamation__client__site=site,
                reclamation__date_reclamation__year=self.annee
            ).aggregate(total=Sum('quantite'))['total'] or 0
            
            ppm = self.calculer_ppm(total_livre, total_non_conforme)
            
            if total_livre > 0 or total_non_conforme > 0:
                resultats.append({
                    'site': site.nom,
                    'uap': site.uap.nom,
                    'quantite_livree': total_livre,
                    'quantite_non_conforme': total_non_conforme,
                    'ppm': round(ppm, 2)
                })
        
        return sorted(resultats, key=lambda x: x['ppm'], reverse=True)
    
    def get_tendance_ppm(self, client_id=None):
        """Calcule la tendance PPM sur les 12 derniers mois"""
        evolution = self.get_ppm_mensuel()
        
        if client_id:
            # Évolution spécifique à un client
            evolution = []
            for mois in range(1, 13):
                total_livre = Livraison.objects.filter(
                    client_id=client_id,
                    date_livraison__year=self.annee,
                    date_livraison__month=mois
                ).aggregate(total=Sum('quantite_livree'))['total'] or 0
                
                total_non_conforme = LigneReclamation.objects.filter(
                    reclamation__client_id=client_id,
                    reclamation__date_reclamation__year=self.annee,
                    reclamation__date_reclamation__month=mois
                ).aggregate(total=Sum('quantite'))['total'] or 0
                
                ppm = self.calculer_ppm(total_livre, total_non_conforme)
                evolution.append(round(ppm, 2))
        
        return evolution
    
    
    def get_statut_ppm(self, ppm):
        """Retourne le statut d'un PPM"""
        if ppm == 0:
            return {'text': 'Parfait', 'class': 'success'}
        elif ppm < 500:
            return {'text': 'Bon', 'class': 'success'}
        elif ppm < 1000:
            return {'text': 'Moyen', 'class': 'warning'}
        else:
            return {'text': 'Critique', 'class': 'danger'}
        
from datetime import timedelta

def est_jour_ouvre(date):
    """Vérifie si une date est un jour ouvré (lundi à vendredi)"""
    return date.weekday() < 5  # 0 = lundi, 4 = vendredi

def calculer_date_limite_ouvree(date_debut, jours_ouvres):
    """Calcule la date limite en jours ouvrés"""
    date_limite = date_debut
    jours_restants = jours_ouvres
    
    while jours_restants > 0:
        date_limite += timedelta(days=1)
        if est_jour_ouvre(date_limite):
            jours_restants -= 1
    
    return date_limite