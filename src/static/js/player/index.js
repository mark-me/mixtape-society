// static/js/player/index.js
import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initShareToast } from './shareToast.js';
import { initAdaptiveTheming } from './adaptiveTheming.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize adaptive theming first (before other UI elements render)
    initAdaptiveTheming();
    
    // Initialise each independent module
    initPlayerControls();   // returns {playTrack, syncPlayIcons}
    initLinerNotes();
    initShareToast();

});
