// ========== UTILITY FUNCTIONS (needed early) ==========
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
}

// Global variables
let currentAccount = null;
let currentFilter = 'all';
let allMarkets = [];
let userBalance = 0.0;
const AGE_GATE_KEY = 'ie_age_gate_passed';
const COOKIE_CONSENT_KEY = 'ie_cookie_consent';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initAgeGateModal();
    initCookieConsentBanner();
    const path = window.location.pathname;
    
    // Common initialization
    tryInitWallet();
    
    // Check for persistent queue warning
    checkPersistentQueueWarning();
    
    // Page-specific initialization
    if (path === '/' || path === '/index.html') {
        initHomePage();
    } else if (path.startsWith('/market/')) {
        initMarketDetailPage();
    } else if (path === '/my-bets') {
        initMyBetsPage();
    } else if (path === '/resolved') {
        // Resolved markets page is handled by inline script in template
        tryInitWallet();
    } else if (path === '/profile') {
        initProfilePage();
    } else if (path === '/admin') {
        initAdminDashboard();
    } else if (path === '/admin/create-market') {
        initAdminCreateMarket();
    } else if (path === '/admin/resolve') {
        initAdminResolvePage();
    }
});

function initAgeGateModal() {
    const modal = document.getElementById('AgeJurisdictionGate');
    const root = document.documentElement;
    if (!modal) {
        document.body.classList.remove('age-gate-locked');
        if (root) {
            root.classList.remove('age-gate-prelock');
            if (!root.dataset.ageGateStatus) {
                root.dataset.ageGateStatus = 'passed';
            }
        }
        return;
    }
    
    const form = document.getElementById('ageGateForm');
    const errorEl = document.getElementById('ageGateError');
    const checkboxes = modal.querySelectorAll('input[type="checkbox"]');
    const hasPassed = localStorage.getItem(AGE_GATE_KEY) === 'true';
    
    toggleAgeGateVisibility(!hasPassed);
    
    if (form) {
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            
            if (!allChecked) {
                if (errorEl) {
                    errorEl.textContent = 'Please confirm all required statements to continue.';
                }
                return;
            }
            
            if (errorEl) {
                errorEl.textContent = '';
            }
            localStorage.setItem(AGE_GATE_KEY, 'true');
            toggleAgeGateVisibility(false);
        });
    }
    
    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            if (errorEl) {
                errorEl.textContent = '';
            }
        });
    });
}

function toggleAgeGateVisibility(showModal) {
    const modal = document.getElementById('AgeJurisdictionGate');
    if (!modal) return;
    const root = document.documentElement;
    
    if (showModal) {
        modal.classList.remove('age-gate-hidden');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('age-gate-locked');
        if (root) {
            root.dataset.ageGateStatus = 'required';
            root.classList.add('age-gate-prelock');
        }
    } else {
        modal.classList.add('age-gate-hidden');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('age-gate-locked');
        if (root) {
            root.dataset.ageGateStatus = 'passed';
            root.classList.remove('age-gate-prelock');
        }
    }
}

function initCookieConsentBanner() {
    const banner = document.getElementById('cookieConsentBanner');
    if (!banner) return;
    
    const acceptBtn = document.getElementById('cookieAcceptBtn');
    const manageBtn = document.getElementById('cookieManageBtn');
    const hasConsent = localStorage.getItem(COOKIE_CONSENT_KEY) === 'accepted';
    
    toggleCookieBanner(!hasConsent);
    
    if (acceptBtn) {
        acceptBtn.addEventListener('click', () => {
            localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');
            toggleCookieBanner(false);
        });
    }
    
    if (manageBtn) {
        manageBtn.addEventListener('click', () => {
            window.location.href = '/gdpr#cookies';
        });
    }
}

function toggleCookieBanner(showBanner) {
    const banner = document.getElementById('cookieConsentBanner');
    if (!banner) return;
    
    if (showBanner) {
        banner.classList.remove('cookie-consent-hidden');
        banner.setAttribute('aria-hidden', 'false');
    } else {
        banner.classList.add('cookie-consent-hidden');
        banner.setAttribute('aria-hidden', 'true');
    }
}

// ========== UTILITY FUNCTIONS ==========
function formatNumberWithCommas(num, decimals = 2) {
    // Format number with commas (thousands separators)
    if (num === null || num === undefined || isNaN(num)) {
        return '0';
    }
    const numValue = parseFloat(num);
    if (decimals === 0) {
        return Math.round(numValue).toLocaleString('en-US');
    }
    return numValue.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatNumber(num) {
    // Format number with k/m notation and 3 significant figures
    if (num >= 1000000) {
        const millions = num / 1000000;
        // Format to 3 significant figures
        if (millions >= 100) {
            return Math.round(millions) + 'm';
        } else if (millions >= 10) {
            return millions.toFixed(1) + 'm';
        } else {
            return millions.toFixed(2) + 'm';
        }
    } else if (num >= 1000) {
        const thousands = num / 1000;
        // Format to show 1 decimal place for numbers between 10k-100k, 2 decimals for smaller
        if (thousands >= 100) {
            return Math.round(thousands) + 'k';
        } else if (thousands >= 10) {
            return thousands.toFixed(1) + 'k';
        } else {
            return thousands.toFixed(2) + 'k';
        }
    } else {
        // For numbers < 1000, show as integer
        return Math.round(num).toString();
    }
}

// ========== HOME PAGE ==========
function initHomePage() {
    // Setup wallet connection
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
    // Setup filters
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilter = this.dataset.filter;
            filterMarkets();
        });
    });
    
    // Setup search
    const searchInput = document.getElementById('searchMarkets');
    if (searchInput) {
        searchInput.addEventListener('input', filterMarkets);
    }
    
    // Load user balance
    loadUserBalance();
    
    // Load markets
    loadHomeMarkets();
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh markets every 5 seconds to show live odds updates
    setInterval(loadHomeMarkets, 5000);
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

async function loadHomeMarkets() {
    try {
        const res = await fetch('/api/markets');
        const data = await res.json();
        allMarkets = data.markets || [];
        
        // Update stats
        updateHomeStats(allMarkets);
        
        // Display markets
        filterMarkets();
        
        document.getElementById('marketsLoading').style.display = 'none';
    } catch (e) {
        console.error('Failed to load markets', e);
        document.getElementById('marketsLoading').style.display = 'none';
        document.getElementById('marketsEmpty').style.display = 'block';
    }
}

function updateHomeStats(markets) {
    const totalMarkets = markets.length;
    const totalVolume = markets.reduce((sum, m) => sum + (m.yes_total || 0) + (m.no_total || 0), 0);
    const uniqueWallets = new Set();
    
    document.getElementById('totalMarkets').textContent = totalMarkets;
    document.getElementById('totalVolume').textContent = `€${formatNumber(totalVolume)}`;
    document.getElementById('totalTraders').textContent = uniqueWallets.size || '0';
}

function filterMarkets() {
    const searchTerm = document.getElementById('searchMarkets')?.value.toLowerCase() || '';
    
    let filtered = allMarkets;
    
    // Filter by category
    if (currentFilter !== 'all') {
        filtered = filtered.filter(m => (m.category || '').toLowerCase() === currentFilter);
    }
    
    // Filter by search
    if (searchTerm) {
        filtered = filtered.filter(m => 
            (m.question || '').toLowerCase().includes(searchTerm) ||
            (m.description || '').toLowerCase().includes(searchTerm)
        );
    }
    
    renderHomeMarkets(filtered);
}

function renderHomeMarkets(markets) {
    const container = document.getElementById('marketsList');
    if (!container) return;
    
    if (!markets.length) {
        container.innerHTML = '';
        document.getElementById('marketsEmpty').style.display = 'block';
        return;
    }
    
    document.getElementById('marketsEmpty').style.display = 'none';
    
    container.innerHTML = markets.map(m => {
        const yesTotal = m.yes_total || 0;
        const noTotal = m.no_total || 0;
        const total = yesTotal + noTotal;
        const yesPercent = total > 0 ? ((yesTotal / total) * 100).toFixed(0) : 50;
        const noPercent = total > 0 ? ((noTotal / total) * 100).toFixed(0) : 50;
        
        const statusClass = m.status === 'resolved' ? 'status-resolved' : 'status-open';
        const statusText = m.status === 'resolved' ? `Resolved: ${m.resolution}` : 'Open';
        
        const imageUrl = m.image_url || 'https://via.placeholder.com/800x400/1E293B/3B82F6?text=No+Image';
        
        return `
            <a href="/market/${m.id}" class="market-card">
                <img src="${imageUrl}" alt="${escapeHtml(m.question)}" class="market-card-image" onerror="this.src='https://via.placeholder.com/800x400/1E293B/3B82F6?text=No+Image'">
                <div class="market-card-body">
                    ${m.category ? `<span class="market-category">${escapeHtml(m.category)}</span>` : ''}
                    <h5 class="market-question">${escapeHtml(m.question)}</h5>
                    <p class="market-description">${escapeHtml(m.description || '')}</p>
                    
                    <div class="market-odds">
                        <div class="odds-btn odds-yes">
                            <span class="odds-percentage">${yesPercent}%</span>
                            <span class="odds-label">YES</span>
                        </div>
                        <div class="odds-btn odds-no">
                            <span class="odds-percentage">${noPercent}%</span>
                            <span class="odds-label">NO</span>
                        </div>
                    </div>
                    
                    <div class="market-stats">
                        <span>$${formatNumberWithCommas(total, 0)} volume</span>
                        <span class="market-status-badge ${statusClass}">${statusText}</span>
                    </div>
                </div>
            </a>
        `;
    }).join('');
}

// ========== ACTIVITY FEED ==========
let previousActivityIds = new Set(); // Track previous transaction IDs for animation

