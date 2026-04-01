# reclamations/services/ai_service.py
import requests
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AIService:
    """Service d'analyse IA pour les KPIs qualité"""
    
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "tinyllama"
    
    def __init__(self):
        self.is_available = self._check_ollama()
    
    def _check_ollama(self) -> bool:
        """Vérifie si Ollama est disponible"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def analyser_kpis(self, kpis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse les KPIs et propose des actions correctives"""
        if not self.is_available:
            return self._get_fallback_response(kpis_data)
        
        prompt = self._construire_prompt_analytique(kpis_data)
        
        try:
            response = requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.5,
                    "max_tokens": 500
                },
                timeout=45
            )
            
            if response.status_code == 200:
                result = response.json()
                return self._analyser_reponse_avancee(result.get('response', ''), kpis_data)
            else:
                return self._get_fallback_response(kpis_data)
                
        except Exception as e:
            logger.error(f"Erreur IA: {e}")
            return self._get_fallback_response(kpis_data)
    
    def _construire_prompt_analytique(self, kpis: Dict) -> str:
        """Construit un prompt analytique basé sur les KPIs"""
        
        # Analyse des KPIs pour générer un contexte
        contexte = []
        
        # Taux de clôture
        taux_cloture = kpis.get('taux_cloture', 0)
        if taux_cloture < 70:
            contexte.append(f"⚠️ Taux de clôture critique ({taux_cloture}%): trop de réclamations restent ouvertes")
        elif taux_cloture < 85:
            contexte.append(f"⚡ Taux de clôture à améliorer ({taux_cloture}%)")
        
        # Réactivité
        taux_reactivite = kpis.get('taux_reactivite', 0)
        if taux_reactivite < 60:
            contexte.append(f"⚠️ Réactivité insuffisante ({taux_reactivite}%): délais de traitement trop longs")
        
        # Délai moyen
        duree_moyenne = kpis.get('duree_moyenne', 0)
        if duree_moyenne > 20:
            contexte.append(f"⚠️ Délai moyen trop élevé ({duree_moyenne} jours)")
        
        # PPM
        ppm = kpis.get('ppm_global', 0)
        if ppm > 1000:
            contexte.append(f"⚠️ Qualité produit dégradée (PPM: {ppm})")
        
        # Coût NQC
        nqc_total = kpis.get('nqc_total', 0)
        if nqc_total > 50000:
            contexte.append(f"⚠️ Coût de non-qualité élevé ({nqc_total:,.0f}€)")
        
        # Analyse des clients problématiques
        top_clients = kpis.get('top_clients_nqc', [])
        if top_clients:
            clients_text = []
            for c in top_clients[:3]:
                if isinstance(c, dict):
                    name = c.get('client__nom', c.get('client', 'Client'))
                    cout = c.get('cout_total', c.get('cout', 0))
                    clients_text.append(f"{name} ({cout:,.0f}€)")
            contexte.append(f"🎯 Clients critiques: {', '.join(clients_text)}")
        
        contexte_text = "\n".join(contexte) if contexte else "✅ Tous les indicateurs sont dans les normes acceptables."
        
        prompt = f"""Tu es un expert qualité. Voici l'analyse des KPIs:

{contexte_text}

Données détaillées:
- Total réclamations: {kpis.get('total_reclamations', 0)}
- Taux de clôture: {taux_cloture}%
- Taux de réactivité: {taux_reactivite}%
- Délai moyen: {duree_moyenne} jours
- PPM Global: {ppm}
- Coût NQC total: {nqc_total:,.0f}€

En te basant sur l'analyse ci-dessus, propose:

1. DIAGNOSTIC: Quel est le principal problème identifié?
2. CAUSES: Quelles sont les causes probables?
3. ACTIONS: 3 actions concrètes prioritaires à mener
4. RECOMMANDATIONS: 2 recommandations stratégiques

Sois précis et actionable. Réponds en français."""
        
        return prompt
    
    def _analyser_reponse_avancee(self, reponse: str, kpis: Dict) -> Dict:
        """Analyse la réponse et structure les recommandations"""
        
        # Extraire les sections
        sections = {
            'diagnostic': "",
            'causes': "",
            'actions': [],
            'recommandations': []
        }
        
        current_section = None
        for ligne in reponse.split('\n'):
            ligne = ligne.strip()
            if not ligne:
                continue
            
            ligne_lower = ligne.lower()
            if 'diagnostic' in ligne_lower or 'problème' in ligne_lower:
                current_section = 'diagnostic'
                continue
            elif 'cause' in ligne_lower:
                current_section = 'causes'
                continue
            elif 'action' in ligne_lower or 'prioritaire' in ligne_lower:
                current_section = 'actions'
                continue
            elif 'recommandation' in ligne_lower or 'stratégique' in ligne_lower:
                current_section = 'recommandations'
                continue
            
            if current_section == 'diagnostic':
                sections['diagnostic'] += ligne + " "
            elif current_section == 'causes':
                sections['causes'] += ligne + " "
            elif current_section == 'actions':
                if ligne.startswith(('-', '•', '*', '1.', '2.', '3.')):
                    sections['actions'].append(ligne.lstrip('-•*0123456789. '))
            elif current_section == 'recommandations':
                if ligne.startswith(('-', '•', '*', '1.', '2.')):
                    sections['recommandations'].append(ligne.lstrip('-•*0123456789. '))
        
        # Si pas d'extraction, utiliser des valeurs par défaut basées sur les KPIs
        if not sections['actions']:
            sections['actions'] = self._generer_actions_par_defaut(kpis)
        if not sections['recommandations']:
            sections['recommandations'] = self._generer_recommandations_par_defaut(kpis)
        
        return {
            'analyse': reponse,
            'diagnostic': sections['diagnostic'].strip() or self._diagnostic_par_defaut(kpis),
            'causes': sections['causes'].strip() or "Non identifiées",
            'actions_prioritaires': sections['actions'][:3],
            'recommandations': sections['recommandations'][:2]
        }
    
    def _generer_actions_par_defaut(self, kpis: Dict) -> List[str]:
        """Génère des actions basées sur les KPIs"""
        actions = []
        
        if kpis.get('taux_cloture', 0) < 80:
            actions.append("Mettre en place un suivi quotidien des réclamations ouvertes")
        if kpis.get('taux_reactivite', 0) < 70:
            actions.append("Automatiser les relances pour les réclamations dépassant 15 jours")
        if kpis.get('duree_moyenne', 0) > 15:
            actions.append("Former les équipes à la méthode 8D pour accélérer les résolutions")
        if kpis.get('ppm_global', 0) > 500:
            actions.append("Lancer une analyse des causes racines sur les produits les plus critiques")
        
        if not actions:
            actions = ["Maintenir les bonnes pratiques actuelles", "Effectuer des audits réguliers"]
        
        return actions[:3]
    
    def _generer_recommandations_par_defaut(self, kpis: Dict) -> List[str]:
        """Génère des recommandations basées sur les KPIs"""
        recos = []
        
        if kpis.get('nqc_total', 0) > 30000:
            recos.append("Réaliser un benchmark des coûts de non-qualité par processus")
        if kpis.get('ppm_global', 0) > 1000:
            recos.append("Renforcer le contrôle qualité en réception")
        
        recos.append("Organiser des revues qualité mensuelles avec les parties prenantes")
        
        return recos[:2]
    
    def _diagnostic_par_defaut(self, kpis: Dict) -> str:
        """Génère un diagnostic basé sur les KPIs"""
        if kpis.get('taux_cloture', 0) < 70:
            return "Risque élevé d'accumulation de réclamations non traitées"
        elif kpis.get('taux_reactivite', 0) < 60:
            return "Réactivité insuffisante impactant la satisfaction client"
        elif kpis.get('ppm_global', 0) > 1000:
            return "Problème qualité produit récurrent"
        return "Performance globale satisfaisante"
    
    def _get_fallback_response(self, kpis: Dict) -> Dict:
        """Réponse par défaut basée sur les KPIs réels"""
        return {
            'analyse': "Analyse basée sur les données disponibles.",
            'diagnostic': self._diagnostic_par_defaut(kpis),
            'causes': self._identifier_causes(kpis),
            'actions_prioritaires': self._generer_actions_par_defaut(kpis),
            'recommandations': self._generer_recommandations_par_defaut(kpis)
        }
    
    def _identifier_causes(self, kpis: Dict) -> str:
        """Identifie les causes probables"""
        causes = []
        if kpis.get('taux_reactivite', 0) < 70:
            causes.append("Processus de traitement non optimisé")
        if kpis.get('duree_moyenne', 0) > 20:
            causes.append("Manque de ressources dédiées")
        if kpis.get('ppm_global', 0) > 1000:
            causes.append("Défauts récurrents sur certaines références")
        return ", ".join(causes) if causes else "À investiguer"
    
