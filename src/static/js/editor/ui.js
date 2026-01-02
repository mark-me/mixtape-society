// static/js/editor/ui.js
import { showAlert, showConfirm } from "./utils.js";
import { playlist, registerUnsavedCallback, registerTrackAddedCallback, registerTrackRemovedCallback } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";
import { showProgressModal } from './progressModal.js';

export let hasUnsavedChanges = false;
let isSaving = false;
let coverDataUrl = null;

/**
 * Helper: mark the UI as "unsaved" and update the Save button badge
 */
function markUnsaved() {
    hasUnsavedChanges = true;
    updateSaveButton();
}

/**
 * Helper: add / remove the "Unsaved" badge on the Save button
 */
function updateSaveButton() {
    const saveBtn = document.getElementById("save-playlist");
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
 * Initializes the playlist editor UI (cover upload, save button,
 * global audio player, unsaved changes handling, etc.).
 */
export function initUI() {
    const coverInput = document.getElementById("cover-upload");
    const coverImg = document.getElementById("playlist-cover");
    const saveBtn = document.getElementById("save-playlist");
    const saveText = document.getElementById("save-text");
    const editingSlug = document.getElementById("editing-slug").value;
    const titleInput = document.getElementById("playlist-title");

    // Cover upload handling with validation
    coverInput.addEventListener("change", e => {
        const file = e.target.files[0];
        if (!file) return;

        // Validate image type
        const allowedExtensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"];
        const allowedMimeTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"];

        const fileName = (file.name || "").toLowerCase();
        const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));

        const mimeType = (file.type || "").toLowerCase();
        const hasValidMime = mimeType && allowedMimeTypes.includes(mimeType);

        if (!hasValidExtension && !hasValidMime) {
            showAlert({
                title: "Invalid File",
                message: "Please upload a valid image file (jpg, png, gif, webp)."
            });
            coverInput.value = "";
            return;
        }

        // Validate size (max 5 MiB)
        const maxSize = 5 * 1024 * 1024;
        if (file.size > maxSize) {
            showAlert({
                title: "File Too Large",
                message: "Image is too large. Maximum size is 5 MiB."
            });
            coverInput.value = "";
            return;
        }

        // Read the file
        const reader = new FileReader();

        reader.onload = ev => {
            coverDataUrl = ev.target.result;
            coverImg.src = coverDataUrl;
            markUnsaved();
        };

        reader.onerror = err => {
            console.error("Cover file could not be read:", err);
            showAlert({
                title: "Read Error",
                message: "Failed to read the image file. Please try a different file."
            });
            coverInput.value = "";
        };

        reader.readAsDataURL(file);
    });

    // Title changes count as "unsaved"
    titleInput.addEventListener("input", markUnsaved);

    // Save button handler with client ID for idempotent creates
    saveBtn.addEventListener("click", async () => {
        if (playlist.length === 0) {
            showAlert({
                title: "Empty Mixtape",
                message: "Your mixtape does not contain any tracks yet."
            });
            return;
        }

        const title = titleInput.value.trim() || "Unnamed Mixtape";

        // Get or generate a clientId for new mixtapes
        let clientId = null;
        const preload = window.PRELOADED_MIXTAPE || {};
        if (editingSlug) {
            clientId = preload.client_id || null;
        } else {
            clientId = preload.client_id || localStorage.getItem("current_mixtape_client_id");
            if (!clientId) {
                clientId = crypto.randomUUID();
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
            const response = await fetch('/editor/save', {
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

    // Register playlist callbacks to mark unsaved changes
    registerUnsavedCallback(markUnsaved);
    registerTrackAddedCallback(() => {
        const toast = bootstrap.Toast.getOrCreateInstance(document.getElementById('addTrackToast'));
        toast.show();
    });
    registerTrackRemovedCallback(() => {
        const toast = bootstrap.Toast.getOrCreateInstance(document.getElementById('removeTrackToast'));
        toast.show();
    });

    // Global audio player close button
    document.getElementById("close-player").addEventListener("click", () => {
        const player = document.getElementById("global-audio-player");
        const container = document.getElementById("audio-player-container");

        player.pause();
        player.src = "";
        container.style.display = "none";

        // Reset any active preview button
        if (window.currentPreviewBtn) {
            window.currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
            window.currentPreviewBtn.classList.remove('btn-warning');
            window.currentPreviewBtn.classList.add('btn-track');
            window.currentPreviewBtn = null;
        }
    });

    // Liner notes changes count as "unsaved"
    if (easyMDE) {
        easyMDE.codemirror.on("change", markUnsaved);
    }

    // Link-click interception for internal navigation
    document.addEventListener("click", e => {
        if (!hasUnsavedChanges || isSaving) return;

        const link = e.target.closest("a");
        if (!link || !link.href) return;

        // Ignore same-page anchors
        try {
            const linkUrl = new URL(link.href, window.location.origin);
            const currentUrl = new URL(window.location.href);
            if (linkUrl.origin === currentUrl.origin && linkUrl.pathname === currentUrl.pathname) return;
        } catch (err) {
            return;
        }

        e.preventDefault();
        showConfirm({
            title: "Unsaved Changes",
            message: "You have unsaved changes. Leave without saving?",
            confirmText: "Leave",
            cancelText: "Stay"
        }).then(confirmed => {
            if (confirmed) {
                hasUnsavedChanges = false;
                window.location.href = link.href;
            }
        });
    });

    // Reorder mode toggle
    const reorderBtn = document.getElementById('toggle-reorder-mode');
    if (reorderBtn) {
        reorderBtn.addEventListener('click', () => {
            document.body.classList.toggle('reorder-mode');

            const icon = reorderBtn.querySelector('i');
            if (document.body.classList.contains('reorder-mode')) {
                icon.classList.replace('bi-arrows-angle-expand', 'bi-arrows-angle-contract');
                reorderBtn.title = 'Exit expanded reordering';
            } else {
                icon.classList.replace('bi-arrows-angle-contract', 'bi-arrows-angle-expand');
                reorderBtn.title = 'Expand for reordering';
            }

            if (window.renderPlaylist) {
                window.renderPlaylist();
            }
        });
    }

    // Browser-level navigation warning
    window.addEventListener("beforeunload", e => {
        if (hasUnsavedChanges && !isSaving) {
            const confirmationMessage = "You have unsaved changes. Are you sure you want to leave?";
            e.returnValue = confirmationMessage;
            return confirmationMessage;
        }
    });

    // Cover generation/uploading modal
    const coverUploadBtn = document.getElementById('cover-upload-btn');
    if (coverUploadBtn) {
        coverUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const coverModal = new bootstrap.Modal(document.getElementById('coverOptionsModal'));
            coverModal.show();
        });
    }

    // Wire up modal options
    const uploadOption = document.getElementById('upload-cover-option');
    const generateOption = document.getElementById('generate-composite-option');

    if (uploadOption) {
        uploadOption.addEventListener('click', () => {
            document.getElementById('cover-upload').click();
            bootstrap.Modal.getInstance(document.getElementById('coverOptionsModal')).hide();
        });
    }

    if (generateOption) {
        generateOption.addEventListener('click', () => {
            generateCompositeCover();
            bootstrap.Modal.getInstance(document.getElementById('coverOptionsModal')).hide();
        });
    }

    /**
     * Generates a composite cover from playlist track covers
     */
    function generateCompositeCover() {
        const allCovers = playlist
            .map(item => item.cover)
            .filter(Boolean);

        if (allCovers.length === 0) {
            showAlert({
                title: "No Covers Available",
                message: "Add tracks with covers to generate a composite."
            });
            return;
        }

        fetch('/editor/generate_composite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ covers: allCovers })
        })
        .then(response => {
            if (!response.ok) throw new Error('Generation failed');
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showAlert({
                    title: "Error",
                    message: data.error
                });
                return;
            }
            coverDataUrl = data.data_url;
            document.getElementById('playlist-cover').src = coverDataUrl;
            markUnsaved();
        })
        .catch(err => {
            console.error("Composite generation error:", err);
            showAlert({
                title: "Error",
                message: "Failed to generate composite. Try again."
            });
        });
    }

    // Floating buttons setup (mobile only)
    const floatingSave = document.getElementById("floating-save");
    const floatingTracks = document.getElementById("floating-tracks");

    if (floatingSave) {
        floatingSave.addEventListener("click", () => {
            saveBtn.click();
        });
    }

    if (floatingTracks) {
        floatingTracks.addEventListener("click", () => {
            const tracksTab = document.getElementById("tracks-tab");
            if (tracksTab) {
                const bsTab = new bootstrap.Tab(tracksTab);
                bsTab.show();
            }

            const mixtapeCard = document.querySelector(".col-lg-5 .card");
            if (mixtapeCard) {
                mixtapeCard.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    }

    // Initial sync of badges
    updateSaveButton();
}

/**
 * Activate the correct sub-tab inside the "Liner Notes" section.
 *
 * @param {boolean} showPreview - If true, the Preview tab becomes active.
 *                                If false, the Write tab becomes active.
 */
export function activateInitialNotesTab(showPreview) {
    const targetId = showPreview ? "preview-tab" : "write-tab";
    const targetEl = document.getElementById(targetId);
    if (!targetEl) return;

    const bsTab = new bootstrap.Tab(targetEl);
    bsTab.show();
}
