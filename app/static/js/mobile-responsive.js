/**
 * Mobile Responsive Manager
 * Handles responsive behavior, viewport adjustments, and mobile-specific enhancements
 * For: AI-Powered Elderly Healthcare System
 */

// =====================================================
// DEVICE DETECTION & VIEWPORT MANAGER
// =====================================================

const DeviceDetector = {
    isIOS: () => /iPad|iPhone|iPod/.test(navigator.userAgent),
    isAndroid: () => /Android/.test(navigator.userAgent),
    isMobile: () => window.innerWidth <= 768,
    isTablet: () => window.innerWidth > 768 && window.innerWidth <= 1024,
    isDesktop: () => window.innerWidth > 1024,
    isPortrait: () => window.matchMedia('(orientation: portrait)').matches,
    isLandscape: () => window.matchMedia('(orientation: landscape)').matches,
    isSmallPhone: () => window.innerWidth <= 480,
    isMediumPhone: () => window.innerWidth > 480 && window.innerWidth <= 640,
    isLargePhone: () => window.innerWidth > 640 && window.innerWidth <= 768,
    
    getViewport() {
        return {
            width: window.innerWidth,
            height: window.innerHeight,
            isMobile: this.isMobile(),
            isTablet: this.isTablet(),
            isDesktop: this.isDesktop(),
            isPortrait: this.isPortrait(),
            isLandscape: this.isLandscape(),
            deviceType: this.isDesktop() ? 'desktop' : this.isTablet() ? 'tablet' : 'mobile',
            osType: this.isIOS() ? 'iOS' : this.isAndroid() ? 'Android' : 'other'
        };
    }
};

// =====================================================
// VIEWPORT META TAG MANAGER
// =====================================================

const ViewportManager = {
    init() {
        // Ensure proper viewport meta tag
        let viewportMeta = document.querySelector('meta[name="viewport"]');
        if (!viewportMeta) {
            viewportMeta = document.createElement('meta');
            viewportMeta.name = 'viewport';
            viewportMeta.content = 'width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=5.0, user-scalable=1';
            document.head.appendChild(viewportMeta);
        } else {
            viewportMeta.content = 'width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=5.0, user-scalable=1';
        }
        
        // Add iOS specific meta tags
        if (DeviceDetector.isIOS()) {
            this.addMetaTag('apple-mobile-web-app-capable', 'yes');
            this.addMetaTag('apple-mobile-web-app-status-bar-style', 'black-translucent');
            this.addMetaTag('apple-mobile-web-app-title', 'Elderly Care');
        }
    },
    
    addMetaTag(name, content) {
        let meta = document.querySelector(`meta[name="${name}"]`);
        if (!meta) {
            meta = document.createElement('meta');
            meta.name = name;
            meta.content = content;
            document.head.appendChild(meta);
        } else {
            meta.content = content;
        }
    }
};

// =====================================================
// RESPONSIVE LAYOUT MANAGER
// =====================================================

const ResponsiveLayoutManager = {
    currentBreakpoint: null,
    
    init() {
        this.updateBreakpoint();
        window.addEventListener('resize', () => this.updateBreakpoint());
        this.applyResponsiveClasses();
    },
    
    updateBreakpoint() {
        const viewport = DeviceDetector.getViewport();
        const oldBreakpoint = this.currentBreakpoint;
        
        if (viewport.width <= 480) {
            this.currentBreakpoint = 'xs';
        } else if (viewport.width <= 640) {
            this.currentBreakpoint = 'sm';
        } else if (viewport.width <= 768) {
            this.currentBreakpoint = 'md';
        } else if (viewport.width <= 1024) {
            this.currentBreakpoint = 'lg';
        } else {
            this.currentBreakpoint = 'xl';
        }
        
        if (oldBreakpoint !== this.currentBreakpoint) {
            this.applyResponsiveClasses();
            window.dispatchEvent(new CustomEvent('breakpointChange', {
                detail: { breakpoint: this.currentBreakpoint, viewport }
            }));
        }
    },
    
    applyResponsiveClasses() {
        const html = document.documentElement;
        html.classList.remove('bp-xs', 'bp-sm', 'bp-md', 'bp-lg', 'bp-xl');
        html.classList.add(`bp-${this.currentBreakpoint}`);
        
        const viewport = DeviceDetector.getViewport();
        html.classList.toggle('is-mobile', viewport.isMobile);
        html.classList.toggle('is-tablet', viewport.isTablet);
        html.classList.toggle('is-desktop', viewport.isDesktop);
        html.classList.toggle('is-portrait', viewport.isPortrait);
        html.classList.toggle('is-landscape', viewport.isLandscape);
    }
};

