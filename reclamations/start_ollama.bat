@echo off
echo Démarrage d'Ollama...
start /B ollama serve
timeout /t 5 /nobreak
echo Téléchargement du modèle mistral...
ollama pull mistral
echo Ollama prêt !