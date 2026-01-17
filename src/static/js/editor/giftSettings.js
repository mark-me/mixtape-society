// static/js/editor/giftSettings.js

let giftSettingsModal = null;
let currentGiftSettings = {
    creator_name: '',
    gift_flow_enabled: false,
    show_tracklist_after_completion: true
};

/**
 * Initialize gift settings UI and modal
 */
export function initGiftSettings() {
    // Get modal instance
    const modalElement = document.getElementById('giftSettingsModal');
    if (!modalElement) {
        console.error('Gift settings modal not found');
        return;
    }
    
    giftSettingsModal = new bootstrap.Modal(modalElement);
    
    // Wire up event listeners
    setupEventListeners();
    
    // Load initial values from PRELOADED_MIXTAPE
    loadInitialValues();
    
    // Auto-show for new mixtapes (only once per session)
    autoShowForNewMixtape();
}

/**
 * Setup event listeners for gift settings controls
 */
function setupEventListeners() {
    // Gift flow enabled toggle
    const giftFlowToggle = document.getElementById('gift-flow-enabled');
    const tracklistContainer = document.getElementById('tracklist-setting-container');
    
    if (giftFlowToggle) {
        giftFlowToggle.addEventListener('change', (e) => {
            // Show/hide tracklist setting based on gift flow toggle
            if (tracklistContainer) {
                tracklistContainer.style.display = e.target.checked ? 'block' : 'none';
            }
            updateCurrentSettings();
        });
    }
    
    // Creator name input
    const creatorNameInput = document.getElementById('gift-creator-name');
    if (creatorNameInput) {
        creatorNameInput.addEventListener('input', updateCurrentSettings);
    }
    
    // Show tracklist toggle
    const showTracklistToggle = document.getElementById('show-tracklist-after-completion');
    if (showTracklistToggle) {
        showTracklistToggle.addEventListener('change', updateCurrentSettings);
    }
    
    // Save as default checkbox
    const saveDefaultCheckbox = document.getElementById('save-creator-name-default');
    if (saveDefaultCheckbox) {
        saveDefaultCheckbox.addEventListener('change', async (e) => {
            if (e.target.checked) {
                await saveCreatorNameAsDefault();
            }
        });
    }
    
    // Open modal button
    const giftSettingsBtn = document.getElementById('gift-settings-btn');
    if (giftSettingsBtn) {
        giftSettingsBtn.addEventListener('click', () => {
            showGiftSettingsModal();
        });
    }
}

/**
 * Load initial values from PRELOADED_MIXTAPE and set form fields
 */
function loadInitialValues() {
    const preload = window.PRELOADED_MIXTAPE || {};
    
    // Set creator name
    const creatorNameInput = document.getElementById('gift-creator-name');
    if (creatorNameInput) {
        creatorNameInput.value = preload.creator_name || '';
    }
    
    // Set gift flow enabled
    const giftFlowToggle = document.getElementById('gift-flow-enabled');
    if (giftFlowToggle) {
        giftFlowToggle.checked = preload.gift_flow_enabled || false;
        
        // Show/hide tracklist setting
        const tracklistContainer = document.getElementById('tracklist-setting-container');
        if (tracklistContainer) {
            tracklistContainer.style.display = giftFlowToggle.checked ? 'block' : 'none';
        }
    }
    
    // Set show tracklist
    const showTracklistToggle = document.getElementById('show-tracklist-after-completion');
    if (showTracklistToggle) {
        showTracklistToggle.checked = preload.show_tracklist_after_completion !== false; // Default true
    }
    
    // Update current settings object
    updateCurrentSettings();
}

/**
 * Update current settings object from form values
 */
function updateCurrentSettings() {
    const creatorNameInput = document.getElementById('gift-creator-name');
    const giftFlowToggle = document.getElementById('gift-flow-enabled');
    const showTracklistToggle = document.getElementById('show-tracklist-after-completion');
    
    currentGiftSettings = {
        creator_name: creatorNameInput?.value?.trim() || '',
        gift_flow_enabled: giftFlowToggle?.checked || false,
        show_tracklist_after_completion: showTracklistToggle?.checked !== false
    };
}

/**
 * Get current gift settings for inclusion in save payload
 */
export function getGiftSettings() {
    updateCurrentSettings();
    return { ...currentGiftSettings };
}

/**
 * Save creator name as default preference
 */
async function saveCreatorNameAsDefault() {
    const creatorNameInput = document.getElementById('gift-creator-name');
    const creatorName = creatorNameInput?.value?.trim() || '';
    
    try {
        const response = await fetch('/editor/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                creator_name: creatorName
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save preferences');
        }
        
        console.log('Creator name saved as default:', creatorName);
        
        // Show brief success feedback
        const checkbox = document.getElementById('save-creator-name-default');
        const label = checkbox?.nextElementSibling;
        if (label) {
            const originalText = label.textContent;
            label.textContent = '✓ Saved as default';
            label.classList.add('text-success');
            
            setTimeout(() => {
                label.textContent = originalText;
                label.classList.remove('text-success');
            }, 2000);
        }
    } catch (error) {
        console.error('Error saving creator name preference:', error);
        
        // Uncheck the checkbox on error
        const checkbox = document.getElementById('save-creator-name-default');
        if (checkbox) {
            checkbox.checked = false;
        }
    }
}

/**
 * Show the gift settings modal
 */
export function showGiftSettingsModal() {
    if (giftSettingsModal) {
        giftSettingsModal.show();
    }
}

/**
 * Auto-show modal for new mixtapes (only once per session)
 */
function autoShowForNewMixtape() {
    const preload = window.PRELOADED_MIXTAPE || {};
    const isNewMixtape = !preload.slug;
    
    // Check if we've already shown it this session
    const hasShownGiftSettings = sessionStorage.getItem('giftSettingsShown');
    
    if (isNewMixtape && !hasShownGiftSettings) {
        // Wait a bit for the page to fully load
        setTimeout(() => {
            showGiftSettingsModal();
            sessionStorage.setItem('giftSettingsShown', 'true');
        }, 800);
    }
}

/**
 * Update gift settings from external source (e.g., after loading preferences)
 */
export function updateGiftSettings(settings) {
    if (settings.creator_name !== undefined) {
        const creatorNameInput = document.getElementById('gift-creator-name');
        if (creatorNameInput) {
            creatorNameInput.value = settings.creator_name;
        }
    }
    
    if (settings.gift_flow_enabled !== undefined) {
        const giftFlowToggle = document.getElementById('gift-flow-enabled');
        if (giftFlowToggle) {
            giftFlowToggle.checked = settings.gift_flow_enabled;
            
            // Update tracklist container visibility
            const tracklistContainer = document.getElementById('tracklist-setting-container');
            if (tracklistContainer) {
                tracklistContainer.style.display = settings.gift_flow_enabled ? 'block' : 'none';
            }
        }
    }
    
    if (settings.show_tracklist_after_completion !== undefined) {
        const showTracklistToggle = document.getElementById('show-tracklist-after-completion');
        if (showTracklistToggle) {
            showTracklistToggle.checked = settings.show_tracklist_after_completion;
        }
    }
    
    updateCurrentSettings();
}
