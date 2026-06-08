from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from .models import (
    UAP, Site, Client, Produit, Reclamation, LigneReclamation, 
    Programme, SiteClient, ObjectifsAnnuel, NonConformite,
    Livraison, HuitD, CinqW2H, CauseIshikawa, VRS, FacteurVRS,
    FacteurHumain, EvaluationFacteurHumain, CauseCinqP, Participant8D,
    Action8D, Alteration8D, Evidence8D, ArticleFAI, HistoriqueImportFAI
)


# ========== FILTRES PERSONNALISÉS ==========

class ReclamationExpirationFilter(SimpleListFilter):
    """Filtre sur l'expiration des délais"""
    title = 'Expiration des délais'
    parameter_name = 'expiration'
    
    def lookups(self, request, model_admin):
        return (
            ('expired_4d', '4D expiré'),
            ('expired_8d', '8D expiré'),
            ('expiring_4d_soon', '4D expire bientôt (<= 2 jours)'),
            ('expiring_8d_soon', '8D expire bientôt (<= 5 jours)'),
            ('not_expired', 'Non expiré'),
        )
    
    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'expired_4d':
            return [r for r in queryset if r.est_expire_4d and r.etat_4d != 'CLOTURE']
        if self.value() == 'expired_8d':
            return [r for r in queryset if r.est_expire_8d and r.etat_8d != 'CLOTURE']
        if self.value() == 'expiring_4d_soon':
            return [r for r in queryset if r.jours_restants_4d and r.jours_restants_4d <= 2 and r.jours_restants_4d > 0]
        if self.value() == 'expiring_8d_soon':
            return [r for r in queryset if r.jours_restants_8d and r.jours_restants_8d <= 5 and r.jours_restants_8d > 0]
        if self.value() == 'not_expired':
            return [r for r in queryset if not (r.est_expire_4d or r.est_expire_8d)]
        return queryset


