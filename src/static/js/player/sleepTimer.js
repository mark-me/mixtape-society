// static/js/player/sleepTimer.js

/**
 * Sleep Timer Module
 *
 * Features:
 * - Quick preset buttons (15, 30, 45, 60 min)
 * - Fine-grained slider control (5-120 min)
 * - Wait until track ends option
 * - Visual countdown toasts every 5 minutes
 * - Cancel/extend active timer
 * - Persistent settings (remembers last duration)
 * - Quick access button in bottom player
 */

import {
    showInfoToast,
    showSuccessToast
} from '../common/toastSystem.js';

// Storage key for persistent settings
const STORAGE_KEY_SLEEP_TIMER = 'sleep_timer_duration';

// Sleep timer state
let sleepTimerState = {
    active: false,
    endTime: null,          // When timer will end (timestamp)
    duration: 30,           // Duration in minutes (for restoration)
    waitForTrackEnd: true,  // Wait for current track to finish
    intervalId: null,       // Countdown interval
    lastNotificationTime: 0 // Last time we showed countdown toast
};

/**
 * Get saved duration from localStorage, or default to 30 minutes
 */
function getSavedDuration() {
    try {
        const saved = localStorage.getItem(STORAGE_KEY_SLEEP_TIMER);
        return saved ? parseInt(saved, 10) : 30;
    } catch (e) {
        console.warn('Failed to load sleep timer duration:', e);
        return 30;
    }
}

/**
 * Save duration to localStorage
 */
function saveDuration(minutes) {
    try {
        localStorage.setItem(STORAGE_KEY_SLEEP_TIMER, minutes.toString());
    } catch (e) {
        console.warn('Failed to save sleep timer duration:', e);
    }
}

/**
 * Format time remaining as "Xm" or "Xh Ym"
 */
