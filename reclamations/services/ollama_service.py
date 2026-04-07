import requests
import logging
from typing import List, Dict, Any
 
logger = logging.getLogger(__name__)
 
 
class OllamaService:
    """Service pour interagir avec l'API Ollama (LLM local)"""
 
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        """
        Initialise le service Ollama
       
        Args:
            base_url: URL de base d'Ollama (défaut: http://localhost:11434)
            model: Modèle à utiliser (recommandé: llama3.2:3b ou mistral, phi3, etc.)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_url = f"{self.base_url}/api/generate"
 
    def get_response(self, message: str, historique: List[Dict] = None) -> Dict[str, Any]:
        """
        Obtient une réponse d'Ollama et génère des suggestions.
        En cas d'échec, retourne une réponse de fallback.
        """
        if not message or not message.strip():
            return self._get_fallback_response("empty")
 
        try:
            context = self._build_context(message, historique)
 
            payload = {
                "model": self.model,
                "prompt": context,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 400,     # mieux que max_tokens pour Ollama
                }
            }
 
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60
            )
 
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get('response', '').strip()
 
                suggestions = self._generate_suggestions(message, bot_response)
 
                return {
                    'reponse': bot_response,
                    'suggestions': suggestions
                }
            else:
                logger.error(f"Ollama API error - Status {response.status_code}: {response.text[:200]}")
                return self._get_fallback_response()
 
        except requests.exceptions.Timeout:
            logger.warning("Ollama request timeout")
            return self._get_fallback_response("timeout")
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama - Is 'ollama serve' running?")
            return self._get_fallback_response("connection")
        except Exception as e:
            logger.exception("Unexpected error in OllamaService")
            return self._get_fallback_response()
 
    def _build_context(self, message: str, historique: List[Dict] = None) -> str:
        """Construit le prompt complet avec le system prompt + historique"""
       
        system_prompt = """Tu es un assistant expert en gestion de la qualité et des réclamations clients.
Tu aides les utilisateurs à naviguer dans le système de gestion des réclamations (réclamations, PPM, 8D, 4D, dashboard, etc.).
Réponds toujours en français, de manière professionnelle, concise et utile.
Si la question est hors sujet ou trop complexe, propose poliment de contacter le responsable qualité."""
 
        context = system_prompt + "\n\n"
 
        # Ajout de l'historique (max 10 derniers messages)
        if historique:
            context += "Historique récent de la conversation :\n"
            for msg in historique[-10:]:
                role = "Utilisateur" if msg.get('role') == 'user' else "Assistant"
                content = msg.get('content', '').strip()
                if content:
                    context += f"{role}: {content}\n"
            context += "\n"
 
        context += f"Utilisateur: {message}\nAssistant:"
 
        return context
 
    def _generate_suggestions(self, message: str, bot_response: str = "") -> List[str]:
        """Génère des suggestions contextuelles (logique centralisée)"""
        message_lower = message.lower()
 
        if any(k in message_lower for k in ['dashboard', 'tableau', 'statistique', 'kpi', 'indicateur']):
            return ['Voir le dashboard', 'Export Excel', 'Graphiques PPM', 'Statistiques qualité']
 
        if any(k in message_lower for k in ['réclamation', 'reclamation', 'claim']):
            return ['Créer une réclamation', 'Liste des réclamations', 'Réclamations en retard', 'Mes réclamations']
 
        if 'ppm' in message_lower:
            return ['PPM par client', 'Tendance PPM', 'Objectifs qualité']
 
        if any(k in message_lower for k in ['produit', 'article', 'amdec']):
            return ['Rechercher un produit', 'Produits récurrents', 'AMDEC']
 
        if any(k in message_lower for k in ['8d', '4d', 'résolution', 'action corrective']):
            return ['Voir fiche 8D', 'Modifier états', 'Actions correctives']
 
        if any(k in message_lower for k in ['bonjour', 'salut', 'aide', 'help']):
            return ['Dashboard', 'Liste des réclamations', 'Créer réclamation', 'Aide']
 
        # Suggestions par défaut
        return ['Dashboard', 'Liste des réclamations', 'Créer une réclamation', 'Aide']
 
    def _get_fallback_response(self, error_type: str = "general") -> Dict[str, Any]:
        """Réponse de secours quand Ollama n'est pas disponible"""
       
        messages = {
            "connection": "⚠️ Je ne peux pas me connecter au service Ollama.\nVérifiez que Ollama est lancé (`ollama serve`).",
            "timeout": "⏰ Le service met trop de temps à répondre. Veuillez réessayer.",
            "empty": "Veuillez entrer un message valide.",
            "general": "🔧 Le service d'intelligence est temporairement indisponible.\nVeuillez réessayer ou contacter le support qualité."
        }
 
        return {
            'reponse': messages.get(error_type, messages["general"]),
            'suggestions': ['Voir le dashboard', 'Liste des réclamations', 'Aide']
        }
 
    def test_connection(self) -> bool:
        """Teste la connexion à Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
 
    def list_models(self) -> List[str]:
        """Liste les modèles disponibles dans Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=8)
            if response.status_code == 200:
                data = response.json()
                return [model.get('name') for model in data.get('models', [])]
            return []
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
            return []