/**
 * WMS — Main JavaScript
 * Handles global UI interactions
 */

(function () {
  "use strict";

  // ── Auto-dismiss alerts after 5 seconds ───────────────────
  document.addEventListener("DOMContentLoaded", function () {
    const alerts = document.querySelectorAll(".alert-dismissible");
    alerts.forEach(function (alert) {
      setTimeout(function () {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) {
          bsAlert.close();
        }
      }, 5000);
    });
  });

  // ── Close offcanvas on nav link click (mobile) ────────────
  document.addEventListener("click", function (e) {
    const link = e.target.closest(".offcanvas .nav-link");
    if (link) {
      const offcanvasEl = link.closest(".offcanvas");
      if (offcanvasEl) {
        const offcanvas = bootstrap.Offcanvas.getInstance(offcanvasEl);
        if (offcanvas) {
          offcanvas.hide();
        }
      }
    }
  });
})();
