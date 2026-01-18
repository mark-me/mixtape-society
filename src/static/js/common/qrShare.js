// static/js/common/qrShare.js

/**
 * Common QR code sharing functionality
 * Works across browser, editor, and player pages
 * NOW WITH GIFT URL SUPPORT!
 */

// Store current slug when modal is opened
let currentModalSlug = null;
let currentGiftFlowEnabled = false;

/**
 * Initialize QR sharing for a specific context
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.shareButtonSelector - CSS selector for share button(s)
 * @param {string} options.modalId - ID of the QR modal
 * @param {Function} options.getSlug - Function to get the current mixtape slug
 * @param {Function} options.isGiftFlow - Function to check if gift flow is enabled
 * @param {boolean} options.autoShow - Whether button should always be visible (default: false)
 */
export function initQRShare(options = {}) {
    const {
        shareButtonSelector = '.qr-share-btn',
        modalId = 'qrShareModal',
        getSlug = null,
        isGiftFlow = null,
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
        initShareButton(btn, modal, getSlug, isGiftFlow, autoShow);
    });

    // Setup modal buttons
    setupModalButtons(modal, getSlug, isGiftFlow);

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
function initShareButton(button, modal, getSlugFn, isGiftFlowFn, autoShow) {
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
            // Check if gift flow is enabled
            const giftFlowEnabled = isGiftFlowFn ? isGiftFlowFn() : checkGiftFlowEnabled();
            showQRModal(modal, slug, giftFlowEnabled);
        } else {
            showError('Please save your mixtape first');
        }
    });
}

/**
 * Check if gift flow is enabled from various sources
 */
