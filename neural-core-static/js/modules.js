/* ============================================================
   modules.js — NeuralOrbit Compat Shim + Initial Route Trigger
   Wires the router-ready event to the initial page load.
   ============================================================ */

(function () {
  'use strict';

  // Wait for router to be ready, then trigger initial tab based on URL hash
  window.addEventListener('router-ready', function () {
    const hash = window.location.hash.replace('#', '') || 'overview';
    window._routerDispatch?.(hash);
  });

})();
