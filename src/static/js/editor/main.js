import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI } from "./ui.js";
import { initPlaylist, playlist, setPlaylist } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";

const preloadMixtape = window.PRELOADED_MIXTAPE;

if (preloadMixtape) {
    setPlaylist(preloadMixtape.tracks || []);
    // Populate other UI elements that depend on the preload data
    const coverImg = document.getElementById("playlist-cover");
    if (preloadMixtape.cover) coverImg.src = preloadMixtape.cover;

    const titleInput = document.getElementById("playlist-title");
    titleInput.value = preloadMixtape.title || "";

    // Liner notes – wait until EasyMDE is ready
    if (window.PRELOADED_MIXTAPE.liner_notes && window.easyMDE) {
        window.easyMDE.value(preloadMixtape.liner_notes);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initSearch();
    initPlaylist();
    initEditorNotes();
    initUI();
});