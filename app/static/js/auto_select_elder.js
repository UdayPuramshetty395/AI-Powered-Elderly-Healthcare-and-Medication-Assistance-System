/**
 * Auto-Select Elder Utility
 * ==========================
 * Overrides all elder dropdowns so that when only ONE elder exists,
 * it is automatically selected — no manual selection needed.
 * 
 * Loaded ONCE in base.html, works across all pages.
 */

(function() {
    'use strict';

    // Cache the single elder ID once loaded
    let _singleElderId   = null;
    let _singleElderName = null;
    let _loaded = false;

    async function _loadSingleElder() {
        if (_loaded) return;
        _loaded = true;
        try {
            const data = await API.get('/elders?per_page=100');
            if (data && data._ok && data.elders && data.elders.length === 1) {
                _singleElderId   = data.elders[0].id;
                _singleElderName = data.elders[0].name;
            }
        } catch (e) {}
    }

    /**
     * After populating any <select> with elder options,
     * call this to auto-select when only one elder exists.
     */
    window.autoSelectSingleElder = function(selectEl) {
        if (!selectEl) return;
        _loadSingleElder().then(() => {
            if (!_singleElderId) return;
            const options = Array.from(selectEl.options).filter(o => o.value !== '');
            if (options.length === 1 && String(options[0].value) === String(_singleElderId)) {
                selectEl.value = _singleElderId;
                selectEl.dispatchEvent(new Event('change'));
            }
        });
    };

    // MutationObserver: watch for any <select> that gets elder options added
    // and auto-select if only one real option exists.
    const observer = new MutationObserver((mutations) => {
        mutations.forEach(m => {
            if (m.type === 'childList' && m.target.tagName === 'SELECT') {
                const sel = m.target;
                const realOptions = Array.from(sel.options).filter(o => o.value !== '');
                if (realOptions.length === 1 && !sel.value) {
                    sel.value = realOptions[0].value;
                    sel.dispatchEvent(new Event('change'));
                }
            }
        });
    });

    // Start observing once DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, {
            childList:  true,
            subtree:    true,
        });
        _loadSingleElder();
    });

})();
