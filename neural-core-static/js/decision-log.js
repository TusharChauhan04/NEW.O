/* ============================================================
   decision-log.js — NeuralOrbit AI Decision Log (Real Backend)
   Admin: ALL decisions across all users + export + replay
   User:  Own decisions only + own toggles
   Falls back to static demo data if backend unavailable.
   ============================================================ */

(function () {
    'use strict';

    const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';

    /* ── Helpers ─────────────────────────────────────────────── */
    async function apiFetch(path, opts = {}) {
        try {
            const token = localStorage.getItem('neuralorbit_token');
            const res = await fetch(BACKEND + path, {
                ...opts,
                signal: AbortSignal.timeout(5000),
                headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers || {}) },
            });
            if (!res.ok) return null;
            return await res.json();
        } catch { return null; }
    }

    /* ── Demo fallback data ───────────────────────────────────── */
    const DEMO_DECISIONS = [
        { id: 'DEC-001', created_at: '2026-02-17T09:14:22Z', module: 'CRM', action: 'Auto-assigned lead to top performer', confidence: 94, outcome: 'applied', override_enabled: false, reasoning: 'Maximized expected conversion value.', state_snapshot: 'Lead score: 82, Reps available: 4', alternatives: ['Round-robin assignment', 'Assign to newest rep', 'Queue for manual review'] },
        { id: 'DEC-002', created_at: '2026-02-17T08:47:15Z', module: 'Marketing', action: 'Paused underperforming ad campaign', confidence: 97, outcome: 'applied', override_enabled: false, reasoning: 'Cost threshold exceeded with declining ROI.', state_snapshot: 'CTR: 0.3%, CPA: $142, Budget: 72%', alternatives: ['Reduce budget 50%', 'A/B test creatives', 'Monitor 24h'] },
        { id: 'DEC-003', created_at: '2026-02-17T07:33:08Z', module: 'Shield', action: 'Blocked suspicious login attempt', confidence: 99, outcome: 'applied', override_enabled: false, reasoning: 'Threat score exceeded critical threshold.', state_snapshot: 'IP: VPN, Failed attempts: 3', alternatives: ['2FA challenge', 'Allow + monitor', 'Lock temp'] },
        { id: 'DEC-004', created_at: '2026-02-17T06:12:44Z', module: 'Website', action: 'Deployed A/B test variant B', confidence: 86, outcome: 'pending', override_enabled: true, reasoning: 'Statistical significance at 95% CI.', state_snapshot: 'Variant B: +0.9% vs A', alternatives: ['Continue', 'Deploy A', 'Hybrid C'] },
        { id: 'DEC-005', created_at: '2026-02-16T22:58:31Z', module: 'CRM', action: 'Triggered re-engagement sequence', confidence: 89, outcome: 'applied', override_enabled: false, reasoning: 'Retention value > acquisition cost.', state_snapshot: '47 dormant, avg 34 days', alternatives: ['Manual outreach', 'Discount offer', 'Wait'] },
        { id: 'DEC-006', created_at: '2026-02-16T19:22:17Z', module: 'Marketing', action: 'Increased bid on high-intent keywords', confidence: 91, outcome: 'applied', override_enabled: false, reasoning: 'ROI positive at current conversion rates.', state_snapshot: "Keyword: 'enterprise AI', CPC: $12.40", alternatives: ['Maintain bids', 'Long-tail shift', 'Pause'] },
        { id: 'DEC-007', created_at: '2026-02-16T15:45:03Z', module: 'Shield', action: 'Escalated compliance alert', confidence: 96, outcome: 'applied', override_enabled: false, reasoning: 'Regulatory risk detected.', state_snapshot: 'Sensitive data access, user:standard', alternatives: ['Log+monitor', 'Restrict silently', 'Notify user'] },
        { id: 'DEC-008', created_at: '2026-02-16T12:10:00Z', module: 'CRM', action: 'Pipeline stage auto-advanced for hot lead', confidence: 92, outcome: 'applied', override_enabled: false, reasoning: 'All deal-closing signals positive.', state_snapshot: 'Score +24, Meeting booked, Budget OK', alternatives: ['Wait manual', 'Send confirm email', 'Flag mgr'] },
        { id: 'DEC-009', created_at: '2026-02-15T18:30:44Z', module: 'Website', action: 'Personalized homepage for returning visitor', confidence: 88, outcome: 'applied', override_enabled: false, reasoning: 'FinTech social proof surfaced.', state_snapshot: '3 visits, Viewed: Pricing, FinTech', alternatives: ['Default home', 'Redirect pricing', 'Demo popup'] },
        { id: 'DEC-010', created_at: '2026-02-15T10:05:22Z', module: 'Marketing', action: 'Sent personalized email to trial segment', confidence: 85, outcome: 'applied', override_enabled: false, reasoning: 'Day 7 peak conversion window.', state_snapshot: 'Segment: Day-7 trial, Conv: 34%', alternatives: ['Wait day 14', 'CSM call', 'In-app only'] },
    ];

    const moduleColors = { CRM: '#5B8CFF', Marketing: '#8B5CF6', Shield: '#F59E0B', Website: '#22C55E' };

    /* ── State ────────────────────────────────────────────────── */
    let allDecisions = [];
    let overrides = {};
    let selectedId = null;
    let filterQuery = '';
    let usingDemo = false;

    /* ── Load from backend / fallback ───────────────────────────── */
    async function fetchDecisions() {
        const isAdmin = window.CURRENT_ROLE === 'admin';
        const moduleKey = window.CURRENT_MODULE || 'neural-orbit';

        let path = '/api/v1/decisions?limit=50';
        if (isAdmin) path += '&all=true';
        if (moduleKey !== 'neural-orbit') {
            const moduleMap = { crm: 'CRM', marketing: 'Marketing', shield: 'Shield', website: 'Website' };
            const mod = moduleMap[moduleKey];
            if (mod) path += `&module=${mod}`;
        }

        const data = await apiFetch(path);
        if (data && Array.isArray(data.decisions)) {
            usingDemo = false;
            return data.decisions;
        }

        // Fallback: filter demo data by module
        usingDemo = true;
        if (moduleKey === 'neural-orbit') return DEMO_DECISIONS;
        const map = { crm: 'CRM', marketing: 'Marketing', shield: 'Shield', website: 'Website' };
        const name = map[moduleKey];
        return name ? DEMO_DECISIONS.filter(d => d.module === name) : DEMO_DECISIONS;
    }

    /* ── Main render ──────────────────────────────────────────── */
    window.loadDecisionLog = async function () {
        const content = document.getElementById('page-content');
        if (!content) return;

        const isAdmin = window.CURRENT_ROLE === 'admin';
        const moduleKey = window.CURRENT_MODULE || 'neural-orbit';
        const isGlobal = moduleKey === 'neural-orbit';

        // Render skeleton first
        content.innerHTML = buildShell(isAdmin, isGlobal);
        renderSkeleton();

        // Fetch real data
        allDecisions = await fetchDecisions();
        allDecisions.forEach(d => { overrides[d.id] = d.override_enabled || false; });
        selectedId = null;
        filterQuery = '';

        renderRows();
        bindEvents();

        if (usingDemo) showDemoBanner(content);
    };

    function buildShell(isAdmin, isGlobal) {
        return `
      <div class="page-animate" style="display:flex;flex-direction:column;height:100%;overflow:hidden;">
        <!-- Header -->
        <div style="padding:24px 24px 16px;flex-shrink:0;">
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <div>
              <h1 style="font-size:22px;font-weight:600;color:var(--text);">AI Decision Log</h1>
              <p style="font-size:13px;color:var(--muted);margin-top:4px;">
                ${isGlobal && isAdmin ? 'All clients — every AI decision tracked, auditable, and overridable' : 'Transparent, explainable AI — every decision tracked and auditable'}
              </p>
            </div>
            <div style="display:flex;align-items:center;gap:10px;">
              <!-- Search -->
              <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:10px;border:1px solid var(--border);background:rgba(30,41,59,0.5);">
                <i class="bi bi-search" style="color:var(--dim);font-size:13px;"></i>
                <input id="decision-search" type="text" placeholder="Search decisions…" aria-label="Search decisions" style="background:transparent;border:none;outline:none;color:var(--text);font-size:13px;width:160px;font-family:var(--font);" />
              </div>
              ${isAdmin ? `
              <!-- Admin: Export button -->
              <button id="dl-export-btn" style="display:flex;align-items:center;gap:6px;padding:8px 12px;border-radius:10px;border:1px solid var(--border);background:transparent;color:var(--muted);font-size:13px;cursor:pointer;font-family:var(--font);">
                <i class="bi bi-download" style="font-size:12px;"></i> Export
              </button>` : ''}
            </div>
          </div>
          ${usingDemo ? '' : ''}
        </div>

        <!-- Table + Drawer -->
        <div style="flex:1;display:flex;overflow:hidden;padding:0 24px 24px;gap:0;">
          <div style="flex:1;overflow-y:auto;min-width:0;">
            <div style="border-radius:14px;border:1px solid var(--border-light);overflow:hidden;background:rgba(17,24,39,0.6);">
              <!-- Column headers -->
              <div style="display:grid;grid-template-columns:140px 100px 1fr 80px 120px 100px;gap:16px;padding:12px 20px;border-bottom:1px solid var(--border-light);background:rgba(17,24,39,0.8);">
                ${['TIMESTAMP', 'MODULE', 'ACTION TAKEN', 'REWARD', 'CONFIDENCE', 'OVERRIDE'].map(h =>
            `<span style="font-size:11px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;">${h}</span>`
        ).join('')}
              </div>
              <div id="decision-rows"></div>
            </div>
          </div>

          <!-- Side Drawer -->
          <div id="decision-drawer" style="width:0;overflow:hidden;transition:width .3s ease;flex-shrink:0;border-left:0px solid var(--border);background:var(--surface-low);display:flex;flex-direction:column;">
            <div id="drawer-inner" style="width:400px;max-width:88vw;display:flex;flex-direction:column;height:100%;overflow-y:auto;opacity:0;transition:opacity .2s;">
              <div style="padding:20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
                <div>
                  <div style="font-size:11px;font-weight:600;color:var(--dim);letter-spacing:.05em;">DECISION DETAILS</div>
                  <div id="drawer-id" style="font-size:14px;font-weight:600;color:var(--text);margin-top:4px;">—</div>
                </div>
                <button id="drawer-close" style="padding:8px;border-radius:8px;background:transparent;border:none;cursor:pointer;color:var(--muted);display:flex;align-items:center;justify-content:center;" aria-label="Close">
                  <i class="bi bi-x-lg" style="font-size:14px;"></i>
                </button>
              </div>
              <div id="drawer-body" style="padding:20px;display:flex;flex-direction:column;gap:20px;"></div>
            </div>
          </div>
        </div>
      </div>`;
    }

    function renderSkeleton() {
        const rows = document.getElementById('decision-rows');
        if (!rows) return;
        rows.innerHTML = Array(5).fill(0).map(() => `
      <div style="display:grid;grid-template-columns:140px 100px 1fr 80px 120px 100px;gap:16px;padding:16px 20px;border-bottom:1px solid rgba(91,140,255,.05);">
        ${Array(6).fill(0).map(() => `<div style="height:16px;border-radius:6px;background:rgba(91,140,255,.08);animation:pulse 1.5s ease-in-out infinite;"></div>`).join('')}
      </div>`).join('');
    }

    /* ── Row builder ─────────────────────────────────────────── */
    function buildRow(d) {
        const color = moduleColors[d.module] || '#94A3B8';
        const time = (d.created_at || d.timestamp || '').split('T')[1]?.slice(0, 8) || d.created_at?.split(' ')[1] || '—';
        const isOn = overrides[d.id] || false;
        const isSel = selectedId === d.id;
        const conf = d.confidence || 0;
        const reward = typeof d.reward_score === 'number' ? d.reward_score : 0.85;
        const rwColor = reward >= 0.9 ? '#22C55E' : reward >= 0.8 ? '#5B8CFF' : '#F59E0B';
        const cfColor = conf >= 95 ? '#22C55E' : conf >= 90 ? '#5B8CFF' : '#F59E0B';
        const isAdmin = window.CURRENT_ROLE === 'admin';

        return `
      <div class="dl-row" data-id="${esc(d.id)}" style="display:grid;grid-template-columns:140px 100px 1fr 80px 120px 100px;gap:16px;padding:16px 20px;border-bottom:1px solid rgba(91,140,255,.05);cursor:pointer;transition:background .15s;${isSel ? 'background:rgba(91,140,255,.06);' : ''}">
        <div style="display:flex;align-items:center;gap:6px;">
          <i class="bi bi-clock" style="font-size:12px;color:var(--dim);"></i>
          <span style="font-size:12px;color:var(--muted);font-family:monospace;">${esc(time)}</span>
        </div>
        <div style="display:flex;align-items:center;">
          <span style="padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;color:${color};background:${color}18;">${esc(d.module)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;overflow:hidden;">
          <span style="font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(d.action)}</span>
          <i class="bi bi-chevron-right dl-chevron" style="flex-shrink:0;opacity:0;transition:opacity .15s;font-size:12px;color:var(--dim);"></i>
        </div>
        <div style="display:flex;align-items:center;">
          <span style="font-size:13px;font-weight:600;font-family:monospace;color:${rwColor};">${reward.toFixed(2)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="flex:1;height:6px;border-radius:99px;background:var(--surface);overflow:hidden;">
            <div style="height:100%;width:${conf}%;background:${cfColor};border-radius:99px;"></div>
          </div>
          <span style="font-size:12px;color:var(--muted);font-family:monospace;flex-shrink:0;">${conf}%</span>
        </div>
        <div style="display:flex;align-items:center;">
          <button class="dl-toggle" data-id="${esc(d.id)}"
            style="width:40px;height:20px;border-radius:99px;border:none;cursor:${isAdmin ? 'pointer' : 'not-allowed'};position:relative;background:${isOn ? '#F59E0B' : '#334155'};transition:background .2s;flex-shrink:0;opacity:${isAdmin ? 1 : 0.5};"
            ${isAdmin ? '' : 'disabled'} aria-label="Toggle override">
            <div class="dl-pip" style="position:absolute;top:2px;left:${isOn ? '22px' : '2px'};width:16px;height:16px;border-radius:50%;background:white;box-shadow:0 1px 3px rgba(0,0,0,.3);transition:left .2s;"></div>
          </button>
        </div>
      </div>`;
    }

    function renderRows() {
        const container = document.getElementById('decision-rows');
        if (!container) return;

        const filtered = allDecisions.filter(d =>
            !filterQuery ||
            (d.action || '').toLowerCase().includes(filterQuery) ||
            (d.module || '').toLowerCase().includes(filterQuery) ||
            (d.id || '').toLowerCase().includes(filterQuery)
        );

        if (!filtered.length) {
            container.innerHTML = `<div style="padding:60px 24px;text-align:center;color:var(--dim);">
        <i class="bi bi-inbox" style="font-size:32px;display:block;margin-bottom:12px;"></i>
        <div style="font-size:14px;">No decisions found</div>
        <div style="font-size:12px;margin-top:6px;">AI decisions will appear here as integrations become active.</div>
      </div>`;
            return;
        }

        container.innerHTML = filtered.map(d => buildRow(d)).join('');

        // Row click → drawer
        container.querySelectorAll('.dl-row').forEach(row => {
            row.addEventListener('click', e => {
                if (e.target.closest('.dl-toggle')) return;
                openDrawer(row.dataset.id);
            });
            row.addEventListener('mouseenter', () => { if (row.dataset.id !== selectedId) row.style.background = 'rgba(91,140,255,.04)'; });
            row.addEventListener('mouseleave', () => { if (row.dataset.id !== selectedId) row.style.background = ''; });
        });

        // Toggle click → backend save
        container.querySelectorAll('.dl-toggle').forEach(btn => {
            btn.addEventListener('click', async e => {
                e.stopPropagation();
                const id = btn.dataset.id;
                const val = !overrides[id];
                overrides[id] = val;

                // Optimistic UI update
                btn.style.background = val ? '#F59E0B' : '#334155';
                const pip = btn.querySelector('.dl-pip');
                if (pip) pip.style.left = val ? '22px' : '2px';

                // Save to backend (non-blocking)
                if (!usingDemo) {
                    const res = await apiFetch(`/api/v1/decisions/${encodeURIComponent(id)}/override?enabled=${val}`, { method: 'POST' });
                    if (!res) {
                        // Revert on failure
                        overrides[id] = !val;
                        btn.style.background = !val ? '#F59E0B' : '#334155';
                        if (pip) pip.style.left = !val ? '22px' : '2px';
                    }
                }
            });
        });
    }

    /* ── Drawer ───────────────────────────────────────────────── */
    function openDrawer(id) {
        selectedId = id;
        const d = allDecisions.find(x => x.id === id);
        if (!d) return;

        const drawer = document.getElementById('decision-drawer');
        const drawerInner = document.getElementById('drawer-inner');
        const drawerId = document.getElementById('drawer-id');
        const drawerBody = document.getElementById('drawer-body');
        if (!drawer || !drawerId || !drawerBody) return;

        drawer.style.width = '400px';
        drawer.style.borderLeftWidth = '1px';
        setTimeout(() => { if (drawerInner) drawerInner.style.opacity = '1'; }, 50);

        drawerId.textContent = d.id;
        const color = moduleColors[d.module] || '#94A3B8';
        const conf = d.confidence || 0;
        const cfColor = conf >= 95 ? '#22C55E' : conf >= 90 ? '#5B8CFF' : '#F59E0B';
        const isAdmin = window.CURRENT_ROLE === 'admin';
        const alts = Array.isArray(d.alternatives) ? d.alternatives : [];

        drawerBody.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div style="padding:12px;border-radius:10px;background:rgba(30,41,59,.5);">
          <div style="font-size:10px;font-weight:600;color:var(--dim);text-transform:uppercase;margin-bottom:4px;">Module</div>
          <div style="font-size:13px;font-weight:600;color:${color};">${esc(d.module)}</div>
        </div>
        <div style="padding:12px;border-radius:10px;background:rgba(30,41,59,.5);">
          <div style="font-size:10px;font-weight:600;color:var(--dim);text-transform:uppercase;margin-bottom:4px;">Confidence</div>
          <div style="font-size:13px;font-weight:600;color:${cfColor};">${conf}%</div>
        </div>
      </div>
      <div>
        <div style="font-size:11px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;">Action Taken</div>
        <div style="font-size:13px;color:var(--text);line-height:1.5;">${esc(d.action)}</div>
      </div>
      <div style="border-radius:10px;padding:16px;border:1px solid var(--border);background:rgba(17,24,39,.8);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;">
          <i class="bi bi-check-circle" style="color:var(--accent);font-size:13px;"></i>
          <span style="font-size:11px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.05em;">State Snapshot</span>
        </div>
        <p style="font-size:12px;color:var(--muted);line-height:1.6;margin:0;">${esc(d.state_snapshot || d.reasoning || '—')}</p>
      </div>
      <div style="border-radius:10px;padding:16px;border:1px solid var(--border);background:rgba(17,24,39,.8);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;">
          <i class="bi bi-check-circle" style="color:var(--success);font-size:13px;"></i>
          <span style="font-size:11px;font-weight:600;color:var(--success);text-transform:uppercase;letter-spacing:.05em;">Reward Logic</span>
        </div>
        <p style="font-size:12px;color:var(--muted);line-height:1.6;margin:0;">${esc(d.reasoning || '—')}</p>
      </div>
      ${alts.length ? `
      <div style="border-radius:10px;padding:16px;border:1px solid var(--border);background:rgba(17,24,39,.8);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;">
          <i class="bi bi-exclamation-circle" style="color:var(--warning);font-size:13px;"></i>
          <span style="font-size:11px;font-weight:600;color:var(--warning);text-transform:uppercase;letter-spacing:.05em;">Alternatives Rejected</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          ${alts.map(alt => `
            <div style="display:flex;align-items:center;gap:8px;">
              <i class="bi bi-x-circle-fill" style="font-size:11px;color:var(--danger);flex-shrink:0;"></i>
              <span style="font-size:12px;color:var(--muted);">${esc(alt)}</span>
            </div>`).join('')}
        </div>
      </div>` : ''}
      <!-- Phase 4 Milestone 1: Approve / Reject feedback buttons -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <button id="dl-approve-btn" data-id="${esc(d.id)}" style="padding:12px;border-radius:10px;border:1px solid rgba(34,197,94,.3);cursor:pointer;background:rgba(34,197,94,.08);color:#22C55E;font-size:13px;font-weight:600;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:6px;transition:background .15s;">
          <i class="bi bi-check-lg"></i> Approve
        </button>
        <button id="dl-reject-btn" data-id="${esc(d.id)}" style="padding:12px;border-radius:10px;border:1px solid rgba(239,68,68,.3);cursor:pointer;background:rgba(239,68,68,.08);color:#EF4444;font-size:13px;font-weight:600;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:6px;transition:background .15s;">
          <i class="bi bi-x-lg"></i> Reject
        </button>
      </div>
      ${d.outcome === 'applied' ? `<div style="padding:8px 12px;border-radius:8px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);font-size:12px;color:#22C55E;display:flex;align-items:center;gap:6px;"><i class="bi bi-check-circle-fill"></i> Decision approved — AI learning updated</div>` : d.outcome === 'rejected' ? `<div style="padding:8px 12px;border-radius:8px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);font-size:12px;color:#EF4444;display:flex;align-items:center;gap:6px;"><i class="bi bi-x-circle-fill"></i> Decision rejected — AI will adjust</div>` : ''}
      ${isAdmin ? `
      <button id="replay-btn" data-id="${esc(d.id)}" style="width:100%;padding:13px;border-radius:10px;border:none;cursor:pointer;background:linear-gradient(135deg,#5B8CFF,#3B6FE0);color:white;font-size:13px;font-weight:600;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:8px;">
        <i class="bi bi-arrow-clockwise"></i> Replay Decision
      </button>` : ''}`;

        // Replay button (admin only)
        document.getElementById('replay-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('replay-btn');
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Replaying…'; }
            if (!usingDemo) await apiFetch(`/api/v1/decisions/${encodeURIComponent(id)}/execute`, { method: 'POST' });
            setTimeout(() => { if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Replay Decision'; } }, 2000);
        });

        // ── Approve / Reject buttons (Phase 4 Milestone 1 — Learning Feedback) ──
        document.getElementById('dl-approve-btn')?.addEventListener('click', async () => {
            await _setOutcome(id, 'applied');
        });
        document.getElementById('dl-reject-btn')?.addEventListener('click', async () => {
            await _setOutcome(id, 'rejected');
        });


        // Highlight selected row
        document.querySelectorAll('.dl-row').forEach(row => {
            row.style.background = row.dataset.id === id ? 'rgba(91,140,255,.06)' : '';
        });
        document.querySelectorAll('.dl-chevron').forEach(ch => {
            ch.style.opacity = ch.closest('.dl-row')?.dataset.id === id ? '1' : '0';
        });
    }

    function closeDrawer() {
        const drawer = document.getElementById('decision-drawer');
        const drawerInner = document.getElementById('drawer-inner');
        if (drawerInner) drawerInner.style.opacity = '0';
        setTimeout(() => {
            if (drawer) { drawer.style.width = '0'; drawer.style.borderLeftWidth = '0px'; }
        }, 200);
        selectedId = null;
        document.querySelectorAll('.dl-row').forEach(r => { r.style.background = ''; });
        document.querySelectorAll('.dl-chevron').forEach(ch => { ch.style.opacity = '0'; });
    }

    /* ── Events ───────────────────────────────────────────────── */
    function bindEvents() {
        document.getElementById('drawer-close')?.addEventListener('click', closeDrawer);

        // Search filter
        document.getElementById('decision-search')?.addEventListener('input', e => {
            filterQuery = e.target.value.toLowerCase().trim();
            renderRows();
        });

        // Admin export (CSV)
        document.getElementById('dl-export-btn')?.addEventListener('click', () => {
            const csv = [
                'ID,Timestamp,Module,Action,Confidence,Outcome,Override',
                ...allDecisions.map(d => [
                    d.id, d.created_at, d.module, `"${(d.action || '').replace(/"/g, '""')}"`,
                    d.confidence, d.outcome, d.override_enabled
                ].join(','))
            ].join('\n');
            const a = document.createElement('a');
            a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
            a.download = `decision-log-${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
        });
    }

    /* ── Demo banner ─────────────────────────────────────────── */
    function showDemoBanner(content) {
        const header = content.querySelector('[style*="padding:24px"]');
        if (!header) return;
        const banner = document.createElement('div');
        banner.style.cssText = 'margin:0 24px 12px;padding:10px 14px;border-radius:8px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);font-size:12px;color:#F59E0B;display:flex;align-items:center;gap:8px;flex-shrink:0;';
        banner.innerHTML = '<i class="bi bi-info-circle"></i> Showing demo data — connect your integrations to see live decisions';
        header.after(banner);
    }

    /* ── Outcome setter (Phase 4 Milestone 1) ──────────────────── */
    async function _setOutcome(id, outcome) {
        const appBtn = document.getElementById('dl-approve-btn');
        const rejBtn = document.getElementById('dl-reject-btn');
        if (appBtn) appBtn.disabled = true;
        if (rejBtn) rejBtn.disabled = true;

        if (!usingDemo) {
            const res = await apiFetch(`/api/v1/decisions/${encodeURIComponent(id)}/outcome`, {
                method:  'PATCH',
                body:    JSON.stringify({ outcome }),
            });
            if (res) {
                // Update local record so the status badge shows immediately
                const dec = allDecisions.find(d => d.id === id);
                if (dec) dec.outcome = outcome;

                // Show instant feedback badge under the buttons
                const feedbackEl = document.createElement('div');
                const isApproved = outcome === 'applied';
                feedbackEl.style.cssText = `padding:8px 12px;border-radius:8px;margin-top:4px;font-size:12px;display:flex;align-items:center;gap:6px;background:${isApproved ? 'rgba(34,197,94,.08)' : 'rgba(239,68,68,.08)'};border:1px solid ${isApproved ? 'rgba(34,197,94,.2)' : 'rgba(239,68,68,.2)'};color:${isApproved ? '#22C55E' : '#EF4444'};`;
                feedbackEl.innerHTML = isApproved
                    ? '<i class="bi bi-check-circle-fill"></i> Approved — AI learning updated'
                    : '<i class="bi bi-x-circle-fill"></i> Rejected — AI will adjust';

                const approveBtn = document.getElementById('dl-approve-btn');
                approveBtn?.parentElement?.after(feedbackEl);

                // Show toast
                if (window.showToast) window.showToast(isApproved ? '✅ Decision approved' : '❌ Decision rejected', isApproved ? 'success' : 'warning');
            } else {
                if (appBtn) appBtn.disabled = false;
                if (rejBtn) rejBtn.disabled = false;
                if (window.showToast) window.showToast('Could not update decision — backend offline', 'error');
            }
        } else {
            // Demo mode: just show visual feedback
            if (appBtn) appBtn.disabled = false;
            if (rejBtn) rejBtn.disabled = false;
            if (window.showToast) window.showToast('Connect integrations to enable AI learning', 'info');
        }
    }

    function esc(str) {
        return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

})();
