// AI Chatbot with OpenAI Function Calling
let chatThreadId = null;
let chatOpen = false;

// Initialize chatbot
function initChatbot() {
    // Ensure chatbot starts closed
    chatOpen = false;
    
    // Clear thread ID on refresh - start fresh conversation each time
    chatThreadId = null;
    localStorage.removeItem('chatbot_thread_id');
    
    // Create chatbot HTML
    createChatbotUI();
    
    // Setup event listeners
    setupChatbotListeners();
    
    // Ensure chatbot window is hidden on init
    const chatWindow = document.getElementById('chatbot-window');
    const toggle = document.getElementById('chatbot-toggle');
    if (chatWindow) chatWindow.style.display = 'none';
    if (toggle) toggle.style.display = 'flex';
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
    const chatWindow = document.getElementById('chatbot-window');
    const toggle = document.getElementById('chatbot-toggle');
    
    if (!chatWindow || !toggle) return;
    
    if (chatOpen) {
        // Closing chatbot
        chatOpen = false;
        chatWindow.style.display = 'none';
        toggle.style.display = 'flex';
    } else {
        // Opening chatbot
        chatOpen = true;
        chatWindow.style.display = 'flex';
        toggle.style.display = 'none';
        
        // Focus input
        const input = document.getElementById('chatbot-input');
        if (input) {
            setTimeout(() => input.focus(), 100);
        }
        
        // Load welcome message if no messages
        const messagesContainer = document.getElementById('chatbot-messages');
        if (messagesContainer && messagesContainer.children.length === 0) {
            addMessage('assistant', 'Hi! I can help you check market odds, place bets, view your portfolio, and get news. What would you like to know?');
        }
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
                thread_id: chatThreadId,
                stream: true
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            addMessage('assistant', `Sorry, I encountered an error: ${errorData.error || 'Unknown error'}`);
            showTyping(false);
            return;
        }
        
        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let assistantMessageElement = null;
        let fullResponse = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.done) {
                            // Save thread ID
                            if (data.thread_id) {
                                chatThreadId = data.thread_id;
                                localStorage.setItem('chatbot_thread_id', chatThreadId);
                            }
                            
                            // Check if bet was placed (we'd need to detect this differently)
                            // For now, we'll check the response content
                            if (fullResponse.toLowerCase().includes('bet placed') && wallet) {
                                await loadUserBalance();
                            }
                            
                            showTyping(false);
                            return;
                        }
                        
                        if (data.chunk) {
                            // Create message element on first chunk
                            if (!assistantMessageElement) {
                                assistantMessageElement = addMessageStreaming('assistant');
                            }
                            
                            // Append chunk to message
                            fullResponse += data.chunk;
                            if (assistantMessageElement) {
                                const contentDiv = assistantMessageElement.querySelector('.chatbot-message-content');
                                if (contentDiv) {
                                    // Use textContent during streaming for performance
                                    contentDiv.textContent = fullResponse;
                                    // Scroll to bottom
                                    const messagesContainer = document.getElementById('chatbot-messages');
                                    if (messagesContainer) {
                                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                    }
                                }
                            }
                            
                            // Save thread ID if provided
                            if (data.thread_id) {
                                chatThreadId = data.thread_id;
                                localStorage.setItem('chatbot_thread_id', chatThreadId);
                            }
                        }
                        
                        // Handle bet metadata (sent separately from chunks)
                        if (data.bet_metadata && data.bet_metadata.bet_placed) {
                            const { request_id, market_id, amount, side } = data.bet_metadata;
                            // Poll for bet completion and refresh UI
                            pollChatbotBetStatus(request_id, market_id, amount, side);
                        }
                        
                        if (data.done && assistantMessageElement && fullResponse) {
                            // Format final message with markdown
                            const contentDiv = assistantMessageElement.querySelector('.chatbot-message-content');
                            if (contentDiv) {
                                contentDiv.innerHTML = formatMessage(fullResponse);
                            }
                            
                            // Check for bet metadata in final message
                            if (data.bet_metadata && data.bet_metadata.bet_placed) {
                                const { request_id, market_id, amount, side } = data.bet_metadata;
                                pollChatbotBetStatus(request_id, market_id, amount, side);
                            }
                        }
                    } catch (e) {
                        console.error('Error parsing SSE data:', e);
                    }
                }
            }
        }
        
        showTyping(false);
    } catch (error) {
        console.error('Chat error:', error);
        addMessage('assistant', 'Sorry, I\'m having trouble connecting. Please try again.');
        showTyping(false);
    }
}

function addMessage(role, content) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (!messagesContainer) return null;
    
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
    
    return messageDiv;
}

function addMessageStreaming(role) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (!messagesContainer) return null;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chatbot-message chatbot-message-${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'chatbot-message-content';
    contentDiv.textContent = ''; // Start empty for streaming
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    return messageDiv;
}

