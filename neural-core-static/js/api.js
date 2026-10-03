/* ============================================================
   api.js — Shared HTTP client for all NeuralOrbit pages

   Load AFTER config.js (needs window.BACKEND_URL) and after auth.js
   (needs window.NOAuth for sign-out on 401).

   WHY THIS EXISTS
   Every page had its own apiFetch — 17+ copies with 21 different timeout
   values (2000ms to 10000ms), and not one of them checked for 401. The
   universal pattern was:

       if (!res.ok) return null;  ...  catch { return null; }

   So an expired Supabase JWT was indistinguishable from a dead backend. Pages
   rendered "BACKEND OFFLINE" — or silently fell back to demo data. An admin
   could sit in front of a dashboard of fabricated numbers believing they were
   live. For an ops tool that is the worst possible failure mode.

   NOApi.fetch distinguishes the cases:
     401/403  -> session is gone: sign out and redirect to login
     other !ok / network error -> returns null, so existing offline handling
                                  and demo fallbacks keep working unchanged
   ============================================================ */

(function () {
    'use strict';

    var DEFAULT_TIMEOUT_MS = 7000;
    var _redirecting = false;   // guard: many parallel calls can 401 at once

    function authHeaders() {
        var token = null;
        try {
            token = localStorage.getItem('neuralorbit_token');
        } catch (e) {
            // Storage can throw in private mode / when site data is blocked.
        }
        return token ? { Authorization: 'Bearer ' + token } : {};
    }

    function handleExpiredSession() {
        if (_redirecting) return;
        _redirecting = true;

        console.warn('[NeuralOrbit] Session expired or unauthorized — signing out.');
        try {
            if (window.NOAuth && typeof window.NOAuth.signOut === 'function') {
                window.NOAuth.signOut();
                return;
            }
        } catch (e) {
            // fall through to the manual redirect below
        }

        // Fallback if NOAuth is unavailable: clear the token and go to login.
        try {
            localStorage.removeItem('neuralorbit_token');
            localStorage.removeItem('no_session');
        } catch (e) { /* ignore */ }

        var root = (window.NOAuth && window.NOAuth.getRootPath)
            ? window.NOAuth.getRootPath()
            : '../';
        window.location.href = root + 'index.html';
    }

    /**
     * Perform an API request.
     * @returns parsed JSON on success, or null on any non-auth failure.
     *          Never returns null for 401/403 — those redirect instead.
     */
    async function apiFetch(path, opts) {
        opts = opts || {};
        var base = window.BACKEND_URL || 'http://127.0.0.1:8000';

        try {
            var res = await fetch(base + path, Object.assign({}, opts, {
                signal: AbortSignal.timeout(opts.timeoutMs || DEFAULT_TIMEOUT_MS),
                headers: Object.assign(
                    { 'Content-Type': 'application/json' },
                    authHeaders(),
                    opts.headers || {}
                ),
            }));

            // The case every previous copy of this function missed.
            if (res.status === 401 || res.status === 403) {
                handleExpiredSession();
                return null;
            }

            if (!res.ok) {
                console.warn('[NeuralOrbit] ' + path + ' -> HTTP ' + res.status);
                return null;
            }

            return await res.json();
        } catch (err) {
            // Timeout or network failure — genuinely "backend unreachable",
            // which is what the callers' offline handling is for.
            return null;
        }
    }

    window.NOApi = {
        fetch:  apiFetch,
        get:    function (path, opts) {
            return apiFetch(path, Object.assign({ method: 'GET' }, opts || {}));
        },
        post:   function (path, body, opts) {
            return apiFetch(path, Object.assign({
                method: 'POST', body: JSON.stringify(body || {}),
            }, opts || {}));
        },
        patch:  function (path, body, opts) {
            return apiFetch(path, Object.assign({
                method: 'PATCH', body: JSON.stringify(body || {}),
            }, opts || {}));
        },
        del:    function (path, opts) {
            return apiFetch(path, Object.assign({ method: 'DELETE' }, opts || {}));
        },
    };
})();
