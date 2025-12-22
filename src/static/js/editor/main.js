import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI } from "./ui.js";
import { initPlaylist, setPlaylist } from "./playlist.js";

const preloadMixtape = window.PRELOADED_MIXTAPE;

document.addEventListener("DOMContentLoaded", () => {
    // ---------------------------------------------------------------
    // 1️⃣  Populate playlist, cover, title … (needs the DOM)
    // ---------------------------------------------------------------
    if (preloadMixtape) {
        setPlaylist(preloadMixtape.tracks || []);
        const coverImg = document.getElementById("playlist-cover");
        if (preloadMixtape.cover) coverImg.src = preloadMixtape.cover;

        const titleInput = document.getElementById("playlist-title");
        titleInput.value = preloadMixtape.title || "";
    }

    // ---------------------------------------------------------------
    // 2️⃣  Initialise the rest of the UI (search, playlist UI, etc.)
    // ---------------------------------------------------------------
    initSearch();
    initPlaylist();
    initUI();

    // ---------------------------------------------------------------
    // 3️⃣  **Now** initialise EasyMDE – the tabs are already rendered,
    //     so the editor will be visible and will receive the correct
    //     initial value.
    // ---------------------------------------------------------------
    if (preloadMixtape) {
        initEditorNotes(preloadMixtape.liner_notes);
    } else {
        initEditorNotes();               // empty notes for a new mixtape
    }
 });


