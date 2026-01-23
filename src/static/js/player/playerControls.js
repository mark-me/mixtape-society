// static/js/player/playerControls.js
import {
    globalCastingState,
    isCasting,
    castPlay,
    castPause,
    castTogglePlayPause,
    castNext,
    castPrevious,
    castJumpToTrack,
    isCastPlaying,
    setCastControlCallbacks,
    stopCasting,
    castSeek,
    getCastPlayState
} from './chromecast.js';

import {
    detectiOS,
    detectAndroid,
    logDeviceInfo,
    silenceLocalPlayer,
    enableLocalPlayer,
    clearMediaSession,
    setupLocalMediaSession,
    updateMediaSessionPosition,
    extractMetadataFromDOM
} from './playerUtils.js';

import {
    setupAndroidAutoMediaSession,
    clearAndroidAutoMediaSession,
    logAndroidAutoStatus,
    isAndroidAutoConnected
} from './androidAuto.js';

/**
 * Quality settings for audio playback
 */
const QUALITY_LEVELS = {
    high: { label: 'High (256k)', bandwidth: 'high' },
    medium: { label: 'Medium (192k)', bandwidth: 'medium' },
    low: { label: 'Low (128k)', bandwidth: 'low' },
    original: { label: 'Original', bandwidth: 'highest' }
};

const DEFAULT_QUALITY = 'medium';

/**
 * Repeat mode settings
 */
const REPEAT_MODES = {
    OFF: 'off',
    ALL: 'all',
    ONE: 'one'
};

const REPEAT_MODE_LABELS = {
    [REPEAT_MODES.OFF]: 'Off',
    [REPEAT_MODES.ALL]: 'All',
    [REPEAT_MODES.ONE]: 'One'
};

const REPEAT_MODE_ICONS = {
    [REPEAT_MODES.OFF]: 'bi-repeat',
    [REPEAT_MODES.ALL]: 'bi-repeat',
    [REPEAT_MODES.ONE]: 'bi-repeat-1'
};

const REPEAT_MODE_STYLES = {
    [REPEAT_MODES.OFF]: 'btn-outline-light',
    [REPEAT_MODES.ALL]: 'btn-light',
    [REPEAT_MODES.ONE]: 'btn-info'
};

const DEFAULT_REPEAT_MODE = REPEAT_MODES.OFF;

/**
 * Timing constants for various UI delays and intervals
 */
const TIMING = {
    AUTO_SAVE_INTERVAL: 5000,      // Save playback position every 5s
    UI_RESTORE_DELAY: 500,          // Delay before scrolling to restored track
    HIGHLIGHT_DURATION: 3000,       // How long to highlight restored track (yellow background)
    IOS_HELP_DISMISS: 10000,        // Auto-dismiss iOS casting help after 10s
    PLAYBACK_RESUME_DELAY: 50       // Small delay before resuming playback after restoration
};

// Global flag to prevent duplicate iOS help setup
let iOSHelpInitialized = false;

const iOS = detectiOS();
const androidInfo = detectAndroid();

/**
 * Show iOS-specific help message for Chromecast
 */
function showiOSCastHelp() {
    if (!iOS || iOSHelpInitialized) return;

    iOSHelpInitialized = true;

    const helpHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert" style="position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; max-width: 90%; width: 400px;">
            <h6 class="alert-heading">📱 Casting from iPhone</h6>
            <small>
                <strong>To cast to Chromecast:</strong><br>
                1. Install Google Home app<br>
                2. Use Chrome browser (not Safari)<br>
                3. Connect to same WiFi network<br>
                <br>
                <strong>For AirPlay (recommended):</strong><br>
                Use Safari and tap the AirPlay icon in audio controls
            </small>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    const castBtn = document.getElementById('cast-button');

    if (castBtn) {
        castBtn.addEventListener('click', () => {
            setTimeout(() => {
                if (!isCasting()) {
                    const existingHelp = document.querySelector('.alert-info');
                    if (!existingHelp) {
                        document.body.insertAdjacentHTML('afterbegin', helpHtml);
                    }
                }
            }, 3000);
        }, { once: true });
    }
}

