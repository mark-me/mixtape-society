/**
 * Initializes the share button to copy the current page URL and show a toast notification.
 * Handles user interaction for sharing the mixtape link and provides feedback on success or failure.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initShareToast() {
    const shareBtn = document.getElementById('big-share-btn');
    const toastEl = document.getElementById('shareToast');

    if (!shareBtn || !toastEl) return;   // safety guard

    const toast = new bootstrap.Toast(toastEl);

    // Build the public URL – on a public page it’s simply the current location
    const shareUrl = window.location.href;

    shareBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(shareUrl)
            .then(() => toast.show())
            .catch(err => {
                console.error('Failed to copy:', err);
                alert('Failed to copy link. Please copy the URL manually.');
            });
    });
}