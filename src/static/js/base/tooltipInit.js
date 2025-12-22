// static/js/base/tooltipInit.js
/**
 * Initializes Bootstrap tooltips for all elements with the tooltip data attribute.
 * Ensures tooltips are enabled and ready after the DOM content is loaded.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initTooltips() {
    document.addEventListener('DOMContentLoaded', () => {
        const triggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        triggers.forEach(el => new bootstrap.Tooltip(el));
    });
}
