from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from accounts.models import Role

class Command(BaseCommand):
    help = 'Crée les rôles et permissions par défaut'

    def handle(self, *args, **options):
        # Définition des permissions par rôle
        ALL_PERMISSIONS = [
            # Réclamations (Reclamation)
            'view_reclamation', 'add_reclamation', 'change_reclamation', 'delete_reclamation',
            
            # Lignes de réclamation (LigneReclamation)
            'view_lignereclamation', 'add_lignereclamation', 'change_lignereclamation', 'delete_lignereclamation',
            
            # Non-conformités (NonConformite)
            'view_nonconformite', 'add_nonconformite', 'change_nonconformite', 'delete_nonconformite',
            
            # Clients (Client)
            'view_client', 'add_client', 'change_client', 'delete_client',
            
            # Sites clients (SiteClient)
            'view_siteclient', 'add_siteclient', 'change_siteclient', 'delete_siteclient',
            
            # Produits (Produit)
            'view_produit', 'add_produit', 'change_produit', 'delete_produit',
            
            # Sites (Site)
            'view_site', 'add_site', 'change_site', 'delete_site',
            
            # UAP (UAP)
            'view_uap', 'add_uap', 'change_uap', 'delete_uap',
            
            # Programmes (Programme)
            'view_programme', 'add_programme', 'change_programme', 'delete_programme',
            
            # Objectifs annuels (ObjectifsAnnuel)
            'view_objectifsannuel', 'add_objectifsannuel', 'change_objectifsannuel', 'delete_objectifsannuel',
            
            # Livraisons (Livraison)
            'view_livraison', 'add_livraison', 'change_livraison', 'delete_livraison',
            
            # 8D (HuitD)
            'view_huitd', 'add_huitd', 'change_huitd', 'delete_huitd',
            
            # 5W2H (CinqW2H)
            'view_cinqw2h', 'add_cinqw2h', 'change_cinqw2h', 'delete_cinqw2h',
            
            # Causes Ishikawa (CauseIshikawa)
            'view_causeishikawa', 'add_causeishikawa', 'change_causeishikawa', 'delete_causeishikawa',
            
            # VRS (VRS)
            'view_vrs', 'add_vrs', 'change_vrs', 'delete_vrs',
            
            # Facteurs VRS (FacteurVRS)
            'view_facteurvrs', 'add_facteurvrs', 'change_facteurvrs', 'delete_facteurvrs',
            
            # Facteurs Humains (FacteurHumain)
            'view_facteurhumain', 'add_facteurhumain', 'change_facteurhumain', 'delete_facteurhumain',
            
            # Évaluations Facteurs Humains (EvaluationFacteurHumain)
            'view_evaluationfacteurhumain', 'add_evaluationfacteurhumain', 'change_evaluationfacteurhumain', 'delete_evaluationfacteurhumain',
            
            # 5 Pourquoi (CauseCinqP)
            'view_causecinqp', 'add_causecinqp', 'change_causecinqp', 'delete_causecinqp',
            
            # Participants 8D (Participant8D)
            'view_participant8d', 'add_participant8d', 'change_participant8d', 'delete_participant8d',
            
            # Actions 8D (Action8D)
            'view_action8d', 'add_action8d', 'change_action8d', 'delete_action8d',
            
            # Altérations 8D (Alteration8D)
            'view_alteration8d', 'add_alteration8d', 'change_alteration8d', 'delete_alteration8d',
            
            # Évidences 8D (Evidence8D)
            'view_evidence8d', 'add_evidence8d', 'change_evidence8d', 'delete_evidence8d',
            
            # Articles FAI (ArticleFAI)
            'view_articlefai', 'add_articlefai', 'change_articlefai', 'delete_articlefai',
            
            # Historique Import FAI (HistoriqueImportFAI)
            'view_historiqueimportfai', 'add_historiqueimportfai', 'change_historiqueimportfai', 'delete_historiqueimportfai',
            
            # Utilisateurs (User)
            'view_user', 'add_user', 'change_user', 'delete_user',
            
            # Permissions personnalisées
            'can_import', 'can_export', 'can_view_reports',
        ]

        role_permissions = {
            'admin': ALL_PERMISSIONS,
           
            'quality_manager':ALL_PERMISSIONS,
           
            'quality_engineer': [
                  # Réclamations (Reclamation)
                'view_reclamation', 'add_reclamation', 'change_reclamation', 'delete_reclamation',
                
                # Lignes de réclamation (LigneReclamation)
                'view_lignereclamation', 'add_lignereclamation', 'change_lignereclamation', 'delete_lignereclamation',
                
                # Non-conformités (NonConformite)
                'view_nonconformite', 'add_nonconformite', 'change_nonconformite', 'delete_nonconformite',
                
                # Clients (Client)
                'view_client', 'add_client', 'change_client', 'delete_client',
                
                # Sites clients (SiteClient)
                'view_siteclient', 'add_siteclient', 'change_siteclient', 'delete_siteclient',
                
                # Produits (Produit)
                'view_produit', 'add_produit', 'change_produit', 'delete_produit',
                
                # Sites (Site)
                'view_site', 'add_site', 'change_site', 'delete_site',
                
                # UAP (UAP)
                'view_uap', 'add_uap', 'change_uap', 'delete_uap',
                
                # Programmes (Programme)
                'view_programme', 'add_programme', 'change_programme', 'delete_programme',
                
                # Objectifs annuels (ObjectifsAnnuel)
                'view_objectifsannuel', 'add_objectifsannuel', 'change_objectifsannuel', 'delete_objectifsannuel',
                
                # Livraisons (Livraison)
                'view_livraison', 'add_livraison', 'change_livraison', 'delete_livraison',
                
                # 8D (HuitD)
                'view_huitd', 'add_huitd', 'change_huitd', 'delete_huitd',
                
                # 5W2H (CinqW2H)
                'view_cinqw2h', 'add_cinqw2h', 'change_cinqw2h', 'delete_cinqw2h',
                
                # Causes Ishikawa (CauseIshikawa)
                'view_causeishikawa', 'add_causeishikawa', 'change_causeishikawa', 'delete_causeishikawa',
                
                # VRS (VRS)
                'view_vrs', 'add_vrs', 'change_vrs', 'delete_vrs',
                
                # Facteurs VRS (FacteurVRS)
                'view_facteurvrs', 'add_facteurvrs', 'change_facteurvrs', 'delete_facteurvrs',
                
                # Facteurs Humains (FacteurHumain)
                'view_facteurhumain', 'add_facteurhumain', 'change_facteurhumain', 'delete_facteurhumain',
                
                # Évaluations Facteurs Humains (EvaluationFacteurHumain)
                'view_evaluationfacteurhumain', 'add_evaluationfacteurhumain', 'change_evaluationfacteurhumain', 'delete_evaluationfacteurhumain',
                
                # 5 Pourquoi (CauseCinqP)
                'view_causecinqp', 'add_causecinqp', 'change_causecinqp', 'delete_causecinqp',
                
                # Participants 8D (Participant8D)
                'view_participant8d', 'add_participant8d', 'change_participant8d', 'delete_participant8d',
                
                # Actions 8D (Action8D)
                'view_action8d', 'add_action8d', 'change_action8d', 'delete_action8d',
                
                # Altérations 8D (Alteration8D)
                'view_alteration8d', 'add_alteration8d', 'change_alteration8d', 'delete_alteration8d',
                
                # Évidences 8D (Evidence8D)
                'view_evidence8d', 'add_evidence8d', 'change_evidence8d', 'delete_evidence8d',
                
                # Articles FAI (ArticleFAI)
                'view_articlefai', 'add_articlefai', 'change_articlefai', 'delete_articlefai',
                
                # Historique Import FAI (HistoriqueImportFAI)
                'view_historiqueimportfai', 'add_historiqueimportfai', 'change_historiqueimportfai', 'delete_historiqueimportfai',
                
                ],

            'product_quality_engineer': [  
                # 8D (HuitD)
                'view_huitd', 'add_huitd', 'change_huitd', 'delete_huitd',
                
                # 5W2H (CinqW2H)
                'view_cinqw2h', 'add_cinqw2h', 'change_cinqw2h', 'delete_cinqw2h',
                
                # Causes Ishikawa (CauseIshikawa)
                'view_causeishikawa', 'add_causeishikawa', 'change_causeishikawa', 'delete_causeishikawa',
                
                # VRS (VRS)
                'view_vrs', 'add_vrs', 'change_vrs', 'delete_vrs',
                
                # Facteurs VRS (FacteurVRS)
                'view_facteurvrs', 'add_facteurvrs', 'change_facteurvrs', 'delete_facteurvrs',
                
                # Facteurs Humains (FacteurHumain)
                'view_facteurhumain', 'add_facteurhumain', 'change_facteurhumain', 'delete_facteurhumain',
                
                # Évaluations Facteurs Humains (EvaluationFacteurHumain)
                'view_evaluationfacteurhumain', 'add_evaluationfacteurhumain', 'change_evaluationfacteurhumain', 'delete_evaluationfacteurhumain',
                
                # 5 Pourquoi (CauseCinqP)
                'view_causecinqp', 'add_causecinqp', 'change_causecinqp', 'delete_causecinqp',
                
                # Participants 8D (Participant8D)
                'view_participant8d', 'add_participant8d', 'change_participant8d', 'delete_participant8d',
                
                # Actions 8D (Action8D)
                'view_action8d', 'add_action8d', 'change_action8d', 'delete_action8d',
                
                # Altérations 8D (Alteration8D)
                'view_alteration8d', 'add_alteration8d', 'change_alteration8d', 'delete_alteration8d',
                
                # Évidences 8D (Evidence8D)
                'view_evidence8d', 'add_evidence8d', 'change_evidence8d', 'delete_evidence8d',       
                ],

            'quality_coordinator': [
                # Articles FAI (ArticleFAI)
                'view_articlefai', 'add_articlefai', 'change_articlefai', 'delete_articlefai',
                 # Historique Import FAI (HistoriqueImportFAI)
                'view_historiqueimportfai', 'add_historiqueimportfai', 'change_historiqueimportfai', 'delete_historiqueimportfai',
                ],

            'production_manager': [
                'view_historiqueimportfai'
                ],

            'viewer': [
                'view_reclamation'
             ],
        }
        
        for role_name, perms in role_permissions.items():
            role, created = Role.objects.get_or_create(name=role_name)
            permissions = Permission.objects.filter(codename__in=perms)
            role.permissions.set(permissions)
            role.save()
            
            status = "créé" if created else "mis à jour"
            self.stdout.write(self.style.SUCCESS(f"Rôle '{role_name}' {status} avec {permissions.count()} permissions"))