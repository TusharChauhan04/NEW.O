/* ============================================================
   config.js — Runtime environment configuration

   MUST be loaded BEFORE every other NeuralOrbit script. It sets
   window.BACKEND_URL, which every other file reads via the pattern
   `window.BACKEND_URL || '<localhost fallback>'`.

   WHY THIS EXISTS
   The backend URL used to be hardcoded to http://127.0.0.1:8000 in 20+
   places. Deployed anywhere real that meant: (a) the page called the
   *visitor's own machine* instead of the API, and (b) an HTTPS page calling
   http:// was blocked outright as mixed content. There is no build step in
   this project, so there is no bundler to inject an env var — this file is
   the single place that decision lives.

   HOW TO CONFIGURE FOR DEPLOYMENT
   Set PRODUCTION_BACKEND_URL below to your deployed API origin, e.g.
       'https://api.neuralorbit.example.com'
   It MUST be https:// (an https page cannot call http), and it must appear
   in the backend's APP_CORS_ORIGINS.

   Local development needs no change — localhost is detected automatically.
   ============================================================ */

(function () {
    'use strict';

    // ── SET THIS BEFORE DEPLOYING ────────────────────────────────────────
    // Leave as null to fall back to same-origin (correct only if the API is
    // reverse-proxied under the same domain as the frontend).
    var PRODUCTION_BACKEND_URL = null;   // e.g. 'https://api.yourdomain.com'

    var LOCAL_BACKEND_URL = 'http://127.0.0.1:8000';

    function isLocalHost(hostname) {
        return hostname === 'localhost'
            || hostname === '127.0.0.1'
            || hostname === '0.0.0.0'
            || hostname === ''            // file:// has an empty hostname
            || hostname.endsWith('.local');
    }

    function resolveBackendUrl() {
        // 1. An explicit override always wins. Lets you point a deployed page
        //    at a different API from the console without editing this file:
        //      window.__BACKEND_URL__ = 'https://staging-api.example.com'
        if (window.__BACKEND_URL__) return window.__BACKEND_URL__;

        // 2. Local development.
        if (isLocalHost(window.location.hostname)) return LOCAL_BACKEND_URL;

        // 3. Configured production API.
        if (PRODUCTION_BACKEND_URL) return PRODUCTION_BACKEND_URL;

        // 4. Same-origin fallback. Correct only behind a reverse proxy that
        //    routes /api to the backend. Warn loudly, because silently calling
        //    the wrong origin is very hard to debug from the network tab.
        console.warn(
            '[NeuralOrbit] PRODUCTION_BACKEND_URL is not set in js/config.js. ' +
            'Falling back to same-origin (' + window.location.origin + '). ' +
            'If the API is hosted separately, set PRODUCTION_BACKEND_URL.'
        );
        return window.location.origin;
    }

    window.BACKEND_URL = resolveBackendUrl();

    // Guard against the mixed-content failure mode, which otherwise shows up
    // only as an opaque "Failed to fetch" with no explanation.
    if (window.location.protocol === 'https:' &&
        window.BACKEND_URL.indexOf('http://') === 0) {
        console.error(
            '[NeuralOrbit] Mixed content: this page is HTTPS but BACKEND_URL is ' +
            'HTTP (' + window.BACKEND_URL + '). The browser will block every ' +
            'API call. Use an https:// backend URL.'
        );
    }
})();
