/* ============================================================
   integrations.js — NeuralOrbit Integration Hub
   Renders the Integration Hub page (L1 Foundation)
   All Levels execute inside this module.
   ============================================================ */

(function () {
    'use strict';

    // Reads the value set by js/config.js. Previously this was hardcoded to
    // localhost with no override, so this file alone broke on any deployment
    // even after every other file was made configurable.
    const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';
    const INT_COLOR = '#06B6D4';

    /* ── Platform Registry ───────────────────────────────────── */
    const PLATFORMS = {
        crm: {
            label: 'CRM',
            icon: 'bi-people-fill',
            color: '#22C55E',
            items: [
                { key: 'zoho', name: 'Zoho CRM', icon: 'bi-briefcase-fill', oauth: true, level: 'L2' },
                { key: 'hubspot', name: 'HubSpot', icon: 'bi-building-fill', oauth: true, level: 'L2' },
                { key: 'salesforce', name: 'Salesforce', icon: 'bi-cloud-fill', oauth: true, level: 'L2' },
                { key: 'custom', name: 'Custom CRM', icon: 'bi-gear-wide-connected', oauth: false, level: 'L1', badge: 'AVAILABLE NOW', connectMode: 'custom' },
            ],
        },
        marketing: {
            label: 'Marketing',
            icon: 'bi-megaphone-fill',
            color: '#8B5CF6',
            items: [
                { key: 'meta_ads', name: 'Meta Ads', icon: 'bi-facebook', oauth: true, level: 'L3' },
                { key: 'google_ads', name: 'Google Ads', icon: 'bi-google', oauth: true, level: 'L3' },
            ],
        },
        website: {
            label: 'Website',
            icon: 'bi-globe',
            color: '#EF4444',
            items: [
                { key: 'no_tracker', name: 'NeuralOrbit Tracker', icon: 'bi-code-slash', oauth: false, level: 'L4', badge: 'AVAILABLE NOW', connectMode: 'tracker' },
            ],
        },
        shield: {
            label: 'Shield',
            icon: 'bi-shield-fill',
            color: '#F59E0B',
            items: [
                { key: 'webhook', name: 'Custom Webhook', icon: 'bi-lightning-fill', oauth: false, level: 'L1', badge: 'AVAILABLE NOW', connectMode: 'webhook' },
            ],
        },
    };

    /* ── State ───────────────────────────────────────────────── */
    let _connections = [];  // loaded from backend

    /* ── API Helpers ─────────────────────────────────────────── */
    // All fetch calls have a 4-second timeout so the hub never hangs
    function fetchWithTimeout(url, options = {}, timeoutMs = 4000) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        return fetch(url, { ...options, signal: controller.signal })
            .finally(() => clearTimeout(timer));
    }

    async function apiGet(path) {
        try {
            const r = await fetchWithTimeout(`${BACKEND}${path}`);
            if (!r.ok) return null;
            return r.json();
        } catch { return null; }
    }

    async function apiPost(path, body) {
        try {
            const r = await fetchWithTimeout(`${BACKEND}${path}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!r.ok) return null;
            return r.json();
        } catch { return null; }
    }

    async function apiDelete(path) {
        try {
            const r = await fetchWithTimeout(`${BACKEND}${path}`, { method: 'DELETE' });
            return r.ok;
        } catch { return false; }
    }

    /* ── Load Connections from Backend ───────────────────────── */
    async function loadConnections() {
        const data = await apiGet('/api/v1/integrations');
        _connections = data?.integrations || [];
    }

    function getConnection(module, platform) {
        return _connections.find(c => c.module === module && c.platform === platform);
    }

    /* ── Render Hub ──────────────────────────────────────────── */
    function renderHub() {
        const el = document.getElementById('page-content');
        if (!el) return;

        const totalActive = _connections.filter(c => c.status === 'active').length;
        const totalAll = Object.values(PLATFORMS).reduce((t, m) => t + m.items.length, 0);

        el.innerHTML = `
            <div style="padding: 28px 32px; animation: fadeIn 0.3s ease;">

                <!-- ── Header ─────────────────────────────── -->
                <div style="margin-bottom: 32px;">
                    <div style="display:flex; align-items:center; gap:14px; margin-bottom:10px;">
                        <div style="
                            width:44px; height:44px; border-radius:12px;
                            background: rgba(6,182,212,0.15);
                            border: 1px solid rgba(6,182,212,0.25);
                            display:flex; align-items:center; justify-content:center;
                            color: ${INT_COLOR}; font-size:20px;
                        "><i class="bi bi-plug-fill"></i></div>
                        <div>
                            <h1 style="font-size:22px; font-weight:700; color:var(--text); margin:0;">Integration Hub</h1>
                            <p style="font-size:13px; color:var(--muted); margin:4px 0 0;">Connect your tools. Power your AI.</p>
                        </div>
                        <div style="margin-left:auto; display:flex; gap:10px;">
                            <div style="
                                padding:8px 16px; border-radius:10px;
                                background: rgba(6,182,212,0.08);
                                border: 1px solid rgba(6,182,212,0.15);
                                text-align:center;
                            ">
                                <div style="font-size:22px; font-weight:700; color:${INT_COLOR};">${totalActive}</div>
                                <div style="font-size:11px; color:var(--muted);">Active</div>
                            </div>
                            <div style="
                                padding:8px 16px; border-radius:10px;
                                background: var(--card-bg);
                                border: 1px solid var(--border);
                                text-align:center;
                            ">
                                <div style="font-size:22px; font-weight:700; color:var(--text);">${totalAll}</div>
                                <div style="font-size:11px; color:var(--muted);">Available</div>
                            </div>
                        </div>
                    </div>
                    <p style="font-size:13px; color:var(--dim); line-height:1.6; max-width:700px;">
                        Connect your business platforms so NeuralOrbit can gather live data, score rewards, and execute AI decisions directly in your tools.
                    </p>
                </div>

                <!-- ── Module Sections ────────────────────── -->
                <div style="display:flex; flex-direction:column; gap:24px;">
                    ${Object.entries(PLATFORMS).map(([modKey, mod]) => renderSection(modKey, mod)).join('')}
                </div>

                <!-- ── API Keys Panel ─────────────────────── -->
                <div style="margin-top:0;" id="api-keys-panel">
                    ${renderApiKeysPanel()}
                </div>

                <!-- ── L5 n8n Execution Panel ────────────── -->
                <div style="margin-top:24px;">
                    ${renderN8nPanel()}
                </div>

            </div>
        `;

        // Attach event listeners
        document.querySelectorAll('[data-connect]').forEach(btn => {
            btn.addEventListener('click', () => {
                const mod = btn.dataset.connect;
                const plat = btn.dataset.platform;
                const item = PLATFORMS[mod].items.find(i => i.key === plat);
                if (item) handleConnect(mod, item);
            });
        });

        document.querySelectorAll('[data-disconnect]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.disconnect;
                if (confirm('Disconnect this integration?')) {
                    await apiDelete(`/api/v1/integrations/${id}`);
                    await refresh();
                }
            });
        });

        // ── Sync Now button handler ──────────────────────────────────────
        document.querySelectorAll('[data-sync]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id       = btn.dataset.sync;
                const platform = btn.dataset.platform;
                const origHtml = btn.innerHTML;

                // Show spinner on the button
                btn.disabled  = true;
                btn.innerHTML = '<i class="bi bi-arrow-repeat" style="animation:spin 0.8s linear infinite;display:inline-block;margin-right:4px;"></i>Syncing...';

                try {
                    const token = localStorage.getItem('neuralorbit_token');
                    const headers = { 'Content-Type': 'application/json' };
                    if (token) headers['Authorization'] = `Bearer ${token}`;

                    const resp = await fetchWithTimeout(
                        `${BACKEND}/api/v1/integrations/${id}/sync`,
                        { method: 'POST', headers },
                        20000   // allow up to 20s for a full CRM pull
                    );

                    if (resp.ok) {
                        const result = await resp.json();
                        const count  = result.synced ?? 0;
                        showSyncToast(platform, count);
                        await refresh();   // refresh connection cards with new last_sync_at
                    } else {
                        showSyncToast(platform, -1, 'Sync failed — check backend logs.');
                    }
                } catch (err) {
                    console.error('[Sync] Error:', err);
                    showSyncToast(platform, -1, 'Backend unreachable. Is uvicorn running?');
                } finally {
                    btn.disabled  = false;
                    btn.innerHTML = origHtml;
                }
            });
        });
    }


    function renderSection(modKey, mod) {
        return `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
            ">
                <!-- Section Header -->
                <div style="
                    padding: 16px 24px;
                    border-bottom: 1px solid var(--border);
                    display:flex; align-items:center; gap:10px;
                    background: rgba(255,255,255,0.015);
                ">
                    <div style="
                        width:32px; height:32px; border-radius:8px;
                        background: ${mod.color}18;
                        border: 1px solid ${mod.color}30;
                        display:flex; align-items:center; justify-content:center;
                        color: ${mod.color}; font-size:14px;
                    "><i class="bi ${mod.icon}"></i></div>
                    <span style="font-size:14px; font-weight:600; color:var(--text);">${mod.label}</span>
                    <span style="font-size:11px; color:var(--dim); margin-left:4px;">${mod.items.length} platform${mod.items.length > 1 ? 's' : ''}</span>
                </div>

                <!-- Platform Grid -->
                <div style="
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
                    gap: 1px;
                    background: var(--border);
                ">
                    ${mod.items.map(item => renderPlatformCard(modKey, item, mod.color)).join('')}
                </div>
            </div>
        `;
    }

    function renderPlatformCard(modKey, item, modColor) {
        const conn = getConnection(modKey, item.key);
        const isActive = conn?.status === 'active';

        // Platforms that are fully implemented and can be connected NOW
        const LIVE_OAUTH = ['zoho', 'hubspot', 'meta_ads', 'google_ads'];
        const LIVE_CUSTOM = ['custom', 'no_tracker', 'webhook'];
        const canConnect = LIVE_OAUTH.includes(item.key) || LIVE_CUSTOM.includes(item.key);
        const isOAuth = LIVE_OAUTH.includes(item.key);

        // Badge label
        let badgeLabel = item.badge || null;
        let badgeColor = INT_COLOR;
        let badgeBg = 'rgba(6,182,212,0.12)';
        let badgeBorder = 'rgba(6,182,212,0.2)';
        if (!badgeLabel) {
            if (canConnect) {
                badgeLabel = 'AVAILABLE NOW';
            } else {
                badgeLabel = item.level;
                badgeColor = 'var(--warning)';
                badgeBg = 'rgba(245,158,11,0.1)';
                badgeBorder = 'rgba(245,158,11,0.15)';
            }
        }

        return `
            <div style="
                background: var(--card-bg);
                padding: 20px;
                display:flex; flex-direction:column; gap:12px;
                transition: background 0.15s;
                position: relative;
            "
            onmouseover="this.style.background='rgba(255,255,255,0.03)'"
            onmouseout="this.style.background='var(--card-bg)'">

                <!-- Badge -->
                <div style="
                    position:absolute; top:12px; right:12px;
                    font-size:9px; font-weight:700; letter-spacing:0.08em;
                    padding:2px 8px; border-radius:4px;
                    background: ${badgeBg};
                    color: ${badgeColor};
                    border: 1px solid ${badgeBorder};
                ">${badgeLabel}</div>

                <!-- Icon + Name -->
                <div style="display:flex; align-items:center; gap:12px;">
                    <div style="
                        width:40px; height:40px; border-radius:10px;
                        background: ${isActive ? modColor + '20' : 'rgba(255,255,255,0.04)'};
                        border: 1px solid ${isActive ? modColor + '40' : 'var(--border)'};
                        display:flex; align-items:center; justify-content:center;
                        color: ${isActive ? modColor : 'var(--muted)'}; font-size:18px;
                        transition: all 0.2s;
                    "><i class="bi ${item.icon}"></i></div>
                    <div>
                        <div style="font-size:14px; font-weight:600; color:var(--text);">${item.name}</div>
                        <div style="display:flex; align-items:center; gap:5px; margin-top:3px;">
                            <span style="
                                width:6px; height:6px; border-radius:50%;
                                background: ${isActive ? '#22C55E' : 'var(--dim)'};
                                display:inline-block;
                                ${isActive ? 'box-shadow: 0 0 6px #22C55E80;' : ''}
                            "></span>
                            <span style="font-size:11px; color:${isActive ? '#22C55E' : 'var(--dim)'};">
                                ${isActive ? 'Connected' : 'Not Connected'}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Last Sync -->
                ${isActive && conn?.last_sync_at ? `
                    <div style="font-size:11px; color:var(--dim);">
                        Last sync: ${new Date(conn.last_sync_at).toLocaleString()}
                    </div>
                ` : ''}

                <!-- Action Button -->
                <div style="margin-top:auto;">
                    ${isActive ? `
                        <div style="display:flex; gap:8px; margin-top:4px;">
                            <!-- Sync Now button (only for CRM platforms with active pull) -->
                            <button style="
                                flex:1; padding:7px 10px; border-radius:8px; border:none; cursor:pointer;
                                background: rgba(6,182,212,0.1); color:${INT_COLOR};
                                font-family:var(--font); font-size:12px; font-weight:600;
                                border: 1px solid rgba(6,182,212,0.2); transition: all 0.15s;
                            "
                            data-sync="${conn.id}" data-platform="${item.key}"
                            onmouseover="this.style.background='rgba(6,182,212,0.2)'"
                            onmouseout="this.style.background='rgba(6,182,212,0.1)'">
                                <i class="bi bi-arrow-repeat" style="margin-right:4px;"></i>Sync
                            </button>
                            <!-- Disconnect button -->
                            <button style="
                                flex:1; padding:7px 10px; border-radius:8px; border:none; cursor:pointer;
                                background: rgba(239,68,68,0.1); color:#EF4444;
                                font-family:var(--font); font-size:12px; font-weight:600;
                                border: 1px solid rgba(239,68,68,0.2); transition: all 0.15s;
                            "
                            data-disconnect="${conn.id}"
                            onmouseover="this.style.background='rgba(239,68,68,0.2)'"
                            onmouseout="this.style.background='rgba(239,68,68,0.1)'">
                                <i class="bi bi-x-circle" style="margin-right:4px;"></i>Disconnect
                            </button>
                        </div>
                    ` : canConnect ? `
                        <button style="
                            width:100%; padding:8px 12px; border-radius:8px; border:none; cursor:pointer;
                            background: ${isOAuth
                    ? 'linear-gradient(135deg,rgba(91,140,255,0.15) 0%,rgba(139,92,246,0.15) 100%)'
                    : 'rgba(6,182,212,0.12)'};
                            color: ${isOAuth ? 'var(--accent)' : INT_COLOR};
                            font-family:var(--font); font-size:12px; font-weight:600;
                            border: 1px solid ${isOAuth ? 'rgba(91,140,255,0.3)' : 'rgba(6,182,212,0.25)'};
                            transition: all 0.15s;
                        "
                        data-connect="${modKey}" data-platform="${item.key}"
                        onmouseover="this.style.opacity='0.8'"
                        onmouseout="this.style.opacity='1'">
                            <i class="bi ${isOAuth ? 'bi-box-arrow-up-right' : 'bi-plug'}" style="margin-right:6px;"></i>
                            ${isOAuth ? 'Connect via OAuth' : 'Setup Connection'}
                        </button>
                    ` : `
                        <button style="
                            width:100%; padding:8px 12px; border-radius:8px; border:none;
                            background: rgba(255,255,255,0.03); color:var(--dim);
                            font-family:var(--font); font-size:12px; font-weight:500;
                            border: 1px solid var(--border); cursor:not-allowed;
                        " disabled>
                            <i class="bi bi-clock" style="margin-right:6px;"></i>Coming Soon
                        </button>
                    `}
                </div>
            </div>
        `;
    }

    function renderApiKeysPanel() {
        const keys = _connections.filter(c => c.platform === 'custom' || c.platform === 'webhook');
        return `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
            ">
                <div style="
                    padding: 16px 24px;
                    border-bottom: 1px solid var(--border);
                    display:flex; align-items:center; justify-content:space-between;
                    background: rgba(255,255,255,0.015);
                ">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div style="
                            width:32px; height:32px; border-radius:8px;
                            background: rgba(91,140,255,0.12);
                            border: 1px solid rgba(91,140,255,0.2);
                            display:flex; align-items:center; justify-content:center;
                            color:var(--accent); font-size:14px;
                        "><i class="bi bi-key-fill"></i></div>
                        <span style="font-size:14px; font-weight:600; color:var(--text);">API Keys & Webhooks</span>
                    </div>
                    <button onclick="window.openNewKeyModal()" style="
                        padding:7px 16px; border-radius:8px;
                        background: rgba(6,182,212,0.12); color:${INT_COLOR};
                        border: 1px solid rgba(6,182,212,0.25); cursor:pointer;
                        font-family:var(--font); font-size:12px; font-weight:600;
                        transition: all 0.15s;
                    "
                    onmouseover="this.style.background='rgba(6,182,212,0.22)'"
                    onmouseout="this.style.background='rgba(6,182,212,0.12)'">
                        <i class="bi bi-plus" style="margin-right:4px;"></i>Generate Key
                    </button>
                </div>
                <div style="padding: 20px 24px;">
                    ${keys.length === 0 ? `
                        <div style="text-align:center; padding:32px; color:var(--dim); font-size:13px;">
                            <i class="bi bi-key" style="font-size:32px; display:block; margin-bottom:12px; opacity:0.4;"></i>
                            No API keys yet. Generate one to connect your custom CRM or webhook.
                        </div>
                    ` : keys.map(k => `
                        <div style="
                            display:flex; align-items:center; gap:12px; padding:12px;
                            border-radius:10px; background:rgba(255,255,255,0.025);
                            border:1px solid var(--border); margin-bottom:8px;
                        ">
                            <i class="bi bi-check-circle-fill" style="color:#22C55E;"></i>
                            <div style="flex:1;">
                                <div style="font-size:13px; color:var(--text); font-weight:500;">${k.config?.label || k.platform}</div>
                                <div style="font-size:11px; color:var(--dim); margin-top:2px;">${k.module} module · Active</div>
                            </div>
                            <button onclick="window.showWebhookInfo('${k.id}')" style="
                                padding:5px 12px; border-radius:6px; border:1px solid var(--border);
                                background:transparent; color:var(--muted); cursor:pointer;
                                font-family:var(--font); font-size:11px;
                            ">View Details</button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /* ── Connect Handlers ────────────────────────────────────── */
    function handleConnect(mod, item) {
        const mode = item.connectMode || (item.oauth ? 'oauth' : 'custom');
        if (mode === 'oauth') showOAuthModal(mod, item);
        else if (mode === 'custom') showCustomCRMModal(mod);
        else if (mode === 'tracker') showTrackerModal();
        else if (mode === 'webhook') showWebhookModal();
        else showComingSoonModal(item);
    }

    function showCustomCRMModal(module) {
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
                    <div style="width:40px; height:40px; border-radius:10px; background:rgba(6,182,212,0.15); border:1px solid rgba(6,182,212,0.25); display:flex; align-items:center; justify-content:center; color:${INT_COLOR}; font-size:18px;">
                        <i class="bi bi-gear-wide-connected"></i>
                    </div>
                    <div>
                        <h3 style="margin:0; font-size:16px; color:var(--text);">Connect Custom CRM</h3>
                        <p style="margin:4px 0 0; font-size:12px; color:var(--muted);">Choose how your CRM sends data to NeuralOrbit</p>
                    </div>
                </div>

                <!-- Option A: Webhook -->
                <div style="margin-bottom:16px;">
                    <div style="font-size:12px; font-weight:600; color:var(--muted); letter-spacing:0.05em; margin-bottom:10px; text-transform:uppercase;">Option A — Webhook (recommended)</div>
                    <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:16px;">
                        <p style="font-size:13px; color:var(--text); margin:0 0 8px;">Your CRM pushes events to a URL we generate. Best for real-time data.</p>
                        <div style="font-size:12px; color:var(--dim);">
                            <i class="bi bi-check2" style="color:#22C55E; margin-right:6px;"></i>Real-time events<br>
                            <i class="bi bi-check2" style="color:#22C55E; margin-right:6px;"></i>HMAC secure signature<br>
                            <i class="bi bi-check2" style="color:#22C55E; margin-right:6px;"></i>Any language/platform
                        </div>
                        <button onclick="window.createWebhookIntegration('${module}')" style="
                            margin-top:14px; padding:8px 18px; border-radius:8px;
                            background:rgba(6,182,212,0.12); color:${INT_COLOR};
                            border:1px solid rgba(6,182,212,0.25); cursor:pointer;
                            font-family:var(--font); font-size:12px; font-weight:600;
                        ">
                            <i class="bi bi-lightning-fill" style="margin-right:5px;"></i>Generate Webhook URL
                        </button>
                    </div>
                </div>

                <!-- Option B: API Key -->
                <div>
                    <div style="font-size:12px; font-weight:600; color:var(--muted); letter-spacing:0.05em; margin-bottom:10px; text-transform:uppercase;">Option B — API Key (developer-friendly)</div>
                    <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:16px;">
                        <p style="font-size:13px; color:var(--text); margin:0 0 8px;">Your developer calls our API directly with an API key in the header.</p>
                        <code style="display:block; background:rgba(0,0,0,0.3); padding:10px 12px; border-radius:6px; font-size:11px; color:#06B6D4; margin-bottom:10px;">
                            POST https://api.neuralorbit.ai/api/v1/events<br>
                            X-API-Key: no_live_••••••••
                        </code>
                        <button onclick="window.createApiKeyIntegration('crm')" style="
                            padding:8px 18px; border-radius:8px;
                            background:rgba(91,140,255,0.12); color:var(--accent);
                            border:1px solid rgba(91,140,255,0.25); cursor:pointer;
                            font-family:var(--font); font-size:12px; font-weight:600;
                        ">
                            <i class="bi bi-key-fill" style="margin-right:5px;"></i>Generate API Key
                        </button>
                    </div>
                </div>
            </div>
        `);
    }

    async function showTrackerModal() {
        // Step 1: Show loading state immediately
        showModal(`
            <div style="padding:28px; text-align:center;">
                <div style="width:40px;height:40px;border-radius:10px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.25);display:flex;align-items:center;justify-content:center;color:#EF4444;font-size:18px;margin:0 auto 16px;">
                    <i class="bi bi-code-slash"></i>
                </div>
                <p style="color:var(--dim);font-size:13px;">Generating your unique tracker token...</p>
            </div>
        `);

        // Step 2: Get auth token and create/fetch the website integration
        const authToken = localStorage.getItem('neuralorbit_token');
        const authHeaders = {
            'Content-Type': 'application/json',
            ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
        };

        let trackerToken = 'YOUR-TOKEN-HERE';

        try {
            const resp = await fetchWithTimeout(`${BACKEND}/api/v1/integrations`, {
                method: 'POST',
                headers: authHeaders,
                body: JSON.stringify({
                    module: 'website',
                    platform: 'no_tracker',
                    label: 'NeuralOrbit Website Tracker',
                    type: 'webhook'
                })
            }, 8000);

            if (resp && resp.ok) {
                const data = await resp.json();
                trackerToken = data?.integration?.webhook_secret || trackerToken;
            }
        } catch (err) {
            console.warn('[Tracker] Could not generate token:', err);
        }

        // Step 3: Build deployable snippet with real token
        const backendUrl = window.BACKEND_URL || 'http://localhost:8000';
        const snippet = `<!-- NeuralOrbit Website Tracker -->
<script>
(function(w,d){
  var s=d.createElement('script');
  s.async=true;
  s.src='${backendUrl}/static/tracker.js';
  s.dataset.token='${trackerToken}';
  s.dataset.endpoint='${backendUrl}/api/v1/track';
  d.head.appendChild(s);
})(window,document);
<\/script>`;

        // Step 4: Show the full modal with real snippet
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
                    <div style="width:40px;height:40px;border-radius:10px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.25);display:flex;align-items:center;justify-content:center;color:#EF4444;font-size:18px;">
                        <i class="bi bi-code-slash"></i>
                    </div>
                    <div>
                        <h3 style="margin:0;font-size:16px;color:var(--text);">NeuralOrbit Website Tracker</h3>
                        <p style="margin:4px 0 0;font-size:12px;color:var(--muted);">Paste in your website &lt;head&gt; to start tracking</p>
                    </div>
                </div>
                ${trackerToken === 'YOUR-TOKEN-HERE' ? `
                <div style="padding:10px 14px;border-radius:8px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);margin-bottom:14px;font-size:12px;color:#EF4444;">
                    <i class="bi bi-exclamation-triangle" style="margin-right:6px;"></i>Backend offline — start the backend server for your real token.
                </div>` : `
                <div style="padding:10px 14px;border-radius:8px;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);margin-bottom:14px;font-size:12px;color:#22C55E;">
                    <i class="bi bi-check-circle-fill" style="margin-right:6px;"></i>Your unique token is embedded. This snippet is ready to deploy.
                </div>`}
                <p style="font-size:13px;color:var(--dim);line-height:1.6;margin-bottom:14px;">
                    Paste once into your site's <code style="color:${INT_COLOR}">&lt;head&gt;</code>. Tracks page views, clicks, forms, scroll depth, and sessions automatically.
                </p>
                <div style="position:relative;">
                    <pre style="background:rgba(0,0,0,0.4);border:1px solid var(--border);border-radius:10px;padding:16px;font-size:11px;color:#06B6D4;overflow-x:auto;margin:0;font-family:'Courier New',monospace;line-height:1.6;">${snippet.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>
                    <button onclick="navigator.clipboard.writeText(\`${snippet.replace(/`/g,'\\`')}\`).then(()=>{this.textContent='Copied!';setTimeout(()=>{this.textContent='Copy'},2000)})" style="position:absolute;top:10px;right:10px;padding:4px 12px;border-radius:6px;border:1px solid var(--border);background:rgba(255,255,255,0.05);color:var(--muted);cursor:pointer;font-family:var(--font);font-size:11px;">Copy</button>
                </div>
                <div style="margin-top:14px;padding:12px 14px;border-radius:8px;background:rgba(6,182,212,0.06);border:1px solid rgba(6,182,212,0.15);">
                    <div style="font-size:12px;color:${INT_COLOR};font-weight:600;margin-bottom:6px;"><i class="bi bi-lightning-fill" style="margin-right:5px;"></i>What it tracks automatically</div>
                    <div style="font-size:12px;color:var(--dim);display:grid;grid-template-columns:1fr 1fr;gap:4px;">
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>Page views & duration</span>
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>CTA & button clicks</span>
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>Form submissions</span>
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>Scroll depth (25/50/75/100%)</span>
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>Bounce detection</span>
                        <span><i class="bi bi-check2" style="color:#22C55E;margin-right:4px;"></i>Session value scoring</span>
                    </div>
                </div>
                <p style="font-size:11px;color:var(--dim);margin-top:12px;">
                    <i class="bi bi-shield-check" style="color:#22C55E;margin-right:4px;"></i>No PII collected. GDPR-friendly. Zero performance impact.
                </p>
            </div>
        `);

        await refresh();
    }


    function showWebhookModal() {
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
                    <div style="width:40px; height:40px; border-radius:10px; background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.25); display:flex; align-items:center; justify-content:center; color:var(--warning); font-size:18px;">
                        <i class="bi bi-lightning-fill"></i>
                    </div>
                    <div>
                        <h3 style="margin:0; font-size:16px; color:var(--text);">Shield Webhook</h3>
                        <p style="margin:4px 0 0; font-size:12px; color:var(--muted);">Send security events to NeuralOrbit</p>
                    </div>
                </div>
                <p style="font-size:13px; color:var(--dim); line-height:1.6; margin-bottom:16px;">
                    Connect your security system to send events like threat detections, login anomalies, and data access logs to NeuralOrbit for AI-powered analysis.
                </p>
                <button onclick="window.createWebhookIntegration('shield')" style="
                    width:100%; padding:10px; border-radius:8px;
                    background:rgba(245,158,11,0.12); color:var(--warning);
                    border:1px solid rgba(245,158,11,0.25); cursor:pointer;
                    font-family:var(--font); font-size:13px; font-weight:600;
                ">
                    <i class="bi bi-lightning-fill" style="margin-right:8px;"></i>Generate Shield Webhook URL
                </button>
            </div>
        `);
    }

    /* ── OAuth Modal (L2/L3) ─────────────────────────────────── */
    function showOAuthModal(module, item) {
        const isMarketing = item.key === 'meta_ads' || item.key === 'google_ads';

        // For Meta Ads & Google Ads: user must provide their own credentials.
        // Show credential form immediately — no need to hit the backend first.
        if (isMarketing) {
            const platformName = item.key === 'meta_ads' ? 'Meta Ads' : 'Google Ads';
            const idLabel      = item.key === 'meta_ads' ? 'Meta App ID' : 'Google OAuth Client ID';
            const secretLabel  = item.key === 'meta_ads' ? 'Meta App Secret' : 'Google OAuth Client Secret';
            const helpUrl      = item.key === 'meta_ads'
                ? 'https://developers.facebook.com/apps/'
                : 'https://console.cloud.google.com/apis/credentials';
            const scopeNote    = item.key === 'meta_ads'
                ? 'Requires: ads_read, ads_management'
                : 'Requires: Google Ads API scope';

            showModal(`
                <div style="padding:28px;">
                    <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
                        <div style="width:40px; height:40px; border-radius:10px; background:rgba(91,140,255,0.12); border:1px solid rgba(91,140,255,0.25); display:flex; align-items:center; justify-content:center; color:var(--accent); font-size:18px;">
                            <i class="bi ${item.icon}"></i>
                        </div>
                        <div>
                            <h3 style="margin:0; font-size:16px; color:var(--text);">Connect ${platformName}</h3>
                            <p style="margin:4px 0 0; font-size:12px; color:var(--muted);">Enter your developer app credentials to authorize</p>
                        </div>
                    </div>

                    <div style="padding:14px; border-radius:10px; background:rgba(91,140,255,0.05); border:1px solid rgba(91,140,255,0.15); margin-bottom:16px;">
                        <div style="font-size:12px; color:var(--accent); font-weight:600; margin-bottom:12px;">
                            <i class="bi bi-shield-lock" style="margin-right:6px;"></i> Your App Credentials
                        </div>

                        <div style="margin-bottom:12px;">
                            <label for="oauth-client-id" style="display:block; font-size:11px; color:var(--dim); margin-bottom:5px;">${idLabel}</label>
                            <input type="text" id="oauth-client-id" placeholder="Paste your App ID / Client ID..." autocomplete="off"
                                style="width:100%; padding:9px 12px; border-radius:8px; background:rgba(0,0,0,0.25); border:1px solid var(--border); color:white; font-size:12px; outline:none; box-sizing:border-box;">
                        </div>

                        <div style="margin-bottom:14px;">
                            <label for="oauth-client-secret" style="display:block; font-size:11px; color:var(--dim); margin-bottom:5px;">${secretLabel}</label>
                            <input type="password" id="oauth-client-secret" placeholder="••••••••••••••••" autocomplete="new-password"
                                style="width:100%; padding:9px 12px; border-radius:8px; background:rgba(0,0,0,0.25); border:1px solid var(--border); color:white; font-size:12px; outline:none; box-sizing:border-box;">
                        </div>

                        <div style="font-size:11px; color:var(--dim); line-height:1.6; padding:10px; border-radius:7px; background:rgba(0,0,0,0.2);">
                            <i class="bi bi-question-circle" style="color:var(--accent); margin-right:5px;"></i>
                            <strong style="color:var(--muted);">Where to find these?</strong><br>
                            Go to <a href="${helpUrl}" target="_blank" style="color:var(--accent);">${platformName} Developer Console</a>,
                            create or select your app, and copy the credentials from the OAuth or App Settings section.<br>
                            <span style="color:var(--dim); margin-top:4px; display:block;">${scopeNote}</span>
                        </div>
                    </div>

                    <div style="padding:10px; border-radius:8px; background:rgba(34,197,94,0.06); border:1px solid rgba(34,197,94,0.15); margin-bottom:16px; font-size:11px; color:var(--muted); line-height:1.5;">
                        <i class="bi bi-lock-fill" style="color:#22C55E; margin-right:5px;"></i>
                        Your credentials are stored <strong style="color:var(--text);">encrypted per your account</strong> and never shared. You can disconnect anytime.
                    </div>

                    <button onclick="window.startUserOAuth('${module}','${item.key}')" style="
                        width:100%; padding:12px; border-radius:10px;
                        background: linear-gradient(135deg, #5B8CFF 0%, #8B5CF6 100%);
                        color:white; border:none; cursor:pointer;
                        font-family:var(--font); font-size:14px; font-weight:600;
                        box-shadow: 0 4px 20px rgba(91,140,255,0.3);
                        transition: opacity .15s;
                    " onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">
                        <i class="bi bi-box-arrow-up-right" style="margin-right:8px;"></i>Authorize ${platformName}
                    </button>
                </div>
            `);
            return;  // Done — no backend GET needed for marketing platforms
        }

        // For CRM platforms (Zoho, HubSpot, Salesforce): NeuralOrbit's system OAuth.
        // Fetch a redirect URL from the backend.
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
                    <div style="width:40px; height:40px; border-radius:10px; background:rgba(91,140,255,0.12); border:1px solid rgba(91,140,255,0.25); display:flex; align-items:center; justify-content:center; color:var(--accent); font-size:18px;">
                        <i class="bi ${item.icon}"></i>
                    </div>
                    <div>
                        <h3 style="margin:0; font-size:16px; color:var(--text);">Connect ${item.name}</h3>
                        <p style="margin:4px 0 0; font-size:12px; color:var(--muted);">OAuth 2.0 Secure Connection</p>
                    </div>
                </div>
                <div id="oauth-modal-content">
                    <div style="text-align:center; padding:20px; color:var(--muted); font-size:13px;">
                        <div class="loading-spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto 12px;"></div>
                        Generating authorization URL...
                    </div>
                </div>
            </div>
        `);

        // POST to /init — CRM platforms use system credentials from .env
        apiPost(`/api/v1/integrations/oauth/${item.key}/init`, { module }).then(data => {
            const el = document.getElementById('oauth-modal-content');
            if (!el) return;

            if (data?.oauth_url) {
                el.innerHTML = `
                    <p style="font-size:13px; color:var(--dim); line-height:1.6; margin-bottom:16px;">
                        You'll be redirected to <strong style="color:var(--text)">${item.name}</strong> to authorize NeuralOrbit. We never store your password.
                    </p>
                    <button onclick="window.openOAuthPopup('${data.oauth_url}','${item.key}')" style="
                        width:100%; padding:12px; border-radius:10px;
                        background: linear-gradient(135deg, #5B8CFF 0%, #8B5CF6 100%);
                        color:white; border:none; cursor:pointer;
                        font-family:var(--font); font-size:14px; font-weight:600;
                        box-shadow: 0 4px 20px rgba(91,140,255,0.3);
                    ">
                        <i class="bi bi-box-arrow-up-right" style="margin-right:8px;"></i>Authorize ${item.name}
                    </button>
                    <p style="font-size:11px; color:var(--dim); text-align:center; margin-top:10px;">
                        <i class="bi bi-lock-fill" style="color:#22C55E; margin-right:4px;"></i>Secure OAuth 2.0 · Read-only access · Can revoke anytime
                    </p>
                `;
            } else if (data?.status === 'not_configured') {
                el.innerHTML = `
                    <div style="padding:16px; border-radius:10px; background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.2);">
                        <div style="font-size:13px; color:var(--warning); font-weight:600; margin-bottom:8px;">
                            <i class="bi bi-exclamation-triangle" style="margin-right:6px;"></i> Not Configured Yet
                        </div>
                        <p style="font-size:12px; color:var(--muted); line-height:1.5; margin:0;">
                            ${item.name} OAuth requires <code>ZOHO_CLIENT_ID</code> / <code>HUBSPOT_CLIENT_ID</code> set in the backend <code>.env</code> file, and the callback URL registered in your developer console.
                        </p>
                    </div>
                `;
            } else {
                el.innerHTML = `<p style="color:var(--danger); font-size:13px;">Failed to get OAuth URL. Is the backend running?</p>`;
            }
        });
    }


    window.startUserOAuth = async function (module, platform) {
        const clientId = document.getElementById('oauth-client-id')?.value;
        const clientSecret = document.getElementById('oauth-client-secret')?.value;

        if (!clientId || !clientSecret) {
            alert('Please enter both ID and Secret.');
            return;
        }

        const btn = document.querySelector('#oauth-modal-content button');
        const oldHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<div class="loading-spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:8px;"></div>Initializing...';

        // Fetch OAuth URL while passing the user-provided credentials
        const data = await apiPost(`/api/v1/integrations/oauth/${platform}/init`, {
            module,
            client_id: clientId,
            client_secret: clientSecret
        });

        if (data?.oauth_url) {
            window.openOAuthPopup(data.oauth_url, platform);
        } else {
            alert(data?.message || 'Failed to initialize OAuth flow. Ensure backend is running.');
            btn.disabled = false;
            btn.innerHTML = oldHtml;
        }
    };

    window.openOAuthPopup = function (url, platform) {
        const popup = window.open(url, 'oauth', 'width=600,height=700,scrollbars=yes');
        const timer = setInterval(() => {
            if (popup && popup.closed) {
                clearInterval(timer);
                closeIntegrationModal();
                refresh();
            }
        }, 500);
        // Also listen for postMessage from callback page
        window.addEventListener('message', function onMsg(e) {
            if (e.data?.type === 'oauth_success') {
                window.removeEventListener('message', onMsg);
                clearInterval(timer);
                closeIntegrationModal();
                refresh();
            }
        });
    };

    /* ── n8n Status Panel (L5) ───────────────────────────────── */
    function renderN8nPanel() {
        return `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
            ">
                <div style="
                    padding: 16px 24px;
                    border-bottom: 1px solid var(--border);
                    display:flex; align-items:center; justify-content:space-between;
                    background: rgba(255,255,255,0.015);
                ">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div style="
                            width:32px; height:32px; border-radius:8px;
                            background: rgba(239,68,68,0.12);
                            border: 1px solid rgba(239,68,68,0.2);
                            display:flex; align-items:center; justify-content:center;
                            color:#EF4444; font-size:14px;
                        "><i class="bi bi-diagram-3-fill"></i></div>
                        <div>
                            <span style="font-size:14px; font-weight:600; color:var(--text);">Bi-directional Execution</span>
                            <span style="font-size:11px; color:var(--warning); background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.2); border-radius:4px; padding:1px 8px; margin-left:8px; font-weight:600;">L5</span>
                        </div>
                    </div>
                    <div style="font-size:11px; color:var(--dim); padding:5px 12px; border-radius:6px; background:rgba(255,255,255,0.03); border:1px solid var(--border);">
                        Requires n8n approval
                    </div>
                </div>
                <div style="padding: 20px 24px;">
                    <p style="font-size:13px; color:var(--dim); line-height:1.6; margin:0 0 16px;">
                        Once n8n is approved and running, AI decisions will automatically execute back into your connected platforms — pausing underperforming ads, assigning leads, sending follow-ups.
                    </p>
                    <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:10px;">
                        ${[
                { icon: 'bi-people', label: 'Assign Lead', module: 'CRM', color: '#22C55E' },
                { icon: 'bi-megaphone', label: 'Pause Campaign', module: 'Marketing', color: '#8B5CF6' },
                { icon: 'bi-currency-dollar', label: 'Adjust Budget', module: 'Marketing', color: '#8B5CF6' },
                { icon: 'bi-shield-exclamation', label: 'Block Threat', module: 'Shield', color: '#F59E0B' },
                { icon: 'bi-send', label: 'Send Follow-up', module: 'CRM', color: '#22C55E' },
                { icon: 'bi-bell', label: 'Notify Team', module: 'Website', color: '#EF4444' },
            ].map(a => `
                            <div style="
                                padding:12px; border-radius:10px;
                                background:rgba(255,255,255,0.02); border:1px solid var(--border);
                                display:flex; align-items:center; gap:10px;
                                opacity:0.7;
                            ">
                                <div style="width:28px; height:28px; border-radius:7px; background:${a.color}18; display:flex; align-items:center; justify-content:center; color:${a.color}; font-size:13px;">
                                    <i class="bi ${a.icon}"></i>
                                </div>
                                <div>
                                    <div style="font-size:12px; color:var(--text); font-weight:500;">${a.label}</div>
                                    <div style="font-size:10px; color:var(--dim);">${a.module}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div style="margin-top:16px; padding:10px 14px; border-radius:8px; background:rgba(6,182,212,0.05); border:1px solid rgba(6,182,212,0.12); font-size:12px; color:var(--dim);">
                        <i class="bi bi-info-circle" style="color:${INT_COLOR}; margin-right:6px;"></i>
                        API endpoint ready: <code style="color:${INT_COLOR};">POST /api/v1/decisions/{id}/execute</code> — will trigger n8n when running.
                    </div>
                </div>
            </div>
        `;
    }

    function showComingSoonModal(item) {
        showModal(`
            <div style="padding:32px; text-align:center;">
                <div style="font-size:48px; margin-bottom:16px; opacity:0.5;"><i class="bi bi-clock-history"></i></div>
                <h3 style="font-size:18px; color:var(--text); margin:0 0 8px;">${item.name}</h3>
                <p style="font-size:13px; color:var(--dim); line-height:1.6; margin:0 0 16px;">
                    OAuth integration for <strong style="color:var(--text);">${item.name}</strong> is planned for <strong style="color:var(--accent);">${item.level}</strong>.
                    We're building it next.
                </p>
                <div style="
                    display:inline-block; padding:6px 16px; border-radius:6px;
                    background:rgba(245,158,11,0.1); color:var(--warning);
                    border:1px solid rgba(245,158,11,0.2); font-size:12px; font-weight:700;
                ">${item.level} — Coming Soon</div>
            </div>
        `);
    }

    /* ── Modal System ────────────────────────────────────────── */
    function showModal(html) {
        const overlay = document.getElementById('integration-modal-overlay');
        overlay.style.cssText = `
            display:flex; align-items:center; justify-content:center;
            position:fixed; inset:0; z-index:9999;
            background: rgba(0,0,0,0.65);
            backdrop-filter: blur(4px);
            animation: fadeIn 0.2s ease;
        `;
        overlay.innerHTML = `
            <div style="
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 20px;
                width: 500px;
                max-width: 90vw;
                max-height: 85vh;
                overflow-y: auto;
                position: relative;
                box-shadow: 0 24px 80px rgba(0,0,0,0.6);
                animation: slideInRight 0.25s ease;
            ">
                <button onclick="window.closeIntegrationModal()" aria-label="Close dialog" style="
                    position:absolute; top:16px; right:16px;
                    width:30px; height:30px; border-radius:50%;
                    background: rgba(255,255,255,0.06); border:1px solid var(--border);
                    color:var(--muted); cursor:pointer; display:flex;
                    align-items:center; justify-content:center; font-size:14px;
                    z-index:1;
                "><i class="bi bi-x"></i></button>
                ${html}
            </div>
        `;
        overlay.onclick = (e) => { if (e.target === overlay) closeIntegrationModal(); };
    }

    window.closeIntegrationModal = function () {
        const overlay = document.getElementById('integration-modal-overlay');
        if (overlay) overlay.style.display = 'none';
    };

    /* ── Integration Creation ────────────────────────────────── */
    window.createWebhookIntegration = async function (module) {
        const label = `${module.toUpperCase()} Webhook`;
        const result = await apiPost('/api/v1/integrations', {
            module,
            platform: module === 'shield' ? 'webhook' : 'custom',
            label,
            type: 'webhook',
        });

        if (result?.integration) {
            closeIntegrationModal();
            showWebhookResultModal(result.integration);
            await refresh();
        } else {
            alert('Failed to create webhook. Is the backend running?');
        }
    };

    window.createApiKeyIntegration = async function (module) {
        const result = await apiPost('/api/v1/integrations', {
            module,
            platform: 'custom',
            label: `${module.toUpperCase()} API Key`,
            type: 'api_key',
        });

        if (result?.integration) {
            closeIntegrationModal();
            showApiKeyResultModal(result.integration);
            await refresh();
        } else {
            alert('Failed to generate API key. Is the backend running?');
        }
    };

    window.openNewKeyModal = function () {
        showCustomCRMModal('crm');
    };

    window.showWebhookInfo = async function (id) {
        const data = await apiGet(`/api/v1/integrations/${id}`);
        if (data?.integration) showWebhookResultModal(data.integration);
    };

    function showWebhookResultModal(integration) {
        const webhookUrl = `${BACKEND}/api/v1/integrations/inbound/${integration.id}`;
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
                    <i class="bi bi-check-circle-fill" style="color:#22C55E; font-size:28px;"></i>
                    <div>
                        <h3 style="margin:0; font-size:16px; color:var(--text);">Webhook Created</h3>
                        <p style="margin:4px 0 0; font-size:12px; color:#22C55E;">Active and ready to receive data</p>
                    </div>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:11px; color:var(--muted); font-weight:600; margin-bottom:6px; text-transform:uppercase;">Webhook URL</div>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <code style="flex:1; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:8px; font-size:11px; color:${INT_COLOR}; border:1px solid var(--border); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${webhookUrl}</code>
                        <button onclick="navigator.clipboard.writeText('${webhookUrl}').then(()=>{this.textContent='✓';setTimeout(()=>{this.textContent='Copy';},1500)})" style="padding:6px 12px; border-radius:6px; border:1px solid var(--border); background:rgba(255,255,255,0.04); color:var(--muted); cursor:pointer; font-size:11px; font-family:var(--font); white-space:nowrap;">Copy</button>
                    </div>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:11px; color:var(--muted); font-weight:600; margin-bottom:6px; text-transform:uppercase;">Webhook Secret (HMAC)</div>
                    <code style="display:block; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:8px; font-size:11px; color:var(--warning); border:1px solid var(--border);">${integration.webhook_secret || '(shown once — copy now)'}</code>
                </div>
                <div style="padding:12px 14px; border-radius:8px; background:rgba(6,182,212,0.06); border:1px solid rgba(6,182,212,0.15); font-size:12px; color:var(--dim);">
                    <strong style="color:${INT_COLOR};">Your CRM sends:</strong> POST to the URL above with JSON body.<br>
                    Include header: <code style="color:${INT_COLOR};">X-NeuralOrbit-Signature: hmac_sha256(secret, body)</code>
                </div>
            </div>
        `);
    }

    function showApiKeyResultModal(integration) {
        const apiKey = integration.api_key || 'no_live_••••••••';
        showModal(`
            <div style="padding:28px;">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
                    <i class="bi bi-check-circle-fill" style="color:#22C55E; font-size:28px;"></i>
                    <div>
                        <h3 style="margin:0; font-size:16px; color:var(--text);">API Key Generated</h3>
                        <p style="margin:4px 0 0; font-size:12px; color:#22C55E;">Copy this key — it won't be shown again</p>
                    </div>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:11px; color:var(--muted); font-weight:600; margin-bottom:6px; text-transform:uppercase;">API Key</div>
                    <div style="display:flex; gap:8px;">
                        <code style="flex:1; background:rgba(0,0,0,0.4); padding:10px 14px; border-radius:8px; font-size:12px; color:#22C55E; border:1px solid var(--border);">${apiKey}</code>
                        <button onclick="navigator.clipboard.writeText('${apiKey}').then(()=>{this.textContent='✓';setTimeout(()=>{this.textContent='Copy';},1500)})" style="padding:8px 14px; border-radius:6px; border:1px solid var(--border); background:rgba(255,255,255,0.04); color:var(--muted); cursor:pointer; font-size:12px; font-family:var(--font);">Copy</button>
                    </div>
                </div>
                <div style="background:rgba(0,0,0,0.3); padding:14px; border-radius:10px; border:1px solid var(--border);">
                    <div style="font-size:11px; color:var(--muted); font-weight:600; margin-bottom:8px; text-transform:uppercase;">How to use</div>
                    <pre style="margin:0; font-size:11px; color:${INT_COLOR}; font-family:'Courier New',monospace;">POST ${BACKEND}/api/v1/events
X-API-Key: ${apiKey}
Content-Type: application/json

{
  "module": "crm",
  "event_type": "deal_closed",
  "payload": { "deal_id": "123", "value": 5000 }
}</pre>
                </div>
            </div>
        `);
    }

    /* ── Sync Toast Notification ────────────────────────────── */
    function showSyncToast(platform, count, errorMsg) {
        // Remove any existing toast
        const existing = document.getElementById('no-sync-toast');
        if (existing) existing.remove();

        const isError   = count < 0 || !!errorMsg;
        const platName  = platform.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
        const message   = isError
            ? (errorMsg || `${platName} sync failed.`)
            : (count === 0
                ? `${platName} synced — no new records found.`
                : `${platName} synced ${count} record${count !== 1 ? 's' : ''} successfully.`);

        const toast = document.createElement('div');
        toast.id = 'no-sync-toast';
        toast.style.cssText = `
            position:fixed; bottom:28px; right:28px; z-index:99999;
            padding:12px 18px; border-radius:10px;
            background:${isError ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)'};
            border:1px solid ${isError ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'};
            color:${isError ? '#ef4444' : '#22c55e'};
            font-size:13px; font-weight:600;
            box-shadow:0 4px 20px rgba(0,0,0,0.3);
            display:flex; align-items:center; gap:8px;
            animation:slideUpIn 0.3s ease;
        `;
        toast.innerHTML = `
            <i class="bi bi-${isError ? 'exclamation-triangle' : 'check-circle-fill'}"></i>
            ${message}
        `;

        // Add slide-up animation if not already in CSS
        if (!document.getElementById('no-toast-keyframes')) {
            const style = document.createElement('style');
            style.id = 'no-toast-keyframes';
            style.textContent = `@keyframes slideUpIn{from{transform:translateY(20px);opacity:0}to{transform:translateY(0);opacity:1}}`;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    /* ── Refresh ─────────────────────────────────────────────── */
    async function refresh() {
        await loadConnections();
        renderHub();
    }

    /* ── Init ────────────────────────────────────────────────── */
    async function loadIntegrationsHub() {
        // Render immediately with empty state — never block on backend
        renderHub();

        // Then silently load connections in background and refresh
        await loadConnections();
        renderHub();
    }

    window.loadIntegrationsHub = loadIntegrationsHub;
    document.addEventListener('DOMContentLoaded', loadIntegrationsHub);

})();
