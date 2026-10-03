/* ============================================================
   learning.js — NeuralOrbit Learning Timeline (Module-Aware)
   Filters chart and notes by CURRENT_MODULE.
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
     PER-MODULE DATA (fallback/demo)
  ------------------------------------------------------- */
  const allWeeklyData = {
    'neural-orbit': [
      { week: 'W1', accuracy: 72, decisions: 620, corrections: 48 }, { week: 'W2', accuracy: 75, decisions: 745, corrections: 41 },
      { week: 'W3', accuracy: 74, decisions: 762, corrections: 43 }, { week: 'W4', accuracy: 79, decisions: 878, corrections: 37 },
      { week: 'W5', accuracy: 82, decisions: 945, corrections: 30 }, { week: 'W6', accuracy: 81, decisions: 1010, corrections: 31 },
      { week: 'W7', accuracy: 85, decisions: 1134, corrections: 22 }, { week: 'W8', accuracy: 88, decisions: 1256, corrections: 16 },
      { week: 'W9', accuracy: 87, decisions: 1278, corrections: 17 }, { week: 'W10', accuracy: 91, decisions: 1401, corrections: 10 },
      { week: 'W11', accuracy: 93, decisions: 1524, corrections: 7 }, { week: 'W12', accuracy: 95, decisions: 1648, corrections: 4 },
    ],
    'crm': [
      { week: 'W1', accuracy: 68, decisions: 120, corrections: 18 }, { week: 'W2', accuracy: 71, decisions: 145, corrections: 15 },
      { week: 'W3', accuracy: 70, decisions: 162, corrections: 16 }, { week: 'W4', accuracy: 76, decisions: 178, corrections: 12 },
      { week: 'W5', accuracy: 79, decisions: 195, corrections: 10 }, { week: 'W6', accuracy: 78, decisions: 210, corrections: 11 },
      { week: 'W7', accuracy: 83, decisions: 234, corrections: 8 }, { week: 'W8', accuracy: 86, decisions: 256, corrections: 6 },
      { week: 'W9', accuracy: 85, decisions: 278, corrections: 7 }, { week: 'W10', accuracy: 90, decisions: 301, corrections: 4 },
      { week: 'W11', accuracy: 92, decisions: 324, corrections: 3 }, { week: 'W12', accuracy: 94, decisions: 348, corrections: 2 },
    ],
    'marketing': [
      { week: 'W1', accuracy: 70, decisions: 88, corrections: 14 }, { week: 'W2', accuracy: 73, decisions: 102, corrections: 11 },
      { week: 'W3', accuracy: 72, decisions: 115, corrections: 12 }, { week: 'W4', accuracy: 78, decisions: 128, corrections: 9 },
      { week: 'W5', accuracy: 81, decisions: 140, corrections: 8 }, { week: 'W6', accuracy: 80, decisions: 155, corrections: 8 },
      { week: 'W7', accuracy: 84, decisions: 168, corrections: 6 }, { week: 'W8', accuracy: 87, decisions: 182, corrections: 5 },
      { week: 'W9', accuracy: 86, decisions: 196, corrections: 5 }, { week: 'W10', accuracy: 90, decisions: 210, corrections: 3 },
      { week: 'W11', accuracy: 93, decisions: 226, corrections: 2 }, { week: 'W12', accuracy: 95, decisions: 241, corrections: 1 },
    ],
    'shield': [
      { week: 'W1', accuracy: 82, decisions: 240, corrections: 11 }, { week: 'W2', accuracy: 84, decisions: 278, corrections: 9 },
      { week: 'W3', accuracy: 83, decisions: 301, corrections: 10 }, { week: 'W4', accuracy: 87, decisions: 334, corrections: 7 },
      { week: 'W5', accuracy: 90, decisions: 368, corrections: 5 }, { week: 'W6', accuracy: 89, decisions: 395, corrections: 6 },
      { week: 'W7', accuracy: 92, decisions: 428, corrections: 4 }, { week: 'W8', accuracy: 94, decisions: 456, corrections: 3 },
      { week: 'W9', accuracy: 93, decisions: 480, corrections: 3 }, { week: 'W10', accuracy: 96, decisions: 512, corrections: 2 },
      { week: 'W11', accuracy: 97, decisions: 538, corrections: 1 }, { week: 'W12', accuracy: 98, decisions: 568, corrections: 1 },
    ],
    'website': [
      { week: 'W1', accuracy: 65, decisions: 172, corrections: 21 }, { week: 'W2', accuracy: 68, decisions: 220, corrections: 17 },
      { week: 'W3', accuracy: 67, decisions: 184, corrections: 18 }, { week: 'W4', accuracy: 74, decisions: 238, corrections: 12 },
      { week: 'W5', accuracy: 77, decisions: 242, corrections: 10 }, { week: 'W6', accuracy: 76, decisions: 250, corrections: 10 },
      { week: 'W7', accuracy: 81, decisions: 304, corrections: 7 }, { week: 'W8', accuracy: 85, decisions: 362, corrections: 5 },
      { week: 'W9', accuracy: 84, decisions: 324, corrections: 5 }, { week: 'W10', accuracy: 89, decisions: 388, corrections: 3 },
      { week: 'W11', accuracy: 91, decisions: 436, corrections: 2 }, { week: 'W12', accuracy: 93, decisions: 491, corrections: 2 },
    ],
  };

  const moduleMistakes = {
    'neural-orbit': [
      { id: 'ERR-047', severity: 'medium', module: 'Marketing', date: 'Feb 14', mistake: 'Over-allocated marketing budget to low-converting channel', correction: 'Implemented real-time ROI thresholds with automatic budget reallocation triggers', impact: 'Saved $4,200 in wasted spend after correction' },
      { id: 'ERR-046', severity: 'low', module: 'CRM', date: 'Feb 11', mistake: 'Assigned high-value lead to rep with full pipeline', correction: 'Added pipeline capacity weight to lead assignment algorithm', impact: 'Lead conversion rate improved by 8% post-correction' },
      { id: 'ERR-045', severity: 'high', module: 'Shield', date: 'Feb 7', mistake: 'Failed to detect sophisticated phishing attempt (new pattern)', correction: 'Expanded threat signature database with 340 new patterns', impact: 'Zero similar incidents since correction' },
      { id: 'ERR-044', severity: 'medium', module: 'Website', date: 'Feb 3', mistake: 'Prematurely ended A/B test before statistical significance', correction: 'Enforced minimum 5,000 visitor sample size before decision', impact: 'No premature terminations since' },
    ],
    'crm': [
      { id: 'ERR-046', severity: 'low', module: 'CRM', date: 'Feb 11', mistake: 'Assigned high-value lead to rep with full pipeline', correction: 'Added pipeline capacity weight to lead assignment algorithm', impact: 'Lead conversion rate improved by 8% post-correction' },
      { id: 'ERR-043', severity: 'medium', module: 'CRM', date: 'Jan 30', mistake: 'Over-scored a lead due to stale firmographic data', correction: 'Added data freshness signals to scoring model with 30-day TTL', impact: 'Lead quality score accuracy improved from 78% to 91%' },
    ],
    'marketing': [
      { id: 'ERR-047', severity: 'medium', module: 'Marketing', date: 'Feb 14', mistake: 'Over-allocated marketing budget to low-converting channel', correction: 'Implemented real-time ROI thresholds with automatic budget reallocation triggers', impact: 'Saved $4,200 in wasted spend after correction' },
      { id: 'ERR-042', severity: 'low', module: 'Marketing', date: 'Feb 8', mistake: 'Email send time optimization chose wrong timezone for EU segment', correction: 'Segmented timezone logic by GeolP with fallback to account timezone', impact: 'Open rate improved +11% for EU segment' },
    ],
    'shield': [
      { id: 'ERR-045', severity: 'high', module: 'Shield', date: 'Feb 7', mistake: 'Failed to detect sophisticated phishing attempt (new pattern)', correction: 'Expanded threat signature database with 340 new patterns', impact: 'Zero similar incidents since correction' },
      { id: 'ERR-041', severity: 'low', module: 'Shield', date: 'Jan 28', mistake: 'False positive blocked legitimate internal API call', correction: 'Added allowlist for verified internal service signatures', impact: 'False positive rate reduced to 0.02%' },
    ],
    'website': [
      { id: 'ERR-044', severity: 'medium', module: 'Website', date: 'Feb 3', mistake: 'Prematurely ended A/B test before statistical significance', correction: 'Enforced minimum 5,000 visitor sample size before decision', impact: 'No premature terminations since' },
      { id: 'ERR-040', severity: 'low', module: 'Website', date: 'Jan 25', mistake: 'Recommended CTA copy change during peak traffic without pre-test', correction: 'All copy changes now staged via feature flags and tested on 10% traffic first', impact: 'CTA conversion rate stable through changes' },
    ],
  };

  const moduleWeeklyNotes = {
    'neural-orbit': [
      { week: 'Week 12', date: 'Feb 10 – Feb 16', improvement: '+2.1%', notes: ['Achieved 95% accuracy milestone — highest recorded', 'CRM lead scoring model refined with 2,400 new data points', 'Marketing attribution model updated to include cross-channel signals'] },
      { week: 'Week 11', date: 'Feb 3 – Feb 9', improvement: '+2.2%', notes: ['Shield module detected and prevented 12 security anomalies', 'Reduced false positive rate by 34%', 'Integrated new behavioral pattern recognition'] },
      { week: 'Week 10', date: 'Jan 27 – Feb 2', improvement: '+4.6%', notes: ['Website optimization decisions reached 91% accuracy', 'A/B testing framework improved with Bayesian approach', 'Decision latency reduced from 340ms to 180ms'] },
    ],
    'crm': [
      { week: 'Week 12', date: 'Feb 10 – Feb 16', improvement: '+2.4%', notes: ['CRM accuracy reached 94% — best ever for lead scoring', 'ICP model refined with firmographic signals from 1,240 new accounts', 'Pipeline velocity increased by 8.4 leads/day'] },
      { week: 'Week 11', date: 'Feb 3 – Feb 9', improvement: '+2.2%', notes: ['Churn prediction model added 7 behavioral signals', 'Lead assignment algorithm refactored with capacity weighting', 'Avg deal value increased $2.1K after targeting refinement'] },
      { week: 'Week 10', date: 'Jan 27 – Feb 2', improvement: '+5.0%', notes: ['Implemented 3-tier lead qualification scoring', 'Conversion rate improved 5.1% week-over-week', 'CRM sync latency reduced from 8 minutes to 90 seconds'] },
    ],
    'marketing': [
      { week: 'Week 12', date: 'Feb 10 – Feb 16', improvement: '+2.1%', notes: ['Email open rate hit 42.1% — 14% above industry average', 'ROAS increased to 4.8x after budget reallocation AI optimized 3 failing campaigns', 'CPL fell to $18.40 from $21.40 in W10'] },
      { week: 'Week 11', date: 'Feb 3 – Feb 9', improvement: '+3.4%', notes: ['Audience segmentation model retrained with 6 new behavioral signals', '11 A/B tests concluded with 8 winners deployed', 'Attribution model now accounts for cross-channel journeys'] },
      { week: 'Week 10', date: 'Jan 27 – Feb 2', improvement: '+4.0%', notes: ['Ad creatives auto-generated from top performing content patterns', 'Keyword bidding strategy updated for Q2 intent shift', 'Email send-time personalization rolled out to all segments'] },
    ],
    'shield': [
      { week: 'Week 12', date: 'Feb 10 – Feb 16', improvement: '+1.4%', notes: ['Shield reached 98.4/100 security score — platform record', '2,841 threats blocked with 0.02% false positives', 'Response time optimized to 180ms — down from 1.2s in W1'] },
      { week: 'Week 11', date: 'Feb 3 – Feb 9', improvement: '+1.0%', notes: ['340 new threat patterns ingested from incident analysis', 'Reduced false positive rate by another 34%', 'Zero successful breaches across all monitored endpoints'] },
      { week: 'Week 10', date: 'Jan 27 – Feb 2', improvement: '+3.0%', notes: ['Behavioral anomaly detection model retrained on 90-day baseline', 'API abuse detection now identifies new exfiltration patterns', 'Compliance check coverage expanded to 98.2% of data flows'] },
    ],
    'website': [
      { week: 'Week 12', date: 'Feb 10 – Feb 16', improvement: '+2.1%', notes: ['Conversion rate hit 4.7% — 31.2% above 12-week starting point', '14 concurrent A/B tests running with no performance degradation', 'Session value reached $8.40 through intent-based personalization'] },
      { week: 'Week 11', date: 'Feb 3 – Feb 9', improvement: '+2.2%', notes: ['Core Web Vitals improved to 94/100 after image optimization AI', 'Bounce rate fell to 18.3% — lowest since launch', 'AI recommended 3 page layout changes — all outperformed control'] },
      { week: 'Week 10', date: 'Jan 27 – Feb 2', improvement: '+5.0%', notes: ['Bayesian A/B testing engine reached statistical significance 40% faster', 'Content personalization deployed to homepage, pricing, and blog', 'Mobile conversion parity achieved with desktop (±0.2%)'] },
    ],
  };

  let learningChartInstance = null;

  window.loadLearning = async function () {
    const content = document.getElementById('page-content');
    if (!content) return;

    if (learningChartInstance) { learningChartInstance.destroy(); learningChartInstance = null; }

    const moduleKey = window.CURRENT_MODULE || 'neural-orbit';

    // ── Milestone 4: Fetch real AI Intelligence Stats ────────────────────────
    const [statsRes, mistakesRes] = await Promise.all([
      apiFetch(`/api/v1/analytics/learning-stats?module=${moduleKey}`),
      apiFetch(`/api/v1/analytics/mistakes?module=${moduleKey}`),
    ]);

    let data, mistakes, overallAcc = 0, grade = '-', velocityLabel = 'Stable', usingDemo = false;

    if (statsRes && statsRes.has_data && statsRes.trend && statsRes.trend.length > 0) {
      // Use real data from Milestone 1/2/3
      data = statsRes.trend.map(t => ({
        label: t.date, // "2026-04-01"
        accuracy: t.accuracy,
        decisions: t.decisions,
        corrections: t.total - t.correct // derived
      }));
      overallAcc = statsRes.overall_accuracy;
      velocityLabel = statsRes.velocity?.label || 'Stable';
      
      // Get grade for this specific module
      const modInfo = statsRes.module_cards.find(m => m.module.toLowerCase() === moduleKey.toLowerCase());
      grade = modInfo ? modInfo.grade : '-';
    } else {
      // Fallback to static demo data
      const demoData = allWeeklyData[moduleKey] || allWeeklyData['neural-orbit'];
      data = demoData.map(d => ({ ...d, label: d.week }));
      overallAcc = demoData[demoData.length-1].accuracy;
      usingDemo = true;
      grade = overallAcc >= 90 ? 'A' : 'B';
    }

    if (mistakesRes && mistakesRes.has_data) {
      mistakes = mistakesRes.mistakes;
    } else {
      mistakes = moduleMistakes[moduleKey] || moduleMistakes['neural-orbit'];
    }

    // Show empty onboarding state if no data at all
    if (!data || data.length === 0) {
      content.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;padding:40px;text-align:center;">
        <i class="bi bi-graph-up" style="font-size:48px;color:var(--dim);"></i>
        <h2 style="font-size:18px;font-weight:600;color:var(--text);">Your AI is still learning</h2>
        <p style="font-size:14px;color:var(--muted);max-width:360px;">The Learning Timeline will appear here after your first week of AI decisions. Connect your integrations to get started.</p>
        <a href="#" onclick="window._routerDispatch&&window._routerDispatch('integrations');return false;" style="padding:10px 20px;border-radius:10px;background:var(--accent);color:white;font-size:13px;font-weight:600;text-decoration:none;">Connect Integrations →</a>
      </div>`;
      return;
    }

    const improvement = usingDemo ? Math.round(data[data.length-1].accuracy - data[0].accuracy) : 0;
    const notes = moduleWeeklyNotes[moduleKey] || moduleWeeklyNotes['neural-orbit'];

    content.innerHTML = `
            <div class="page-animate" style="padding: 24px; display: flex; flex-direction: column; gap: 24px;">

                <!-- Header -->
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Learning Timeline ${usingDemo ? '<span style="font-size:12px;opacity:0.6;margin-left:8px;">(Demo Mode)</span>' : '<span style="font-size:10px;color:var(--success);background:rgba(34,197,94,0.1);padding:2px 8px;border-radius:20px;margin-left:8px;letter-spacing:0.05em;"><i class="bi bi-broadcast"></i> LIVE SYNC</span>'}</h1>
                        <p class="page-subtitle">Track AI evolution — intelligence growth and self-reflection</p>
                    </div>
                    <div style="display: flex; gap: 16px;">
                        <!-- Intelligence Grade Card -->
                        <div style="display: flex; align-items: center; gap: 16px; padding: 12px 20px; border-radius: var(--radius-lg); border: 1px solid rgba(91,140,255,0.2); background: rgba(91,140,255,0.06);">
                            <div style="font-size: 32px; font-weight: 800; color: var(--accent); opacity: 0.8;">${grade}</div>
                            <div>
                                <div style="font-size: 11px; font-weight: 600; color: var(--dim); text-transform: uppercase;">Intelligence Grade</div>
                                <div style="font-size: 14px; font-weight: 600; color: var(--text);">${overallAcc}% Accuracy</div>
                            </div>
                        </div>

                        <!-- Improvement Card -->
                        <div style="display: flex; align-items: center; gap: 16px; padding: 12px 20px; border-radius: var(--radius-lg); border: 1px solid rgba(34,197,94,0.2); background: rgba(34,197,94,0.06);">
                            <div style="width: 48px; height: 48px; border-radius: var(--radius-lg); background: rgba(34,197,94,0.15); display: flex; align-items: center; justify-content: center;">
                                <i class="bi bi-graph-up-arrow" style="font-size: 22px; color: var(--success);"></i>
                            </div>
                            <div>
                                <div style="font-size: 11px; font-weight: 600; color: var(--dim); text-transform: uppercase; letter-spacing: 0.05em;">AI Velocity</div>
                                <div style="display: flex; align-items: baseline; gap: 4px; margin-top: 4px;">
                                    <span style="font-size: 24px; font-weight: 700; color: var(--success);">${usingDemo ? '+' + improvement + '%' : velocityLabel}</span>
                                    <span style="font-size: 11px; color: var(--muted);">${usingDemo ? '12wk trend' : 'recent performance'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Chart -->
                <div class="card">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                        <div class="card-title" style="margin: 0;"><i class="bi bi-cpu" style="color: var(--accent);"></i> Learning Progress Over Time</div>
                        <div class="chart-legend">
                            <div class="legend-item"><div class="legend-line" style="background:#5B8CFF;"></div><span>Accuracy %</span></div>
                            <div class="legend-item"><div class="legend-line" style="background:#22C55E;"></div><span>Decisions Made</span></div>
                            <div class="legend-item"><div class="legend-line" style="background:#EF4444;"></div><span>Corrections</span></div>
                        </div>
                    </div>
                    <div class="chart-wrap" style="height: 280px;"><canvas id="learning-chart"></canvas></div>
                    ${usingDemo ? `<div style="margin-top:8px;font-size:11px;color:var(--dim);display:flex;align-items:center;gap:6px;"><i class="bi bi-info-circle"></i> Showing demo data</div>` : ''}
                </div>

                <!-- Notes + Mistakes -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                    <div class="card">
                        <div class="card-title"><i class="bi bi-lightbulb" style="color: var(--warning);"></i> Weekly Learning Notes</div>
                        <div style="display: flex; flex-direction: column; gap: 16px;">
                            ${notes.length ? notes.map(n => buildWeekNote(n)).join('') : '<div style="color:var(--dim);font-size:13px;">Notes will appear after your first week of AI activity.</div>'}
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-title" style="display: flex; align-items: center; gap: 8px;">
                            <i class="bi bi-exclamation-circle" style="color: var(--danger);"></i>
                            Mistake → Correction Log
                            <span style="margin-left: auto; font-size: 10px; font-weight: 600; color: #94A3B8; background: rgba(30,41,59,0.6); padding: 2px 8px; border-radius: 4px;">AI SELF-REFLECTION</span>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 14px;">
                            ${mistakes.length ? mistakes.map(m => buildMistakeCard(m)).join('') : '<div style="color:var(--dim);font-size:13px;">Mistakes will be logged here when the AI is corrected by a human override.</div>'}
                        </div>
                    </div>
                </div>
            </div>
        `;

    requestAnimationFrame(() => initLearningChart(data));
  };

  function buildWeekNote(n) {
    return `
            <div class="week-note-card">
                <div class="week-note-header">
                    <div class="week-note-left">
                        <i class="bi bi-calendar3" style="font-size: 13px; color: var(--dim);"></i>
                        <span class="week-note-name">${n.week}</span>
                        <span class="week-note-date">${n.date}</span>
                    </div>
                    <span style="font-size: 12px; font-weight: 700; color: var(--success);">${n.improvement}</span>
                </div>
                <div class="week-note-items">
                    ${n.notes.map(note => `<div class="week-note-item"><i class="bi bi-lightning" style="color: var(--accent);"></i><span>${escHtml(note)}</span></div>`).join('')}
                </div>
            </div>
        `;
  }

  const modColor = { CRM: '#5B8CFF', Marketing: '#8B5CF6', Shield: '#F59E0B', Website: '#22C55E' };

  function buildMistakeCard(m) {
    const mc = modColor[m.module] || '#94A3B8';
    return `
            <div class="mistake-card">
                <div class="mistake-header">
                    <span class="mistake-id">${m.id}</span>
                    <span class="sev-badge sev-${m.severity}">${m.severity.toUpperCase()}</span>
                    <span class="mod-badge" style="color:${mc}; background:${mc}18;">${m.module}</span>
                    <span style="font-size: 11px; color: var(--dim); margin-left: auto;">${m.date}</span>
                </div>
                <div class="mistake-row"><i class="bi bi-x-circle"></i><span>${escHtml(m.mistake)}</span></div>
                <div style="display:flex;align-items:center;gap:4px;padding:0 4px;"><i class="bi bi-arrow-right" style="font-size:12px;color:var(--dim);"></i></div>
                <div class="correction-row"><i class="bi bi-check-circle"></i><span>${escHtml(m.correction)}</span></div>
                <div class="impact-row"><i class="bi bi-star" style="font-size:12px;"></i> ${escHtml(m.impact)}</div>
            </div>
        `;
  }

  function initLearningChart(data) {
    const canvas = document.getElementById('learning-chart');
    if (!canvas) return;
    if (learningChartInstance) { learningChartInstance.destroy(); learningChartInstance = null; }
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 280);
    grad.addColorStop(0, 'rgba(91,140,255,0.25)');
    grad.addColorStop(1, 'rgba(91,140,255,0.00)');

    learningChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(d => d.label),
        datasets: [
          { label: 'Accuracy', data: data.map(d => d.accuracy), borderColor: '#5B8CFF', backgroundColor: grad, borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5, yAxisID: 'y' },
          { label: 'Decisions Made', data: data.map(d => d.decisions), borderColor: '#22C55E', backgroundColor: 'transparent', borderWidth: 2, fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 5, yAxisID: 'y1' },
          { label: 'Corrections', data: data.map(d => d.corrections), borderColor: '#EF4444', backgroundColor: 'transparent', borderWidth: 2, fill: false, tension: 0.4, pointRadius: 3, pointBackgroundColor: '#EF4444', yAxisID: 'y2' },
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
          y: { position: 'left', min: 60, max: 100, grid: { color: 'rgba(91,140,255,0.06)' }, border: { color: 'rgba(91,140,255,0.1)' }, ticks: { color: '#64748B', font: { size: 11 } } },
          y1: { position: 'right', display: false },
          y2: { position: 'right', display: false },
        },
      },
    });
  }

  function escHtml(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

})();
