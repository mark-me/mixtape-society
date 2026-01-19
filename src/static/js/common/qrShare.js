// static/js/common/qrShare.js

/**
 * Unified QR code sharing with regular and gift modes
 * Works across browser, editor, and player pages
 */

// Store current state
let currentModalSlug = null;
let currentShareMode = 'regular'; // 'regular' or 'gift'
let giftSettings = {
    creator_name: '',
    unwrap_style: 'playful',
    show_tracklist_after_completion: true
};

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

    // Load saved gift preferences
    loadGiftPreferences();

    // Initialize all share buttons
    const shareButtons = document.querySelectorAll(shareButtonSelector);
    shareButtons.forEach(btn => {
        initShareButton(btn, modal, getSlug, autoShow);
    });

    // Setup modal controls
    setupModalControls(modal, getSlug);

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
    const shareMatch = window.location.pathname.match(/\/play\/share\/([^\/]+)/);
    if (shareMatch) {
        return decodeURIComponent(shareMatch[1]);
    }
    
    const giftMatch = window.location.pathname.match(/\/play\/gift\/([^\/]+)/);
    if (giftMatch) {
        return decodeURIComponent(giftMatch[1]);
    }
    
    // Try from preloaded data
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
 * Show QR modal
 */
function showQRModal(modal, slug) {
    currentModalSlug = slug;
    currentShareMode = 'regular';
    
    // Reset to regular share tab
    const regularTab = document.getElementById('regular-share-tab');
    if (regularTab) {
        const tab = new bootstrap.Tab(regularTab);
        tab.show();
    }
    
    // Show modal
    modal.show();
    
    // Load regular QR code
    loadRegularQR(slug);
}

/**
 * Load regular share QR code
 */
