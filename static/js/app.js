// Global variables
let userLocation = { latitude: null, longitude: null, country: '', city: '' };
let currentAccount = null;
let currentFilter = 'all';
let allMarkets = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;
    
    // Common initialization
    tryInitWallet();
    
    // Page-specific initialization
    if (path === '/' || path === '/index.html') {
        initHomePage();
    } else if (path === '/waitlist') {
        initWaitlistPage();
    } else if (path.startsWith('/market/')) {
        initMarketDetailPage();
    } else if (path === '/my-bets') {
        initMyBetsPage();
    } else if (path === '/admin') {
        initAdminDashboard();
    } else if (path === '/admin/create-market') {
        initAdminCreateMarket();
    } else if (path === '/admin/resolve') {
        initAdminResolvePage();
    }
});

// ========== UTILITY FUNCTIONS ==========
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
    
    // Load markets
    loadHomeMarkets();
    
    // Load activity feed
    loadActivityFeed();
    
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
    document.getElementById('totalVolume').textContent = `$${formatNumber(totalVolume)}`;
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
                        <span>€${(total).toFixed(0)} volume</span>
                        <span class="market-status-badge ${statusClass}">${statusText}</span>
                    </div>
                </div>
            </a>
        `;
    }).join('');
}

// ========== WAITLIST PAGE ==========
function initWaitlistPage() {
    // Load initial count
    updateCount();
    
    // Request geolocation
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            handleGeolocationSuccess,
            handleGeolocationError,
            { timeout: 10000, enableHighAccuracy: false }
        );
    } else {
        fallbackIPLookup();
    }
    
    // Setup form submission
    const form = document.getElementById('waitlistForm');
    if (form) {
    form.addEventListener('submit', handleFormSubmit);
    }
    
    // Setup premium button
    const premiumBtn = document.getElementById('premiumBtn');
    if (premiumBtn) {
        premiumBtn.addEventListener('click', handlePremiumSubscription);
    }
}

function handleGeolocationSuccess(position) {
    userLocation.latitude = position.coords.latitude;
    userLocation.longitude = position.coords.longitude;
    reverseGeocode(userLocation.latitude, userLocation.longitude);
}

function handleGeolocationError(error) {
    console.log('Geolocation error:', error.message);
    fallbackIPLookup();
}

function reverseGeocode(lat, lon) {
    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`)
        .then(response => response.json())
        .then(data => {
            if (data.address) {
                userLocation.country = data.address.country || '';
                userLocation.city = data.address.city || data.address.town || data.address.village || '';
            }
        })
        .catch(error => console.log('Reverse geocoding failed:', error));
}

function fallbackIPLookup() {
    fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {
            userLocation.latitude = data.latitude || null;
            userLocation.longitude = data.longitude || null;
            userLocation.country = data.country_name || '';
            userLocation.city = data.city || '';
        })
        .catch(error => console.log('IP lookup failed:', error));
}

function updateCount() {
    fetch('/api/count')
        .then(response => response.json())
        .then(data => {
            const countElement = document.getElementById('registrationCount');
            if (countElement) {
            countElement.textContent = data.count || 0;
            }
        })
        .catch(error => console.log('Error fetching count:', error));
}