async function loadActivityFeed() {
    const feedContainer = document.getElementById('activityFeed');
    if (!feedContainer) return;
    
    try {
        const response = await fetch('/api/activity/recent');
        const data = await response.json();
        
        if (data.activity && data.activity.length > 0) {
            // Group transactions by market
            const marketsMap = {};
            data.activity.forEach(item => {
                if (!marketsMap[item.market_id]) {
                    marketsMap[item.market_id] = {
                        market_id: item.market_id,
                        question: item.question,
                        image_url: item.image_url,
                        transactions: [],
                        totalVolume: 0
                    };
                }
                marketsMap[item.market_id].transactions.push(item);
                marketsMap[item.market_id].totalVolume += item.amount || 0;
            });
            
            // Sort markets by total volume (largest first)
            const sortedMarkets = Object.values(marketsMap).sort((a, b) => b.totalVolume - a.totalVolume);
            
            // Sort transactions within each market by time (newest first for display)
            sortedMarkets.forEach(market => {
                market.transactions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            });
            
            // Render grouped by market
            feedContainer.innerHTML = sortedMarkets.map(market => {
                const transactionsHtml = market.transactions.map(item => {
                    // Handle missing or invalid probability_change
                    const probChange = item.probability_change != null && !isNaN(item.probability_change) ? 
                                      parseFloat(item.probability_change) : 0;
                    const changeClass = probChange > 0 ? 'positive' : 
                                      probChange < 0 ? 'negative' : 'neutral';
                    const changeIcon = probChange > 0 ? '↑' : 
                                     probChange < 0 ? '↓' : '→';
                    const changeText = probChange !== 0 ? 
                                     `${changeIcon} ${Math.abs(probChange).toFixed(1)}%` : 
                                     '—';
                    
                    // Format wallet address (shortened)
                    const walletShort = item.wallet ? `${item.wallet.slice(0, 6)}...${item.wallet.slice(-4)}` : 'Unknown';
                    
                    // Format timestamp
                    const date = new Date(item.created_at);
                    const timeAgo = getTimeAgo(date);
                    
                    // Check if this is a new transaction
                    const isNew = !previousActivityIds.has(item.id);
                    const rollClass = isNew ? 'rolling-in' : '';
                    
                    return `
                        <div class="activity-transaction ${rollClass}" data-transaction-id="${item.id}">
                            <span class="activity-item-side ${item.side.toLowerCase()}">${item.side}</span>
                            <span class="activity-amount">${formatNumberWithCommas(item.amount, 2)} EURC</span>
                            <span class="activity-shares">${formatNumberWithCommas(item.shares, 2)} shares</span>
                            <span class="activity-item-wallet">${walletShort}</span>
                            <span class="activity-item-time">${timeAgo}</span>
                            <div class="activity-transaction-prob">
                                <span class="activity-probability-value">${(item.current_probability != null && !isNaN(item.current_probability)) ? parseFloat(item.current_probability).toFixed(1) : '0.0'}%</span>
                                <span class="activity-probability-change ${changeClass} ${probChange !== 0 ? 'flash' : ''}" data-prob-change="${probChange}">${changeText}</span>
                            </div>
                        </div>
                    `;
                }).join('');
                
                return `
                    <div class="activity-market-group" data-market-id="${market.market_id}">
                        <div class="activity-market-header" onclick="handleMarketHeaderClick(event)">
                            <img src="${market.image_url || '/static/images/default-market.jpg'}" 
                                 alt="Market" 
                                 class="activity-market-image"
                                 onerror="this.src='/static/images/default-market.jpg'">
                            <div class="activity-market-title">${escapeHtml(market.question)}</div>
                            <div class="activity-resize-handle" onmousedown="handleResizeStart(event)"></div>
                        </div>
                        <div class="activity-transactions-list">
                            ${transactionsHtml}
                        </div>
                    </div>
                `;
            }).join('');
            
            // Update previous activity IDs
            const currentIds = new Set(data.activity.map(item => item.id));
            previousActivityIds = currentIds;
            
            // Initialize resize handlers
            initializeResizeHandlers();
            
            // Scroll to show newest transactions (scroll to left)
            setTimeout(() => {
                const transactionLists = feedContainer.querySelectorAll('.activity-transactions-list');
                transactionLists.forEach(list => {
                    list.scrollLeft = 0; // Scroll to newest (leftmost)
                });
            }, 100);
            
            // Remove roll-in animation class after animation completes
            setTimeout(() => {
                const rollingElements = feedContainer.querySelectorAll('.activity-transaction.rolling-in');
                rollingElements.forEach(el => {
                    el.classList.remove('rolling-in');
                });
            }, 600);
            
        } else {
            feedContainer.innerHTML = `
                <div class="text-center py-5" style="color: var(--text-secondary);">
                    <p style="font-size: 1rem; font-weight: 500; margin: 0;">No recent activity yet. Be the first to place a trade!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load activity feed:', error);
        feedContainer.innerHTML = `
            <div class="text-center py-5" style="color: var(--text-secondary);">
                <p style="font-size: 1rem; font-weight: 500; margin: 0;">Unable to load activity feed</p>
            </div>
        `;
    }
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return '<1m ago';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// ========== RESIZE HANDLERS ==========
let isResizing = false;
let resizeStartX = 0;
let resizeStartWidth = 0;
let currentResizeHeader = null;

function handleMarketHeaderClick(event) {
    // Don't navigate if clicking on the resize handle or if we're resizing
    if (event.target.classList.contains('activity-resize-handle') || isResizing) {
        return;
    }
    // Find the market ID from the parent group
    const marketGroup = event.currentTarget.closest('.activity-market-group');
    const marketId = marketGroup?.dataset?.marketId;
    if (marketId) {
        window.location.href = `/market/${marketId}`;
    }
}

function handleResizeStart(event) {
    event.preventDefault();
    event.stopPropagation();
    
    isResizing = true;
    currentResizeHeader = event.target.parentElement;
    resizeStartX = event.clientX;
    resizeStartWidth = currentResizeHeader.offsetWidth;
    
    // Add resizing class for visual feedback
    event.target.classList.add('resizing');
    
    // Prevent text selection during drag
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    
    // Add event listeners
    document.addEventListener('mousemove', handleResizeMove);
    document.addEventListener('mouseup', handleResizeEnd);
}

function handleResizeMove(event) {
    if (!isResizing || !currentResizeHeader) return;
    
    const deltaX = event.clientX - resizeStartX;
    const newWidth = resizeStartWidth + deltaX;
    
    // Constrain width between min and max
    const minWidth = 260;
    const maxWidth = 600;
    const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    
    // Apply new width
    currentResizeHeader.style.width = `${constrainedWidth}px`;
}

function handleResizeEnd(event) {
    if (!isResizing || !currentResizeHeader) return;
    
    isResizing = false;
    
    // Save width to localStorage
    const savedWidth = currentResizeHeader.offsetWidth;
    localStorage.setItem('activityMarketHeaderWidth', savedWidth.toString());
    
    // Remove resizing class
    const resizeHandle = currentResizeHeader.querySelector('.activity-resize-handle');
    if (resizeHandle) {
        resizeHandle.classList.remove('resizing');
    }
    
    // Restore cursor and selection
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    
    // Remove event listeners
    document.removeEventListener('mousemove', handleResizeMove);
    document.removeEventListener('mouseup', handleResizeEnd);
    
    currentResizeHeader = null;
}

function initializeResizeHandlers() {
    // Load saved width from localStorage
    const savedWidth = localStorage.getItem('activityMarketHeaderWidth');
    if (savedWidth) {
        const headers = document.querySelectorAll('.activity-market-header');
        headers.forEach(header => {
            header.style.width = `${savedWidth}px`;
        });
    }
}

// ========== MARKET DETAIL PAGE ==========
let selectedSide = null; // 'YES' or 'NO' or null
let expectedShares = null; // Expected shares when trade was submitted (for slippage detection)
let hasBeenInQueue = false; // Track if user has ever entered the queue
let persistentQueueWarning = null; // Persistent warning indicator
// MARKET_ID is set by the template (window.MARKET_ID) or extracted from URL

function initMarketDetailPage() {
    // Check if MARKET_ID is set by template, otherwise extract from URL
    if (typeof window.MARKET_ID === 'undefined' || window.MARKET_ID === null) {
        const pathMatch = window.location.pathname.match(/\/market\/(\d+)/);
        if (pathMatch) {
            window.MARKET_ID = parseInt(pathMatch[1], 10);
        } else {
            console.error('Could not extract MARKET_ID from URL');
            const infoContainer = document.getElementById('marketDetailInfo');
            if (infoContainer) {
                infoContainer.innerHTML = '<div class="alert alert-danger">Market ID not found</div>';
            }
            return;
        }
    }
    
    console.log('Initializing market detail page, MARKET_ID:', window.MARKET_ID);
    
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
    // Setup side selection buttons with explicit checks
    const yesBtn = document.getElementById('selectYesBtn');
    const noBtn = document.getElementById('selectNoBtn');
    
    console.log('Yes button found:', !!yesBtn);
    console.log('No button found:', !!noBtn);
    
    if (yesBtn) {
        yesBtn.addEventListener('click', () => {
            console.log('YES button clicked');
            selectSide('YES');
        });
    } else {
        console.error('selectYesBtn not found in DOM');
    }
    
    if (noBtn) {
        noBtn.addEventListener('click', () => {
            console.log('NO button clicked');
            selectSide('NO');
        });
    } else {
        console.error('selectNoBtn not found in DOM');
    }
    
    // Setup input listener for live preview
    const input = document.getElementById('betAmountInput');
    if (input) {
        input.addEventListener('input', updateTradePreview);
    }
    
    // Setup buy button
    const buyBtn = document.getElementById('buyButton');
    if (buyBtn) {
        buyBtn.addEventListener('click', executeBuy);
    }
    
    // Load user balance
    loadUserBalance();
    
    loadMarketDetail();
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh market prices every 3 seconds to show price changes
    setInterval(loadMarketDetail, 3000);
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

function selectSide(side) {
    console.log('selectSide called with:', side);
    selectedSide = side;
    
    // Update button states
    const yesBtn = document.getElementById('selectYesBtn');
    const noBtn = document.getElementById('selectNoBtn');
    
    if (yesBtn) yesBtn.classList.toggle('selected', side === 'YES');
    if (noBtn) noBtn.classList.toggle('selected', side === 'NO');
    
    // Show amount section (if not already shown)
    const amountSection = document.getElementById('amountSection');
    if (amountSection) {
        amountSection.style.display = 'block';
    }
    
    // Show risk confirmation section
    const riskConfirmationSection = document.getElementById('riskConfirmationSection');
    if (riskConfirmationSection) {
        riskConfirmationSection.style.display = 'block';
    }
    
    // Update buy button text
    const buyBtn = document.getElementById('buyButton');
    if (buyBtn) {
        buyBtn.textContent = `Place Trade`;
    buyBtn.style.display = 'block';
        // Disable until risk confirmation is checked
        buyBtn.disabled = true;
    }
    
    // Setup risk confirmation checkbox listener
    const riskCheckbox = document.getElementById('riskConfirmationCheckbox');
    if (riskCheckbox) {
        riskCheckbox.addEventListener('change', function() {
            if (buyBtn) {
                buyBtn.disabled = !this.checked;
            }
        });
    }
    
    // Keep input value when switching sides - just update preview
    updateTradePreview();
}

let currentPrices = { yes_price: 0.50, no_price: 0.50 };
let previousPrices = { yes_price: 0.50, no_price: 0.50 }; // Track previous prices for animations

async function loadMarketDetail() {
    const marketId = window.MARKET_ID;
    if (!marketId) {
        console.error('MARKET_ID is not set');
        const infoContainer = document.getElementById('marketDetailInfo');
        if (infoContainer) {
            infoContainer.innerHTML = '<div class="alert alert-danger">Market ID not found</div>';
        }
        return;
    }
    
    console.log('Loading market detail for MARKET_ID:', marketId);
    
    try {
        const [marketRes, priceRes, blockchainRes] = await Promise.all([
            fetch(`/api/markets/${marketId}`),
            fetch(`/api/markets/${marketId}/price`),
            fetch(`/api/markets/${marketId}/blockchain-status`).catch(() => ({ ok: false }))
        ]);
        
        const marketData = await marketRes.json();
        
        // Handle price API - it might fail for resolved markets
        let priceData = {};
        try {
            if (priceRes.ok) {
                priceData = await priceRes.json();
            } else {
                // For resolved markets or if price API fails, use prices from market data
                priceData = {
                    yes_price: marketData.market.yes_price,
                    no_price: marketData.market.no_price,
                    yes_price_cents: marketData.market.yes_price_cents,
                    no_price_cents: marketData.market.no_price_cents
                };
                // Ensure we have valid prices
                if (!priceData.yes_price || !priceData.no_price) {
                    priceData.yes_price = marketData.market.yes_price || 0.5;
                    priceData.no_price = marketData.market.no_price || 0.5;
                    priceData.yes_price_cents = priceData.yes_price * 100;
                    priceData.no_price_cents = priceData.no_price * 100;
                }
            }
        } catch (e) {
            console.warn('Price API failed, using market data prices:', e);
            // Use market data prices directly (they should be up-to-date)
            priceData = {
                yes_price: marketData.market.yes_price,
                no_price: marketData.market.no_price,
                yes_price_cents: marketData.market.yes_price_cents,
                no_price_cents: marketData.market.no_price_cents
            };
            // If market data doesn't have prices, calculate from totals
            if (!priceData.yes_price && !priceData.no_price) {
                const yesTotal = marketData.market.yes_total || 0;
                const noTotal = marketData.market.no_total || 0;
                const total = yesTotal + noTotal;
                if (total > 0) {
                    priceData.yes_price = yesTotal / total;
                    priceData.no_price = noTotal / total;
                    priceData.yes_price_cents = priceData.yes_price * 100;
                    priceData.no_price_cents = priceData.no_price * 100;
                } else {
                    // Last resort: use LMSR prices from market data
                    priceData.yes_price = marketData.market.yes_price || 0.5;
                    priceData.no_price = marketData.market.no_price || 0.5;
                    priceData.yes_price_cents = priceData.yes_price * 100;
                    priceData.no_price_cents = priceData.no_price * 100;
                }
            }
        }
        
        // Handle blockchain status
        let blockchainData = { on_blockchain: false };
        try {
            if (blockchainRes.ok) {
                blockchainData = await blockchainRes.json();
            }
        } catch (e) {
            // Ignore blockchain errors
        }
        
        if (!marketData.market) {
            console.error('Market data not found:', marketData);
            const infoContainer = document.getElementById('marketDetailInfo');
            if (infoContainer) {
                infoContainer.innerHTML = '<div class="alert alert-danger">Market not found</div>';
            }
            return;
        }
        
        currentPrices = priceData;
        console.log('Market data loaded, rendering...', marketData.market);
        renderMarketDetail(marketData.market, priceData, blockchainData);
        console.log('Market detail rendered successfully');
        } catch (e) {
        console.error('Failed to load market detail', e);
        console.error('Error stack:', e.stack);
        const infoContainer = document.getElementById('marketDetailInfo');
        if (infoContainer) {
            infoContainer.innerHTML = `<div class="alert alert-danger">Error loading market: ${e.message || 'Unknown error'}</div>`;
        }
    }
}

function renderMarketDetail(market, prices, blockchainData = {}) {
    console.log('renderMarketDetail called with:', { market: market?.id, prices, blockchainData });
    
    const infoContainer = document.getElementById('marketDetailInfo');
    const oddsContainer = document.getElementById('oddsDisplay');
    
    if (!market) {
        console.error('No market data provided to renderMarketDetail');
        if (infoContainer) {
            infoContainer.innerHTML = '<div class="alert alert-danger">No market data available</div>';
        }
        return;
    }
    
    if (!infoContainer) {
        console.error('marketDetailInfo container not found');
        return;
    }
    
    if (!oddsContainer) {
        console.error('oddsDisplay container not found');
        return;
    }
    
    try {
    
    const yesTotal = market.yes_total || 0;
    const noTotal = market.no_total || 0;
    const total = yesTotal + noTotal;
    
    // Use prices from API if available, otherwise fall back to market data
    const yesCents = prices.yes_price_cents !== undefined ? prices.yes_price_cents : (market.yes_price_cents !== undefined ? market.yes_price_cents : (market.yes_price ? market.yes_price * 100 : 50));
    const noCents = prices.no_price_cents !== undefined ? prices.no_price_cents : (market.no_price_cents !== undefined ? market.no_price_cents : (market.no_price ? market.no_price * 100 : 50));
    
    // Calculate price changes
    const prevYesCents = (previousPrices.yes_price || 0.5) * 100;
    const prevNoCents = (previousPrices.no_price || 0.5) * 100;
    const yesChange = yesCents - prevYesCents;
    const noChange = noCents - prevNoCents;
    
    // Determine if animation needed (> 1% change)
    const yesAnimate = Math.abs(yesChange) > 1;
    const noAnimate = Math.abs(noChange) > 1;
    const yesDirection = yesChange > 0 ? 'up' : 'down';
    const noDirection = noChange > 0 ? 'up' : 'down';
    
    // Update previous prices
    previousPrices = {
        yes_price: prices.yes_price || 0.5,
        no_price: prices.no_price || 0.5
    };
    
    const imageUrl = market.image_url || 'https://via.placeholder.com/1200x400/1E293B/3B82F6?text=No+Image';
    
    const blockchainBadge = blockchainData.on_blockchain ? `
        <div class="mb-3">
            <span class="badge bg-success me-2">✓ Verified on Blockchain</span>
            ${blockchainData.etherscan_tx_url ? `<a href="${blockchainData.etherscan_tx_url}" target="_blank" class="btn btn-sm btn-outline-light">View on Etherscan</a>` : ''}
        </div>
    ` : '';
    
    const isResolved = market.status === 'resolved';
    const resolutionBadge = isResolved ? `
        <div class="mb-3">
            <span class="badge ${market.resolution === 'YES' ? 'bg-success' : 'bg-danger'}" style="font-size: 1rem; padding: 0.5rem 1rem;">
                ${market.resolution === 'YES' ? '✓' : '✗'} Resolved: ${market.resolution || 'Unknown'}
            </span>
        </div>
    ` : '';
    
    infoContainer.innerHTML = `
        ${market.image_url ? `<img src="${imageUrl}" alt="${escapeHtml(market.question)}" style="width: 100%; border-radius: 12px; margin-bottom: 2rem;" onerror="this.src='https://via.placeholder.com/1200x400/1E293B/3B82F6?text=No+Image'">` : ''}
        ${market.category ? `<span class="market-category">${escapeHtml(market.category)}</span>` : ''}
        <h1 class="mb-3">${escapeHtml(market.question)}</h1>
        ${blockchainBadge}
        ${resolutionBadge}
        <p class="text-muted mb-4">${escapeHtml(market.description || '')}</p>
        ${market.end_date ? `<p class="text-muted small">Ends: ${market.end_date}</p>` : ''}
        <div class="border-top border-secondary pt-3 mt-3">
            <div class="row">
                <div class="col-md-4">
                    <strong>Status:</strong> 
                    ${isResolved ? `<span class="badge bg-primary">Resolved: ${market.resolution || 'Unknown'}</span>` : '<span class="badge bg-success">Open</span>'}
                </div>
                <div class="col-md-4"><strong>Total Volume:</strong> €${formatNumberWithCommas(total, 2)}</div>
                <div class="col-md-4"><strong>Trades:</strong> ${market.bet_count || 0}</div>
            </div>
        </div>
    `;
    
    // Get existing elements to check if we need rolling animation
    const existingYesBtn = document.getElementById('yesOddsBtn');
    const existingNoBtn = document.getElementById('noOddsBtn');
    const existingYesPrice = document.getElementById('yesPrice');
    const existingNoPrice = document.getElementById('noPrice');
    
    const yesPercent = yesCents.toFixed(1);
    const noPercent = noCents.toFixed(1);
    
    oddsContainer.innerHTML = `
        <div class="odds-btn odds-yes mb-2 ${yesAnimate ? `price-change-flash-yes` : ''}" id="yesOddsBtn">
            <span class="odds-price-container">
                <span class="odds-percentage odds-price-value ${yesAnimate ? `rolling-${yesDirection}` : ''}" id="yesPrice">${yesPercent}%</span>
            </span>
            <span class="odds-label">YES</span>
        </div>
        <div class="odds-btn odds-no ${noAnimate ? `price-change-flash-no` : ''}" id="noOddsBtn">
            <span class="odds-price-container">
                <span class="odds-percentage odds-price-value ${noAnimate ? `rolling-${noDirection}` : ''}" id="noPrice">${noPercent}%</span>
            </span>
            <span class="odds-label">NO</span>
        </div>
        <div class="mt-3 text-muted small text-center">
            Each share pays €1.00 if correct
        </div>
    `;
    
    // Remove animation classes after animation completes
    if (yesAnimate) {
        setTimeout(() => {
            const yesBtn = document.getElementById('yesOddsBtn');
            const yesPriceEl = document.getElementById('yesPrice');
            if (yesBtn) {
                yesBtn.classList.remove('price-change-flash-yes');
            }
            if (yesPriceEl) {
                yesPriceEl.classList.remove(`rolling-${yesDirection}`);
            }
        }, 500);
    }
    
    if (noAnimate) {
        setTimeout(() => {
            const noBtn = document.getElementById('noOddsBtn');
            const noPriceEl = document.getElementById('noPrice');
            if (noBtn) {
                noBtn.classList.remove('price-change-flash-no');
            }
            if (noPriceEl) {
                noPriceEl.classList.remove(`rolling-${noDirection}`);
            }
        }, 500);
    }
    
    // Disable trading if resolved
    const selectYesBtn = document.getElementById('selectYesBtn');
    const selectNoBtn = document.getElementById('selectNoBtn');
    const betAmountInput = document.getElementById('betAmountInput');
    const buyButton = document.getElementById('buyButton');
    
    if (isResolved) {
        if (selectYesBtn) selectYesBtn.disabled = true;
        if (selectNoBtn) selectNoBtn.disabled = true;
        if (betAmountInput) betAmountInput.disabled = true;
        if (buyButton) buyButton.disabled = true;
        
        // Show resolution message
        const tradingMessage = document.getElementById('tradingMessage');
        if (tradingMessage) {
            const resolution = market.resolution || 'Unknown';
            const resolutionClass = resolution === 'YES' ? 'text-success' : 'text-danger';
            tradingMessage.innerHTML = `<div class="alert alert-info mt-3"><strong>Market Resolved:</strong> <span class="${resolutionClass}">${resolution}</span></div>`;
        }
    } else {
        if (selectYesBtn) selectYesBtn.disabled = false;
        if (selectNoBtn) selectNoBtn.disabled = false;
        if (betAmountInput) betAmountInput.disabled = false;
        if (buyButton) buyButton.disabled = false;
        
        // Clear resolution message
        const tradingMessage = document.getElementById('tradingMessage');
        if (tradingMessage) {
            tradingMessage.innerHTML = '';
        }
    }
    
    console.log('Market detail rendered successfully');
    
    } catch (e) {
        console.error('Error rendering market detail:', e);
        console.error('Error stack:', e.stack);
        if (infoContainer) {
            infoContainer.innerHTML = `<div class="alert alert-danger">Error displaying market: ${e.message}</div>`;
        }
    }
}

function updateTradePreview() {
    const inputValue = parseFloat(document.getElementById('betAmountInput').value || 0);
    const previewDiv = document.getElementById('tradePreview');
    const balanceDisplay = document.getElementById('userBalance');
    
    if (inputValue <= 0 || !currentPrices || !selectedSide) {
        // Hide preview if no input or no side selected
        previewDiv.style.display = 'none';
        // Reset balance display to current balance
        if (balanceDisplay) {
            balanceDisplay.innerHTML = `${formatNumberWithCommas(userBalance, 2)} EURC`;
            balanceDisplay.style.color = '';
        }
        return;
    }
    
    // Show preview
    previewDiv.style.display = 'block';
    
    // Calculate based on selected side
    const price = selectedSide === 'YES' ? currentPrices.yes_price : currentPrices.no_price;
    const shares = inputValue / price;
    const roundedShares = Math.round(shares * 100) / 100;
    
    // Potential win is shares * 1 EURC
    const potentialWin = roundedShares * 1.0;
    const profit = potentialWin - inputValue;
    
    // Calculate net amount after 2% fee (only on profits)
    const netProfit = Math.max(0, profit);
    const fee = netProfit * 0.02;  // 2% fee on profits only
    const netAmount = potentialWin - fee;
    
    // Update preview - separate raw profit (white) and net profit (green)
    document.getElementById('previewShares').textContent = `${formatNumberWithCommas(roundedShares, 2)} shares`;
        document.getElementById('previewWinAmount').textContent = `${formatNumberWithCommas(potentialWin, 2)} EURC`;
        document.getElementById('previewWinProfit').textContent = `(+${formatNumberWithCommas(profit, 2)} EURC)`;
    
    // Show "after fee" only if there's a profit
    const afterFeeRow = document.getElementById('previewAfterFeeRow');
    const afterFeeText = document.getElementById('previewAfterFee');
    if (profit > 0 && fee > 0) {
        afterFeeRow.style.display = 'flex';
        afterFeeText.textContent = `(${formatNumberWithCommas(netAmount, 2)} EURC after 2% fee)`;
    } else {
        afterFeeRow.style.display = 'none';
    }
    
    // Update balance display dynamically
    if (balanceDisplay) {
        const remainingBalance = userBalance - inputValue;
        if (remainingBalance < 0) {
            // Insufficient balance - show in red
            balanceDisplay.innerHTML = `<span style="color: var(--red-no); font-weight: 700;">${formatNumberWithCommas(userBalance, 2)} EURC (Insufficient!)</span>`;
        } else {
            // Show only remaining balance (highlighted)
            balanceDisplay.innerHTML = `<span style="color: var(--blue-primary); font-weight: 800;">${formatNumberWithCommas(remainingBalance, 2)} EURC</span>`;
        }
    }
}

function executeBuy() {
    if (!selectedSide) {
        showMessage('Please select Yes or No first', 'error', 'tradingMessage');
        return;
    }
    
    // Check risk confirmation checkbox
    const riskCheckbox = document.getElementById('riskConfirmationCheckbox');
    if (!riskCheckbox || !riskCheckbox.checked) {
        showMessage('Please confirm that you understand the financial risks involved', 'error', 'tradingMessage');
        return;
    }
    
    placeBetOnDetail(selectedSide);
}

async function placeBetOnDetail(side) {
    if (!currentAccount) {
        showMessage('Connect your wallet first.', 'error', 'tradingMessage');
        return;
    }
    
    if (!window.MARKET_ID) {
        showMessage('Market ID is missing', 'error', 'tradingMessage');
        return;
    }
    
    const inputValue = parseFloat(document.getElementById('betAmountInput').value || '0');
    if (!inputValue || inputValue <= 0) {
        showMessage('Enter a valid amount', 'error', 'tradingMessage');
        return;
    }
    
    const amount = Math.round(inputValue * 100) / 100;
    
    // Check if user has sufficient balance
    if (amount > userBalance) {
        showMessage(`Insufficient balance. You have ${formatNumberWithCommas(userBalance, 2)} EURC`, 'error', 'tradingMessage');
        return;
    }
    
    // Get expected shares using LMSR calculation (same as backend) for accurate slippage detection
    try {
        const previewRes = await fetch(`/api/markets/${window.MARKET_ID}/preview?amount=${amount}&side=${side}`);
        if (previewRes.ok) {
            const previewData = await previewRes.json();
            if (previewData.success) {
                expectedShares = previewData.shares;
            } else {
                expectedShares = null;
            }
        } else {
            expectedShares = null;
        }
    } catch (e) {
        console.error('Failed to get trade preview', e);
        expectedShares = null;
    }
    
    try {
        showMessage('Placing trade...', 'info', 'tradingMessage');
        
        const res = await fetch(`/api/markets/${window.MARKET_ID}/bet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet: currentAccount, side, amount })
    });
        
    const body = await res.json();
        
        if (res.status === 202) {
            if (body.status === 'queued' && body.queue_position > 0) {
                // Bet is queued with other bets ahead - show warning
                hasBeenInQueue = true;
            showQueueWarning();
                showPersistentQueueIndicator();
            } else {
                // Queue was empty (queue_position = 0) - processing immediately, no warning needed
                // Just show processing message
                showMessage('Processing trade...', 'info', 'tradingMessage');
            }
            // Poll for completion regardless
            pollTradeStatus(body.request_id, amount, side);
        } else if (res.ok && body.success) {
            // Immediate success (backward compatibility)
            const actualShares = body.shares || 0;
            const totalCost = formatNumberWithCommas(amount, 2);
            showMessage(`Trade placed! You bought ${formatNumberWithCommas(actualShares, 2)} shares for ${totalCost} EURC`, 'success', 'tradingMessage');
            resetBetUI();
            await loadMarketDetail();
            updateTradePreview();
    } else {
            showMessage(body.message || 'Failed to place trade', 'error', 'tradingMessage');
        }
    } catch (e) {
        console.error('Failed to place trade', e);
        showMessage('Error placing trade', 'error', 'tradingMessage');
    }
}

