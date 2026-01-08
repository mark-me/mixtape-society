// static/js/editor/index.js
import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI, activateInitialNotesTab } from "./ui.js";
import { initPlaylist, setPlaylist } from "./playlist.js";
import { initEditorQRShare } from './editorQrShare.js';

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

        // Auto-grow the textarea after setting value
        if (titleInput.tagName === 'TEXTAREA') {
            titleInput.style.height = 'auto';
            titleInput.style.height = titleInput.scrollHeight + 'px';
        }
    }

    if (!preloadMixtape || !preloadMixtape.slug) {
        // This is a brand-new mixtape (no slug → not loaded from disk)
        // Remove any stale client_id from a previous abandoned session
        localStorage.removeItem("current_mixtape_client_id");
    }

    // ---------------------------------------------------------------
    // 2️⃣  Initialise EasyMDE (the editor) – the tabs are already rendered,
    //     so the editor will be visible and will receive the correct
    //     initial value.
    // ---------------------------------------------------------------
    if (preloadMixtape) {
        initEditorNotes(preloadMixtape.liner_notes);
    } else {
        initEditorNotes();               // empty notes for a new mixtape
    }

    // ---------------------------------------------------------------
    // 3️⃣  Initialise the rest of the UI (search, playlist UI, etc.)
    // ---------------------------------------------------------------
   initSearch();
   initPlaylist();
   initUI();
   initEditorQRShare();

    // ---------------------------------------------------------------
    // 4️⃣  Activate the appropriate sub‑tab (Write vs Preview)
    // ---------------------------------------------------------------
    // If there are liner notes, we want the *Preview* tab to be visible
    // right away. Otherwise we fall back to the *Write* tab.
    const hasNotes = Boolean(
        preloadMixtape && preloadMixtape.liner_notes && preloadMixtape.liner_notes.trim()
    );
    activateInitialNotesTab(hasNotes);
});


