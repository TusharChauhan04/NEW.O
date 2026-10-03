/* ============================================================
   auth.js — NeuralOrbit Authentication Layer
   Handles login, logout, session persistence.
   Uses real Supabase if configured, else mock auth.
   ============================================================ */

(function () {
    'use strict';

    const SESSION_KEY = 'no_session';

    /* -------------------------------------------------------
       SESSION HELPERS
    ------------------------------------------------------- */
    function saveSession(email, role, name) {
        const session = { email, role, name, ts: Date.now() };
        try { localStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch (e) { }
    }

    function clearSession() {
        try { localStorage.removeItem(SESSION_KEY); } catch (e) { }
    }

    function getSession() {
        try {
            const raw = localStorage.getItem(SESSION_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            // 8 hour session TTL
            if (Date.now() - parsed.ts > 8 * 60 * 60 * 1000) { clearSession(); return null; }
            return parsed;
        } catch (e) { return null; }
    }

    /* -------------------------------------------------------
       LOGIN — Supabase real auth or mock fallback
    ------------------------------------------------------- */
    async function signIn(email, password) {
        const em = (email || '').trim().toLowerCase();

        // 1. Try real Supabase first
        if (window.SUPABASE_READY && window.supabaseClient) {
            try {
                const { data, error } = await window.supabaseClient.auth.signInWithPassword({ email: em, password });

                if (!error && data?.user) {
                    const accessToken = data.session?.access_token;

                    // Store JWT token immediately for backend calls
                    if (accessToken) {
                        localStorage.setItem('neuralorbit_token', accessToken);
                    }

                    // ── Fetch real role from profiles table (source of truth) ──
                    // user_metadata.role is only set at signup and never updates.
                    // The profiles table is where we control roles via SQL.
                    let role = data.user.user_metadata?.role || 'user';
                    const name = data.user.user_metadata?.name || data.user.email;

                    try {
                        const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';
                        const profileRes = await fetch(BACKEND + '/api/v1/profile', {
                            signal: AbortSignal.timeout(4000),
                            headers: {
                                'Content-Type': 'application/json',
                                ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
                            },
                        });
                        if (profileRes.ok) {
                            const profileData = await profileRes.json();
                            const dbRole = profileData?.profile?.role;
                            if (dbRole === 'admin' || dbRole === 'user') {
                                role = dbRole;  // ✅ Use DB role (authoritative)
                            }
                        }
                    } catch (profileErr) {
                        console.warn('[Auth] Could not fetch profile role — using metadata role:', profileErr?.message);
                    }

                    saveSession(em, role, name);
                    return { ok: true, role, name };
                }

                // If it's a real error (not just bad creds), log it
                if (error && error.message !== 'Invalid login credentials') {
                    console.warn('[Auth] Supabase login error:', error.message);
                }
            } catch (err) {
                console.error('[Auth] Connection error:', err);
            }
        }

        // 2. Mock auth fallback (Developer/Demo mode)
        const demo = window.DEMO_CREDENTIALS?.[em];
        if (demo && demo.password === password) {
            console.info('[Auth] Developer demo login:', em);
            saveSession(em, demo.role, demo.name);
            return { ok: true, role: demo.role, name: demo.name };
        }

        return { ok: false, error: 'Invalid email or password.' };
    }

    /* -------------------------------------------------------
       SIGN UP — Supabase real registration
    ------------------------------------------------------- */
    async function signUp(email, password, name, company) {
        const em = (email || '').trim().toLowerCase();

        if (window.SUPABASE_READY && window.supabaseClient) {
            try {
                const { data, error } = await window.supabaseClient.auth.signUp({
                    email: em,
                    password: password,
                    options: {
                        data: {
                            name:    name    || em,
                            company: company || null,
                            role:    'user'
                        }
                    }
                });

                if (error) {
                    // ── Translate technical Supabase errors into user-friendly messages ──
                    const msg = error.message || '';
                    if (msg.toLowerCase().includes('rate limit') || msg.toLowerCase().includes('too many')) {
                        return { ok: false, error: 'Too many sign-up attempts. Please wait 60 seconds and try again.' };
                    }
                    if (msg.toLowerCase().includes('already registered') || msg.toLowerCase().includes('user already exists')) {
                        return { ok: false, error: 'This email is already registered. Please sign in instead.' };
                    }
                    if (msg.toLowerCase().includes('password')) {
                        return { ok: false, error: 'Password must be at least 6 characters long.' };
                    }
                    return { ok: false, error: msg || 'Registration failed. Please try again.' };
                }

                // ── Smart detection: email confirmation disabled (auto login) ──
                // When email confirmation is OFF, Supabase returns a full session immediately.
                if (data?.session && data?.user) {
                    const role = data.user.user_metadata?.role || 'user';
                    const displayName = data.user.user_metadata?.name || em;
                    saveSession(em, role, displayName);
                    console.info('[Auth] Email confirmation disabled — auto-logged in:', em);
                    return { ok: true, autoLogin: true, role, name: displayName };
                }

                // ── Standard: email confirmation required ──
                return {
                    ok: true,
                    message: 'Account created! ✅ Please check your email inbox and click the confirmation link before logging in.'
                };

            } catch (err) {
                console.error('[Auth] Supabase signup error:', err);
                return { ok: false, error: err.message || 'Registration failed.' };
            }
        }

        return { ok: false, error: 'Registration is unavailable (Supabase connection issue).' };
    }

    /* -------------------------------------------------------
       LOGOUT
    ------------------------------------------------------- */
    async function signOut() {
        if (window.SUPABASE_READY && window.supabaseClient) {
            try { await window.supabaseClient.auth.signOut(); } catch (e) { }
        }
        clearSession();
        window.location.href = getRootPath() + 'index.html';
    }

    /* -------------------------------------------------------
       REFRESH ROLE — Re-fetch role from backend without re-login
       Call this after running bootstrap_admin.sql if already logged in.
       Usage: await window.NOAuth.refreshRole()
    ------------------------------------------------------- */
    async function refreshRole() {
        const session = getSession();
        if (!session) return { ok: false, error: 'Not logged in' };

        const token = localStorage.getItem('neuralorbit_token');
        if (!token) return { ok: false, error: 'No bearer token — please log out and log in again' };

        try {
            const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';
            const res = await fetch(BACKEND + '/api/v1/profile', {
                signal: AbortSignal.timeout(5000),
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
            });
            if (!res.ok) return { ok: false, error: `Backend returned ${res.status}` };
            const data = await res.json();
            const newRole = data?.profile?.role;
            if (!newRole) return { ok: false, error: 'No role in profile response' };

            if (newRole !== session.role) {
                // Role changed — update localStorage and reload
                saveSession(session.email, newRole, session.name);
                console.info(`[Auth] Role refreshed: ${session.role} → ${newRole}`);
                return { ok: true, changed: true, role: newRole };
            }
            return { ok: true, changed: false, role: newRole };
        } catch (err) {
            return { ok: false, error: err.message };
        }
    }

    /* -------------------------------------------------------
       GET CURRENT USER
    ------------------------------------------------------- */
    function getCurrentUser() {
        return getSession();
    }

    /* -------------------------------------------------------
       ROOT PATH RESOLVER
       Works whether page is in /admin/, /user/, or root.
    ------------------------------------------------------- */
    function getRootPath() {
        const path = window.location.pathname;
        if (path.includes('/admin/') || path.includes('/user/')) return '../';
        return '';
    }

    /* -------------------------------------------------------
       LOGIN PAGE INIT
    ------------------------------------------------------- */
    function initLoginPage() {
        // If already logged in, redirect
        const session = getSession();
        if (session) {
            const dest = session.role === 'admin' ? 'admin/neural-orbit.html' : 'user/neural-orbit.html';
            window.location.href = dest;
            return;
        }

        // Login UI
        const loginForm = document.getElementById('login-form');
        const loginEmailEl = document.getElementById('login-email');
        const loginPassEl = document.getElementById('login-password');
        const loginBtn = document.getElementById('login-btn');

        // Register UI
        const registerForm = document.getElementById('register-form');
        const registerEmailEl = document.getElementById('register-email');
        const registerPassEl = document.getElementById('register-password');
        const registerNameEl = document.getElementById('register-name');
        const registerBtn = document.getElementById('register-btn');

        // Combined UI error/loading state helper
        const errEl = document.getElementById('auth-error');
        const errMsg = document.getElementById('auth-error-msg');

        function showError(msg) {
            if (errEl) {
                errEl.style.display = 'flex';
                errEl.style.opacity = '1';
                errEl.className = 'auth-status error';
            }
            if (errMsg) errMsg.textContent = msg;
        }

        function showSuccess(msg) {
            if (errEl) {
                errEl.style.display = 'flex';
                errEl.style.opacity = '1';
                errEl.className = 'auth-status success';
            }
            if (errMsg) errMsg.textContent = msg;
        }

        // Login Listener
        if (loginForm) {
            loginForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                const email = loginEmailEl?.value || '';
                const password = loginPassEl?.value || '';

                if (!email || !password) { showError('Please enter both email and password.'); return; }

                if (loginBtn) {
                    loginBtn.disabled = true;
                    loginBtn.innerHTML = '<div class="btn-spinner"></div> Authenticating...';
                }
                if (errEl) errEl.style.display = 'none';

                const result = await signIn(email, password);

                if (result.ok) {
                    if (loginBtn) loginBtn.innerHTML = '<i class="bi bi-check-lg"></i> Welcome!';
                    const dest = result.role === 'admin' ? 'admin/neural-orbit.html' : 'user/neural-orbit.html';
                    setTimeout(() => { window.location.href = dest; }, 400);
                } else {
                    showError(result.error || 'Login failed.');
                    if (loginBtn) {
                        loginBtn.disabled = false;
                        loginBtn.innerHTML = 'Login';
                    }
                }
            });
        }

        // Register Listener
        if (registerForm) {
            registerForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                const email   = registerEmailEl?.value  || '';
                const password = registerPassEl?.value  || '';
                const name    = registerNameEl?.value   || '';
                const company = document.getElementById('register-company')?.value?.trim() || '';

                if (!email || !password) { showError('Please enter email and password.'); return; }

                if (registerBtn) {
                    registerBtn.disabled = true;
                    registerBtn.innerHTML = '<div class="btn-spinner"></div> Creating Account...';
                }
                if (errEl) errEl.style.display = 'none';

                const result = await signUp(email, password, name, company);


                if (result.ok) {
                    // ── Auto-login path: email confirmation is disabled in Supabase ──
                    if (result.autoLogin) {
                        if (registerBtn) registerBtn.innerHTML = '<i class="bi bi-check-lg"></i> Welcome!';
                        showSuccess('Account created! Redirecting to your dashboard...');
                        const dest = result.role === 'admin' ? 'admin/neural-orbit.html' : 'user/neural-orbit.html';
                        setTimeout(() => { window.location.href = dest; }, 800);
                        return;
                    }
                    // ── Standard path: email confirmation required ──
                    showSuccess(result.message || 'Account created! Check your email to confirm.');
                    if (registerBtn) {
                        registerBtn.disabled = false;
                        registerBtn.innerHTML = 'Register';
                    }
                    // Flip back to login panel after 3 seconds
                    setTimeout(() => { if (window.toggleAuth) window.toggleAuth(); }, 3000);
                } else {
                    showError(result.error || 'Registration failed.');
                    if (registerBtn) {
                        registerBtn.disabled = false;
                        registerBtn.innerHTML = 'Register';
                    }
                }
            });
        }
    }

    /* -------------------------------------------------------
       EXPOSE GLOBALLY
    ------------------------------------------------------- */
    window.NOAuth = {
        signIn,
        signUp,
        signOut,
        getCurrentUser,
        getSession,
        getRootPath,
        refreshRole,   // Call after bootstrap_admin.sql to pick up new role without re-login
    };

    // Also expose for login page
    window.initLoginPage = initLoginPage;

})();
