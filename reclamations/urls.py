from django.urls import path
from .views import recurrence, export, dashboard, reclamation, site, client, produit, objectif, programme, livraison, import_views, notification, huitd, pdca, fai, chatbot

app_name = 'reclamations'

urlpatterns = [
    #kpis et dashboard
    path('', dashboard.dashboard, name='dashboard'),
    path('dashboard/big-screen/', dashboard.big_screen_dashboard, name='big_screen_dashboard'),
    path('api/dashboard-data/', dashboard.api_dashboard_data, name='api_dashboard_data'),
    path('qualite/', dashboard.qualite_dashboard, name='qualite_dashboard'),
    path('pdca/dashboard/', dashboard.dashboard_pdca, name='dashboard_pdca'),

    # Exports
    path('export/dashboard/pdf/', export.export_dashboard_pdf, name='export_dashboard_pdf'),
    path('export/reclamations/excel/', export.export_reclamations_excel, name='export_reclamations_excel'),
    path('export/dashboard/excel/', export.export_dashboard_excel, name='export_dashboard_excel'),

    # Taux de récurrence des NC 
    path('taux-recurrence-nc/', recurrence.taux_recurrence_nc, name='taux_recurrence_nc'),
    path('recurrence/nc/<path:description>/', recurrence.detail_recurrence_nc, name='detail_recurrence_nc'),
    path('recurrence/nc/<path:description>/', recurrence.detail_recurrence_nc, name='detail_recurrence_nc'),
    path('produits/recurrence/', recurrence.taux_recurrence_produits, name='taux_recurrence_produits'),
    path('produits/<int:product_id>/recurrence/', recurrence.detail_recurrence_produit, name='detail_recurrence_produit'),
    path('exporter-recurrence-nc/', recurrence.exporter_recurrence_nc_excel, name='exporter_recurrence_nc'),
    path('recurrence/produits/export/', recurrence.export_recurrence_produits_excel, name='export_recurrence_produits'),

    # Gestion des reclamations
    path('liste/', reclamation.liste_reclamations, name='liste'),
    path('creer/', reclamation.creer_reclamation, name='creer'),
    path('<int:pk>/', reclamation.detail_reclamation, name='detail_reclamation'),
    path('<int:pk>/modifier-etats/', reclamation.modifier_etats, name='modifier_etats'),
    path('<int:pk>/supprimer/', reclamation.supprimer_reclamation, name='supprimer_reclamation'),
    path('<int:pk>/modifier/', reclamation.modifier_reclamation, name='modifier_reclamation'),
    path('api/rechercher-descriptions-nc/', reclamation.rechercher_descriptions_nc, name='rechercher_descriptions_nc'),

    # Gestion des UAP
    path('uap/', site.liste_uap, name='liste_uap'),
    path('uap/creer/', site.creer_uap, name='creer_uap'),
    path('uap/<int:pk>/modifier/', site.modifier_uap, name='modifier_uap'),
    path('uap/<int:pk>/supprimer/', site.supprimer_uap, name='supprimer_uap'),
    
    # Gestion des Sites
    path('sites/', site.liste_sites, name='liste_sites'),
    path('sites/creer/', site.creer_site, name='creer_site'),
    path('sites/<int:pk>/modifier/', site.modifier_site, name='modifier_site'),
    path('sites/<int:pk>/supprimer/', site.supprimer_site, name='supprimer_site'),
    
    # Gestion des Clients
    path('clients/', client.liste_clients, name='liste_clients'),
    path('clients/creer/', client.creer_client, name='creer_client'),
    path('clients/<int:pk>/modifier/', client.modifier_client, name='modifier_client'),
    path('clients/<int:pk>/supprimer/', client.supprimer_client, name='supprimer_client'),
    
    # Gestion des Produits
    path('produits/', produit.liste_produits, name='liste_produits'),
    path('produits/creer/', produit.creer_produit, name='creer_produit'),
    path('produits/<int:pk>/modifier/', produit.modifier_produit, name='modifier_produit'),
    path('produits/<int:pk>/supprimer/', produit.supprimer_produit, name='supprimer_produit'),
    
    # Gestion des objectifs
    path('objectifs/', objectif.liste_objectifs, name='liste_objectifs'),
    path('objectifs/creer/', objectif.creer_objectifs_annee, name='creer_objectifs_annee'),
    path('objectifs/<int:annee>/modifier/', objectif.modifier_objectifs_annee, name='modifier_objectifs_annee'),
    path('objectifs/<int:annee>/supprimer/', objectif.supprimer_objectifs_annee, name='supprimer_objectifs_annee'),

    # Gestion des Programmes
    path('programmes/', programme.liste_programmes, name='liste_programmes'),
    path('programmes/creer/', programme.creer_programme, name='creer_programme'),
    path('programmes/<int:pk>/modifier/', programme.modifier_programme, name='modifier_programme'),
    path('programmes/<int:pk>/supprimer/', programme.supprimer_programme, name='supprimer_programme'),

    # Gestion des Livraisons
    path('livraisons/', livraison.liste_livraisons, name='liste_livraisons'),
    path('livraisons/ajouter/', livraison.ajouter_livraison, name='ajouter_livraison'),
    path('livraisons/<int:pk>/modifier/', livraison.modifier_livraison, name='modifier_livraison'),
    path('livraisons/<int:pk>/supprimer/', livraison.supprimer_livraison, name='supprimer_livraison'),

    # Notifications
    path('notifications/', notification.reclamations_en_retard, name='reclamations_en_retard'),
    
    # Imports
    path('import/produits/', import_views.import_produits_excel, name='import_produits'),
    path('import/clients/', import_views.import_clients_excel, name='import_clients'),
    path('import/reclamations/', import_views.import_reclamations_excel, name='import_reclamations'),
    
    # API AJAX
    path('api/programmes-par-client/', reclamation.programmes_par_client, name='programmes_par_client'),
    path('api/sites-client-par-client/', reclamation.sites_client_par_client, name='sites_client_par_client'),
    path('api/recherche-produits/', reclamation.recherche_produits, name='recherche_produits'),
    path('api/recherche-produits-ajax/', produit.recherche_produits_ajax, name='recherche_produits_ajax'),
    path('api/reclamations-client-mois/', reclamation.api_reclamations_client_mois, name='api_reclamations_client_mois'),

    #AI 
    path('api/analyse-kpis/', chatbot.api_analyse_kpis, name='api_analyse_kpis'),
    path('chat/stream/', chatbot.chat_stream, name='chat_stream'),
    path('api/chatbot/', chatbot.api_chatbot, name='api_chatbot'),
    path('api/chatbot/suggestions/', chatbot.get_chatbot_suggestions, name='chatbot_suggestions'),

    # 8D 
    path('8d/creer/<int:reclamation_id>/', huitd.huitd_creer, name='huitd_creer'),
    path('8d/<int:pk>/', huitd.huitd_detail, name='huitd_detail'),
    path('8d/<int:pk>/modifier/', huitd.huitd_modifier, name='huitd_modifier'),
    path('8d/evidence/<int:pk>/supprimer/', huitd.huitd_supprimer_evidence, name='huitd_supprimer_evidence'),
    path('reclamation/<int:pk>/marquer-8d-na/', huitd.marquer_8d_non_applicable, name='marquer_8d_na'),
    path('reclamation/<int:pk>/annuler-8d-na/', huitd.annuler_8d_non_applicable, name='annuler_8d_na'),
    
    # ========== PDCA ==========
    path('pdca/<int:pk>/modifier/', pdca.pdca_modifier, name='pdca_modifier'),

    # ================ GESTION FAI ================
    path('fai/importer/', fai.importer_fai, name='importer_fai'),
    path('fai/configurer-chemin/', fai.configurer_chemin_fai, name='configurer_chemin_fai'),
    path('fai/synchroniser/', fai.synchroniser_fai, name='synchroniser_fai'),
    path('fai/liste/', fai.liste_fai, name='liste_fai'),
    path('fai/exporter-alertes/', fai.exporter_alertes_fai, name='exporter_alertes_fai'),
    path('fai/envoyer-alertes/', fai.envoyer_alertes_fai_email, name='envoyer_alertes_email'),
]