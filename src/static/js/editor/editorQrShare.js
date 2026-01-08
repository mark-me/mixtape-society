// static/js/editor/qrShare.js

/**
 * QR code sharing functionality for the editor page
 * Shows share button only when mixtape is saved
 */

export function initEditorQRShare() {
    const shareBtn = document.getElementById('share-playlist');
    const qrModal = document.getElementById('qrShareModal');
    
    if (!shareBtn || !qrModal) {
        console.warn('QR share components not found in editor');
        return;
    }
    
    // Initialize Bootstrap modal
    const modal = new bootstrap.Modal(qrModal);
    
    // Show share button when mixtape is saved
    updateShareButtonVisibility();
    
    // Listen for save events to update share button
    document.addEventListener('mixtape-saved', (e) => {
        updateShareButtonVisibility();
    });
    
    // Show QR modal when share button is clicked
    shareBtn.addEventListener('click', () => {
        const slug = getCurrentSlug();
        if (slug) {
            showQRModal(modal, slug);
        } else {
            showError('Please save your mixtape first');
        }
    });
    
    // Setup download button
    const downloadBtn = document.getElementById('qr-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const slug = getCurrentSlug();
            if (slug) {
                downloadQRCode(slug);
            }
        });
    }
    
    // Setup copy link button
    const copyLinkBtn = document.getElementById('qr-copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', () => {
            copyShareLink();
        });
    }
}

/**
 * Get current mixtape slug
 */
function getCurrentSlug() {
    // Check editing slug input
    const editingInput = document.getElementById('editing-slug');
    if (editingInput && editingInput.value) {
        return editingInput.value;
    }
    
    // Check preloaded data
    if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.slug) {
        return window.PRELOADED_MIXTAPE.slug;
    }
    
    return null;
}

/**
 * Update share button visibility based on save state
 */
function updateShareButtonVisibility() {
    const shareBtn = document.getElementById('share-playlist');
    const slug = getCurrentSlug();
    
    if (!shareBtn) return;
    
    if (slug) {
        shareBtn.style.display = '';
    } else {
        shareBtn.style.display = 'none';
    }
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
            const errorMsg = qrError.querySelector('#qr-error-message');
            if (errorMsg) {
                errorMsg.textContent = 'Failed to generate QR code. Please try again.';
            }
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
        const response = await fetch(`/qr/${slug}/download?size=800&include_cover=true&include_title=true`);
        
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
        showToast('QR code downloaded successfully!', 'success');
        
    } catch (error) {
        console.error('QR download failed:', error);
        showToast('Failed to download QR code', 'danger');
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
    const slug = getCurrentSlug();
    if (!slug) {
        showToast('No mixtape to share', 'danger');
        return;
    }
    
    const shareUrl = `${window.location.origin}/share/${slug}`;
    
    try {
        await navigator.clipboard.writeText(shareUrl);
        showToast('Link copied to clipboard!', 'success');
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
            showToast('Link copied to clipboard!', 'success');
        } catch (e) {
            showToast('Failed to copy link', 'danger');
        }
        
        document.body.removeChild(textarea);
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'success') {
    // Try to use existing toast container
    let container = document.querySelector('.toast-container');
    
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1090';
        document.body.appendChild(container);
    }
    
    // Create toast element
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0 shadow`;
    toastEl.setAttribute('role', 'alert');
    
    const icon = type === 'success' ? 'check2-circle' : 'exclamation-triangle';
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-${icon} me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toastEl);
    
    // Show toast
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
    
    // Remove from DOM after hidden
    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

/**
 * Show error in QR modal
 */
function showError(message) {
    showToast(message, 'danger');
}

/**
 * Export function to manually trigger share
 */
export function triggerShare() {
    const shareBtn = document.getElementById('share-playlist');
    if (shareBtn && shareBtn.style.display !== 'none') {
        shareBtn.click();
    } else {
        showError('Please save your mixtape first');
    }
}
