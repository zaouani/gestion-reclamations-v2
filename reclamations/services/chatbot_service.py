# reclamations/services/chatbot_service.py
import requests
import logging
from typing import Dict, List, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service de chatbot IA pour assister les utilisateurs"""
    
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "tinyllama"
    
    def __init__(self):
        self.is_available = self._check_ollama()
        self.context = self._init_context()
    
    def _check_ollama(self) -> bool:
        """Vérifie si Ollama est disponible"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _init_context(self) -> Dict:
        """Initialise le contexte du chatbot"""
        return {
            "role": "assistant",
            "personality": "expert qualité",
            "knowledge": [
                "méthode 8D",
                "gestion des réclamations",
                "indicateurs qualité (PPM, NQC)",
                "démarches 4D et 8D"
            ]
        }
    
    def get_response(self, message: str, historique: List[Dict] = None) -> Dict:
        """Génère une réponse du chatbot"""
        if not self.is_available:
            return self._get_fallback_response(message)
        
        prompt = self._construire_prompt(message, historique)
        
        try:
            response = requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                    "max_tokens": 300
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'reponse': result.get('response', ''),
                    'suggestions': self._generer_suggestions(message),
                    'actions': self._extraire_actions(result.get('response', ''))
                }
            else:
                return self._get_fallback_response(message)
                
        except Exception as e:
            logger.error(f"Erreur chatbot: {e}")
            return self._get_fallback_response(message)
    
    def _construire_prompt(self, message: str, historique: List[Dict] = None) -> str:
        """Construit le prompt pour le chatbot"""
        
        system_prompt = """Tu es un assistant expert en qualité industrielle pour une application de gestion des réclamations.
Tu connais:
- La méthode 8D pour résoudre les problèmes
- Les indicateurs qualité (PPM, NQC, taux de réactivité)
- Les démarches 4D et 8D
- Les délais de clôture (2 jours ouvrés pour 4D, 10 pour 8D)

Réponds de manière:
- Concise et professionnelle
- En français
- Avec des suggestions d'actions concrètes si pertinent
- En posant des questions pour clarifier si nécessaire

Question: {message}

Réponse:"""
        
        return system_prompt.format(message=message)
    
    def _generer_suggestions(self, message: str) -> List[str]:
        """Génère des suggestions de questions"""
        suggestions = [
            "Comment créer une réclamation ?",
            "Qu'est-ce que la méthode 8D ?",
            "Comment calculer le taux de réactivité ?",
            "Quels sont les délais pour la 4D et la 8D ?",
            "Comment exporter les données ?",
            "Que faire en cas de dépassement de délai ?"
        ]
        return suggestions[:3]
    
    def _extraire_actions(self, reponse: str) -> List[str]:
        """Extrait les actions de la réponse"""
        actions = []
        lignes = reponse.split('\n')
        for ligne in lignes:
            if any(word in ligne.lower() for word in ['action', 'faire', 'mettre en place', 'vérifier']):
                actions.append(ligne.strip())
        return actions[:2]
    
    def _get_fallback_response(self, message: str) -> Dict:
        """Réponse par défaut"""
        reponses_fallback = {
            "créer réclamation": "Pour créer une réclamation, cliquez sur le bouton 'Nouvelle réclamation' dans le menu.",
            "8d": "La méthode 8D est une démarche de résolution de problèmes en 8 étapes: 1. Préparer, 2. Équipe, 3. Décrire, 4. Actions immédiates, 5. Causes racines, 6. Actions correctives, 7. Prévention, 8. Félicitations.",
            "4d": "La 4D est une démarche simplifiée de résolution de problèmes en 4 étapes: 1. Identifier, 2. Analyser, 3. Corriger, 4. Valider.",
            "délai": "Les délais sont: 2 jours ouvrés pour la 4D, 10 jours ouvrés pour la 8D.",
            "ppm": "Le PPM (Parts Per Million) mesure la qualité: (nombre de pièces défectueuses / nombre de pièces livrées) × 1 000 000.",
            "nqc": "Le NQC (Non-Quality Cost) est le coût de la non-qualité, calculé à partir des réclamations."
        }
        
        message_lower = message.lower()
        for key, reponse in reponses_fallback.items():
            if key in message_lower:
                return {
                    'reponse': reponse,
                    'suggestions': self._generer_suggestions(message),
                    'actions': []
                }
        
        return {
            'reponse': "Je peux vous aider sur la gestion des réclamations, les méthodes qualité (4D, 8D), les indicateurs (PPM, NQC), et les délais de clôture. Que souhaitez-vous savoir ?",
            'suggestions': self._generer_suggestions(message),
            'actions': []
        }