function showQueueWarning() {
    // Remove any existing popup first
    hideQueueWarning();
    
    // Create warning popup
    const popup = document.createElement('div');
    popup.id = 'queueWarningPopup';
    popup.className = 'queue-warning-popup';
    popup.innerHTML = `
        <div class="queue-warning-content">
            <div class="queue-warning-icon">⚠️</div>
            <h5>Trade in Queue</h5>
            <p>Your trade is being processed. Prices may change while you wait!</p>
            <p class="queue-warning-subtitle">Market prices update in real-time</p>
            <div class="queue-warning-loader">
                <div class="spinner-border spinner-border-sm" role="status" style="margin-top: 0.5rem;">
                    <span class="visually-hidden">Processing...</span>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(popup);
    
    // Animate in
    setTimeout(() => popup.classList.add('show'), 10);
    
    // NO auto-hide - popup persists until trade is processed
}

function showPersistentQueueIndicator() {
    // Show persistent indicator that user has been in queue
    if (persistentQueueWarning) return; // Already showing
    
    const indicator = document.createElement('div');
    indicator.id = 'persistentQueueWarning';
    indicator.className = 'persistent-queue-indicator';
    indicator.innerHTML = `
        <div class="persistent-queue-content">
            <span class="persistent-queue-icon">⚠️</span>
            <span class="persistent-queue-text">You've experienced queue delays. Prices may change while trades process.</span>
            <button class="persistent-queue-close" onclick="hidePersistentQueueIndicator()">×</button>
        </div>
    `;
    document.body.appendChild(indicator);
    persistentQueueWarning = indicator;
    
    // Store in localStorage so it persists across page reloads
    localStorage.setItem('has_been_in_queue', 'true');
}

function hidePersistentQueueIndicator() {
    if (persistentQueueWarning) {
        persistentQueueWarning.remove();
        persistentQueueWarning = null;
    }
    localStorage.removeItem('has_been_in_queue');
}

// Check on page load if user has been in queue
function checkPersistentQueueWarning() {
    if (localStorage.getItem('has_been_in_queue') === 'true') {
        hasBeenInQueue = true;
        showPersistentQueueIndicator();
    }
}

function hideQueueWarning() {
    const popup = document.getElementById('queueWarningPopup');
    if (popup) {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 300);
    }
}

async function pollTradeStatus(requestId, submittedAmount, submittedSide) {
    const maxAttempts = 30; // 30 seconds max
    let attempts = 0;
    
    const poll = async () => {
        try {
            const res = await fetch(`/api/bets/${requestId}/status`);
        const data = await res.json();
            
            if (data.success !== undefined && data.status !== 'processing') {
                // Trade completed
                hideQueueWarning();
                if (data.success) {
                    const actualShares = data.shares || 0;
                    const price = data.price_per_share || 0;
                    const betId = data.bet_id;
                    
                    // Check for slippage (>5% difference)
                    if (expectedShares !== null && expectedShares > 0) {
                        const slippagePercent = Math.abs((actualShares - expectedShares) / expectedShares) * 100;
                        
                        if (slippagePercent > 5) {
                            // Show slippage warning popup with undo option
                            showSlippageWarning(actualShares, expectedShares, slippagePercent, betId, submittedAmount, submittedSide);
                            // Don't show success message yet - wait for user decision
                        } else {
                            // Normal success message
                            showMessage(`Trade placed! ${formatNumberWithCommas(actualShares, 2)} shares @ €${formatNumberWithCommas(price, 2)}`, 'success', 'tradingMessage');
                    resetBetUI();
                    await loadUserBalance();
                    await loadMarketDetail();
                    updateTradePreview();
                        }
                } else {
                        // No expected shares stored, just show success
                        showMessage(`Trade placed! ${formatNumberWithCommas(actualShares, 2)} shares @ €${formatNumberWithCommas(price, 2)}`, 'success', 'tradingMessage');
                        resetBetUI();
                        await loadUserBalance();
                        await loadMarketDetail();
                        updateTradePreview();
                    }
                } else {
                    showMessage(data.message || 'Trade failed', 'error', 'tradingMessage');
                }
                return;
            }
            
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 1000); // Poll every second
            } else {
                hideQueueWarning();
                showMessage('Trade processing is taking longer than expected. Please check your portfolio.', 'warning', 'tradingMessage');
            }
    } catch (e) {
            console.error('Error polling bet status', e);
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 1000);
            } else {
                hideQueueWarning();
            }
        }
    };
    
    poll();
}

function showSlippageWarning(actualShares, expectedShares, slippagePercent, betId, amount, side) {
    // Remove any existing slippage popup
    const existing = document.getElementById('slippageWarningPopup');
    if (existing) existing.remove();
    
    const popup = document.createElement('div');
    popup.id = 'slippageWarningPopup';
    popup.className = 'slippage-warning-popup';
    popup.innerHTML = `
        <div class="slippage-warning-content">
            <div class="slippage-warning-icon">⚠️</div>
            <h5>Price Slippage Detected</h5>
            <p>Your trade executed with significant price movement:</p>
            <div class="slippage-details">
                <div class="slippage-row">
                    <span class="slippage-label">Expected shares:</span>
                    <span class="slippage-value">${formatNumberWithCommas(expectedShares, 2)}</span>
                </div>
                <div class="slippage-row">
                    <span class="slippage-label">Actual shares:</span>
                    <span class="slippage-value">${formatNumberWithCommas(actualShares, 2)}</span>
                </div>
                <div class="slippage-row">
                    <span class="slippage-label">Difference:</span>
                    <span class="slippage-value slippage-bad">${slippagePercent > 0 ? '+' : ''}${formatNumberWithCommas(slippagePercent, 1)}%</span>
                </div>
            </div>
            <p class="slippage-note">Prices changed while your trade was in the queue. You can undo this transaction if you're not satisfied.</p>
            <div class="slippage-actions">
                <button class="btn btn-secondary slippage-keep" onclick="keepTrade(${betId})">Keep Trade</button>
                <button class="btn btn-danger slippage-undo" onclick="undoTrade(${betId}, ${amount})">Undo Transaction</button>
            </div>
        </div>
    `;
    document.body.appendChild(popup);
    
    // Animate in
    setTimeout(() => popup.classList.add('show'), 10);
}

function hideSlippageWarning() {
    const popup = document.getElementById('slippageWarningPopup');
    if (popup) {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 300);
    }
}

async function keepTrade(betId) {
    hideSlippageWarning();
    showMessage(`Trade kept. Transaction completed.`, 'success', 'tradingMessage');
    resetBetUI();
    await loadUserBalance();
    await loadMarketDetail();
    updateTradePreview();
}

async function undoTrade(betId, amount) {
    if (!currentAccount) {
        showMessage('Wallet not connected', 'error', 'tradingMessage');
        return;
    }
    
    try {
        showMessage('Undoing transaction...', 'info', 'tradingMessage');
        
        const res = await fetch(`/api/bets/${betId}/undo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet: currentAccount })
        });
        
        const data = await res.json();
        
        if (res.ok && data.success) {
            hideSlippageWarning();
            showMessage(`Transaction undone. Refunded ${formatNumberWithCommas(data.refunded_amount, 2)} EURC`, 'success', 'tradingMessage');
            resetBetUI();
            await loadUserBalance();
            await loadMarketDetail();
            updateTradePreview();
        } else {
            showMessage(data.message || 'Failed to undo transaction', 'error', 'tradingMessage');
        }
    } catch (e) {
        console.error('Failed to undo trade', e);
        showMessage('Error undoing transaction', 'error', 'tradingMessage');
    }
}

