import { showAlert, showConfirm, escapeHtml } from "./utils.js";
import { playlist, registerUnsavedCallback } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";

let hasUnsavedChanges = false;
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
    // UI elements we’ll interact with
    // -----------------------------------------------------------------
    const coverInput   = document.getElementById("cover-upload");
    const coverImg     = document.getElementById("playlist-cover");
    const saveBtn      = document.getElementById("save-playlist");
    const saveText     = document.getElementById("save-text");
    const editingSlug  = document.getElementById("editing-slug").value;
    const titleInput   = document.getElementById("playlist-title");

    // -----------------------------------------------------------------
    // Cover upload handling
    // -----------------------------------------------------------------
    coverInput.addEventListener("change", e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = ev => {
            coverDataUrl = ev.target.result;
            coverImg.src = coverDataUrl;
            markUnsaved();
        };
        reader.readAsDataURL(file);
    });

    // Title changes also count as “unsaved”
    titleInput.addEventListener("input", markUnsaved);

    // -----------------------------------------------------------------
    // SAVE button – send mixtape JSON to the backend
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

        const playlistData = {
            title: title,
            created_at: new Date().toISOString(),
            cover: coverDataUrl,
            liner_notes: easyMDE ? easyMDE.value() : "",
            tracks: playlist.map(t => ({
                artist: t.artist,
                album: t.album,
                title: t.title,
                duration: t.duration,
                path: t.path,
                filename: t.filename
            }))
        };

        if (editingSlug) {
            const confirmOverwrite = await showConfirm({
                title: "Overwrite mixtape",
                message: `Are you sure you want to overwrite <strong>${escapeHtml(title)}</strong>?`,
                confirmText: "Overwrite"
            });
            if (!confirmOverwrite) return;
            playlistData.slug = editingSlug;
        }

        isSaving = true;
        saveText.textContent = "Saving...";

        try {
            const response = await fetch("/editor/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(playlistData)
            });
            const data = await response.json();

            if (data.success) {
                hasUnsavedChanges = false;
                updateSaveButton();

                if (editingSlug) {
                    saveText.textContent = "Save changes";
                }

                const finalSlug = data.slug || editingSlug;

                // ---- SUCCESS TOAST -------------------------------------------------
                const toast = document.createElement("div");
                toast.className =
                    "toast align-items-center text-bg-success border-0 position-fixed bottom-0 end-0 m-4";
                toast.style.zIndex = "1090";
                toast.innerHTML = `
                    <div class="d-flex">
                        <div class="toast-body">
                            Mixtape ${editingSlug ? "updated" : "saved"} as <strong>${escapeHtml(
                    data.title
                )}</strong><br>
                            <a href="/play/share/${finalSlug}" class="text-white text-decoration-underline" target="_blank">Open public link →</a>
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>`;
                document.body.appendChild(toast);
                new bootstrap.Toast(toast).show();

                // ---- UPDATE URL after a *new* mixtape ----------------------------
                if (!editingSlug) {
                    window.history.replaceState({}, "", `/editor/${data.slug}`);
                    document.getElementById("editing-slug").value = data.slug;
                    saveText.textContent = "Save changes";
                }
            } else {
                showAlert({
                    title: "Save failed",
                    message: escapeHtml(data.error || "Unknown error")
                });
            }
        } catch (e) {
            showAlert({ title: "Network error", message: escapeHtml(e.message) });
        } finally {
            isSaving = false;
            saveText.textContent = editingSlug ? "Save changes" : "Save";
        }
    });

    // -----------------------------------------------------------------
    // Global audio player (bottom‑fixed)
    // -----------------------------------------------------------------
    const audioPlayer    = document.getElementById("global-audio-player");
    const playerContainer = document.getElementById("audio-player-container");
    const closeBtn       = document.getElementById("close-player");

    // When any track (including preview tracks) starts playing, show the player.
    audioPlayer?.addEventListener("play", () => {
        playerContainer.style.display = "block";
    });

    // Close button hides the player and pauses playback.
    closeBtn?.addEventListener("click", () => {
        audioPlayer?.pause();
        playerContainer.style.display = "none";
    });

    // -----------------------------------------------------------------
    // “Track added” toast (re‑used for any playlist mutation)
    // -----------------------------------------------------------------
    const addTrackToastEl = document.createElement("div");
    addTrackToastEl.className =
        "toast position-fixed bottom-0 end-0 m-3";
    addTrackToastEl.setAttribute("role", "alert");
    addTrackToastEl.setAttribute("aria-live", "assertive");
    addTrackToastEl.setAttribute("aria-atomic", "true");
    addTrackToastEl.innerHTML = `
        <div class="toast-header bg-success text-white">
            <strong class="me-auto">Track added!</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
    `;
    document.body.appendChild(addTrackToastEl);
    const addTrackToast = new bootstrap.Toast(addTrackToastEl, { delay: 2000 });

    // -----------------------------------------------------------------
    // Register the **unsaved‑changes callback** with the playlist module.
    //      The playlist module will call this function after ANY mutation
    //      (add, clear, remove, drag‑reorder).
    // -----------------------------------------------------------------
    registerUnsavedCallback(() => {
        // Show the “Unsaved” badge
        markUnsaved();
        // Also fire the toast that tells the user a track was added / playlist changed
        addTrackToast.show();
    });

    // -----------------------------------------------------------------
    // EasyMDE (liner‑notes) – mark unsaved on any edit
    // -----------------------------------------------------------------
    if (easyMDE) {
        easyMDE.codemirror.on("change", markUnsaved);
    }

    // -----------------------------------------------------------------
    // 8️⃣  Warn the user if they try to navigate away with unsaved changes
    // -----------------------------------------------------------------
    document.addEventListener("click", e => {
        if (hasUnsavedChanges && !isSaving) {
            const link = e.target.closest("a");
            if (link && link.href && !link.href.includes(window.location.pathname)) {
                e.preventDefault();
                showConfirm({
                    title: "Unsaved changes",
                    message: "You have unsaved changes. Leave without saving?",
                    confirmText: "Leave",
                    cancelText: "Stay"
                }).then(confirmed => {
                    if (confirmed) {
                        hasUnsavedChanges = false;
                        window.location.href = link.href;
                    }
                });
            }
        }
    });
}