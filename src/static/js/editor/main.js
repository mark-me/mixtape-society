import { initSearch } from "./search.js";
import { initPlaylist } from "./playlist.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI } from "./ui.js";
import { playlist } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";

document.addEventListener("DOMContentLoaded", () => {
    // Preload handling (align with HTML Jinja)
    const preloadMixtape = window.PRELOADED_MIXTAPE;
    if (preloadMixtape) {
        playlist = preloadMixtape.tracks || [];
        document.getElementById("playlist-title").value = preloadMixtape.title || "";
        document.getElementById("playlist-cover").src = preloadMixtape.cover ? `/mixtapes/files/${preloadMixtape.cover}` : "{{ url_for('static', filename='image.jpg') }}";
        if (preloadMixtape.liner_notes && easyMDE) {
            easyMDE.value(preloadMixtape.liner_notes);
        }
    }

    initSearch();
    initPlaylist();
    initEditorNotes();
    initUI();
});