function loadRegularQR(slug) {
    const qrImg = document.getElementById('qr-code-img');
    const qrLoading = document.getElementById('qr-loading');
    const qrError = document.getElementById('qr-error');
    const qrInstructions = document.getElementById('qr-instructions');
    
    if (!qrImg) return;
    
    // Reset state
    qrImg.style.display = 'none';
    if (qrLoading) qrLoading.style.display = 'block';
    if (qrError) qrError.style.display = 'none';
    if (qrInstructions) qrInstructions.style.display = 'none';
    
    // Build QR URL
    const qrUrl = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true&type=share`;
    
    // Load QR code image
    const img = new Image();
    
    img.onload = () => {
        qrImg.src = qrUrl;
        qrImg.style.display = 'block';
        if (qrLoading) qrLoading.style.display = 'none';
        if (qrInstructions) qrInstructions.style.display = 'block';
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
 * Setup modal controls (tabs, buttons, etc.)
 */
function setupModalControls(modal, getSlugFn) {
    // Tab switching
    const regularTab = document.getElementById('regular-share-tab');
    const giftTab = document.getElementById('gift-share-tab');
    
    if (regularTab) {
        regularTab.addEventListener('shown.bs.tab', () => {
            currentShareMode = 'regular';
            const slug = getCurrentSlug(getSlugFn);
            if (slug) loadRegularQR(slug);
        });
    }
    
    if (giftTab) {
        giftTab.addEventListener('shown.bs.tab', () => {
            currentShareMode = 'gift';
            showGiftConfigForm();
        });
    }
    
    // Gift form controls
    setupGiftFormControls();
    
    // Action buttons
    const downloadBtn = document.getElementById('qr-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await downloadQRCode(slug, currentShareMode);
            }
        });
    }
    
    const copyLinkBtn = document.getElementById('qr-copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', async () => {
            const slug = getCurrentSlug(getSlugFn);
            if (slug) {
                await copyShareLink(slug, currentShareMode);
            }
        });
    }
}

/**
 * Setup gift form controls
 */
function setupGiftFormControls() {
    // Preview button
    const previewBtn = document.getElementById('preview-gift-style');
    if (previewBtn) {
        previewBtn.addEventListener('click', () => {
            const style = getSelectedGiftStyle();
            openGiftPreview(style);
        });
    }
    
    // Generate gift QR button
    const generateBtn = document.getElementById('generate-gift-qr');
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            await generateGiftQR();
        });
    }
    
    // Edit gift settings button
    const editBtn = document.getElementById('edit-gift-settings');
    if (editBtn) {
        editBtn.addEventListener('click', () => {
            showGiftConfigForm();
        });
    }
}

/**
 * Show gift configuration form
 */
function showGiftConfigForm() {
    const configForm = document.getElementById('gift-config-form');
    const qrDisplay = document.getElementById('gift-qr-display');
    
    if (configForm) {
        configForm.style.display = 'block';
        
        // Populate with saved settings
        const nameInput = document.getElementById('gift-creator-name-modal');
        if (nameInput) nameInput.value = giftSettings.creator_name;
        
        const styleRadio = document.getElementById(`style-${giftSettings.unwrap_style}-modal`);
        if (styleRadio) styleRadio.checked = true;
        
        const tracklistCheckbox = document.getElementById('show-tracklist-modal');
        if (tracklistCheckbox) tracklistCheckbox.checked = giftSettings.show_tracklist_after_completion;
    }
    
    if (qrDisplay) {
        qrDisplay.style.display = 'none';
    }
}

/**
 * Get selected gift style from form
 */
function getSelectedGiftStyle() {
    const selected = document.querySelector('input[name="gift-style-modal"]:checked');
    return selected ? selected.value : 'playful';
}

/**
 * Open gift preview window
 */
function openGiftPreview(style) {
    const previewUrl = `/static/mockups/mockup-${style}.html`;
    
    const width = 600;
    const height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    window.open(
        previewUrl,
        'GiftFlowPreview',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );
}

/**
 * Generate gift QR code
 */
async function generateGiftQR() {
    const slug = currentModalSlug;
    if (!slug) return;
    
    // Get form values
    const nameInput = document.getElementById('gift-creator-name-modal');
    const receiverInput = document.getElementById('gift-receiver-name-modal');
    const noteInput = document.getElementById('gift-note-modal');
    const style = getSelectedGiftStyle();
    const tracklistCheckbox = document.getElementById('show-tracklist-modal');
    const saveDefaultsCheckbox = document.getElementById('save-gift-defaults-modal');
    
    // Update settings (storing for QR generation and copy link)
    giftSettings.creator_name = nameInput ? nameInput.value.trim() : '';
    giftSettings.receiver_name = receiverInput ? receiverInput.value.trim() : '';
    giftSettings.gift_note = noteInput ? noteInput.value.trim() : '';
    giftSettings.unwrap_style = style;
    giftSettings.show_tracklist_after_completion = tracklistCheckbox ? tracklistCheckbox.checked : true;
    
    // Save defaults if requested (only save creator name, not receiver/note)
    if (saveDefaultsCheckbox && saveDefaultsCheckbox.checked) {
        await saveGiftPreferences();
        saveDefaultsCheckbox.checked = false; // Reset checkbox
    }
    
    // Show QR display area
    const configForm = document.getElementById('gift-config-form');
    const qrDisplay = document.getElementById('gift-qr-display');
    const giftQrLoading = document.getElementById('gift-qr-loading');
    const giftQrImg = document.getElementById('gift-qr-code-img');
    const giftInfo = document.getElementById('gift-info');
    const giftEditLink = document.getElementById('gift-edit-link');
    
    if (configForm) configForm.style.display = 'none';
    if (qrDisplay) qrDisplay.style.display = 'block';
    if (giftQrLoading) giftQrLoading.style.display = 'block';
    if (giftQrImg) giftQrImg.style.display = 'none';
    if (giftInfo) giftInfo.style.display = 'none';
    if (giftEditLink) giftEditLink.style.display = 'none';
    
    // Build gift URL with query parameters for personalization
    const params = new URLSearchParams();
    if (giftSettings.receiver_name) params.append('to', giftSettings.receiver_name);
    if (giftSettings.gift_note) params.append('note', giftSettings.gift_note);
    if (giftSettings.creator_name) params.append('from', giftSettings.creator_name);
    
    const urlType = style === 'elegant' ? 'gift-elegant' : 'gift-playful';
    const baseQrUrl = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true&type=${urlType}`;
    
    // Add gift parameters to QR URL
    const qrUrl = params.toString() ? `${baseQrUrl}&${params.toString()}` : baseQrUrl;
    
    // Load QR code image
    const img = new Image();
    
    img.onload = () => {
        if (giftQrImg) {
            giftQrImg.src = qrUrl;
            giftQrImg.style.display = 'block';
        }
        if (giftQrLoading) giftQrLoading.style.display = 'none';
        
        // Show gift info
        if (giftInfo) {
            const fromDisplay = document.getElementById('gift-from-display');
            const toDisplay = document.getElementById('gift-to-display');
            const styleDisplay = document.getElementById('gift-style-display');
            
            if (fromDisplay) fromDisplay.textContent = giftSettings.creator_name || 'Anonymous';
            if (toDisplay) toDisplay.textContent = giftSettings.receiver_name || '(not specified)';
            if (styleDisplay) {
                const emoji = style === 'elegant' ? '✨' : '🎉';
                const label = style.charAt(0).toUpperCase() + style.slice(1);
                styleDisplay.textContent = `${emoji} ${label}`;
            }
            
            giftInfo.style.display = 'block';
        }
        
        if (giftEditLink) giftEditLink.style.display = 'block';
    };
    
    img.onerror = () => {
        if (giftQrLoading) giftQrLoading.style.display = 'none';
        showError('Failed to generate gift QR code');
    };
    
    img.src = qrUrl;
}

