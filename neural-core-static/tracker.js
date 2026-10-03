/**
 * NeuralOrbit Website Tracker v1.0
 * Paste in <head> to track visitor behaviour and send to NeuralOrbit.
 * No PII collected · Zero CLS · Async load · GDPR-friendly
 *
 * Usage:
 *   <script src="https://cdn.neuralorbit.ai/tracker.js"
 *           data-token="USR-TOKEN-HERE"></script>
 */
(function (w, d) {
    'use strict';

    /* ── Config ──────────────────────────────────────────────── */
    var token = '';
    var endpoint = 'http://localhost:8000/api/v1/track';   // swap to prod URL
    var queue = [];
    var sessionId = 'sess_' + Math.random().toString(36).slice(2, 11);
    var sessionStart = Date.now();
    var flushing = false;

    /* ── Find our script tag ─────────────────────────────────── */
    var scripts = d.querySelectorAll('script[data-token]');
    for (var i = 0; i < scripts.length; i++) {
        if (scripts[i].dataset.token) {
            token = scripts[i].dataset.token;
            endpoint = scripts[i].dataset.endpoint || endpoint;
            break;
        }
    }
    /* Abort silently if no token found */
    if (!token) return;

    /* ── Helpers ─────────────────────────────────────────────── */
    function now() { return Date.now() - sessionStart; }

    function push(type, data) {
        queue.push({
            type: type,
            path: w.location.pathname,
            referrer: d.referrer || '',
            title: d.title || '',
            data: data || {},
            ms: now()
        });
        if (queue.length >= 8) flush();
    }

    function flush() {
        if (flushing || !queue.length) return;
        var batch = queue.splice(0);
        flushing = true;

        var payload = JSON.stringify({
            token: token,
            session_id: sessionId,
            url: w.location.href,
            events: batch,
            ts: new Date().toISOString()
        });

        /* sendBeacon for page-unload reliability */
        if (navigator.sendBeacon) {
            navigator.sendBeacon(endpoint, new Blob([payload], { type: 'application/json' }));
            flushing = false;
        } else {
            var x = new XMLHttpRequest();
            x.open('POST', endpoint, true);
            x.setRequestHeader('Content-Type', 'application/json');
            x.onload = x.onerror = function () { flushing = false; };
            x.send(payload);
        }
    }

    /* ── Auto-tracking ───────────────────────────────────────── */

    /* 1. Page view */
    push('page_view', { referrer: d.referrer });

    /* 2. CTA / link clicks */
    d.addEventListener('click', function (e) {
        var el = e.target.closest('button, a, [data-track]');
        if (!el) return;
        push('cta_click', {
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || el.value || '').trim().slice(0, 60),
            id: el.id || '',
            href: el.href || '',
            track: el.dataset.track || ''
        });
    }, true);

    /* 3. Form submissions */
    d.addEventListener('submit', function (e) {
        push('form_submit', {
            form_id: e.target.id || '',
            form_name: e.target.name || e.target.dataset.form || ''
        });
    }, true);

    /* 4. Scroll depth milestones (25 / 50 / 75 / 100 %) */
    var milestones = [25, 50, 75, 100];
    var reached = {};
    w.addEventListener('scroll', function () {
        var pct = Math.round(
            (w.scrollY / (d.body.scrollHeight - w.innerHeight)) * 100
        );
        milestones.forEach(function (m) {
            if (!reached[m] && pct >= m) {
                reached[m] = true;
                push('scroll_depth', { pct: m });
            }
        });
    }, { passive: true });

    /* 5. Session end (page unload) */
    w.addEventListener('beforeunload', function () {
        var duration = Math.round((Date.now() - sessionStart) / 1000);
        push('session_end', { duration_s: duration, events_count: queue.length });
        flush();
    });

    /* 6. Periodic flush every 30 s */
    setInterval(flush, 30000);

    /* ── Public API ──────────────────────────────────────────── */
    w.NeuralTrack = push;  // manual: NeuralTrack('checkout_complete', {value:299})

})(window, document);
