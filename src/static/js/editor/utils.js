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
