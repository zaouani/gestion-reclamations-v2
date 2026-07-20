import json
import logging
import time
from typing import Generator

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.utils.dashboard_stats import DashboardStats
from reclamations.notifications import NotificationService
from reclamations.services.ai_service import AIService
from reclamations.services.ollama_service import OllamaService


logger = logging.getLogger(__name__)

ollama_service = OllamaService(model="phi3:mini") 
moyenne_reactivite=100 
ollama_service = OllamaService(model="llama3.2:3b")
# ====================== CHATBOT VIEWS ======================
 
@login_required
def chatbot_ollama_status(request):
    """Vérifie si Ollama est disponible"""
    try:
        is_connected = ollama_service.test_connection()
        models = ollama_service.list_models() if is_connected else []
       
        return JsonResponse({
            'ollama_available': is_connected,
            'models': models,
            'current_model': ollama_service.model,
            'status': 'OK' if is_connected else 'Ollama non démarré'
        })
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return JsonResponse({
            'ollama_available': False,
            'error': str(e)
        }, status=500)

# API Chatbot 
@login_required
def api_chatbot(request):
    """Endpoint non-streaming (alternative au streaming)"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        historique = data.get('historique', [])
 
        if not user_message:
            return JsonResponse({'error': 'Message vide'}, status=400)
 
        # Utilise Ollama si disponible, sinon fallback
        if ollama_service.test_connection():
            result = ollama_service.get_response(user_message, historique)
            reponse = result.get('reponse', '')
            suggestions = result.get('suggestions', [])
        else:
            reponse = traiter_message_chatbot(user_message, historique)
            suggestions = generer_suggestions(user_message)
 
        return JsonResponse({
            'reponse': reponse,
            'suggestions': suggestions
        })
 
    except Exception as e:
        logger.exception("Error in api_chatbot")
        return JsonResponse({'error': 'Erreur interne'}, status=500)

@login_required
def chat_stream(request):
    """Endpoint principal pour le streaming du chatbot"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        historique = data.get('historique', [])
 
        if not user_message:
            return JsonResponse({'error': 'Message vide'}, status=400)
 
        response = StreamingHttpResponse(
            stream_generator(user_message, historique),
            content_type='text/event-stream',
        )
       
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
       
        return response
 
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    except Exception as e:
        logger.exception("Error in chat_stream")
        return JsonResponse({'error': 'Erreur interne du serveur'}, status=500)
 
def stream_generator(message: str, historique: list) -> Generator:
    """Streaming optimisé - plus rapide et plus naturel"""
    try:
        if ollama_service.test_connection():
            result = ollama_service.get_response(message, historique)
            reponse_complete = result.get('reponse', '')
        else:
            reponse_complete = traiter_message_chatbot(message, historique)
    except Exception as e:
        logger.warning(f"Ollama failed: {e}")
        reponse_complete = traiter_message_chatbot(message, historique)
 
    # Version améliorée : on envoie par mots au lieu de caractère par caractère
    words = reponse_complete.split(' ')
    for i, word in enumerate(words):
        yield (word + ' ').encode('utf-8')
        # Pause variable : plus courte pour les mots courts
        time.sleep(0.1 if len(word) > 8 else 0.04)
 
    # Petit délai final pour que le dernier mot s’affiche bien
    time.sleep(1)
 
def traiter_message_chatbot(message: str, historique: list = None) -> str:
    """Fallback manuel quand Ollama n'est pas disponible"""
    if historique is None:
        historique = []
   
    message_lower = message.lower().strip()
 
    if any(word in message_lower for word in ['bonjour', 'salut', 'coucou', 'hello', 'hi']):
        return "Bonjour ! Je suis votre assistant qualité. Comment puis-je vous aider aujourd'hui ?"
 
    elif any(word in message_lower for word in ['réclamation', 'reclamation']):
        if any(word in message_lower for word in ['créer', 'nouvelle', 'ajouter']):
            return "Pour créer une nouvelle réclamation, cliquez sur 'Nouvelle réclamation' dans le menu. Renseignez le client, le produit et décrivez le problème."
        elif any(word in message_lower for word in ['statut', 'suivi']):
            return "Pour voir le statut d'une réclamation, allez dans 'Liste des réclamations' et recherchez par numéro ou client."
        else:
            return "Les réclamations sont accessibles via le menu 'Réclamations'. Vous pouvez les lister, les filtrer et exporter les données."
 
    elif any(word in message_lower for word in ['délai', 'retard', 'échéance']):
        return "Les échéances et réclamations en retard sont visibles dans l'onglet 'Échéances' du menu principal."
 
    elif 'dashboard' in message_lower or 'tableau' in message_lower or 'kpi' in message_lower:
        return "Le Dashboard affiche les indicateurs clés : nombre de réclamations, taux de clôture, PPM, etc. Accédez-y depuis le menu principal."
 
    elif 'ppm' in message_lower:
        return "Le PPM mesure la qualité fournisseur. Vous pouvez le consulter par client dans la section dédiée.\nObjectif général : < 1000 PPM."
 
    elif any(word in message_lower for word in ['8d', '4d']):
        return "La méthode 8D est utilisée pour résoudre les problèmes qualité. Chaque réclamation importante dispose d'une fiche 8D dédiée."
 
    elif 'aide' in message_lower or 'help' in message_lower:
        return ("Je peux vous aider sur :\n"
                "• Créer ou suivre une réclamation\n"
                "• Consulter le dashboard et les statistiques\n"
                "• Comprendre le PPM et la méthode 8D\n"
                "• Gestion des produits et clients\n\n"
                "Que souhaitez-vous faire ?")
 
    else:
        return ("Je n'ai pas bien compris votre demande.\n\n"
                "Essayez de me parler de :\n"
                "• Réclamations\n"
                "• Dashboard\n"
                "• PPM\n"
                "• 8D\n\n"
                "Ou tapez 'aide'.")
 
