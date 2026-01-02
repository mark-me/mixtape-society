// static/js/player/index.js
import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initShareToast } from './shareToast.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialise each independent module
    initPlayerControls();   // returns {playTrack, syncPlayIcons}
    initLinerNotes();
    initShareToast();

});