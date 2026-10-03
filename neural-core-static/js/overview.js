/* ============================================================
   overview.js — NeuralOrbit Executive Overview (Module-Aware)
   KPI cards + Chart.js area chart + AI Insight banner
   Reads window.CURRENT_MODULE to show correct module data.
   ============================================================ */

(function () {
  'use strict';

  const BACKEND = window.BACKEND_URL || 'http://127.0.0.1:8000';

  async function apiFetch(path) {
    try {
      const token = localStorage.getItem('neuralorbit_token');
      const res = await fetch(BACKEND + path, {
        signal: AbortSignal.timeout(5000),
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }

  /* -------------------------------------------------------
     MODULE-SPECIFIC DATA
  ------------------------------------------------------- */
  const moduleData = {
    'neural-orbit': {
      title: 'Executive Overview',
      subtitle: 'Real-time performance intelligence across all AI modules',
      insight: 'Your business is 4.1% smarter than last week',
      insightSub: 'NeuralOrbit AI Insight — Based on 1,847 data points analyzed in the last 7 days',
      kpis: [
        { title: 'Business Intelligence Score', value: '87.3', unit: '/100', change: '+4.1%', trend: 'up', icon: 'bi-cpu', color: '#5B8CFF', desc: 'Composite AI intelligence rating' },
        { title: 'Revenue Momentum', value: '$2.4M', unit: '/mo', change: '+12.8%', trend: 'up', icon: 'bi-graph-up-arrow', color: '#22C55E', desc: 'Monthly recurring revenue trend' },
        { title: 'AI Confidence', value: '94.7', unit: '%', change: '+2.3%', trend: 'up', icon: 'bi-bullseye', color: '#8B5CF6', desc: 'Average decision confidence level' },
        { title: 'Risk Index', value: '12.1', unit: '/100', change: '-3.2%', trend: 'up', icon: 'bi-shield-exclamation', color: '#F59E0B', desc: 'Aggregate operational risk score' },
      ],
      chartLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12'],
      chartA: { label: 'Intelligence', data: [72, 74, 73, 78, 80, 79, 83, 85, 84, 88, 90, 87], color: '#5B8CFF' },
      chartB: { label: 'Revenue', data: [18, 19.5, 18.7, 20.5, 21, 22, 21.5, 22.8, 23.1, 23.9, 24.5, 24], color: '#22C55E' },
      chartC: { label: 'Confidence', data: [88, 89, 88, 90, 91, 91, 92, 93, 92, 94, 95, 95], color: '#8B5CF6' },
    },
    'crm': {
      title: 'CRM Overview',
      subtitle: 'AI-powered lead intelligence and pipeline performance',
      insight: 'Lead conversion improved by 5.1% this week — AI pipeline scoring driving results',
      insightSub: 'NeuralOrbit CRM AI — Based on 1,247 lead interactions in the last 7 days',
      kpis: [
        { title: 'Active Leads', value: '1,247', unit: '', change: '+18.4%', trend: 'up', icon: 'bi-people', color: '#5B8CFF', desc: 'Leads in active pipeline' },
        { title: 'Conversion Rate', value: '34.2', unit: '%', change: '+5.1%', trend: 'up', icon: 'bi-graph-up', color: '#22C55E', desc: 'Leads converted to customers' },
        { title: 'Avg Deal Value', value: '$24.8K', unit: '', change: '+12.3%', trend: 'up', icon: 'bi-currency-dollar', color: '#8B5CF6', desc: 'Average deal size closed' },
        { title: 'Pipeline Velocity', value: '8.4', unit: '/day', change: '+6.7%', trend: 'up', icon: 'bi-lightning', color: '#F59E0B', desc: 'Leads advancing per day' },
      ],
      chartLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12'],
      chartA: { label: 'Leads', data: [820, 870, 860, 920, 980, 940, 1050, 1100, 1090, 1180, 1220, 1247], color: '#5B8CFF' },
      chartB: { label: 'Conversions', data: [28, 29, 28.5, 30, 31, 31.5, 32, 33, 32.5, 34, 34.5, 34.2], color: '#22C55E' },
      chartC: { label: 'Deal Value', data: [18, 19, 19.5, 20, 21, 21.5, 22, 23, 22.5, 23.5, 24, 24.8], color: '#8B5CF6' },
    },
    'marketing': {
      title: 'Marketing Overview',
      subtitle: 'AI-optimized campaign performance and ROI intelligence',
      insight: 'Campaign ROAS increased 21.3% — AI reallocated budget to top 3 performers',
      insightSub: 'NeuralOrbit Marketing AI — Based on 14 active campaigns analyzed this week',
      kpis: [
        { title: 'Campaign ROAS', value: '4.8', unit: 'x', change: '+21.3%', trend: 'up', icon: 'bi-bar-chart', color: '#8B5CF6', desc: 'Return on ad spend' },
        { title: 'Cost Per Lead', value: '$18.40', unit: '', change: '-14.2%', trend: 'up', icon: 'bi-coin', color: '#22C55E', desc: 'Average cost per acquired lead' },
        { title: 'Email Open Rate', value: '42.1', unit: '%', change: '+8.7%', trend: 'up', icon: 'bi-envelope-open', color: '#5B8CFF', desc: 'AI-optimized send times' },
        { title: 'Ad Spend Efficiency', value: '87', unit: '%', change: '+11.2%', trend: 'up', icon: 'bi-pie-chart', color: '#F59E0B', desc: 'Spend allocation accuracy' },
      ],
      chartLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12'],
      chartA: { label: 'ROAS', data: [3.0, 3.1, 3.2, 3.5, 3.7, 3.8, 4.0, 4.2, 4.3, 4.5, 4.7, 4.8], color: '#8B5CF6' },
      chartB: { label: 'Open Rate', data: [35, 36, 35.5, 37, 38, 39, 40, 41, 40.5, 41.5, 42, 42.1], color: '#5B8CFF' },
      chartC: { label: 'Efficiency', data: [70, 72, 73, 75, 77, 78, 80, 82, 83, 85, 86, 87], color: '#22C55E' },
    },
    'shield': {
      title: 'Shield Overview',
      subtitle: 'AI-powered threat detection and compliance intelligence',
      insight: 'Shield blocked 33% more threats this week with 0.02% false positive rate',
      insightSub: 'NeuralOrbit Shield AI — Monitoring 847 active security signals 24/7',
      kpis: [
        { title: 'Threats Blocked', value: '2,841', unit: '', change: '+33.1%', trend: 'up', icon: 'bi-shield-check', color: '#F59E0B', desc: 'Threats neutralized this period' },
        { title: 'False Positive Rate', value: '0.02', unit: '%', change: '-61.4%', trend: 'up', icon: 'bi-check-circle', color: '#22C55E', desc: 'AI accuracy in threat detection' },
        { title: 'Response Time', value: '180', unit: 'ms', change: '-47.2%', trend: 'up', icon: 'bi-lightning', color: '#5B8CFF', desc: 'Avg threat containment speed' },
        { title: 'Security Score', value: '98.4', unit: '/100', change: '+4.1%', trend: 'up', icon: 'bi-shield-fill', color: '#8B5CF6', desc: 'Overall security health' },
      ],
      chartLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12'],
      chartA: { label: 'Threats Blocked', data: [1800, 1900, 1950, 2100, 2200, 2300, 2400, 2500, 2550, 2700, 2800, 2841], color: '#F59E0B' },
      chartB: { label: 'Security Score', data: [90, 91, 91, 92, 93, 94, 95, 96, 96, 97, 98, 98.4], color: '#22C55E' },
      chartC: { label: 'Response(ms/10)', data: [34, 32, 30, 28, 26, 25, 24, 22, 21, 20, 19, 18], color: '#5B8CFF' },
    },
    'website': {
      title: 'Website Overview',
      subtitle: 'AI-driven conversion optimization and user experience intelligence',
      insight: 'Website conversion rate improved 31.2% — 14 concurrent A/B tests running',
      insightSub: 'NeuralOrbit Website AI — Personalizing content for every visitor in real-time',
      kpis: [
        { title: 'Conversion Rate', value: '4.7', unit: '%', change: '+31.2%', trend: 'up', icon: 'bi-graph-up-arrow', color: '#22C55E', desc: 'Visitors converting to leads' },
        { title: 'Bounce Rate', value: '18.3', unit: '%', change: '-22.1%', trend: 'up', icon: 'bi-arrow-left-right', color: '#5B8CFF', desc: 'Single-page session rate' },
        { title: 'Avg Session Value', value: '$8.40', unit: '', change: '+19.8%', trend: 'up', icon: 'bi-currency-dollar', color: '#8B5CF6', desc: 'Revenue attributed per session' },
        { title: 'Core Web Vitals', value: '94', unit: '/100', change: '+7.4%', trend: 'up', icon: 'bi-speedometer2', color: '#F59E0B', desc: 'Google performance score' },
      ],
      chartLabels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12'],
      chartA: { label: 'Conversion %', data: [2.8, 3.0, 3.1, 3.5, 3.7, 3.9, 4.0, 4.2, 4.3, 4.5, 4.6, 4.7], color: '#22C55E' },
      chartB: { label: 'Session Value', data: [5.5, 5.8, 6.0, 6.4, 6.8, 7.0, 7.2, 7.6, 7.8, 8.0, 8.2, 8.4], color: '#8B5CF6' },
      chartC: { label: 'Web Vitals', data: [80, 82, 83, 85, 87, 88, 89, 90, 91, 92, 93, 94], color: '#5B8CFF' },
    },
  };

  /* -------------------------------------------------------
     CHART INSTANCE (preserve for re-render)
  ------------------------------------------------------- */
  let overviewChartInstance = null;

  /* -------------------------------------------------------
     RENDER
  ------------------------------------------------------- */
  window.loadOverview = async function () {
    const content = document.getElementById('page-content');
    if (!content) return;

    const moduleKey = window.CURRENT_MODULE || 'neural-orbit';
    const isAdmin = window.CURRENT_ROLE === 'admin';

    // Show skeleton while loading
    content.innerHTML = `<div style="padding:24px;display:flex;flex-direction:column;gap:20px;">
      <div style="height:28px;width:260px;border-radius:8px;background:rgba(91,140,255,.08);animation:pulse 1.5s infinite;"></div>
      <div class="kpi-grid">${Array(4).fill('<div style="border-radius:14px;background:rgba(91,140,255,.05);height:120px;animation:pulse 1.5s infinite;"></div>').join('')}</div>
      <div style="border-radius:14px;background:rgba(91,140,255,.05);height:320px;animation:pulse 1.5s infinite;"></div>
    </div>`;

    // Try backend first
    const apiData = await apiFetch(`/api/v1/analytics/overview?module=${moduleKey}`);

    // Session check: is this a demo user?
    const session = window.NOAuth.getSession();
    const isDemoAccount = session && window.DEMO_CREDENTIALS && window.DEMO_CREDENTIALS[session.email];

    // Merge: if backend returned real KPIs, use them; else fall back to static
    let d = moduleData[moduleKey] || moduleData['neural-orbit'];
    let hasRealData = false;
    let noDataMsg = '';

    if (apiData && apiData.kpis) {
      hasRealData = apiData.has_data || false;
      if (hasRealData) {
        // Real data — override KPIs with backend values
        d = {
          ...d,
          kpis: apiData.kpis,
          insight: apiData.insight || d.insight,
          insightSub: apiData.insight_sub || d.insightSub,
        };
      } else {
        // Backend responded but no data yet
        if (isDemoAccount) {
            // Keep demo data visible for developer accounts
            d = { ...d, kpis: apiData.kpis, insight: apiData.insight || d.insight, insightSub: apiData.insight_sub || d.insightSub };
            noDataMsg = apiData.insight || '';
        } else {
            // REAL USER with NO DATA: Zero out everything for a clean slate
            d = { 
                ...d, 
                kpis: d.kpis.map(k => ({ ...k, value: '0', change: '0%', trend: 'up' })),
                chartA: { ...d.chartA, data: d.chartA.data.map(() => 0) },
                chartB: { ...d.chartB, data: d.chartB.data.map(() => 0) },
                chartC: { ...d.chartC, data: d.chartC.data.map(() => 0) },
                insight: 'Connect your business tools to generate AI insights.',
                insightSub: 'NeuralOrbit AI is currently in sleep mode.'
            };
            noDataMsg = 'Your dashboard is ready. Connect an integration to start gathering data.';
        }
      }
    } else if (!isDemoAccount) {
        // Fallback for real users if API fails or backend is down
        d = { 
            ...d, 
            kpis: d.kpis.map(k => ({ ...k, value: '--', change: '0%', trend: 'up' })),
            chartA: { ...d.chartA, data: d.chartA.data.map(() => 0) },
            chartB: { ...d.chartB, data: d.chartB.data.map(() => 0) },
            chartC: { ...d.chartC, data: d.chartC.data.map(() => 0) },
            insight: 'Waiting for system handshake...',
            insightSub: 'Connect integrations to activate intelligence.'
        };
    }

    content.innerHTML = `
            <div class="page-animate" style="padding: 24px; display: flex; flex-direction: column; gap: 24px; min-height: 100%;">

                <!-- Page Header -->
                <div>
                    <h1 class="page-title">${isAdmin && moduleKey === 'neural-orbit' ? 'Platform Overview' : d.title}</h1>
                    <p class="page-subtitle">${isAdmin && moduleKey === 'neural-orbit' ? 'AI performance intelligence across all client businesses' : d.subtitle}</p>
                </div>

                ${!hasRealData ? `
                <!-- Onboarding Dashboard -->
                <div class="card onboarding-card" style="padding: 30px; background: linear-gradient(135deg, rgba(91,140,255,0.1), rgba(139,92,246,0.1)); border: 1px solid rgba(91,140,255,0.2); margin-bottom: 24px;">
                    <div style="display: flex; align-items: flex-start; gap: 20px;">
                        <div style="width: 50px; height: 50px; border-radius: 12px; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 24px; box-shadow: 0 4px 15px rgba(91,140,255,0.3);">
                            <i class="bi bi-rocket-takeoff"></i>
                        </div>
                        <div style="flex: 1;">
                            <h2 style="font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 8px;">Welcome to your NeuralOrbit Workspace</h2>
                            <p style="font-size: 14px; color: var(--dim); line-height: 1.6; max-width: 600px; margin-bottom: 20px;">
                                Your AI Operating System is initialized and ready. To start gathering intelligence, scoring rewards, and automating your growth, connect your first business tool.
                            </p>
                            <div style="display: flex; gap: 12px;">
                                <button onclick="window._routerDispatch('integrations')" class="btn-primary" style="padding: 10px 20px; font-size: 14px;">
                                    <i class="bi bi-plug"></i> Connect Integrations
                                </button>
                                <button onclick="window.location.hash='#intelligence-docs'" class="btn-subtle" style="padding: 10px 20px; font-size: 14px;">
                                    <i class="bi bi-book"></i> Read Docs
                                </button>
                            </div>
                        </div>
                    </div>
                </div>` : ''}

                <!-- KPI Cards -->
                <div class="kpi-grid">
                    ${d.kpis.map(kpi => buildKPICard(kpi)).join('')}
                </div>

                <!-- Area Chart -->
                <div class="card" style="padding: 24px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                        <div>
                            <div class="card-title" style="margin-bottom: 4px;">
                                <i class="bi bi-graph-up" style="color: var(--accent);"></i>
                                ${d.title} — Weekly Growth
                            </div>
                            <p style="font-size: 12px; color: var(--dim);">${hasRealData ? 'Live data from your integrations' : '12-week performance trajectory (demo)'}</p>
                        </div>
                        <div class="chart-legend">
                            <div class="legend-item"><div class="legend-line" style="background:${d.chartA.color};"></div><span>${d.chartA.label}</span></div>
                            <div class="legend-item"><div class="legend-line" style="background:${d.chartB.color};"></div><span>${d.chartB.label}</span></div>
                            <div class="legend-item"><div class="legend-line" style="background:${d.chartC.color};"></div><span>${d.chartC.label}</span></div>
                        </div>
                    </div>
                    <div class="chart-wrap" style="height: 300px;">
                        <canvas id="overview-chart"></canvas>
                    </div>
                </div>

                 <!-- AI Insight Banner -->
                <div class="ai-insight">
                    <div class="ai-insight-left">
                        <div class="ai-insight-icon"><i class="bi bi-stars"></i></div>
                        <div>
                            <div class="ai-insight-quote" id="insight-quote">${d.insight}</div>
                            <div class="ai-insight-sub" id="insight-sub">${d.insightSub}</div>
                        </div>
                    </div>
                    <div class="ai-insight-right">
                        <div class="ai-generated-badge" id="insight-refresh-btn" style="cursor:pointer;user-select:none;transition:opacity .15s;" title="Click to refresh AI insight">
                            <i class="bi bi-cpu"></i> AI GENERATED &nbsp;<i class="bi bi-arrow-clockwise" style="font-size:10px;opacity:.7;"></i>
                        </div>
                    </div>
                </div>

            </div>
        `;

    requestAnimationFrame(() => initOverviewChart(d));

    // Wire the AI insight refresh button
    document.getElementById('insight-refresh-btn')?.addEventListener('click', async function() {
        const btn = this;
        const quoteEl = document.getElementById('insight-quote');
        const subEl = document.getElementById('insight-sub');
        if (!quoteEl || !subEl) return;
        btn.style.opacity = '0.5';
        btn.innerHTML = '<div class="apply-btn-spinner" style="width:12px;height:12px;display:inline-block;"></div> Thinking…';
        const token = localStorage.getItem('neuralorbit_token');
        const module = window.CURRENT_MODULE || 'neural-orbit';
        const res = await apiFetch('/api/v1/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
            body: JSON.stringify({ module, question: `Give me the most important action I should take for my ${module} module right now, based on recent performance data.`, context: { source: 'overview_insight' } }),
        }).catch(() => null);
        btn.style.opacity = '1';
        btn.innerHTML = '<i class="bi bi-cpu"></i> AI GENERATED &nbsp;<i class="bi bi-arrow-clockwise" style="font-size:10px;opacity:.7;"></i>';
        if (res?.result?.recommendation) {
            quoteEl.style.transition = 'opacity .2s';
            quoteEl.style.opacity = '0';
            setTimeout(() => {
                quoteEl.textContent = res.result.recommendation;
                subEl.textContent = `NeuralOrbit AI — ${new Date().toLocaleTimeString()} · Confidence ${Math.round((res.result.confidence || 0.9) * 100)}%`;
                quoteEl.style.opacity = '1';
            }, 200);
        } else {
            quoteEl.style.opacity = '0';
            setTimeout(() => {
                quoteEl.textContent = 'AI insight unavailable — make sure backend is running and OPENAI_API_KEY is set in .env';
                quoteEl.style.opacity = '1';
            }, 200);
        }
    });
  };

  /* -------------------------------------------------------
     KPI CARD BUILDER
  ------------------------------------------------------- */
  function buildKPICard(kpi) {
    const trendClass = kpi.trend === 'up' ? 'trend-up' : 'trend-down';
    const trendIcon = kpi.trend === 'up' ? 'bi-arrow-up' : 'bi-arrow-down';
    return `
            <div class="kpi-card">
                <div class="kpi-card-top">
                    <div class="kpi-icon" style="background: ${kpi.color}18; color: ${kpi.color};">
                        <i class="${kpi.icon}"></i>
                    </div>
                    <div class="kpi-trend ${trendClass}">
                        <i class="bi ${trendIcon}"></i> ${kpi.change}
                    </div>
                </div>
                <div class="kpi-value">
                    ${kpi.value}
                    ${kpi.unit ? `<span class="kpi-unit">${kpi.unit}</span>` : ''}
                </div>
                <div class="kpi-label">${kpi.title}</div>
                <div class="kpi-desc">${kpi.desc}</div>
            </div>
        `;
  }

  /* -------------------------------------------------------
     CHART.JS AREA CHART
  ------------------------------------------------------- */
  function initOverviewChart(d) {
    const canvas = document.getElementById('overview-chart');
    if (!canvas) return;

    if (overviewChartInstance) { overviewChartInstance.destroy(); overviewChartInstance = null; }

    const ctx = canvas.getContext('2d');

    function makeGrad(color) {
      const g = ctx.createLinearGradient(0, 0, 0, 300);
      g.addColorStop(0, color.replace(')', ', 0.28)').replace('rgb', 'rgba'));
      g.addColorStop(1, color.replace(')', ', 0.00)').replace('rgb', 'rgba'));
      return g;
    }

    function hexToRgba(hex, alpha) {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `rgba(${r},${g},${b},${alpha})`;
    }

    const gradA = ctx.createLinearGradient(0, 0, 0, 300);
    gradA.addColorStop(0, hexToRgba(d.chartA.color, 0.28));
    gradA.addColorStop(1, hexToRgba(d.chartA.color, 0.00));

    const gradB = ctx.createLinearGradient(0, 0, 0, 300);
    gradB.addColorStop(0, hexToRgba(d.chartB.color, 0.18));
    gradB.addColorStop(1, hexToRgba(d.chartB.color, 0.00));

    const gradC = ctx.createLinearGradient(0, 0, 0, 300);
    gradC.addColorStop(0, hexToRgba(d.chartC.color, 0.22));
    gradC.addColorStop(1, hexToRgba(d.chartC.color, 0.00));

    overviewChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: d.chartLabels,
        datasets: [
          { label: d.chartA.label, data: d.chartA.data, borderColor: d.chartA.color, backgroundColor: gradA, borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5 },
          { label: d.chartB.label, data: d.chartB.data, borderColor: d.chartB.color, backgroundColor: gradB, borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5 },
          { label: d.chartC.label, data: d.chartC.data, borderColor: d.chartC.color, backgroundColor: gradC, borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: '#111827', borderColor: 'rgba(91,140,255,0.2)', borderWidth: 1, titleColor: '#94A3B8', bodyColor: '#E2E8F0', padding: 12, cornerRadius: 8 },
        },
        scales: {
          x: { grid: { color: 'rgba(91,140,255,0.06)' }, border: { color: 'rgba(91,140,255,0.1)' }, ticks: { color: '#64748B', font: { size: 11 } } },
          y: { grid: { color: 'rgba(91,140,255,0.06)' }, border: { color: 'rgba(91,140,255,0.1)' }, ticks: { color: '#64748B', font: { size: 11 } }, min: 0 },
        },
      },
    });
  }

})();