function handleFormSubmit(event) {
    event.preventDefault();
    
    const emailInput = document.getElementById('emailInput');
    const submitBtn = document.getElementById('submitBtn');
    const email = emailInput.value.trim();
    
    if (!email || !isValidEmail(email)) {
        showMessage('Please enter a valid email address', 'error', 'messageContainer');
        return;
    }
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Joining...';
    
    fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
        email: email,
        latitude: userLocation.latitude,
        longitude: userLocation.longitude,
        country: userLocation.country,
        city: userLocation.city
        })
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(result => {
        if (result.status === 200 && result.body.success) {
            showMessage(result.body.message, 'success', 'messageContainer');
            emailInput.value = '';
            updateCount();
        } else {
            showMessage(result.body.message || 'An error occurred', 'error', 'messageContainer');
        }
    })
    .catch(error => {
        console.error('Submission error:', error);
        showMessage('Network error. Please try again.', 'error', 'messageContainer');
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Join Waitlist';
    });
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function handlePremiumSubscription() {
    const premiumBtn = document.getElementById('premiumBtn');
    const originalText = premiumBtn.innerHTML;
    
    try {
        premiumBtn.disabled = true;
        premiumBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
        
        const emailInput = document.getElementById('emailInput');
        const userEmail = emailInput ? emailInput.value.trim() : '';
        
        const response = await fetch('/api/create-checkout-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: userEmail })
        });
        
        const data = await response.json();
        
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            throw new Error(data.error || 'Failed to create checkout session');
        }
    } catch (error) {
        console.error('Premium subscription error:', error);
        showMessage('Failed to start premium subscription. Please try again.', 'error', 'messageContainer');
        premiumBtn.disabled = false;
        premiumBtn.innerHTML = originalText;
    }
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
                    const changeClass = item.probability_change > 0 ? 'positive' : 
                                      item.probability_change < 0 ? 'negative' : 'neutral';
                    const changeIcon = item.probability_change > 0 ? '↑' : 
                                     item.probability_change < 0 ? '↓' : '→';
                    const changeText = item.probability_change !== 0 ? 
                                     `${changeIcon} ${Math.abs(item.probability_change).toFixed(1)}%` : 
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
                            <span class="activity-amount">$${item.amount.toFixed(2)}</span>
                            <span class="activity-shares">${item.shares.toFixed(2)} shares</span>
                            <span class="activity-item-wallet">${walletShort}</span>
                            <span class="activity-item-time">${timeAgo}</span>
                            <div class="activity-transaction-prob">
                                <span class="activity-probability-value">${item.current_probability}%</span>
                                <span class="activity-probability-change ${changeClass} ${item.probability_change !== 0 ? 'flash' : ''}" data-prob-change="${item.probability_change}">${changeText}</span>
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
                <div class="text-center text-muted py-5">
                    <p>No recent activity yet. Be the first to place a bet!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load activity feed:', error);
        feedContainer.innerHTML = `
            <div class="text-center text-muted py-5">
                <p>Unable to load activity feed</p>
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

function initMarketDetailPage() {
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
    // Setup side selection buttons
    document.getElementById('selectYesBtn')?.addEventListener('click', () => selectSide('YES'));
    document.getElementById('selectNoBtn')?.addEventListener('click', () => selectSide('NO'));
    
    // Setup input listener for live preview
    const input = document.getElementById('betAmountInput');
    if (input) {
        input.addEventListener('input', updateTradePreview);
    }
    
    // Setup buy button
    document.getElementById('buyButton')?.addEventListener('click', executeBuy);
    
    loadMarketDetail();
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh market prices every 3 seconds to show price changes
    setInterval(loadMarketDetail, 3000);
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

function selectSide(side) {
    selectedSide = side;
    
    // Update button states
    document.getElementById('selectYesBtn').classList.toggle('selected', side === 'YES');
    document.getElementById('selectNoBtn').classList.toggle('selected', side === 'NO');
    
    // Show amount section (if not already shown)
    document.getElementById('amountSection').style.display = 'block';
    
    // Update buy button text
    const buyBtn = document.getElementById('buyButton');
    buyBtn.textContent = `Buy ${side}`;
    buyBtn.style.display = 'block';
    
    // Keep input value when switching sides - just update preview
    updateTradePreview();
}

let currentPrices = { yes_price: 0.50, no_price: 0.50 };
let previousPrices = { yes_price: 0.50, no_price: 0.50 }; // Track previous prices for animations

async function loadMarketDetail() {
    try {
        const [marketRes, priceRes] = await Promise.all([
            fetch(`/api/markets/${MARKET_ID}`),
            fetch(`/api/markets/${MARKET_ID}/price`)
        ]);
        
        const marketData = await marketRes.json();
        const priceData = await priceRes.json();
        
        currentPrices = priceData;
        renderMarketDetail(marketData.market, priceData);
        } catch (e) {
        console.error('Failed to load market detail', e);
    }
}

function renderMarketDetail(market, prices) {
    const infoContainer = document.getElementById('marketDetailInfo');
    const oddsContainer = document.getElementById('oddsDisplay');
    
    if (!market) return;
    
    const yesTotal = market.yes_total || 0;
    const noTotal = market.no_total || 0;
    const total = yesTotal + noTotal;
    
    const yesCents = prices.yes_price_cents || 50;
    const noCents = prices.no_price_cents || 50;
    
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
    
    infoContainer.innerHTML = `
        ${market.image_url ? `<img src="${imageUrl}" alt="${escapeHtml(market.question)}" style="width: 100%; border-radius: 12px; margin-bottom: 2rem;" onerror="this.src='https://via.placeholder.com/1200x400/1E293B/3B82F6?text=No+Image'">` : ''}
        ${market.category ? `<span class="market-category">${escapeHtml(market.category)}</span>` : ''}
        <h1 class="mb-3">${escapeHtml(market.question)}</h1>
        <p class="text-muted mb-4">${escapeHtml(market.description || '')}</p>
        ${market.end_date ? `<p class="text-muted small">Ends: ${market.end_date}</p>` : ''}
        <div class="border-top border-secondary pt-3 mt-3">
            <div class="row">
                <div class="col-md-4"><strong>Status:</strong> ${market.status}</div>
                <div class="col-md-4"><strong>Total Volume:</strong> €${total.toFixed(2)}</div>
                <div class="col-md-4"><strong>Bets:</strong> ${market.bet_count || 0}</div>
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
            Each share pays $1.00 if correct
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
    
    // Disable betting if resolved
    if (market.status !== 'open') {
        document.getElementById('selectYesBtn').disabled = true;
        document.getElementById('selectNoBtn').disabled = true;
        document.getElementById('betAmountInput').disabled = true;
        document.getElementById('buyButton').disabled = true;
    } else {
        document.getElementById('selectYesBtn').disabled = false;
        document.getElementById('selectNoBtn').disabled = false;
        document.getElementById('betAmountInput').disabled = false;
        document.getElementById('buyButton').disabled = false;
    }
}

