// static/js/editor/ui.js
import { showAlert, showConfirm, escapeHtml } from "./utils.js";
import { playlist, registerUnsavedCallback, registerTrackAddedCallback, registerTrackRemovedCallback } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";
import { showProgressModal } from './progressModal.js';

export let hasUnsavedChanges = false;
let isSaving = false;
let coverDataUrl = null;

/*--------------------------------------------------------------
 * Helper: mark the UI as “unsaved” and update the Save button badge
 *--------------------------------------------------------------*/
function markUnsaved() {
    hasUnsavedChanges = true;
    updateSaveButton();
}

/*--------------------------------------------------------------
 * Helper: add / remove the “Unsaved” badge on the Save button
 *--------------------------------------------------------------*/
function updateSaveButton() {
    const saveBtn   = document.getElementById("save-playlist");
    const saveBadge = saveBtn.querySelector(".badge");

    // Regular header save button badge
    if (hasUnsavedChanges) {
        if (!saveBadge) {
            const badge = document.createElement("span");
            badge.className = "badge bg-warning text-dark ms-2";
            badge.textContent = "Unsaved";
            saveBtn.appendChild(badge);
        }
    } else if (saveBadge) {
        saveBtn.removeChild(saveBadge);
    }

    // Floating save button: show/hide with animation
    const floatingSave = document.getElementById("floating-save");
    if (floatingSave) {
        if (hasUnsavedChanges) {
            floatingSave.classList.remove("hidden");
            floatingSave.classList.add("visible");
        } else {
            floatingSave.classList.remove("visible");
            floatingSave.classList.add("hidden");
        }
    }
}

/**
 * Initializes the playlist‑editor UI (cover upload, save button,
 * global audio player, unsaved‑changes handling, etc.).
 */
