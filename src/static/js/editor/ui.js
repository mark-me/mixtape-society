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
                filename: t.filename
            })),
            client_id: clientId  // ← This is the key addition
        };

        // If editing, include the slug
        if (editingSlug) {
            const confirmOverwrite = await showConfirm({
                title: "Overwrite mixtape",
                message: `Are you sure you want to overwrite <strong>${escapeHtml(title)}</strong>?`,
                confirmText: "Overwrite"
            });
            if (!confirmOverwrite) return;

            playlistData.slug = editingSlug;
        }

        // -----------------------------------------------------------------
        // UI state during save
        // -----------------------------------------------------------------
        isSaving = true;
        saveBtn.disabled = true;
        saveText.textContent = "Saving...";

        const FETCH_TIMEOUT = 30000;  // 30 seconds
        const MAX_RETRIES = 2;

        let attempt = 0;
        let success = false;
        let lastError = null;

        while (attempt <= MAX_RETRIES && !success) {
            attempt++;
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

                const response = await fetch("/editor/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(playlistData),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(`Server error ${response.status}: ${text}`);
                }

                const data = await response.json();

                if (data.success) {
                    success = true;
                    hasUnsavedChanges = false;
                    updateSaveButton();

                    // Show progress modal for caching
                    showProgressModal(data.slug);

                    // If this was a new mixtape, update URL and hidden field
                    if (!editingSlug) {
                        window.history.replaceState({}, "", `/editor/${data.slug}`);
                        document.getElementById("editing-slug").value = data.slug;

                        // Persist clientId for future retries (optional, but safe)
                        if (data.client_id) {
                            localStorage.setItem("current_mixtape_client_id", data.client_id);
                        } else {
                            localStorage.setItem("current_mixtape_client_id", clientId);
                        }

                        saveText.textContent = "Save changes";
                    }
                } else {
                    throw new Error(data.error || "Unknown save error");
                }
            } catch (e) {
                lastError = e;
                console.error(`Save attempt ${attempt} failed:`, e);

                if (attempt <= MAX_RETRIES) {
                    // Wait before retry (2s, 4s)
                    await new Promise(r => setTimeout(r, 2000 * attempt));
                }
            }
        }

        // -----------------------------------------------------------------
        // Final cleanup
        // -----------------------------------------------------------------
        isSaving = false;
        saveBtn.disabled = false;
        saveText.textContent = editingSlug ? "Save changes" : "Save";

        if (!success) {
            showAlert({
                title: "Save failed",
                message: `Could not save after ${MAX_RETRIES + 1} attempts.<br><br>
                        Error: ${escapeHtml(lastError?.message || "Network error")}<br><br>
                        Your changes are still here — you can try again.`,
                buttonText: "OK"
            });
        }
    });

    // -----------------------------------------------------------------
    // 5️⃣  Global audio player (bottom‑fixed)
    // -----------------------------------------------------------------
    const audioPlayer    = document.getElementById("global-audio-player");
    const playerContainer = document.getElementById("audio-player-container");
    const closeBtn       = document.getElementById("close-player");
    const nowPlayingTitle = document.getElementById("now-playing-title");
    const nowPlayingArtist = document.getElementById("now-playing-artist");

    // When any track (including preview tracks) starts playing, show the player.
    audioPlayer?.addEventListener("play", () => {
        playerContainer.style.display = "block";
    });

    // Close button hides the player and pauses playback.
    closeBtn?.addEventListener("click", () => {
        audioPlayer?.pause();
        playerContainer.style.display = "none";
    });

    // Helper function to update track info in the player
    // This can be called from search.js or other modules when previewing tracks
    window.updatePlayerTrackInfo = function(title, artist) {
        if (nowPlayingTitle) nowPlayingTitle.textContent = title || "—";
        if (nowPlayingArtist) nowPlayingArtist.textContent = artist || "—";
    };

    // -----------------------------------------------------------------
    // 6️⃣  “Track added” toast (re‑used for any playlist mutation)
    // -----------------------------------------------------------------
    const addTrackToastEl = document.getElementById('addTrackToast');
    const removeTrackToastEl = document.getElementById('removeTrackToast');

    const addTrackToast = addTrackToastEl ? new bootstrap.Toast(addTrackToastEl, { delay: 2000 }) : null;
    const removeTrackToast = removeTrackToastEl ? new bootstrap.Toast(removeTrackToastEl, { delay: 2000 }) : null;

    addTrackToastEl.className = "toast position-fixed bottom-0 end-0 m-3";
    addTrackToastEl.setAttribute("role", "alert");
    addTrackToastEl.setAttribute("aria-live", "assertive");
    addTrackToastEl.setAttribute("aria-atomic", "true");
    addTrackToastEl.innerHTML = `
        <div class="toast-header bg-success text-white">
            <strong class="me-auto">Track added!</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>`;
    document.body.appendChild(addTrackToastEl);

    // -----------------------------------------------------------------
    // 7️⃣  Register the **unsaved‑changes callback** with the playlist module.
    //      The playlist module will call this function after ANY mutation
    //      (add, clear, remove, drag‑reorder).
    // -----------------------------------------------------------------
    registerUnsavedCallback(() => {
        // Show the “Unsaved” badge
        markUnsaved();
    });

    registerTrackAddedCallback(() => {
        if (addTrackToast) addTrackToast.show();
    });

    registerTrackRemovedCallback(() => {
        if (removeTrackToast) removeTrackToast.show();
    });
    // -----------------------------------------------------------------
    // 8️⃣  EasyMDE (liner‑notes) – mark unsaved on any edit
    // -----------------------------------------------------------------
    if (easyMDE) {
        easyMDE.codemirror.on("change", markUnsaved);
    }

    // -----------------------------------------------------------------
    // 9️⃣  Warn the user if they try to navigate away with unsaved changes
    // -----------------------------------------------------------------
    // 9a. Click‑based navigation (links)
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
    // Reorder mode toggle
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
