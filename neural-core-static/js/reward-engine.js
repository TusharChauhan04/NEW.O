/* ============================================================
   reward-engine.js — Reward Weight Control (Real Backend)
   Admin: client selector + apply for any user + change history
   User:  own weights, own apply, locked indicator from admin
   Falls back gracefully if backend unavailable.
   ============================================================ */

(function () {
  'use strict';

  const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';

  async function apiFetch(path, opts = {}) {
    try {
      const token = localStorage.getItem('neuralorbit_token');
      const res = await fetch(BACKEND + path, {
        ...opts,
        signal: AbortSignal.timeout(3000),
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers || {}) },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }

  /* ── Slider config ───────────────────────────────────────── */
  const SLIDERS = [
    { key: 'conversion', label: 'Conversion', icon: 'bi-graph-up-arrow', color: '#5B8CFF', desc: 'Optimize for converting prospects to customers' },
    { key: 'retention', label: 'Retention', icon: 'bi-people-fill', color: '#22C55E', desc: 'Prioritize keeping existing customers engaged' },
    { key: 'cost', label: 'Cost', icon: 'bi-coin', color: '#F59E0B', desc: 'Control spending and budget allocation' },
    { key: 'risk', label: 'Risk', icon: 'bi-shield-fill', color: '#EF4444', desc: 'Manage risk tolerance across operations' },
  ];

  const PRESETS = [
    { name: 'SaaS', values: { conversion: 75, retention: 85, cost: 40, risk: 30 } },
    { name: 'Finance', values: { conversion: 60, retention: 70, cost: 50, risk: 20 } },
    { name: 'E-commerce', values: { conversion: 85, retention: 60, cost: 55, risk: 45 } },
    { name: 'Healthcare', values: { conversion: 50, retention: 90, cost: 35, risk: 15 } },
  ];

  /* ── State ───────────────────────────────────────────────── */
  let values = { conversion: 75, retention: 85, cost: 40, risk: 30 };
  let simMode = true;
  let applying = false;
  let activePreset = 'SaaS';
  let lastUpdated = null;
  let lastUpdatedBy = null;
  let selectedClientId = null;   // Admin: currently selected client
  let clientList = [];           // Admin: all clients from backend

  /* ── Load clients (admin) ─────────────────────────────────── */
  async function loadClients() {
    const data = await apiFetch('/api/v1/states/autonomy/clients');
    clientList = data?.clients || [];
    return clientList;
  }

  /* ── Load from backend ────────────────────────────────────── */
  async function loadConfig(targetUserId = null) {
    let path = '/api/v1/rewards/config';
    if (targetUserId) path += `?target_user_id=${encodeURIComponent(targetUserId)}`;
    const data = await apiFetch(path);
    if (data && data.config) {
      const c = data.config;
      values = { conversion: c.conversion ?? 75, retention: c.retention ?? 85, cost: c.cost ?? 40, risk: c.risk ?? 30 };
      simMode = c.sim_mode ?? true;
      activePreset = c.industry ?? 'SaaS';
      lastUpdated = c.updated_at ?? null;
      lastUpdatedBy = c.updated_by ?? null;
      return true;
    }
    return false;
  }

  /* ── Save to backend ─────────────────────────────────────── */
  async function saveConfig(targetUserId = null) {
    const body = { conversion: values.conversion, retention: values.retention, cost: values.cost, risk: values.risk, industry: activePreset, sim_mode: simMode };
    if (targetUserId) body.target_user_id = targetUserId;
    return await apiFetch('/api/v1/rewards/config', { method: 'POST', body: JSON.stringify(body) });
  }

  /* ── Reward Summary KPIs ─────────────────────────────────── */
  async function loadRewardSummary() {
    try {
      const data = await apiFetch('/api/v1/rewards/summary');
      if (!data) return null;
      return {
        total_events:  data.total_events  ?? data.total ?? 0,
        avg_score:     data.avg_score     ?? data.average_reward ?? 0,
        top_module:    data.top_module    ?? data.best_module ?? '—',
      };
    } catch { return null; }
  }

  function renderSummaryKPIs(container, summary) {
    if (!container) return;
    const s = summary || { total_events: '—', avg_score: '—', top_module: '—' };
    const cards = [
      { icon: 'bi-lightning-fill',    color: '#F59E0B', label: 'Total Reward Events',    val: s.total_events },
      { icon: 'bi-graph-up-arrow',    color: '#22C55E', label: 'Avg Reward Score',       val: typeof s.avg_score === 'number' ? s.avg_score.toFixed(2) : s.avg_score },
      { icon: 'bi-trophy-fill',       color: '#5B8CFF', label: 'Top Rewarded Module',   val: String(s.top_module).toUpperCase() },
    ];
    container.innerHTML = cards.map(c => `
      <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 18px;display:flex;align-items:center;gap:12px;flex:1;min-width:160px;">
        <div style="width:36px;height:36px;border-radius:8px;background:${c.color}1a;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <i class="bi ${c.icon}" style="color:${c.color};font-size:16px;"></i>
        </div>
        <div>
          <div style="font-size:11px;color:var(--muted);font-weight:500;">${c.label}</div>
          <div style="font-size:20px;font-weight:700;color:var(--text);margin-top:2px;">${c.val}</div>
        </div>
      </div>`).join('');
  }

  /* ── Main render ─────────────────────────────────────────── */
  window.loadRewardEngine = async function () {
    const content = document.getElementById('page-content');
    if (!content) return;

    const isAdmin = window.CURRENT_ROLE === 'admin';

    // Show skeleton
    content.innerHTML = buildSkeleton();

    // Load clients list first (admin only)
    if (isAdmin) await loadClients();

    // Load config + summary in parallel
    const [, summary] = await Promise.all([
      loadConfig(selectedClientId),
      loadRewardSummary(),
    ]);

    // Full render
    renderFull(content, isAdmin);

    // Inject summary KPI strip below the header
    const kpiStrip = document.createElement('div');
    kpiStrip.style.cssText = 'display:flex;gap:12px;flex-wrap:wrap;padding:0 24px 0;flex-shrink:0;';
    renderSummaryKPIs(kpiStrip, summary);
    const pageAnimate = content.querySelector('.page-animate');
    if (pageAnimate) {
      // Insert after header (first child) but before client picker
      const firstChild = pageAnimate.firstElementChild;
      if (firstChild && firstChild.nextSibling) {
        pageAnimate.insertBefore(kpiStrip, firstChild.nextSibling);
      } else {
        pageAnimate.appendChild(kpiStrip);
      }
    }
  };


  function buildSkeleton() {
    return `<div style="padding:24px;display:flex;flex-direction:column;gap:16px;height:100%;">
      <div style="height:52px;width:320px;border-radius:14px;background:rgba(91,140,255,.08);animation:pulse 1.5s infinite;"></div>
      <div style="display:flex;gap:20px;flex:1;">
        <div style="flex:1;border-radius:14px;background:rgba(91,140,255,.05);animation:pulse 1.5s infinite;"></div>
        <div style="width:240px;border-radius:14px;background:rgba(91,140,255,.05);animation:pulse 1.5s infinite;"></div>
      </div>
    </div>`;
  }

  function renderFull(content, isAdmin) {
    // Build client selector bar (admin only)
    const selectedClient = clientList.find(c => c.id === selectedClientId);
    const clientPickerHtml = isAdmin && clientList.length > 0 ? `
      <div style="margin:12px 24px 0;padding:12px 16px;border-radius:var(--radius);background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.15);display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <i class="bi bi-person-workspace" style="font-size:14px;color:#EF4444;"></i>
        <span style="font-size:12px;font-weight:700;color:#EF4444;text-transform:uppercase;letter-spacing:.05em;">Manage Client:</span>
        <select id="client-selector" style="flex:1;min-width:200px;padding:7px 12px;border-radius:8px;border:1px solid rgba(239,68,68,.3);background:var(--surface);color:var(--text);font-size:13px;font-family:var(--font);outline:none;cursor:pointer;">
          <option value="">— My own settings —</option>
          ${clientList.map(c => `<option value="${c.id}" ${c.id === selectedClientId ? 'selected' : ''}>${c.email} (${c.global_level})</option>`).join('')}
        </select>
        ${selectedClient ? `<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(239,68,68,.1);color:#EF4444;font-weight:600;">Editing: ${selectedClient.email}</span>` : ''}
      </div>` : isAdmin ? `
      <div style="margin:12px 24px 0;padding:10px 16px;border-radius:var(--radius);background:rgba(91,140,255,.05);border:1px solid rgba(91,140,255,.1);font-size:12px;color:var(--dim);display:flex;align-items:center;gap:8px;">
        <i class="bi bi-people" style="color:#5B8CFF;"></i> No client accounts found yet — manage your own settings below
      </div>` : '';

    content.innerHTML = `
      <div class="page-animate" style="display:flex;flex-direction:column;height:100%;overflow:hidden;">

        <!-- Header -->
        <div style="padding:24px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:16px;">
            <div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#EF4444,#DC2626);display:flex;align-items:center;justify-content:center;color:white;flex-shrink:0;">
              <i class="bi bi-lightning-fill" style="font-size:22px;"></i>
            </div>
            <div>
              <h1 style="font-size:22px;font-weight:700;color:var(--text);line-height:1.2;">Reward Control Center</h1>
              <p style="font-size:13px;color:var(--muted);margin-top:4px;">Control how the AI thinks — tune reward signals that drive every decision</p>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;padding:8px 14px;border-radius:var(--radius);border:1px solid ${isAdmin ? 'rgba(239,68,68,.3)' : 'var(--border)'};background:${isAdmin ? 'rgba(239,68,68,.08)' : 'rgba(30,41,59,.5)'};flex-shrink:0;">
            <i class="bi bi-${isAdmin ? 'exclamation-triangle' : 'eye'}" style="font-size:13px;color:${isAdmin ? '#EF4444' : 'var(--muted)'};"></i>
            <span style="font-size:11px;font-weight:700;color:${isAdmin ? '#EF4444' : 'var(--muted)'};letter-spacing:.05em;">
              ${isAdmin ? 'CRITICAL SYSTEM — Changes affect all AI behavior' : 'YOUR REWARD SETTINGS'}
            </span>
          </div>
        </div>

        <!-- Admin Client Picker -->
        ${clientPickerHtml}

        ${lastUpdated ? `<div style="margin:8px 24px 0;font-size:11px;color:var(--dim);">Last updated: ${new Date(lastUpdated).toLocaleString()}${lastUpdatedBy ? ' · by ' + lastUpdatedBy.slice(0, 8) : ''}</div>` : ''}

        <!-- Main 2-Column -->
        <div style="flex:1;display:flex;gap:20px;padding:20px 24px 24px;overflow:hidden;min-height:0;">

          <!-- LEFT: Sliders -->
          <div style="flex:1;display:flex;flex-direction:column;gap:16px;overflow-y:auto;min-width:0;">
            <div class="card" style="flex-shrink:0;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
                <span style="font-size:13px;font-weight:600;color:var(--text);text-transform:uppercase;letter-spacing:.05em;">Reward Weight Distribution</span>
                ${isAdmin ? '<button style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:var(--radius-sm);border:1px solid var(--border);background:rgba(30,41,59,.5);font-size:11px;font-weight:600;color:var(--muted);cursor:pointer;font-family:var(--font);"><i class="bi bi-gear" style="font-size:11px;"></i> Advanced</button>' : ''}
              </div>
              <div class="sliders-grid" id="sliders-grid">
                ${SLIDERS.map(s => buildSlider(s, isAdmin)).join('')}
              </div>
            </div>

            <!-- Weight Bar -->
            <div class="card" style="flex-shrink:0;">
              <div style="font-size:10px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px;">Combined Weight Distribution</div>
              <div class="weight-bar" id="weight-bar">${buildWeightBar()}</div>
              <div id="weight-bar-legend" style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:var(--muted);">${buildWeightLegend()}</div>
            </div>
          </div>

          <!-- RIGHT: Panel -->
          <div style="width:240px;flex-shrink:0;display:flex;flex-direction:column;gap:16px;overflow-y:auto;">

            <!-- Industry Presets -->
            <div class="card card-sm">
              <div style="font-size:10px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;">Industry Presets</div>
              <div style="position:relative;" id="preset-dropdown-wrap">
                <button id="preset-trigger" style="width:100%;display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:var(--radius);background:var(--surface);border:1px solid var(--border);font-size:13px;color:var(--text);cursor:pointer;font-family:var(--font);">
                  <span id="preset-current">${activePreset}</span>
                  <i class="bi bi-chevron-down" style="color:var(--dim);font-size:12px;"></i>
                </button>
                <div id="preset-list" style="display:none;position:absolute;top:calc(100% + 4px);left:0;right:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;z-index:100;box-shadow:0 8px 24px rgba(0,0,0,.4);">
                  ${PRESETS.map(p => `<div class="preset-option ${p.name === activePreset ? 'is-selected' : ''}" data-preset="${p.name}" style="padding:9px 14px;font-size:13px;color:var(--muted);cursor:pointer;">${p.name}</div>`).join('')}
                </div>
              </div>
            </div>

            <!-- Simulation Mode -->
            <div class="card card-sm">
              <div style="font-size:10px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;">Simulation Mode</div>
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                <span id="sim-label" style="font-size:13px;font-weight:600;color:${simMode ? 'var(--text)' : 'var(--muted)'};">${simMode ? 'Active — No real impact' : 'Inactive — LIVE mode'}</span>
                <button id="sim-toggle" class="toggle-pill ${simMode ? 'is-on blue-toggle' : 'is-off blue-toggle'}" aria-label="Toggle simulation mode">
                  <div class="toggle-pip"></div>
                </button>
              </div>
              <div id="sim-note" style="display:${simMode ? 'flex' : 'none'};align-items:center;gap:6px;font-size:11px;color:var(--accent);">
                <i class="bi bi-play-fill" style="font-size:11px;"></i> Learning only — safe to experiment.
              </div>
            </div>

            <!-- Apply Button -->
            <button id="apply-btn" class="apply-btn state-idle">
              <div class="apply-btn-overlay"></div>
              <span id="apply-btn-inner">
                <i class="bi bi-lightning-fill"></i>
                ${isAdmin ? 'Apply Intelligence Rules' : 'Save My Settings'}
              </span>
            </button>

            <!-- Save status -->
            <div id="save-status" style="display:none;text-align:center;font-size:12px;padding:8px;border-radius:8px;"></div>

            <!-- Current Configuration -->
            <div class="card card-sm">
              <div style="font-size:10px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px;">Current Configuration</div>
              <div style="display:flex;flex-direction:column;gap:10px;" id="current-config">${buildConfigList()}</div>
            </div>

          </div>
        </div>
      </div>`;

    bindRewardEvents(isAdmin);
  }

  function buildSlider(s, isAdmin) {
    const val = values[s.key];
    return `
      <div class="slider-col">
        <div class="slider-value-display" style="color:${s.color};">${val}<span class="slider-value-unit">%</span></div>
        <div class="slider-track-wrap">
          <div class="slider-track-bg"></div>
          <div class="slider-track-fill" id="fill-${s.key}" style="height:${val}%;background:linear-gradient(to top,${s.color}cc,${s.color});"></div>
          <div class="slider-thumb" id="thumb-${s.key}" style="border-color:${s.color};bottom:calc(${val}% - 10px);box-shadow:0 0 8px ${s.color}66;"></div>
          <input type="range" class="slider-input" id="slider-${s.key}" data-key="${s.key}" min="0" max="100" step="1" value="${val}" aria-label="${s.label} weight" />
        </div>
        <div class="slider-icon-wrap" style="background:${s.color}22;color:${s.color};"><i class="bi ${s.icon}" style="font-size:18px;"></i></div>
        <div class="slider-label" style="color:${s.color};">${s.label}</div>
        <div class="slider-desc">${s.desc}</div>
      </div>`;
  }

  function totalWeight() { return Object.values(values).reduce((a, b) => a + b, 0) || 1; }
  function buildWeightBar() { return SLIDERS.map(s => `<div class="weight-segment" style="flex:${values[s.key]};background:${s.color};min-width:4px;"></div>`).join(''); }
  function buildWeightLegend() {
    const total = totalWeight();
    return SLIDERS.map(s => {
      const pct = (values[s.key] / total * 100).toFixed(1);
      return `<div style="display:flex;align-items:center;gap:5px;"><div style="width:8px;height:8px;border-radius:50%;background:${s.color};flex-shrink:0;"></div><span>${s.label}: ${pct}%</span></div>`;
    }).join('');
  }
  function buildConfigList() {
    const rows = SLIDERS.map(s => `
      <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;">
        <div style="display:flex;align-items:center;gap:6px;color:var(--muted);">
          <i class="bi ${s.icon}" style="color:${s.color};font-size:12px;"></i> ${s.label}
        </div>
        <span style="font-weight:600;color:${s.color};">${values[s.key]}%</span>
      </div>`);
    rows.push(`
      <div style="height:1px;background:var(--border-light);margin:2px 0;"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;">
        <span style="color:var(--muted);">Industry</span>
        <span style="font-weight:600;color:var(--accent);">${activePreset}</span>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;">
        <span style="color:var(--muted);">Simulation</span>
        <span style="font-weight:600;color:${simMode ? 'var(--success)' : 'var(--danger)'};">${simMode ? 'ON' : 'OFF'}</span>
      </div>`);
    return rows.join('');
  }

  function updateSliderVisuals(key, val) {
    const fill = document.getElementById(`fill-${key}`);
    const thumb = document.getElementById(`thumb-${key}`);
    const input = document.getElementById(`slider-${key}`);
    const col = input?.closest('.slider-col');
    const vDisp = col?.querySelector('.slider-value-display');
    if (fill) fill.style.height = val + '%';
    if (thumb) thumb.style.bottom = `calc(${val}% - 10px)`;
    if (vDisp) vDisp.innerHTML = `${val}<span class="slider-value-unit">%</span>`;
  }

  function showSaveStatus(ok, msg) {
    const el = document.getElementById('save-status');
    if (!el) return;
    el.style.display = 'block';
    el.style.background = ok ? 'rgba(34,197,94,.1)' : 'rgba(239,68,68,.1)';
    el.style.color = ok ? '#22C55E' : '#EF4444';
    el.style.border = `1px solid ${ok ? 'rgba(34,197,94,.3)' : 'rgba(239,68,68,.3)'}`;
    el.textContent = msg;
    setTimeout(() => { el.style.display = 'none'; }, 3000);
  }

  function bindRewardEvents(isAdmin) {
    // Admin client selector — reload weights when client changes
    const clientSel = document.getElementById('client-selector');
    if (clientSel) {
      clientSel.addEventListener('change', async () => {
        selectedClientId = clientSel.value || null;
        const content = document.getElementById('page-content');
        if (content) content.innerHTML = buildSkeleton();
        await loadConfig(selectedClientId);
        renderFull(content, true);
        bindRewardEvents(true);
      });
    }

    // Sliders
    document.querySelectorAll('.slider-input').forEach(input => {
      input.addEventListener('input', () => {
        const key = input.dataset.key;
        const val = parseInt(input.value, 10);
        values[key] = val;
        updateSliderVisuals(key, val);
        document.getElementById('weight-bar').innerHTML = buildWeightBar();
        document.getElementById('weight-bar-legend').innerHTML = buildWeightLegend();
        document.getElementById('current-config').innerHTML = buildConfigList();
      });
    });

    // Industry preset dropdown
    const trigger = document.getElementById('preset-trigger');
    const list = document.getElementById('preset-list');
    if (trigger && list) {
      trigger.addEventListener('click', e => { e.stopPropagation(); list.style.display = list.style.display === 'block' ? 'none' : 'block'; });
      list.querySelectorAll('.preset-option').forEach(opt => {
        opt.addEventListener('click', () => {
          const preset = PRESETS.find(p => p.name === opt.dataset.preset);
          if (!preset) return;
          activePreset = preset.name;
          Object.assign(values, preset.values);
          document.getElementById('preset-current').textContent = preset.name;
          list.style.display = 'none';
          SLIDERS.forEach(s => { document.getElementById(`slider-${s.key}`).value = values[s.key]; updateSliderVisuals(s.key, values[s.key]); });
          document.getElementById('weight-bar').innerHTML = buildWeightBar();
          document.getElementById('weight-bar-legend').innerHTML = buildWeightLegend();
          document.getElementById('current-config').innerHTML = buildConfigList();
        });
      });
      document.addEventListener('click', e => { if (!trigger.contains(e.target) && !list.contains(e.target)) list.style.display = 'none'; }, { passive: true });
    }

    // Simulation mode toggle
    const simToggle = document.getElementById('sim-toggle');
    if (simToggle) {
      simToggle.addEventListener('click', () => {
        simMode = !simMode;
        simToggle.className = `toggle-pill ${simMode ? 'is-on blue-toggle' : 'is-off blue-toggle'}`;
        const lbl = document.getElementById('sim-label');
        const note = document.getElementById('sim-note');
        if (lbl) { lbl.textContent = simMode ? 'Active — No real impact' : 'Inactive — LIVE mode'; lbl.style.color = simMode ? 'var(--text)' : 'var(--muted)'; }
        if (note) note.style.display = simMode ? 'flex' : 'none';
        document.getElementById('current-config').innerHTML = buildConfigList();
      });
    }

    // Apply / Save button → real backend call
    const applyBtn = document.getElementById('apply-btn');
    if (applyBtn) {
      applyBtn.addEventListener('click', async () => {
        if (applying) return;
        applying = true;
        const inner = document.getElementById('apply-btn-inner');
        applyBtn.className = 'apply-btn state-applying';
        if (inner) inner.innerHTML = '<div class="apply-btn-spinner"></div> Saving…';

        const res = await saveConfig(selectedClientId);

        applying = false;
        applyBtn.className = 'apply-btn state-idle';
        if (inner) inner.innerHTML = `<i class="bi bi-lightning-fill"></i> ${isAdmin ? 'Apply Intelligence Rules' : 'Save My Settings'}`;

        const clientLabel = selectedClientId ? ` for client` : '';
        if (res && res.status === 'ok') {
          showSaveStatus(true, `✓ Settings saved${clientLabel} successfully`);
        } else {
          showSaveStatus(false, '✗ Save failed — settings applied locally only');
        }
      });
    }
  }

})();