function resetBetUI() {
    const betInput = document.getElementById('betAmountInput');
    if (betInput) betInput.value = '';
    selectedSide = null;
    expectedShares = null; // Reset expected shares
    
    const amountSection = document.getElementById('amountSection');
    if (amountSection) amountSection.style.display = 'none';
    
    const tradePreview = document.getElementById('tradePreview');
    if (tradePreview) tradePreview.style.display = 'none';
    
    const riskSection = document.getElementById('riskConfirmationSection');
    if (riskSection) riskSection.style.display = 'none';
    
    const buyBtn = document.getElementById('buyButton');
    if (buyBtn) {
        buyBtn.style.display = 'none';
        buyBtn.disabled = true;
    }
    const riskCheckbox = document.getElementById('riskConfirmationCheckbox');
    if (riskCheckbox) {
        riskCheckbox.checked = false;
    }
    const yesBtn = document.getElementById('selectYesBtn');
    if (yesBtn) yesBtn.classList.remove('selected');
    const noBtn = document.getElementById('selectNoBtn');
    if (noBtn) noBtn.classList.remove('selected');
}

// ========== MY BETS PAGE ==========
function initMyBetsPage() {
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
    // Setup event delegation for sell buttons (works for dynamically created buttons)
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('sell-btn-portfolio')) {
            e.preventDefault();
            e.stopPropagation();
            const btn = e.target;
            const betId = parseInt(btn.dataset.betId);
            const marketId = parseInt(btn.dataset.marketId);
            const shares = parseFloat(btn.dataset.shares || 0);
            const amount = parseFloat(btn.dataset.amount || 0);
            const buyPrice = parseFloat(btn.dataset.buyPrice || 0);
            const currentPrice = parseFloat(btn.dataset.currentPrice || 0);
            const currentValue = parseFloat(btn.dataset.currentValue || 0);
            const unrealizedProfit = parseFloat(btn.dataset.unrealizedProfit || 0);
            const question = btn.dataset.question || '';
            const side = btn.dataset.side || 'YES';
            
            console.log('Sell button clicked:', { betId, marketId, shares, question, side });
            openSellModal(betId, marketId, shares, amount, buyPrice, currentPrice, currentValue, unrealizedProfit, question, side);
        }
    });
    
    // Load user balance
    loadUserBalance();
    
    // Load user bets
    loadUserBets();
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

async function loadUserBets() {
    if (!currentAccount) {
        const container = document.getElementById('betsList');
        if (container) {
            container.innerHTML = '<div class="alert alert-warning">Please connect your wallet to view your bets.</div>';
        }
        return;
    }
    
    try {
        const res = await fetch(`/api/user/${currentAccount}/bets`);
        const data = await res.json();
        renderUserBets(data.bets || []);
    } catch (e) {
        console.error('Failed to load bets', e);
    }
}

