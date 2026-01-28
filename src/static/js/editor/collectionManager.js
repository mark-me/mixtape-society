// static/js/editor/collectionManager.js
/**
 * Collection Manager Module
 * 
 * Manages collection selection, locking, and state in the mixtape editor.
 * Provides a simple API for other modules to interact with collection state.
 */

let selectedCollectionId = null;
let selectedCollectionName = null;
let collectionLocked = false;
let hasMultipleCollections = false;
let editingMode = false;

/**
 * Initialize the collection manager
 * 
 * @param {Object} config - Configuration object
 * @param {string} config.defaultCollectionId - Default or preselected collection ID
 * @param {string} config.defaultCollectionName - Default collection name
 * @param {boolean} config.hasMultiple - Whether there are multiple collections
 * @param {boolean} config.isEditing - Whether editing an existing mixtape
 * @param {boolean} config.shouldLock - Whether to immediately lock the collection
 */
export function initCollectionManager(config = {}) {
    selectedCollectionId = config.defaultCollectionId || null;
    selectedCollectionName = config.defaultCollectionName || null;
    hasMultipleCollections = config.hasMultiple || false;
    editingMode = config.isEditing || false;
    collectionLocked = config.shouldLock || false;
    
    console.log('Collection Manager initialized:', {
        selectedCollectionId,
        selectedCollectionName,
        hasMultipleCollections,
        editingMode,
        collectionLocked
    });
    
    if (hasMultipleCollections) {
        initCollectionSelector();
    }
}

/**
 * Initialize collection selector UI
 */
function initCollectionSelector() {
    const collectionSelect = document.getElementById('collectionSelect');
    const searchInput = document.getElementById('searchInput');
    
    if (!collectionSelect) {
        console.warn('Collection selector not found');
        return;
    }
    
    // Handle collection selection change
    collectionSelect.addEventListener('change', handleCollectionChange);
    
    // Handle "Change Collection" button
    const changeBtn = document.getElementById('changeCollectionBtn');
    if (changeBtn) {
        changeBtn.addEventListener('click', () => {
            if (!collectionLocked) {
                collectionSelect.disabled = false;
                collectionSelect.focus();
                changeBtn.style.display = 'none';
            }
        });
    }
    
    // If collection is already selected (editing or preloaded), enable search
    if (selectedCollectionId && searchInput) {
        searchInput.disabled = false;
        searchInput.placeholder = 'Search your music...';
    }
    
    // If locked (editing mode), show lock UI
    if (collectionLocked) {
        showLockUI();
    }
}

/**
 * Handle collection dropdown change
 */
function handleCollectionChange(e) {
    const option = e.target.selectedOptions[0];
    if (!option) return;
    
    selectedCollectionId = e.target.value;
    selectedCollectionName = option.dataset.name;
    
    console.log('Collection changed:', selectedCollectionId, selectedCollectionName);
    
    // Update info display
    const nameDisplay = document.getElementById('selectedCollectionName');
    const statsDisplay = document.getElementById('selectedCollectionStats');
    const selectedInfo = document.getElementById('selectedCollectionInfo');
    
    if (nameDisplay) {
        nameDisplay.textContent = selectedCollectionName;
    }
    
    if (statsDisplay) {
        const trackCount = option.dataset.trackCount;
        const artistCount = option.dataset.artistCount;
        statsDisplay.textContent = `${trackCount} tracks, ${artistCount} artists`;
    }
    
    if (selectedInfo) {
        selectedInfo.style.display = 'block';
    }
    
    // Show change button (if not locked)
    const changeBtn = document.getElementById('changeCollectionBtn');
    if (changeBtn && !collectionLocked) {
        changeBtn.style.display = 'inline-block';
    }
    
    // Enable search
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.disabled = false;
        searchInput.placeholder = 'Search your music...';
        searchInput.focus();
    }
    
    // Update hidden field
    const hiddenField = document.getElementById('mixtapeCollectionId');
    if (hiddenField) {
        hiddenField.value = selectedCollectionId;
    }
    
    // Dispatch custom event
    document.dispatchEvent(new CustomEvent('collectionChanged', {
        detail: {
            id: selectedCollectionId,
            name: selectedCollectionName
        }
    }));
}