function updateTradePreview() {
    const inputValue = parseFloat(document.getElementById('betAmountInput').value || 0);
    const previewDiv = document.getElementById('tradePreview');
    
    if (inputValue <= 0 || !currentPrices || !selectedSide) {
        // Hide preview if no input or no side selected
        previewDiv.style.display = 'none';
        return;
    }
    
    // Show preview
    previewDiv.style.display = 'block';
    
    // Calculate based on selected side
    const price = selectedSide === 'YES' ? currentPrices.yes_price : currentPrices.no_price;
    const shares = inputValue / price;
    const roundedShares = Math.round(shares * 100) / 100;
    
    // Potential win is shares * $1
    const potentialWin = roundedShares * 1.0;
    const profit = potentialWin - inputValue;
    
    // Update preview - separate raw profit (white) and net profit (green)
    document.getElementById('previewShares').textContent = `${roundedShares.toFixed(2)} shares`;
    document.getElementById('previewWinAmount').textContent = `$${potentialWin.toFixed(2)}`;
    document.getElementById('previewWinProfit').textContent = `(+$${profit.toFixed(2)})`;
}

function executeBuy() {
    if (!selectedSide) {
        showMessage('Please select Yes or No first', 'error', 'tradingMessage');
        return;
    }
    
    placeBetOnDetail(selectedSide);
}