function formatTimeRemaining(seconds) {
    const minutes = Math.ceil(seconds / 60);

    if (minutes < 60) {
        return `${minutes}m`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (remainingMinutes === 0) {
        return `${hours}h`;
    }

    return `${hours}h ${remainingMinutes}m`;
}

/**
 * Show countdown notification toast every 5 minutes
 */
function showCountdownNotification(secondsRemaining) {
    // Don't show notification if timer is no longer active
    if (!sleepTimerState.active) {
        return;
    }

    const minutesRemaining = Math.ceil(secondsRemaining / 60);

    // Show notification at: 60min, 30min, 15min, 10min, 5min, 1min
    const notificationPoints = [60, 30, 15, 10, 5, 1];

    if (notificationPoints.includes(minutesRemaining)) {
        const now = Date.now();
        // Prevent duplicate notifications within 30 seconds
        if (now - sleepTimerState.lastNotificationTime < 30000) {
            return;
        }

        sleepTimerState.lastNotificationTime = now;

        const message = minutesRemaining === 1
            ? 'Playback will stop in 1 minute'
            : `Playback will stop in ${formatTimeRemaining(secondsRemaining)}`;

        showInfoToast(message, {
            duration: 4000,
            actions: [
                {
                    label: 'Extend',
                    handler: () => showSleepTimerModal(),
                    primary: false
                },
                {
                    label: 'Cancel',
                    handler: () => cancelSleepTimer(),
                    primary: false
                }
            ]
        });
    }
}

/**
 * Update sleep timer button state
 */
function updateSleepTimerButton() {
    const sleepBtn = document.getElementById('sleep-timer-btn');
    if (!sleepBtn) return;

    const icon = sleepBtn.querySelector('i');

    if (sleepTimerState.active) {
        // Calculate time remaining
        const now = Date.now();
        const secondsRemaining = Math.ceil((sleepTimerState.endTime - now) / 1000);
        const timeStr = formatTimeRemaining(secondsRemaining);

        // Show as active
        sleepBtn.classList.remove('btn-outline-light');
        sleepBtn.classList.add('btn-warning');
        sleepBtn.title = `Sleep timer: ${timeStr} remaining - click to modify`;

        if (icon) {
            icon.className = 'bi bi-alarm-fill';
        }
    } else {
        // Show as inactive
        sleepBtn.classList.remove('btn-warning');
        sleepBtn.classList.add('btn-outline-light');
        sleepBtn.title = 'Set sleep timer';

        if (icon) {
            icon.className = 'bi bi-alarm';
        }
    }
}

/**
 * Start the sleep timer countdown
 */
function startCountdown() {
    // Clear any existing countdown
    if (sleepTimerState.intervalId) {
        clearInterval(sleepTimerState.intervalId);
    }

    sleepTimerState.intervalId = setInterval(() => {
        const now = Date.now();
        const secondsRemaining = Math.ceil((sleepTimerState.endTime - now) / 1000);

        if (secondsRemaining <= 0) {
            // Timer expired
            stopPlayback();
            return;
        }

        // Update button tooltip every 30 seconds
        if (secondsRemaining % 30 === 0) {
            updateSleepTimerButton();
        }

        // Show countdown notifications
        showCountdownNotification(secondsRemaining);

    }, 1000); // Check every second
}

/**
 * Stop playback when timer expires
 */
function stopPlayback() {
    console.log('⏰ Sleep timer expired - stopping playback');

    // Clear interval immediately to prevent repeated calls
    if (sleepTimerState.intervalId) {
        clearInterval(sleepTimerState.intervalId);
        sleepTimerState.intervalId = null;
    }

    const player = document.getElementById('main-player');

    if (sleepTimerState.waitForTrackEnd && player && !player.paused) {
        // Wait for track to end
        const handleEnd = () => {
            player.pause();
            cleanupSleepTimer();
            showSuccessToast('Sleep timer ended - playback stopped', { duration: 5000 });
            player.removeEventListener('ended', handleEnd);
        };

        player.addEventListener('ended', handleEnd, { once: true });

        showInfoToast('Waiting for current track to finish...', { duration: 3000 });
    } else {
        // Stop immediately
        if (player) {
            player.pause();
        }
        cleanupSleepTimer();
        showSuccessToast('Sleep timer ended - playback stopped', { duration: 5000 });
    }
}

/**
 * Cleanup sleep timer state
 */
function cleanupSleepTimer() {
    if (sleepTimerState.intervalId) {
        clearInterval(sleepTimerState.intervalId);
        sleepTimerState.intervalId = null;
    }

    sleepTimerState.active = false;
    sleepTimerState.endTime = null;
    sleepTimerState.lastNotificationTime = 0;

    updateSleepTimerButton();

    console.log('🛑 Sleep timer cleaned up');
}

/**
 * Cancel the sleep timer
 */
function cancelSleepTimer() {
    // Clear state first to prevent any race conditions
    cleanupSleepTimer();

    // Then show toast
    showInfoToast('Sleep timer cancelled', { duration: 3000 });
}

/**
 * Start the sleep timer
 */
function startSleepTimer(minutes, waitForTrackEnd) {
    // Cancel existing timer if any
    if (sleepTimerState.active) {
        cleanupSleepTimer();
    }

    // Calculate end time
    const now = Date.now();
    const durationMs = minutes * 60 * 1000;
    const endTime = now + durationMs;

    // Update state
    sleepTimerState.active = true;
    sleepTimerState.endTime = endTime;
    sleepTimerState.duration = minutes;
    sleepTimerState.waitForTrackEnd = waitForTrackEnd;
    sleepTimerState.lastNotificationTime = 0;

    // Save duration preference
    saveDuration(minutes);

    // Start countdown
    startCountdown();

    // Update UI
    updateSleepTimerButton();

    // Show confirmation
    const message = waitForTrackEnd
        ? `Sleep timer set for ${minutes} minutes (will wait for track to finish)`
        : `Sleep timer set for ${minutes} minutes`;

    showSuccessToast(message, {
        duration: 4000,
        actions: [
            {
                label: 'Cancel',
                handler: () => cancelSleepTimer(),
                primary: false
            }
        ]
    });

    console.log(`⏰ Sleep timer started: ${minutes} minutes, waitForTrackEnd: ${waitForTrackEnd}`);
}

/**
 * Create and show the sleep timer modal
 */
export function showSleepTimerModal() {
    // Remove existing modal if present (ensures fresh state)
    let existingModal = document.getElementById('sleepTimerModal');
    if (existingModal) {
        // Clean up bootstrap modal instance
        const bsModal = bootstrap.Modal.getInstance(existingModal);
        if (bsModal) {
            bsModal.dispose();
        }
        existingModal.remove();
    }

    // Create fresh modal with current timer state
    const modal = createSleepTimerModal();
    document.body.appendChild(modal);

    // Initialize modal with saved/active duration
    const duration = sleepTimerState.active
        ? sleepTimerState.duration
        : getSavedDuration();

    initializeModalValues(modal, duration, sleepTimerState.waitForTrackEnd);

    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    // Clean up modal after it's hidden
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    }, { once: true });
}

/**
 * Create the sleep timer modal HTML
 */
