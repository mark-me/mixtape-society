// static/js/browser/index.js
import { initDeleteMixtape } from './deleteMixtape.js';
import { initQRShare } from '../common/qrShare.js';
import { initSorting } from './sorting.js';

document.addEventListener('DOMContentLoaded', () => {
    initDeleteMixtape();
    initSorting();

    // Initialize QR sharing for browser page
    initQRShare({
        shareButtonSelector: '.qr-share-btn',
        modalId: 'qrShareModal',
        getSlug: (button) => button ? button.dataset.slug : null,
        autoShow: true
    });
});
