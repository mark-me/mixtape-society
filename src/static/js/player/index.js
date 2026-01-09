// static/js/player/index.js
import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initAdaptiveTheming } from './adaptiveTheming.js';
import { initCassettePlayer } from './cassettePlayer.js';
import { initQRShare } from '../common/qrShare.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize adaptive theming first (before other UI elements render)
    initAdaptiveTheming();
    
    // Initialize each independent module
    initPlayerControls();
    initLinerNotes();
    
    // Initialize cassette player (retro mode)
    initCassettePlayer();
    
    // Initialize QR share for player page
    // Share button is the big play button companion
    initQRShare({
        shareButtonSelector: '#big-share-btn',
        modalId: 'qrShareModal',
        getSlug: () => {
            // Extract slug from URL: /share/mixtape-slug
            const match = window.location.pathname.match(/\/share\/([^\/]+)/);
            return match ? match[1] : null;
        },
        autoShow: true  // Always visible on play page
    });
});