def generer_suggestions(message: str) -> list:
    """Génère des suggestions contextuelles pour le frontend"""
    message_lower = message.lower().strip()
   
    if any(k in message_lower for k in ['dashboard', 'statistique', 'kpi']):
        return ['Voir le dashboard', 'Export Excel', 'Graphiques PPM']
   
    elif any(k in message_lower for k in ['réclamation', 'reclamation']):
        return ['Créer une réclamation', 'Liste des réclamations', 'Réclamations en retard']
   
    elif 'ppm' in message_lower:
        return ['PPM par client', 'Tendance PPM', 'Objectifs qualité']
   
    elif any(k in message_lower for k in ['8d', '4d']):
        return ['Voir fiche 8D', 'Modifier états', 'Actions correctives']
   
    else:
        return ['Dashboard', 'Liste des réclamations', 'Créer réclamation', 'Aide']
 
# ====================== CHATBOT SUGGESTIONS ======================
 
# Suggestions that will always be shown to the user (quick start ideas)
CHATBOT_SUGGESTIONS = [
    "Créer une nouvelle réclamation",
    "Liste des réclamations",
    "Consulter le PPM",
    "Réclamations en retard",
    "Comment utiliser la méthode 8D ?",
    "Voir les statistiques qualité",
    "Aide"
]

@login_required
def get_chatbot_suggestions(request):
    """Return static suggestions for the chatbot interface"""
    return JsonResponse({
        'suggestions': CHATBOT_SUGGESTIONS
    })

@login_required
def api_analyse_kpis(request):
    """API pour analyser les KPIs avec IA - déclenchée à la demande"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        # Récupérer les données
        stats = DashboardStats()
        data = stats.get_all_stats()
        # Récupérer les données de réactivité par UAP
        reactivite_uap_data = data.get('taux_reactivite_par_uap', {})
                # Calculer la moyenne des taux de réactivité par UAP pour l'année courante
        moyenne_reactivite = 0
        annee_courante = timezone.now().year
    
        if reactivite_uap_data and annee_courante in reactivite_uap_data:
            annees_data = reactivite_uap_data.get(annee_courante, {})
            data_mensuelle = annees_data.get('data', {})
            
            # Récupérer tous les taux
            tous_les_taux = []
            for mois, uap_data in data_mensuelle.items():
                for uap, taux in uap_data.items():
                    if taux > 0:  # Ne compter que les UAP avec des données
                        tous_les_taux.append(taux)
            
            # Calculer la moyenne
            if tous_les_taux:
                moyenne_reactivite = sum(tous_les_taux) / len(tous_les_taux)
        
        # Préparer les données pour l'IA
        kpis_data = {
            'total_reclamations': data.get('global', {}).get('total', 0),
            'taux_cloture': data.get('global', {}).get('taux_cloture', 0),
            'taux_reactivite': round(moyenne_reactivite, 1),
            'duree_moyenne': data.get('delai_moyen', 0),
            'ppm_global': data.get('ppm', {}).get('global', 0),
            'nqc_total': data.get('nqc', {}).get('mois', {}).get('total_nqc', 0),
            'top_clients_nqc': data.get('nqc', {}).get('par_client', [])[:5],
            'uap_risque': []
        }
        
        # Analyser avec IA
        ai_service = AIService()
        analyse = ai_service.analyser_kpis(kpis_data)
        
        return JsonResponse(analyse)
        
    except Exception as e:
        logger.exception("Erreur lors de l'analyse des KPIs avec IA")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'diagnostic': "Erreur d'analyse",
            'actions_prioritaires': [],
            'recommandations': []
        }, status=500)

@login_required
@role_required(['admin', 'quality_manager', 'quality_coordinator'])
def envoyer_notifications(request):
    """Envoyer les notifications groupées"""
    if request.method == 'POST':
        service = NotificationService()
        resultats = service.envoyer_notifications_groupes()
        
        messages.success(
            request, 
            f"{resultats['emails_envoyes']} email(s) envoyé(s) - "
            f"{resultats['notifications_envoyees']} notification(s) de retard, "
            f"{resultats['alertes_envoyees']} alerte(s)"
        )
        return redirect('reclamations:dashboard')
    
    # GET: afficher la confirmation
    notifications_grouped = NotificationService.get_notifications_grouped()
    total_retard = sum(len(data['retard']) for data in notifications_grouped.values())
    total_alerte = sum(len(data['alerte']) for data in notifications_grouped.values())
    
    context = {
        'total_retard': total_retard,
        'total_alerte': total_alerte,
        'destinataires': len(notifications_grouped),
        'notifications_grouped': notifications_grouped
    }
    return render(request, 'reclamations/notifications/confirmation_envoi.html', context)