function createSleepTimerModal() {
    const modalHtml = `
        <div class="modal fade" id="sleepTimerModal" tabindex="-1" aria-labelledby="sleepTimerModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header border-bottom-0">
                        <h5 class="modal-title" id="sleepTimerModalLabel">
                            <i class="bi bi-moon-stars me-2"></i>Sleep Timer
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Large time display -->
                        <div class="text-center mb-4">
                            <div class="timer-display" style="font-size: 3rem; font-weight: 300; font-variant-numeric: tabular-nums; color: var(--bs-success);">
                                <span id="sleep-timer-display">30</span><span class="text-muted" style="font-size: 2rem;">min</span>
                            </div>
                        </div>

                        <!-- Slider -->
                        <div class="mb-4">
                            <label class="form-label small text-muted">Adjust duration:</label>
                            <input type="range"
                                   class="form-range"
                                   id="sleep-timer-slider"
                                   min="5"
                                   max="120"
                                   step="5"
                                   value="30">
                            <div class="d-flex justify-content-between small text-muted mt-1">
                                <span>5 min</span>
                                <span>2 hours</span>
                            </div>
                        </div>

                        <!-- Quick presets -->
                        <div class="mb-3">
                            <p class="text-muted small mb-2">Quick presets:</p>
                            <div class="d-grid gap-2">
                                <button class="btn btn-outline-secondary sleep-preset" data-minutes="15">
                                    <i class="bi bi-clock me-2"></i>15 minutes
                                </button>
                                <button class="btn btn-outline-secondary sleep-preset" data-minutes="30">
                                    <i class="bi bi-clock me-2"></i>30 minutes
                                </button>
                                <button class="btn btn-outline-secondary sleep-preset" data-minutes="45">
                                    <i class="bi bi-clock me-2"></i>45 minutes
                                </button>
                                <button class="btn btn-outline-secondary sleep-preset" data-minutes="60">
                                    <i class="bi bi-clock me-2"></i>1 hour
                                </button>
                            </div>
                        </div>

                        <!-- Wait for track end option -->
                        <div class="p-3 bg-body-secondary rounded">
                            <div class="form-check d-flex align-items-center">
                                <input class="form-check-input mt-0 me-2 flex-shrink-0" type="checkbox" id="sleep-wait-track-end" checked>
                                <label class="form-check-label mb-0" for="sleep-wait-track-end">
                                    <i class="bi bi-skip-end me-2"></i>Wait until current track ends
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer border-top-0">
                        ${sleepTimerState.active ? `
                            <button type="button" class="btn btn-danger me-auto" id="sleep-cancel-btn">
                                <i class="bi bi-x-circle me-2"></i>Cancel Timer
                            </button>
                        ` : ''}
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-success" id="sleep-start-btn">
                            <i class="bi bi-alarm me-2"></i>${sleepTimerState.active ? 'Update Timer' : 'Start Timer'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    const div = document.createElement('div');
    div.innerHTML = modalHtml;
    return div.firstElementChild;
}

/**
 * Initialize modal values and event listeners
 */
function initializeModalValues(modal, duration, waitForTrackEnd) {
    const slider = modal.querySelector('#sleep-timer-slider');
    const display = modal.querySelector('#sleep-timer-display');
    const checkbox = modal.querySelector('#sleep-wait-track-end');
    const startBtn = modal.querySelector('#sleep-start-btn');
    const cancelBtn = modal.querySelector('#sleep-cancel-btn');
    const presetBtns = modal.querySelectorAll('.sleep-preset');

    // Set initial values
    slider.value = duration;
    display.textContent = duration;
    checkbox.checked = waitForTrackEnd;

    // Update display function
    const updateDisplay = (value) => {
        display.textContent = value;
    };

    // Slider event listener
    slider.addEventListener('input', (e) => {
        updateDisplay(e.target.value);
    });

    // Preset buttons
    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const minutes = parseInt(btn.dataset.minutes, 10);
            slider.value = minutes;
            updateDisplay(minutes);
        });
    });

    // Start/Update button
    startBtn.addEventListener('click', () => {
        const minutes = parseInt(slider.value, 10);
        const wait = checkbox.checked;

        startSleepTimer(minutes, wait);

        // Close modal
        const bsModal = bootstrap.Modal.getInstance(modal);
        bsModal.hide();
    });

    // Cancel button (only shown if timer is active)
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            cancelSleepTimer();

            // Close modal
            const bsModal = bootstrap.Modal.getInstance(modal);
            bsModal.hide();
        });
    }
}

/**
 * Initialize sleep timer button in bottom player
 */
export function initSleepTimer() {
    console.log('⏰ Initializing sleep timer');

    // Find the sleep timer button
    const sleepBtn = document.getElementById('sleep-timer-btn');

    if (!sleepBtn) {
        console.warn('Sleep timer button not found in DOM');
        return;
    }

    // Add click handler
    sleepBtn.addEventListener('click', () => {
        showSleepTimerModal();
    });

    // Initialize button state
    updateSleepTimerButton();

    console.log('✅ Sleep timer initialized');
}

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', () => {
    cleanupSleepTimer();
});
