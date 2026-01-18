// static/js/editor/giftSettings.js

/**
 * Gift Settings Module
 * Manages the gift flow settings modal: creator name, gift flow toggle, unwrap style, and tracklist visibility
 */

let currentGiftSettings = {
    creator_name: '',
    gift_flow_enabled: false,
    unwrap_style: 'playful',  // NEW: 'playful' or 'elegant'
    show_tracklist_after_completion: true
};

/**
 * Initialize gift settings modal and event listeners
 */
export function initGiftSettings() {
    const modal = document.getElementById('giftSettingsModal');
    const giftBtn = document.getElementById('gift-settings-btn');
    const giftFlowToggle = document.getElementById('gift-flow-enabled');
    const styleContainer = document.getElementById('gift-style-container');
    const tracklistContainer = document.getElementById('tracklist-setting-container');
    const saveDefaultCheckbox = document.getElementById('save-creator-name-default');
    const previewBtn = document.getElementById('preview-gift-flow');

    if (!modal || !giftBtn) return;

    // Load initial values from preloaded mixtape
    loadInitialSettings();

    // Show/hide style and tracklist settings based on gift flow toggle
    giftFlowToggle?.addEventListener('change', function() {
        const isEnabled = this.checked;
        if (styleContainer) {
            styleContainer.style.display = isEnabled ? 'block' : 'none';
        }
        if (tracklistContainer) {
            tracklistContainer.style.display = isEnabled ? 'block' : 'none';
        }
        currentGiftSettings.gift_flow_enabled = isEnabled;
    });

    // Handle unwrap style selection
    document.querySelectorAll('input[name="gift-style"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentGiftSettings.unwrap_style = this.value;
        });
    });

    // Handle tracklist toggle
    const tracklistToggle = document.getElementById('show-tracklist-after-completion');
    tracklistToggle?.addEventListener('change', function() {
        currentGiftSettings.show_tracklist_after_completion = this.checked;
    });

    // Handle creator name input
    const creatorNameInput = document.getElementById('gift-creator-name');
    creatorNameInput?.addEventListener('input', function() {
        currentGiftSettings.creator_name = this.value.trim();
    });

    // Handle "Save as default" functionality
    saveDefaultCheckbox?.addEventListener('change', async function() {
        if (!this.checked) return;

        const creatorName = creatorNameInput?.value.trim() || '';

        try {
            const response = await fetch('/editor/preferences', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    creator_name: creatorName,
                    default_gift_flow_enabled: giftFlowToggle?.checked || false,
                    default_unwrap_style: currentGiftSettings.unwrap_style,
                    default_show_tracklist: tracklistToggle?.checked ?? true
                })
            });

            if (response.ok) {
                // Visual feedback
                const originalText = this.nextElementSibling.textContent;
                this.nextElementSibling.textContent = '✓ Saved as default';
                this.nextElementSibling.classList.add('text-success');

                setTimeout(() => {
                    this.nextElementSibling.textContent = originalText;
                    this.nextElementSibling.classList.remove('text-success');
                    this.checked = false;
                }, 2000);
            }
        } catch (error) {
            console.error('Failed to save default preferences:', error);
        }
    });

    // Handle preview button
    previewBtn?.addEventListener('click', openPreview);

    // Handle gift button click to open modal
    giftBtn?.addEventListener('click', () => {
        showGiftSettingsModal();
    });

    // Auto-show modal for new mixtapes (once per session)
    autoShowForNewMixtape();
}

/**
 * Load initial settings from preloaded mixtape or preferences
 */
