// static/js/common/qrShare.js

/**
 * Common QR code sharing functionality
 * Works across browser, editor, and player pages
 */

// Store current slug when modal is opened
let currentModalSlug = null;

/**
 * Initialize QR sharing for a specific context
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.shareButtonSelector - CSS selector for share button(s)
 * @param {string} options.modalId - ID of the QR modal
 * @param {Function} options.getSlug - Function to get the current mixtape slug
 * @param {boolean} options.autoShow - Whether button should always be visible (default: false)
 */
export function initQRShare(options = {}) {
    const {
        shareButtonSelector = '.qr-share-btn',
        modalId = 'qrShareModal',
        getSlug = null,
        autoShow = false
    } = options;

    const modal = initModal(modalId);
    if (!modal) {
        console.warn('QR share modal not found');
        return;
    }

    // Initialize all share buttons
    const shareButtons = document.querySelectorAll(shareButtonSelector);
    shareButtons.forEach(btn => {
        initShareButton(btn, modal, getSlug, autoShow);
    });

    // Setup modal buttons
    setupModalButtons(modal, getSlug);

    // Listen for dynamic updates (e.g., after save in editor)
    document.addEventListener('mixtape-saved', (e) => {
        updateShareButtons(shareButtonSelector, autoShow);
    });
}

/**
 * Initialize Bootstrap modal
 */
function initModal(modalId) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return null;
    
    return new bootstrap.Modal(modalEl);
}

/**
 * Initialize a single share button
 */
function initShareButton(button, modal, getSlugFn, autoShow) {
    // Show button if autoShow or if slug exists
    if (autoShow) {
        button.style.display = '';
    } else {
        const slug = getSlugFromButton(button, getSlugFn);
        if (slug) {
            button.style.display = '';
        }
    }

    // Click handler
    button.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        const slug = getSlugFromButton(button, getSlugFn);
        if (slug) {
            showQRModal(modal, slug);
        } else {
            showError('Please save your mixtape first');
        }
    });
}

/**
 * Get slug from button or custom function
 */
function getSlugFromButton(button, getSlugFn) {
    // Try custom function first
    if (getSlugFn) {
        try {
            const slug = getSlugFn(button);
            if (slug) return slug;
        } catch (e) {
            console.warn('getSlugFn error:', e);
        }
    }
    
    // Try data attribute (browser page buttons)
    if (button && button.dataset && button.dataset.slug) {
        return button.dataset.slug;
    }
    
    // Try getting from editing input (editor page)
    const editingInput = document.getElementById('editing-slug');
    if (editingInput && editingInput.value) {
        return editingInput.value;
    }
    
    // Try getting from URL (player page)
    const match = window.location.pathname.match(/\/play\/share\/([^\/]+)/);
    if (match) {
        return decodeURIComponent(match[1]);
    }
    
    // Try from preloaded data (editor page)
    if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.slug) {
        return window.PRELOADED_MIXTAPE.slug;
    }
    
    return null;
}

/**
 * Update visibility of share buttons after save
 */
function updateShareButtons(selector, autoShow) {
    if (autoShow) return; // Already always visible
    
    const buttons = document.querySelectorAll(selector);
    buttons.forEach(btn => {
        const slug = getSlugFromButton(btn, null);
        if (slug) {
            btn.style.display = '';
        }
    });
}

/**
 * Show QR modal with loading state
 */
function showQRModal(modal, slug) {
    const qrImg = document.getElementById('qr-code-img');
    const qrLoading = document.getElementById('qr-loading');
    const qrError = document.getElementById('qr-error');
    
    if (!qrImg) return;
    
    // Store current slug for modal buttons
    currentModalSlug = slug;
    
    // Show modal
    modal.show();
    
    // Reset state
    qrImg.style.display = 'none';
    if (qrLoading) qrLoading.style.display = 'block';
    if (qrError) qrError.style.display = 'none';
    
    // Build QR URL
    const qrUrl = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true`;
    
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
 * Setup modal action buttons (download, copy link)
 */
function setupModalButtons(modal, getSlugFn) {
    // Download button
    const downloadBtn = document.getElementById('qr-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await downloadQRCode(slug);
            }
        });
    }
    
    // Copy link button
    const copyLinkBtn = document.getElementById('qr-copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await copyShareLink(slug);
            }
        });
    }
}

/**
 * Get current slug from modal context
 */
function getCurrentSlug(getSlugFn) {
    // First, try the stored slug from when modal was opened
    if (currentModalSlug) {
        return currentModalSlug;
    }
    
    // Then try custom function (without parameters)
    if (getSlugFn) {
        try {
            const slug = getSlugFn();
            if (slug) return slug;
        } catch (e) {
            console.warn('getSlug function error:', e);
        }
    }
    
    // Try various sources
    const editingInput = document.getElementById('editing-slug');
    if (editingInput && editingInput.value) {
        return editingInput.value;
    }
    
    const match = window.location.pathname.match(/\/play\/share\/([^\/]+)/);
    if (match) {
        return decodeURIComponent(match[1]);
    }
    
    if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.slug) {
        return window.PRELOADED_MIXTAPE.slug;
    }
    
    return null;
}

/**
 * Download enhanced QR code with cover art
 */
async function downloadQRCode(slug) {
    const downloadBtn = document.getElementById('qr-download-btn');
    
    if (!downloadBtn) return;
    
    // Disable button during download
    const originalHTML = downloadBtn.innerHTML;
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generating...';
    
    try {
        const response = await fetch(`/qr/${encodeURIComponent(slug)}/download?size=800&include_cover=true&include_title=true`);
        
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
async function copyShareLink(slug) {
    // URL-encode the slug to handle spaces and special characters
    const encodedSlug = encodeURIComponent(slug);
    const shareUrl = `${window.location.origin}/play/share/${encodedSlug}`;
    
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
 * Show error message
 */
function showError(message) {
    showToast(message, 'danger');
}

/**
 * Helper function to preload QR code (optional optimization)
 */
export function preloadQRCode(slug) {
    if (!slug) return;
    
    const img = new Image();
    img.src = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true`;
}
