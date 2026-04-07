(function() {
    if (window.chatbotInitialized) return;
    window.chatbotInitialized = true;
   
    // ========== SUGGESTIONS FIXES (au-dessus de la zone de saisie) ==========
    const STATIC_SUGGESTIONS = [
        "Voir le dashboard",
        "Créer une nouvelle réclamation",
        "Liste des réclamations",
        "Réclamations en retard",
        "Consulter le PPM",
        "Comment utiliser la méthode 8D ?",
        "Voir les statistiques qualité",
        "Aide"
    ];
 
    // ========== ÉTAT ==========
    let messages = [];
    let isSending = false;
    let currentStreamingDiv = null;
    let accumulatedText = '';
    let dotAnimationInterval = null;
   
    // ========== ÉLÉMENTS DOM ==========
    let elements = {};
   
    // ========== UTILITAIRES ==========
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
   
    function getCsrfToken() {
        const cookieValue = document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
   
    // ========== UI: MESSAGES ==========
    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message user';
        messageDiv.innerHTML = `
            <div class="message-bubble user-bubble">
                ${escapeHtml(text)}
            </div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
 
    let typingIndicator = null;
   
    function showTypingIndicator() {
        // Remove existing if any
        if (typingIndicator && typingIndicator.remove) {
            if (dotAnimationInterval) clearInterval(dotAnimationInterval);
            typingIndicator.remove();
        }
       
        typingIndicator = document.createElement('div');
        typingIndicator.className = 'chat-message bot';
        typingIndicator.id = 'typing-indicator';
        typingIndicator.innerHTML = `
            <div class="message-bubble bot-bubble typing-bubble">
                <span class="thinking-label">thinking</span><span class="thinking-dots"></span>
            </div>
        `;
        elements.messagesContainer.appendChild(typingIndicator);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
       
        // Animate dots after "typing"
        const dotsSpan = typingIndicator.querySelector('.thinking-dots');
        if (dotsSpan) {
            let dotCount = 0;
            dotAnimationInterval = setInterval(() => {
                if (dotsSpan && typingIndicator && typingIndicator.parentElement) {
                    dotCount = (dotCount % 3) + 1;
                    dotsSpan.textContent = '.'.repeat(dotCount);
                } else if (dotAnimationInterval) {
                    clearInterval(dotAnimationInterval);
                }
            }, 500);
        }
    }
   
    function hideTypingIndicator() {
        if (dotAnimationInterval) {
            clearInterval(dotAnimationInterval);
            dotAnimationInterval = null;
        }
        if (typingIndicator && typingIndicator.remove) {
            typingIndicator.remove();
            typingIndicator = null;
        }
    }
 
    function createStreamingMessage() {
        // Don't remove typing indicator yet - we'll replace it when we have data
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot';
        messageDiv.style.display = 'none'; // Hide initially
        messageDiv.innerHTML = `
            <div class="message-bubble bot-bubble streaming-bubble">
                <span class="streaming-content"></span><span class="thinking-cursor">|</span>
            </div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
       
        return {
            div: messageDiv,
            contentSpan: messageDiv.querySelector('.streaming-content'),
            cursorSpan: messageDiv.querySelector('.thinking-cursor'),
            isStreaming: true
        };
    }
 
    function updateStreamingMessage(streamingObj, text) {
        if (!streamingObj || !streamingObj.contentSpan) return;
       
        // First time we get data, hide typing indicator and show streaming message
        if (streamingObj.div.style.display === 'none') {
            hideTypingIndicator();
            streamingObj.div.style.display = 'block';
        }
       
        // Update the content span with the new text
        streamingObj.contentSpan.innerHTML = escapeHtml(text);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
 
    function finalizeStreamingMessage(streamingObj, text) {
        if (!streamingObj || !streamingObj.div) return;
 
        // Replace the streaming message with a final static message
        streamingObj.div.innerHTML = `
            <div class="message-bubble bot-bubble">
                ${escapeHtml(text)}
            </div>
        `;
        streamingObj.div.style.display = 'block';
    }
   
    function addBotMessage(text) {
        hideTypingIndicator();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot';
        messageDiv.innerHTML = `
            <div class="message-bubble bot-bubble">
                ${escapeHtml(text)}
            </div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
   
    function addErrorMessage(error) {
        hideTypingIndicator();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot';
        messageDiv.innerHTML = `
            <div class="message-bubble bot-bubble error-bubble">
                ❌ Désolé, une erreur s'est produite: ${escapeHtml(error)}<br>
                Veuillez réessayer.
            </div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }
   
    // ========== UI: SUGGESTIONS FIXES (au-dessus de l'input) ==========
    function showFixedSuggestions() {
        if (!elements.suggestionsContainer) return;
 
        elements.suggestionsContainer.innerHTML = `
            <div class="suggestions-title">
                <i class="fas fa-lightbulb"></i> Suggestions rapides :
            </div>
            <div class="suggestions-buttons">
                ${STATIC_SUGGESTIONS.map(s => `
                    <button class="suggestion-btn" data-suggestion="${escapeHtml(s)}">
                        ${escapeHtml(s)}
                    </button>
                `).join('')}
            </div>
        `;
       
        elements.suggestionsContainer.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (elements.input && !isSending) {
                    elements.input.value = btn.getAttribute('data-suggestion');
                    sendMessage();
                }
            });
        });
       
        elements.suggestionsContainer.style.display = 'block';
    }
   
    // ========== UI: CONTROLES ==========
    function disableUI() {
        if (elements.send) {
            elements.send.disabled = true;
            elements.send.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        if (elements.input) {
            elements.input.disabled = true;
        }
    }
   
    function enableUI() {
        if (elements.send) {
            elements.send.disabled = false;
            elements.send.innerHTML = '➤';
        }
        if (elements.input) {
            elements.input.disabled = false;
            elements.input.placeholder = 'Votre message...';
            elements.input.focus();
        }
    }
   
    function cleanupStreaming() {
        currentStreamingDiv = null;
        accumulatedText = '';
    }
   
    // ========== MESSAGERIE AVEC STREAMING ==========
    async function sendMessageStreaming(message) {
        currentStreamingDiv = createStreamingMessage();
        accumulatedText = '';
 
        try {
            const response = await fetch('/chat/stream/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    message: message,
                    historique: messages.slice(-20)
                })
            });
 
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
 
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
 
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
 
                const chunk = decoder.decode(value);
                accumulatedText += chunk;
 
                if (currentStreamingDiv) {
                    updateStreamingMessage(currentStreamingDiv, accumulatedText);
                }
            }
 
            finalizeStreamingMessage(currentStreamingDiv, accumulatedText);
            return accumulatedText;
 
        } catch (error) {
            console.error('Erreur streaming:', error);
            if (currentStreamingDiv && currentStreamingDiv.div) {
                currentStreamingDiv.div.remove();
            }
            throw error;
        } finally {
            cleanupStreaming();
        }
    }
   
    // ========== MESSAGERIE STANDARD (FALLBACK) ==========
    async function sendMessageStandard(message) {
        try {
            const response = await fetch('/api/chatbot/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    message: message,
                    historique: messages.slice(-20)
                })
            });
           
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
           
            const data = await response.json();
            addBotMessage(data.reponse);
            return data.reponse;
           
        } catch (error) {
            throw error;
        }
    }
   
    // ========== ENVOI PRINCIPAL ==========
    async function sendMessage() {
        if (isSending) return;
       
        const message = elements.input.value.trim();
        if (!message) return;
       
        isSending = true;
        disableUI();
       
        addUserMessage(message);
        elements.input.value = '';
       
        messages.push({ role: 'user', content: message });
       
        // Show typing indicator immediately
        showTypingIndicator();
 
        try {
            let botResponse;
           
            try {
                botResponse = await sendMessageStreaming(message);
            } catch (streamingError) {
                console.warn('Streaming failed, falling back:', streamingError);
                hideTypingIndicator();
                botResponse = await sendMessageStandard(message);
            }
           
            messages.push({ role: 'assistant', content: botResponse });
           
            if (messages.length > 50) {
                messages = messages.slice(-50);
            }
           
        } catch (error) {
            console.error('Erreur envoi message:', error);
            hideTypingIndicator();
            addErrorMessage(error.message);
        } finally {
            isSending = false;
            enableUI();
            if (elements.input) elements.input.focus();
        }
    }
   
    // ========== CHAT WINDOW TOGGLE ==========
    function toggleChat() {
        if (elements.chatWindow) {
            const isHidden = elements.chatWindow.style.display === 'none';
            elements.chatWindow.style.display = isHidden ? 'flex' : 'none';
           
            if (isHidden && elements.input) {
                setTimeout(() => elements.input.focus(), 100);
            }
        }
    }
   
    // ========== INITIALISATION ==========
    function init() {
        elements = {
            toggle: document.getElementById('chatbotToggle'),
            chatWindow: document.getElementById('chatbotWindow'),
            close: document.getElementById('closeChatbot'),
            input: document.getElementById('chatbotInput'),
            send: document.getElementById('sendChatbot'),
            messagesContainer: document.getElementById('chatbotMessages'),
            suggestionsContainer: document.getElementById('chatbotSuggestions')
        };
       
        if (!elements.messagesContainer) {
            console.error('Éléments du chatbot manquants');
            return;
        }
       
        if (elements.chatWindow) {
            elements.chatWindow.style.display = 'none';
        }
       
        if (elements.messagesContainer.children.length === 0 ) {
            addBotMessage('👋 Bonjour ! Je suis votre assistant spécialisé dans la gestion des réclamations. Comment puis-je vous aider aujourd\'hui ?');
        }
       
        // Show suggestions above input
        showFixedSuggestions();
       
        if (elements.toggle) elements.toggle.addEventListener('click', toggleChat);
        if (elements.close) elements.close.addEventListener('click', toggleChat);
        if (elements.send) elements.send.addEventListener('click', sendMessage);
        if (elements.input) {
            elements.input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
       
        if (elements.chatWindow) {
            elements.chatWindow.addEventListener('click', (e) => e.stopPropagation());
        }
    }
   
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
 
})();