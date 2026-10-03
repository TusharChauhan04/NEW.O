/* ============================================================
   sandbox.js — AI Sandbox (Real Backend)
   User:  run test scenarios + custom events (sandbox=true flag)
          see AI reward score + inferred decision live
   Admin: client selector (impersonate any user's context) +
          batch run all scenarios + download result JSON
   Events are sent as POST /api/v1/events with sandbox=true
   so they NEVER affect real production data or AI behaviour.
   ============================================================ */

(function () {
    'use strict';

    const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';

    async function apiFetch(path, opts = {}) {
        try {
            const token = localStorage.getItem('neuralorbit_token');
            const res = await fetch(BACKEND + path, {
                ...opts,
                signal: AbortSignal.timeout(8000),
                headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers || {}) },
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                return { __error: err.detail || `HTTP ${res.status}` };
            }
            return await res.json();
        } catch (e) { return { __error: e.message || 'Network error' }; }
    }

    /* ── Pre-built Scenarios ─────────────────────────────────── */
    const SCENARIOS = [
        {
            id: 'scn-001', category: 'CRM', title: 'Hot Lead Assigned',
            icon: 'bi-person-check', color: '#5B8CFF',
            desc: 'Simulates a high-score lead entering your pipeline. Tests whether the AI assigns it to the correct sales rep.',
            event: { module: 'crm', event_type: 'lead_reply', payload: { lead_score: 88, source: 'demo', name: 'Sandbox Corp' } },
        },
        {
            id: 'scn-002', category: 'CRM', title: 'Deal Closed',
            icon: 'bi-trophy', color: '#22C55E',
            desc: 'Simulates a deal closing. Tests reward scoring and pipeline stage transitions.',
            event: { module: 'crm', event_type: 'deal_closed', payload: { deal_value: 15000, rep: 'Alice', stage: 'closed-won' } },
        },
        {
            id: 'scn-003', category: 'Marketing', title: 'Ad Campaign Underperforming',
            icon: 'bi-megaphone', color: '#8B5CF6',
            desc: 'Simulates a campaign where CPA exceeds threshold. Tests if AI pauses or adjusts the campaign.',
            event: { module: 'marketing', event_type: 'ad_fatigue', payload: { campaign_id: 'cmp-042', cpa: 195, cpa_threshold: 120 } },
        },
        {
            id: 'scn-004', category: 'Marketing', title: 'CTR Spike',
            icon: 'bi-graph-up-arrow', color: '#8B5CF6',
            desc: 'Simulates a sudden CTR increase. Tests bid optimization response.',
            event: { module: 'marketing', event_type: 'ctr_increase', payload: { campaign_id: 'cmp-017', ctr_before: 1.2, ctr_after: 3.8 } },
        },
        {
            id: 'scn-005', category: 'Shield', title: 'Suspicious Login Attempt',
            icon: 'bi-shield-exclamation', color: '#F59E0B',
            desc: 'Simulates a login from an unusual location with repeated failures. Tests threat detection and block logic.',
            event: { module: 'shield', event_type: 'threat_blocked', payload: { ip: '185.220.101.42', failed_attempts: 5, vpn: true } },
        },
        {
            id: 'scn-006', category: 'Website', title: 'High-Value Visitor',
            icon: 'bi-person-badge', color: '#22C55E',
            desc: 'Simulates a returning visitor who viewed the pricing page 3 times. Tests personalisation logic.',
            event: { module: 'website', event_type: 'session_value_high', payload: { visits: 4, pages: ['pricing', 'enterprise', 'contact'], time_on_site_s: 320 } },
        },
        {
            id: 'scn-007', category: 'Website', title: 'Form Submission',
            icon: 'bi-envelope-check', color: '#22C55E',
            desc: 'Simulates a contact form submission from the website tracker.',
            event: { module: 'website', event_type: 'form_submit', payload: { form_id: 'contact-demo', email: 'test@example.com' } },
        },
        {
            id: 'scn-008', category: 'NeuralOrbit', title: 'AI Decision Acted On',
            icon: 'bi-cpu', color: '#5B8CFF',
            desc: 'Simulates a user acting on an AI recommendation. Tests reward reinforcement loop.',
            event: { module: 'neural-orbit', event_type: 'insight_acted_on', payload: { insight_id: 'ins-sandbox', action: 'approved' } },
        },
    ];

    const categoryColors = { CRM: '#5B8CFF', Marketing: '#8B5CF6', Shield: '#F59E0B', Website: '#22C55E', NeuralOrbit: '#5B8CFF' };

    /* ── State ───────────────────────────────────────────────── */
    let results = {};   // { [scenario_id]: result }
    let running = {};   // { [scenario_id]: true }
    let batchRunning = false;
    let selectedTargetUser = null;
    let customPayloadStr = '{}';

    /* ── Main entry ──────────────────────────────────────────── */
    window.loadSandbox = async function () {
        const content = document.getElementById('page-content');
        if (!content) return;

        const isAdmin = window.CURRENT_ROLE === 'admin';
        const moduleKey = window.CURRENT_MODULE || 'neural-orbit';

        content.innerHTML = buildPage(isAdmin, moduleKey);
        bindSandboxEvents(isAdmin);
    };

    /* ── Page builder ────────────────────────────────────────── */
    function buildPage(isAdmin, moduleKey) {
        const filtered = moduleKey === 'neural-orbit'
            ? SCENARIOS
            : SCENARIOS.filter(s => s.category.toLowerCase() === moduleKey);

        return `
      <div class="page-animate" style="display:flex;flex-direction:column;height:100%;overflow-y:auto;">
        <div style="padding:24px 24px 0;flex-shrink:0;">

          <!-- Header -->
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:16px;">
              <div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#6366F1,#4F46E5);display:flex;align-items:center;justify-content:center;color:white;flex-shrink:0;">
                <i class="bi bi-play-circle-fill" style="font-size:22px;"></i>
              </div>
              <div>
                <h1 style="font-size:22px;font-weight:700;color:var(--text);line-height:1.2;">AI Sandbox</h1>
                <p style="font-size:13px;color:var(--muted);margin-top:4px;">
                  ${isAdmin
                ? 'Simulate AI events for any client — all runs are sandboxed, never affect live data'
                : 'Test how your AI responds to real scenarios — fully isolated, no production impact'}
                </p>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
              ${isAdmin ? `
              <button id="batch-run-btn" style="display:flex;align-items:center;gap:6px;padding:9px 16px;border-radius:var(--radius);border:1px solid rgba(99,102,241,.4);background:rgba(99,102,241,.08);color:#818CF8;font-size:13px;font-weight:600;cursor:pointer;font-family:var(--font);">
                <i class="bi bi-collection-play" style="font-size:13px;"></i> Batch Run All
              </button>
              <button id="download-results-btn" style="display:flex;align-items:center;gap:6px;padding:9px 16px;border-radius:var(--radius);border:1px solid var(--border);background:transparent;color:var(--muted);font-size:13px;cursor:pointer;font-family:var(--font);">
                <i class="bi bi-download" style="font-size:12px;"></i> Export
              </button>` : ''}
              <div style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:8px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);">
                <i class="bi bi-shield-check" style="font-size:12px;color:#818CF8;"></i>
                <span style="font-size:11px;font-weight:700;color:#818CF8;letter-spacing:.05em;">SANDBOX MODE</span>
              </div>
            </div>
          </div>

          <!-- Admin: client selector -->
          ${isAdmin ? `
          <div style="margin-bottom:20px;padding:16px;border-radius:var(--radius);background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.15);">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <i class="bi bi-person-workspace" style="font-size:14px;color:#EF4444;"></i>
              <span style="font-size:12px;font-weight:600;color:#EF4444;text-transform:uppercase;letter-spacing:.05em;">Run As Client:</span>
              <input id="target-user-input" type="text" aria-label="Target client User ID" placeholder="Paste client User ID (or leave blank to run as yourself)…"
                style="flex:1;min-width:260px;padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:13px;outline:none;font-family:var(--font);" />
              <div id="target-user-status" style="font-size:11px;color:var(--dim);"></div>
            </div>
          </div>` : ''}

          <!-- Info bar -->
          <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:8px;background:rgba(99,102,241,.05);border:1px solid rgba(99,102,241,.1);margin-bottom:24px;font-size:12px;color:var(--muted);">
            <i class="bi bi-info-circle" style="color:#818CF8;font-size:14px;"></i>
            All events are sent with <code style="background:rgba(99,102,241,.1);color:#818CF8;padding:1px 5px;border-radius:4px;">sandbox: true</code> —
            they <strong style="color:var(--text);">never</strong> affect your live AI decisions, rewards, or real data.
            Ideal for testing before going live.
          </div>
        </div>

        <!-- Scenarios Grid + Custom -->
        <div style="padding:0 24px 24px;display:grid;grid-template-columns:1fr 380px;gap:20px;flex:1;min-height:0;">

          <!-- Scenarios -->
          <div style="overflow-y:auto;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;" id="scenario-grid">
              ${filtered.map(s => buildScenarioCard(s)).join('')}
            </div>
          </div>

          <!-- Right panel: Custom Event + Results -->
          <div style="display:flex;flex-direction:column;gap:16px;overflow-y:auto;">

            <!-- Custom Event -->
            <div class="card">
              <div style="font-size:11px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px;">Custom Event</div>
              <div style="display:flex;flex-direction:column;gap:10px;">
                <select id="custom-module" style="padding:9px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:13px;font-family:var(--font);outline:none;">
                  <option value="crm">CRM</option>
                  <option value="marketing">Marketing</option>
                  <option value="shield">Shield</option>
                  <option value="website">Website</option>
                  <option value="neural-orbit">NeuralOrbit</option>
                </select>
                <input id="custom-event-type" type="text" placeholder="Event type  e.g. lead_reply" aria-label="Custom event type" style="padding:9px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:13px;font-family:var(--font);outline:none;" />
                <textarea id="custom-payload" rows="5" placeholder='{"key": "value"}' style="padding:9px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:12px;font-family:monospace;resize:vertical;outline:none;">{}</textarea>
                <div id="custom-payload-error" style="font-size:11px;color:var(--danger);display:none;">Invalid JSON payload</div>
                <button id="run-custom-btn" style="padding:10px;border-radius:8px;border:none;cursor:pointer;background:linear-gradient(135deg,#6366F1,#4F46E5);color:white;font-size:13px;font-weight:600;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:8px;">
                  <i class="bi bi-play-fill"></i> Run Custom Event
                </button>
              </div>
            </div>

            <!-- Results Feed -->
            <div class="card" style="flex:1;min-height:0;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
                <div style="font-size:11px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;">Results Feed</div>
                <button id="clear-results-btn" style="font-size:11px;color:var(--dim);background:none;border:none;cursor:pointer;font-family:var(--font);">Clear</button>
              </div>
              <div id="results-feed" style="display:flex;flex-direction:column;gap:10px;overflow-y:auto;max-height:400px;">
                <div style="padding:24px;text-align:center;color:var(--dim);">
                  <i class="bi bi-play-circle" style="font-size:28px;display:block;margin-bottom:8px;"></i>
                  <div style="font-size:13px;">Run a scenario to see results here</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    }

    function buildScenarioCard(s) {
        const color = categoryColors[s.category] || '#94A3B8';
        return `
      <div class="sandbox-card card" data-scenario="${s.id}" style="cursor:pointer;transition:border-color .2s,box-shadow .2s;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:36px;height:36px;border-radius:10px;background:${color}18;color:${color};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
              <i class="bi ${s.icon}" style="font-size:16px;"></i>
            </div>
            <div>
              <div style="font-size:13px;font-weight:600;color:var(--text);">${s.title}</div>
              <div style="font-size:11px;font-weight:600;padding:2px 7px;border-radius:4px;background:${color}18;color:${color};display:inline-block;margin-top:3px;">${s.category}</div>
            </div>
          </div>
          <div id="status-${s.id}" style="flex-shrink:0;"></div>
        </div>
        <p style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:14px;">${s.desc}</p>
        <button class="run-scenario-btn" data-id="${s.id}" style="width:100%;padding:8px;border-radius:8px;border:1px solid ${color}30;background:${color}0a;color:${color};font-size:12px;font-weight:600;cursor:pointer;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:6px;transition:background .15s;">
          <i class="bi bi-play-fill" style="font-size:12px;"></i> Run Scenario
        </button>
      </div>`;
    }

    /* ── Run scenario ─────────────────────────────────────────── */
    async function runScenario(scenario, feedEl, statusEl) {
        if (running[scenario.id]) return;
        running[scenario.id] = true;

        // Update button state
        const btn = document.querySelector(`.run-scenario-btn[data-id="${scenario.id}"]`);
        if (btn) { btn.disabled = true; btn.innerHTML = '<div class="apply-btn-spinner"></div> Running…'; }
        if (statusEl) statusEl.innerHTML = '<i class="bi bi-hourglass-split" style="color:var(--dim);font-size:14px;"></i>';

        const body = {
            ...scenario.event,
            sandbox: true,
            context: { sandbox_scenario: scenario.id, sandbox_title: scenario.title },
        };
        if (selectedTargetUser) body.target_user_id = selectedTargetUser;

        const res = await apiFetch('/api/v1/events', { method: 'POST', body: JSON.stringify(body) });

        running[scenario.id] = false;
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise" style="font-size:12px;"></i> Run Again';
        }

        const ok = res && !res.__error;
        results[scenario.id] = { scenario, res, ok, ts: new Date() };

        // Update status dot on card
        if (statusEl) {
            statusEl.innerHTML = `<i class="bi ${ok ? 'bi-check-circle-fill' : 'bi-x-circle-fill'}" style="color:${ok ? 'var(--success)' : 'var(--danger)'};font-size:16px;"></i>`;
        }

        appendResult(feedEl, scenario, res, ok);
    }

    function appendResult(feedEl, scenario, res, ok) {
        if (!feedEl) return;
        // Remove empty state
        const empty = feedEl.querySelector('[style*="text-align:center"]');
        if (empty) empty.remove();

        const color = categoryColors[scenario.category] || '#94A3B8';
        const reward = res?.reward_value ?? res?.reward ?? null;
        const decision = res?.decision_action || res?.ai_decision || null;

        const card = document.createElement('div');
        card.style.cssText = `padding:12px 14px;border-radius:10px;background:${ok ? 'rgba(34,197,94,.05)' : 'rgba(239,68,68,.05)'};border:1px solid ${ok ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)'};`;
        card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <i class="bi ${ok ? 'bi-check-circle-fill' : 'bi-x-octagon-fill'}" style="color:${ok ? '#22C55E' : '#EF4444'};font-size:14px;"></i>
          <span style="font-size:13px;font-weight:600;color:var(--text);">${scenario.title}</span>
          <span style="font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;background:${color}18;color:${color};">${scenario.category}</span>
        </div>
        <span style="font-size:11px;color:var(--dim);">${new Date().toLocaleTimeString()}</span>
      </div>
      ${ok ? `
        ${reward !== null ? `<div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Reward Score: <strong style="color:${reward >= 0 ? 'var(--success)' : 'var(--danger)'};">${reward >= 0 ? '+' : ''}${reward}</strong></div>` : ''}
        ${decision ? `<div style="font-size:12px;color:var(--muted);margin-bottom:4px;">AI Decision: <span style="color:var(--text);font-style:italic;">"${decision}"</span></div>` : ''}
        <div style="font-size:11px;color:var(--success);">✓ Event processed successfully (sandbox)</div>
      ` : `
        <div style="font-size:12px;color:var(--danger);">${res?.__error || 'Event failed'}</div>
        <div style="font-size:11px;color:var(--dim);margin-top:4px;">Make sure the backend is running at 127.0.0.1:8000</div>
      `}`;

        feedEl.prepend(card);
    }

    /* ── Event binding ────────────────────────────────────────── */
    function bindSandboxEvents(isAdmin) {
        const feedEl = document.getElementById('results-feed');

        // Scenario run buttons
        document.querySelectorAll('.run-scenario-btn').forEach(btn => {
            btn.addEventListener('click', async e => {
                e.stopPropagation();
                const id = btn.dataset.id;
                const scn = SCENARIOS.find(s => s.id === id);
                if (!scn) return;
                const statusEl = document.getElementById(`status-${id}`);
                await runScenario(scn, feedEl, statusEl);
            });
            // Card hover
            btn.closest('.sandbox-card')?.addEventListener('mouseenter', () => { btn.closest('.sandbox-card').style.borderColor = 'rgba(99,102,241,.4)'; btn.closest('.sandbox-card').style.boxShadow = '0 0 20px rgba(99,102,241,.08)'; });
            btn.closest('.sandbox-card')?.addEventListener('mouseleave', () => { btn.closest('.sandbox-card').style.borderColor = ''; btn.closest('.sandbox-card').style.boxShadow = ''; });
        });

        // Custom event run
        document.getElementById('run-custom-btn')?.addEventListener('click', async () => {
            const moduleEl = document.getElementById('custom-module');
            const typeEl = document.getElementById('custom-event-type');
            const payloadEl = document.getElementById('custom-payload');
            const errEl = document.getElementById('custom-payload-error');
            const btn = document.getElementById('run-custom-btn');

            let payload = {};
            try {
                payload = JSON.parse(payloadEl?.value || '{}');
                if (errEl) errEl.style.display = 'none';
            } catch {
                if (errEl) errEl.style.display = 'block';
                return;
            }

            const eventType = typeEl?.value?.trim();
            if (!eventType) { typeEl?.focus(); return; }

            btn.disabled = true;
            btn.innerHTML = '<div class="apply-btn-spinner"></div> Running…';

            const body = {
                module: moduleEl?.value || 'crm',
                event_type: eventType,
                payload,
                sandbox: true,
                context: { sandbox_scenario: 'custom', sandbox_title: 'Custom Event' },
            };
            if (selectedTargetUser) body.target_user_id = selectedTargetUser;

            const res = await apiFetch('/api/v1/events', { method: 'POST', body: JSON.stringify(body) });
            const ok = res && !res.__error;

            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Custom Event';

            appendResult(feedEl, { id: 'custom', title: `Custom: ${eventType}`, category: moduleEl?.value || 'custom', desc: '' }, res, ok);
        });

        // Admin: target user input
        if (isAdmin) {
            document.getElementById('target-user-input')?.addEventListener('input', e => {
                selectedTargetUser = e.target.value.trim() || null;
                const status = document.getElementById('target-user-status');
                if (status) status.textContent = selectedTargetUser ? `✓ Running as client ${selectedTargetUser.slice(0, 8)}…` : '';
            });

            // Batch run
            document.getElementById('batch-run-btn')?.addEventListener('click', async () => {
                if (batchRunning) return;
                batchRunning = true;
                const btn = document.getElementById('batch-run-btn');
                if (btn) { btn.disabled = true; btn.innerHTML = '<div class="apply-btn-spinner"></div> Running all…'; }

                const visible = SCENARIOS; // run all scenarios sequentially
                for (const scn of visible) {
                    const statusEl = document.getElementById(`status-${scn.id}`);
                    await runScenario(scn, feedEl, statusEl);
                    await new Promise(r => setTimeout(r, 400)); // brief pause between runs
                }

                batchRunning = false;
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-collection-play" style="font-size:13px;"></i> Batch Run All'; }
            });

            // Export results
            document.getElementById('download-results-btn')?.addEventListener('click', () => {
                const data = Object.values(results).map(r => ({
                    scenario: r.scenario.title,
                    category: r.scenario.category,
                    success: r.ok,
                    response: r.res,
                    timestamp: r.ts?.toISOString(),
                }));
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `sandbox-results-${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
            });
        }

        // Clear results
        document.getElementById('clear-results-btn')?.addEventListener('click', () => {
            results = {};
            const feedEl = document.getElementById('results-feed');
            if (feedEl) feedEl.innerHTML = `
        <div style="padding:24px;text-align:center;color:var(--dim);">
          <i class="bi bi-play-circle" style="font-size:28px;display:block;margin-bottom:8px;"></i>
          <div style="font-size:13px;">Run a scenario to see results here</div>
        </div>`;
            // Reset all status dots and buttons
            document.querySelectorAll('[id^="status-"]').forEach(el => el.innerHTML = '');
            document.querySelectorAll('.run-scenario-btn').forEach(btn => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-play-fill" style="font-size:12px;"></i> Run Scenario';
            });
        });
    }

})();