function renderUserBets(bets) {
    if (!bets || !bets.length) {
        // Show empty state
        return;
    }
    
    // Update timestamp
    document.getElementById('lastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    
    // Separate open and closed positions
    const openPositions = bets.filter(b => b.status === 'open');
    const closedPositions = bets.filter(b => b.status === 'resolved');
    
    // Calculate metrics
    const totalInvested = bets.reduce((sum, b) => sum + (parseFloat(b.amount) || 0), 0);
    const realizedPL = closedPositions.reduce((sum, b) => sum + (parseFloat(b.profit) || 0), 0);
    const unrealizedPL = openPositions.reduce((sum, b) => sum + (parseFloat(b.unrealized_profit) || 0), 0);
    const currentValue = openPositions.reduce((sum, b) => sum + (parseFloat(b.current_value) || 0), 0);
    const totalPL = realizedPL + unrealizedPL;
    const navValue = currentValue + realizedPL;
    const returnPct = totalInvested > 0 ? (totalPL / totalInvested) * 100 : 0;
    
    // Update NAV
    document.getElementById('navValue').textContent = `€${formatNumberWithCommas(navValue, 2)}`;
    const navChangeEl = document.getElementById('navChange');
    navChangeEl.className = `nav-change ${totalPL > 0 ? 'positive' : (totalPL < 0 ? 'negative' : '')}`;
    navChangeEl.innerHTML = `
        <span class="nav-change-amount">${totalPL > 0 ? '+' : ''}€${formatNumberWithCommas(totalPL, 2)}</span>
        <span class="nav-change-percent">(${returnPct > 0 ? '+' : ''}${formatNumberWithCommas(returnPct, 2)}%)</span>
    `;
    
    // Update metric cards
    document.getElementById('openPositions').textContent = formatNumberWithCommas(openPositions.length, 0);
    document.getElementById('totalInvested').textContent = `€${formatNumberWithCommas(totalInvested, 2)}`;
    
    // Update performance metrics
    const realizedPLEl = document.getElementById('realizedPL');
    realizedPLEl.textContent = `${realizedPL > 0 ? '+' : ''}${formatNumberWithCommas(realizedPL, 2)}`;
    realizedPLEl.className = `performance-value realized-pl ${realizedPL > 0 ? 'positive' : (realizedPL < 0 ? 'negative' : '')}`;
    
    const unrealizedPLEl = document.getElementById('unrealizedPL');
    unrealizedPLEl.textContent = `${unrealizedPL > 0 ? '+' : ''}${formatNumberWithCommas(unrealizedPL, 2)}`;
    unrealizedPLEl.className = `performance-value unrealized-pl ${unrealizedPL > 0 ? 'positive' : (unrealizedPL < 0 ? 'negative' : '')}`;
    
    const totalPLEl = document.getElementById('totalPL');
    totalPLEl.textContent = `${totalPL > 0 ? '+' : ''}${formatNumberWithCommas(totalPL, 2)}`;
    totalPLEl.className = `performance-value total-pl ${totalPL > 0 ? 'positive' : (totalPL < 0 ? 'negative' : '')}`;
    
    const returnPctEl = document.getElementById('returnPct');
    returnPctEl.textContent = `${returnPct > 0 ? '+' : ''}${formatNumberWithCommas(returnPct, 2)}%`;
    returnPctEl.className = `performance-value return-pct ${returnPct > 0 ? 'positive' : (returnPct < 0 ? 'negative' : '')}`;
    
    // Render open positions table
    const openPositionsBody = document.getElementById('positionsTableBody');
    if (openPositions.length > 0) {
        openPositionsBody.innerHTML = openPositions.map(b => {
            const unrealizedProfit = b.unrealized_profit || 0;
            const returnPct = b.amount > 0 ? (unrealizedProfit / b.amount) * 100 : 0;
            const plClass = unrealizedProfit > 0 ? 'position-pl-positive' : (unrealizedProfit < 0 ? 'position-pl-negative' : '');
            
        return `
                <tr>
                    <td>
                        <img src="${b.image_url || '/static/img/default-market.png'}" 
                             alt="${escapeHtml(b.question)}" 
                             class="position-thumbnail">
                    </td>
                    <td>
                        <a href="/market/${b.market_id}" class="position-market">${escapeHtml(b.question)}</a>
                    </td>
                    <td>
                        <span class="position-side-${b.side.toLowerCase()}">${b.side}</span>
                    </td>
                    <td class="text-end">${formatNumberWithCommas(b.shares || 0, 2)}</td>
                    <td class="text-end">${formatNumberWithCommas(b.amount, 2)}</td>
                    <td class="text-end">${formatNumberWithCommas((b.buy_price || 0) * 100, 1)}¢</td>
                    <td class="text-end">${formatNumberWithCommas((b.current_price || 0) * 100, 1)}¢</td>
                    <td class="text-end">${formatNumberWithCommas(b.current_value || 0, 2)}</td>
                    <td class="text-end ${plClass}">
                        ${unrealizedProfit > 0 ? '+' : ''}${formatNumberWithCommas(unrealizedProfit, 2)}
                    </td>
                    <td class="text-end ${plClass}">
                        ${returnPct > 0 ? '+' : ''}${formatNumberWithCommas(returnPct, 2)}%
                    </td>
                    <td class="text-center">
                        <button class="sell-btn-portfolio" 
                                data-bet-id="${b.id}" 
                                data-market-id="${b.market_id}"
                                data-shares="${(b.shares || 0)}"
                                data-amount="${(b.amount || 0)}"
                                data-buy-price="${(b.buy_price || 0)}"
                                data-current-price="${(b.current_price || 0)}"
                                data-current-value="${(b.current_value || 0)}"
                                data-unrealized-profit="${(b.unrealized_profit || 0)}"
                                data-question="${escapeHtml(b.question || '')}"
                                data-side="${b.side || ''}">
                            Sell
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } else {
        openPositionsBody.innerHTML = `
            <tr class="empty-state">
                <td colspan="11" class="text-center py-5">
                    <div class="text-muted">
                        <div class="mb-2">No open positions</div>
                        <small>Visit <a href="/">Markets</a> to start trading</small>
                    </div>
                </td>
            </tr>
        `;
    }
    
    // Render closed positions table
    const closedPositionsBody = document.getElementById('closedPositionsTableBody');
    if (closedPositions.length > 0) {
        closedPositionsBody.innerHTML = closedPositions.map(b => {
            const payout = b.payout || 0;
            const costBasis = b.amount;
            const profit = b.profit || 0;
            const returnPct = costBasis > 0 ? (profit / costBasis) * 100 : 0;
            const plClass = profit > 0 ? 'position-pl-positive' : (profit < 0 ? 'position-pl-negative' : '');
            const statusClass = b.result === 'won' ? 'position-status-won' : 'position-status-lost';
            
            return `
                <tr>
                    <td>
                        <img src="${b.image_url || '/static/img/default-market.png'}" 
                             alt="${escapeHtml(b.question)}" 
                             class="position-thumbnail">
                    </td>
                    <td>
                        <a href="/market/${b.market_id}" class="position-market">${escapeHtml(b.question)}</a>
                    </td>
                    <td>
                        <span class="position-side-${b.side.toLowerCase()}">${b.side}</span>
                    </td>
                    <td class="text-end">${formatNumberWithCommas(b.shares || 0, 2)}</td>
                    <td class="text-end">${formatNumberWithCommas(costBasis, 2)}</td>
                    <td class="text-end">${formatNumberWithCommas(payout, 2)}</td>
                    <td class="text-end ${plClass}">
                        ${profit > 0 ? '+' : ''}${formatNumberWithCommas(profit, 2)}
                    </td>
                    <td class="text-end ${plClass}">
                        ${returnPct > 0 ? '+' : ''}${formatNumberWithCommas(returnPct, 2)}%
                    </td>
                    <td>
                        <span class="${statusClass}">${b.result.toUpperCase()}</span>
                    </td>
                </tr>
            `;
        }).join('');
    } else {
        closedPositionsBody.innerHTML = `
            <tr class="empty-state">
                <td colspan="9" class="text-center py-4">
                    <div class="text-muted">No closed positions</div>
                </td>
            </tr>
        `;
    }
}

function openSellModal(betId, marketId, shares, costBasis, buyPrice, currentPrice, currentValue, unrealizedProfit, question, side) {
    console.log('openSellModal called:', { betId, marketId, shares, question, side });
    if (!currentAccount) {
        showMessage('Connect your wallet first.', 'error');
        return;
    }
    
    // Calculate return percentage
    const returnPct = costBasis > 0 ? (unrealizedProfit / costBasis) * 100 : 0;
    const plClass = unrealizedProfit >= 0 ? 'positive' : 'negative';
    const plColor = unrealizedProfit >= 0 ? 'var(--green-yes)' : 'var(--red-no)';
    
    // Create modal
    const modal = document.createElement('div');
    modal.id = 'sellModal';
    modal.className = 'sell-modal-overlay';
    modal.innerHTML = `
        <div class="sell-modal-content">
            <div class="sell-modal-header">
                <h4>Sell Position</h4>
                <button class="sell-modal-close" id="sellModalCloseBtn">&times;</button>
                </div>
            <div class="sell-modal-body">
                <div class="sell-market-info">
                    <h5>${escapeHtml(question)}</h5>
                    <span class="position-side-${side.toLowerCase()}">${side}</span>
                    </div>
                
                <div class="sell-details-grid">
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Shares</span>
                        <span class="sell-detail-value">${formatNumberWithCommas(shares, 2)}</span>
                        </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Cost Basis</span>
                        <span class="sell-detail-value">${formatNumberWithCommas(costBasis, 2)}</span>
                    </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Buy Price</span>
                        <span class="sell-detail-value">${formatNumberWithCommas(buyPrice * 100, 1)}¢</span>
                </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Current Price</span>
                        <span class="sell-detail-value">${formatNumberWithCommas(currentPrice * 100, 1)}¢</span>
            </div>
                </div>
                
                <div class="sell-summary">
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Sell Value</span>
                        <span class="sell-summary-value">${formatNumberWithCommas(currentValue, 2)}</span>
                    </div>
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Cost Basis</span>
                        <span class="sell-summary-value">${formatNumberWithCommas(costBasis, 2)}</span>
                    </div>
                    <div class="sell-summary-divider"></div>
                    <div class="sell-summary-row sell-summary-net">
                        <span class="sell-summary-label">Net P/L</span>
                        <span class="sell-summary-value ${plClass}" style="color: ${plColor}; font-weight: 700; font-size: 1.25rem;">
                            ${unrealizedProfit >= 0 ? '+' : ''}${formatNumberWithCommas(unrealizedProfit, 2)}
                        </span>
                    </div>
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Return</span>
                        <span class="sell-summary-value ${plClass}" style="color: ${plColor};">
                            ${returnPct >= 0 ? '+' : ''}${formatNumberWithCommas(returnPct, 2)}%
                        </span>
                    </div>
                </div>
            </div>
            <div class="sell-modal-footer">
                <button class="sell-modal-cancel" id="sellModalCancelBtn">Cancel</button>
                <button class="sell-modal-confirm" id="sellModalConfirmBtn" data-bet-id="${betId}" data-market-id="${marketId}" data-shares="${shares}">
                    Confirm Sell
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
    
    // Setup button handlers
    const closeBtn = modal.querySelector('#sellModalCloseBtn');
    const cancelBtn = modal.querySelector('#sellModalCancelBtn');
    const confirmBtn = modal.querySelector('#sellModalConfirmBtn');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSellModal);
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeSellModal);
    }
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            const betId = parseInt(confirmBtn.dataset.betId);
            const marketId = parseInt(confirmBtn.dataset.marketId);
            const shares = parseFloat(confirmBtn.dataset.shares);
            console.log('Confirm sell clicked:', { betId, marketId, shares });
            confirmSell(betId, marketId, shares);
        });
    }
    
    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeSellModal();
        }
    });
    
    // Close on Escape key
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            closeSellModal();
            document.removeEventListener('keydown', escapeHandler);
        }
    };
    document.addEventListener('keydown', escapeHandler);
}

function closeSellModal() {
    const modal = document.getElementById('sellModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    }
}

async function confirmSell(betId, marketId, totalShares) {
    console.log('confirmSell called:', { betId, marketId, totalShares, wallet: currentAccount });
    if (!currentAccount) {
        showMessage('Connect your wallet first.', 'error');
        return;
    }
    
    try {
        console.log('Sending sell request to /api/markets/' + marketId + '/sell');
        const res = await fetch(`/api/markets/${marketId}/sell`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                wallet: currentAccount,
                bet_id: betId,
                shares: totalShares
            })
        });
        
        const data = await res.json();
        console.log('Sell response:', { status: res.status, ok: res.ok, data });
        
        if (res.ok && data.success) {
            closeSellModal();
            showMessage(data.message || `Successfully sold ${data.shares_sold || totalShares} shares`, 'success');
            // Reload balance after selling
            await loadUserBalance();
            // Reload bets
            await loadUserBets();
        } else {
            // Don't close modal on error so user can try again
            const errorMsg = data.message || data.error || `Failed to sell shares (Status: ${res.status})`;
            console.error('Sell failed:', errorMsg, data);
            showMessage(errorMsg, 'error');
        }
    } catch (e) {
        console.error('Failed to sell shares', e);
        showMessage('Error selling shares: ' + e.message, 'error');
    }
}

async function sellShares(betId, marketId, totalShares) {
    // Legacy function - redirects to modal
    // This is kept for backward compatibility but shouldn't be called directly
    openSellModal(betId, marketId, totalShares, 0, 0, 0, 0, 0, 'Unknown', 'YES');
}

