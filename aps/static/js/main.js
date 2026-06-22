/**
 * Product Pilot Go — Main JavaScript
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

// ── Image Preview Hover System ──────────────────────────────────
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    // Inject the DOM elements for previews
    const desktopPreview = document.createElement('div');
    desktopPreview.id = 'globalImagePreview';
    desktopPreview.innerHTML = '<img src="" alt="Preview">';
    document.body.appendChild(desktopPreview);

    const mobileModalHtml = `
      <div class="modal fade" id="mobileImagePreviewModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            <div class="modal-body text-center">
              <img src="" id="mobileImagePreviewImg" alt="Preview">
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', mobileModalHtml);

    const desktopImg = desktopPreview.querySelector('img');
    const mobileImg = document.getElementById('mobileImagePreviewImg');
    let previewModal = null;
    
    // Selectors that indicate a small image thumbnail
    const thumbnailSelectors = [
      '.product-thumb', 
      '.product-card-img img', 
      '.selected-bar-thumb img', 
      '.inv-th img', 
      'td img', 
      '.order-card-field img',
      '.location-product-thumb img'
    ].join(', ');

    document.addEventListener('mouseover', function(e) {
      if (window.innerWidth <= 768) return; // Desktop only
      
      const target = e.target.closest(thumbnailSelectors);
      if (target && target.tagName === 'IMG') {
        const src = target.getAttribute('data-full') || target.src;
        if (!src || src.includes('no-image') || src.includes('placeholder')) return;
        
        desktopImg.src = src;
        desktopPreview.classList.add('show');
        
        // Position it logic
        const rect = target.getBoundingClientRect();
        let top = rect.top + (rect.height / 2) - 150; // Center vertically
        let left = rect.right + 15; // Right of the thumb
        
        // Boundaries
        if (top < 10) top = 10;
        if (top + 300 > window.innerHeight) top = window.innerHeight - 310;
        if (left + 300 > window.innerWidth) left = rect.left - 315; // Put on left side if no space
        
        desktopPreview.style.top = top + 'px';
        desktopPreview.style.left = left + 'px';
      }
    });

    document.addEventListener('mouseout', function(e) {
      if (window.innerWidth <= 768) return;
      const target = e.target.closest(thumbnailSelectors);
      if (target && target.tagName === 'IMG') {
        desktopPreview.classList.remove('show');
      }
    });

    // Mobile tap handling
    document.addEventListener('click', function(e) {
      if (window.innerWidth > 768) return;
      
      const target = e.target.closest(thumbnailSelectors);
      if (target && target.tagName === 'IMG') {
        // Only override default click if it's not wrapped in a link that we want to follow
        // Actually, preventing default might break navigation if they click a product card.
        // If it's a product card, usually the whole card is a link, so we shouldn't intercept tap unless it's just the thumb?
        // To be safe, we'll only trigger if the thumb is in a table or a specific wrap, but let's try allowing it for all if we prevent default.
        // Wait, if we prevent default, they can't open product details on mobile by tapping the image.
        // Let's only intercept if the parent isn't an 'A' tag, OR if it's explicitly a thumb class not in an A tag.
        
        if (target.closest('a')) return; // Let links behave normally
        
        const src = target.getAttribute('data-full') || target.src;
        if (!src) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        mobileImg.src = src;
        if (!previewModal) {
          previewModal = new bootstrap.Modal(document.getElementById('mobileImagePreviewModal'));
        }
        previewModal.show();
      }
    });
  });
})();
