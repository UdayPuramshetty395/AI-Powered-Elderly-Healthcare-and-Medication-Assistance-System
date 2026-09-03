/**
 * Chatbot JS - AI Healthcare Assistant
 */

let isTyping = false;
let selectedElder = null;

function getSelectedLanguage() {
    const select = document.getElementById('language-select');
    return select ? select.value : 'en';
}

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    initChatbot();
    loadConversationHistory();
    loadSuggestions();
});

function initChatbot() {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message || isTyping) return;

        addMessage(message, 'user');
        input.value = '';
        await sendMessageToBot(message);
    });

    input?.addEventListener('input', () => {
        sendBtn.disabled = !input.value.trim();
    });

    document.getElementById('clear-chat')?.addEventListener('click', clearChat);
    document.getElementById('voice-btn')?.addEventListener('click', startVoiceInput);
}

async function sendMessageToBot(message) {
    isTyping = true;
    showTypingIndicator();

    const payload = { message, language: getSelectedLanguage() };
    if (selectedElder) payload.elder_id = selectedElder;

    try {
        const data = await API.post('/chatbot/message', payload);
        hideTypingIndicator();
        isTyping = false;

        if (data && data._ok && data.response) {
            addMessage(data.response, 'assistant');
            if (data.suggestions && data.suggestions.length) {
                updateSuggestions(data.suggestions);
            }
        } else {
            addMessage('I am here to help. Please try again with a short question like “What are my medicines today?”', 'assistant');
            Toast.error('Failed to get response');
        }
    } catch (error) {
        hideTypingIndicator();
        isTyping = false;
        addMessage('I am here to help. Please try again with a short question like “What are my medicines today?”', 'assistant');
        Toast.error('Unable to reach the assistant right now');
    }
}

function addMessage(text, role) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const safeText = typeof text === 'string' ? text : 'I can help with that.';
    const msgDiv = document.createElement('div');
    msgDiv.className = `message-bubble ${role}`;
    msgDiv.innerHTML = `
        <div class="message-content">${escapeHtml(safeText).replace(/\n/g, '<br>')}</div>
        <div class="message-time">${new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'message-bubble assistant';
    indicator.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    document.getElementById('typing-indicator')?.remove();
}

async function loadConversationHistory() {
    const data = await API.get('/chatbot/history');
    if (!data || !data._ok || !data.history.length) return;

    const container = document.getElementById('chat-messages');
    container.innerHTML = '';
    
    data.history.forEach(msg => {
        addMessage(msg.content, msg.role);
    });
}

async function loadSuggestions() {
    const data = await API.get('/chatbot/suggestions');
    if (data && data._ok && data.suggestions) {
        updateSuggestions(data.suggestions);
    }
}

function updateSuggestions(suggestions) {
    const container = document.getElementById('suggestions-panel');
    if (!container) return;

    container.innerHTML = suggestions.slice(0, 4).map(s => 
        `<button class="suggestion-chip" onclick="sendSuggestion('${escapeHtml(s)}')">${escapeHtml(s)}</button>`
    ).join('');
}

function sendSuggestion(text) {
    document.getElementById('chat-input').value = text;
    document.getElementById('chat-form').dispatchEvent(new Event('submit'));
}

async function clearChat() {
    if (!confirmAction('Clear conversation history?')) return;
    const data = await API.delete('/chatbot/clear');
    if (data && data._ok) {
        document.getElementById('chat-messages').innerHTML = '<p class="text-center text-muted py-4">Conversation cleared. Start a new chat!</p>';
        await loadSuggestions();
        Toast.success('Chat history cleared');
    }
}

function startVoiceInput() {
    if (!('webkitSpeechRecognition' in window)) {
        Toast.error('Voice input not supported in this browser');
        return;
    }

    const recognition = new webkitSpeechRecognition();
    recognition.lang = getSelectedLanguage() === 'te' ? 'te-IN' : 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = false;

    const voiceBtn = document.getElementById('voice-btn');
    voiceBtn.classList.add('recording');
    voiceBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Listening...';

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById('chat-input').value = transcript;
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Voice';
        Toast.success('Voice captured!');
    };

    recognition.onerror = () => {
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Voice';
        Toast.error('Voice recognition failed');
    };

    recognition.onend = () => {
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Voice';
    };

    recognition.start();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