async function placeBetOnDetail(side) {
    if (!currentAccount) {
        showMessage('Connect your wallet first.', 'error', 'tradingMessage');
        return;
    }
    
    const inputValue = parseFloat(document.getElementById('betAmountInput').value || '0');
    if (!inputValue || inputValue <= 0) {
        showMessage('Enter a valid amount', 'error', 'tradingMessage');
        return;
    }
    
    const amount = Math.round(inputValue * 100) / 100;
    
    try {
        showMessage('Placing bet...', 'info', 'tradingMessage');
        
        const res = await fetch(`/api/markets/${MARKET_ID}/bet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet: currentAccount, side, amount })
    });
        
    const body = await res.json();
        
        if (res.status === 202 && body.status === 'queued') {
            // Bet is queued, show warning popup
            showQueueWarning();
            // Poll for completion
            pollBetStatus(body.request_id);
        } else if (res.ok && body.success) {
            // Immediate success (backward compatibility)
            const actualShares = body.shares || 0;
            const totalCost = amount.toFixed(2);
            showMessage(`Bet placed! You bought ${actualShares.toFixed(2)} shares for $${totalCost}`, 'success', 'tradingMessage');
            resetBetUI();
            await loadMarketDetail();
            updateTradePreview();
    } else {
            showMessage(body.message || 'Failed to place bet', 'error', 'tradingMessage');
        }
    } catch (e) {
        console.error('Failed to place bet', e);
        showMessage('Error placing bet', 'error', 'tradingMessage');
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
            <h5>Bet in Queue</h5>
            <p>Your bet is being processed. Prices may change while you wait!</p>
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
    
    // NO auto-hide - popup persists until bet is processed
}

function hideQueueWarning() {
    const popup = document.getElementById('queueWarningPopup');
    if (popup) {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 300);
    }
}

async function pollBetStatus(requestId) {
    const maxAttempts = 30; // 30 seconds max
    let attempts = 0;
    
    const poll = async () => {
        try {
            const res = await fetch(`/api/bets/${requestId}/status`);
        const data = await res.json();
            
            if (data.success !== undefined && data.status !== 'processing') {
                // Bet completed
                hideQueueWarning();
                if (data.success) {
                    const shares = data.shares || 0;
                    const price = data.price_per_share || 0;
                    showMessage(`Bet placed! ${shares.toFixed(2)} shares @ ${(price * 100).toFixed(1)}¢`, 'success', 'tradingMessage');
                    resetBetUI();
                    await loadMarketDetail();
                    updateTradePreview();
                } else {
                    showMessage(data.message || 'Bet failed', 'error', 'tradingMessage');
                }
                return;
            }
            
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 1000); // Poll every second
            } else {
                hideQueueWarning();
                showMessage('Bet processing is taking longer than expected. Please check your portfolio.', 'warning', 'tradingMessage');
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

function resetBetUI() {
    document.getElementById('betAmountInput').value = '';
    selectedSide = null;
    document.getElementById('amountSection').style.display = 'none';
    document.getElementById('tradePreview').style.display = 'none';
    document.getElementById('buyButton').style.display = 'none';
    document.getElementById('selectYesBtn').classList.remove('selected');
    document.getElementById('selectNoBtn').classList.remove('selected');
}

// ========== MY BETS PAGE ==========
function initMyBetsPage() {
    const connectBtn = document.getElementById('connectWalletBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWallet);
    }
    
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
    document.getElementById('navValue').textContent = `$${navValue.toFixed(2)}`;
    const navChangeEl = document.getElementById('navChange');
    navChangeEl.className = `nav-change ${totalPL > 0 ? 'positive' : (totalPL < 0 ? 'negative' : '')}`;
    navChangeEl.innerHTML = `
        <span class="nav-change-amount">${totalPL > 0 ? '+' : ''}$${totalPL.toFixed(2)}</span>
        <span class="nav-change-percent">(${returnPct > 0 ? '+' : ''}${returnPct.toFixed(2)}%)</span>
    `;
    
    // Update metric cards
    document.getElementById('openPositions').textContent = openPositions.length;
    document.getElementById('totalInvested').textContent = `$${totalInvested.toFixed(2)}`;
    
    // Update performance metrics
    const realizedPLEl = document.getElementById('realizedPL');
    realizedPLEl.textContent = `${realizedPL > 0 ? '+' : ''}$${realizedPL.toFixed(2)}`;
    realizedPLEl.className = `performance-value realized-pl ${realizedPL > 0 ? 'positive' : (realizedPL < 0 ? 'negative' : '')}`;
    
    const unrealizedPLEl = document.getElementById('unrealizedPL');
    unrealizedPLEl.textContent = `${unrealizedPL > 0 ? '+' : ''}$${unrealizedPL.toFixed(2)}`;
    unrealizedPLEl.className = `performance-value unrealized-pl ${unrealizedPL > 0 ? 'positive' : (unrealizedPL < 0 ? 'negative' : '')}`;
    
    const totalPLEl = document.getElementById('totalPL');
    totalPLEl.textContent = `${totalPL > 0 ? '+' : ''}$${totalPL.toFixed(2)}`;
    totalPLEl.className = `performance-value total-pl ${totalPL > 0 ? 'positive' : (totalPL < 0 ? 'negative' : '')}`;
    
    const returnPctEl = document.getElementById('returnPct');
    returnPctEl.textContent = `${returnPct > 0 ? '+' : ''}${returnPct.toFixed(2)}%`;
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
                    <td class="text-end">${(b.shares || 0).toFixed(2)}</td>
                    <td class="text-end">$${b.amount.toFixed(2)}</td>
                    <td class="text-end">${((b.buy_price || 0) * 100).toFixed(1)}¢</td>
                    <td class="text-end">${((b.current_price || 0) * 100).toFixed(1)}¢</td>
                    <td class="text-end">$${(b.current_value || 0).toFixed(2)}</td>
                    <td class="text-end ${plClass}">
                        ${unrealizedProfit > 0 ? '+' : ''}$${unrealizedProfit.toFixed(2)}
                    </td>
                    <td class="text-end ${plClass}">
                        ${returnPct > 0 ? '+' : ''}${returnPct.toFixed(2)}%
                    </td>
                    <td class="text-center">
                        <button class="sell-btn-portfolio" onclick="openSellModal(${b.id}, ${b.market_id}, ${(b.shares || 0)}, ${(b.amount || 0)}, ${(b.buy_price || 0)}, ${(b.current_price || 0)}, ${(b.current_value || 0)}, ${(b.unrealized_profit || 0)}, '${escapeHtml(b.question || '')}', '${b.side || ''}')">
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
                    <td class="text-end">${(b.shares || 0).toFixed(2)}</td>
                    <td class="text-end">$${costBasis.toFixed(2)}</td>
                    <td class="text-end">$${payout.toFixed(2)}</td>
                    <td class="text-end ${plClass}">
                        ${profit > 0 ? '+' : ''}$${profit.toFixed(2)}
                    </td>
                    <td class="text-end ${plClass}">
                        ${returnPct > 0 ? '+' : ''}${returnPct.toFixed(2)}%
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
                <button class="sell-modal-close" onclick="closeSellModal()">&times;</button>
                </div>
            <div class="sell-modal-body">
                <div class="sell-market-info">
                    <h5>${escapeHtml(question)}</h5>
                    <span class="position-side-${side.toLowerCase()}">${side}</span>
                    </div>
                
                <div class="sell-details-grid">
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Shares</span>
                        <span class="sell-detail-value">${shares.toFixed(2)}</span>
                        </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Cost Basis</span>
                        <span class="sell-detail-value">$${costBasis.toFixed(2)}</span>
                    </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Buy Price</span>
                        <span class="sell-detail-value">${(buyPrice * 100).toFixed(1)}¢</span>
                </div>
                    <div class="sell-detail-item">
                        <span class="sell-detail-label">Current Price</span>
                        <span class="sell-detail-value">${(currentPrice * 100).toFixed(1)}¢</span>
            </div>
                </div>
                
                <div class="sell-summary">
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Sell Value</span>
                        <span class="sell-summary-value">$${currentValue.toFixed(2)}</span>
                    </div>
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Cost Basis</span>
                        <span class="sell-summary-value">$${costBasis.toFixed(2)}</span>
                    </div>
                    <div class="sell-summary-divider"></div>
                    <div class="sell-summary-row sell-summary-net">
                        <span class="sell-summary-label">Net P/L</span>
                        <span class="sell-summary-value ${plClass}" style="color: ${plColor}; font-weight: 700; font-size: 1.25rem;">
                            ${unrealizedProfit >= 0 ? '+' : ''}$${unrealizedProfit.toFixed(2)}
                        </span>
                    </div>
                    <div class="sell-summary-row">
                        <span class="sell-summary-label">Return</span>
                        <span class="sell-summary-value ${plClass}" style="color: ${plColor};">
                            ${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%
                        </span>
                    </div>
                </div>
            </div>
            <div class="sell-modal-footer">
                <button class="sell-modal-cancel" onclick="closeSellModal()">Cancel</button>
                <button class="sell-modal-confirm" onclick="confirmSell(${betId}, ${marketId}, ${shares})">
                    Confirm Sell
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
    
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
    if (!currentAccount) {
        showMessage('Connect your wallet first.', 'error');
        return;
    }
    
    try {
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
        
        closeSellModal();
        
        if (res.ok && data.success) {
            showMessage(data.message, 'success');
            // Reload bets
            await loadUserBets();
        } else {
            showMessage(data.message || 'Failed to sell shares', 'error');
        }
    } catch (e) {
        console.error('Failed to sell shares', e);
        showMessage('Error selling shares', 'error');
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
    
    // Load activity feed
    loadActivityFeed();
    
    // Refresh activity feed every 10 seconds
    setInterval(loadActivityFeed, 10000);
}

async function loadAdminStats() {
    try {
        const [marketsRes, countRes] = await Promise.all([
            fetch('/api/markets'),
            fetch('/api/count')
        ]);
        
        const marketsData = await marketsRes.json();
        const countData = await countRes.json();
        
        const markets = marketsData.markets || [];
        const totalMarkets = markets.length;
        const totalVolume = markets.reduce((sum, m) => sum + (m.yes_total || 0) + (m.no_total || 0), 0);
        const totalBets = markets.reduce((sum, m) => sum + (m.bet_count || 0), 0);
        
        document.getElementById('adminTotalMarkets').textContent = totalMarkets;
        document.getElementById('adminTotalBets').textContent = totalBets;
        document.getElementById('adminTotalVolume').textContent = `€${totalVolume.toFixed(0)}`;
        document.getElementById('waitlistCount').textContent = countData.count || 0;
    } catch (e) {
        console.error('Failed to load admin stats', e);
    }
}

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
    
    if (!question || !description || !category) {
        showMessage('Please fill in all required fields', 'error', 'createMessageContainer');
        return;
    }
    
    try {
    const res = await fetch('/api/markets', {
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
            showMessage('Market created successfully!', 'success', 'createMessageContainer');
            setTimeout(() => {
                window.location.href = '/admin';
            }, 2000);
    } else {
            showMessage(body.message || 'Failed to create market', 'error', 'createMessageContainer');
        }
    } catch (e) {
        showMessage('Error creating market', 'error', 'createMessageContainer');
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
        const yes = Number(m.yes_total || 0).toFixed(2);
        const no = Number(m.no_total || 0).toFixed(2);
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
                <strong>YES Pool:</strong> €${yes} | <strong>NO Pool:</strong> €${no} | <strong>Total Bets:</strong> ${m.bet_count}
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
        
    if (res.ok && body.success) {
            alert('Market resolved successfully!');
            await loadAdminMarkets();
    } else {
        alert(body.message || 'Failed to resolve market');
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
            alert(data.error || 'Failed to load payouts');
        return;
    }
        
        let html = `
            <div class="mb-3">
                <strong>Market Resolution:</strong> ${data.resolution}<br>
                <strong>Winning Pool:</strong> €${data.winning_total.toFixed(2)}<br>
                <strong>Losing Pool:</strong> €${data.losing_total.toFixed(2)}
            </div>
            <table class="table table-dark table-striped">
                <thead>
                    <tr>
                        <th>Wallet</th>
                        <th>Total Bet</th>
                        <th>Payout</th>
                        <th>Profit/Loss</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        data.payouts.forEach(p => {
            const profitClass = p.profit >= 0 ? 'text-success' : 'text-danger';
            const profitSign = p.profit >= 0 ? '+' : '';
            html += `
                <tr>
                    <td><code>${p.wallet.slice(0,6)}...${p.wallet.slice(-4)}</code></td>
                    <td>€${p.total_bet.toFixed(2)}</td>
                    <td>€${p.payout.toFixed(2)}</td>
                    <td class="${profitClass}"><strong>${profitSign}€${p.profit.toFixed(2)}</strong></td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
        
        document.getElementById('payoutModalBody').innerHTML = html;
        const modal = new bootstrap.Modal(document.getElementById('payoutModal'));
        modal.show();
        
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
        currentAccount = accounts[0];
        updateWalletUI();
        
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
                currentAccount = accounts[0];
                updateWalletUI();
                
                // Load user bets if on my-bets page
                if (window.location.pathname === '/my-bets') {
                    loadUserBets();
                }
            }
            window.ethereum.on('accountsChanged', (accs) => {
                currentAccount = accs && accs.length ? accs[0] : null;
                updateWalletUI();
                
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

function updateWalletUI() {
    const display = document.getElementById('walletAddressDisplay');
    const btn = document.getElementById('connectWalletBtn');
    if (!display || !btn) return;
    
    if (currentAccount) {
        const short = `${currentAccount.slice(0,6)}...${currentAccount.slice(-4)}`;
        
        // Create wallet dropdown if it doesn't exist
        let walletDropdown = document.getElementById('walletDropdown');
        if (!walletDropdown) {
            walletDropdown = document.createElement('div');
            walletDropdown.id = 'walletDropdown';
            walletDropdown.className = 'wallet-dropdown';
            walletDropdown.innerHTML = `
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
            document.body.appendChild(walletDropdown);
        }
        
        // Update dropdown with current address
        const addressSpan = walletDropdown.querySelector('.wallet-dropdown-address');
        if (addressSpan) {
            addressSpan.textContent = currentAccount;
        }
        
        // Position dropdown relative to wallet address display
        const updateDropdownPosition = () => {
            const rect = display.getBoundingClientRect();
            walletDropdown.style.position = 'fixed';
            walletDropdown.style.top = `${rect.bottom + 8}px`;
            walletDropdown.style.right = `${window.innerWidth - rect.right}px`;
        };
        
        // Make display clickable
        display.textContent = short;
        display.style.cursor = 'pointer';
        display.classList.add('wallet-address-clickable');
        display.onclick = (e) => {
            e.stopPropagation();
            updateDropdownPosition();
            walletDropdown.classList.toggle('show');
        };
        
        // Close dropdown when clicking outside
        const closeDropdownOnOutsideClick = (e) => {
            if (!walletDropdown.contains(e.target) && e.target !== display) {
                walletDropdown.classList.remove('show');
            }
        };
        
        // Remove old listener if exists
        document.removeEventListener('click', closeDropdownOnOutsideClick);
        document.addEventListener('click', closeDropdownOnOutsideClick);
        
        // Update position on scroll/resize
        window.addEventListener('scroll', updateDropdownPosition);
        window.addEventListener('resize', updateDropdownPosition);
        
        btn.innerHTML = '<span class="wallet-icon">✅</span> Connected';
        btn.disabled = true;
        btn.style.opacity = '0.7';
    } else {
        display.textContent = '';
        display.style.cursor = 'default';
        display.classList.remove('wallet-address-clickable');
        display.onclick = null;
        
        // Remove dropdown if exists
        const walletDropdown = document.getElementById('walletDropdown');
        if (walletDropdown) {
            walletDropdown.remove();
        }
        
        btn.innerHTML = '<span class="wallet-icon">🔗</span> Connect Wallet';
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

function disconnectWallet() {
    currentAccount = null;
    updateWalletUI();
    
    // Close dropdown
    const walletDropdown = document.getElementById('walletDropdown');
    if (walletDropdown) {
        walletDropdown.classList.remove('show');
    }
    
    // Show message
    showMessage('Wallet disconnected', 'info', 'tradingMessage');
    
    // Reload page data if on my-bets page
    if (window.location.pathname === '/my-bets') {
        loadUserBets();
    }
}

// ========== UTILITY FUNCTIONS ==========
function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
}

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
