/* ============================================================
   router.js — NeuralOrbit Hash-Based Tab Router
   Controls tab switching WITHIN a module page.
   Cross-page module navigation is done via href links in shell.js.
   ============================================================ */

(function () {
    'use strict';

    // Admin-only routes that don't use tab navigation
    const ADMIN_ONLY_ROUTES = ['users', 'portfolio', 'analytics', 'alerts'];
    const currentModule = document.body?.dataset?.module || 'crm';

    // Tab routes → page loader function map
    const routes = {
        'overview': () => window.loadOverview?.(),
        'decisions': () => window.loadDecisionLog?.(),
        'reward': () => window.loadRewardEngine?.(),
        'autonomy': () => window.loadAutonomy?.(),
        'learning': () => window.loadLearning?.(),
        'sandbox': () => window.loadSandbox?.(),
        // Design system (legacy)
        'design-system': () => window.loadDesignSystem?.(),
        // Admin-only page loaders
        'users': () => window.loadUsersPage?.(),
        'portfolio': () => window.loadPortfolioPage?.(),
        'analytics': () => window.loadAnalyticsPage?.(),
        'alerts': () => window.loadAlertsPage?.(),
    };

    /**
     * Navigate to a hash route (tab switch within current page)
     */
    function navigate(route) {
        const hash = route.startsWith('#') ? route.slice(1) : route;
        if (window.location.hash === '#' + hash) {
            dispatch(hash);
        } else {
            window.location.hash = hash;
        }
    }

    /**
     * Dispatch a route change — update UI and call page loader
     */
    function dispatch(hash) {
        const route = hash || 'overview';

        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(el => {
            el.classList.toggle('is-active', el.dataset.route === route);
        });

        // Update breadcrumb
        const breadcrumb = document.getElementById('breadcrumb');
        if (breadcrumb) {
            const labels = {
                'overview': moduleLabel(currentModule),
                'decisions': 'Decision Log',
                'reward': 'Reward Engine',
                'autonomy': 'Autonomy Control',
                'learning': 'Learning Timeline',
                'sandbox': 'AI Sandbox',
                'design-system': 'Design System',
                'users': 'User Management',
                'portfolio': 'Business Portfolio',
                'analytics': 'System Analytics',
                'alerts': 'Alert Center',
            };
            breadcrumb.textContent = labels[route] || labels['overview'];
        }

        // Call the page loader if registered
        const loader = routes[route];
        if (loader) {
            loader();
        } else {
            // Default: overview
            routes['overview']?.();
        }
    }

    function moduleLabel(mod) {
        const labels = {
            'neural-orbit': 'NeuralOrbit Dashboard',
            'crm': 'CRM Module',
            'marketing': 'Marketing Module',
            'shield': 'Shield Module',
            'website': 'Website Module',
        };
        return labels[mod] || 'Overview';
    }

    // Listen for hash changes (tab switching)
    window.addEventListener('hashchange', () => {
        const hash = window.location.hash.replace('#', '');
        dispatch(hash);
    });

    // Expose globally
    window.navigate = navigate;
    window._routerDispatch = dispatch;

    // Fire router-ready on DOMContentLoaded so ALL scripts (overview.js,
    // decision-log.js, modules.js, etc.) have had a chance to load and
    // register their listeners before the initial dispatch fires.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            window.dispatchEvent(new Event('router-ready'));
        });
    } else {
        // Fallback: DOM already loaded
        setTimeout(function () {
            window.dispatchEvent(new Event('router-ready'));
        }, 0);
    }

})();
