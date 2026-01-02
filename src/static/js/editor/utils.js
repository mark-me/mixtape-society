// static/js/editor/utils.js

/**
 * Converts special characters in a string to their corresponding HTML entities.
 * Prevents HTML injection by escaping user-provided text for safe rendering.
 */
export function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&apos;");
}

/**
 * Escapes special characters in a string for use in a regular expression.
 * Ensures that user-provided strings can be safely inserted into regex patterns.
 */
export function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Highlights all occurrences of a query string within a given text by wrapping them in a <mark> tag.
 * Returns the text with highlighted matches, or the original text if the query is empty.
 */
export function highlightText(text, query) {
    if (!query.trim()) return escapeHtml(text);
    const regex = new RegExp(`(${escapeRegExp(query.trim())})`, "gi");
    return escapeHtml(text).replace(regex, "<mark>$1</mark>");
}

// Modal instance
const appModalEl = document.getElementById('appModal');
const appModal = new bootstrap.Modal(appModalEl);

/**
 * Displays a modal alert dialog with a customizable title, message, and button text.
 * Shows a simple notification to the user that requires acknowledgment.
 *
 * @param {Object|string} options - Either an options object or a message string
 * @param {string} options.title - The title of the alert dialog (default: "Notice")
 * @param {string} options.message - The message to display in the alert body
 * @param {string} options.buttonText - The text for the confirmation button (default: "OK")
 */
export function showAlert(options) {
    // Support both object and string parameters for backwards compatibility
    if (typeof options === 'string') {
        options = { message: options };
    }

    const {
        title = "Notice",
        message,
        buttonText = "OK"
    } = options;

    document.getElementById('appModalTitle').textContent = title;
    document.getElementById('appModalBody').innerHTML = message;
    document.getElementById('appModalFooter').innerHTML = `
        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
            ${buttonText}
        </button>
    `;
    appModal.show();
}

/**
 * Displays a modal confirmation dialog with customizable title, message, and button texts.
 * Returns a promise that resolves to true if the user confirms, or false if cancelled or dismissed.
 *
 * @param {Object} options - Configuration object
 * @param {string} options.title - The title of the confirmation dialog (default: "Confirm")
 * @param {string} options.message - The message to display in the dialog body
 * @param {string} options.confirmText - The text for the confirmation button (default: "Confirm")
 * @param {string} options.cancelText - The text for the cancellation button (default: "Cancel")
 * @returns {Promise<boolean>} A Promise that resolves to true if confirmed, false otherwise
 */
export function showConfirm({
    title = "Confirm",
    message,
    confirmText = "Confirm",
    cancelText = "Cancel"
}) {
    return new Promise(resolve => {
        document.getElementById('appModalTitle').textContent = title;
        document.getElementById('appModalBody').innerHTML = message;
        document.getElementById('appModalFooter').innerHTML = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                ${cancelText}
            </button>
            <button type="button" class="btn btn-danger" id="appModalConfirmBtn">
                ${confirmText}
            </button>
        `;

        let confirmed = false;
        const confirmBtn = document.getElementById('appModalConfirmBtn');

        confirmBtn.onclick = () => {
            confirmed = true;
            appModal.hide();
            resolve(true);
        };

        // If the modal is closed without confirming (X, backdrop, ESC)
        const hiddenHandler = () => {
            if (!confirmed) resolve(false);
        };
        appModalEl.addEventListener('hidden.bs.modal', hiddenHandler, { once: true });

        appModal.show();
    });
}

/**
 * Renders track references in markdown text.
 * Expands shorthand references like #1, #2-4 into full track information.
 *
 * @param {string} text - The text containing track references
 * @param {Array} tracks - Array of track objects
 * @returns {string} The text with expanded track references
 */
export function renderTrackReferences(text, tracks) {
    if (typeof text !== 'string') return '';
    if (!Array.isArray(tracks) || tracks.length === 0) return text;

    // Range: #3-7
    text = text.replace(/#(\d+)-(\d+)/g, (match, start, end) => {
        start = parseInt(start);
        end = parseInt(end);
        if (start > end || start < 1 || end > tracks.length) return match;

        const parts = [];
        for (let i = start; i <= end; i++) {
            const t = tracks[i - 1];
            parts.push(`${i}. ${t.title} — ${t.artist}`);
        }
        return parts.join(" → ");
    });

    // Single: #4
    text = text.replace(/#(\d+)/g, (match, num) => {
        const i = parseInt(num);
        if (i < 1 || i > tracks.length) return match;
        const t = tracks[i - 1];
        return `**${i}. ${t.title} — ${t.artist}**`;
    });

    return text;
}

/**
 * Safely encodes JSON for embedding in HTML attributes
 *
 * @param {*} json - Any JSON-serializable value
 * @returns {string} HTML-safe JSON string
 */
export function htmlSafeJson(json) {
    return JSON.stringify(JSON.stringify(json)).slice(1, -1);
}
