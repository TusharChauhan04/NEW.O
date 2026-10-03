/* ============================================================
   app.js — NeuralOrbit App Bootstrap (Module Pages)
   Lightweight entry point for all module pages.
   Most logic lives in shell.js / guard.js / router.js now.
   ============================================================ */

(function () {
    'use strict';

    // Guard runs and calls initShell() after auth check.
    // Router.js fires 'router-ready' event → shell.js handles initial load.
    // This file only handles any final initialization logic.

    // Expose helper for modules.js (legacy compat)
    window.escHtml = window.escHtml || function (str) {
        return String(str || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };

    // Mark app as ready
    document.addEventListener('DOMContentLoaded', function () {
        document.body.classList.add('app-ready');
    });

})();