/**
 * Get current slug from modal context
 */
function getCurrentSlug(getSlugFn) {
    if (currentModalSlug) {
        return currentModalSlug;
    }
    
    if (getSlugFn) {
        try {
            const slug = getSlugFn();
            if (slug) return slug;
        } catch (e) {
            console.warn('getSlug function error:', e);
        }
    }
    
    return getSlugFromButton(null, null);
}

/**
 * Download QR code (regular or gift)
 */
async function downloadQRCode(slug, mode) {
    const downloadBtn = document.getElementById('qr-download-btn');
    
    if (!downloadBtn) return;
    
    const originalHTML = downloadBtn.innerHTML;
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generating...';
    
    try {
        let urlType = 'share';
        if (mode === 'gift') {
            urlType = giftSettings.unwrap_style === 'elegant' ? 'gift-elegant' : 'gift-playful';
        }
        
        const response = await fetch(
            `/qr/${encodeURIComponent(slug)}/download?size=800&include_cover=true&include_title=true&type=${urlType}`
        );
        
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
        
        const message = mode === 'gift' ? 'Gift QR code downloaded!' : 'QR code downloaded successfully!';
        showToast(message, 'success');
        
    } catch (error) {
        console.error('QR download failed:', error);
        showToast('Failed to download QR code', 'danger');
    } finally {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = originalHTML;
    }
}

/**
 * Copy share link to clipboard
 */
async function copyShareLink(slug, mode) {
    const encodedSlug = encodeURIComponent(slug);
    let shareUrl;
    
    if (mode === 'gift') {
        // Get current style from form (in case user changed it after generating QR)
        const currentStyle = getSelectedGiftStyle();
        const baseUrl = `${window.location.origin}/play/gift-${currentStyle}/${encodedSlug}`;
        
        // Add personalization parameters
        const params = new URLSearchParams();
        if (giftSettings.receiver_name) params.append('to', giftSettings.receiver_name);
        if (giftSettings.gift_note) params.append('note', giftSettings.gift_note);
        if (giftSettings.creator_name) params.append('from', giftSettings.creator_name);
        
        shareUrl = params.toString() ? `${baseUrl}?${params.toString()}` : baseUrl;
    } else {
        shareUrl = `${window.location.origin}/play/share/${encodedSlug}`;
    }
    
    try {
        await navigator.clipboard.writeText(shareUrl);
        const message = mode === 'gift' ? 'Gift link copied to clipboard!' : 'Link copied to clipboard!';
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
            const message = mode === 'gift' ? 'Gift link copied to clipboard!' : 'Link copied to clipboard!';
            showToast(message, 'success');
        } catch (e) {
            showToast('Failed to copy link', 'danger');
        }
        
        document.body.removeChild(textarea);
    }
}

/**
 * Load gift preferences from server
 */
async function loadGiftPreferences() {
    try {
        const response = await fetch('/editor/preferences');
        if (response.ok) {
            const prefs = await response.json();
            
            if (prefs.creator_name) {
                giftSettings.creator_name = prefs.creator_name;
            }
            if (prefs.default_unwrap_style) {
                giftSettings.unwrap_style = prefs.default_unwrap_style;
            }
            if (prefs.default_show_tracklist !== undefined) {
                giftSettings.show_tracklist_after_completion = prefs.default_show_tracklist;
            }
        }
    } catch (error) {
        console.warn('Failed to load gift preferences:', error);
    }
}

/**
 * Save gift preferences to server
 */
async function saveGiftPreferences() {
    try {
        const response = await fetch('/editor/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                creator_name: giftSettings.creator_name,
                default_unwrap_style: giftSettings.unwrap_style,
                default_show_tracklist: giftSettings.show_tracklist_after_completion
            })
        });
        
        if (response.ok) {
            showToast('Gift preferences saved!', 'success');
        }
    } catch (error) {
        console.error('Failed to save gift preferences:', error);
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1090';
        document.body.appendChild(container);
    }
    
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
    
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
    
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
    img.src = `/qr/${encodeURIComponent(slug)}.png?size=400&logo=true&type=share`;
}
