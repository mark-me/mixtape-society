// static/js/common/toastSystem.js

/**
 * Toast Queue System - Centralized Implementation
 * 
 * A comprehensive toast notification system with:
 * - Queue management (multiple toasts don't replace each other)
 * - Different toast types (success, info, warning, error)
 * - Action buttons support
 * - Auto-hide and manual dismiss
 * - Programmatic control
 * - Clean animations
 * 
 * Used across all pages: browser, editor, player, and common utilities
 */

// Toast notification system constants
const TOAST_TYPES = {
    SUCCESS: 'success',
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'error'
};

const TOAST_CONFIG = {
    [TOAST_TYPES.SUCCESS]: {
        icon: 'bi-check-circle-fill',
        bgClass: 'bg-success',
        textClass: 'text-white',
        duration: 3000
    },
    [TOAST_TYPES.INFO]: {
        icon: 'bi-info-circle-fill',
        bgClass: 'bg-info',
        textClass: 'text-white',
        duration: 4000
    },
    [TOAST_TYPES.WARNING]: {
        icon: 'bi-exclamation-circle-fill',
        bgClass: 'bg-warning',
        textClass: 'text-dark',
        duration: 5000
    },
    [TOAST_TYPES.ERROR]: {
        icon: 'bi-exclamation-triangle-fill',
        bgClass: 'bg-danger',
        textClass: 'text-white',
        duration: 8000,
        autohide: false
    }
};

// Toast queue management
let toastQueue = [];
let currentToast = null;
let toastIdCounter = 0;

/**
 * Show a toast notification with queue support
 * 
 * @param {string} message - Message to display
 * @param {Object} options - Configuration
 * @param {string} options.type - Toast type: 'success', 'info', 'warning', 'error'
 * @param {number} options.duration - Duration in ms (default: based on type)
 * @param {boolean} options.autohide - Whether to auto-hide (default: true for non-errors)
 * @param {Array} options.actions - Array of action buttons: [{ label, handler, primary }]
 * @returns {Object} Toast control object with dismiss() method
 */
export function showToast(message, options = {}) {
    const {
        type = TOAST_TYPES.INFO,
        duration,
        autohide,
        actions = []
    } = options;

    const config = TOAST_CONFIG[type] || TOAST_CONFIG[TOAST_TYPES.INFO];
    const toastDuration = duration !== undefined ? duration : config.duration;
    const shouldAutohide = autohide !== undefined ? autohide : (config.autohide !== false);

    const toastId = ++toastIdCounter;
    
    const toastData = {
        id: toastId,
        message,
        type,
        config,
        duration: toastDuration,
        autohide: shouldAutohide,
        actions,
        element: null,
        timeoutId: null
    };

    // Add to queue
    toastQueue.push(toastData);

    // Process queue if no toast is currently showing
    if (!currentToast) {
        processToastQueue();
    }

    // Return control object
    return {
        dismiss: () => dismissToast(toastId)
    };
}

/**
 * Process the toast queue - show next toast
 */
function processToastQueue() {
    if (toastQueue.length === 0) {
        currentToast = null;
        return;
    }

    const toastData = toastQueue.shift();
    currentToast = toastData;

    displayToast(toastData);
}

/**
 * Display a single toast
 */
