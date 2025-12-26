// static/js/editor/ui.js
import { showAlert, showConfirm, escapeHtml } from "./utils.js";
import { playlist, registerUnsavedCallback } from "./playlist.js";
import { easyMDE } from "./editorNotes.js";

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

        // ---- Validate MIME type -------------------------------------------------
        const validTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"];
        if (!validTypes.includes(file.type)) {
            showAlert("Please upload a valid image file (jpg, png, gif, webp).");
            coverInput.value = "";
            return;
        }

        // ---- Validate size (max 5 MiB) -----------------------------------------
        const maxSize = 5 * 1024 * 1024; // 5 MiB
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
    // 4️⃣  SAVE button – send mixtape JSON to the backend
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
                track: t.track,
                duration: t.duration,
                path: t.path,
                filename: t.filename
            }))
        };

        if (editingSlug) {
            const confirmOverwrite = await showConfirm({
                title: "Overwrite mixtape",
                message: `Are you sure you want to overwrite <strong>${escapeHtml(
                    title
                )}</strong>?`,
                confirmText: "Overwrite"
            });
            if (!confirmOverwrite) return;
            playlistData.slug = editingSlug;
        }

        isSaving = true;
        saveText.textContent = "Saving...";

        // Add a timeout for the fetch request (e.g., 10 seconds)
        const FETCH_TIMEOUT = 10000;
        let timeoutId;
        let didTimeout = false;

        try {
            const fetchPromise = fetch("/editor/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(playlistData)
            });

            // Create a timeout promise that rejects after FETCH_TIMEOUT ms
            const timeoutPromise = new Promise((_, reject) => {
                timeoutId = setTimeout(() => {
                    didTimeout = true;
                    reject(new Error("Network timeout: The server took too long to respond."));
                }, FETCH_TIMEOUT);
            });

            let response;
            try {
                response = await Promise.race([fetchPromise, timeoutPromise]);
            } catch (err) {
                if (didTimeout) {
                    throw err; // Timeout error
                } else {
                    throw new Error("Network error: Could not reach the server.");
                }
            } finally {
                clearTimeout(timeoutId);
            }

            if (!response.ok) {
                // Server responded with 4xx/5xx – try to extract a JSON error message or log raw text
                let errMsg = `Server returned ${response.status}`;
                try {
                    const errJson = await response.json();
                    // Only use a generic error message for users, but log details for debugging
                    if (errJson && typeof errJson.error === "string") {
                        // Log the actual error for debugging, but do not show it to the user
                        console.error("Server error:", errJson.error);
                    }
                } catch (_) {
                    let rawText = await response.text();
                    // Log the raw response text for debugging, but do not show it to the user
                    console.error("Non-JSON error response:", rawText);
                }
                // Always show a sanitized, generic error message to the user
                throw new Error("An error occurred while processing your request. Please try again later.");
            }

            const data = await response.json();

            // --------------------------------------------------------------
            // SUCCESS path
            // --------------------------------------------------------------
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

            // ---- UPDATE URL after a *new* mixtape -----------------------------
            if (!editingSlug) {
                window.history.replaceState({}, "", `/editor/${data.slug}`);
                document.getElementById("editing-slug").value = data.slug;
                saveText.textContent = "Save changes";
            }
        } catch (e) {
            // --------------------------------------------------------------
            // FAILURE path – show a friendly alert
            // --------------------------------------------------------------
            console.error("Save error:", e);
            showAlert({
                title: "Save failed",
                message: escapeHtml(e.message || "Unexpected error")
            });
        } finally {
            isSaving = false;
            saveText.textContent = editingSlug ? "Save changes" : "Save";
        }
    });

    // -----------------------------------------------------------------
    // 5️⃣  Global audio player (bottom‑fixed)
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
    // 6️⃣  “Track added” toast (re‑used for any playlist mutation)
    // -----------------------------------------------------------------
    const addTrackToastEl = document.createElement("div");
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
    const addTrackToast = new bootstrap.Toast(addTrackToastEl, { delay: 2000 });

    // -----------------------------------------------------------------
    // 7️⃣  Register the **unsaved‑changes callback** with the playlist module.
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

    // 9b. Browser‑level navigation (back/forward, tab close, refresh)
    window.addEventListener("beforeunload", e => {
        if (hasUnsavedChanges && !isSaving) {
            // Modern browsers ignore the custom text, but returning a string triggers the native confirmation dialog.
            const confirmationMessage = "You have unsaved changes. Are you sure you want to leave?";
            e.returnValue = confirmationMessage; // Gecko, Chrome 34+
            return confirmationMessage;          // WebKit, Safari
        }
    });
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