/**
 * Lock the collection (called when first track is added)
 */
export function lockCollection() {
    if (collectionLocked || !hasMultipleCollections) {
        return;
    }
    
    collectionLocked = true;
    console.log('Collection locked:', selectedCollectionId);
    
    showLockUI();
    
    // Dispatch custom event
    document.dispatchEvent(new CustomEvent('collectionLocked', {
        detail: {
            id: selectedCollectionId,
            name: selectedCollectionName
        }
    }));
}

/**
 * Show lock UI elements
 */
function showLockUI() {
    // Disable collection selector
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        collectionSelect.disabled = true;
        collectionSelect.classList.add('collection-locked');
    }
    
    // Hide change button
    const changeBtn = document.getElementById('changeCollectionBtn');
    if (changeBtn) {
        changeBtn.style.display = 'none';
    }
    
    // Show lock notice
    const lockNotice = document.getElementById('collectionLockNotice');
    const lockedNameDisplay = document.getElementById('lockedCollectionName');
    
    if (lockNotice && lockedNameDisplay) {
        lockedNameDisplay.textContent = selectedCollectionName || selectedCollectionId;
        lockNotice.style.display = 'block';
    }
}

/**
 * Unlock the collection (called when all tracks are removed)
 */
export function unlockCollection() {
    if (!collectionLocked || !hasMultipleCollections || editingMode) {
        return;
    }
    
    collectionLocked = false;
    console.log('Collection unlocked');
    
    // Enable collection selector
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        collectionSelect.disabled = false;
        collectionSelect.classList.remove('collection-locked');
    }
    
    // Show change button
    const changeBtn = document.getElementById('changeCollectionBtn');
    if (changeBtn) {
        changeBtn.style.display = 'inline-block';
    }
    
    // Hide lock notice
    const lockNotice = document.getElementById('collectionLockNotice');
    if (lockNotice) {
        lockNotice.style.display = 'none';
    }
    
    // Dispatch custom event
    document.dispatchEvent(new CustomEvent('collectionUnlocked'));
}

/**
 * Get the currently selected collection ID
 * @returns {string|null} Collection ID or null if none selected
 */
export function getSelectedCollectionId() {
    return selectedCollectionId;
}

/**
 * Get the currently selected collection name
 * @returns {string|null} Collection name or null if none selected
 */
export function getSelectedCollectionName() {
    return selectedCollectionName;
}

/**
 * Check if collection is locked
 * @returns {boolean} True if locked
 */
export function isCollectionLocked() {
    return collectionLocked;
}

/**
 * Check if in multi-collection mode
 * @returns {boolean} True if multiple collections available
 */
export function hasMultipleCollectionsAvailable() {
    return hasMultipleCollections;
}

/**
 * Check if in editing mode
 * @returns {boolean} True if editing existing mixtape
 */
export function isEditingMode() {
    return editingMode;
}

/**
 * Set collection ID programmatically
 * Used when loading existing mixtape data
 * 
 * @param {string} collectionId - Collection ID to set
 * @param {string} collectionName - Collection name to set
 */
export function setCollection(collectionId, collectionName) {
    selectedCollectionId = collectionId;
    selectedCollectionName = collectionName;
    
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        const option = collectionSelect.querySelector(`option[value="${collectionId}"]`);
        if (option) {
            collectionSelect.value = collectionId;
            collectionSelect.dispatchEvent(new Event('change'));
        }
    }
    
    console.log('Collection set programmatically:', collectionId, collectionName);
}

// Export as default for convenience
export default {
    init: initCollectionManager,
    getSelectedCollectionId,
    getSelectedCollectionName,
    isCollectionLocked,
    hasMultipleCollectionsAvailable,
    isEditingMode,
    lockCollection,
    unlockCollection,
    setCollection
};
