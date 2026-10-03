/* ============================================================
   guard.js — NeuralOrbit Route Guard
   Runs on every module page. Verifies auth + role.
   If invalid: redirects to login.
   If valid: sets CURRENT_MODULE / CURRENT_ROLE then calls initShell().
   ============================================================ */

(function () {
    'use strict';

    const USER_MODULES = new Set([
        'neural-orbit', 'crm', 'marketing', 'shield', 'website', 'integrations',
    ]);

    function run() {
        const session = window.NOAuth?.getSession?.();
        const root = window.NOAuth?.getRootPath?.() || '../';

        // Not logged in → back to login
        if (!session) {
            window.location.href = root + 'index.html';
            return;
        }

        const pageRole = document.body.dataset.role || 'user';
        const pageModule = document.body.dataset.module || 'neural-orbit';

        // Role mismatch → redirect to user's correct area
        if (session.role !== pageRole) {
            const dest = session.role === 'admin'
                ? root + 'admin/neural-orbit.html'
                : root + 'user/neural-orbit.html';
            window.location.href = dest;
            return;
        }

        // Admin-only pages → non-admin redirect
        if (session.role !== 'admin' && !USER_MODULES.has(pageModule)) {
            window.location.href = root + 'user/neural-orbit.html';
            return;
        }

        // ── Auth passed ─────────────────────────────────────────
        window.CURRENT_MODULE = pageModule;
        window.CURRENT_ROLE = session.role;
        window.CURRENT_USER = session;

        // IMPORTANT: shell.js is loaded AFTER guard.js in the HTML.
        // We must wait for DOMContentLoaded so all scripts are ready
        // before calling initShell.
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function () {
                window.initShell?.();
            });
        } else {
            // DOM already loaded (shouldn't normally happen, but safe)
            window.initShell?.();
        }
    }

    // Run immediately — auth check is synchronous (localStorage)
    run();

})();
