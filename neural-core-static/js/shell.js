/* ============================================================
   shell.js — NeuralOrbit App Shell v2
   Builds sidebar + topnav for every module page.
   Topnav: Left=breadcrumb | Center=tabs | Right=search+notif+avatar
   Sidebar: Logo → Nav (modules + admin) → Status → Footer
   ============================================================ */

(function () {
    'use strict';

    /* -------------------------------------------------------
       CONFIG
    ------------------------------------------------------- */
    const modules = [
        { key: 'neural-orbit', label: 'NeuralOrbit', icon: 'bi-cpu', color: '#5B8CFF', file: 'neural-orbit.html' },
        { key: 'crm', label: 'CRM', icon: 'bi-people', color: '#22C55E', file: 'crm.html' },
        { key: 'marketing', label: 'Marketing', icon: 'bi-megaphone', color: '#8B5CF6', file: 'marketing.html' },
        { key: 'shield', label: 'Shield', icon: 'bi-shield-fill', color: '#F59E0B', file: 'shield.html' },
        { key: 'website', label: 'Website', icon: 'bi-globe', color: '#EF4444', file: 'website.html' },
    ];

    const adminCenter = [
        { key: 'neural-orbit',    label: 'AI Command',      icon: 'bi-cpu-fill',       file: 'neural-orbit.html'  },
        { key: 'decisions',       label: 'Decision Log',    icon: 'bi-journal-text',   file: 'decisions.html'     },
        { key: 'users',           label: 'User Management', icon: 'bi-people-fill',    file: 'users.html'         },
        { key: 'portfolio',       label: 'Businesses',      icon: 'bi-building',       file: 'portfolio.html'     },
        { key: 'analytics',       label: 'Analytics',       icon: 'bi-bar-chart-line', file: 'analytics.html'     },
        { key: 'alerts',          label: 'Alert Center',    icon: 'bi-bell-fill',      file: 'alerts.html'        },
        { key: 'integrations',    label: 'Integrations',    icon: 'bi-plug-fill',      file: 'integrations.html'  },
        { key: 'admin-crm',       label: 'CRM (Admin)',        icon: 'bi-people',         file: 'crm.html'           },
        { key: 'admin-marketing', label: 'Marketing (Admin)',   icon: 'bi-megaphone',     file: 'marketing.html'     },
        { key: 'admin-shield',    label: 'Shield (Admin)',      icon: 'bi-shield-fill',    file: 'shield.html'        },
        { key: 'admin-website',   label: 'Website (Admin)',     icon: 'bi-globe',          file: 'website.html'       },
        { key: 'ai-intelligence', label: 'AI Intelligence',     icon: 'bi-brain',          file: 'ai-intelligence.html'},
    ];

    const tabs = [
        { route: 'overview', label: 'Overview', icon: 'bi-grid-1x2' },
        { route: 'decisions', label: 'Decision Log', icon: 'bi-journal-text' },
        { route: 'reward', label: 'Reward Engine', icon: 'bi-lightning-fill' },
        { route: 'autonomy', label: 'Autonomy', icon: 'bi-robot' },
        { route: 'learning', label: 'Learning', icon: 'bi-graph-up' },
        { route: 'sandbox', label: 'Sandbox', icon: 'bi-play-circle' },
    ];

    const ADMIN_ONLY_MODULES = new Set([
        'neural-orbit', 'decisions', 'users', 'portfolio', 'analytics', 'alerts', 'integrations',
        'admin-crm', 'admin-marketing', 'admin-shield', 'admin-website', 'ai-intelligence',
    ]);

    const moduleLabels = {
        'neural-orbit': 'NeuralOrbit', crm: 'CRM', marketing: 'Marketing',
        shield: 'Shield', website: 'Website', users: 'User Management',
        portfolio: 'Businesses', analytics: 'Analytics', alerts: 'Alert Center',
        integrations: 'Integration Hub', sandbox: 'AI Sandbox',
        'admin-crm': 'CRM (Admin)', 'admin-marketing': 'Marketing (Admin)',
        'admin-shield': 'Shield (Admin)', 'admin-website': 'Website (Admin)',
        'ai-intelligence': 'AI Intelligence',
    };

    function getFolder() {
        return window.CURRENT_ROLE === 'admin' ? 'admin/' : 'user/';
    }

    /* -------------------------------------------------------
       BUILD SIDEBAR
    ------------------------------------------------------- */
    function buildSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        const cur = window.CURRENT_MODULE;
        const isAdmin = window.CURRENT_ROLE === 'admin';
        const user = window.CURRENT_USER || {};
        const folder = getFolder();
        const root = window.NOAuth?.getRootPath?.() || '../';

        sidebar.innerHTML = `
            <div class="sidebar-inner">

                <!-- ── Logo ──────────────────────────────── -->
                <div class="sidebar-logo">
                    <div class="sidebar-logo-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>
                            <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>
                            <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/>
                            <path d="M12 18v-5"/>
                        </svg>
                    </div>
                    <div class="sidebar-logo-text">
                        <span class="sidebar-brand">NEURAL<span class="brand-accent">ORBIT</span></span>
                        <span class="sidebar-role-badge">${isAdmin ? 'ADMIN' : 'USER'}</span>
                    </div>
                </div>

                <!-- ── Nav ───────────────────────────────── -->
                <nav class="sidebar-nav">

                    <!-- Modules -->
                    <div class="sidebar-section-label">MODULES</div>
                    ${modules.map(m => `
                        <a class="sidebar-link ${cur === m.key ? 'is-active' : ''}"
                           href="${root}${folder}${m.file}"
                           style="${cur === m.key ? `--link-color:${m.color};` : ''}">
                            <div class="sidebar-link-icon ${cur === m.key ? 'is-active' : ''}"
                                 style="${cur === m.key ? `background:${m.color}20; color:${m.color};` : ''}">
                                <i class="bi ${m.icon}"></i>
                            </div>
                            <span class="sidebar-link-label">${m.label}</span>
                            ${cur === m.key ? '<div class="sidebar-active-bar"></div>' : ''}
                        </a>
                    `).join('')}

                    <!-- Design System — visible to all roles -->
                    <div class="sidebar-divider"></div>
                    <div class="sidebar-section-label">TOOLS</div>
                    <a class="sidebar-link ${cur === 'design-system' ? 'is-active' : ''}"
                       href="${root}design-system.html" style="--link-color:#EC4899;">
                        <div class="sidebar-link-icon ${cur === 'design-system' ? 'is-active' : ''}"
                             style="${cur === 'design-system' ? 'background:rgba(236,72,153,0.15); color:#EC4899;' : ''}">
                            <i class="bi bi-palette2"></i>
                        </div>
                        <span class="sidebar-link-label">Design System</span>
                        ${cur === 'design-system' ? '<div class="sidebar-active-bar" style="background:#EC4899;"></div>' : ''}
                    </a>
                    <a class="sidebar-link ${cur === 'integrations' ? 'is-active' : ''}"
                       href="${root}${folder}integrations.html" style="--link-color:#06B6D4;">
                        <div class="sidebar-link-icon ${cur === 'integrations' ? 'is-active' : ''}"
                             style="${cur === 'integrations' ? 'background:rgba(6,182,212,0.15); color:#06B6D4;' : ''}">
                            <i class="bi bi-plug-fill"></i>
                        </div>
                        <span class="sidebar-link-label">Integrations</span>
                        ${cur === 'integrations' ? '<div class="sidebar-active-bar" style="background:#06B6D4;"></div>' : ''}
                    </a>

                    <!-- Admin-only section -->
                    ${isAdmin ? `
                        <div class="sidebar-divider"></div>
                        <div class="sidebar-section-label">ADMIN CENTER</div>
                        ${adminCenter.map(a => `
                            <a class="sidebar-link ${cur === a.key ? 'is-active is-admin' : ''}"
                               href="${root}admin/${a.file}">
                                <div class="sidebar-link-icon ${cur === a.key ? 'is-active' : ''}">
                                    <i class="bi ${a.icon}"></i>
                                </div>
                                <span class="sidebar-link-label">${a.label}</span>
                                ${cur === a.key ? '<div class="sidebar-active-bar"></div>' : ''}
                            </a>
                        `).join('')}
                    ` : ''}
                </nav>

                <!-- ── AI Status (bottom-left) ────────────── -->
                <div class="sidebar-status">
                    <div class="status-dot-wrap">
                        <span class="status-dot"></span>
                    </div>
                    <div class="status-label">
                        <span style="color: var(--dim); font-weight: 600; font-size: 11px;">AI Active</span>
                        <div style="font-size: 10px; color: var(--success); margin-top: 1px;">All systems operational</div>
                    </div>
                </div>

                <!-- ── Footer / User row ──────────────────── -->
                <div class="sidebar-footer">
                    <div class="sidebar-user">
                        <div class="sidebar-avatar">${(user.name || 'U').substring(0, 2)}</div>
                        <div class="sidebar-user-info">
                            <div class="sidebar-user-name">${user.name || 'Demo User'}</div>
                            <div class="sidebar-user-email">${user.email || ''}</div>
                        </div>
                        <button class="sidebar-logout-btn"
                                onclick="window.NOAuth?.signOut?.()"
                                title="Sign Out" aria-label="Sign Out">
                            <i class="bi bi-box-arrow-right"></i>
                        </button>
                    </div>
                </div>

            </div>
        `;
    }

    /* -------------------------------------------------------
       BUILD TOPNAV
       3-column CSS Grid: [left 1fr] [center auto] [right 1fr]
       This guarantees true centering for both admin & user.
    ------------------------------------------------------- */
    function buildTopNav() {
        const topnav = document.getElementById('topnav');
        if (!topnav) return;

        const cur = window.CURRENT_MODULE;
        const isAdminOnly = ADMIN_ONLY_MODULES.has(cur);
        const activeHash = window.location.hash.replace('#', '') || 'overview';
        const user = window.CURRENT_USER || {};
        const isAdmin = window.CURRENT_ROLE === 'admin';
        const pageLabel = isAdminOnly
            ? (moduleLabels[cur] || 'Dashboard')
            : (tabs.find(t => t.route === activeHash)?.label || 'Overview');

        topnav.innerHTML = `
            <div style="
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                align-items: center;
                width: 100%;
                height: 100%;
                padding: 0 20px;
                gap: 12px;
            ">

                <!-- COL 1 LEFT: Mobile menu toggle + Breadcrumb -->
                <div style="display:flex; align-items:center; gap:8px; min-width:0;">
                    <button class="mobile-menu-btn" aria-label="Open navigation menu" aria-expanded="false"
                            onclick="window.toggleMobileSidebar?.()">
                        <i class="bi bi-list" aria-hidden="true"></i>
                    </button>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
                        <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>
                        <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>
                        <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/><path d="M12 18v-5"/>
                    </svg>
                    <span style="font-size:13px; font-weight:500; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                        ${moduleLabels[cur] || 'Dashboard'}
                    </span>
                    <span style="color:var(--dim); font-size:12px; flex-shrink:0;">/</span>
                    <span id="breadcrumb" style="font-size:13px; font-weight:600; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                        ${pageLabel}
                    </span>
                </div>

                <!-- COL 2 CENTER: Tabs (auto width, perfectly centered) -->
                <div style="display:flex; align-items:center; justify-content:center;">
                    ${(!isAdminOnly || !isAdmin) ? `
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 2px;
                            padding: 4px;
                            border-radius: 10px;
                            background: rgba(30,41,59,0.6);
                            border: 1px solid var(--border);
                        " id="topnav-tabs">
                            ${tabs.map(t => `
                                <button
                                    class="tab-btn ${activeHash === t.route ? 'is-active' : ''}"
                                    data-route="${t.route}"
                                    onclick="window.navigate?.('${t.route}')"
                                    style="
                                        display:flex; align-items:center; gap:5px;
                                        padding:6px 11px; border-radius:7px;
                                        font-size:12px; font-weight:${activeHash === t.route ? '600' : '500'};
                                        white-space:nowrap; border:none; cursor:pointer;
                                        font-family:var(--font);
                                        background:${activeHash === t.route ? 'var(--accent)' : 'transparent'};
                                        color:${activeHash === t.route ? 'white' : 'var(--muted)'};
                                        box-shadow:${activeHash === t.route ? '0 2px 10px rgba(91,140,255,0.3)' : 'none'};
                                        transition: all 0.15s;
                                    "
                                    onmouseover="if(!this.classList.contains('is-active')){this.style.background='rgba(30,41,59,0.8)';this.style.color='var(--text)';}"
                                    onmouseout="if(!this.classList.contains('is-active')){this.style.background='transparent';this.style.color='var(--muted)';}"
                                >
                                    <i class="bi ${t.icon}" style="font-size:11px;"></i>${t.label}
                                </button>
                            `).join('')}
                        </div>
                    ` : `
                        <span style="
                            font-size:11px; font-weight:700; padding:5px 14px;
                            border-radius:6px; letter-spacing:0.06em;
                            color:${cur === 'integrations' ? '#06B6D4' : 'var(--warning)'};
                            background:${cur === 'integrations' ? 'rgba(6,182,212,0.12)' : 'rgba(245,158,11,0.12)'};
                            border:1px solid ${cur === 'integrations' ? 'rgba(6,182,212,0.2)' : 'rgba(245,158,11,0.2)'};
                        ">${cur === 'integrations' ? 'INTEGRATION HUB' : isAdmin ? 'ADMIN PANEL' : 'READ ONLY'}</span>
                    `}
                </div>

                <!-- COL 3 RIGHT: Icons + Avatar (right-aligned) -->
                <div style="display:flex; align-items:center; gap:10px; justify-content:flex-end;">

                    <!-- Notification bell -->
                    <button class="topnav-icon-btn topnav-bell" aria-label="Notifications" title="Notifications">
                        <i class="bi bi-bell"></i>
                        <span class="bell-dot"></span>
                    </button>

                    <!-- Settings -->
                    <button class="topnav-icon-btn" aria-label="Settings" title="Settings">
                        <i class="bi bi-gear"></i>
                    </button>

                    <!-- AI Status chip -->
                    <div class="ai-status status-active">
                        <span class="ai-status-dot"></span>
                        <span class="ai-status-text">AI ACTIVE</span>
                    </div>

                    <!-- Profile avatar -->
                    <div class="topnav-avatar"
                         title="${user.name || 'Demo User'} · ${isAdmin ? 'Admin' : 'User'}"
                         style="cursor:pointer;">
                        ${(user.name || 'U').substring(0, 2)}
                    </div>

                </div>

            </div>
        `;
    }

    /* -------------------------------------------------------
       MOBILE SIDEBAR (off-canvas drawer under ~900px — see layout.css)
    ------------------------------------------------------- */
    function ensureMobileBackdrop() {
        if (document.getElementById('sidebar-backdrop')) return;
        const backdrop = document.createElement('div');
        backdrop.id = 'sidebar-backdrop';
        backdrop.className = 'sidebar-backdrop';
        backdrop.setAttribute('aria-hidden', 'true');
        backdrop.addEventListener('click', () => window.toggleMobileSidebar(false));
        document.body.appendChild(backdrop);
    }

    window.toggleMobileSidebar = function (force) {
        const sidebar = document.getElementById('sidebar');
        const backdrop = document.getElementById('sidebar-backdrop');
        const btn = document.querySelector('.mobile-menu-btn');
        if (!sidebar) return;
        const shouldOpen = typeof force === 'boolean' ? force : !sidebar.classList.contains('sidebar--mobile-open');
        sidebar.classList.toggle('sidebar--mobile-open', shouldOpen);
        backdrop?.classList.toggle('is-visible', shouldOpen);
        btn?.setAttribute('aria-expanded', String(shouldOpen));
        document.body.style.overflow = shouldOpen ? 'hidden' : '';
    };

    /* -------------------------------------------------------
       INIT SHELL
    ------------------------------------------------------- */
    function initShell() {
        buildSidebar();
        buildTopNav();
        ensureMobileBackdrop();

        // Close the mobile drawer on any in-shell navigation.
        document.getElementById('sidebar')?.addEventListener('click', (e) => {
            if (e.target.closest('a')) window.toggleMobileSidebar(false);
        });

        const cur = window.CURRENT_MODULE;
        const isAdminOnly = ADMIN_ONLY_MODULES.has(cur);

        if (isAdminOnly) {
            const loaderMap = {
                'neural-orbit':    () => window.loadNeuralOrbitAdminPage?.() || window.loadNeuralOrbitPage?.(),
                decisions:         () => window.loadDecisionsPage?.(),
                users:             () => window.loadUsersPage?.(),
                portfolio:         () => window.loadPortfolioPage?.(),
                analytics:         () => window.loadAnalyticsPage?.(),
                alerts:            () => window.loadAlertsPage?.(),
                integrations:      () => window.loadIntegrationsPage?.(),
                'admin-crm':       () => window.loadCrmAdminPage?.(),
                'admin-marketing': () => window.loadMarketingAdminPage?.(),
                'admin-shield':    () => window.loadShieldAdminPage?.(),
                'admin-website':   () => window.loadWebsiteAdminPage?.(),
                'ai-intelligence': () => window.loadAIIntelligencePage?.(),
            };
            const loader = loaderMap[cur];
            if (loader) loader();
        }
    }

    window.initShell = initShell;

})();
