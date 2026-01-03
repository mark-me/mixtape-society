// static/js/base/databaseCorruption.js
/**
 * Handles database corruption detection and recovery UI.
 * Shows modals when corruption is detected and manages the reset process.
 */

let corruptionModal;
let confirmResetModal;

/**
 * Initializes the database corruption detection and recovery system.
 * Sets up modal instances and global fetch wrapper.
 */
export function initDatabaseCorruption() {
    // Initialize Bootstrap modals
    const corruptionModalEl = document.getElementById('corruptionModal');
    const confirmResetModalEl = document.getElementById('confirmResetModal');
    
    if (corruptionModalEl) {
        corruptionModal = new bootstrap.Modal(corruptionModalEl, {
            backdrop: 'static',
            keyboard: false
        });
    }
    
    if (confirmResetModalEl) {
        confirmResetModal = new bootstrap.Modal(confirmResetModalEl, {
            backdrop: 'static',
            keyboard: false
        });
    }
    
    // Set up button handlers
    setupButtonHandlers();
    
    // Wrap fetch to detect corruption
    setupFetchWrapper();
    
    // Check for server-side corruption errors on page load
    checkForServerSideError();
    
    // Check database health on page load (only for authenticated users)
    if (document.body.classList.contains('authenticated')) {
        checkDatabaseHealth();
    }
    
    // Make showCorruptionModal available globally for testing/debugging
    window.showCorruptionModal = showCorruptionModal;
}

/**
 * Checks if there's a server-side corruption error displayed on the page.
 * This handles cases where the error happens during page render.
 */
function checkForServerSideError() {
    // Check if page body contains corruption error
    const bodyText = document.body.textContent || document.body.innerText;
    
    if (bodyText.includes('database_corrupted') || 
        bodyText.includes('DatabaseCorruptionError') ||
        bodyText.includes('database is corrupted')) {
        console.log('Server-side corruption error detected');
        showCorruptionModal();
    }
}

/**
 * Sets up event handlers for modal buttons.
 */
function setupButtonHandlers() {
    // First modal: Reset Database button
    const resetBtn = document.getElementById('showResetConfirmBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', showConfirmModal);
    }
    
    // Confirmation modal: Yes, Reset button
    const confirmResetBtn = document.getElementById('confirmResetBtn');
    if (confirmResetBtn) {
        confirmResetBtn.addEventListener('click', executeDatabaseReset);
    }
}

/**
 * Shows the initial corruption detection modal.
 */
export function showCorruptionModal() {
    console.log('showCorruptionModal called');
    console.log('corruptionModal instance:', corruptionModal);
    
    if (corruptionModal) {
        console.log('Showing corruption modal');
        corruptionModal.show();
    } else {
        console.error('Corruption modal not initialized!');
        // Fallback: try to show it directly
        const modalEl = document.getElementById('corruptionModal');
        console.log('Modal element:', modalEl);
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl, {
                backdrop: 'static',
                keyboard: false
            });
            modal.show();
        } else {
            console.error('Modal element not found in DOM!');
            alert('Database corruption detected. Please use the collection stats modal to reset the database.');
        }
    }
}

/**
 * Closes the corruption modal.
 */
function closeCorruptionModal() {
    if (corruptionModal) {
        corruptionModal.hide();
    }
}

/**
 * Shows the confirmation modal after user clicks "Reset Database".
 */
function showConfirmModal() {
    closeCorruptionModal();
    if (confirmResetModal) {
        confirmResetModal.show();
    }
}

/**
 * Closes the confirmation modal.
 */
function closeConfirmModal() {
    if (confirmResetModal) {
        confirmResetModal.hide();
    }
}

/**
 * Executes the database reset operation.
 * Shows loading overlay and redirects on success.
 */
async function executeDatabaseReset() {
    closeConfirmModal();
    
    // Show loading overlay
    const loadingOverlay = document.getElementById('resetLoadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
    
    try {
        const response = await fetch('/reset-database', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Redirect to home page (which will show indexing progress)
            window.location.href = '/?reset=true';
        } else {
            alert('Error resetting database: ' + (data.error || 'Unknown error'));
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error resetting database:', error);
        alert('Failed to reset database. Please try again or contact support.');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }
}

/**
 * Wraps the global fetch function to automatically detect corruption errors.
 */
function setupFetchWrapper() {
    const originalFetch = window.fetch;
    
    window.fetch = async function(...args) {
        try {
            const response = await originalFetch(...args);
            
            // Check if response indicates corruption
            if (!response.ok && response.status === 500) {
                const clone = response.clone();
                try {
                    const data = await clone.json();
                    if (data.error === 'database_corrupted' || data.requires_reset) {
                        console.log('Corruption detected in fetch response');
                        showCorruptionModal();
                    }
                } catch (e) {
                    // Not JSON or couldn't parse, continue normally
                }
            }
            
            return response;
        } catch (error) {
            throw error;
        }
    };
    
    // Also handle jQuery AJAX if it's being used
    if (window.jQuery) {
        jQuery(document).ajaxError(function(event, jqxhr, settings, thrownError) {
            if (jqxhr.status === 500) {
                try {
                    const data = JSON.parse(jqxhr.responseText);
                    if (data.error === 'database_corrupted' || data.requires_reset) {
                        console.log('Corruption detected in AJAX response');
                        showCorruptionModal();
                    }
                } catch (e) {
                    // Not JSON
                }
            }
        });
    }
    
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
        if (event.reason && event.reason.message) {
            const msg = event.reason.message.toLowerCase();
            if (msg.includes('corrupt') || msg.includes('malformed')) {
                console.log('Corruption detected in unhandled rejection');
                showCorruptionModal();
            }
        }
    });
}

/**
 * Checks database health on page load.
 * Silently fails if check cannot be performed.
 */
async function checkDatabaseHealth() {
    try {
        const response = await fetch('/check-database-health');
        const data = await response.json();
        
        if (!data.healthy && data.requires_reset) {
            showCorruptionModal();
        }
    } catch (error) {
        // Silent fail - don't bother user if health check fails
        console.error('Database health check failed:', error);
    }
}
