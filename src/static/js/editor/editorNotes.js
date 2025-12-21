// static/js/editor/editorNotes.js
import { playlist } from "./playlist.js";
import { renderTrackReferences } from "./utils.js";

export let easyMDE;

const {EasyMDE, DOMPurify, marked} = window;

export function initEditorNotes() {
    const textarea = document.getElementById("liner-notes");
    const initialValue = window.PRELOADED_LINER_NOTES || "";

    easyMDE = new EasyMDE({
        element: textarea,
        initialValue,
        spellChecker: false,
        toolbar: ["bold","italic","heading","|","quote","unordered-list","ordered-list","|","link","image","|","preview","side-by-side","fullscreen","|","guide"],
        previewRender: plain => DOMPurify.sanitize(marked.parse(plain))
    });

    // sync preview tab
    const previewPane = document.getElementById("markdown-preview");
    const previewTab  = document.getElementById("preview-tab");
    previewTab.addEventListener("shown.bs.tab", () => {
        previewPane.innerHTML = DOMPurify.sanitize(marked.parse(easyMDE.value()));
    });

    easyMDE.codemirror.on("change", () => {
        if (document.querySelector('#preview-tab.active')) {
            const html = marked.parse(easyMDE.value());
            previewPane.innerHTML = DOMPurify.sanitize(html);
        }
    });

    // custom renderer that expands #1, #2‑4, etc.
    const originalRender = easyMDE.options.previewRender;
    easyMDE.options.previewRender = (plain, preview) => {
        const processed = renderTrackReferences(plain, playlist);
        preview.innerHTML = DOMPurify.sanitize(marked.parse(processed));
        return preview;
    };
}
