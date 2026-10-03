/* ============================================================
   autonomy.js — Autonomy Control (Real Backend)
   Admin: global defaults + per-client settings + lock modules
   User:  own settings only + locked modules read-only
   Falls back to defaults if backend unavailable.
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

  const LEVELS = [
    { key: 'observe', label: 'Observe', icon: 'bi-eye', color: '#5B8CFF', bg: 'rgba(91,140,255,.1)', border: 'rgba(91,140,255,.2)', desc: 'AI watches and learns without taking any action', features: ['Monitors all data streams', 'Builds decision models', 'Suggests improvements', 'Zero risk'] },
    { key: 'assist', label: 'Assist', icon: 'bi-hand-index-thumb', color: '#22C55E', bg: 'rgba(34,197,94,.1)', border: 'rgba(34,197,94,.3)', desc: 'AI recommends actions but you approve every decision', features: ['Real-time recommendations', 'Draft responses & actions', 'Human approval required', 'Low risk'] },
    { key: 'autonomous', label: 'Autonomous', icon: 'bi-robot', color: '#EF4444', bg: 'rgba(239,68,68,.1)', border: 'rgba(239,68,68,.3)', desc: 'AI makes and executes decisions independently within boundaries', features: ['Full decision authority', 'Real-time execution', 'Post-action reporting', 'High efficiency'] },
  ];

  const MODULE_DEFS = [
    { key: 'crm', label: 'CRM', icon: 'bi-people', color: '#5B8CFF' },
    { key: 'marketing', label: 'Marketing', icon: 'bi-megaphone', color: '#8B5CF6' },
    { key: 'shield', label: 'Shield', icon: 'bi-shield', color: '#F59E0B' },
    { key: 'website', label: 'Website', icon: 'bi-globe', color: '#22C55E' },
  ];

  /* ── State ───────────────────────────────────────────────── */
  let globalLevel = 'assist';
  let moduleSettings = { crm: 'assist', marketing: 'assist', shield: 'observe', website: 'autonomous' };
  let lockedModules = [];
  let selectedClientId = null;   // Admin: currently selected client
  let clientList = [];           // Admin: full client list
  let planGates = null;          // User plan gate config (null = no restriction / admin)
  let userPlan = 'starter';      // User's subscription plan

  async function loadClients() {
    const data = await apiFetch('/api/v1/states/autonomy/clients');
    clientList = data?.clients || [];
  }

  /* ── Backend load/save ───────────────────────────────────── */
  async function loadAutonomy(targetUserId = null) {
    let path = '/api/v1/states/autonomy';
    if (targetUserId) path += `?target_user_id=${encodeURIComponent(targetUserId)}`;
    const data = await apiFetch(path);
    if (data && data.autonomy) {
      const a = data.autonomy;
      globalLevel = a.global_level || 'assist';
      moduleSettings = { crm: a.crm || 'assist', marketing: a.marketing || 'assist', shield: a.shield || 'observe', website: a.website || 'autonomous' };
      lockedModules = a.locked_modules || [];
    }
  }

  /* ── Load plan gates (user only) ─────────────────────────── */
  async function loadPlanGates() {
    try {
      const data = await apiFetch('/api/v1/user/autonomy');
      if (!data) return;
      // Sync settings from user endpoint (more authoritative for own data)
      if (data.settings) {
        const s = data.settings;
        globalLevel = s.global_level || globalLevel;
        moduleSettings = {
          crm:       s.crm       || moduleSettings.crm,
          marketing: s.marketing || moduleSettings.marketing,
          shield:    s.shield    || moduleSettings.shield,
          website:   s.website   || moduleSettings.website,
        };
      }
      planGates = data.plan_gates || null;
      userPlan  = data.plan       || 'starter';
    } catch { /* fallback: no gates */ }
  }

  /* ── Gate helper ──────────────────────────────────────────── */
  function isLevelGated(level, module) {
    if (!planGates) return false;  // admin or no gates = never gated
    const allowed = planGates.allowed_levels || [];
    if (!allowed.includes(level)) return true;  // level not in plan
    const mods = planGates.allowed_modules;
    if (mods === '__all__' || !module) return false;
    return !mods.includes(module);  // module not in plan
  }

  async function saveAutonomy(targetUserId = null) {
    const body = { global_level: globalLevel, ...moduleSettings, locked_modules: lockedModules };
    if (targetUserId) body.target_user_id = targetUserId;
    return await apiFetch('/api/v1/states/autonomy', { method: 'POST', body: JSON.stringify(body) });
  }

  /* ── User self-save (routes to /user/autonomy endpoint) ───── */
  async function saveMyAutonomy() {
    const body = {
      global_level: globalLevel,
      crm:          moduleSettings.crm,
      marketing:    moduleSettings.marketing,
      shield:       moduleSettings.shield,
      website:      moduleSettings.website,
    };
    return await apiFetch('/api/v1/user/autonomy', { method: 'PATCH', body: JSON.stringify(body) });
  }

  /* ── Main entry ─────────────────────────────────────────── */
  window.loadAutonomy = async function () {
    const content = document.getElementById('page-content');
    if (!content) return;

    const isAdmin = window.CURRENT_ROLE === 'admin';
    const moduleKey = window.CURRENT_MODULE || 'neural-orbit';
    const isGlobal = moduleKey === 'neural-orbit';

    // Show skeleton
    content.innerHTML = `<div style="padding:24px;display:flex;flex-direction:column;gap:20px;">
      <div style="height:36px;width:260px;border-radius:10px;background:rgba(91,140,255,.08);animation:pulse 1.5s infinite;"></div>
      <div style="display:flex;gap:20px;">${Array(3).fill('<div style="flex:1;height:180px;border-radius:14px;background:rgba(91,140,255,.05);animation:pulse 1.5s infinite;"></div>').join('')}</div>
    </div>`;

    // Load clients (admin) and autonomy settings
    if (isAdmin) {
      await loadClients();
      await loadAutonomy(selectedClientId);
      planGates = null; // admins have no plan restrictions
    } else {
      // Users: load plan gates + settings in parallel
      await loadPlanGates();
    }

    // For module-specific pages, show that module's level
    if (!isGlobal) {
      globalLevel = moduleSettings[moduleKey] || 'assist';
    }

    renderAutonomy(content, isAdmin, isGlobal, moduleKey);
  };

  /* ── Full render ─────────────────────────────────────────── */
  function renderAutonomy(content, isAdmin, isGlobal, moduleKey) {
    // Build client selector bar (admin only)
    const selectedClient = clientList.find(c => c.id === selectedClientId);
    const clientPickerHtml = isAdmin && clientList.length > 0 ? `
      <div style="padding:12px 16px;border-radius:var(--radius);background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.15);display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <i class="bi bi-person-workspace" style="font-size:14px;color:#EF4444;"></i>
        <span style="font-size:12px;font-weight:700;color:#EF4444;text-transform:uppercase;letter-spacing:.05em;">Manage Client:</span>
        <select id="autonomy-client-selector" style="flex:1;min-width:200px;padding:7px 12px;border-radius:8px;border:1px solid rgba(239,68,68,.3);background:var(--surface);color:var(--text);font-size:13px;font-family:var(--font);outline:none;cursor:pointer;">
          <option value="">— My own settings —</option>
          ${clientList.map(c => `<option value="${c.id}" ${c.id === selectedClientId ? 'selected' : ''}>${c.email} (${c.global_level})</option>`).join('')}
        </select>
        ${selectedClient ? `<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(239,68,68,.1);color:#EF4444;font-weight:600;">Editing: ${selectedClient.email}</span>` : ''}
      </div>` : '';

    content.innerHTML = `
      <div class="page-animate" style="padding:24px;display:flex;flex-direction:column;gap:24px;">

        <!-- Header -->
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div>
            <h1 class="page-title">Autonomy Control</h1>
            <p class="page-subtitle">Set operational boundaries for AI decision autonomy</p>
          </div>
          ${!isAdmin ? `
          <div style="display:flex;align-items:center;gap:8px;padding:8px 14px;border-radius:var(--radius);border:1px solid var(--border);background:rgba(30,41,59,.5);">
            <i class="bi bi-eye" style="font-size:13px;color:var(--muted);"></i>
            <span style="font-size:11px;font-weight:600;color:var(--muted);">YOUR ACCOUNT SETTINGS</span>
          </div>` : ''}
        </div>

        <!-- Admin Client Picker -->
        ${clientPickerHtml}

        <!-- Save status -->
        <div id="auto-save-status" style="display:none;padding:10px 14px;border-radius:8px;font-size:12px;"></div>

        <!-- Global Level Cards -->
        <div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
            <span style="font-size:13px;font-weight:600;color:var(--text);">
              ${isGlobal ? 'Global Autonomy Level' : `${(moduleKey.charAt(0).toUpperCase() + moduleKey.slice(1))} Autonomy Level`}
            </span>
            ${isAdmin ? `
            <button id="disable-all-btn" class="btn btn-danger btn-sm">
              <i class="bi bi-x-circle"></i> ${isGlobal ? 'Disable All' : 'Set to Observe'}
            </button>` : ''}
          </div>
          <div class="autonomy-grid" id="level-cards">
            ${LEVELS.map(l => buildLevelCard(l, isAdmin)).join('')}
          </div>
        </div>

        <!-- Warning Banner (Autonomous mode) -->
        <div class="warning-banner" id="autonomous-warning" style="display:${globalLevel === 'autonomous' ? 'flex' : 'none'};">
          <div class="warning-icon-wrap"><i class="bi bi-exclamation-triangle-fill"></i></div>
          <div>
            <div class="warning-title">Full Autonomy Activated</div>
            <div class="warning-desc">The AI will execute decisions automatically without human approval. Monitor actively.</div>
            ${isAdmin ? `
            <div class="warning-actions">
              <button class="btn btn-danger btn-sm" id="emergency-override"><i class="bi bi-x-octagon"></i> Emergency Override</button>
              <button class="btn btn-secondary btn-sm" id="switch-to-assist">Switch to Assist</button>
            </div>` : `
            <div class="warning-actions">
              <button class="btn btn-secondary btn-sm" id="switch-to-assist">Switch to Assist</button>
            </div>`}
          </div>
        </div>

        <!-- Per-module overrides (global view only) -->
        ${isGlobal ? `
        <div class="card">
          <div class="card-title">
            <i class="bi bi-grid-3x3-gap" style="color:var(--accent);"></i>
            Per-Module Autonomy Override
            ${!isAdmin ? '<span style="margin-left:auto;font-size:10px;font-weight:600;color:var(--dim);background:rgba(30,41,59,.6);padding:2px 8px;border-radius:4px;">YOUR SETTINGS</span>' : ''}
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;" id="module-rows">
            ${MODULE_DEFS.map(m => buildModuleRow(m, isAdmin)).join('')}
          </div>
        </div>` : ''}

      </div>`;

    bindAutonomyEvents(isAdmin, isGlobal);
  }

  /* ── Card builders ───────────────────────────────────────── */
  function buildLevelCard(l, isAdmin) {
    const isActive  = globalLevel === l.key;
    const isGated   = !isAdmin && isLevelGated(l.key, null);
    const lockTitle = isGated ? `Upgrade to unlock ${l.label} mode` : '';
    return `
      <div class="autonomy-card ${isActive ? 'is-active' : ''} ${isGated ? 'is-gated' : ''}"
           id="level-card-${l.key}" data-level="${l.key}"
           style="${isActive ? `border-color:${l.color};box-shadow:0 0 30px ${l.bg};` : ''}${isGated ? 'opacity:0.55;cursor:not-allowed;position:relative;' : ''}"
           role="${isAdmin && !isGated ? 'button' : 'presentation'}" tabindex="${isAdmin && !isGated ? 0 : -1}"
           title="${lockTitle}">
        ${isGated ? `<div style="position:absolute;top:8px;right:8px;background:rgba(245,158,11,.15);border-radius:6px;padding:3px 7px;display:flex;align-items:center;gap:4px;"><i class="bi bi-lock-fill" style="color:#F59E0B;font-size:11px;"></i><span style="font-size:10px;color:#F59E0B;font-weight:700;">${userPlan.toUpperCase()}</span></div>` : ''}
        <i class="bi bi-check-circle-fill autonomy-check" style="color:${l.color};"></i>
        <div class="autonomy-level-icon" style="background:${l.bg};">
          <i class="bi ${l.icon}" style="color:${l.color};font-size:24px;"></i>
        </div>
        <div class="autonomy-title">${l.label}</div>
        <div class="autonomy-desc">${l.desc}</div>
        <ul class="autonomy-features">
          ${l.features.map(f => `<li>${f}</li>`).join('')}
        </ul>
        ${isGated ? `<div style="font-size:11px;color:#F59E0B;text-align:center;margin-top:6px;">🔒 Upgrade to unlock</div>` : ''}
      </div>`;
  }

  function buildModuleRow(m, isAdmin) {
    const setting = moduleSettings[m.key] || 'assist';
    const isLocked = lockedModules.includes(m.key) && !isAdmin;
    return `
      <div class="module-row">
        <div class="module-row-left">
          <div class="module-icon-sq" style="background:${m.color}18;color:${m.color};"><i class="bi ${m.icon}"></i></div>
          <div class="module-row-info">
            <div class="module-row-name">
              ${m.label}
              ${isLocked ? '<i class="bi bi-lock-fill" style="font-size:11px;color:var(--dim);margin-left:6px;" title="Locked by admin"></i>' : ''}
            </div>
            <div class="module-row-status">
              <span class="module-row-dot" style="background:${levelColor(setting)};"></span>
              <span style="text-transform:capitalize;">${setting}</span>
              ${isLocked ? '<span style="font-size:10px;color:var(--dim);margin-left:4px;">(locked)</span>' : ''}
            </div>
          </div>
        </div>
        <div class="module-pill-group" data-module="${m.key}">
          ${['observe', 'assist', 'autonomous'].map(lv => {
            const gated   = !isAdmin && isLevelGated(lv, m.key);
            const blocked = isLocked || gated;
            const lockTip = gated ? `Upgrade to ${gated ? userPlan + ' plan' : ''} to unlock` : (isLocked ? 'Locked by admin' : '');
            return `<button class="module-pill ${setting === lv ? 'is-active' : ''}"
                    data-module="${m.key}" data-level="${lv}"
                    style="${setting === lv ? `background:${m.color}18;color:${m.color};border-color:${m.color}40;` : ''}${blocked ? 'opacity:0.45;cursor:not-allowed;' : ''}"
                    ${blocked ? 'disabled' : ''}
                    title="${lockTip}">
              ${gated ? '<i class="bi bi-lock-fill" style="font-size:9px;margin-right:3px;color:#F59E0B;"></i>' : ''}${lv.charAt(0).toUpperCase() + lv.slice(1)}
            </button>`;
          }).join('')}
        </div>
      </div>`;
  }

  /* ── Event binding ────────────────────────────────────────── */
  function bindAutonomyEvents(isAdmin, isGlobal) {
    // Level card clicks
    document.querySelectorAll('.autonomy-card').forEach(card => {
      if (card.getAttribute('role') === 'button' && !card.classList.contains('is-gated')) {
        card.addEventListener('click', () => setGlobalLevel(card.dataset.level, isAdmin, isGlobal));
      }
    });

    // Module pill clicks
    if (isGlobal) bindModulePills(isAdmin);

    // Disable all
    document.getElementById('disable-all-btn')?.addEventListener('click', async () => {
      setGlobalLevel('observe', isAdmin, isGlobal);
      if (isGlobal) {
        MODULE_DEFS.forEach(m => { moduleSettings[m.key] = 'observe'; });
        refreshModuleRows(isAdmin);
      }
      updateWarningBanner();
      await persit(isAdmin);
    });

    // Emergency override & switch to assist
    document.getElementById('emergency-override')?.addEventListener('click', async () => {
      setGlobalLevel('observe', isAdmin, isGlobal);
      MODULE_DEFS.forEach(m => { moduleSettings[m.key] = 'observe'; });
      if (isGlobal) refreshModuleRows(isAdmin);
      await persit(isAdmin);
    });
    document.getElementById('switch-to-assist')?.addEventListener('click', async () => {
      setGlobalLevel('assist', isAdmin, isGlobal);
      await persit(isAdmin);
    });
  }

  function bindModulePills(isAdmin) {
    // Admin client selector — reload autonomy when client changes
    const clientSel = document.getElementById('autonomy-client-selector');
    if (clientSel) {
      clientSel.addEventListener('change', async () => {
        selectedClientId = clientSel.value || null;
        const content = document.getElementById('page-content');
        const moduleKey = window.CURRENT_MODULE || 'neural-orbit';
        const isGlobal = moduleKey === 'neural-orbit';
        if (content) content.innerHTML = `<div style="padding:24px;display:flex;flex-direction:column;gap:20px;"><div style="height:36px;width:260px;border-radius:10px;background:rgba(91,140,255,.08);animation:pulse 1.5s infinite;"></div></div>`;
        await loadAutonomy(selectedClientId);
        if (!isGlobal) globalLevel = moduleSettings[moduleKey] || 'assist';
        renderAutonomy(content, true, isGlobal, moduleKey);
      });
    }

    document.querySelectorAll('.module-pill').forEach(btn => {
      btn.addEventListener('click', async () => {
        const mod = btn.dataset.module;
        const lv  = btn.dataset.level;
        if (btn.disabled) return;  // plan-gated or admin-locked
        if (lockedModules.includes(mod) && !isAdmin) return;
        moduleSettings[mod] = lv;
        refreshModuleRows(isAdmin);
        updateWarningBanner();
        await persit(isAdmin);
      });
    });
  }

  async function persit(isAdmin) {
    let res;
    if (isAdmin) {
      res = await saveAutonomy(selectedClientId);  // admin path: existing endpoint
    } else {
      res = await saveMyAutonomy();                // user path: new /user/autonomy endpoint
    }
    const clientLabel = selectedClientId ? ' for client' : '';
    showAutoSaveStatus(res && res.status === 'ok',
      res ? `✓ Autonomy settings saved${clientLabel}` : '✗ Saved locally only — backend unavailable');
  }

  function setGlobalLevel(lvl, isAdmin, isGlobal) {
    globalLevel = lvl;
    LEVELS.forEach(l => {
      const card = document.getElementById(`level-card-${l.key}`);
      if (!card) return;
      const isActive = l.key === lvl;
      card.classList.toggle('is-active', isActive);
      card.style.borderColor = isActive ? l.color : '';
      card.style.boxShadow = isActive ? `0 0 30px ${l.bg}` : '';
    });
    updateWarningBanner();
  }

  function updateWarningBanner() {
    const anyAuto = globalLevel === 'autonomous' || Object.values(moduleSettings).some(v => v === 'autonomous');
    const banner = document.getElementById('autonomous-warning');
    if (banner) banner.style.display = anyAuto ? 'flex' : 'none';
  }

  function refreshModuleRows(isAdmin) {
    const container = document.getElementById('module-rows');
    if (!container) return;
    container.innerHTML = MODULE_DEFS.map(m => buildModuleRow(m, isAdmin)).join('');
    bindModulePills(isAdmin);
  }

  function showAutoSaveStatus(ok, msg) {
    const el = document.getElementById('auto-save-status');
    if (!el) return;
    el.style.display = 'block';
    el.style.background = ok ? 'rgba(34,197,94,.1)' : 'rgba(245,158,11,.08)';
    el.style.color = ok ? '#22C55E' : '#F59E0B';
    el.style.border = `1px solid ${ok ? 'rgba(34,197,94,.3)' : 'rgba(245,158,11,.2)'}`;
    el.textContent = msg;
    setTimeout(() => { el.style.display = 'none'; }, 3000);
  }

  function levelColor(lvl) { return { observe: '#94A3B8', assist: '#5B8CFF', autonomous: '#22C55E' }[lvl] || '#94A3B8'; }

})();