// ========== ADMIN DASHBOARD ==========
function initAdminDashboard() {
    loadAdminStats();
    loadUserDatabase();
    loadKYCDatabase();
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

async function loadAdminStats() {
    try {
        const marketsRes = await fetch('/api/markets');
        const marketsData = await marketsRes.json();
        
        const markets = marketsData.markets || [];
        const totalMarkets = markets.length;
        const totalVolume = markets.reduce((sum, m) => sum + (m.yes_total || 0) + (m.no_total || 0), 0);
        const totalBets = markets.reduce((sum, m) => sum + (m.bet_count || 0), 0);
        
        document.getElementById('adminTotalMarkets').textContent = totalMarkets;
        document.getElementById('adminTotalBets').textContent = totalBets;
        document.getElementById('adminTotalVolume').textContent = `${formatNumberWithCommas(totalVolume, 0)}`;
    } catch (e) {
        console.error('Failed to load admin stats', e);
    }
}

async function loadUserDatabase() {
    try {
        const res = await fetch('/api/admin/users');
        const data = await res.json();
        
        const tbody = document.getElementById('userDatabaseTableBody');
        if (!tbody) return;
        
        if (!res.ok || !data.users || data.users.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center py-4 text-muted">No users found</td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.users.map(user => {
            const walletShort = `${user.wallet.slice(0, 6)}...${user.wallet.slice(-4)}`;
            const createdDate = user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A';
            const lastLogin = user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never';
            
            // Auth status badge
            const authStatus = user.auth_status || 'unverified';
            let authBadge = '';
            if (authStatus === 'verified') {
                authBadge = '<span class="badge bg-success">Verified</span>';
            } else if (authStatus === 'rejected') {
                authBadge = '<span class="badge bg-danger">Rejected</span>';
            } else {
                authBadge = '<span class="badge bg-secondary">Unverified</span>';
            }
            
            return `
                <tr>
                    <td>
                        <code style="font-size: 0.85rem;">${walletShort}</code>
                        <button class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="navigator.clipboard.writeText('${user.wallet}')" title="Copy full address" style="font-size: 0.75rem;">Copy</button>
                    </td>
                    <td>${authBadge}</td>
                    <td class="text-end"><strong>${formatNumberWithCommas(user.balance, 2)} EURC</strong></td>
                    <td class="text-end">${formatNumberWithCommas(user.total_bets, 0)}</td>
                    <td class="text-end">${formatNumberWithCommas(user.total_bet_amount, 2)} EURC</td>
                    <td class="text-end">${formatNumberWithCommas(user.open_positions, 0)}</td>
                    <td>${createdDate}</td>
                    <td>${lastLogin}</td>
                    <td class="text-end">
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-outline-primary" onclick="showCreditModalForUser('${user.wallet}')" title="Credit user">
                                Credit
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteUser('${user.wallet}')" title="Delete user">
                                Delete
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('Failed to load user database', e);
        const tbody = document.getElementById('userDatabaseTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center py-4 text-danger">Error loading users: ${e.message}</td>
                </tr>
            `;
        }
    }
}

function showCreditModalForUser(wallet) {
    // Pre-fill the credit modal with the wallet address
    const walletInput = document.getElementById('creditWalletInput');
    const modal = new bootstrap.Modal(document.getElementById('creditUserModal'));
    if (walletInput) {
        walletInput.value = wallet;
    }
    modal.show();
}

async function deleteUser(wallet) {
    const walletShort = `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;
    const confirmMsg = `Are you sure you want to DELETE user ${walletShort}?\n\nThis will:\n• Automatically sell all open positions\n• Delete all bets\n• Remove user from database\n• Clear their balance\n\nThis action cannot be undone!`;
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    try {
        const res = await fetch(`/api/admin/users/${wallet}/delete`, {
            method: 'DELETE'
        });
        
        const data = await res.json();
        
        if (res.ok && data.success) {
            alert(data.message);
            await loadUserDatabase();
            await loadAdminStats();
        } else {
            alert('Failed to delete user: ' + (data.error || data.message || 'Unknown error'));
        }
    } catch (e) {
        console.error('Failed to delete user', e);
        alert('Error deleting user: ' + e.message);
    }
}

async function loadKYCDatabase() {
    try {
        const res = await fetch('/api/admin/kyc');
        const data = await res.json();
        
        const tbody = document.getElementById('kycDatabaseTableBody');
        if (!tbody) return;
        
        if (!res.ok || !data.verifications || data.verifications.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="13" class="text-center py-4 text-muted">No KYC verifications found</td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.verifications.map(kyc => {
            const walletShort = kyc.wallet ? `${kyc.wallet.slice(0, 6)}...${kyc.wallet.slice(-4)}` : 'N/A';
            const status = kyc.status || 'pending';
            
            // Status badge
            let statusBadge = '';
            if (status === 'verified') {
                statusBadge = '<span class="badge bg-success">Verified</span>';
            } else if (status === 'rejected') {
                statusBadge = '<span class="badge bg-danger">Rejected</span>';
            } else {
                statusBadge = '<span class="badge bg-secondary">Pending</span>';
            }
            
            // Document type formatting
            const docType = kyc.document_type ? kyc.document_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : '—';
            
            // Official document indicator
            const officialDoc = kyc.is_official_document ? '<span class="text-success">Yes</span>' : '<span class="text-muted">No</span>';
            
            // Dates
            const submittedDate = kyc.created_at ? new Date(kyc.created_at).toLocaleString() : 'N/A';
            const verifiedDate = kyc.verified_at ? new Date(kyc.verified_at).toLocaleString() : '—';
            const expiryDate = kyc.expiry_date || '—';
            
            // Check if expired (if expiry_date exists and is in the past)
            let expiryDisplay = expiryDate;
            if (expiryDate && expiryDate !== '—') {
                try {
                    const expiry = new Date(expiryDate);
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    if (expiry < today) {
                        expiryDisplay = `<span class="text-danger" title="Document expired">${expiryDate}</span>`;
                    } else {
                        expiryDisplay = expiryDate;
                    }
                } catch (e) {
                    // Invalid date format, just display as-is
                    expiryDisplay = expiryDate;
                }
            }
            
            // Notes (truncate if too long)
            const notes = kyc.verification_notes ? (kyc.verification_notes.length > 50 ? kyc.verification_notes.substring(0, 50) + '...' : kyc.verification_notes) : '—';
            
            return `
                <tr>
                    <td>
                        <code style="font-size: 0.85rem;">${walletShort}</code>
                        ${kyc.wallet ? `<button class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="navigator.clipboard.writeText('${kyc.wallet}')" title="Copy full address" style="font-size: 0.75rem;">Copy</button>` : ''}
                    </td>
                    <td>${statusBadge}</td>
                    <td>${kyc.full_name || '—'}</td>
                    <td>${kyc.date_of_birth || '—'}</td>
                    <td>${expiryDisplay}</td>
                    <td>${kyc.nationality || '—'}</td>
                    <td>${docType}</td>
                    <td><code style="font-size: 0.85rem;">${kyc.document_number || '—'}</code></td>
                    <td class="text-center">${officialDoc}</td>
                    <td>${submittedDate}</td>
                    <td>${verifiedDate}</td>
                    <td><small class="text-muted">${escapeHtml(notes)}</small></td>
                    <td class="text-end">
                        ${kyc.wallet ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteKYCVerification('${kyc.wallet}')" title="Delete KYC verification">Delete</button>` : '—'}
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('Failed to load KYC database', e);
        const tbody = document.getElementById('kycDatabaseTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="13" class="text-center py-4 text-danger">Error loading KYC verifications: ${e.message}</td>
                </tr>
            `;
        }
    }
}

async function deleteKYCVerification(wallet) {
    const walletShort = wallet ? `${wallet.slice(0, 6)}...${wallet.slice(-4)}` : 'this wallet';
    const confirmMsg = `Are you sure you want to DELETE the KYC verification for ${walletShort}?\n\nThis will:\n• Remove the KYC verification record\n• Reset user auth status to unverified\n\nThis action cannot be undone!`;
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    try {
        const res = await fetch(`/api/admin/kyc/${wallet}/delete`, {
            method: 'DELETE'
        });
        
        const data = await res.json();
        
        if (res.ok && data.success) {
            alert(`✅ ${data.message}`);
            // Reload KYC database
            await loadKYCDatabase();
        } else {
            alert(`❌ Failed to delete KYC verification: ${data.error || data.message || 'Unknown error'}`);
        }
    } catch (e) {
        console.error('Failed to delete KYC verification', e);
        alert(`❌ Error deleting KYC verification: ${e.message}`);
    }
}

async function clearAllKYC() {
    const confirmMsg = `⚠️ WARNING: Are you sure you want to CLEAR ALL KYC VERIFICATIONS?\n\nThis will:\n• Delete ALL KYC verification records\n• Reset ALL user auth statuses to unverified\n• This affects ALL users in the database\n\nThis action CANNOT be undone!\n\nType "DELETE ALL" to confirm:`;
    
    const userInput = prompt(confirmMsg);
    if (userInput !== 'DELETE ALL') {
        alert('❌ Clear cancelled. You must type "DELETE ALL" to confirm.');
        return;
    }
    
    try {
        const res = await fetch('/api/admin/kyc/clear', {
            method: 'DELETE'
        });
        
        const data = await res.json();
        
        if (res.ok && data.success) {
            alert(`✅ ${data.message}\n\nDeleted ${data.deleted_count} KYC verification(s).`);
            // Reload KYC database
            await loadKYCDatabase();
        } else {
            alert(`❌ Failed to clear KYC verifications: ${data.error || data.message || 'Unknown error'}`);
        }
    } catch (e) {
        console.error('Failed to clear KYC verifications', e);
        alert(`❌ Error clearing KYC verifications: ${e.message}`);
    }
}

// Make admin functions globally accessible
window.loadUserDatabase = loadUserDatabase;
window.loadKYCDatabase = loadKYCDatabase;
window.deleteUser = deleteUser;
window.deleteKYCVerification = deleteKYCVerification;
window.clearAllKYC = clearAllKYC;
window.showCreditModalForUser = showCreditModalForUser;

// ========== ADMIN CREATE MARKET ==========
function initAdminCreateMarket() {
    const form = document.getElementById('createMarketForm');
    if (form) {
        form.addEventListener('submit', handleAdminCreateMarket);
        
        // Live preview
        ['marketQuestion', 'marketDescription', 'marketImageUrl', 'marketCategory'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', updateMarketPreview);
        });
    }
}

function updateMarketPreview() {
    const question = document.getElementById('marketQuestion').value;
    const description = document.getElementById('marketDescription').value;
    const imageUrl = document.getElementById('marketImageUrl').value;
    const category = document.getElementById('marketCategory').value;
    
    const preview = document.getElementById('marketPreview');
    
    if (!question && !description) {
        preview.innerHTML = '<div class="text-muted text-center py-4">Fill out the form to see a preview</div>';
        return;
    }
    
    preview.innerHTML = `
        ${imageUrl ? `<img src="${imageUrl}" style="width: 100%; border-radius: 8px; margin-bottom: 1rem;" onerror="this.style.display='none'">` : ''}
        ${category ? `<span class="market-category">${escapeHtml(category)}</span>` : ''}
        <h5 class="mt-2">${escapeHtml(question) || 'Market question'}</h5>
        <p class="text-muted small">${escapeHtml(description) || 'Market description'}</p>
    `;
}

async function handleAdminCreateMarket(e) {
    e.preventDefault();
    
    const question = document.getElementById('marketQuestion').value.trim();
    const description = document.getElementById('marketDescription').value.trim();
    const imageUrl = document.getElementById('marketImageUrl').value.trim();
    const category = document.getElementById('marketCategory').value;
    const endDate = document.getElementById('marketEndDate').value;
    const deployBlockchain = document.getElementById('deployBlockchain')?.checked || false;
    
    if (!question || !description || !category) {
        showMessage('Please fill in all required fields', 'error', 'createMessageContainer');
        return;
    }
    
    // Validate end_date if blockchain deployment is requested
    if (deployBlockchain && !endDate) {
        showMessage('End date is required when deploying to blockchain', 'error', 'createMessageContainer');
        return;
    }
    
    try {
        let endpoint = '/api/markets';
        if (deployBlockchain) {
            endpoint = '/api/admin/markets/blockchain';
        }
        
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question,
                description,
                image_url: imageUrl,
                category,
                end_date: endDate,
                created_by: 'admin'
            })
        });
        
        const body = await res.json();
        
        if (res.ok && body.success) {
            let message = 'Market created successfully!';
            if (deployBlockchain && body.blockchain_tx_hash) {
                message += `<br><small>Blockchain TX: <a href="${body.etherscan_url}" target="_blank">${body.blockchain_tx_hash.substring(0, 10)}...</a></small>`;
            }
            showMessage(message, 'success', 'createMessageContainer');
            setTimeout(() => {
                window.location.href = '/admin';
            }, 3000);
        } else {
            const errorMsg = body.message || body.error || 'Failed to create market';
            showMessage(errorMsg, 'error', 'createMessageContainer');
            console.error('Market creation error:', body);
        }
    } catch (e) {
        console.error('Market creation exception:', e);
        showMessage('Error creating market: ' + (e.message || 'Unknown error'), 'error', 'createMessageContainer');
    }
}

// ========== ADMIN RESOLVE ==========
function initAdminResolvePage() {
    loadAdminMarkets();
}

async function loadAdminMarkets() {
    try {
        const res = await fetch('/api/markets');
        const data = await res.json();
        renderAdminMarkets(data.markets || []);
    } catch (e) {
        console.error('Failed to load markets', e);
    }
}

function renderAdminMarkets(markets) {
    const container = document.getElementById('adminMarketsList');
    if (!container) return;
    
    if (!markets.length) {
        container.innerHTML = '<div class="alert alert-info">No markets available.</div>';
        return;
    }

    container.innerHTML = markets.map(m => {
        const yes = formatNumberWithCommas(Number(m.yes_total || 0), 2);
        const no = formatNumberWithCommas(Number(m.no_total || 0), 2);
        const isResolved = m.status === 'resolved';
        const statusBadge = isResolved 
            ? `<span class="badge" style="background: var(--blue-primary)">Resolved: ${m.resolution}</span>`
            : `<span class="badge" style="background: var(--green-yes)">Open</span>`;
        
        const resolveButtons = !isResolved ? `
            <div class="btn-group" role="group">
                <button class="btn btn-yes" onclick="adminResolveMarket(${m.id}, 'YES')">Resolve YES</button>
                <button class="btn btn-no" onclick="adminResolveMarket(${m.id}, 'NO')">Resolve NO</button>
            </div>
        ` : '';
        
        const viewPayoutsBtn = isResolved ? `
            <button class="btn btn-outline-secondary btn-sm ms-2" onclick="viewPayouts(${m.id})">View Payouts</button>
        ` : '';
        
        return `
        <div class="market-detail-card mb-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                    <h5>${escapeHtml(m.question)}</h5>
                    <p class="text-muted">${escapeHtml(m.description || '')}</p>
                    </div>
                <div>${statusBadge}</div>
                </div>
            <div class="mb-3">
                <strong>YES Pool:</strong> ${yes} | <strong>NO Pool:</strong> ${no} | <strong>Total Bets:</strong> ${m.bet_count}
                    </div>
            <div class="d-flex gap-2">
                ${resolveButtons}
                ${viewPayoutsBtn}
            </div>
        </div>`;
    }).join('');
}

async function adminResolveMarket(marketId, outcome) {
    if (!confirm(`Are you sure you want to resolve this market as ${outcome}?`)) {
        return;
    }
    
    try {
    const res = await fetch(`/api/markets/${marketId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outcome })
    });
    const body = await res.json();
        
        // Check if outcome exists (success) or error/message exists
        if (res.ok && body.outcome) {
            // Show detailed success message with payout info
            let message = `✅ Market resolved as ${outcome}!`;
            if (body.payouts_distributed && body.total_payout > 0) {
                message += `\n\n💰 Payouts Distributed:\n`;
                message += `  • Total: ${formatNumberWithCommas(body.total_payout, 2)} EURC\n`;
                if (body.total_fees && body.total_fees > 0) {
                    message += `  • Fees: ${formatNumberWithCommas(body.total_fees, 2)} EURC (2% on profits)\n`;
                }
                message += `  • Winners: ${body.winners_count} user(s)\n`;
                message += `\nWinner balances have been automatically updated!`;
            } else if (!body.payouts_distributed) {
                message += `\n\n⚠️ Note: Payout distribution failed. You may need to manually credit winners.`;
            } else {
                message += `\n\n📊 No winning bets found for this market.`;
            }
            alert(message);
            await loadAdminMarkets();
    } else {
            alert(body.error || body.message || 'Failed to resolve market');
        }
    } catch (e) {
        alert('Error resolving market');
        console.error(e);
    }
}