// =====================================================
// MOBILE SIDEBAR MANAGER
// =====================================================

const MobileSidebarManager = {
    sidebar: null,
    overlay: null,
    
    init() {
        this.sidebar = document.getElementById('sidebar');
        if (!this.sidebar) return;
        
        this.createOverlay();
        this.setupEventListeners();
        this.closeOnNavClick();
        this.handleEscape();
    },
    
    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'sidebar-mobile-overlay';
        this.overlay.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1049;
            display: none;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(this.overlay);
        
        this.overlay.addEventListener('click', () => this.close());
    },
    
    setupEventListeners() {
        const toggle = document.getElementById('sidebar-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => this.toggle());
        }
        
        window.addEventListener('resize', () => {
            if (DeviceDetector.isDesktop()) {
                this.close();
            }
        });
    },
    
    closeOnNavClick() {
        if (!this.sidebar) return;
        this.sidebar.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (DeviceDetector.isMobile()) {
                    this.close();
                }
            });
        });
    },
    
    handleEscape() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.sidebar?.classList.contains('mobile-open')) {
                this.close();
            }
        });
    },
    
    toggle() {
        if (!this.sidebar) return;
        this.sidebar.classList.contains('mobile-open') ? this.close() : this.open();
    },
    
    open() {
        if (!this.sidebar) return;
        this.sidebar.classList.add('mobile-open');
        this.overlay.style.display = 'block';
        setTimeout(() => this.overlay.style.opacity = '1', 10);
        document.body.style.overflow = 'hidden';
    },
    
    close() {
        if (!this.sidebar) return;
        this.sidebar.classList.remove('mobile-open');
        this.overlay.style.opacity = '0';
        setTimeout(() => this.overlay.style.display = 'none', 300);
        document.body.style.overflow = '';
    }
};

// =====================================================
// TOUCH GESTURE MANAGER
// =====================================================

const TouchGestureManager = {
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
    minSwipeDistance: 50,
    
    init() {
        if (!DeviceDetector.isMobile()) return;
        
        document.addEventListener('touchstart', (e) => this.onTouchStart(e), false);
        document.addEventListener('touchend', (e) => this.onTouchEnd(e), false);
    },
    
    onTouchStart(e) {
        this.startX = e.changedTouches[0].screenX;
        this.startY = e.changedTouches[0].screenY;
    },
    
    onTouchEnd(e) {
        this.endX = e.changedTouches[0].screenX;
        this.endY = e.changedTouches[0].screenY;
        this.detectGesture();
    },
    
    detectGesture() {
        const diffX = this.startX - this.endX;
        const diffY = this.startY - this.endY;
        
        // Swipe left (open sidebar if not already open)
        if (diffX < -this.minSwipeDistance && Math.abs(diffY) < 50) {
            if (DeviceDetector.isMobile() && !MobileSidebarManager.sidebar?.classList.contains('mobile-open')) {
                MobileSidebarManager.open();
            }
        }
        
        // Swipe right (close sidebar)
        if (diffX > this.minSwipeDistance && Math.abs(diffY) < 50) {
            if (MobileSidebarManager.sidebar?.classList.contains('mobile-open')) {
                MobileSidebarManager.close();
            }
        }
    }
};

// =====================================================
// MOBILE FORM ENHANCEMENTS
// =====================================================

const MobileFormManager = {
    init() {
        if (!DeviceDetector.isMobile()) return;
        
        this.enhanceInputs();
        this.improveKeyboardBehavior();
    },
    
    enhanceInputs() {
        document.querySelectorAll('input, textarea, select').forEach(input => {
            // Set correct input types for better mobile keyboards
            if (input.type === 'text') {
                if (input.name.includes('email')) input.type = 'email';
                else if (input.name.includes('phone') || input.name.includes('tel')) input.type = 'tel';
                else if (input.name.includes('number')) input.type = 'number';
                else if (input.name.includes('url') || input.name.includes('website')) input.type = 'url';
            }
            
            // Ensure font size is 16px to prevent iOS zoom
            input.style.fontSize = '16px';
            
            // Add padding for better touch targets
            if (input.classList && !input.classList.contains('form-control')) {
                input.style.minHeight = '44px';
            }
        });
    },
    
    improveKeyboardBehavior() {
        // Blur input on Enter to close keyboard
        document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"]').forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    input.blur();
                }
            });
        });
        
        // Adjust scroll position when keyboard appears/disappears
        document.querySelectorAll('input, textarea, select').forEach(input => {
            input.addEventListener('focus', () => {
                setTimeout(() => {
                    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 300);
            });
        });
    }
};