export function initPlayerControls() {
    const player = document.getElementById('main-player');
    const container = document.getElementById('bottom-player-container');
    const closeBtn = document.getElementById('close-bottom-player');
    const prevBtn = document.getElementById('prev-btn-bottom');
    const nextBtn = document.getElementById('next-btn-bottom');
    const trackItems = document.querySelectorAll('.track-item');
    const bottomTitle = document.getElementById('bottom-now-title');
    const bottomArtistAlbum = document.getElementById('bottom-now-artist-album');

    let currentIndex = -1;
    window.currentTrackIndex = currentIndex;
    
    // Initialize quality from storage with error handling
    let currentQuality = DEFAULT_QUALITY;
    try {
        currentQuality = localStorage.getItem('audioQuality') || DEFAULT_QUALITY;
    } catch (e) {
        console.warn('Failed to load audio quality from storage, using default:', e.message);
    }

    // Playback state persistence
    const STORAGE_KEY_POSITION = 'mixtape_playback_position';
    const STORAGE_KEY_TRACK = 'mixtape_current_track';
    const STORAGE_KEY_TIME = 'mixtape_current_time';
    const STORAGE_KEY_SHUFFLE = 'mixtape_shuffle_state';
    const STORAGE_KEY_REPEAT = 'mixtape_repeat_mode';
    let autoSaveTimer = null;
    let isCurrentlyCasting = false;

    // Shuffle state
    let isShuffled = false;
    let shuffleOrder = [];

    // Repeat state
    let repeatMode = DEFAULT_REPEAT_MODE;

    // Guard flag to prevent duplicate document click listener installation
    let documentClickHandlerInstalled = false;

    // Toast notification system
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
            autohide: false  // Don't auto-hide errors
        }
    };

    // Toast queue management
    let toastQueue = [];
    let currentToast = null;
    let toastIdCounter = 0;

    // Log device capabilities
    logDeviceInfo();

    // Log Android Auto status if Android device
    if (androidInfo) {
        logAndroidAutoStatus();
    }

    // Show iOS help if needed
    if (iOS) {
        showiOSCastHelp();
    }

    console.log('ðŸŽ® PlayerControls initialized');

    // Player control API for external modules
    const playerControlsAPI = {
        play: () => {
            if (player.paused) {
                player.play().catch(err => console.error("Play failed:", err));
            }
        },
        pause: () => {
            if (!player.paused) {
                player.pause();
            }
        },
        next: () => {
            // Use proper next track logic (respects shuffle/repeat)
            const nextIdx = getNextTrackWithRepeat(currentIndex);
            if (nextIdx >= 0 && nextIdx < trackItems.length) {
                playTrack(nextIdx);
            } else {
                console.log('🚗 No next track available');
            }
        },
        previous: () => {
            // Use proper previous track logic (respects shuffle/repeat)
            const prevIdx = getPreviousTrackWithRepeat(currentIndex);
            if (prevIdx >= 0 && prevIdx < trackItems.length) {
                playTrack(prevIdx);
            } else {
                console.log('🚗 No previous track available');
            }
        },
        jumpTo: (index) => {
            if (index >= 0 && index < trackItems.length) {
                playTrack(index);
            }
        },
        seek: (time) => {
            // Guard against invalid player or time
            if (!player || !Number.isFinite(time) || time < 0) {
                return;
            }
            
            // Guard against seeking beyond duration (only if duration is finite)
            // Some streaming sources have NaN/Infinity duration
            if (Number.isFinite(player.duration) && time > player.duration) {
                return;
            }
            
            player.currentTime = time;
        }
    };

    const checkCastingState = () => {
        return globalCastingState || isCurrentlyCasting;
    }

    const onlyWhenNotCasting = (handler) => {
        return function (...args) {
            if (!checkCastingState()) {
                handler.apply(this, args);
            }
        };
    }

    // =============================================================================
    // HELPER FUNCTIONS - Centralized logic to avoid repetition
    // =============================================================================

    /**
     * Check if player has a source loaded
     */
    const hasSource = () => {
        return !!(player && player.src && player.src !== '');
    };

    /**
     * Get a safe track index for playback
     * Returns currentIndex if valid, otherwise 0, or -1 if no tracks
     */
    const getSafeTrackIndex = () => {
        if (trackItems.length === 0) {
            return -1; // No tracks available
        }
        
        if (currentIndex >= 0 && currentIndex < trackItems.length) {
            return currentIndex;
        }
        
        return 0; // Default to first track
    };

    /**
     * Ensure a track is loaded and start playing
     * Centralizes the "check source, load if needed, then play" logic
     */
    const ensureTrackLoadedAndPlay = () => {
        const index = getSafeTrackIndex();
        
        if (index === -1) {
            console.warn('⚠️ No tracks available to play');
            return;
        }
        
        // If no source, load the track first
        if (!hasSource()) {
            console.log('🎵 Loading track before play:', index);
            playTrack(index);
            // Update play icons after track loads
            setTimeout(() => syncPlayIcons(), 100);
        } else {
            // Source already loaded, just resume
            player.play().catch(err => console.error("Resume failed:", err));
        }
    };

    /**
     * Seek to a specific time when player is ready
     * More deterministic than arbitrary setTimeout
     */
    const seekWhenReady = (targetTime) => {
        if (!targetTime || targetTime <= 0) {
            return;
        }
        
        const trySeek = () => {
            if (!player) return;
            if (!player.duration || isNaN(player.duration)) return;
            if (targetTime > player.duration) return;
            if (player.readyState < 2) return; // Need HAVE_CURRENT_DATA or better
            
            player.currentTime = targetTime;
            console.log(`⏩ Restored position: ${Math.floor(targetTime)}s`);
            
            // Clean up listeners
            player.removeEventListener('canplay', trySeek);
            player.removeEventListener('loadedmetadata', trySeek);
        };
        
        // Check if already ready
        if (player.readyState >= 2) {
            trySeek();
        } else {
            // Wait for ready events
            player.addEventListener('canplay', trySeek, { once: true });
            player.addEventListener('loadedmetadata', trySeek, { once: true });
        }
    };

    /**
     * Apply UI state from restored playback position
     */
    const applyRestoredUIState = (savedState) => {
        const track = trackItems[savedState.track];
        if (!track) {
            console.warn('⚠️ Cannot restore UI: track not found');
            return;
        }
        
        // Update bottom player info
        updateBottomPlayerInfo(track);
        container.style.display = 'block';
        
        // Mark track as active
        setActiveTrack(track);
        
        // Update play icons
        syncPlayIcons();
        
        // Scroll to track with visual indicator
        setTimeout(() => {
            track.scrollIntoView({ behavior: 'smooth', block: 'center' });
            track.style.backgroundColor = '#fff3cd';
            setTimeout(() => {
                track.style.backgroundColor = '';
            }, TIMING.HIGHLIGHT_DURATION);
        }, TIMING.UI_RESTORE_DELAY);
    };

    /**
     * Attach listener to seek on first play after restoration
     */
    const attachRestoredSeekOnFirstPlay = (savedState) => {
        let restoredSeekTime = savedState.time;
        
        const handleRestoredPlay = () => {
            if (player && currentIndex === savedState.track && restoredSeekTime > 0) {
                seekWhenReady(restoredSeekTime);
                restoredSeekTime = 0; // Clear after use
            }
            player.removeEventListener('play', handleRestoredPlay);
        };
        
        player.addEventListener('play', handleRestoredPlay);
    };

    // =============================================================================
    // UI UPDATE HELPERS
    // =============================================================================

    /**
     * Set the active track in the UI
     * Removes active class from all tracks and adds it to the specified track
     * 
     * @param {HTMLElement} trackElement - Track element to make active (or null to clear all)
     */
    const setActiveTrack = (trackElement) => {
        trackItems.forEach(t => t.classList.remove('active-track'));
        if (trackElement) {
            trackElement.classList.add('active-track');
        }
    };

    /**
     * Update bottom player display with track info
     * 
     * @param {HTMLElement} track - Track element with data attributes (or null to clear)
     */
    const updateBottomPlayerInfo = (track) => {
        if (!track) {
            bottomTitle.textContent = '–';
            bottomArtistAlbum.textContent = '–';
            return;
        }
        bottomTitle.textContent = track.dataset.title;
        bottomArtistAlbum.textContent = `${track.dataset.artist} • ${track.dataset.album}`;
    };

    /**
     * Create a handler that checks casting state before executing
     * Centralizes the casting vs local playback decision pattern
     * 
     * @param {Function} castHandler - Handler function for casting mode
     * @param {Function} localHandler - Handler function for local playback
     * @returns {Function} Combined handler that chooses based on casting state
     */
    const createCastAwareHandler = (castHandler, localHandler) => {
        return () => {
            if (checkCastingState()) {
                castHandler();
            } else {
                localHandler();
            }
        };
    };

    // =============================================================================
    // SHUFFLE FUNCTIONS
    // =============================================================================

    /**
     * Generate a shuffled order of track indices using Fisher-Yates algorithm
     */
    const generateShuffleOrder = () => {
        const order = Array.from({ length: trackItems.length }, (_, i) => i);
        
        // Fisher-Yates shuffle
        for (let i = order.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [order[i], order[j]] = [order[j], order[i]];
        }
        
        return order;
    };

    /**
     * Enable shuffle mode
     */
    const enableShuffle = () => {
        if (trackItems.length === 0) {
            console.warn('⚠️ Cannot shuffle: no tracks available');
            return;
        }

        isShuffled = true;
        
        // Generate new shuffle order
        shuffleOrder = generateShuffleOrder();
        
        // Save to storage with error handling
        try {
            const shuffleState = {
                enabled: true,
                order: shuffleOrder,
                timestamp: Date.now()
            };
            localStorage.setItem(STORAGE_KEY_SHUFFLE, JSON.stringify(shuffleState));
        } catch (e) {
            // Storage failed (privacy mode, quota exceeded, etc.)
            // Shuffle still works in-memory, just won't persist
            console.warn('Failed to save shuffle state to storage:', e.message);
        }
        
        // Update button UI
        updateShuffleButton();
        
        console.log('🔀 Shuffle enabled:', shuffleOrder);
    };

    /**
     * Disable shuffle mode
     */
    const disableShuffle = () => {
        isShuffled = false;
        shuffleOrder = [];
        
        // Remove from storage with error handling
        try {
            localStorage.removeItem(STORAGE_KEY_SHUFFLE);
        } catch (e) {
            // Storage removal failed (privacy mode, etc.)
            // Shuffle is still disabled in-memory
            console.warn('Failed to remove shuffle state from storage:', e.message);
        }
        
        // Update button UI
        updateShuffleButton();
        
        console.log('▶️ Shuffle disabled - sequential playback');
    };

    /**
     * Toggle shuffle on/off
     */
    const toggleShuffle = () => {
        if (isShuffled) {
            disableShuffle();
        } else {
            enableShuffle();
        }
    };

    /**
     * Update shuffle button appearance
     */
    const updateShuffleButton = () => {
        const shuffleBtn = document.getElementById('shuffle-btn-bottom');
        if (!shuffleBtn) return;
        
        if (isShuffled) {
            shuffleBtn.classList.remove('btn-outline-light');
            shuffleBtn.classList.add('btn-light');
            shuffleBtn.title = 'Shuffle: ON';
        } else {
            shuffleBtn.classList.remove('btn-light');
            shuffleBtn.classList.add('btn-outline-light');
            shuffleBtn.title = 'Shuffle: OFF';
        }
    };

    /**
     * Restore shuffle state from localStorage
     */
    const restoreShuffleState = () => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY_SHUFFLE);
            if (!stored) return false;
            
            const shuffleState = JSON.parse(stored);
            
            // Validate shuffle order matches current playlist length
            if (shuffleState.enabled && 
                shuffleState.order && 
                shuffleState.order.length === trackItems.length) {
                
                isShuffled = true;
                shuffleOrder = shuffleState.order;
                updateShuffleButton();
                
                console.log('🔀 Restored shuffle mode:', shuffleOrder);
                return true;
            } else if (shuffleState.order && shuffleState.order.length !== trackItems.length) {
                // Playlist changed - clear old shuffle
                console.log('⚠️ Shuffle order length mismatch - clearing');
                localStorage.removeItem(STORAGE_KEY_SHUFFLE);
            }
        } catch (error) {
            console.warn('Could not restore shuffle state:', error);
        }
        
        return false;
    };

    /**
     * Get the next track index based on shuffle state
     */
    const getNextTrackIndex = (fromIndex) => {
        if (isShuffled && shuffleOrder.length > 0) {
            // Find current position in shuffle order
            const currentPosition = shuffleOrder.indexOf(fromIndex);
            
            if (currentPosition === -1) {
                // Current track not in shuffle order (shouldn't happen)
                // Return first track in shuffle
                console.warn('⚠️ Track not in shuffle order, starting from beginning');
                return shuffleOrder[0];
            }
            
            // Get next position in shuffle order
            const nextPosition = currentPosition + 1;
            
            if (nextPosition < shuffleOrder.length) {
                return shuffleOrder[nextPosition];
            } else {
                // End of shuffle
                return -1; // Signal end of playlist
            }
        } else {
            // Sequential playback
            const nextIndex = fromIndex + 1;
            return nextIndex < trackItems.length ? nextIndex : -1;
        }
    };

    /**
     * Get the previous track index based on shuffle state
     */
    const getPreviousTrackIndex = (fromIndex) => {
        if (isShuffled && shuffleOrder.length > 0) {
            // Find current position in shuffle order
            const currentPosition = shuffleOrder.indexOf(fromIndex);
            
            if (currentPosition === -1) {
                // Current track not in shuffle order
                return shuffleOrder[shuffleOrder.length - 1];
            }
            
            // Get previous position in shuffle order
            const prevPosition = currentPosition - 1;
            
            if (prevPosition >= 0) {
                return shuffleOrder[prevPosition];
            } else {
                // At start of shuffle
                return -1;
            }
        } else {
            // Sequential playback
            return fromIndex - 1;
        }
    };

    // =============================================================================
    // REPEAT MODE FUNCTIONS
    // =============================================================================

    /**
     * Cycle through repeat modes: off → all → one → off
     */
    const cycleRepeatMode = () => {
        const modes = Object.values(REPEAT_MODES);
        const currentIndex = modes.indexOf(repeatMode);
        const nextIndex = (currentIndex + 1) % modes.length;
        repeatMode = modes[nextIndex];
        
        // Save to storage
        try {
            localStorage.setItem(STORAGE_KEY_REPEAT, repeatMode);
        } catch (e) {
            console.warn('Failed to save repeat mode:', e.message);
        }
        
        // Update button UI
        updateRepeatButton();
        
        console.log(`🔁 Repeat: ${REPEAT_MODE_LABELS[repeatMode]}`);
    };

    /**
     * Update repeat button appearance based on current mode
     */
    const updateRepeatButton = () => {
        const repeatBtn = document.getElementById('repeat-btn-bottom');
        if (!repeatBtn) return;
        
        // Remove all mode classes
        Object.values(REPEAT_MODE_STYLES).forEach(cls => {
            repeatBtn.classList.remove(cls);
        });
        
        // Add appropriate style class
        const styleClass = REPEAT_MODE_STYLES[repeatMode] || REPEAT_MODE_STYLES[REPEAT_MODES.OFF];
        repeatBtn.classList.add(styleClass);
        
        // Set icon using safe DOM manipulation
        const iconClass = REPEAT_MODE_ICONS[repeatMode] || REPEAT_MODE_ICONS[REPEAT_MODES.OFF];
        
        // Clear existing content safely
        repeatBtn.textContent = '';
        
        // Create and append icon element
        const icon = document.createElement('i');
        icon.className = iconClass;
        repeatBtn.appendChild(icon);
        
        // Set title
        const label = REPEAT_MODE_LABELS[repeatMode] || REPEAT_MODE_LABELS[REPEAT_MODES.OFF];
        repeatBtn.title = `Repeat: ${label}`;
    };

    /**
     * Validate if a value is a valid repeat mode
     */
    const isValidRepeatMode = (mode) => {
        return Object.values(REPEAT_MODES).includes(mode);
    };

    /**
     * Normalize a repeat mode against the current playback context
     * Forces Repeat Off when it doesn't make sense (e.g., 0-1 tracks)
     * 
     * @param {string} mode - The repeat mode to normalize
     * @returns {string} Normalized repeat mode
     */
    const normalizeRepeatModeForContext = (mode) => {
        // Force Repeat Off when there are 0-1 tracks (repeat makes no sense)
        if (!Array.isArray(trackItems) || trackItems.length <= 1) {
            return REPEAT_MODES.OFF;
        }

        // If casting is active and doesn't support repeat, force Off
        // (This is a placeholder - implement if casting limitations exist)
        // if (checkCastingState() && !castingSupportsRepeat()) {
        //     return REPEAT_MODES.OFF;
        // }

        return mode;
    };

    /**
     * Restore repeat mode from localStorage
     */
    const restoreRepeatMode = () => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY_REPEAT);
            if (stored && isValidRepeatMode(stored)) {
                // Normalize stored mode to current context
                const normalizedMode = normalizeRepeatModeForContext(stored);
                
                repeatMode = normalizedMode;
                updateRepeatButton();
                
                if (normalizedMode !== stored) {
                    console.log(`🔁 Normalized repeat mode: ${stored} → ${normalizedMode} (context: ${trackItems.length} tracks)`);
                } else {
                    console.log(`🔁 Restored repeat mode: ${REPEAT_MODE_LABELS[repeatMode]}`);
                }
                return true;
            }
        } catch (e) {
            console.warn('Failed to restore repeat mode:', e.message);
        }
        return false;
    };

    /**
     * Get next track index considering repeat mode
     * Handles edge cases: invalid currentIndex, empty playlist, etc.
     * 
     * @param {number} currentIndex - Current track index
     * @param {Object} options - Optional behavior modifiers
     * @param {boolean} options.skipRepeatOne - If true, treat Repeat One as Repeat Off (for prefetch)
     * @returns {number} Next track index, or -1 if no next track
     */
    const getNextTrackWithRepeat = (currentIndex, options = {}) => {
        const { skipRepeatOne = false } = options;
        
        // Defensive: Validate playlist has tracks
        if (trackItems.length === 0) {
            console.warn('⚠️ No tracks available');
            return -1;
        }
        
        // Defensive: Handle invalid currentIndex
        // Treat out-of-bounds or negative as "start from beginning"
        if (currentIndex < 0 || currentIndex >= trackItems.length) {
            console.warn(`⚠️ Invalid currentIndex: ${currentIndex}, defaulting to 0`);
            currentIndex = 0;
        }
        
        // Repeat One: Return same track (unless skipRepeatOne is set for prefetch)
        if (repeatMode === REPEAT_MODES.ONE && !skipRepeatOne) {
            return currentIndex;
        }
        
        // Get next track based on shuffle
        let nextIndex = getNextTrackIndex(currentIndex);
        
        // Repeat All: Loop back to start if we've reached the end
        if (nextIndex === -1 && repeatMode === REPEAT_MODES.ALL) {
            // Loop back to start (respecting shuffle if enabled)
            if (isShuffled && shuffleOrder.length > 0) {
                return shuffleOrder[0];
            } else {
                return 0;
            }
        }
        
        return nextIndex;
    };

    /**
     * Get previous track index considering repeat mode
     * Handles edge cases: invalid currentIndex, empty playlist, etc.
     * 
     * @param {number} currentIndex - Current track index
     * @returns {number} Previous track index, or -1 if no previous track
     */
    const getPreviousTrackWithRepeat = (currentIndex) => {
        // Defensive: Validate playlist has tracks
        if (trackItems.length === 0) {
            console.warn('⚠️ No tracks available');
            return -1;
        }
        
        // Defensive: Handle invalid currentIndex
        if (currentIndex < 0 || currentIndex >= trackItems.length) {
            console.warn(`⚠️ Invalid currentIndex: ${currentIndex}, defaulting to last track`);
            currentIndex = trackItems.length - 1;
        }
        
        // Repeat One: Return same track (validated)
        if (repeatMode === REPEAT_MODES.ONE) {
            return currentIndex;
        }
        
        // Get previous track based on shuffle
        let prevIndex = getPreviousTrackIndex(currentIndex);
        
        // Repeat All: Loop to end if we're at the start
        if (prevIndex === -1 && repeatMode === REPEAT_MODES.ALL) {
            // Loop to end (respecting shuffle if enabled)
            if (isShuffled && shuffleOrder.length > 0) {
                return shuffleOrder[shuffleOrder.length - 1];
            } else {
                return trackItems.length - 1;
            }
        }
        
        return prevIndex;
    };

    // =============================================================================
    // END HELPER FUNCTIONS
    // =============================================================================

    const setupAudioControlInterception = () => {
        player.addEventListener('play', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                player.pause();
                castPlay();
                return false;
            }
            
            // Check if trying to play without a source (after restoration)
            if (!hasSource()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                console.log('🎵 Native play button clicked - loading track first');
                ensureTrackLoadedAndPlay();
                return false;
            }
        }, true);

        player.addEventListener('pause', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                castPause();
            }
        });

        player.addEventListener('seeking', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);

        player.addEventListener('loadeddata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                player.pause();
            }
        }, true);

        // Block metadata events while casting
        player.addEventListener('loadedmetadata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
            }
        }, true);
    }

    const initQualitySelector = () => {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');

        if (!qualityBtn || !qualityMenu) return;

        updateQualityButtonText();

        qualityBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            qualityMenu.classList.toggle('show');
        });

        // Only install document click listener once to prevent memory leaks
        if (!documentClickHandlerInstalled) {
            document.addEventListener('click', (e) => {
                const qualityBtn = document.getElementById('quality-btn-bottom');
                const qualityMenu = document.getElementById('quality-menu');
                
                if (qualityBtn && qualityMenu && 
                    !qualityBtn.contains(e.target) && 
                    !qualityMenu.contains(e.target)) {
                    qualityMenu.classList.remove('show');
                }
            });
            documentClickHandlerInstalled = true;
        }

        qualityMenu.querySelectorAll('.quality-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                const newQuality = option.dataset.quality;

                if (newQuality !== currentQuality) {
                    changeQuality(newQuality);
                }

                qualityMenu.classList.remove('show');
            });
        });
    }

    const updateQualityButtonText = () => {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;

        const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
        
        // Clear existing content safely
        qualityBtn.textContent = '';
        
        // Create and append icon
        const icon = document.createElement('i');
        icon.className = 'bi bi-gear-fill me-1';
        qualityBtn.appendChild(icon);
        
        // Append text node for quality label
        qualityBtn.appendChild(document.createTextNode(qualityLabel));
    }

    const updateQualityMenuState = (quality) => {
        document.querySelectorAll('.quality-option').forEach(opt => {
            const checkIcon = opt.querySelector('.bi-check2');
            if (opt.dataset.quality === quality) {
                opt.classList.add('active');
                if (checkIcon) checkIcon.style.display = 'inline';
            } else {
                opt.classList.remove('active');
                if (checkIcon) checkIcon.style.display = 'none';
            }
        });
    }

    const changeQuality = (newQuality) => {
        currentQuality = newQuality;
        
        // Save quality preference with error handling
        try {
            localStorage.setItem('audioQuality', newQuality);
        } catch (e) {
            // Quality change still works, just won't persist
            console.warn('Failed to save audio quality preference:', e.message);
        }

        updateQualityButtonText();
        updateQualityMenuState(newQuality);

        if (currentIndex >= 0 && player.src && !checkCastingState()) {
            const wasPlaying = !player.paused;
            const {currentTime} = player;

            playTrack(currentIndex);

            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }

        showQualityToast(newQuality);
    }

    const showQualityToast = (quality) => {
        const toastEl = document.getElementById('qualityToast');
        if (!toastEl) return;

        const toastBody = toastEl.querySelector('.toast-body');
        const qualityInfo = QUALITY_LEVELS[quality];

        if (toastBody && qualityInfo) {
            toastBody.textContent = `Quality changed to ${qualityInfo.label}`;
        }

        const toast = new bootstrap.Toast(toastEl, { delay: 2000 });
        toast.show();
    }

    const updateLocalMediaSession = (metadata) => {
        if (checkCastingState()) {
            // CRITICAL: Do NOT create Media Session when casting
            console.log('â­ï¸ Skipping Media Session - Chromecast handles it');
            return;
        }

        // Use Android Auto optimized Media Session for ALL Android devices
        // Android Auto will automatically pick it up if connected to car
        // This also improves notification controls for regular Android usage
        const androidInfo = detectAndroid();
        
        if (androidInfo) {
            console.log('Using Android-optimized Media Session (works with Android Auto)');
            setupAndroidAutoMediaSession(metadata, playerControlsAPI, player);
        } else if (detectiOS()) {
            // iOS Media Session
            console.log('Using iOS Media Session');
            setupLocalMediaSession(metadata, playerControlsAPI);
        } else {
            // Desktop/other Media Session
            console.log('Using desktop Media Session');
            setupLocalMediaSession(metadata, playerControlsAPI);
        }
    }

    const updatePositionState = () => {
        if (checkCastingState()) return;
        updateMediaSessionPosition(player.currentTime, player.duration, player.playbackRate);
    }

    const buildAudioUrl = (basePath, quality) => {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * Prefetch the next track to ensure smooth playback transitions
     * This will cache the audio file in the browser/service worker
     *
     * Prefetch strategy:
     * - First check if already cached to avoid redundant network traffic
     * - Use requestIdleCallback for low-priority scheduling (fallback to setTimeout)
     * - The service worker will handle caching asynchronously
     * - Does NOT mutate global repeat state (uses options parameter instead)
     */
    const prefetchNextTrack = async (currentIdx) => {
        // For prefetching, skip Repeat One (otherwise we'd prefetch the same track)
        // Pass this as an option instead of mutating global repeatMode
        const nextIdx = getNextTrackWithRepeat(currentIdx, { 
            skipRepeatOne: true 
        });

        // Check if there's a valid next track (-1 means no next track)
        if (nextIdx < 0 || nextIdx >= trackItems.length || nextIdx === currentIdx) {
            console.log('🚫 No next track to prefetch (end of playlist or same track)');
            return;
        }

        const nextTrack = trackItems[nextIdx];
        if (!nextTrack) {
            console.log('🚫 Resolved next track for prefetch is missing');
            return;
        }

        const audioUrl = buildAudioUrl(nextTrack.dataset.path, currentQuality);

        const modeInfo = isShuffled ? '🔀 shuffle' : '▶️ sequential';
        const repeatInfo = repeatMode !== REPEAT_MODES.OFF ? ` (repeat: ${repeatMode})` : '';
        console.log(`🔥 Prefetching next track (${modeInfo}${repeatInfo}):`, nextTrack.dataset.title);

        const doPrefetch = async () => {
            try {
                // Check if already cached (avoid redundant network request)
                if ('caches' in window) {
                    try {
                        const cached = await caches.match(audioUrl);
                        if (cached) {
                            console.log('✅ Next track already cached, skipping prefetch');
                            return;
                        }
                    } catch (cacheError) {
                        // Non-fatal: fall through to network prefetch
                        console.debug('Cache lookup failed during prefetch:', cacheError);
                    }
                }

                // Single GET request to warm the service worker cache
                // Note: priority: 'low' is non-standard and ignored by most browsers
                // We use requestIdleCallback for proper low-priority scheduling instead
                await fetch(audioUrl, {
                    method: 'GET',
                    credentials: 'include'
                });

                console.log('✅ Next track prefetch initiated');
            } catch (error) {
                // Prefetch failures are non-critical, just log them
                console.warn('⚠️ Prefetch failed (not critical):', error.message);
            }
        };

        // Schedule prefetch as a low-priority task
        // Use requestIdleCallback when available, otherwise defer with setTimeout
        if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
            window.requestIdleCallback(() => doPrefetch());
        } else {
            // Fallback: defer slightly so we don't contend with critical UI work
            setTimeout(() => doPrefetch(), 0);
        }
    };

    const playTrack = (index) => {
        console.log(`ðŸŽµ playTrack(${index}), casting: ${checkCastingState()}`);

        if (checkCastingState()) {
            console.log(`ðŸ“¡ Routing to Chromecast`);
            castJumpToTrack(index);
            updateUIForTrack(index);
            // NO Media Session setup - Chromecast handles it
            return;
        }

        console.log(`ðŸ”Š Playing locally`);

        if (index === currentIndex && player.src !== '') {
            player.play().catch(e => console.log('Autoplay prevented:', e));
            return;
        }

        if (index < 0 || index >= trackItems.length) {
            stopPlayback();
            return;
        }

        const track = trackItems[index];

        player.src = buildAudioUrl(track.dataset.path, currentQuality);
        if ('mediaSession' in navigator && 'setPositionState' in navigator.mediaSession) {
            try {
                navigator.mediaSession.setPositionState();
            } catch (e) { }
        }

        updateUIForTrack(index);

        const metadata = extractMetadataFromDOM(track);
        updateLocalMediaSession(metadata);

        player.play().catch(e => console.log('Autoplay prevented:', e));

        // Prefetch next track for smooth transitions
        prefetchNextTrack(index);
    }

    const updateUIForTrack = (index) => {
        if (index < 0 || index >= trackItems.length) return;

        const track = trackItems[index];

        updateBottomPlayerInfo(track);
        container.style.display = 'block';

        setActiveTrack(track);

        currentIndex = index;
        window.currentTrackIndex = index;

        // Auto-scroll to keep currently playing track visible
        scrollToCurrentTrack(track);
    }

    /**
     * Scroll to the currently playing track to keep it visible
     */
    const scrollToCurrentTrack = (trackElement) => {
        if (!trackElement) return;

        // Use smooth scrolling with 'center' alignment for best visibility
        trackElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest'
        });
    }

    const stopPlayback = () => {
        player.pause();
        player.src = '';
        player.load();
        container.style.display = 'none';
        setActiveTrack(null);  // Clear all active tracks
        currentIndex = -1;

        // Clear appropriate Media Session
        if (isAndroidAutoConnected()) {
            clearAndroidAutoMediaSession();
        } else {
            clearMediaSession();
        }
    }

    const syncPlayIcons = () => {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            const isPlaying = isCurrentTrack && (
                (checkCastingState() && isCastPlaying()) ||
                (!checkCastingState() && !player.paused)
            );

            if (isPlaying) {
                icon.classList.remove('bi-play-fill');
                icon.classList.add('bi-pause-fill');
            } else {
                icon.classList.remove('bi-pause-fill');
                icon.classList.add('bi-play-fill');
            }

            if (isPlaying) {
                item.classList.add('playing');
            } else {
                item.classList.remove('playing');
            }
        });
    }

    // Save current playback state
    /**
     * Save current playback state to localStorage
     * Saves position regardless of playing/paused state so pause position is preserved
     */
    const savePlaybackState = () => {
        // Only save if we have a valid track and player
        if (currentIndex < 0 || !player) {
            return;
        }

        // Don't save if current time is invalid
        if (!Number.isFinite(player.currentTime) || player.currentTime < 0) {
            return;
        }

        try {
            const trackElement = trackItems[currentIndex];
            const title = trackElement?.dataset.title || 'Unknown';
            
            localStorage.setItem(STORAGE_KEY_TRACK, currentIndex.toString());
            localStorage.setItem(STORAGE_KEY_TIME, player.currentTime.toString());
            localStorage.setItem(STORAGE_KEY_POSITION, JSON.stringify({
                track: currentIndex,
                time: player.currentTime,
                title: title,
                timestamp: Date.now(),
                paused: player.paused  // Track whether it was paused
            }));
            
            console.debug(`💾 Saved state: track ${currentIndex}, time ${Math.floor(player.currentTime)}s, paused: ${player.paused}`);
        } catch (e) {
            console.warn('Failed to save playback state:', e);
        }
    };

    // Restore playback state
    const restorePlaybackState = () => {
        try {
            const savedPosition = localStorage.getItem(STORAGE_KEY_POSITION);
            if (savedPosition) {
                const state = JSON.parse(savedPosition);
                // Only restore if saved within last 24 hours
                if (Date.now() - state.timestamp < 24 * 60 * 60 * 1000) {
                    console.log(`📍 Resuming from track ${state.track}: "${state.title}" at ${Math.floor(state.time)}s`);
                    return state;
                }
            }
        } catch (e) {
            console.warn('Failed to restore playback state:', e);
        }
        return null;
    };

    // Clear saved state
    const clearPlaybackState = () => {
        try {
            localStorage.removeItem(STORAGE_KEY_TRACK);
            localStorage.removeItem(STORAGE_KEY_TIME);
            localStorage.removeItem(STORAGE_KEY_POSITION);
        } catch (e) {
            // Storage removal failed (privacy mode, etc.)
            console.warn('Failed to clear playback state from storage:', e.message);
        }
    };

    // Start auto-saving playback position
    const startAutoSave = () => {
        if (autoSaveTimer) clearInterval(autoSaveTimer);
        autoSaveTimer = setInterval(savePlaybackState, TIMING.AUTO_SAVE_INTERVAL);
    };

    // Stop auto-saving
    const stopAutoSave = () => {
        if (autoSaveTimer) {
            clearInterval(autoSaveTimer);
            autoSaveTimer = null;
        }
    };

    const togglePlayPause = () => {
        if (checkCastingState()) {
            castTogglePlayPause();
        }
        else if (player.paused) {
            ensureTrackLoadedAndPlay();
        }
        else {
            player.pause();
        }
    }

    const updateAudioProgress = () => {
        if (!player.duration || isNaN(player.duration)) return;

        const progress = (player.currentTime / player.duration) * 100;
        player.style.setProperty('--audio-progress', `${progress}%`);
    }

    const initCastListeners = () => {
        document.addEventListener('cast:started', () => {
            isCurrentlyCasting = true;
            silenceLocalPlayer();

            // Clear local Media Session when casting starts
            if (isAndroidAutoConnected()) {
                clearAndroidAutoMediaSession();
            } else {
                clearMediaSession();
            }

            syncPlayIcons();
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            enableLocalPlayer();

            // Restore local Media Session when casting ends
            if (currentIndex >= 0) {
                const track = trackItems[currentIndex];
                const metadata = extractMetadataFromDOM(track);
                updateLocalMediaSession(metadata);
            }

            syncPlayIcons();
        });

        setCastControlCallbacks({
            onTrackChange: (index) => {
                updateUIForTrack(index);
            },
            onPlayStateChange: (state) => {
                syncPlayIcons();
            },
            onTimeUpdate: (time) => {
                // No-op - Chromecast handles progress
            }
        });
    }

    const initEventListeners = () => {
        document.getElementById('big-play-btn')?.addEventListener('click', () => {
            if (trackItems.length === 0) return;
            
            if (currentIndex === -1) {
                // No track selected - start from beginning
                if (trackItems.length > 0) {
                    playTrack(0);
                }
            } else if (checkCastingState()) {
                castPlay();
            } else {
                ensureTrackLoadedAndPlay();
            }
        });

        player?.addEventListener('play', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));

        player?.addEventListener('pause', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));

        // Prefetch next track when current track can play (has buffered enough)
        player?.addEventListener('canplay', onlyWhenNotCasting(() => {
            if (currentIndex >= 0) {
                prefetchNextTrack(currentIndex);
            }
        }));

        /**
         * Show a non-blocking playback error toast with optional skip action
         * Provides better UX than blocking alert dialogs
         * 
         * @param {string} message - Error message to display
         * @param {Object} options - Configuration options
         * @param {boolean} options.isTerminal - Whether this is a terminal error
         * @param {Function} options.onSkip - Handler for skip action
         */
        const showPlaybackErrorToast = (message, { isTerminal = false, onSkip } = {}) => {
            const toastEl = document.getElementById('qualityToast');
            
            if (toastEl) {
                // Reuse existing Bootstrap toast
                const toastBody = toastEl.querySelector('.toast-body');
                if (toastBody) {
                    // Clear existing content
                    toastBody.textContent = '';
                    
                    // Add message
                    const messageSpan = document.createElement('span');
                    messageSpan.textContent = message;
                    messageSpan.style.display = 'block';
                    messageSpan.style.marginBottom = onSkip ? '0.5rem' : '0';
                    toastBody.appendChild(messageSpan);
                    
                    // Add skip button if terminal error
                    if (isTerminal && onSkip) {
                        const skipBtn = document.createElement('button');
                        skipBtn.className = 'btn btn-sm btn-light me-2';
                        skipBtn.textContent = 'Skip Track';
                        skipBtn.onclick = () => {
                            onSkip();
                            const toast = bootstrap.Toast.getInstance(toastEl);
                            if (toast) toast.hide();
                        };
                        toastBody.appendChild(skipBtn);
                    }
                    
                    // Show toast with appropriate duration
                    const toast = new bootstrap.Toast(toastEl, { 
                        delay: isTerminal ? 8000 : 5000 
                    });
                    toast.show();
                    return;
                }
            }
            
            // Fallback: Create minimal inline banner
            const containerId = 'player-error-banner';
            let banner = document.getElementById(containerId);
            
            if (!banner) {
                banner = document.createElement('div');
                banner.id = containerId;
                banner.className = 'alert alert-danger d-flex align-items-center justify-content-between';
                banner.style.position = 'fixed';
                banner.style.bottom = '80px';
                banner.style.left = '50%';
                banner.style.transform = 'translateX(-50%)';
                banner.style.zIndex = '1060';
                banner.style.minWidth = '300px';
                banner.style.maxWidth = '500px';
                banner.style.margin = '0';
                
                document.body.appendChild(banner);
            }
            
            // Clear and set content
            banner.innerHTML = '';
            
            const messageEl = document.createElement('span');
            messageEl.textContent = message;
            messageEl.style.flex = '1';
            banner.appendChild(messageEl);
            
            const actionsEl = document.createElement('div');
            actionsEl.className = 'd-flex gap-2';
            
            if (isTerminal && onSkip) {
                const skipBtn = document.createElement('button');
                skipBtn.className = 'btn btn-sm btn-light';
                skipBtn.textContent = 'Skip';
                skipBtn.onclick = () => {
                    onSkip();
                    banner.remove();
                };
                actionsEl.appendChild(skipBtn);
            }
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn-close btn-close-white';
            closeBtn.setAttribute('aria-label', 'Close');
            closeBtn.onclick = () => banner.remove();
            actionsEl.appendChild(closeBtn);
            
            banner.appendChild(actionsEl);
            
            // Auto-hide for non-terminal errors
            if (!isTerminal) {
                setTimeout(() => {
                    if (banner && banner.parentElement) {
                        banner.remove();
                    }
                }, 5000);
            }
        };

        // Handle playback errors with retry logic
        let errorRetryCount = 0;
        let hasShownTerminalErrorToast = false;  // Track if terminal error toast shown
        const MAX_RETRIES = 2;
        
        player?.addEventListener('error', (e) => {
            const error = player?.error;
            if (!error) return;

            // Use currentIndex with guard instead of undefined 'index'
            const trackInfo = currentIndex >= 0 && trackItems[currentIndex]
                ? trackItems[currentIndex].dataset.title
                : 'Unknown track';
            
            console.error('🚫 Playback error:', {
                code: error.code,
                message: error.message,
                src: player?.src,
                track: trackInfo,
                trackIndex: currentIndex
            });
            
            // Save state before handling error
            savePlaybackState();
            
            if (errorRetryCount < MAX_RETRIES) {
                errorRetryCount++;
                console.log(`🔄 Retrying playback (attempt ${errorRetryCount}/${MAX_RETRIES})...`);
                setTimeout(() => {
                    player.load();
                    player.play().catch(err => {
                        console.error('Retry failed:', err);
                        // Show toast once when max retries reached
                        if (errorRetryCount >= MAX_RETRIES && !hasShownTerminalErrorToast) {
                            hasShownTerminalErrorToast = true;
                            showPlaybackErrorToast(
                                `Unable to play "${trackInfo}". Try skipping to another track.`,
                                {
                                    isTerminal: true,
                                    onSkip: () => {
                                        // Skip to next track
                                        const nextIndex = getNextTrackWithRepeat(currentIndex);
                                        if (nextIndex >= 0 && nextIndex < trackItems.length) {
                                            playTrack(nextIndex);
                                        }
                                    }
                                }
                            );
                        }
                    });
                }, 1000);
            } else if (!hasShownTerminalErrorToast) {
                // Max retries reached, show toast once
                hasShownTerminalErrorToast = true;
                showPlaybackErrorToast(
                    `Unable to play "${trackInfo}". Try skipping to another track.`,
                    {
                        isTerminal: true,
                        onSkip: () => {
                            // Skip to next track
                            const nextIndex = getNextTrackWithRepeat(currentIndex);
                            if (nextIndex >= 0 && nextIndex < trackItems.length) {
                                playTrack(nextIndex);
                            }
                        }
                    }
                );
            }
        });
        
        // Handle stalled playback
        player?.addEventListener('stalled', () => {
            console.warn('⚠️ Playback stalled, attempting to recover...');
            savePlaybackState();
        });
        
        // Handle waiting/buffering
        player?.addEventListener('waiting', () => {
            console.log('⏳ Buffering...');
        });
        
        // Handle successful play resume after buffering
        player?.addEventListener('playing', () => {
            console.log('▶️ Playback resumed');
            errorRetryCount = 0; // Reset error count on successful playback
            hasShownTerminalAlert = false;  // Reset alert flag on successful playback
        });

        player?.addEventListener('ended', () => {
            syncPlayIcons();
            const trackElement = trackItems[currentIndex];
            const trackTitle = trackElement?.dataset.title || 'Unknown';
            console.log('✅ Track ended:', trackTitle);
            
            if (!checkCastingState()) {
                // Save that we completed this track
                savePlaybackState();
                
                // Get next track based on shuffle and repeat state
                const nextIndex = getNextTrackWithRepeat(currentIndex);
                
                if (nextIndex >= 0 && nextIndex < trackItems.length) {
                    const shuffleMode = isShuffled ? '🔀 shuffle' : '▶️ sequential';
                    const repeatInfo = repeatMode !== 'off' ? ` (repeat: ${repeatMode})` : '';
                    console.log(`🎵 Auto-advancing to next track (${shuffleMode}${repeatInfo})`);
                    playTrack(nextIndex);
                } else {
                    console.log('🏁 Reached end of playlist');
                    clearPlaybackState(); // Clear saved position at end
                }
            }
        });

        const handleAudioProgress = onlyWhenNotCasting(updateAudioProgress);
        player?.addEventListener('timeupdate', handleAudioProgress);
        player?.addEventListener('loadedmetadata', handleAudioProgress);
        player?.addEventListener('seeked', handleAudioProgress);


        // Start auto-saving position when playing
        player?.addEventListener('play', () => {
            startAutoSave();
        });
        
        // Stop auto-saving when paused
        player?.addEventListener('pause', () => {
            savePlaybackState(); // Save immediately on pause
            stopAutoSave();
        });
        
        const handlePositionUpdate = onlyWhenNotCasting(updatePositionState);
        player?.addEventListener('loadedmetadata', handlePositionUpdate);
        player?.addEventListener('play', handlePositionUpdate);
        player?.addEventListener('pause', handlePositionUpdate);
        player?.addEventListener('ratechange', handlePositionUpdate);
        player?.addEventListener('seeked', handlePositionUpdate);

        let lastPositionUpdate = 0;
        player?.addEventListener('timeupdate', onlyWhenNotCasting(() => {
            const now = Date.now();
            if (now - lastPositionUpdate >= 1000) {
                updatePositionState();
                lastPositionUpdate = now;
            }
        }));

        prevBtn?.addEventListener('click', createCastAwareHandler(
            castPrevious,
            () => {
                const prevIndex = getPreviousTrackWithRepeat(currentIndex);
                if (prevIndex >= 0) {
                    playTrack(prevIndex);
                } else {
                    console.log('⏮️ At start of playlist');
                }
            }
        ));

        nextBtn?.addEventListener('click', createCastAwareHandler(
            castNext,
            () => {
                const nextIndex = getNextTrackWithRepeat(currentIndex);
                if (nextIndex >= 0 && nextIndex < trackItems.length) {
                    playTrack(nextIndex);
                } else {
                    console.log('⏭️ At end of playlist');
                }
            }
        ));

        // Shuffle button
        const shuffleBtn = document.getElementById('shuffle-btn-bottom');
        shuffleBtn?.addEventListener('click', toggleShuffle);

        // Repeat button
        const repeatBtn = document.getElementById('repeat-btn-bottom');
        repeatBtn?.addEventListener('click', cycleRepeatMode);

        closeBtn?.addEventListener('click', stopPlayback);

        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                if (i === currentIndex) {
                    togglePlayPause();
                } else {
                    playTrack(i);
                }
            });
        });
    }

    const handleAutoStart = () => {
        if (trackItems.length === 0) return;

        if (window.location.hash === '#play') {
            setTimeout(() => playTrack(0), 500);
        } else if (sessionStorage.getItem('startPlaybackNow')) {
            sessionStorage.removeItem('startPlaybackNow');
            playTrack(0);
        }
    }

    // Initialize
    initQualitySelector();
    setupAudioControlInterception();
    initCastListeners();
    initEventListeners();

    // Restore shuffle and repeat state FIRST (before playback restoration)
    restoreShuffleState();
    restoreRepeatMode();

    // Restore playback position if available (BEFORE handleAutoStart)
    const savedState = restorePlaybackState();
    if (savedState && savedState.track < trackItems.length) {
        // Update currentIndex to the saved track
        currentIndex = savedState.track;
        window.currentTrackIndex = savedState.track;  // Keep window property in sync
        
        // Apply UI state using helper
        applyRestoredUIState(savedState);
        
        // Attach seek handler using helper
        attachRestoredSeekOnFirstPlay(savedState);
    } else {
        // No saved state - run auto-start logic
        handleAutoStart();
    }


    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