async function viewPayouts(marketId) {
    try {
        const res = await fetch(`/api/markets/${marketId}/payouts`);
        const data = await res.json();
        
        if (!res.ok) {
            alert(data.error || data.message || 'Failed to load payouts');
        return;
    }
        
        // Handle case where payouts array might be empty or missing
        const payouts = data.payouts || [];
        const winningTotal = data.winning_total || 0;
        const losingTotal = data.losing_total || 0;
        
        let html = `
            <div class="mb-3">
                <strong>Market Resolution:</strong> ${data.resolution || 'N/A'}<br>
                <strong>Winning Pool:</strong> ${formatNumberWithCommas(winningTotal, 2)}<br>
                <strong>Losing Pool:</strong> ${formatNumberWithCommas(losingTotal, 2)}
            </div>
        `;
        
        if (payouts.length > 0) {
            html += `
            <table class="table table-dark table-striped">
                <thead>
                    <tr>
                        <th>Wallet</th>
                        <th>Total Trade Amount</th>
                        <th>Payout</th>
                        <th>Profit/Loss</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
            payouts.forEach(p => {
                const profit = p.profit || 0;
                const profitClass = profit >= 0 ? 'text-success' : 'text-danger';
                const profitSign = profit >= 0 ? '+' : '';
            html += `
                <tr>
                        <td><code>${p.wallet ? p.wallet.slice(0,6) + '...' + p.wallet.slice(-4) : 'N/A'}</code></td>
                        <td>${formatNumberWithCommas(p.total_bet || 0, 2)}</td>
                        <td>${formatNumberWithCommas(p.payout || 0, 2)}</td>
                        <td class="${profitClass}"><strong>${profitSign}${formatNumberWithCommas(profit, 2)}</strong></td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
        } else {
            html += `<div class="alert alert-info">No bets placed on this market yet.</div>`;
        }
        
        const modalBody = document.getElementById('payoutModalBody');
        if (modalBody) {
            modalBody.innerHTML = html;
            const modalElement = document.getElementById('payoutModal');
            if (modalElement) {
                const modal = new bootstrap.Modal(modalElement);
        modal.show();
            } else {
                alert('Modal element not found');
            }
        } else {
            alert('Modal body element not found');
        }
        
    } catch (e) {
        alert('Error loading payouts');
        console.error(e);
    }
}

// ========== WEB3 WALLET ==========
async function connectWallet() {
    if (!window.ethereum) {
        alert('MetaMask not found. Please install MetaMask.');
        return;
    }
    try {
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        currentAccount = accounts[0]?.toLowerCase();  // Normalize to lowercase
        updateWalletUI();
        
        // Load balance on connect (auto-credits if new user)
        await loadUserBalance();
        
        // Update profile page if we're on it
        if (window.location.pathname === '/profile') {
            updateProfileDisplay();
            loadKYCStatus();
        }
        
        // Load user bets if on my-bets page
        if (window.location.pathname === '/my-bets') {
            loadUserBets();
        }
    } catch (e) {
        console.error('Wallet connect error:', e);
    }
}

async function tryInitWallet() {
    if (window.ethereum) {
        try {
            const accounts = await window.ethereum.request({ method: 'eth_accounts' });
            if (accounts && accounts.length) {
                currentAccount = accounts[0]?.toLowerCase();  // Normalize to lowercase
                updateWalletUI();
                
                // Load balance on init
                await loadUserBalance();
                
                // Update profile page if we're on it
                if (window.location.pathname === '/profile') {
                    updateProfileDisplay();
                    loadKYCStatus();
                }
                
                // Load user bets if on my-bets page
                if (window.location.pathname === '/my-bets') {
                    loadUserBets();
                }
            }
            window.ethereum.on('accountsChanged', async (accs) => {
                currentAccount = accs && accs.length ? accs[0]?.toLowerCase() : null;  // Normalize to lowercase
                updateWalletUI();
                
                // Load balance when account changes
                if (currentAccount) {
                    await loadUserBalance();
                }
                
                // Update profile page if we're on it
                if (window.location.pathname === '/profile') {
                    updateProfileDisplay();
                    if (currentAccount) {
                        loadKYCStatus();
                    }
                }
                
                // Reload bets if on my-bets page
                if (window.location.pathname === '/my-bets') {
                    loadUserBets();
                }
            });
        } catch (e) {
            // ignore
        }
    }
}

async function loadUserBalance() {
    if (!currentAccount) {
        userBalance = 0.0;
        updateBalanceDisplay();
        return;
    }
    
    try {
        const res = await fetch(`/api/user/${currentAccount}/balance`);
        const data = await res.json();
        
        if (res.ok) {
            userBalance = data.balance || 0.0;
            updateBalanceDisplay();
            
            // Show welcome message for new users
            if (data.is_new_user) {
                showMessage(`Welcome! You've been credited with ${formatNumberWithCommas(userBalance, 2)} EURC to start trading!`, 'success', 'tradingMessage');
            }
        }
    } catch (e) {
        console.error('Failed to load balance', e);
    }
}

// Make function globally accessible
window.clearCacheAndLogout = function() {
    if (!confirm('Are you sure you want to clear all cache and logout? This will:\n\n• Clear all stored data (localStorage, sessionStorage)\n• Disconnect your wallet\n• Reset all app state\n• Reload the page')) {
        return;
    }
    
    // Clear all localStorage
    localStorage.clear();
    
    // Clear all sessionStorage
    sessionStorage.clear();
    
    // Reset global variables
    currentAccount = null;
    userBalance = 0.0;
    allMarkets = [];
    currentFilter = 'all';
    
    // Clear chatbot thread ID if exists
    if (typeof chatThreadId !== 'undefined') {
        chatThreadId = null;
    }
    
    // Update UI
    updateWalletUI();
    
    // Clear balance displays
    const balanceElements = document.querySelectorAll('.user-balance, #userBalance, #userBalanceDisplay');
    balanceElements.forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });
    
    // Clear wallet address display
    const walletDisplay = document.getElementById('walletAddressDisplay');
    if (walletDisplay) {
        walletDisplay.textContent = '';
        walletDisplay.style.display = 'none';
    }
    
    // Reload page to clear all state
    window.location.reload();
};

function updateBalanceDisplay() {
    // Update balance in trading UI
    const balanceElements = document.querySelectorAll('.user-balance, #userBalance');
    balanceElements.forEach(el => {
        el.textContent = `${formatNumberWithCommas(userBalance, 2)} EURC`;
    });
    
    // Update balance in navbar - show when wallet is connected
    const balanceDisplay = document.getElementById('userBalanceDisplay');
    if (balanceDisplay) {
        if (currentAccount) {
            balanceDisplay.innerHTML = `
                <span>${formatNumberWithCommas(userBalance, 2)} EURC</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="opacity: 0.6;">
                    <path d="M3 4.5L6 7.5L9 4.5"/>
                </svg>
            `;
            balanceDisplay.style.display = 'inline-flex';
            balanceDisplay.style.cursor = 'pointer';
        } else {
            balanceDisplay.style.display = 'none';
        }
    }
    
    // Update balance in profile page
    const profileBalance = document.getElementById('profileBalance');
    if (profileBalance) {
        profileBalance.innerHTML = `
            <span>${formatNumberWithCommas(userBalance, 2)} EURC</span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="opacity: 0.6;">
                <path d="M3 4.5L6 7.5L9 4.5"/>
            </svg>
        `;
        profileBalance.style.cursor = 'pointer';
    }
    
    // Update balance in market detail page trading card
    const balanceSmall = document.querySelector('small.text-muted');
    if (balanceSmall && balanceSmall.textContent.includes('Balance:')) {
        balanceSmall.innerHTML = `Balance: <span id="userBalance">${formatNumberWithCommas(userBalance, 2)} EURC</span>`;
    }
}

function updateWalletUI() {
    const btn = document.getElementById('connectWalletBtn');
    const connectedGroup = document.getElementById('walletConnectedGroup');
    
    if (!btn) return;
    
    if (currentAccount) {
        // Show connected group (only balance, no wallet address)
        if (connectedGroup) {
            connectedGroup.style.display = 'flex';
        }
        
        // Hide connect button
        btn.style.display = 'none';
        
        // Create and setup dropdown
        createWalletDropdown();
    } else {
        // Hide connected group
        if (connectedGroup) {
            connectedGroup.style.display = 'none';
        }
        
        // Remove dropdown if exists
        const walletDropdown = document.getElementById('walletDropdown');
        if (walletDropdown) {
            walletDropdown.remove();
        }
        
        btn.style.display = 'inline-block';
        btn.innerHTML = '<span class="wallet-icon">🔗</span> Connect Wallet';
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.onclick = connectWallet;
    }
    
    // Update balance display when wallet state changes
    updateBalanceDisplay();
}

function createWalletDropdown() {
    // Remove existing dropdown if any
    const existingDropdown = document.getElementById('walletDropdown');
    if (existingDropdown) {
        existingDropdown.remove();
    }
    
    // Create new dropdown
    const dropdown = document.createElement('div');
    dropdown.id = 'walletDropdown';
    dropdown.className = 'wallet-dropdown';
    dropdown.innerHTML = `
                <div class="wallet-dropdown-header">
                    <span class="wallet-dropdown-label">Connected Wallet</span>
                    <span class="wallet-dropdown-address">${currentAccount}</span>
                </div>
                <div class="wallet-dropdown-divider"></div>
                <button class="wallet-dropdown-item" onclick="disconnectWallet()">
                    <span class="wallet-dropdown-icon">🚪</span>
                    <span>Disconnect</span>
                </button>
            `;
    
    document.body.appendChild(dropdown);
    
    // Make balance display clickable to toggle dropdown
    const balanceDisplay = document.getElementById('userBalanceDisplay');
    if (balanceDisplay) {
        balanceDisplay.style.cursor = 'pointer';
        balanceDisplay.onclick = (e) => {
            e.stopPropagation();
            const rect = balanceDisplay.getBoundingClientRect();
            dropdown.style.position = 'fixed';
            dropdown.style.top = `${rect.bottom + 8}px`;
            dropdown.style.right = `${window.innerWidth - rect.right}px`;
            dropdown.classList.toggle('show');
        };
    }
        
        // Close dropdown when clicking outside
        const closeDropdownOnOutsideClick = (e) => {
        if (!dropdown.contains(e.target) && e.target !== balanceDisplay) {
            dropdown.classList.remove('show');
            }
        };
        
        document.removeEventListener('click', closeDropdownOnOutsideClick);
        document.addEventListener('click', closeDropdownOnOutsideClick);
}

