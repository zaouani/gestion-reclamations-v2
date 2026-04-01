// static/js/chatbot.js

// Initialisation du chatbot
if (typeof window.chatbotInitialized === 'undefined') {
    window.chatbotInitialized = true;
    
    document.addEventListener('DOMContentLoaded', function() {
        const toggle = document.getElementById('chatbotToggle');
        const chatbotWindow = document.getElementById('chatbotWindow');
        const close = document.getElementById('closeChatbot');
        const input = document.getElementById('chatbotInput');
        const send = document.getElementById('sendChatbot');
        const messagesContainer = document.getElementById('chatbotMessages');
        const suggestionsContainer = document.getElementById('chatbotSuggestions');
        
        let messages = [];
        chatbotWindow.style.display = 'none';
        
        if (toggle) {
            toggle.addEventListener('click', function(e) {
                e.stopPropagation();
                chatbotWindow.style.display = chatbotWindow.style.display === 'none' ? 'flex' : 'none';
            });
        }
        
        if (close) {
            close.addEventListener('click', function(e) {
                e.stopPropagation();
                chatbotWindow.style.display = 'none';
            });
        }
        
        function sendMessage() {
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'user');
            input.value = '';
            const typingIndicator = addTypingIndicator();
            
            fetch('/api/chatbot/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message, historique: messages })
            })
            .then(response => response.json())
            .then(data => {
                typingIndicator.remove();
                addMessage(data.reponse, 'bot');
                if (data.suggestions && data.suggestions.length > 0) updateSuggestions(data.suggestions);
                messages.push({ role: 'user', content: message });
                messages.push({ role: 'assistant', content: data.reponse });
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            })
            .catch(error => {
                typingIndicator.remove();
                addMessage("Désolé, une erreur s'est produite. Veuillez réessayer.", 'bot');
                console.error('Erreur chatbot:', error);
            });
        }
        
        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${sender}`;
            messageDiv.innerHTML = `<div style="background: ${sender === 'user' ? '#03316e' : 'white'}; color: ${sender === 'user' ? 'white' : '#333'}; padding: 10px; border-radius: 12px; max-width: 85%; display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">${text}</div>`;
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function addTypingIndicator() {
            const indicator = document.createElement('div');
            indicator.className = 'chat-message bot';
            indicator.innerHTML = `<div style="background: white; padding: 10px; border-radius: 12px; display: inline-block;"><i class="fas fa-ellipsis-h"></i></div>`;
            messagesContainer.appendChild(indicator);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return indicator;
        }
        
        function updateSuggestions(suggestions) {
            suggestionsContainer.innerHTML = `<div style="display: flex; gap: 8px; overflow-x: auto; padding-bottom: 5px;">${suggestions.map(s => `<button class="suggestion-btn">${s}</button>`).join('')}</div>`;
            document.querySelectorAll('.suggestion-btn').forEach(btn => btn.addEventListener('click', () => { input.value = btn.textContent; sendMessage(); }));
        }
        
        if (send) send.addEventListener('click', sendMessage);
        if (input) input.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });
        
        document.querySelectorAll('.suggestion-btn').forEach(btn => btn.addEventListener('click', () => { input.value = btn.textContent; sendMessage(); }));
        
        if (chatbotWindow) {
            chatbotWindow.addEventListener('click', function(e) {
                e.stopPropagation();
            });
        }
    });
}