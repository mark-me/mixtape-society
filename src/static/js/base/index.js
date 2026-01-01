// static/js/base/index.js
import { initThemeSwitcher } from './themeSwitcher.js';
import { initTooltips } from './tooltipInit.js';
import { initNavigationGuard } from "./navigationGuard.js";
import { hasUnsavedChanges } from "../editor/ui.js";

document.addEventListener('DOMContentLoaded', () => {
    initThemeSwitcher();
    initTooltips();
    // Initialise the guard, passing a function that returns the latest flag.
    initNavigationGuard(() => getUnsavedFlag());
    
    // Initialize resync functionality
    initResyncButton();
});

export function getUnsavedFlag() {
    return hasUnsavedChanges; // or whatever variable you use internally
}

/**
 * Initializes the resync button functionality.
 * Handles confirmation modal, API call, and redirect to indexing page.
 */
function initResyncButton() {
    const resyncBtn = document.getElementById('resyncBtn');
    const resyncConfirmModal = document.getElementById('resyncConfirmModal');
    const confirmResyncBtn = document.getElementById('confirmResyncBtn');
    
    if (!resyncBtn || !resyncConfirmModal || !confirmResyncBtn) {
        // Elements don't exist (user not authenticated or not on a page with resync)
        return;
    }

    // Check if indexing is already in progress and disable button if so
    if (window.isIndexing) {
        resyncBtn.disabled = true;
        resyncBtn.title = 'Indexing already in progress';
    }

    const modal = new bootstrap.Modal(resyncConfirmModal);

    // Show confirmation modal when resync button is clicked
    resyncBtn.addEventListener('click', () => {
        modal.show();
    });

    // Handle confirmation
    confirmResyncBtn.addEventListener('click', async () => {
        // Disable button to prevent double-clicks
        confirmResyncBtn.disabled = true;
        confirmResyncBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Starting...';

        try {
            const response = await fetch('/resync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                // Close modal and redirect to indexing page
                modal.hide();
                window.location.href = '/';
            } else {
                // Show error message
                alert('Error starting resync: ' + (data.error || 'Unknown error'));
                confirmResyncBtn.disabled = false;
                confirmResyncBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Start Resync';
            }
        } catch (error) {
            console.error('Error triggering resync:', error);
            alert('Failed to start resync. Please try again.');
            confirmResyncBtn.disabled = false;
            confirmResyncBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Start Resync';
        }
    });

    // Reset button state when modal is closed
    resyncConfirmModal.addEventListener('hidden.bs.modal', () => {
        confirmResyncBtn.disabled = false;
        confirmResyncBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Start Resync';
    });
}
