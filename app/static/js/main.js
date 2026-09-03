/**
 * Main JS - Utility functions, API helpers, JWT management
 * AI-Powered Elderly Healthcare System
 */

// ===================== Token Management =====================
const TokenManager = {
    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        if (refresh) localStorage.setItem('refresh_token', refresh);
    },
    getAccessToken() { return localStorage.getItem('access_token'); },
    getRefreshToken() { return localStorage.getItem('refresh_token'); },
    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_data');
    },
    setUser(user) { localStorage.setItem('user_data', JSON.stringify(user)); },
    getUser() {
        try { return JSON.parse(localStorage.getItem('user_data')); }
        catch { return null; }
    },
    isLoggedIn() { return !!this.getAccessToken(); }
};

// ===================== API Helper =====================
const API = {
    BASE_URL: '/api',

    async request(method, endpoint, data = null, isFormData = false) {
        const url = `${this.BASE_URL}${endpoint}`;
        const headers = {};
        const token = TokenManager.getAccessToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        if (!isFormData) headers['Content-Type'] = 'application/json';

        const options = { method, headers };
        if (data) {
            options.body = isFormData ? data : JSON.stringify(data);
        }

        let response = await fetch(url, options);

        // Auto-refresh if 401
        if (response.status === 401 && endpoint !== '/auth/login') {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${TokenManager.getAccessToken()}`;
                options.headers = headers;
                response = await fetch(url, options);
            } else {
                TokenManager.clearTokens();
                window.location.href = '/login';
                return null;
            }
        }

        const json = await response.json().catch(() => ({}));
        json._status = response.status;
        json._ok = response.ok;
        return json;
    },

    async refreshToken() {
        const refreshToken = TokenManager.getRefreshToken();
        if (!refreshToken) return false;
        try {
            const res = await fetch(`${this.BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${refreshToken}`,
                    'Content-Type': 'application/json'
                }
            });
            if (res.ok) {
                const data = await res.json();
                TokenManager.setTokens(data.access_token, null);
                return true;
            }
        } catch { }
        return false;
    },

    get(endpoint) { return this.request('GET', endpoint); },
    post(endpoint, data) { return this.request('POST', endpoint, data); },
    put(endpoint, data) { return this.request('PUT', endpoint, data); },
    delete(endpoint) { return this.request('DELETE', endpoint); }
};

// ===================== Toast Notifications =====================
const Toast = {
    container: null,

    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', duration = 4000) {
        this.init();
        const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        const toast = document.createElement('div');
        toast.className = `toast-custom ${type}`;
        toast.innerHTML = `
            <span style="font-size:18px">${icons[type] || 'ℹ️'}</span>
            <span style="flex:1;font-size:14px;font-weight:500">${message}</span>
            <button onclick="this.parentElement.remove()" 
                style="border:none;background:none;cursor:pointer;color:#94a3b8;font-size:16px;padding:0;line-height:1">×</button>
        `;
        this.container.appendChild(toast);
        setTimeout(() => toast.remove(), duration);
    },

    success(msg) { this.show(msg, 'success'); },
    error(msg) { this.show(msg, 'error'); },
    warning(msg) { this.show(msg, 'warning'); },
    info(msg) { this.show(msg, 'info'); }
};

// ===================== Sidebar Toggle =====================
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const content = document.getElementById('content');
    const toggleBtn = document.getElementById('sidebar-toggle');

    if (!sidebar) return;

    toggleBtn?.addEventListener('click', () => {
        if (window.innerWidth <= 768) {
            sidebar.classList.toggle('mobile-open');
        } else {
            sidebar.classList.toggle('collapsed');
            content?.classList.toggle('expanded');
        }
    });

    // Mark active nav link
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.startsWith(href) && href !== '/') {
            link.classList.add('active');
        } else if (href === '/' && currentPath === '/') {
            link.classList.add('active');
        }
    });
}

// ===================== User Menu =====================
function initUserMenu() {
    const user = TokenManager.getUser();
    if (!user) return;

    // Update sidebar user info
    const sidebarAvatar = document.getElementById('sidebar-avatar');
    const sidebarUsername = document.getElementById('sidebar-username');
    const sidebarRole = document.getElementById('sidebar-role');
    const navbarUsername = document.getElementById('navbar-username');

    if (sidebarAvatar) sidebarAvatar.textContent = (user.full_name || user.username || 'U')[0].toUpperCase();
    if (sidebarUsername) sidebarUsername.textContent = user.full_name || user.username;
    if (sidebarRole) sidebarRole.textContent = user.role?.charAt(0).toUpperCase() + user.role?.slice(1);
    if (navbarUsername) navbarUsername.textContent = user.full_name || user.username;
}

// ===================== Auth Guard =====================
function requireAuth() {
    if (!TokenManager.isLoggedIn()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

function redirectIfLoggedIn() {
    if (TokenManager.isLoggedIn()) {
        window.location.href = '/dashboard';
    }
}

// ===================== Logout =====================
async function logout() {
    try {
        await API.post('/auth/logout');
    } catch { }
    TokenManager.clearTokens();
    window.location.href = '/login';
}

// ===================== Load Unread Alerts Badge =====================
async function loadAlertsBadge() {
    const badge = document.getElementById('alerts-badge');
    if (!badge || !TokenManager.isLoggedIn()) return;
    try {
        const data = await API.get('/alerts/unread');
        if (data && data.count > 0) {
            badge.textContent = data.count > 99 ? '99+' : data.count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    } catch { }
}

// ===================== Formatting Utilities =====================
const Utils = {
    formatDate(dateStr) {
        if (!dateStr) return '—';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    },
    formatTime(timeStr) {
        if (!timeStr) return '—';
        const [h, m] = timeStr.split(':');
        const d = new Date(); d.setHours(h, m);
        return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
    },
    formatDateTime(dtStr) {
        if (!dtStr) return '—';
        const d = new Date(dtStr);
        return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
    },
    timeAgo(dtStr) {
        if (!dtStr) return '';
        const diff = (Date.now() - new Date(dtStr)) / 1000;
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    },
    capitalize(str) { return str ? str.charAt(0).toUpperCase() + str.slice(1) : ''; },
    statusBadge(status) {
        const colors = {
            taken: 'badge-taken', missed: 'badge-missed',
            skipped: 'badge-skipped', pending: 'badge-pending',
            active: 'badge-active', inactive: 'badge-inactive'
        };
        return `<span class="badge ${colors[status] || 'bg-secondary'} px-2 py-1 rounded-pill">${Utils.capitalize(status)}</span>`;
    },
    severityBadge(severity) {
        const colors = { critical: 'danger', high: 'danger', medium: 'warning', low: 'success' };
        return `<span class="badge bg-${colors[severity] || 'secondary'}">${Utils.capitalize(severity)}</span>`;
    },
    adherenceColor(rate) {
        if (rate >= 80) return 'success';
        if (rate >= 60) return 'warning';
        return 'danger';
    },
    debounce(fn, delay = 300) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    }
};

// ===================== Table Helpers =====================
function showTableLoading(tbodyId, cols) {
    const tbody = document.getElementById(tbodyId);
    if (tbody) tbody.innerHTML = `<tr><td colspan="${cols}" class="text-center py-5"><div class="spinner-healthcare mx-auto"></div><p class="mt-3 text-muted">Loading...</p></td></tr>`;
}

function showTableEmpty(tbodyId, cols, message = 'No records found') {
    const tbody = document.getElementById(tbodyId);
    if (tbody) tbody.innerHTML = `<tr><td colspan="${cols}" class="text-center py-5 text-muted"><i class="bi bi-inbox" style="font-size:36px;display:block;margin-bottom:10px"></i>${message}</td></tr>`;
}

// ===================== Confirm Dialog =====================
function confirmAction(message) {
    return confirm(message);
}

// ===================== Auto-select single elder =====================
/**
 * If a dropdown has only one real option (ignoring the "All/Choose" placeholder),
 * automatically select it and trigger the change event.
 */
function autoSelectIfSingle(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    // Count real options (exclude empty/placeholder values)
    const realOptions = Array.from(sel.options).filter(o => o.value !== '');
    if (realOptions.length === 1) {
        sel.value = realOptions[0].value;
        sel.dispatchEvent(new Event('change'));
    }
}

// ===================== Init =====================
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initUserMenu();
    initLiveClock();
    initBrowserNotifications();
    
    if (TokenManager.isLoggedIn()) {
        loadAlertsBadge();
        setInterval(loadAlertsBadge, 30000); // Every 30 seconds
        startDoseChecker(); // Check for due doses
        loadNextDose(); // Show countdown
    }
});

// ===================== Live Clock =====================
function initLiveClock() {
    const clockEl = document.getElementById('live-clock');
    const dateEl = document.getElementById('live-date');
    if (!clockEl) return;

    function updateClock() {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        if (dateEl) dateEl.textContent = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
    }

    updateClock();
    setInterval(updateClock, 1000);
}

// ===================== Browser Notifications =====================
async function initBrowserNotifications() {
    if (!('Notification' in window)) return;
    
    if (Notification.permission === 'default') {
        const result = await Notification.requestPermission();
        if (result === 'granted') Toast.success('Browser notifications enabled!');
    }
}

function showBrowserNotification(title, body, icon = '/static/logo.png') {
    if (Notification.permission === 'granted') {
        new Notification(title, { body, icon, badge: icon });
    }
}

// ===================== Dose Checker (Real-Time) =====================
let lastCheckedMinute = null;

function startDoseChecker() {
    checkDueDoses(); // Check immediately
    setInterval(checkDueDoses, 60000); // Check every minute
}

async function checkDueDoses() {
    try {
        const now = new Date();
        const currentMinute = now.getHours() * 60 + now.getMinutes();
        
        if (currentMinute === lastCheckedMinute) return;
        lastCheckedMinute = currentMinute;

        const data = await API.get('/dashboard/upcoming-doses?minutes=5');
        if (!data || !data._ok || !data.doses.length) return;

        data.doses.forEach(dose => {
            const doseTime = dose.scheduled_time.substring(0, 5); // HH:MM
            const nowTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
            
            if (doseTime === nowTime) {
                showBrowserNotification(
                    'Medication Reminder',
                    `Time for ${dose.elder_name} to take ${dose.medicine_name} ${dose.medicine_dosage}`,
                    '/static/logo.png'
                );
                Toast.warning(`⏰ ${dose.elder_name}: Take ${dose.medicine_name} now!`);
            }
        });
    } catch (e) {
        console.error('Dose checker error:', e);
    }
}

// ===================== Next Dose Countdown =====================
async function loadNextDose() {
    try {
        const data = await API.get('/dashboard/next-dose');
        if (!data || !data._ok || !data.next_dose) return;

        const nextDose = data.next_dose;
        const countdownEl = document.getElementById('next-dose-countdown');
        if (!countdownEl) return;

        updateCountdown(nextDose, countdownEl);
        setInterval(() => updateCountdown(nextDose, countdownEl), 1000);
    } catch (e) {}
}

function updateCountdown(doseInfo, element) {
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const doseTime = new Date(`${today}T${doseInfo.scheduled_time}`);
    const diff = doseTime - now;

    if (diff < 0) {
        element.innerHTML = `<span class="text-danger fw-700">OVERDUE</span> — ${doseInfo.medicine_name} for ${doseInfo.elder_name}`;
        element.classList.add('overdue-alert');
        return;
    }

    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);

    if (minutes < 5) {
        element.innerHTML = `<span class="text-warning fw-700">⏰ ${minutes}m ${seconds}s</span> — ${doseInfo.medicine_name} for ${doseInfo.elder_name}`;
        element.classList.add('urgent-dose');
    } else if (minutes < 30) {
        element.innerHTML = `<span class="text-info fw-700">${minutes} min</span> — ${doseInfo.medicine_name} for ${doseInfo.elder_name}`;
    } else {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        element.innerHTML = `<span class="text-muted">${hours}h ${mins}m</span> — ${doseInfo.medicine_name} for ${doseInfo.elder_name}`;
    }
}

// ===================== Inline Alerts Dropdown =====================
async function toggleAlertsDropdown() {
    const dropdown = document.getElementById('alerts-dropdown');
    const isVisible = dropdown.style.display === 'block';
    
    dropdown.style.display = isVisible ? 'none' : 'block';
    
    if (!isVisible) {
        await loadAlertsDropdownContent();
    }
    
    // Close on click outside
    document.addEventListener('click', closeDropdownOnClickOutside);
}

function closeDropdownOnClickOutside(e) {
    const dropdown = document.getElementById('alerts-dropdown');
    const btn = document.getElementById('alerts-btn');
    if (!dropdown.contains(e.target) && !btn.contains(e.target)) {
        dropdown.style.display = 'none';
        document.removeEventListener('click', closeDropdownOnClickOutside);
    }
}

async function loadAlertsDropdownContent() {
    const container = document.getElementById('alerts-dropdown-content');
    container.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></div>';

    const data = await API.get('/alerts/unread?limit=10');
    if (!data || !data._ok || !data.alerts.length) {
        container.innerHTML = '<p class="text-center text-muted py-3 mb-0">No new alerts</p>';
        return;
    }

    container.innerHTML = data.alerts.map(alert => `
        <div class="alert-dropdown-item" onclick="markAlertReadInline(${alert.id})">
            <div class="d-flex justify-content-between align-items-start mb-1">
                <strong style="font-size:12px">${alert.alert_type.replace('_', ' ').toUpperCase()}</strong>
                <span class="badge bg-${alert.severity === 'critical' ? 'danger' : alert.severity === 'high' ? 'warning' : 'info'} badge-sm">${alert.severity}</span>
            </div>
            <p class="mb-1" style="font-size:13px">${alert.message}</p>
            <small class="text-muted">${Utils.timeAgo(alert.sent_at)}</small>
        </div>
    `).join('');
}

async function markAlertReadInline(alertId) {
    await API.put(`/alerts/${alertId}/read`);
    await loadAlertsDropdownContent();
    await loadAlertsBadge();
}

async function markAllAlertsReadInline() {
    await API.put('/alerts/mark-all-read');
    Toast.success('All alerts marked as read');
    await loadAlertsDropdownContent();
    await loadAlertsBadge();
}

/* =============================================
   MOBILE RESPONSIVENESS MANAGER
   ============================================= */

const ResponsiveManager = {
    isMobile: () => window.innerWidth <= 768,
    isTablet: () => window.innerWidth > 768 && window.innerWidth <= 1024,
    isDesktop: () => window.innerWidth > 1024,
    isPortrait: () => window.innerHeight > window.innerWidth,
    isLandscape: () => window.innerHeight <= window.innerWidth,
    
    init() {
        this.setupViewportHandling();
        this.setupOrientationHandling();
        this.setupTouchHandling();
        this.setupSidebarMobileClose();
        this.adjustLayoutForDevice();
    },
    
    setupViewportHandling() {
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.adjustLayoutForDevice();
                const sidebar = document.getElementById('sidebar');
                if (sidebar && this.isDesktop()) {
                    sidebar.classList.remove('mobile-open');
                }
            }, 250);
        });
    },
    
    setupOrientationHandling() {
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.adjustLayoutForDevice();
                const sidebar = document.getElementById('sidebar');
                if (sidebar && this.isMobile()) {
                    sidebar.classList.remove('mobile-open');
                }
                // Adjust viewport to avoid address bar issues
                window.scrollTo(0, 0);
            }, 100);
        });
    },
    
    setupTouchHandling() {
        // Enhance touch event handling for better UX
        if (window.innerWidth <= 768) {
            document.documentElement.addEventListener('touchstart', (e) => {
                if (e.target.closest('button, a, input, select, textarea')) {
                    e.target.closest('button, a, input, select, textarea').style.opacity = '0.8';
                }
            });
            
            document.documentElement.addEventListener('touchend', (e) => {
                if (e.target.closest('button, a, input, select, textarea')) {
                    e.target.closest('button, a, input, select, textarea').style.opacity = '1';
                }
            });
        }
    },
    
    setupSidebarMobileClose() {
        const sidebar = document.getElementById('sidebar');
        const content = document.getElementById('content');
        
        if (!sidebar || !content) return;
        
        // Close sidebar when clicking on a nav link on mobile
        sidebar.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (this.isMobile()) {
                    sidebar.classList.remove('mobile-open');
                }
            });
        });
        
        // Close sidebar when clicking outside on mobile
        if (this.isMobile()) {
            content.addEventListener('click', () => {
                if (sidebar.classList.contains('mobile-open')) {
                    sidebar.classList.remove('mobile-open');
                }
            });
        }
    },
    
    adjustLayoutForDevice() {
        const sidebar = document.getElementById('sidebar');
        const content = document.getElementById('content');
        const body = document.body;
        
        if (!sidebar || !content) return;
        
        if (this.isMobile()) {
            // Mobile layout
            body.classList.add('is-mobile');
            body.classList.remove('is-desktop', 'is-tablet');
            sidebar.classList.remove('collapsed');
            content.classList.remove('expanded');
        } else if (this.isTablet()) {
            // Tablet layout
            body.classList.add('is-tablet');
            body.classList.remove('is-mobile', 'is-desktop');
        } else {
            // Desktop layout
            body.classList.add('is-desktop');
            body.classList.remove('is-mobile', 'is-tablet');
        }
    }
};

// Initialize responsive manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ResponsiveManager.init();
});

/* =============================================
   MOBILE VIEWPORT UTILITIES
   ============================================= */

// Get safe area insets for notched devices (iPhone X, etc)
const SafeAreaManager = {
    init() {
        const style = document.createElement('style');
        style.textContent = `
            :root {
                --safe-area-inset-top: ${window.safeAreaInsets?.top || 0}px;
                --safe-area-inset-right: ${window.safeAreaInsets?.right || 0}px;
                --safe-area-inset-bottom: ${window.safeAreaInsets?.bottom || 0}px;
                --safe-area-inset-left: ${window.safeAreaInsets?.left || 0}px;
            }
            
            @supports (padding: max(0px)) {
                body { padding-left: max(16px, var(--safe-area-inset-left)); }
                .sidebar { padding-right: max(0px, var(--safe-area-inset-left)); }
                .top-navbar { padding-right: max(16px, var(--safe-area-inset-right)); }
            }
        `;
        document.head.appendChild(style);
    }
};

if (typeof window.safeAreaInsets !== 'undefined') {
    SafeAreaManager.init();
}

/* =============================================
   MOBILE PERFORMANCE OPTIMIZATIONS
   ============================================= */

const PerformanceOptimizer = {
    disableTransitionsOnMobile() {
        if (window.innerWidth <= 768) {
            const style = document.createElement('style');
            style.textContent = `
                @media (max-width: 768px) {
                    * { transition-duration: 0.1s !important; }
                }
            `;
            document.head.appendChild(style);
        }
    },
    
    optimizeImages() {
        if (this.isMobile()) {
            const images = document.querySelectorAll('img[data-src-mobile]');
            images.forEach(img => {
                img.src = img.dataset.srcMobile;
            });
        }
    },
    
    isMobile() { return window.innerWidth <= 768; }
};

// Optimize on load
document.addEventListener('DOMContentLoaded', () => {
    PerformanceOptimizer.disableTransitionsOnMobile();
    PerformanceOptimizer.optimizeImages();
});

/* =============================================
   MOBILE FORM ENHANCEMENTS
   ============================================= */

const MobileFormEnhancements = {
    init() {
        this.enhanceInputs();
        this.improveFormUX();
    },
    
    enhanceInputs() {
        // Prevent zoom on input focus for iOS
        const inputs = document.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            // Set proper input type for better mobile keyboard
            if (input.type === 'text' && input.name.includes('email')) {
                input.type = 'email';
                input.inputMode = 'email';
            }
            if (input.name.includes('phone')) {
                input.type = 'tel';
                input.inputMode = 'tel';
            }
            if (input.name.includes('number')) {
                input.type = 'number';
                input.inputMode = 'numeric';
            }
            
            // Ensure font size is 16px to prevent zoom
            input.style.fontSize = '16px';
        });
    },
    
    improveFormUX() {
        // Add better mobile form handling
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            // Add action on form submission for mobile
            form.addEventListener('submit', () => {
                // Blur active input to hide keyboard
                document.activeElement?.blur();
            });
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (window.innerWidth <= 768) {
        MobileFormEnhancements.init();
    }
});

/* =============================================
   MOBILE MENU SWIPE HANDLING
   ============================================= */

const SwipeManager = {
    startX: 0,
    endX: 0,
    
    init() {
        if (window.innerWidth <= 768) {
            document.addEventListener('touchstart', (e) => this.handleTouchStart(e), false);
            document.addEventListener('touchend', (e) => this.handleTouchEnd(e), false);
        }
    },
    
    handleTouchStart(e) {
        this.startX = e.changedTouches[0].screenX;
    },
    
    handleTouchEnd(e) {
        this.endX = e.changedTouches[0].screenX;
        this.detectSwipe();
    },
    
    detectSwipe() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;
        
        const diff = this.startX - this.endX;
        const threshold = 50;
        
        // Swipe left (open sidebar)
        if (diff < -threshold && window.innerWidth <= 768) {
            sidebar.classList.add('mobile-open');
        }
        
        // Swipe right (close sidebar)
        if (diff > threshold && sidebar.classList.contains('mobile-open')) {
            sidebar.classList.remove('mobile-open');
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    SwipeManager.init();
});

/* =============================================
   MOBILE BOTTOM SHEET HANDLING
   ============================================= */

function openMobileBottomSheet(title, content) {
    if (window.innerWidth <= 768) {
        const sheet = document.createElement('div');
        sheet.className = 'mobile-bottom-sheet show';
        sheet.innerHTML = `
            <div class="mobile-bottom-sheet-header">
                <h6>${title}</h6>
                <button onclick="this.closest('.mobile-bottom-sheet').remove()" class="btn-close"></button>
            </div>
            <div class="mobile-bottom-sheet-body">
                ${content}
            </div>
        `;
        document.body.appendChild(sheet);
        
        // Close on backdrop click
        sheet.addEventListener('click', (e) => {
            if (e.target === sheet) sheet.remove();
        });
    }
}

/* =============================================
   INITIALIZE ALL MOBILE ENHANCEMENTS ON PAGE LOAD
   ============================================= */

document.addEventListener('DOMContentLoaded', () => {
    // Ensure sidebar is properly initialized
    if (document.getElementById('sidebar')) {
        initSidebar();
    }
});
