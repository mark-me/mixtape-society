// static/js/browser/index.js
import { initDeleteMixtape } from './deleteMixtape.js';
import { initQRShare } from '../common/qrShare.js';
import { initSorting } from './sorting.js';
import { initSearch } from './search.js';

document.addEventListener('DOMContentLoaded', () => {
    initDeleteMixtape();
    initSorting();
    initSearch();
    
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Initialize QR sharing for browser page
    initQRShare({
        shareButtonSelector: '.qr-share-btn',
        modalId: 'qrShareModal',
        getSlug: (button) => button ? button.dataset.slug : null,
        autoShow: true
    });
});
