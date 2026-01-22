/**
 * Toast Queue System - Comprehensive Implementation
 * 
 * This is a complete toast notification system with:
 * - Queue management (multiple toasts don't replace each other)
 * - Different toast types (success, info, warning, error)
 * - Action buttons support
 * - Auto-hide and manual dismiss
 * - Proper cleanup
 * 
 * INSERT THIS CODE after the prefetch event listener, before the error handler
 * REPLACE both existing showPlaybackErrorToast function definitions
 */

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
const showToast = (message, options = {}) => {
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
};

/**
 * Process the toast queue - show next toast
 */
const processToastQueue = () => {
    if (toastQueue.length === 0) {
        currentToast = null;
        return;
    }

    const toastData = toastQueue.shift();
    currentToast = toastData;

    displayToast(toastData);
};

/**
 * Display a single toast
 */
const displayToast = (toastData) => {
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
};

/**
 * Dismiss a toast by ID
 */
const dismissToast = (toastId) => {
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
};

/**
 * Convenience functions for different toast types
 */
const showSuccessToast = (message, options = {}) => {
    return showToast(message, { ...options, type: TOAST_TYPES.SUCCESS });
};

const showInfoToast = (message, options = {}) => {
    return showToast(message, { ...options, type: TOAST_TYPES.INFO });
};

const showWarningToast = (message, options = {}) => {
    return showToast(message, { ...options, type: TOAST_TYPES.WARNING });
};

const showErrorToast = (message, options = {}) => {
    return showToast(message, { ...options, type: TOAST_TYPES.ERROR });
};

/**
 * Compatibility wrapper for existing showPlaybackErrorToast calls
 * Maps old API to new toast system
 */
const showPlaybackErrorToast = (message, { isTerminal = false, onSkip } = {}) => {
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
};

/* 
 * USAGE EXAMPLES:
 * 
 * // Simple success toast
 * showSuccessToast('Track added to queue');
 * 
 * // Info toast with custom duration
 * showInfoToast('Buffering track...', { duration: 2000 });
 * 
 * // Warning toast
 * showWarningToast('Slow network detected');
 * 
 * // Error toast with action button
 * showErrorToast('Playback failed', {
 *     autohide: false,
 *     actions: [
 *         { label: 'Retry', handler: () => retry(), primary: true },
 *         { label: 'Skip', handler: () => skip() }
 *     ]
 * });
 * 
 * // Using convenience wrapper (backward compatible)
 * showPlaybackErrorToast('Unable to play track', {
 *     isTerminal: true,
 *     onSkip: () => playNextTrack()
 * });
 * 
 * // Programmatic dismiss
 * const toast = showErrorToast('Critical error');
 * setTimeout(() => toast.dismiss(), 3000);
 */
