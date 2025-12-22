// static/js/browser/copyToast.js
/**
 * Initializes copy-to-clipboard functionality and displays a toast notification on success.
 * Attaches event listeners to copy buttons and shows feedback when a URL is copied.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initCopyToast() {
    const copyToastEl = document.getElementById('copyToast');
    const copyToast = copyToastEl ? new bootstrap.Toast(copyToastEl) : null;

    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            navigator.clipboard.writeText(btn.dataset.url).then(() => copyToast?.show());
        });
    });
}