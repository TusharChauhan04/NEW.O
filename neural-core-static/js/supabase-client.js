/* ============================================================
   supabase-client.js — NeuralOrbit Supabase Client Init
   Real Supabase connection with mock auth fallback.
   ============================================================ */

(function () {
    'use strict';

    // ── Supabase Configuration ───────────────────────────────
    // Real Supabase project credentials
    const SUPABASE_URL = 'https://mqubjchmdcitprbvbeje.supabase.co';
    // Anon/public key — safe to expose in frontend (Row Level Security protects data)
    // Get from: Supabase Dashboard → Settings → API → Project API Keys → anon public
    const SUPABASE_ANON = window.__SUPABASE_ANON_KEY__ || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1xdWJqY2htZGNpdHByYnZiZWplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4NzUzMDMsImV4cCI6MjA4NzQ1MTMwM30.PcIfKUuqPpPeO1dpvODuP8T_2CtTYpacMmCBs2mPPK4';

    // Backend URL — used by all apiFetch calls in dashboard JS files
    window.BACKEND_URL = window.BACKEND_URL || 'http://127.0.0.1:8000';

    // ── Demo credentials (mock auth fallback) ────────────────
    window.DEMO_CREDENTIALS = {
        'admin@neuralorbit.ai': { password: 'NeuralAdmin@2025', role: 'admin', name: 'Admin User' },
        'user@neuralorbit.ai': { password: 'NeuralUser@2025', role: 'user', name: 'Demo User' },
    };

    // ── Try to init real Supabase client ─────────────────────
    let client = null;

    function initClient() {
        try {
            console.info('[NeuralOrbit] Initializing Supabase client...');

            if (typeof window.supabase !== 'undefined' && window.supabase.createClient) {
                client = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON);

                // ── Token Bridge ────────────────────────────────
                client.auth.onAuthStateChange((_event, session) => {
                    if (session?.access_token) {
                        localStorage.setItem('neuralorbit_token', session.access_token);
                    } else {
                        localStorage.removeItem('neuralorbit_token');
                    }
                });

                window.supabaseClient = client;
                window.SUPABASE_READY = !!client;
                console.info('[NeuralOrbit] ✅ Supabase initialized successfully.');
            } else {
                console.error('[NeuralOrbit] ❌ Supabase library not found in window.');
                // Retry once after 500ms
                setTimeout(initClientOnce, 500);
            }
        } catch (err) {
            console.error('[NeuralOrbit] ❌ Supabase init failed:', err);
        }
    }

    // Single-shot retry wrapper
    let retried = false;
    function initClientOnce() {
        if (!retried) { retried = true; initClient(); }
    }

    // Run first attempt
    initClient();

    // ── CORS Debug Helper ───────────────────────────────────
    fetch(window.BACKEND_URL + '/health', { signal: AbortSignal.timeout(2000) })
        .then(r => r.ok && console.info('[NeuralOrbit] ✅ Backend reachable at', window.BACKEND_URL))
        .catch(() => console.warn('[NeuralOrbit] ⚠️ Backend not reachable — check uvicorn.'));

})();