function loadInitialSettings() {
    const preload = window.PRELOADED_MIXTAPE || {};

    // Load creator name
    currentGiftSettings.creator_name = preload.creator_name || '';
    const creatorNameInput = document.getElementById('gift-creator-name');
    if (creatorNameInput) {
        creatorNameInput.value = currentGiftSettings.creator_name;
    }

    // Load gift flow enabled
    currentGiftSettings.gift_flow_enabled = preload.gift_flow_enabled || false;
    const giftFlowToggle = document.getElementById('gift-flow-enabled');
    if (giftFlowToggle) {
        giftFlowToggle.checked = currentGiftSettings.gift_flow_enabled;

        // Show/hide dependent sections
        const styleContainer = document.getElementById('gift-style-container');
        const tracklistContainer = document.getElementById('tracklist-setting-container');
        if (currentGiftSettings.gift_flow_enabled) {
            if (styleContainer) styleContainer.style.display = 'block';
            if (tracklistContainer) tracklistContainer.style.display = 'block';
        }
    }

    // Load unwrap style
    currentGiftSettings.unwrap_style = preload.unwrap_style || 'playful';
    const styleRadio = document.getElementById(`style-${currentGiftSettings.unwrap_style}`);
    if (styleRadio) {
        styleRadio.checked = true;
    }

    // Load show tracklist
    currentGiftSettings.show_tracklist_after_completion = 
        preload.show_tracklist_after_completion !== undefined 
            ? preload.show_tracklist_after_completion 
            : true;
    const tracklistToggle = document.getElementById('show-tracklist-after-completion');
    if (tracklistToggle) {
        tracklistToggle.checked = currentGiftSettings.show_tracklist_after_completion;
    }
}

/**
 * Auto-show modal for new mixtapes (not when editing existing ones)
 */
function autoShowForNewMixtape() {
    const preload = window.PRELOADED_MIXTAPE || {};
    const isNewMixtape = !preload.slug;

    // Only auto-show once per session for new mixtapes
    if (isNewMixtape && !sessionStorage.getItem('giftSettingsShown')) {
        setTimeout(() => {
            const modal = bootstrap.Modal.getOrCreateInstance(
                document.getElementById('giftSettingsModal')
            );
            modal.show();
            sessionStorage.setItem('giftSettingsShown', 'true');
        }, 800);
    }
}

/**
 * Open preview window with selected unwrap style
 */
function openPreview() {
    const style = currentGiftSettings.unwrap_style;
    const previewUrl = `/static/mockups/mockup-${style}.html`;
    
    // Open in new window with appropriate size
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
 * Get current gift settings for save payload
 * @returns {Object} Current gift settings
 */
export function getGiftSettings() {
    return { ...currentGiftSettings };
}

/**
 * Programmatically show the gift settings modal
 */
export function showGiftSettingsModal() {
    const modal = bootstrap.Modal.getOrCreateInstance(
        document.getElementById('giftSettingsModal')
    );
    modal.show();
}

/**
 * Update gift settings from external source
 * @param {Object} settings - Settings to update
 */
export function updateGiftSettings(settings) {
    if (settings.creator_name !== undefined) {
        currentGiftSettings.creator_name = settings.creator_name;
        const input = document.getElementById('gift-creator-name');
        if (input) input.value = settings.creator_name;
    }

    if (settings.gift_flow_enabled !== undefined) {
        currentGiftSettings.gift_flow_enabled = settings.gift_flow_enabled;
        const toggle = document.getElementById('gift-flow-enabled');
        if (toggle) toggle.checked = settings.gift_flow_enabled;
    }

    if (settings.unwrap_style !== undefined) {
        currentGiftSettings.unwrap_style = settings.unwrap_style;
        const radio = document.getElementById(`style-${settings.unwrap_style}`);
        if (radio) radio.checked = true;
    }

    if (settings.show_tracklist_after_completion !== undefined) {
        currentGiftSettings.show_tracklist_after_completion = settings.show_tracklist_after_completion;
        const toggle = document.getElementById('show-tracklist-after-completion');
        if (toggle) toggle.checked = settings.show_tracklist_after_completion;
    }
}

// Export to window for access from qrShare module
window.getGiftSettings = getGiftSettings;
