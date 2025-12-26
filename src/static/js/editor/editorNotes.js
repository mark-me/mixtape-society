// static/js/editor/editorNotes.js
import { playlist } from "./playlist.js";
import { renderTrackReferences } from "./utils.js";

const { EasyMDE, DOMPurify, marked } = window;

export let easyMDE;


/**
 * Initialise the EasyMDE markdown editor.
 *
 * @param {string|null} preloadNotes – If supplied, the editor will be pre‑filled
 *                                     with these notes (used when editing a mixtape).
 */
export function initEditorNotes(preloadNotes = null) {
    // -----------------------------------------------------------------
    // If an EasyMDE instance already exists, just update its content.
    // -----------------------------------------------------------------
    if (easyMDE) {
        if (preloadNotes) easyMDE.value(preloadNotes);
        return;
    }

    const textarea = document.getElementById("liner-notes");

    // Use the pre‑loaded notes as the *initial* value.
    // Fall back to the generic global (used for a brand‑new mixtape).
    const initialValue = preloadNotes ?? window.PRELOADED_LINER_NOTES ?? "";

    easyMDE = new EasyMDE({
        element: textarea,
        initialValue,
        spellChecker: false,
        toolbar: [
            "bold", "italic", "heading", "|", "quote", "unordered-list", "ordered-list",
            "|", "link", "image", "|", "preview", "side-by-side", "fullscreen", "|", "guide"
        ],
        previewRender: plain => DOMPurify.sanitize(marked.parse(plain))
    });

    // -----------------------------------------------------------------
    // Sync the *Preview* tab when the user switches to it.
    // -----------------------------------------------------------------
    const previewPane = document.getElementById("markdown-preview");
    const previewTab = document.getElementById("preview-tab");
    previewTab.addEventListener("shown.bs.tab", () => {
        previewPane.innerHTML = DOMPurify.sanitize(marked.parse(easyMDE.value()));
    });

    // Keep the preview live while the user types (if the preview tab is active).
    easyMDE.codemirror.on("change", () => {
        if (document.querySelector('#preview-tab.active')) {
            const html = marked.parse(easyMDE.value());
            previewPane.innerHTML = DOMPurify.sanitize(html);
        }
    });

    // -----------------------------------------------------------------
    // Custom renderer – expands #1, #2‑4, etc. using the current playlist.
    // -----------------------------------------------------------------
    easyMDE.options.previewRender = (plain, preview) => {
        const processed = renderTrackReferences(plain, playlist);
        preview.innerHTML = DOMPurify.sanitize(marked.parse(processed));
        return preview;
    };

    // -----------------------------------------------------------------
    // If the caller supplied notes *after* construction, inject them now.
    // (Usually this branch won’t run because we already gave the notes as
    // `initialValue`, but it’s kept for completeness.)
    // -----------------------------------------------------------------
    if (preloadNotes) {
        easyMDE.value(preloadNotes);
    }
}