function disconnectWallet() {
    currentAccount = null;
    // Don't reset userBalance to 0 - it's stored in database and will be loaded when reconnecting
    userBalance = 0.0; // Only reset display, actual balance stays in database
    updateWalletUI();
    updateBalanceDisplay();
    
    // Update profile page if we're on it
    if (window.location.pathname === '/profile') {
        updateProfileDisplay();
    }
    
    // Close dropdown
    const walletDropdown = document.getElementById('walletDropdown');
    if (walletDropdown) {
        walletDropdown.classList.remove('show');
    }
    
    // Show message
    showMessage('Wallet disconnected. Your balance is saved and will be restored when you reconnect.', 'info', 'tradingMessage');
    
    // Reload page data if on my-bets page
    if (window.location.pathname === '/my-bets') {
        loadUserBets();
    }
}

// ========== UTILITY FUNCTIONS ==========
// (escapeHtml is at top of file)

function showMessage(message, type, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const alertClass = type === 'success' ? 'alert-success' : (type === 'error' ? 'alert-danger' : 'alert-info');
    
    container.innerHTML = `
        <div class="alert ${alertClass}" role="alert">
            ${message}
        </div>
    `;
    
    if (type === 'success') {
        setTimeout(() => {
            container.innerHTML = '';
        }, 5000);
    }
}

// ========== PROFILE / KYC PAGE ==========
function initProfilePage() {
    console.log('Initializing profile page');
    
    // Setup wallet connection
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
    // Setup KYC submit button - use event delegation for dynamic buttons
    document.addEventListener('click', (e) => {
        if (e.target && e.target.id === 'kycSubmitBtn') {
            e.preventDefault();
            openKYCModal();
        }
    });
    
    // Also setup the button if it exists on page load
    const kycSubmitBtn = document.getElementById('kycSubmitBtn');
    if (kycSubmitBtn) {
        kycSubmitBtn.addEventListener('click', (e) => {
            e.preventDefault();
            openKYCModal();
        });
    }
    
    // Initialize profile display based on wallet connection
    updateProfileDisplay();
    
    // Load KYC status if wallet is connected
    if (currentAccount) {
        loadKYCStatus();
    }
    
    // Setup file input handler
    const fileInput = document.getElementById('kycFileInput');
    if (fileInput) {
        fileInput.addEventListener('change', handleKYCFileSelect);
    }
    
    // Setup upload button
    const uploadBtn = document.getElementById('kycUploadBtn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', uploadKYCDocument);
    }
    
    // Setup cancel button
    const cancelBtn = document.getElementById('kycCancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', cancelKYCUpload);
    }
    
    // Setup retry button
    const retryBtn = document.getElementById('kycRetryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', resetKYCUpload);
    }
}

function updateProfileDisplay() {
    const profileWallet = document.getElementById('profileWalletAddress');
    const profileBalance = document.getElementById('profileBalance');
    
    if (!currentAccount) {
        // Update profile display for disconnected state
        if (profileWallet) profileWallet.textContent = 'Not connected';
        if (profileBalance) {
            profileBalance.innerHTML = `
                <span>0.00 EURC</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="opacity: 0.6;">
                    <path d="M3 4.5L6 7.5L9 4.5"/>
                </svg>
            `;
        }
    } else {
        // Update wallet and balance display
        if (profileWallet) {
            profileWallet.textContent = currentAccount.slice(0, 6) + '...' + currentAccount.slice(-4);
        }
        if (profileBalance) {
            profileBalance.innerHTML = `
                <span>${formatNumberWithCommas(userBalance, 2)} EURC</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="opacity: 0.6;">
                    <path d="M3 4.5L6 7.5L9 4.5"/>
                </svg>
            `;
            profileBalance.style.cursor = 'pointer';
        }
    }
}

function openKYCModal() {
    const modal = document.getElementById('kycUploadModal');
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeKYCModal() {
    const modal = document.getElementById('kycUploadModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
        resetKYCUpload();
    }
}

async function loadKYCStatus() {
    const profileWallet = document.getElementById('profileWalletAddress');
    const profileBalance = document.getElementById('profileBalance');
    const profileKYCStatus = document.getElementById('profileKYCStatus');
    const kycNotVerified = document.getElementById('kycNotVerified');
    const kycVerified = document.getElementById('kycVerified');
    const kycRejected = document.getElementById('kycRejected');
    
    if (!currentAccount) {
        // Update profile display for disconnected state
        if (profileWallet) profileWallet.textContent = 'Not connected';
        if (profileBalance) profileBalance.textContent = '0.00 EURC';
        if (profileKYCStatus) profileKYCStatus.innerHTML = '<span class="badge bg-secondary">Not Submitted</span>';
        // Keep KYC section visible even when not connected
        return;
    }
    
    try {
        // Update wallet and balance display
        if (profileWallet) {
            profileWallet.textContent = currentAccount.slice(0, 6) + '...' + currentAccount.slice(-4);
        }
        if (profileBalance) {
            profileBalance.innerHTML = `
                <span>${formatNumberWithCommas(userBalance, 2)} EURC</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="opacity: 0.6;">
                    <path d="M3 4.5L6 7.5L9 4.5"/>
                </svg>
            `;
            profileBalance.style.cursor = 'pointer';
        }
        
        // Fetch KYC status
        const response = await fetch(`/api/kyc/status?wallet=${currentAccount}`);
        const data = await response.json();
        
        if (data.status === 'not_submitted') {
            // Show upload form
            if (kycNotVerified) kycNotVerified.style.display = 'block';
            if (kycVerified) kycVerified.style.display = 'none';
            if (kycRejected) kycRejected.style.display = 'none';
            if (profileKYCStatus) {
                profileKYCStatus.innerHTML = `
                    <span class="badge bg-secondary" style="font-size: 0.875rem; padding: 0.5rem 0.75rem;">Not Submitted</span>
                    <button id="kycSubmitBtn" class="btn btn-primary" style="font-size: 0.875rem; padding: 0.5rem 1rem; height: auto;">Submit Now</button>
                `;
                // Event listener will be handled by document-level delegation
            }
        } else if (data.status === 'verified') {
            // Show verified status with re-verify button
            if (profileKYCStatus) {
                profileKYCStatus.innerHTML = `
                    <span class="badge bg-success" style="font-size: 0.875rem; padding: 0.5rem 0.75rem;">✓ Verified</span>
                    <button id="kycSubmitBtn" class="btn btn-outline-primary" style="font-size: 0.875rem; padding: 0.5rem 1rem; height: auto;">Re-verify</button>
                `;
            }
            
            // Don't show alert on status load - only on new verification
            // The alert is handled in uploadKYCDocument function
            
            // Populate verified info (if elements exist)
            const kycFullName = document.getElementById('kycFullName');
            const kycDOB = document.getElementById('kycDOB');
            const kycNationality = document.getElementById('kycNationality');
            const kycDocType = document.getElementById('kycDocType');
            const kycDocNumber = document.getElementById('kycDocNumber');
            
            if (kycFullName) kycFullName.textContent = data.data.full_name || '—';
            if (kycDOB) kycDOB.textContent = data.data.date_of_birth || '—';
            if (kycNationality) kycNationality.textContent = data.data.nationality || '—';
            if (kycDocType) {
                kycDocType.textContent = (data.data.document_type || '—').replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            }
            if (kycDocNumber) kycDocNumber.textContent = data.data.document_number || '—';
        } else if (data.status === 'rejected') {
            // Show rejection
            if (profileKYCStatus) {
                profileKYCStatus.innerHTML = `
                    <span class="badge bg-danger">✕ Rejected</span>
                    <button id="kycSubmitBtn" class="btn btn-primary" style="font-size: 0.875rem; padding: 0.5rem 1rem; height: auto;">Try Again</button>
                `;
            }
        }
    } catch (error) {
        console.error('Failed to load KYC status:', error);
    }
}

function handleKYCFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.type.match('image/(jpeg|jpg|png)')) {
        alert('Please upload a JPEG or PNG image');
        event.target.value = '';
        return;
    }
    
    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
        alert('Image size must be less than 5MB');
        event.target.value = '';
        return;
    }
    
    // Show preview
    const reader = new FileReader();
    reader.onload = function(e) {
        const previewImg = document.getElementById('kycPreviewImg');
        const imagePreview = document.getElementById('kycImagePreview');
        if (previewImg) previewImg.src = e.target.result;
        if (imagePreview) imagePreview.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

async function uploadKYCDocument() {
    if (!currentAccount) {
        alert('Please connect your wallet first');
        closeKYCModal();
        return;
    }
    
    const fileInput = document.getElementById('kycFileInput');
    const file = fileInput?.files[0];
    
    if (!file) {
        alert('Please select a document to upload');
        return;
    }
    
    // Show progress
    const imagePreview = document.getElementById('kycImagePreview');
    const uploadProgress = document.getElementById('kycUploadProgress');
    if (imagePreview) imagePreview.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'block';
    
    try {
        // Convert image to base64
        const base64 = await convertImageToBase64(file);
        
        // Upload to API (API will handle data URL prefix stripping)
        const response = await fetch('/api/kyc/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                wallet: currentAccount,
                document_image: base64
            })
        });
        
        // Parse response
        let data;
        try {
            data = await response.json();
        } catch (parseError) {
            throw new Error(`Server returned invalid response (Status: ${response.status})`);
        }
        
        // Hide progress
        if (uploadProgress) uploadProgress.style.display = 'none';
        
        // Handle response based on status code and data
        if (!response.ok) {
            // HTTP error status
            const errorMsg = data.error || data.message || `Upload failed (HTTP ${response.status})`;
            throw new Error(errorMsg);
        }
        
        // Handle response
        if (data.status === 'verified') {
            // Close modal
            closeKYCModal();
            
            // Show surprise reward message
            const oldBalance = userBalance;
            await loadUserBalance();
            const rewardAmount = userBalance - oldBalance;
            
            if (rewardAmount > 0) {
                alert(`✅ Identity verified successfully!\n\n🎉 Surprise! You've received ${formatNumberWithCommas(rewardAmount, 2)} EURC as a verification bonus!`);
            } else {
                alert('✅ Identity verified successfully!');
            }
            
            // Reload status and update display
            await loadKYCStatus();
            updateProfileDisplay();
        } else if (data.status === 'rejected') {
            // Show rejection message
            const rejectionReason = data.reason || data.message || 'Verification failed. Please try again with a clear photo of your official ID.';
            alert(`❌ Verification Failed\n\n${rejectionReason}`);
            
            // Reset upload form
            if (fileInput) fileInput.value = '';
            if (imagePreview) imagePreview.style.display = 'none';
            if (uploadProgress) uploadProgress.style.display = 'none';
        } else if (data.error || data.message) {
            // Show error message
            const errorMsg = data.error || data.message || 'Unknown error occurred';
            alert(`❌ Error: ${errorMsg}`);
            
            // Reset upload form
            if (fileInput) fileInput.value = '';
            if (imagePreview) imagePreview.style.display = 'none';
            if (uploadProgress) uploadProgress.style.display = 'none';
        } else {
            // Unknown response format
            console.error('Unexpected API response:', data);
            alert('❌ Unexpected response from server. Please try again.');
            if (uploadProgress) uploadProgress.style.display = 'none';
            if (imagePreview) imagePreview.style.display = 'block';
        }
    } catch (error) {
        console.error('KYC upload error:', error);
        
        // Hide progress
        if (uploadProgress) uploadProgress.style.display = 'none';
        
        // Show user-friendly error message
        const errorMessage = error.message || 'Failed to upload document. Please check your connection and try again.';
        alert(`❌ Upload Failed\n\n${errorMessage}`);
        
        // Reset upload form
        if (fileInput) fileInput.value = '';
        if (imagePreview) imagePreview.style.display = 'block';
    }
}

function cancelKYCUpload() {
    // Reset file input and hide preview
    const fileInput = document.getElementById('kycFileInput');
    const imagePreview = document.getElementById('kycImagePreview');
    if (fileInput) fileInput.value = '';
    if (imagePreview) imagePreview.style.display = 'none';
}

function resetKYCUpload() {
    // Reset to upload form
    const kycRejected = document.getElementById('kycRejected');
    const kycNotVerified = document.getElementById('kycNotVerified');
    const fileInput = document.getElementById('kycFileInput');
    const imagePreview = document.getElementById('kycImagePreview');
    const previewImg = document.getElementById('kycPreviewImg');
    
    if (kycRejected) kycRejected.style.display = 'none';
    if (kycNotVerified) kycNotVerified.style.display = 'block';
    if (fileInput) fileInput.value = '';
    if (imagePreview) imagePreview.style.display = 'none';
    if (previewImg) previewImg.src = '';
}

function convertImageToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Return the full data URL - the API will handle stripping the prefix
            resolve(reader.result);
        };
        reader.onerror = (error) => {
            reject(new Error('Failed to read file: ' + error));
        };
        reader.readAsDataURL(file);
    });
}

// Make functions globally accessible
window.initProfilePage = initProfilePage;
window.loadKYCStatus = loadKYCStatus;
