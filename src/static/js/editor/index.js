// static/js/editor/index.js
/**
 * UPDATED: Now includes collection manager initialization
 */

import { initSearch } from "./search.js";
import { initEditorNotes } from "./editorNotes.js";
import { initUI, activateInitialNotesTab } from "./ui.js";
import { initPlaylist, setPlaylist } from "./playlist.js";
import { initQRShare } from '../common/qrShare.js';
import { initCollectionManager } from './collectionManager.js';  // NEW

const preloadMixtape = window.PRELOADED_MIXTAPE;

document.addEventListener("DOMContentLoaded", () => {
    // ---------------------------------------------------------------
    // 🆕 0️⃣ Initialize Collection Manager FIRST
    // ---------------------------------------------------------------
    // Get collection configuration from body data attributes or preloaded mixtape
    const hasMultiple = document.body.dataset.hasMultipleCollections === 'true';
    const isEditing = document.body.dataset.editingMode === 'true';
    const defaultCollectionId = document.body.dataset.defaultCollection;
    const mixtapeCollectionId = preloadMixtape?.collection_id;
    
    // Determine which collection to use
    const collectionId = mixtapeCollectionId || defaultCollectionId;
    
    // Get collection name from the selector if available
    let collectionName = null;
    if (hasMultiple) {
        const collectionSelect = document.getElementById('collectionSelect');
        if (collectionSelect && collectionId) {
            const option = collectionSelect.querySelector(`option[value="${collectionId}"]`);
            if (option) {
                collectionName = option.dataset.name;
            }
        }
    }
    
    // Initialize collection manager
    initCollectionManager({
        defaultCollectionId: collectionId,
        defaultCollectionName: collectionName,
        hasMultiple: hasMultiple,
        isEditing: isEditing,
        shouldLock: isEditing || (preloadMixtape?.tracks?.length > 0)
    });
    
    console.log('Collection manager initialized:', {
        collectionId,
        collectionName,
        hasMultiple,
        isEditing
    });
    
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
    // 5️⃣  Activate the appropriate sub-tab (Write vs Preview)
    // ---------------------------------------------------------------
    // If there are liner notes, we want the *Preview* tab to be visible
    // right away. Otherwise we fall back to the *Write* tab.
    const hasNotes = Boolean(
        preloadMixtape && preloadMixtape.liner_notes && preloadMixtape.liner_notes.trim()
    );
    activateInitialNotesTab(hasNotes);
});
