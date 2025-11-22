// AI Chatbot with OpenAI Function Calling
let chatThreadId = null;
let chatOpen = false;

// Initialize chatbot
function initChatbot() {
    // Load thread ID from localStorage
    chatThreadId = localStorage.getItem('chatbot_thread_id');
    
    // Create chatbot HTML
    createChatbotUI();
    
    // Setup event listeners
    setupChatbotListeners();
}

function createChatbotUI() {
    // Check if chatbot already exists
    if (document.getElementById('chatbot-container')) {
        return;
    }
    
    const chatbotHTML = `
        <div id="chatbot-container">
            <div id="chatbot-window" style="display: none;">
                <div class="chatbot-header">
                    <span class="chatbot-title">🤖 Market Assistant</span>
                    <button id="chatbot-close" class="chatbot-close-btn">×</button>
                </div>
                <div id="chatbot-messages" class="chatbot-messages"></div>
                <div id="chatbot-typing" class="chatbot-typing" style="display: none;">
                    <span></span><span></span><span></span>
                </div>
                <div class="chatbot-input-container">
                    <input 
                        type="text" 
                        id="chatbot-input" 
                        class="chatbot-input" 
                        placeholder="Ask about markets, odds, or place a bet..."
                        autocomplete="off"
                    />
                    <button id="chatbot-send" class="chatbot-send-btn">Send</button>
                </div>
            </div>
            <button id="chatbot-toggle" class="chatbot-toggle-btn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="chatbot-icon">
                    <path d="M21 11.5C21.0034 12.8199 20.6951 14.1219 20.1 15.3C19.3944 16.7118 18.3098 17.8992 16.9674 18.7293C15.6251 19.5594 14.0782 19.9994 12.5 20C11.1801 20.0035 9.87812 19.6951 8.7 19.1L3 21L4.9 15.3C4.30493 14.1219 3.99656 12.8199 4 11.5C4.00061 9.92179 4.44061 8.37488 5.27072 7.03258C6.10083 5.69028 7.28825 4.6056 8.7 3.90003C9.87812 3.30496 11.1801 2.99659 12.5 3.00003H13C15.0843 3.11502 17.053 3.99479 18.5291 5.47089C20.0052 6.94699 20.885 8.91568 21 11V11.5Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', chatbotHTML);
}

function setupChatbotListeners() {
    const toggleBtn = document.getElementById('chatbot-toggle');
    const closeBtn = document.getElementById('chatbot-close');
    const sendBtn = document.getElementById('chatbot-send');
    const input = document.getElementById('chatbot-input');
    
    toggleBtn?.addEventListener('click', toggleChatbot);
    closeBtn?.addEventListener('click', toggleChatbot);
    sendBtn?.addEventListener('click', sendMessage);
    
    input?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

function toggleChatbot() {
    const window = document.getElementById('chatbot-window');
    const toggle = document.getElementById('chatbot-toggle');
    
    chatOpen = !chatOpen;
    
    if (chatOpen) {
        window.style.display = 'flex';
        toggle.style.display = 'none';
        document.getElementById('chatbot-input')?.focus();
        
        // Load welcome message if no messages
        if (document.getElementById('chatbot-messages').children.length === 0) {
            addMessage('assistant', 'Hi! I can help you check market odds, place bets, view your portfolio, and get news. What would you like to know?');
        }
    } else {
        window.style.display = 'none';
        toggle.style.display = 'flex';
    }
}

async function sendMessage() {
    const input = document.getElementById('chatbot-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to UI
    addMessage('user', message);
    input.value = '';
    
    // Show typing indicator
    showTyping(true);
    
    // Get wallet address if available
    const wallet = currentAccount || '';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                wallet: wallet,
                thread_id: chatThreadId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Save thread ID
            if (data.thread_id) {
                chatThreadId = data.thread_id;
                localStorage.setItem('chatbot_thread_id', chatThreadId);
            }
            
            // Add assistant response
            addMessage('assistant', data.response);
            
            // If bet was placed, reload balance
            if (data.function_called === 'place_bet' && wallet) {
                await loadUserBalance();
            }
        } else {
            addMessage('assistant', `Sorry, I encountered an error: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessage('assistant', 'Sorry, I\'m having trouble connecting. Please try again.');
    } finally {
        showTyping(false);
    }
}

function addMessage(role, content) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (!messagesContainer) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chatbot-message chatbot-message-${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'chatbot-message-content';
    
    if (role === 'user') {
        contentDiv.textContent = content; // Use textContent for user messages
    } else {
        contentDiv.innerHTML = formatMessage(content); // Use innerHTML for formatted assistant messages
    }
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatMessage(content) {
    // First escape HTML to prevent XSS
    const escapeDiv = document.createElement('div');
    escapeDiv.textContent = content;
    let escaped = escapeDiv.innerHTML;
    
    // Convert **bold** to <strong> (do this before line breaks)
    escaped = escaped.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
    
    // Convert line breaks to <br>
    escaped = escaped.replace(/\n\n/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');
    
    // Convert numbered lists (must be after line breaks)
    escaped = escaped.replace(/(\d+)\.\s+\*\*([^<]+)<\/strong>/g, 
        '<div class="chat-list-item"><span class="chat-list-number">$1.</span> <strong>$2</strong></div>');
    escaped = escaped.replace(/(\d+)\.\s+([^<\n]+)/g, 
        '<div class="chat-list-item"><span class="chat-list-number">$1.</span> $2</div>');
    
    // Convert URLs to links
    escaped = escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" class="chat-link">$1</a>');
    
    // Highlight percentages
    escaped = escaped.replace(/(\d+)%/g, '<span class="chat-percentage">$1%</span>');
    
    return escaped;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showTyping(show) {
    const typing = document.getElementById('chatbot-typing');
    if (typing) {
        typing.style.display = show ? 'flex' : 'none';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChatbot);
} else {
    initChatbot();
}

