// static/js/base/index.js
/**
 * Main entry point for base JavaScript functionality.
 * Imports and initializes all base modules.
 */

import { initThemeSwitcher } from './themeSwitcher.js';
import { initCollectionStats } from './collectionStats.js';

// Initialize all modules when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initThemeSwitcher();
    initCollectionStats();
    
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});
