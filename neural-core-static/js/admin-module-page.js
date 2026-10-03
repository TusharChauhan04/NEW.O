/* ============================================================
   admin-module-page.js — Shared builder for the admin per-module
   dashboards (CRM / Marketing / Shield / Website).

   Previously each of admin/crm.html, marketing.html, shield.html,
   website.html hand-rolled its own ~75-line copy of this exact same
   KPI + decision-table + filter + drawer UI, differing only in the
   module name, KPI definitions, demo data, and DOM-id prefix. This
   file is the single implementation; each HTML page now just supplies
   its own config object.

   Usage (in each admin/<module>.html):
     window.loadCrmAdminPage = window.createAdminModulePage({
       module: 'crm', idPrefix: 'crm',
       title: 'CRM Module', subtitle: '...',
       kpiDefs: [...], demoDecisions: [...],
     });
   window.loadXAdminPage is exactly what shell.js dispatches to
   (see js/shell.js's ROUTE_LOADERS map) — that contract is unchanged.
============================================================ */
(function () {
    'use strict';

    function escHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function defaultConfidenceColor(pct) {
        return pct >= 90 ? '#22C55E' : pct >= 70 ? '#5B8CFF' : '#F59E0B';
    }

    window.createAdminModulePage = function createAdminModulePage(config) {
        const BACKEND    = window.BACKEND_URL || 'http://127.0.0.1:8000';
        const MODULE     = config.module;
        const ID         = config.idPrefix;
        const KPI_DEFS   = config.kpiDefs || [];
        const DEMO       = config.demoDecisions || [];
        const confColor  = config.confidenceColor || defaultConfidenceColor;

        let decisionsState = [];
        let filter = 'all';

        // Delegates to the shared client (js/api.js) so a 401 signs the user
        // out instead of silently rendering demoDecisions as if they were live
        // data. The local fallback keeps this file working if api.js is not
        // loaded for some reason.
        async function apiFetch(path, opts = {}) {
            if (window.NOApi && window.NOApi.fetch) {
                return window.NOApi.fetch(path, { timeoutMs: 4000, ...opts });
            }
            try {
                const token = localStorage.getItem('neuralorbit_token');
                const res = await fetch(BACKEND + path, {
                    ...opts,
                    signal: AbortSignal.timeout(4000),
                    headers: {
                        'Content-Type': 'application/json',
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                        ...(opts.headers || {}),
                    },
                });
                if (!res.ok) return null;
                return await res.json();
            } catch { return null; }
        }

        function badge(d) {
            if (d.observe_only)  return `<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(100,116,139,.15);color:#94a3b8;font-weight:600;">OBSERVE ONLY</span>`;
            if (d.auto_executed) return `<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(34,197,94,.15);color:#22C55E;font-weight:600;">AUTO-APPLIED</span>`;
            if (d.outcome === 'rejected') return `<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(239,68,68,.15);color:#EF4444;font-weight:600;">REJECTED</span>`;
            return `<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(245,158,11,.15);color:#F59E0B;font-weight:600;">PENDING</span>`;
        }

        function confBar(c) {
            const pct = Math.round((c || 0) * 100);
            const col = confColor(pct);
            return `<div style="display:flex;align-items:center;gap:6px;" role="img" aria-label="Confidence ${pct} percent">
                <div style="flex:1;height:4px;background:rgba(255,255,255,.08);border-radius:2px;overflow:hidden;">
                    <div style="height:100%;width:${pct}%;background:${col};border-radius:2px;"></div>
                </div>
                <span style="font-size:11px;color:${col};font-weight:600;min-width:30px;">${pct}%</span>
            </div>`;
        }

        function kpiCard(def, val) {
            const display = val != null ? `${def.prefix || ''}${val}${def.suffix || ''}` : '—';
            return `<div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;display:flex;flex-direction:column;gap:8px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <div style="width:32px;height:32px;border-radius:8px;background:${def.color}1a;display:flex;align-items:center;justify-content:center;" aria-hidden="true">
                        <i class="bi ${def.icon}" style="color:${def.color};font-size:15px;"></i>
                    </div>
                    <span style="font-size:12px;color:var(--muted);font-weight:500;">${escHtml(def.label)}</span>
                </div>
                <div style="font-size:28px;font-weight:700;color:var(--text);">${escHtml(display)}</div>
            </div>`;
        }

        function decisionRows(list) {
            const filtered = filter === 'all' ? list : list.filter(d =>
                filter === 'observe'  ? d.observe_only :
                filter === 'auto'     ? d.auto_executed :
                filter === 'pending'  ? (d.outcome === 'pending' && !d.observe_only) :
                d.outcome === filter
            );
            if (!filtered.length) {
                return `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--muted);">No decisions match this filter.</td></tr>`;
            }
            return filtered.map(d => `
                <tr style="cursor:pointer;transition:background 0.15s;"
                    onmouseover="this.style.background='rgba(255,255,255,.03)'"
                    onmouseout="this.style.background='transparent'"
                    onclick="window._${ID}Detail && window._${ID}Detail('${d.id}')"
                    tabindex="0" role="button" aria-label="View details for decision: ${escHtml(d.action)}">
                    <td style="padding:12px 16px;font-size:13px;color:var(--text);max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escHtml(d.action)}</td>
                    <td style="padding:12px 16px;">${badge(d)}</td>
                    <td style="padding:12px 16px;min-width:100px;">${confBar(d.confidence)}</td>
                    <td style="padding:12px 16px;font-size:11px;color:var(--muted);">${d.created_at ? String(d.created_at).slice(0, 10) : '—'}</td>
                    <td style="padding:12px 16px;">
                        ${d.outcome === 'pending' && !d.observe_only ? `
                            <div style="display:flex;gap:6px;">
                                <button onclick="event.stopPropagation();window._${ID}Action && window._${ID}Action('${d.id}','applied')"
                                    aria-label="Approve decision"
                                    style="padding:4px 10px;border-radius:6px;border:none;background:rgba(34,197,94,.15);color:#22C55E;font-size:11px;font-weight:600;cursor:pointer;">Approve</button>
                                <button onclick="event.stopPropagation();window._${ID}Action && window._${ID}Action('${d.id}','rejected')"
                                    aria-label="Reject decision"
                                    style="padding:4px 10px;border-radius:6px;border:none;background:rgba(239,68,68,.15);color:#EF4444;font-size:11px;font-weight:600;cursor:pointer;">Reject</button>
                            </div>
                        ` : '—'}
                    </td>
                </tr>`).join('');
        }

        function renderPage(analytics, decisions, isOffline) {
            const content = document.getElementById('page-content');
            if (!content) return;
            decisionsState = decisions;
            filter = 'all';

            const kpis = analytics?.kpis || {};
            const statusBadge = isOffline
                ? '<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(245,158,11,.12);color:#F59E0B;font-weight:600;">BACKEND OFFLINE</span>'
                : (analytics
                    ? '<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(34,197,94,.12);color:#22C55E;font-weight:600;">LIVE</span>'
                    : '<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(148,163,184,.1);color:#94A3B8;font-weight:600;">NO DATA YET</span>');

            content.innerHTML = `
                <div style="padding:24px;display:flex;flex-direction:column;gap:24px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div>
                            <h1 style="font-size:22px;font-weight:700;color:var(--text);margin:0;">${escHtml(config.title)} <span style="font-size:14px;font-weight:500;color:var(--muted);">— Admin View</span></h1>
                            <p style="font-size:13px;color:var(--muted);margin:4px 0 0;">${escHtml(config.subtitle)}</p>
                        </div>
                        ${statusBadge}
                    </div>

                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;">
                        ${KPI_DEFS.map(def => kpiCard(def, kpis[def.key])).join('')}
                    </div>

                    <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;">
                        <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
                            <span style="font-size:14px;font-weight:600;color:var(--text);">${escHtml(config.title)} Decisions (All Users)</span>
                            <div style="display:flex;gap:6px;" id="${ID}-filter-btns" role="group" aria-label="Filter decisions by status">
                                ${['all', 'pending', 'observe', 'auto', 'rejected'].map(f =>
                                    `<button onclick="window._${ID}Filter && window._${ID}Filter('${f}')" id="${ID}-f-${f}"
                                        aria-pressed="${f === 'all' ? 'true' : 'false'}"
                                        style="padding:4px 12px;border-radius:6px;border:none;cursor:pointer;font-size:11px;font-weight:600;
                                        background:${f === 'all' ? 'var(--accent)' : 'rgba(255,255,255,.06)'};
                                        color:${f === 'all' ? 'white' : 'var(--muted)'};">${f.charAt(0).toUpperCase() + f.slice(1)}</button>`
                                ).join('')}
                            </div>
                        </div>
                        <div style="overflow-x:auto;">
                            <table style="width:100%;border-collapse:collapse;">
                                <caption class="sr-only" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);">${escHtml(config.title)} decisions, all users</caption>
                                <thead>
                                    <tr style="border-bottom:1px solid var(--border);">
                                        <th scope="col" style="padding:10px 16px;text-align:left;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Action</th>
                                        <th scope="col" style="padding:10px 16px;text-align:left;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Status</th>
                                        <th scope="col" style="padding:10px 16px;text-align:left;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Confidence</th>
                                        <th scope="col" style="padding:10px 16px;text-align:left;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Date</th>
                                        <th scope="col" style="padding:10px 16px;text-align:left;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="${ID}-tbody">${decisionRows(decisions)}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="${ID}-drawer" style="display:none;position:fixed;top:0;right:0;width:400px;max-width:92vw;height:100vh;background:var(--card);border-left:1px solid var(--border);z-index:999;overflow-y:auto;padding:24px;box-sizing:border-box;" role="dialog" aria-label="Decision detail">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
                        <span style="font-size:15px;font-weight:700;color:var(--text);">Decision Detail</span>
                        <button onclick="document.getElementById('${ID}-drawer').style.display='none'" aria-label="Close decision detail" style="background:none;border:none;color:var(--muted);font-size:20px;cursor:pointer;">&times;</button>
                    </div>
                    <div id="${ID}-drawer-body" style="color:var(--text);font-size:13px;"></div>
                </div>
            `;

            window[`_${ID}Filter`] = function (f) {
                filter = f;
                document.getElementById(`${ID}-tbody`).innerHTML = decisionRows(decisionsState);
                document.querySelectorAll(`#${ID}-filter-btns button`).forEach(btn => {
                    const isActive = btn.id === `${ID}-f-${f}`;
                    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
                    btn.style.background = isActive ? 'var(--accent)' : 'rgba(255,255,255,.06)';
                    btn.style.color = isActive ? 'white' : 'var(--muted)';
                });
            };

            window[`_${ID}Detail`] = function (id) {
                const d = decisionsState.find(x => x.id === id);
                if (!d) return;
                const drawer = document.getElementById(`${ID}-drawer`);
                document.getElementById(`${ID}-drawer-body`).innerHTML = `
                    <div style="margin-bottom:12px;">${badge(d)}</div>
                    <p style="font-weight:600;margin:0 0 12px;">${escHtml(d.action)}</p>
                    <div style="background:var(--surface);border-radius:8px;padding:12px;margin-bottom:12px;">
                        <p style="font-size:12px;color:var(--muted);margin:0 0 4px;">Reasoning</p>
                        <p style="margin:0;color:var(--text);line-height:1.5;">${escHtml(d.reasoning || '—')}</p>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;">
                        <div style="background:var(--surface);border-radius:8px;padding:10px;"><p style="color:var(--muted);margin:0 0 4px;">Confidence</p><p style="color:var(--text);font-weight:600;margin:0;">${Math.round((d.confidence || 0) * 100)}%</p></div>
                        <div style="background:var(--surface);border-radius:8px;padding:10px;"><p style="color:var(--muted);margin:0 0 4px;">Date</p><p style="color:var(--text);font-weight:600;margin:0;">${d.created_at ? String(d.created_at).slice(0, 10) : '—'}</p></div>
                    </div>
                `;
                drawer.style.display = 'block';
            };

            window[`_${ID}Action`] = async function (id, outcome) {
                const res = await apiFetch(`/api/v1/decisions/${id}/outcome`, {
                    method: 'PATCH', body: JSON.stringify({ outcome }),
                });
                if (res) {
                    const d = decisionsState.find(x => x.id === id);
                    if (d) { d.outcome = outcome; d.auto_executed = false; }
                    document.getElementById(`${ID}-tbody`).innerHTML = decisionRows(decisionsState);
                }
            };
        }

        return async function loadAdminModulePage() {
            const [analytics, decisionsData] = await Promise.all([
                apiFetch('/api/v1/analytics/overview?module=' + MODULE),
                apiFetch('/api/v1/decisions?module=' + MODULE + '&all=true&limit=50'),
            ]);
            const isOffline = !analytics && !decisionsData;
            const decisions = (decisionsData && decisionsData.decisions && decisionsData.decisions.length)
                ? decisionsData.decisions
                : (isOffline ? DEMO : []);
            renderPage(analytics, decisions, isOffline);
        };
    };
})();
