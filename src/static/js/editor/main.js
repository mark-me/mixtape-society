import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI } from "./ui.js";
import { initPlaylist, setPlaylist } from "./playlist.js";

const preloadMixtape = window.PRELOADED_MIXTAPE;

if (preloadMixtape) {
    setPlaylist(preloadMixtape.tracks || []);
    // Populate other UI elements that depend on the preload data
    const coverImg = document.getElementById("playlist-cover");
    if (preloadMixtape.cover) coverImg.src = preloadMixtape.cover;

    const titleInput = document.getElementById("playlist-title");
    titleInput.value = preloadMixtape.title || "";

    // Pass the pre‑loaded liner notes (if any) so the editor shows them.
    initEditorNotes(preloadMixtape ? preloadMixtape.liner_notes : null);
} else {
    // No mixtape to preload – just initialise the editor normally.
    initEditorNotes();
}

document.addEventListener("DOMContentLoaded", () => {
    initSearch();
    initPlaylist();
    initEditorNotes();   // (will be a no‑op if already called above)
    initUI();
});