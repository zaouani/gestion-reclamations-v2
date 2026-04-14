from django.contrib import admin
from .models import (
    UAP, Site, Client, Produit, Reclamation, LigneReclamation, 
    Programme, SiteClient, ObjectifsAnnuel, NonConformite
)


class NonConformiteInline(admin.TabularInline):
    """Inline pour les non-conformités"""
    model = NonConformite
    extra = 1
    fields = ['description', 'quantite']
    ordering = ['-date_creation']


class LigneReclamationInline(admin.TabularInline):
    """Inline pour les lignes de réclamation avec leurs NC"""
    model = LigneReclamation
    extra = 1
    fields = ['produit', 'quantite', 'site', 'uap_concernee', 'commentaire']
    autocomplete_fields = ['produit', 'site', 'uap_concernee']
    inlines = [NonConformiteInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('produit', 'site', 'site__uap', 'uap_concernee')


class SiteClientInline(admin.TabularInline):
    """Inline pour les sites client"""
    model = SiteClient
    extra = 1
    fields = ['nom', 'ville', 'pays', 'telephone', 'email', 'actif']


@admin.register(UAP)
class UAPAdmin(admin.ModelAdmin):
    list_display = ['nom', 'date_creation']
    search_fields = ['nom']
    ordering = ['nom']


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['nom', 'uap', 'date_creation']
    list_filter = ['uap']
    search_fields = ['nom', 'uap__nom']
    autocomplete_fields = ['uap']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'email', 'telephone', 'actif', 'date_creation']
    list_filter = ['actif']
    search_fields = ['nom', 'email', 'telephone']
    inlines = [SiteClientInline]
    
    def nb_programmes(self, obj):
        return obj.programmes.count()
    nb_programmes.short_description = "Programmes"


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ['nom', 'get_clients_list', 'actif', 'date_creation']
    list_filter = ['actif']
    search_fields = ['nom']
    filter_horizontal = ['clients']
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'clients', 'description', 'actif')
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['date_creation', 'date_modification']
    
    def get_clients_list(self, obj):
        return ", ".join([client.nom for client in obj.clients.all()])
    get_clients_list.short_description = "Clients"
    get_clients_list.admin_order_field = 'clients'


@admin.register(SiteClient)
class SiteClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'client', 'ville', 'pays', 'actif']
    list_filter = ['client', 'pays', 'actif']
    search_fields = ['nom', 'client__nom', 'ville', 'contact_principal']
    autocomplete_fields = ['client']


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ['product_number', 'designation', 'actif', 'date_creation']
    list_filter = ['actif']
    search_fields = ['product_number', 'designation']


# ⚠️ AJOUT : Enregistrer d'abord LigneReclamation
@admin.register(LigneReclamation)
class LigneReclamationAdmin(admin.ModelAdmin):
    """Admin pour LigneReclamation (nécessaire pour l'autocomplete)"""
    list_display = ['id', 'reclamation', 'produit', 'quantite', 'site', 'uap_concernee']
    list_filter = ['site', 'uap_concernee']
    search_fields = ['reclamation__numero_reclamation', 'produit__product_number']
    autocomplete_fields = ['reclamation', 'produit', 'site', 'uap_concernee']
    raw_id_fields = ['reclamation']
    list_per_page = 20


@admin.register(NonConformite)
class NonConformiteAdmin(admin.ModelAdmin):
    list_display = ['description', 'ligne_reclamation', 'quantite', 'date_creation']
    list_filter = ['date_creation']
    search_fields = ['description', 'ligne_reclamation__reclamation__numero_reclamation']
    autocomplete_fields = ['ligne_reclamation']  # ← Maintenant LigneReclamation est enregistré
    raw_id_fields = ['ligne_reclamation']
    list_per_page = 20


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = [
        'numero_reclamation', 'date_reclamation', 'client_nom', 
        'programme_nom', 'type_nc', 'imputation', 
        'etat_4d', 'etat_8d', 'cloture'
    ]
    list_filter = [
        'type_nc', 'imputation', 'etat_4d', 'etat_8d', 'cloture',
        'client', 'programme'
    ]
    search_fields = ['numero_reclamation', 'client__nom', 'programme__nom']
    autocomplete_fields = ['client', 'programme', 'site_client', 'createur']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [LigneReclamationInline]
    date_hierarchy = 'date_reclamation'
    list_per_page = 25
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'numero_reclamation', 'date_reclamation', 'client', 
                'site_client', 'programme', 'imputation', 'type_nc'
            )
        }),
        ('Références qualité', {
            'fields': ('numero_4d', 'numero_8d'),
            'classes': ('collapse',)
        }),
        ('États et clôture', {
            'fields': (
                'etat_4d', 'etat_8d', 'me', 'cloture', 
                'date_cloture', 'date_cloture_4d', 'date_cloture_8d'
            )
        }),
        ('Documentation', {
            'fields': ('evidence',)
        }),
        ('Décisions', {
            'fields': ('decision', 'nqc')
        }),
        ('Métadonnées', {
            'fields': ('createur', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def client_nom(self, obj):
        return obj.client.nom if obj.client else "-"
    client_nom.short_description = "Client"
    client_nom.admin_order_field = 'client__nom'
    
    def programme_nom(self, obj):
        return obj.programme.nom if obj.programme else "-"
    programme_nom.short_description = "Programme"
    programme_nom.admin_order_field = 'programme__nom'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'client', 'programme', 'site_client', 'createur'
        ).prefetch_related('lignes__produit', 'lignes__site', 'lignes__uap_concernee', 'lignes__non_conformites')


@admin.register(ObjectifsAnnuel)
class ObjectifsAnnuelAdmin(admin.ModelAdmin):
    list_display = ['annee', 'obj_nc_court', 'obj_nqc_court', 'date_modification']
    search_fields = ['annee']
    ordering = ['-annee']
    
    def obj_nc_court(self, obj):
        if obj.obj_nc and len(obj.obj_nc) > 50:
            return obj.obj_nc[:50] + "..."
        return obj.obj_nc
    obj_nc_court.short_description = "Objectif NC"
    
    def obj_nqc_court(self, obj):
        if obj.obj_nqc and len(obj.obj_nqc) > 50:
            return obj.obj_nqc[:50] + "..."
        return obj.obj_nqc
    obj_nqc_court.short_description = "Objectif NQC"