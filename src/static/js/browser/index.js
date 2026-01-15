// static/js/browser/index.js
import { initDeleteMixtape } from './deleteMixtape.js';
import { initQRShare } from '../common/qrShare.js';
import { initSorting } from './sorting.js';
import { initSearch } from './search.js';

document.addEventListener('DOMContentLoaded', () => {
    initDeleteMixtape();
    initSorting();
    initSearch();

    // Initialize QR sharing for browser page
    initQRShare({
        shareButtonSelector: '.qr-share-btn',
        modalId: 'qrShareModal',
        getSlug: (button) => button ? button.dataset.slug : null,
        autoShow: true
    });
});
