// static/js/player/index.js
import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initShareToast } from './shareToast.js';
import { initAdaptiveTheming } from './adaptiveTheming.js';
import { initCassettePlayer } from './cassettePlayer.js';
import { initQRShare } from './qrShare.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize adaptive theming first (before other UI elements render)
    initAdaptiveTheming();
    
    // Initialise each independent module
    initPlayerControls();   // returns {playTrack, syncPlayIcons}
    initLinerNotes();
    initShareToast();
    initQRShare();          // Initialize QR code sharing
    
    // Initialize cassette player (retro mode)
    initCassettePlayer();
});