function displayToast(toastData) {
    const containerId = 'toast-container';
    let container = document.getElementById(containerId);

    if (!container) {
        container = document.createElement('div');
        container.id = containerId;
        container.style.position = 'fixed';
        container.style.bottom = '20px';
        container.style.right = '20px';
        container.style.zIndex = '1060';
        container.style.maxWidth = '400px';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast show ${toastData.config.bgClass}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.style.minWidth = '300px';

    const toastHeader = document.createElement('div');
    toastHeader.className = `toast-header ${toastData.config.bgClass} ${toastData.config.textClass} border-0`;

    // Icon
    const icon = document.createElement('i');
    icon.className = `bi ${toastData.config.icon} me-2`;
    toastHeader.appendChild(icon);

    // Type label
    const typeLabel = document.createElement('strong');
    typeLabel.className = 'me-auto';
    typeLabel.textContent = toastData.type.charAt(0).toUpperCase() + toastData.type.slice(1);
    toastHeader.appendChild(typeLabel);

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    if (toastData.config.textClass === 'text-white') {
        closeBtn.className += ' btn-close-white';
    }
    closeBtn.setAttribute('aria-label', 'Close');
    closeBtn.onclick = () => dismissToast(toastData.id);
    toastHeader.appendChild(closeBtn);

    toast.appendChild(toastHeader);

    // Toast body
    const toastBody = document.createElement('div');
    toastBody.className = `toast-body ${toastData.config.textClass}`;
    toastBody.textContent = toastData.message;
    toast.appendChild(toastBody);

    // Action buttons
    if (toastData.actions && toastData.actions.length > 0) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'd-flex gap-2 mt-2 px-3 pb-2';

        toastData.actions.forEach(action => {
            const btn = document.createElement('button');
            btn.className = action.primary ? 'btn btn-sm btn-light' : 'btn btn-sm btn-outline-light';
            btn.textContent = action.label;
            btn.onclick = () => {
                if (action.handler) action.handler();
                dismissToast(toastData.id);
            };
            actionsDiv.appendChild(btn);
        });

        toast.appendChild(actionsDiv);
    }

    toastData.element = toast;
    container.appendChild(toast);

    // Auto-hide
    if (toastData.autohide && toastData.duration > 0) {
        toastData.timeoutId = setTimeout(() => {
            dismissToast(toastData.id);
        }, toastData.duration);
    }
}

/**
 * Dismiss a toast by ID
 */
function dismissToast(toastId) {
    if (currentToast && currentToast.id === toastId) {
        if (currentToast.timeoutId) {
            clearTimeout(currentToast.timeoutId);
        }

        if (currentToast.element) {
            currentToast.element.classList.remove('show');
            currentToast.element.classList.add('hide');

            setTimeout(() => {
                if (currentToast.element && currentToast.element.parentElement) {
                    currentToast.element.remove();
                }
                // Process next toast in queue
                processToastQueue();
            }, 150);
        } else {
            processToastQueue();
        }

        currentToast = null;
    } else {
        // Remove from queue if not current
        const index = toastQueue.findIndex(t => t.id === toastId);
        if (index !== -1) {
            toastQueue.splice(index, 1);
        }
    }
}

/**
 * Convenience functions for different toast types
 */
export function showSuccessToast(message, options = {}) {
    return showToast(message, { ...options, type: TOAST_TYPES.SUCCESS });
}

export function showInfoToast(message, options = {}) {
    return showToast(message, { ...options, type: TOAST_TYPES.INFO });
}

export function showWarningToast(message, options = {}) {
    return showToast(message, { ...options, type: TOAST_TYPES.WARNING });
}

export function showErrorToast(message, options = {}) {
    return showToast(message, { ...options, type: TOAST_TYPES.ERROR });
}

/**
 * Compatibility wrapper for existing showPlaybackErrorToast calls
 * Maps old API to new toast system
 * 
 * @param {string} message - Error message
 * @param {Object} options
 * @param {boolean} options.isTerminal - If true, toast won't auto-hide
 * @param {Function} options.onSkip - Handler for skip button
 * @returns {Object} Toast control object
 */
export function showPlaybackErrorToast(message, { isTerminal = false, onSkip } = {}) {
    const actions = [];

    if (isTerminal && onSkip) {
        actions.push({
            label: 'Skip Track',
            handler: onSkip,
            primary: true
        });
    }

    return showErrorToast(message, {
        autohide: !isTerminal,
        actions
    });
}

/**
 * Legacy compatibility: Simple toast with Bootstrap type names
 * Maps Bootstrap type names (success, danger, warning, info) to new system
 * 
 * @param {string} message - Message to display
 * @param {string} type - Bootstrap type: 'success', 'danger', 'warning', 'info'
 * @returns {Object} Toast control object
 */
export function showLegacyToast(message, type = 'success') {
    // Map Bootstrap types to new system types
    const typeMap = {
        'success': TOAST_TYPES.SUCCESS,
        'danger': TOAST_TYPES.ERROR,
        'warning': TOAST_TYPES.WARNING,
        'info': TOAST_TYPES.INFO
    };

    const mappedType = typeMap[type] || TOAST_TYPES.INFO;
    return showToast(message, { type: mappedType });
}

// Export types for consumers
export { TOAST_TYPES };
