from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from accounts.models import Role

class Command(BaseCommand):
    help = 'Crée les rôles et permissions par défaut'

    def handle(self, *args, **options):
        # Définition des permissions par rôle
        role_permissions = {
            'admin': [
                'view_reclamation', 'add_reclamation', 'change_reclamation', 'delete_reclamation',
                'view_client', 'add_client', 'change_client', 'delete_client',
                'view_produit', 'add_produit', 'change_produit', 'delete_produit',
                'view_site', 'add_site', 'change_site', 'delete_site',
                'view_uap', 'add_uap', 'change_uap', 'delete_uap',
                'view_programme', 'add_programme', 'change_programme', 'delete_programme',
                'view_objectifsannuel', 'add_objectifsannuel', 'change_objectifsannuel', 'delete_objectifsannuel',
                'view_user', 'add_user', 'change_user', 'delete_user',
                'can_import', 'can_export', 'can_view_reports'
            ],
            'quality_manager': [
                'view_reclamation', 'add_reclamation', 'change_reclamation', 'delete_reclamation',
                'view_client', 'add_client', 'change_client',
                'view_produit', 'add_produit', 'change_produit',
                'view_site', 'add_site', 'change_site',
                'view_uap', 'add_uap', 'change_uap',
                'view_programme', 'add_programme', 'change_programme',
                'view_objectifsannuel', 'change_objectifsannuel',
                'can_import', 'can_export', 'can_view_reports'
            ],
            'quality_engineer': [
                'view_reclamation', 'add_reclamation', 'change_reclamation',
                'view_client', 'view_produit', 'add_produit', 'change_produit',
                'can_view_reports'
            ],
            'production_manager': [
                'view_reclamation', 'add_reclamation', 'change_reclamation',
                'view_produit', 'view_site',
                'can_view_reports'
            ],
            'production_operator': [
                'view_reclamation', 'add_reclamation',
                'view_produit'
            ],
            'supplier': [
                'view_reclamation'
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