export function initUI() {
    // -----------------------------------------------------------------
    // 1️⃣  UI elements we’ll interact with
    // -----------------------------------------------------------------
    const coverInput   = document.getElementById("cover-upload");
    const coverImg     = document.getElementById("playlist-cover");
    const saveBtn      = document.getElementById("save-playlist");
    const saveText     = document.getElementById("save-text");
    const editingSlug  = document.getElementById("editing-slug").value;
    const titleInput   = document.getElementById("playlist-title");

    // -----------------------------------------------------------------
    // 2️⃣  Cover upload handling (validation + FileReader error handling)
    // -----------------------------------------------------------------
    coverInput.addEventListener("change", e => {
        const file = e.target.files[0];
        if (!file) return;

        // ---- Validate image type (best-effort, UX only – server must re-validate) ----
        const allowedExtensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"];
        const allowedMimeTypes  = ["image/jpeg", "image/png", "image/gif", "image/webp"];

        const fileName = (file.name || "").toLowerCase();
        const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));

        // note: file.type can be empty or incorrect in some browsers
        const mimeType = (file.type || "").toLowerCase();
        const hasValidMime = mimeType && allowedMimeTypes.includes(mimeType);

        if (!hasValidExtension && !hasValidMime) {
            showAlert("Please upload a valid image file (jpg, png, gif, webp).");
            coverInput.value = "";
            return;
        }

        // ---- Validate size (max 5 MiB) -----------------------------------------
        const maxSize = 5 * 1024 * 1024; // 5 MiB
        if (file.size > maxSize) {
            showAlert("Image is too large. Maximum size is 5 MiB.");
            coverInput.value = "";
            return;
        }

        // ---- Read the file ------------------------------------------------------
        const reader = new FileReader();

        // Successful read --------------------------------------------------------
        reader.onload = ev => {
            coverDataUrl = ev.target.result;
            coverImg.src = coverDataUrl;
            markUnsaved();
        };

        reader.onerror = err => {
            console.error("Cover file could not be read:", err);
            showAlert("Failed to read the image file. Please try a different file.");
            coverInput.value = ""; // reset the input so the user can retry
        };

        reader.readAsDataURL(file);
    });

    // -----------------------------------------------------------------
    // 3️⃣  Title changes also count as “unsaved”
    // -----------------------------------------------------------------
    titleInput.addEventListener("input", markUnsaved);

    // -----------------------------------------------------------------
    // 4️⃣  SAVE button – improved with clientId for idempotent creates
    // -----------------------------------------------------------------
    saveBtn.addEventListener("click", async () => {
        if (playlist.length === 0) {
            showAlert({
                title: "Empty mixtape",
                message: "Your mixtape does not contain any tracks yet."
            });
            return;
        }

        const title = titleInput.value.trim() || "Unnamed Mixtape";

        // -----------------------------------------------------------------
        // Get or generate a clientId for new mixtapes
        // -----------------------------------------------------------------
        let clientId = null;
        const preload = window.PRELOADED_MIXTAPE || {};
        if (editingSlug) {
            // We're editing → use the existing slug, no need for clientId
            clientId = preload.client_id || null;
        } else {
            // We're creating a new one
            clientId = preload.client_id || localStorage.getItem("current_mixtape_client_id");
            if (!clientId) {
                clientId = crypto.randomUUID();  // Generate fresh UUID
                localStorage.setItem("current_mixtape_client_id", clientId);
            }
        }

        const playlistData = {
            title: title,
            cover: coverDataUrl,
            liner_notes: easyMDE ? easyMDE.value() : "",
            tracks: playlist.map(t => ({
                artist: t.artist,
                album: t.album,
                track: t.track,
                duration: t.duration,
                path: t.path,
                filename: t.filename,
                cover: t.cover
            })),
            slug: editingSlug || null,
            client_id: clientId
        };

        isSaving = true;
        saveText.textContent = "Saving…";
        saveBtn.disabled = true;

        try {
            const url = '/editor/save';
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(playlistData)
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Save failed');
            }

            const data = await response.json();
            hasUnsavedChanges = false;
            updateSaveButton();

            // Clear clientId for new mixtapes after successful save
            if (!editingSlug) {
                localStorage.removeItem("current_mixtape_client_id");
            }

            showProgressModal(data.slug);
        } catch (err) {
            console.error("Save error:", err);
            showAlert({
                title: "Save Failed",
                message: err.message || "An error occurred while saving."
            });
        } finally {
            isSaving = false;
            saveText.textContent = "Save";
            saveBtn.disabled = false;
        }
    });

    // -----------------------------------------------------------------
    // 5️⃣  Register callbacks for playlist mutations (unsaved + toasts)
    // -----------------------------------------------------------------
    registerUnsavedCallback(markUnsaved);

    const addToast = new bootstrap.Toast(document.getElementById("addTrackToast"));
    registerTrackAddedCallback(() => addToast.show());

    const removeToast = new bootstrap.Toast(document.getElementById("removeTrackToast"));
    registerTrackRemovedCallback(() => removeToast.show());

    // -----------------------------------------------------------------
    // 6️⃣  Global audio player controls
    // -----------------------------------------------------------------
    const player = document.getElementById('global-audio-player');
    const container = document.getElementById('audio-player-container');
    const closeBtn = document.getElementById('close-player');

    closeBtn.addEventListener('click', () => {
        player.pause();
        player.src = '';
        container.style.display = 'none';
        // Reset all preview buttons in search results
        document.querySelectorAll('.preview-btn').forEach(btn => {
            btn.innerHTML = '<i class="bi bi-play-fill"></i>';
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-primary');
        });
        window.currentPreviewBtn = null;
    });

    player.addEventListener('ended', () => {
        // Reset preview button on end
        if (window.currentPreviewBtn) {
            window.currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
            window.currentPreviewBtn.classList.remove('btn-warning');
            window.currentPreviewBtn.classList.add('btn-primary');
            window.currentPreviewBtn = null;
        }
    });

    // -----------------------------------------------------------------
    // 7️⃣  Unsaved-changes handling
    // -----------------------------------------------------------------
    // 7a. Liner notes changes count as “unsaved”
    if (easyMDE) {
        easyMDE.codemirror.on("change", markUnsaved);
    }

    // -----------------------------------------------------------------
    // 8️⃣  Link-click interception (for internal navigation)
    // -----------------------------------------------------------------
    document.addEventListener("click", e => {
        if (!hasUnsavedChanges || isSaving) return;

        const link = e.target.closest("a");
        if (!link || !link.href) return;

        // Ignore same-page anchors or links that already point to the current base path (ignoring query/hash)
        try {
            const linkUrl = new URL(link.href, window.location.origin);
            const currentUrl = new URL(window.location.href);
            if (linkUrl.origin === currentUrl.origin && linkUrl.pathname === currentUrl.pathname) return;
        } catch (err) {
            // If URL parsing fails, fall back to default behavior (do not suppress navigation)
        }

        e.preventDefault(); // stop immediate navigation
        showConfirm({
            title: "Unsaved changes",
            message: "You have unsaved changes. Leave without saving?",
            confirmText: "Leave",
            cancelText: "Stay"
        }).then(confirmed => {
            if (confirmed) {
                hasUnsavedChanges = false; // suppress the beforeunload dialog
                window.location.href = link.href;
            }
        });
    });

    // -----------------------------------------------------------------
    // 9️⃣  Reorder mode toggle
    // -----------------------------------------------------------------
    const reorderBtn = document.getElementById('toggle-reorder-mode');
    if (reorderBtn) {
        reorderBtn.addEventListener('click', () => {
            document.body.classList.toggle('reorder-mode');

            // Toggle between expand and collapse icons
            const icon = reorderBtn.querySelector('i');
            if (document.body.classList.contains('reorder-mode')) {
                icon.classList.replace('bi-arrows-angle-expand', 'bi-arrows-angle-contract');
                reorderBtn.title = 'Exit expanded reordering';
            } else {
                icon.classList.replace('bi-arrows-angle-contract', 'bi-arrows-angle-expand');
                reorderBtn.title = 'Expand for reordering';
            }

            // Optional: re-render to adapt heights
            if (window.renderPlaylist) {
                window.renderPlaylist();
            }
        });
    }

    // 9b. Browser‑level navigation (back/forward, tab close, refresh)
    window.addEventListener("beforeunload", e => {
        if (hasUnsavedChanges && !isSaving) {
            // Modern browsers ignore the custom text, but returning a string triggers the native confirmation dialog.
            const confirmationMessage = "You have unsaved changes. Are you sure you want to leave?";
            e.returnValue = confirmationMessage; // Gecko, Chrome 34+
            return confirmationMessage;          // WebKit, Safari
        }
    });

    // Cover generation/uploading
    const coverUploadBtn = document.getElementById('cover-upload-btn');
    if (coverUploadBtn) {
        coverUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();  // Prevent default if it's a button
            const coverModal = new bootstrap.Modal(document.getElementById('coverOptionsModal'));
            coverModal.show();
        });
    }

    // Wire up modal options
    const uploadOption = document.getElementById('upload-cover-option');
    const generateOption = document.getElementById('generate-composite-option');

    if (uploadOption) {
        uploadOption.addEventListener('click', () => {
            document.getElementById('cover-upload').click();  // Trigger existing upload
            bootstrap.Modal.getInstance(document.getElementById('coverOptionsModal')).hide();
        });
    }

    if (generateOption) {
        generateOption.addEventListener('click', () => {
            generateCompositeCover();
            bootstrap.Modal.getInstance(document.getElementById('coverOptionsModal')).hide();
        });
    }

    // Generate composite cover
    function generateCompositeCover() {
        // Collect ALL cover paths (including duplicates for weighting)
        const allCovers = playlist
            .map(item => item.cover)
            .filter(Boolean);  // remove null/undefined

        if (allCovers.length === 0) {
            showAlert({ title: "No Covers Available", message: "Add tracks with covers to generate a composite." });
            return;
        }

        // POST to server — send full list with duplicates
        fetch('/editor/generate_composite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ covers: allCovers })  // ← changed: allCovers, not unique
        })
        .then(response => {
            if (!response.ok) throw new Error('Generation failed');
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showAlert({ title: "Error", message: data.error });
                return;
            }
            coverDataUrl = data.data_url;
            document.getElementById('playlist-cover').src = coverDataUrl;
            markUnsaved();
        })
        .catch(err => {
            console.error("Composite generation error:", err);
            showAlert({ title: "Error", message: "Failed to generate composite. Try again." });
        });
    }

    // Floating buttons setup (mobile only)
    const floatingSave = document.getElementById("floating-save");
    const floatingTracks = document.getElementById("floating-tracks");

    if (floatingSave) {
        // Trigger original save on click
        floatingSave.addEventListener("click", () => {
            saveBtn.click();
        });
    }

    if (floatingTracks) {
        floatingTracks.addEventListener("click", () => {
            // Activate Tracks tab
            const tracksTab = document.getElementById("tracks-tab");
            if (tracksTab) {
                const bsTab = new bootstrap.Tab(tracksTab);
                bsTab.show();
            }

            // Scroll to mixtape card (smoothly, to handle long search results)
            const mixtapeCard = document.querySelector(".col-lg-5 .card"); // Selector for mixtape card
            if (mixtapeCard) {
                mixtapeCard.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    }

    // Initial sync of badges (in case there are unsaved changes on load)
    updateSaveButton();
}


/**
 * Activate the correct *sub‑tab* inside the “Liner Notes” section.
 *
 * @param {boolean} showPreview – If true, the Preview tab becomes active.
 *                                 If false, the Write tab becomes active.
 *
 * This function is called from `main.js` **after** the UI (including the
 * tab markup) has been rendered, guaranteeing that the tab elements exist.
 */
export function activateInitialNotesTab(showPreview) {
    // The tab buttons have the IDs `write-tab` and `preview-tab`.
    const targetId = showPreview ? "preview-tab" : "write-tab";
    const targetEl = document.getElementById(targetId);
    if (!targetEl) return;               // safety‑check

    // Use the global `bootstrap.Tab` class (provided by the CDN script).
    const bsTab = new bootstrap.Tab(targetEl);
    bsTab.show();
}