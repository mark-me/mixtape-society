// static/js/browser/index.js
import { initDeleteMixtape } from './deleteMixtape.js';
import { initQRShare } from '../common/qrShare.js';

document.addEventListener('DOMContentLoaded', () => {
    initCopyToast();
    initDeleteMixtape();

    // Initialize QR sharing for browser page
    initQRShare({
        shareButtonSelector: '.qr-share-btn',
        modalId: 'qrShareModal',
        getSlug: (button) => button ? button.dataset.slug : null,
        autoShow: true
    });
});
