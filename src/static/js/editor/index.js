// static/js/editor/index.js
import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI, activateInitialNotesTab } from "./ui.js";
import { initPlaylist, setPlaylist } from "./playlist.js";
import { initQRShare } from '../common/qrShare.js';
import { initGiftSettings } from './giftSettings.js';

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
    // 2️⃣  Initialise EasyMDE (the editor) — the tabs are already rendered,
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

    // ---------------------------------------------------------------
    // 3.5️⃣  Initialize gift settings
    // ---------------------------------------------------------------
    initGiftSettings();

    // ---------------------------------------------------------------
    // 4️⃣  Initialize QR share functionality
    // ---------------------------------------------------------------
    // Check if this is an existing mixtape (has slug)
    const isExistingMixtape = Boolean(
        (preloadMixtape && preloadMixtape.slug) ||
        document.getElementById('editing-slug')?.value
    );
    
    initQRShare({
        shareButtonSelector: '#share-playlist',
        modalId: 'qrShareModal',
        getSlug: () => {
            // Try editing-slug input first (set after save)
            const editingInput = document.getElementById('editing-slug');
            if (editingInput && editingInput.value) {
                return editingInput.value;
            }

            // Try preloaded data (when editing existing mixtape)
            if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.slug) {
                return window.PRELOADED_MIXTAPE.slug;
            }

            return null;
        },
        autoShow: isExistingMixtape  // Show immediately for existing, hide for new
    });

    // ---------------------------------------------------------------
    // 5️⃣  Activate the appropriate sub‑tab (Write vs Preview)
    // ---------------------------------------------------------------
    // If there are liner notes, we want the *Preview* tab to be visible
    // right away. Otherwise we fall back to the *Write* tab.
    const hasNotes = Boolean(
        preloadMixtape && preloadMixtape.liner_notes && preloadMixtape.liner_notes.trim()
    );
    activateInitialNotesTab(hasNotes);
});