class ReclamationAutoClotureFilter(SimpleListFilter):
    """Filtre sur l'éligibilité à la clôture automatique"""
    title = 'Clôture automatique'
    parameter_name = 'auto_cloture'
    
    def lookups(self, request, model_admin):
        return (
            ('eligible', 'Éligible à la clôture auto'),
            ('not_eligible', 'Non éligible'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'eligible':
            return [r for r in queryset if r.peut_etre_cloturee_auto()]
        if self.value() == 'not_eligible':
            return [r for r in queryset if not r.peut_etre_cloturee_auto()]
        return queryset


# ========== ADMIN INLINES ==========

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
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('produit', 'site', 'site__uap', 'uap_concernee')


class SiteClientInline(admin.TabularInline):
    """Inline pour les sites client"""
    model = SiteClient
    extra = 1
    fields = ['nom', 'ville', 'pays', 'telephone', 'email', 'actif']


class Action8DInline(admin.TabularInline):
    """Inline pour les actions 8D"""
    model = Action8D
    extra = 1
    fields = ['type_action', 'action', 'pilote', 'date_prevue', 'statut', 'avancement', 'efficacite']
    classes = ['collapse']


class Participant8DInline(admin.TabularInline):
    """Inline pour les participants 8D"""
    model = Participant8D
    extra = 1
    fields = ['nom', 'fonction', 'role', 'ordre']
    classes = ['collapse']


class Alteration8DInline(admin.TabularInline):
    """Inline pour les altérations 8D"""
    model = Alteration8D
    extra = 1
    fields = ['type_document', 'remarque', 'pilote', 'deadline']
    classes = ['collapse']


class Evidence8DInline(admin.TabularInline):
    """Inline pour les preuves 8D"""
    model = Evidence8D
    extra = 1
    fields = ['titre', 'fichier', 'description']
    classes = ['collapse']


class CauseIshikawaInline(admin.TabularInline):
    """Inline pour les causes Ishikawa"""
    model = CauseIshikawa
    extra = 1
    fields = ['categorie', 'cause', 'type_cause', 'ordre']
    classes = ['collapse']


class CauseCinqPInline(admin.TabularInline):
    """Inline pour les 5 Pourquoi"""
    model = CauseCinqP
    extra = 1
    fields = ['type_cause', 'facteur_prouve', 'pourquoi_1', 'pourquoi_2', 'pourquoi_3', 'pourquoi_4', 'pourquoi_5']
    classes = ['collapse']


class FacteurVRSInline(admin.TabularInline):
    """Inline pour les facteurs VRS"""
    model = FacteurVRS
    extra = 1
    fields = ['categorie', 'facteur_probable', 'standard_suivi', 'facteur_prouve']
    classes = ['collapse']


class EvaluationFacteurHumainInline(admin.TabularInline):
    """Inline pour les évaluations facteurs humains"""
    model = EvaluationFacteurHumain
    extra = 1
    fields = ['categorie', 'numero_critere', 'critere', 'evaluation', 'commentaire']
    classes = ['collapse']
    readonly_fields = ['critere']


# ========== ADMIN PRINCIPAUX ==========

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
    autocomplete_fields = ['ligne_reclamation']
    raw_id_fields = ['ligne_reclamation']
    list_per_page = 20


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = [
        'numero_reclamation', 'date_reclamation', 'client_nom', 
        'programme_nom', 'type_nc', 'imputation', 
        'etat_4d', 'etat_8d', 'cloture', 'statut_affichage'
    ]
    list_filter = [
        'type_nc', 'imputation', 'etat_4d', 'etat_8d', 'cloture',
        'client', 'programme', ReclamationExpirationFilter, ReclamationAutoClotureFilter
    ]
    search_fields = ['numero_reclamation', 'client__nom', 'programme__nom']
    autocomplete_fields = ['client', 'programme', 'site_client', 'createur']
    readonly_fields = ['date_creation', 'date_modification', 'get_date_expiration_4d', 'get_date_expiration_8d']
    inlines = [LigneReclamationInline]
    date_hierarchy = 'date_reclamation'
    list_per_page = 25
    actions = ['auto_cloturer_selected', 'marquer_4d_cloture', 'marquer_8d_cloture']
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'numero_reclamation', 'date_reclamation', 'client', 
                'site_client', 'programme', 'imputation', 'type_nc'
            )
        }),
        ('Démarches qualité', {
            'fields': ('numero_4d', 'numero_8d', 'besoin_4dp'),
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
    
    def statut_affichage(self, obj):
        if obj.cloture:
            return format_html('<span style="color: green;">✓ Clôturée</span>')
        if obj.est_expire_4d or obj.est_expire_8d:
            return format_html('<span style="color: red;">⚠️ Expirée</span>')
        return format_html('<span style="color: orange;">⏳ En cours</span>')
    statut_affichage.short_description = 'Statut'
    
    def auto_cloturer_selected(self, request, queryset):
        cloturees = 0
        for reclamation in queryset:
            if reclamation.auto_cloturer():
                cloturees += 1
        self.message_user(request, f"{cloturees} réclamation(s) clôturée(s) automatiquement.")
    auto_cloturer_selected.short_description = "Clôturer automatiquement les réclamations sélectionnées"
    
    def marquer_4d_cloture(self, request, queryset):
        updated = queryset.filter(etat_4d__in=['OUVERT', 'EN_COURS']).update(etat_4d='CLOTURE')
        self.message_user(request, f"{updated} réclamation(s) marquée(s) 4D clôturé.")
    marquer_4d_cloture.short_description = "Marquer 4D comme clôturé"
    
    def marquer_8d_cloture(self, request, queryset):
        updated = queryset.filter(etat_8d__in=['OUVERT', 'EN_COURS']).update(etat_8d='CLOTURE')
        self.message_user(request, f"{updated} réclamation(s) marquée(s) 8D clôturé.")
    marquer_8d_cloture.short_description = "Marquer 8D comme clôturé"
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.createur = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'client', 'programme', 'site_client', 'createur'
        ).prefetch_related('lignes__produit', 'lignes__site', 'lignes__uap_concernee', 'lignes__non_conformites')


@admin.register(ObjectifsAnnuel)
class ObjectifsAnnuelAdmin(admin.ModelAdmin):
    list_display = ['annee', 'site', 'objectif_rebut', 'objectif_ppm_externe', 'objectif_rework', 'date_modification']
    list_filter = ['annee', 'site']
    list_editable = ['objectif_rebut', 'objectif_ppm_externe', 'objectif_rework']
    search_fields = ['annee', 'site__nom']
    ordering = ['-annee', 'site__nom']


# ========== NOUVEAUX ADMIN POUR LES MODÈLES 8D ==========

@admin.register(HuitD)
class HuitDAdmin(admin.ModelAdmin):
    list_display = ['reclamation', 'etat', 'date_ouverture', 'pilote', 'nb_actions']
    list_filter = ['etat', 'decision_8d', 'huitd_accepte']
    search_fields = ['reclamation__numero_reclamation', 'pilote', 'numero_of']
    readonly_fields = ['date_creation', 'date_modification', 'date_maj']
    
    inlines = [
        Action8DInline, Participant8DInline, Alteration8DInline, 
        Evidence8DInline, CauseIshikawaInline, CauseCinqPInline
    ]
    
    fieldsets = (
        ('Liaison', {
            'fields': ('reclamation',)
        }),
        ('En-tête', {
            'fields': ('ref', 'version', 'date_maj')
        }),
        ('Informations générales', {
            'fields': ('numero_of', 'date_ouverture', 'designation_piece', 'numero_article', 
                      'numero_nc', 'client', 'interne', 'lieu_detection')
        }),
        ('D1 - Caractérisation (5W2H)', {
            'fields': ('d1_qui', 'd1_quoi', 'd1_ou', 'd1_quand', 'd1_comment', 
                      'd1_combien', 'd1_pourquoi', 'd1_caracterisation', 
                      'd1_probleme_connu', 'd1_risque', 'd1_risque_detail'),
            'classes': ('collapse',)
        }),
        ('D2 - Actions d\'urgence', {
            'fields': ('d2_date', 'd2_actions', 'd2_tri', 'd2_of_concernes', 
                      'd2_quantite_rebutee', 'd2_quantite_retoucher'),
            'classes': ('collapse',)
        }),
        ('D3 - Équipe', {
            'fields': ('d3_date', 'pilote', 'pilote_fonction', 'animateur', 'animateur_fonction'),
            'classes': ('collapse',)
        }),
        ('D4 - Analyse préliminaire', {
            'fields': ('d4_date', 'd4_causes_apparition', 'd4_causes_non_detection', 'decision_8d'),
            'classes': ('collapse',)
        }),
        ('D5 - Causes racines', {
            'fields': ('d5_causes_occurrence', 'd5_causes_non_detection'),
            'classes': ('collapse',)
        }),
        ('D7 - Vérification', {
            'fields': ('d7_verification', 'd7_suffisant'),
            'classes': ('collapse',)
        }),
        ('D8 - Transversalisation', {
            'fields': ('d8_transversalisation',),
            'classes': ('collapse',)
        }),
        ('Décision HCIM', {
            'fields': ('huitd_accepte', 'decision_hcim'),
            'classes': ('collapse',)
        }),
        ('Clôture', {
            'fields': ('etat', 'fin_huitd', 'fin_huitd_signature'),
            'classes': ('collapse',)
        })
    )
    
    def nb_actions(self, obj):
        return obj.nb_actions
    nb_actions.short_description = "Nb actions"
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Mettre à jour l'état 8D de la réclamation parente
        if obj.reclamation.etat_8d != obj.etat:
            obj.reclamation.etat_8d = obj.etat
            obj.reclamation.save()


@admin.register(CinqW2H)
class CinqW2HAdmin(admin.ModelAdmin):
    list_display = ['huitd', 'date']
    fieldsets = (
        ('Client View', {
            'fields': ('c_what_happened', 'c_who_detected', 'c_where_detected', 
                      'c_when_detected', 'c_how_detected', 'c_how_many', 
                      'c_why_problem', 'c_logistic_impact', 'c_other_customers_delivered', 
                      'c_other_customers_defect')
        }),
        ('HCIM View', {
            'fields': ('h_symptoms', 'h_defects_ruled_out', 'h_where_created', 
                      'h_when_generated', 'h_rework', 'h_detection_expected', 
                      'h_reinjection', 'h_known_problem', 'h_last_reported')
        }),
        ('Métadonnées', {
            'fields': ('nom', 'site', 'date', 'suivi'),
            'classes': ('collapse',)
        })
    )


@admin.register(VRS)
class VRSAdmin(admin.ModelAdmin):
    list_display = ['huitd', 'suivi']
    inlines = [FacteurVRSInline]


@admin.register(FacteurHumain)
class FacteurHumainAdmin(admin.ModelAdmin):
    list_display = ['huitd']
    inlines = [EvaluationFacteurHumainInline]


@admin.register(Action8D)
class Action8DAdmin(admin.ModelAdmin):
    list_display = ['action_courte', 'type_action', 'pilote', 'date_prevue', 
                   'statut', 'avancement', 'est_retard']
    list_filter = ['type_action', 'statut', 'date_prevue']
    search_fields = ['action', 'pilote']
    list_editable = ['statut', 'avancement']
    actions = ['marquer_realise', 'marquer_en_cours']
    
    def action_courte(self, obj):
        return obj.action[:50] + "..." if len(obj.action) > 50 else obj.action
    action_courte.short_description = 'Action'
    
    def est_retard(self, obj):
        if obj.en_retard:
            return format_html('<span style="color: red;">⚠️ En retard</span>')
        return format_html('<span style="color: green;">✓ À jour</span>')
    est_retard.short_description = 'Retard'
    
    def marquer_realise(self, request, queryset):
        updated = queryset.update(statut='REALISE', avancement=100, date_realisee=timezone.now().date())
        self.message_user(request, f"{updated} action(s) marquée(s) réalisée(s).")
    marquer_realise.short_description = "Marquer comme réalisé"
    
    def marquer_en_cours(self, request, queryset):
        updated = queryset.update(statut='EN_COURS')
        self.message_user(request, f"{updated} action(s) marquée(s) en cours.")
    marquer_en_cours.short_description = "Marquer comme en cours"


@admin.register(Livraison)
class LivraisonAdmin(admin.ModelAdmin):
    list_display = ['client', 'date_livraison', 'quantite_livree', 'numero_bon_livraison']
    list_filter = ['date_livraison', 'client']
    search_fields = ['client__nom', 'numero_bon_livraison', 'reference_commande']
    date_hierarchy = 'date_livraison'


@admin.register(ArticleFAI)
class ArticleFAIAdmin(admin.ModelAdmin):
    list_display = ['produit', 'numero_of', 'derniere_production', 'statut', 'date_analyse', 'commentaire']
    list_filter = ['statut', 'derniere_production']
    search_fields = ['produit__product_number', 'numero_of', 'commentaire']
    list_editable = ['statut']
    actions = ['marquer_alerte', 'marquer_urgent', 'marquer_critique']
    
    def marquer_alerte(self, request, queryset):
        queryset.update(statut='ALERTE')
        self.message_user(request, "Articles marqués comme Alerte")
    marquer_alerte.short_description = "Marquer comme Alerte"
    
    def marquer_urgent(self, request, queryset):
        queryset.update(statut='URGENT')
        self.message_user(request, "Articles marqués comme Urgent")
    marquer_urgent.short_description = "Marquer comme Urgent"
    
    def marquer_critique(self, request, queryset):
        queryset.update(statut='CRITIQUE')
        self.message_user(request, "Articles marqués comme Critique")
    marquer_critique.short_description = "Marquer comme Critique"


@admin.register(HistoriqueImportFAI)
class HistoriqueImportFAIAdmin(admin.ModelAdmin):
    list_display = ['date_import', 'fichier_nom', 'lignes_importees', 'lignes_modifiees']
    list_filter = ['date_import']
    readonly_fields = ['date_import', 'fichier_nom', 'lignes_importees', 'lignes_modifiees', 'erreurs']