function checkGiftFlowEnabled() {
    // Try to get from window.getGiftSettings if available (editor page)
    if (typeof window.getGiftSettings === 'function') {
        try {
            const settings = window.getGiftSettings();
            return settings.gift_flow_enabled || false;
        } catch (e) {
            console.warn('Error getting gift settings:', e);
        }
    }
    
    // Try to get from PRELOADED_MIXTAPE (editor or player page)
    if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.gift_flow_enabled) {
        return true;
    }
    
    // Try to check if we're on a gift page (player page)
    if (window.location.pathname.includes('/play/gift/')) {
        return true;
    }
    
    return false;
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
    const shareMatch = window.location.pathname.match(/\/play\/share\/([^\/]+)/);
    if (shareMatch) {
        return decodeURIComponent(shareMatch[1]);
    }
    
    const giftMatch = window.location.pathname.match(/\/play\/gift\/([^\/]+)/);
    if (giftMatch) {
        return decodeURIComponent(giftMatch[1]);
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
 * @param {Object} modal - Bootstrap modal instance
 * @param {string} slug - Mixtape slug
 * @param {boolean} isGiftFlow - Whether gift flow is enabled
 */
function showQRModal(modal, slug, isGiftFlow = false) {
    const qrImg = document.getElementById('qr-code-img');
    const qrLoading = document.getElementById('qr-loading');
    const qrError = document.getElementById('qr-error');
    const modalTitle = document.querySelector('#qrShareModal .modal-title');
    const modalBody = document.querySelector('#qrShareModal .modal-body');
    
    if (!qrImg) return;
    
    // Store current slug and gift flow status for modal buttons
    currentModalSlug = slug;
    currentGiftFlowEnabled = isGiftFlow;
    
    // Update modal title and messaging based on gift flow
    if (modalTitle) {
        if (isGiftFlow) {
            modalTitle.innerHTML = '<i class="bi bi-gift me-2"></i>Share Gift Link';
        } else {
            modalTitle.innerHTML = '<i class="bi bi-share me-2"></i>Share Mixtape';
        }
    }
    
    // Add/update gift flow indicator
    let giftIndicator = document.getElementById('qr-gift-indicator');
    if (isGiftFlow) {
        if (!giftIndicator && modalBody) {
            giftIndicator = document.createElement('div');
            giftIndicator.id = 'qr-gift-indicator';
            giftIndicator.className = 'alert alert-info d-flex align-items-center mb-3';
            giftIndicator.innerHTML = `
                <i class="bi bi-gift-fill me-2"></i>
                <small>This will share the gift unwrap experience</small>
            `;
            modalBody.insertBefore(giftIndicator, modalBody.firstChild);
        }
    } else if (giftIndicator) {
        giftIndicator.remove();
    }
    
    // Show modal
    modal.show();
    
    // Reset state
    qrImg.style.display = 'none';
    if (qrLoading) qrLoading.style.display = 'block';
    if (qrError) qrError.style.display = 'none';
    
    // Build QR URL - use gift endpoint if gift flow is enabled
    const urlType = isGiftFlow ? 'gift' : 'share';
    const qrUrl = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true&type=${urlType}`;
    
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
function setupModalButtons(modal, getSlugFn, isGiftFlowFn) {
    // Download button
    const downloadBtn = document.getElementById('qr-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await downloadQRCode(slug, currentGiftFlowEnabled);
            }
        });
    }
    
    // Copy link button
    const copyLinkBtn = document.getElementById('qr-copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await copyShareLink(slug, currentGiftFlowEnabled);
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
    
    const shareMatch = window.location.pathname.match(/\/play\/share\/([^\/]+)/);
    if (shareMatch) {
        return decodeURIComponent(shareMatch[1]);
    }
    
    const giftMatch = window.location.pathname.match(/\/play\/gift\/([^\/]+)/);
    if (giftMatch) {
        return decodeURIComponent(giftMatch[1]);
    }
    
    if (window.PRELOADED_MIXTAPE && window.PRELOADED_MIXTAPE.slug) {
        return window.PRELOADED_MIXTAPE.slug;
    }
    
    return null;
}

/**
 * Download enhanced QR code with cover art
 * @param {string} slug - Mixtape slug
 * @param {boolean} isGiftFlow - Whether gift flow is enabled
 */
async function downloadQRCode(slug, isGiftFlow = false) {
    const downloadBtn = document.getElementById('qr-download-btn');
    
    if (!downloadBtn) return;
    
    // Disable button during download
    const originalHTML = downloadBtn.innerHTML;
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generating...';
    
    try {
        const urlType = isGiftFlow ? 'gift' : 'share';
        const response = await fetch(
            `/qr/${encodeURIComponent(slug)}/download?size=800&include_cover=true&include_title=true&type=${urlType}`
        );
        
        if (!response.ok) {
            throw new Error('Download failed');
        }
        
        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        const prefix = isGiftFlow ? 'gift' : 'mixtape';
        let filename = `${slug}-${prefix}-qr-code.png`;
        
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
        const message = isGiftFlow ? 'Gift QR code downloaded!' : 'QR code downloaded successfully!';
        showToast(message, 'success');
        
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
 * @param {string} slug - Mixtape slug
 * @param {boolean} isGiftFlow - Whether gift flow is enabled
 */
async function copyShareLink(slug, isGiftFlow = false) {
    // URL-encode the slug to handle spaces and special characters
    const encodedSlug = encodeURIComponent(slug);
    const urlPath = isGiftFlow ? 'gift' : 'share';
    const shareUrl = `${window.location.origin}/play/${urlPath}/${encodedSlug}`;
    
    try {
        await navigator.clipboard.writeText(shareUrl);
        const message = isGiftFlow ? 'Gift link copied to clipboard!' : 'Link copied to clipboard!';
        showToast(message, 'success');
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
            const message = isGiftFlow ? 'Gift link copied to clipboard!' : 'Link copied to clipboard!';
            showToast(message, 'success');
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
 * @param {string} slug - Mixtape slug
 * @param {boolean} isGiftFlow - Whether gift flow is enabled
 */
export function preloadQRCode(slug, isGiftFlow = false) {
    if (!slug) return;
    
    const urlType = isGiftFlow ? 'gift' : 'share';
    const img = new Image();
    img.src = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true&type=${urlType}`;
}