function formatMessage(content) {
    if (!content) return '';
    
    // First escape HTML to prevent XSS
    const escapeDiv = document.createElement('div');
    escapeDiv.textContent = content;
    let escaped = escapeDiv.innerHTML;
    
    // Convert **bold** to <strong>
    escaped = escaped.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
    
    // Convert line breaks to <br> (handle multiple line breaks)
    escaped = escaped.replace(/\n\n+/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');
    
    // Convert bullet lists (- or •)
    escaped = escaped.replace(/<br>-\s+([^<]+)/g, '<br>• $1');
    escaped = escaped.replace(/<br>•\s+([^<]+)/g, '<br>• $1');
    
    // Convert numbered lists (1. 2. 3.)
    escaped = escaped.replace(/(\d+)\.\s+\*\*([^<]+)<\/strong>/g, 
        '<div class="chat-list-item"><span class="chat-list-number">$1.</span> <strong>$2</strong></div>');
    escaped = escaped.replace(/(\d+)\.\s+([^<\n]+)/g, 
        '<div class="chat-list-item"><span class="chat-list-number">$1.</span> $2</div>');
    
    // Convert URLs to links
    escaped = escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" class="chat-link">$1</a>');
    
    // Highlight percentages and Market IDs
    escaped = escaped.replace(/(\d+)%/g, '<span class="chat-percentage">$1%</span>');
    escaped = escaped.replace(/\(Market ID:\s*(\d+)\)/gi, '<span class="chat-market-id">(Market ID: $1)</span>');
    
    // Format market listings better
    escaped = escaped.replace(/<br>-\s+\*\*([^<]+)\*\*\s+-\s+YES:\s+([^%]+)%\s+\|\s+NO:\s+([^%]+)%/g, 
        '<br><div class="chat-market-item"><strong>$1</strong><br><span class="chat-odds">YES: <span class="chat-percentage">$2%</span> | NO: <span class="chat-percentage">$3%</span></span></div>');
    
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

// Poll for bet completion when placed through chatbot
async function pollChatbotBetStatus(requestId, marketId, amount, side) {
    const maxAttempts = 30; // 30 seconds max
    let attempts = 0;
    
    const poll = async () => {
        try {
            const res = await fetch(`/api/bets/${requestId}/status`);
            const data = await res.json();
            
            if (data.success !== undefined && data.status !== 'processing') {
                // Bet completed - refresh UI
                if (data.success) {
                    console.log('Chatbot bet completed, refreshing UI...', { marketId, currentPage: window.location.pathname });
                    
                    // Refresh wallet balance
                    if (typeof loadUserBalance === 'function') {
                        await loadUserBalance();
                    }
                    
                    // Refresh market detail page if we're on it
                    // Check if we're viewing the market detail page for the market we just bet on
                    if (typeof loadMarketDetail === 'function' && window.MARKET_ID) {
                        const currentMarketId = parseInt(window.MARKET_ID, 10);
                        const betMarketId = parseInt(marketId, 10);
                        if (currentMarketId === betMarketId) {
                            console.log('Refreshing market detail page for MARKET_ID:', window.MARKET_ID);
                            // Force refresh by clearing any cached prices
                            if (typeof currentPrices !== 'undefined') {
                                currentPrices = null;
                            }
                            await loadMarketDetail();
                            
                            // Trigger glow animation on the odds button for the side that was bet on
                            setTimeout(() => {
                                const glowClass = side === 'YES' ? 'bet-complete-glow-yes' : 'bet-complete-glow-no';
                                const oddsBtn = side === 'YES' ? document.getElementById('yesOddsBtn') : document.getElementById('noOddsBtn');
                                if (oddsBtn) {
                                    oddsBtn.classList.add(glowClass);
                                    // Remove class after animation completes
                                    setTimeout(() => {
                                        oddsBtn.classList.remove(glowClass);
                                    }, 1500);
                                }
                            }, 100); // Small delay to ensure DOM is updated
                            
                            // Also force update trade preview to reflect new prices
                            if (typeof updateTradePreview === 'function') {
                                updateTradePreview();
                            }
                        } else {
                            console.log('Not refreshing market detail - bet on market', betMarketId, 'but viewing market', currentMarketId);
                        }
                    }
                    
                    // Always refresh home markets (to update prices in market list)
                    if (typeof loadHomeMarkets === 'function') {
                        console.log('Refreshing home markets list');
                        await loadHomeMarkets();
                        
                        // Trigger glow animation on the market card for the side that was bet on
                        setTimeout(() => {
                            const marketCard = document.querySelector(`.market-card[href="/market/${marketId}"]`);
                            if (marketCard) {
                                const glowClass = side === 'YES' ? 'bet-complete-glow-yes' : 'bet-complete-glow-no';
                                const oddsBtn = marketCard.querySelector(side === 'YES' ? '.odds-yes' : '.odds-no');
                                if (oddsBtn) {
                                    oddsBtn.classList.add(glowClass);
                                    // Remove class after animation completes
                                    setTimeout(() => {
                                        oddsBtn.classList.remove(glowClass);
                                    }, 1500);
                                }
                            }
                        }, 100); // Small delay to ensure DOM is updated
                    }
                    
                    // Refresh user bets (if on my-bets page)
                    if (typeof loadUserBets === 'function') {
                        await loadUserBets();
                    }
                    
                    console.log('UI refresh complete');
                }
                return;
            }
            
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 1000); // Poll every second
            }
        } catch (e) {
            console.error('Error polling chatbot bet status', e);
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 1000);
            }
        }
    };
    
    poll();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChatbot);
} else {
    initChatbot();
}

