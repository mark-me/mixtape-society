// static/js/player/qrShare.js

/**
 * QR code sharing functionality for mixtapes
 * Handles QR code modal display, generation, and download
 */

/**
 * Initialize QR code sharing functionality
 */
export function initQRShare() {
    const shareBtn = document.getElementById('big-share-btn');
    const qrModal = document.getElementById('qrShareModal');

    if (!shareBtn || !qrModal) {
        console.warn('QR share components not found');
        return;
    }

    // Get mixtape slug from page
    const slug = getSlugFromURL();
    if (!slug) {
        console.error('Could not determine mixtape slug');
        return;
    }

    // Initialize Bootstrap modal
    const modal = new bootstrap.Modal(qrModal);

    // Show QR modal when share button is clicked
    shareBtn.addEventListener('click', () => {
        showQRModal(modal, slug);
    });

    // Setup download button
    const downloadBtn = document.getElementById('qr-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            downloadQRCode(slug);
        });
    }

    // Setup copy link button in modal
    const copyLinkBtn = document.getElementById('qr-copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', () => {
            copyShareLink();
        });
    }
}

/**
 * Extract mixtape slug from current URL
 */
function getSlugFromURL() {
    const path = window.location.pathname;
    const match = path.match(/\/share\/([^\/]+)/);
    return match ? match[1] : null;
}

/**
 * Show QR code modal and load QR image
 */
function showQRModal(modal, slug) {
    const qrImg = document.getElementById('qr-code-img');
    const qrLoading = document.getElementById('qr-loading');
    const qrError = document.getElementById('qr-error');

    if (!qrImg) return;

    // Show modal
    modal.show();

    // Reset state
    qrImg.style.display = 'none';
    if (qrLoading) qrLoading.style.display = 'block';
    if (qrError) qrError.style.display = 'none';

    // Build QR URL
    const qrUrl = `/qr/${slug}.png?size=400&logo=true`;

    // Load QR code image
    const img = new Image();

    img.onload = () => {
        qrImg.src = qrUrl;
        qrImg.style.display = 'block';
        if (qrLoading) qrLoading.style.display = 'none';
    };

    img.onerror = () => {
        if (qrLoading) qrLoading.style.display = 'none';
        if (qrError) {
            qrError.style.display = 'block';
            qrError.textContent = 'Failed to generate QR code. Please try again.';
        }
    };

    img.src = qrUrl;
}

/**
 * Download QR code as PNG file
 */
async function downloadQRCode(slug) {
    const downloadBtn = document.getElementById('qr-download-btn');

    if (!downloadBtn) return;

    // Disable button during download
    const originalHTML = downloadBtn.innerHTML;
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generating...';

    try {
        const response = await fetch(`/qr/${slug}/download?size=800`);

        if (!response.ok) {
            throw new Error('Download failed');
        }

        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `${slug}-qr-code.png`;

        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?(.+)"?/);
            if (match) filename = match[1];
        }

        // Create blob and download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Show success message
        showDownloadToast('QR code downloaded successfully!', 'success');

    } catch (error) {
        console.error('QR download failed:', error);
        showDownloadToast('Failed to download QR code', 'danger');
    } finally {
        // Re-enable button
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = originalHTML;
    }
}

/**
 * Copy share link to clipboard
 */
async function copyShareLink() {
    const shareUrl = window.location.href;

    try {
        await navigator.clipboard.writeText(shareUrl);
        showDownloadToast('Link copied to clipboard!', 'success');
    } catch (error) {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = shareUrl;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();

        try {
            document.execCommand('copy');
            showDownloadToast('Link copied to clipboard!', 'success');
        } catch (e) {
            showDownloadToast('Failed to copy link', 'danger');
        }

        document.body.removeChild(textarea);
    }
}

/**
 * Show toast notification
 */
function showDownloadToast(message, type = 'success') {
    // Use existing toast or create new one
    let toastEl = document.getElementById('qrToast');

    if (!toastEl) {
        // Create toast element
        toastEl = document.createElement('div');
        toastEl.id = 'qrToast';
        toastEl.className = 'toast align-items-center border-0 shadow';
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body"></div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        // Add to container
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1090';
            document.body.appendChild(container);
        }
        container.appendChild(toastEl);
    }

    // Update toast styling and content
    toastEl.className = `toast align-items-center text-bg-${type} border-0 shadow`;
    const body = toastEl.querySelector('.toast-body');
    if (body) {
        const icon = type === 'success' ? 'check2-circle' : 'exclamation-triangle';
        body.innerHTML = `<i class="bi bi-${icon} me-2"></i>${message}`;
    }

    // Show toast
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
}

/**
 * Preload QR code (optional - for faster display)
 */
export function preloadQRCode(slug) {
    if (!slug) return;

    const img = new Image();
    img.src = `/qr/${slug}.png?size=400&logo=true`;
}