// =====================================================
// MOBILE BOTTOM SHEET COMPONENT
// =====================================================

const MobileBottomSheet = {
    create(options = {}) {
        const { title, content, onClose } = options;
        
        const backdrop = document.createElement('div');
        backdrop.className = 'mobile-bottom-sheet-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1060;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        const sheet = document.createElement('div');
        sheet.className = 'mobile-bottom-sheet';
        sheet.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            border-radius: 16px 16px 0 0;
            z-index: 1061;
            transform: translateY(100%);
            transition: transform 0.3s ease;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
        `;
        
        const header = document.createElement('div');
        header.className = 'mobile-bottom-sheet-header';
        header.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
            border-bottom: 1px solid #e2e8f0;
            flex-shrink: 0;
        `;
        header.innerHTML = `
            <h6 style="margin: 0; font-weight: 600;">${title || 'Options'}</h6>
            <button type="button" class="btn-close" style="flex-shrink: 0;"></button>
        `;
        
        const body = document.createElement('div');
        body.className = 'mobile-bottom-sheet-body';
        body.style.cssText = `
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            flex: 1;
            padding: 16px;
        `;
        body.innerHTML = content || '';
        
        sheet.appendChild(header);
        sheet.appendChild(body);
        document.body.appendChild(backdrop);
        document.body.appendChild(sheet);
        
        const closeBtn = header.querySelector('.btn-close');
        const close = () => {
            sheet.style.transform = 'translateY(100%)';
            backdrop.style.opacity = '0';
            setTimeout(() => {
                sheet.remove();
                backdrop.remove();
                document.body.style.overflow = '';
                if (onClose) onClose();
            }, 300);
        };
        
        closeBtn.addEventListener('click', close);
        backdrop.addEventListener('click', close);
        
        setTimeout(() => {
            backdrop.style.opacity = '1';
            sheet.style.transform = 'translateY(0)';
        }, 10);
        
        document.body.style.overflow = 'hidden';
        
        return { sheet, backdrop, close };
    }
};

// =====================================================
// MOBILE PERFORMANCE OPTIMIZER
// =====================================================

const MobilePerformanceOptimizer = {
    init() {
        if (!DeviceDetector.isMobile()) return;
        
        this.optimizeScrolling();
        this.optimizeAnimations();
        this.lazyLoadImages();
    },
    
    optimizeScrolling() {
        document.querySelectorAll('.sidebar, .table-responsive, .chat-messages').forEach(el => {
            el.style.webkitOverflowScrolling = 'touch';
        });
    },
    
    optimizeAnimations() {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.documentElement.style.setProperty('--transition', '0.01ms');
        }
    },
    
    lazyLoadImages() {
        const images = document.querySelectorAll('img[data-src]');
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                });
            });
            images.forEach(img => imageObserver.observe(img));
        }
    }
};

// =====================================================
// SAFE AREA INSETS (For Notched Devices)
// =====================================================

const SafeAreaManager = {
    init() {
        if (!DeviceDetector.isIOS()) return;
        
        const getCSSVariable = (varName) => {
            return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '0px';
        };
        
        const style = document.createElement('style');
        style.textContent = `
            @supports (padding: max(0px)) {
                body {
                    padding-left: max(16px, env(safe-area-inset-left));
                    padding-right: max(16px, env(safe-area-inset-right));
                }
                
                .sidebar {
                    padding-left: env(safe-area-inset-left);
                }
                
                .top-navbar {
                    padding-right: max(16px, env(safe-area-inset-right));
                }
            }
        `;
        document.head.appendChild(style);
    }
};

// =====================================================
// MOBILE STATUS BAR MANAGER (PWA)
// =====================================================

const StatusBarManager = {
    init() {
        if (!DeviceDetector.isIOS()) return;
        
        // Set theme color
        let themeColor = document.querySelector('meta[name="theme-color"]');
        if (themeColor) {
            themeColor.content = '#1976d2';
        }
    }
};

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize all mobile managers
    ViewportManager.init();
    ResponsiveLayoutManager.init();
    MobileSidebarManager.init();
    TouchGestureManager.init();
    MobileFormManager.init();
    MobilePerformanceOptimizer.init();
    SafeAreaManager.init();
    StatusBarManager.init();
});

// Export for global access
window.MobileManager = {
    DeviceDetector,
    ViewportManager,
    ResponsiveLayoutManager,
    MobileSidebarManager,
    TouchGestureManager,
    MobileBottomSheet
};
