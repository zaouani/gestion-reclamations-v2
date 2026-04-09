from django.urls import path
from . import views

app_name = 'reclamations'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('produits/recurrence/', views.taux_recurrence_produits, name='taux_recurrence_produits'),
    path('produits/<int:product_id>/recurrence/', views.detail_recurrence_produit, name='detail_recurrence_produit'),
    
    # Taux de récurrence des NC (tous produits confondus)
    path('recurrence/nc/', views.taux_recurrence_nc, name='taux_recurrence_nc'),
    path('recurrence/nc/<path:description>/', views.detail_recurrence_nc, name='detail_recurrence_nc'),
    path('recurrence/nc/<path:description>/', views.detail_recurrence_nc, name='detail_recurrence_nc'),
    
    # Gestion des reclamations
    path('liste/', views.liste_reclamations, name='liste'),
    path('creer/', views.creer_reclamation, name='creer'),
    path('<int:pk>/', views.detail_reclamation, name='detail_reclamation'),
    path('<int:pk>/modifier-etats/', views.modifier_etats, name='modifier_etats'),
    path('<int:pk>/ajouter-ligne/', views.ajouter_ligne, name='ajouter_ligne'),
    path('<int:pk>/supprimer/', views.supprimer_reclamation, name='supprimer_reclamation'),
    path('<int:pk>/modifier/', views.modifier_reclamation, name='modifier_reclamation'),
    
    # Gestion des UAP
    path('uap/', views.liste_uap, name='liste_uap'),
    path('uap/creer/', views.creer_uap, name='creer_uap'),
    path('uap/<int:pk>/modifier/', views.modifier_uap, name='modifier_uap'),
    path('uap/<int:pk>/supprimer/', views.supprimer_uap, name='supprimer_uap'),
    
    # Gestion des Sites
    path('sites/', views.liste_sites, name='liste_sites'),
    path('sites/creer/', views.creer_site, name='creer_site'),
    path('sites/<int:pk>/modifier/', views.modifier_site, name='modifier_site'),
    path('sites/<int:pk>/supprimer/', views.supprimer_site, name='supprimer_site'),
    
    # Gestion des Clients
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/creer/', views.creer_client, name='creer_client'),
    path('clients/<int:pk>/modifier/', views.modifier_client, name='modifier_client'),
    path('clients/<int:pk>/supprimer/', views.supprimer_client, name='supprimer_client'),
    
    # Gestion des Produits
    path('produits/', views.liste_produits, name='liste_produits'),
    path('produits/creer/', views.creer_produit, name='creer_produit'),
    path('produits/<int:pk>/modifier/', views.modifier_produit, name='modifier_produit'),
    path('produits/<int:pk>/supprimer/', views.supprimer_produit, name='supprimer_produit'),
    
    # Gestion des objectifs
    path('objectifs/', views.liste_objectifs, name='liste_objectifs'),
    path('objectifs/creer/', views.creer_objectifs_annee, name='creer_objectifs_annee'),
    path('objectifs/<int:annee>/modifier/', views.modifier_objectifs_annee, name='modifier_objectifs_annee'),
    path('objectifs/<int:annee>/supprimer/', views.supprimer_objectifs_annee, name='supprimer_objectifs_annee'),

    # Gestion des Programmes
    path('programmes/', views.liste_programmes, name='liste_programmes'),
    path('programmes/creer/', views.creer_programme, name='creer_programme'),
    path('programmes/<int:pk>/modifier/', views.modifier_programme, name='modifier_programme'),
    path('programmes/<int:pk>/supprimer/', views.supprimer_programme, name='supprimer_programme'),

    # Gestion des Livraisons
    path('livraisons/', views.liste_livraisons, name='liste_livraisons'),
    path('livraisons/ajouter/', views.ajouter_livraison, name='ajouter_livraison'),
    path('livraisons/<int:pk>/modifier/', views.modifier_livraison, name='modifier_livraison'),
    path('livraisons/<int:pk>/supprimer/', views.supprimer_livraison, name='supprimer_livraison'),

    # Notifications
    path('notifications/', views.reclamations_en_retard, name='reclamations_en_retard'),

    # Exports
    path('export/dashboard/pdf/', views.export_dashboard_pdf, name='export_dashboard_pdf'),
    path('export/reclamations/excel/', views.export_reclamations_excel, name='export_reclamations_excel'),
    path('export/dashboard/excel/', views.export_dashboard_excel, name='export_dashboard_excel'),
    
    # Imports
    path('import/produits/', views.import_produits_excel, name='import_produits'),
    path('import/clients/', views.import_clients_excel, name='import_clients'),
    path('import/reclamations/', views.import_reclamations_excel, name='import_reclamations'),
    
    # API AJAX
    path('api/programmes-par-client/', views.programmes_par_client, name='programmes_par_client'),
    path('api/sites-client-par-client/', views.sites_client_par_client, name='sites_client_par_client'),
    path('api/recherche-produits/', views.recherche_produits, name='recherche_produits'),
    path('api/recherche-produits-ajax/', views.recherche_produits_ajax, name='recherche_produits_ajax'),
    path('api/reclamations-client-mois/', views.api_reclamations_client_mois, name='api_reclamations_client_mois'),

    #AI
    path('api/analyse-kpis/', views.api_analyse_kpis, name='api_analyse_kpis'),
    path('chat/stream/', views.chat_stream, name='chat_stream'),
    path('api/chatbot/', views.api_chatbot, name='api_chatbot'),
    path('api/chatbot/suggestions/', views.get_chatbot_suggestions, name='chatbot_suggestions'),

    #AMDEC
    path('amdec/', views.amdec_produit, name='amdec_produit'),
    path('amdec/produit/<int:produit_id>/', views.amdec_produit, name='amdec_produit_detail'),
    path('amdec/export-pdf/', views.amdec_export_pdf, name='amdec_export_pdf'),
    path('amdec/export-pdf/<int:produit_id>/', views.amdec_export_pdf, name='amdec_export_pdf_detail'),
    path('amdec/export-excel/', views.amdec_export_excel, name='amdec_export_excel'),
    path('amdec/export-excel/<int:produit_id>/', views.amdec_export_excel, name='amdec_export_excel_detail'),

    #8D
    path('reclamation/<int:pk>/8d/', views.huitd_detail, name='huitd_detail'),
    path('reclamation/8d/<int:pk>/modifier/', views.huitd_modifier, name='huitd_modifier'),

        # ================ GESTION FAI ================
    # Vérification et alertes
    path('fai/verifier/', views.verifier_alertes_fai, name='verifier_alertes_fai'),
    path('fai/alertes/', views.liste_alertes_fai, name='liste_alertes_fai'),
    path('fai/alertes/<int:pk>/traiter/', views.traiter_alerte_fai, name='traiter_alerte_fai'),
    path('fai/alertes/envoyer/', views.envoyer_alertes_fai, name='envoyer_alertes_fai'),
    path('fai/alertes/of/<int:of_id>/', views.alertes_par_of, name='alertes_par_of'),
    
    # Gestion des OF
    path('fai/of/', views.liste_of, name='liste_of'),
    path('fai/of/<int:pk>/', views.detail_of, name='detail_of'),
    path('fai/of/importer/', views.importer_of_erp, name='importer_of_erp'),
    path('fai/of/<int:pk>/fermer/', views.fermer_of, name='fermer_of'),
    
    # Gestion des produits FAI
    path('fai/produits/', views.liste_produits_fai, name='liste_produits_fai'),
    path('fai/produits/<int:pk>/', views.detail_produit_fai, name='detail_produit_fai'),
    path('fai/produits/<int:pk>/inspection/', views.enregistrer_inspection_fai, name='enregistrer_inspection_fai'),
    
    # API pour l'ERP (intégration)
    path('api/erp/importer-of/', views.api_importer_of, name='api_importer_of'),
    path('api/erp/statut-of/', views.api_statut_of, name='api_statut_of'),
]