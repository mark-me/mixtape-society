// static/js/editor/collectionSelector.js
/**
 * Collection Selector Module
 * 
 * Manages collection selection in the mixtape editor.
 * Handles:
 * - Collection dropdown initialization
 * - Collection locking after first track
 * - Collection info display
 * - Integration with search and playlist
 */

let selectedCollectionId = null;
let selectedCollectionName = null;
let collectionLocked = false;
let hasMultipleCollections = false;

/**
 * Initialize the collection selector
 * Auto-selects if only one collection, otherwise requires user selection
 */
export function initCollectionSelector() {
    const collectionSelect = document.getElementById('collectionSelect');
    const searchInput = document.getElementById('searchInput');
    const selectedInfo = document.getElementById('selectedCollectionInfo');
    
    // Check if we have collection selector (multiple collections)
    if (!collectionSelect) {
        // Single collection mode - auto-select default
        selectedCollectionId = document.body.dataset.defaultCollection || 'main';
        selectedCollectionName = document.body.dataset.defaultCollectionName || 'Main Collection';
        hasMultipleCollections = false;
        
        console.log('Single collection mode:', selectedCollectionId);
        return;
    }
    
    hasMultipleCollections = true;
    console.log('Multiple collections mode');
    
    // Handle collection selection
    collectionSelect.addEventListener('change', handleCollectionChange);
    
    // Handle "Change Collection" button (before locked)
    const changeBtn = document.getElementById('changeCollection');
    if (changeBtn) {
        changeBtn.addEventListener('click', () => {
            if (!collectionLocked) {
                collectionSelect.disabled = false;
                collectionSelect.focus();
                changeBtn.style.display = 'none';
            }
        });
    }
    
    // Check if editing existing mixtape (collection pre-selected)
    const editingMixtape = document.body.dataset.editingMixtape === 'true';
    const preselectedCollection = document.body.dataset.mixtapeCollection;
    
    if (editingMixtape && preselectedCollection) {
        // Editing mode - pre-select and lock collection
        collectionSelect.value = preselectedCollection;
        collectionSelect.dispatchEvent(new Event('change'));
        lockCollection();
        console.log('Editing mode: locked to', preselectedCollection);
    }
}

/**
 * Handle collection dropdown change
 */
function handleCollectionChange(e) {
    const collectionSelect = e.target;
    selectedCollectionId = collectionSelect.value;
    const option = collectionSelect.selectedOptions[0];
    
    if (!option) return;
    
    selectedCollectionName = option.dataset.name;
    const trackCount = option.dataset.trackCount;
    const artistCount = option.dataset.artistCount;
    
    // Update collection info display
    const nameDisplay = document.getElementById('selectedCollectionName');
    const statsDisplay = document.getElementById('selectedCollectionStats');
    const selectedInfo = document.getElementById('selectedCollectionInfo');
    
    if (nameDisplay) {
        nameDisplay.textContent = selectedCollectionName;
    }
    
    if (statsDisplay) {
        statsDisplay.textContent = `${trackCount} tracks, ${artistCount} artists`;
    }
    
    if (selectedInfo) {
        selectedInfo.style.display = 'block';
    }
    
    // Show change button
    const changeBtn = document.getElementById('changeCollection');
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
    
    console.log('Collection selected:', selectedCollectionId, selectedCollectionName);
    
    // Dispatch custom event for other modules
    document.dispatchEvent(new CustomEvent('collectionSelected', {
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
    if (collectionLocked) return;
    
    collectionLocked = true;
    console.log('Collection locked:', selectedCollectionId);
    
    // Disable collection selector
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        collectionSelect.disabled = true;
    }
    
    // Hide change button
    const changeBtn = document.getElementById('changeCollection');
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
    
    // Dispatch lock event
    document.dispatchEvent(new CustomEvent('collectionLocked', {
        detail: {
            id: selectedCollectionId,
            name: selectedCollectionName
        }
    }));
}

/**
 * Unlock collection (used when all tracks are removed)
 */
export function unlockCollection() {
    if (!collectionLocked || hasMultipleCollections === false) return;
    
    collectionLocked = false;
    console.log('Collection unlocked');
    
    // Enable collection selector
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        collectionSelect.disabled = false;
    }
    
    // Show change button
    const changeBtn = document.getElementById('changeCollection');
    if (changeBtn) {
        changeBtn.style.display = 'inline-block';
    }
    
    // Hide lock notice
    const lockNotice = document.getElementById('collectionLockNotice');
    if (lockNotice) {
        lockNotice.style.display = 'none';
    }
    
    // Dispatch unlock event
    document.dispatchEvent(new CustomEvent('collectionUnlocked'));
}

/**
 * Get the currently selected collection ID
 */
export function getSelectedCollectionId() {
    return selectedCollectionId;
}

/**
 * Get the currently selected collection name
 */
export function getSelectedCollectionName() {
    return selectedCollectionName;
}

/**
 * Check if collection is locked
 */
export function isCollectionLocked() {
    return collectionLocked;
}

/**
 * Check if in multi-collection mode
 */
export function hasMultipleCollectionsAvailable() {
    return hasMultipleCollections;
}

/**
 * Set collection (programmatically)
 * Used when loading existing mixtape
 */
export function setCollection(collectionId, collectionName) {
    selectedCollectionId = collectionId;
    selectedCollectionName = collectionName;
    
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect && collectionSelect.querySelector(`option[value="${collectionId}"]`)) {
        collectionSelect.value = collectionId;
        collectionSelect.dispatchEvent(new Event('change'));
    }
}
