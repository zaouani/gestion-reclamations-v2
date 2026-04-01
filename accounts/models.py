from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone

class Role(models.Model):
    """Modèle pour les rôles personnalisés"""
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('quality_manager', 'Responsable Qualité'),
        ('quality_engineer', 'Ingénieur Qualité'),
        ('production_manager', 'Responsable Production'),
        ('production_operator', 'Opérateur Production'),
        ('supplier', 'Fournisseur'),
        ('viewer', 'Consultant'),
    ]
    
    name = models.CharField(max_length=50, unique=True, choices=ROLE_CHOICES)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"
    
    def __str__(self):
        return dict(self.ROLE_CHOICES).get(self.name, self.name)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('quality_manager', 'Responsable Qualité'),
        ('quality_engineer', 'Ingénieur Qualité'),
        ('production_manager', 'Responsable Production'),
        ('production_operator', 'Opérateur Production'),
        ('supplier', 'Fournisseur'),
        ('viewer', 'Consultant'),
    ]
    
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    #created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Relations avec les groupes Django (pour compatibilité)
    groups = models.ManyToManyField(Group, related_name='custom_users', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='custom_users', blank=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} - {self.get_role_display()}"
    
    def get_role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)
    
    def has_permission(self, permission_codename):
        """Vérifie si l'utilisateur a une permission spécifique"""
        # Admin a toutes les permissions
        if self.role == 'admin' or self.is_superuser:
            return True
        
        # Vérifier les permissions du rôle
        try:
            role_obj = Role.objects.get(name=self.role)
            return role_obj.permissions.filter(codename=permission_codename).exists()
        except Role.DoesNotExist:
            return False
    
    def get_menu_permissions(self):
        """Retourne les menus accessibles selon le rôle"""
        menus = {
            'admin': [
                'dashboard', 'liste', 'creer', 'modifier_reclamation',
                'gestion_clients', 'gestion_produits', 'gestion_sites',
                'gestion_uap', 'gestion_programmes', 'gestion_objectifs',
                'gestion_utilisateurs', 'rapports', 'import_export', 'parametres'
            ],
            'quality_manager': [
                'dashboard', 'liste', 'creer', 'modifier_reclamation',
                'gestion_clients', 'gestion_produits', 'gestion_sites',
                'gestion_uap', 'gestion_programmes', 'gestion_objectifs',
                'rapports', 'import_export'
            ],
            'quality_engineer': [
                'dashboard', 'liste', 'creer', 'modifier_reclamation',
                'gestion_produits', 'rapports'
            ],
            'production_manager': [
                'dashboard', 'liste', 'creer', 'modifier_reclamation',
                'gestion_produits', 'gestion_sites'
            ],
            'production_operator': [
                'dashboard', 'liste', 'creer'
            ],
            'supplier': [
                'dashboard', 'liste'
            ],
            'viewer': [
                'dashboard', 'liste'
            ],
        }
        return menus.get(self.role, menus['viewer'])