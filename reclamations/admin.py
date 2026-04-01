from django.contrib import admin
from .models import UAP, Site, Client, Produit, Reclamation, LigneReclamation, Programme, SiteClient, ObjectifsAnnuel

class LigneReclamationInline(admin.TabularInline):
    model = LigneReclamation
    extra = 1
    fields = ['produit', 'quantite', 'description_non_conformite', 'commentaire', 'uap_concernee']
    autocomplete_fields = ['produit', 'uap_concernee']

class SiteClientInline(admin.TabularInline):
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
    filter_horizontal = ['clients']  # Pour la sélection multiple des clients
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
        """Retourne la liste des clients sous forme de chaîne"""
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

@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = [
        'numero_reclamation', 'date_reclamation', 'client_nom', 
        'site_nom', 'programme_nom', 'type_nc', 'imputation', 
        'etat_4d', 'etat_8d', 'cloture'
    ]
    list_filter = [
        'type_nc', 'imputation', 'etat_4d', 'etat_8d', 'cloture',
        'client', 'site__uap', 'programme'
    ]
    search_fields = ['numero_reclamation', 'client__nom', 'programme__nom']
    autocomplete_fields = ['client', 'site', 'programme', 'createur']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [LigneReclamationInline]
    date_hierarchy = 'date_reclamation'
    list_per_page = 25
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'numero_reclamation', 'date_reclamation', 'client', 
                'site', 'programme', 'site_client', 'imputation', 'type_nc'
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
    
    def site_nom(self, obj):
        return obj.site.nom if obj.site else "-"
    site_nom.short_description = "Site usine"
    site_nom.admin_order_field = 'site__nom'
    
    def programme_nom(self, obj):
        return obj.programme.nom if obj.programme else "-"
    programme_nom.short_description = "Programme"
    programme_nom.admin_order_field = 'programme__nom'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'client', 'site', 'site__uap', 'programme', 'createur'
        )