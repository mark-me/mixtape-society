// static/js/player/index.js
import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initShareToast } from './shareToast.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialise each independent module
    const playerAPI = initPlayerControls();   // returns {playTrack, syncPlayIcons}
    initLinerNotes();
    initShareToast();

    // Keep play‑icon state in sync whenever the audio element changes state
    const player = document.getElementById('main-player');
    if (player) {
        player.addEventListener('play', playerAPI.syncPlayIcons);
        player.addEventListener('pause', playerAPI.syncPlayIcons);
    }
});