// chromecast.js - Complete Implementation with Queue-Based Track Detection
// =========================================================================

/**
 * Global state
 */
let remotePlayer = null;
let remotePlayerController = null;
let castSession = null;
let lastQueueIndex = -1;
let castTimeUpdateInterval = null;

/**
 * Callbacks that will be set by playerControls.js
 */
let castCallbacks = {
    onCastStart: null,
    onCastEnd: null,
    onTrackChange: null,
    onPlayStateChange: null,
    onTimeUpdate: null,
    onVolumeChange: null
};

/**
 * Current playlist data (stored when casting starts)
 */
let currentPlaylist = [];
let currentCastIndex = 0;

/**
 * Export: Set callbacks from playerControls.js
 */
export function setCastControlCallbacks(callbacks) {
    castCallbacks = { ...castCallbacks, ...callbacks };
    console.log('✅ Cast callbacks registered:', Object.keys(callbacks));
}

/**
 * Export: Check if currently casting
 */
export function isCasting() {
    return remotePlayer?.isConnected || false;
}

/**
 * Export: Check if cast is playing
 */
export function isCastPlaying() {
    return remotePlayer?.isConnected && !remotePlayer?.isPaused;
}

/**
 * Export: Global casting state (for compatibility)
 */
export let globalCastingState = false;

// =============================================================================
// INITIALIZATION
// =============================================================================

/**
 * Initialize the Cast SDK
 * Call this when your page loads
 */
export function initializeCast() {
    console.log('🎬 Initializing Chromecast...');
    
    // Wait for Cast SDK to load
    window['__onGCastApiAvailable'] = (isAvailable) => {
        if (isAvailable) {
            initializeCastApi();
        } else {
            console.warn('⚠️ Cast SDK not available');
        }
    };
}

/**
 * Initialize Cast API
 */
function initializeCastApi() {
    const castContext = cast.framework.CastContext.getInstance();
    
    // Set options
    castContext.setOptions({
        receiverApplicationId: chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
        autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED
    });
    
    // Enable debug logging (optional - remove in production)
    castContext.setLoggerLevel(cast.framework.LoggerLevel.INFO);
    
    // Create remote player
    remotePlayer = new cast.framework.RemotePlayer();
    remotePlayerController = new cast.framework.RemotePlayerController(remotePlayer);
    
    // Set up event listeners
    setupCastEventListeners();
    
    console.log('✅ Cast SDK initialized');
}

/**
 * Set up all Cast event listeners
 */
function setupCastEventListeners() {
    // Connection changes
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.IS_CONNECTED_CHANGED,
        handleConnectionChange
    );
    
    // Queue/track changes (METHOD 1 - MAIN EVENT)
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.CURRENT_ITEM_CHANGED,
        handleTrackChange
    );
    
    // Media info changes (BACKUP)
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.MEDIA_INFO_CHANGED,
        handleMediaInfoChange
    );
    
    // Play/pause state changes
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.IS_PAUSED_CHANGED,
        handlePlayStateChange
    );
    
    // Volume changes
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.VOLUME_LEVEL_CHANGED,
        handleVolumeChange
    );
    
    remotePlayerController.addEventListener(
        cast.framework.RemotePlayerEventType.IS_MUTED_CHANGED,
        handleVolumeChange
    );
    
    console.log('✅ Cast event listeners registered');
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

/**
 * Handle connection changes
 */
function handleConnectionChange(e) {
    globalCastingState = e.value;
    
    if (e.value) {
        // Cast connected
        console.log('🚀 Cast session started');
        castSession = cast.framework.CastContext.getInstance().getCurrentSession();
        lastQueueIndex = -1; // Reset
        
        // Start time updates
        startCastTimeUpdates();
        
        // Call callback
        if (castCallbacks.onCastStart) {
            castCallbacks.onCastStart();
        }
    } else {
        // Cast disconnected
        console.log('🛑 Cast session ended');
        castSession = null;
        lastQueueIndex = -1;
        
        // Stop time updates
        stopCastTimeUpdates();
        
        // Call callback
        if (castCallbacks.onCastEnd) {
            castCallbacks.onCastEnd();
        }
    }
}

/**
 * Handle track changes - METHOD 1 (Queue Position)
 * This is the main track detection method
 */
function handleTrackChange() {
    console.log('🔔 CURRENT_ITEM_CHANGED event fired');
    
    if (!remotePlayer?.isConnected) {
        console.log('   ⚠️ Not connected, ignoring');
        return;
    }
    
    if (!castSession) {
        console.log('   ⚠️ No cast session, ignoring');
        return;
    }
    
    const mediaSession = castSession.getMediaSession();
    if (!mediaSession) {
        console.log('   ⚠️ No media session, ignoring');
        return;
    }
    
    const items = mediaSession.items || [];
    const currentItemId = mediaSession.currentItemId;
    
    console.log(`   Current item ID: ${currentItemId}`);
    console.log(`   Total items in queue: ${items.length}`);
    
    // Find the index in the queue
    let trackIndex = -1;
    for (let i = 0; i < items.length; i++) {
        if (items[i].itemId === currentItemId) {
            trackIndex = i;
            break;
        }
    }
    
    console.log(`   Calculated track index: ${trackIndex}`);
    console.log(`   Last queue index: ${lastQueueIndex}`);
    
    // Only trigger callback if index actually changed
    if (trackIndex >= 0 && trackIndex !== lastQueueIndex) {
        console.log(`🎵 Track changed from ${lastQueueIndex} to ${trackIndex}`);
        lastQueueIndex = trackIndex;
        currentCastIndex = trackIndex;
        
        // Call callback
        if (castCallbacks.onTrackChange) {
            castCallbacks.onTrackChange(trackIndex);
        }
    } else {
        console.log('   ℹ️ Index unchanged, not triggering callback');
    }
}

/**
 * Handle media info changes - BACKUP METHOD
 */
function handleMediaInfoChange() {
    if (!remotePlayer?.isConnected || !remotePlayer.mediaInfo) {
        return;
    }
    
    const mediaInfo = remotePlayer.mediaInfo;
    const metadata = mediaInfo.metadata;
    
    console.log('📻 Media info changed:', {
        title: metadata?.title,
        artist: metadata?.artist,
        album: metadata?.albumName
    });
}

/**
 * Handle play state changes
 */
function handlePlayStateChange() {
    if (!remotePlayer?.isConnected) return;
    
    const isPlaying = !remotePlayer.isPaused;
    console.log(`▶️ Play state changed: ${isPlaying ? 'playing' : 'paused'}`);
    
    if (castCallbacks.onPlayStateChange) {
        castCallbacks.onPlayStateChange(isPlaying);
    }
}

/**
 * Handle volume changes
 */
function handleVolumeChange() {
    if (!remotePlayer?.isConnected) return;
    
    const volume = remotePlayer.volumeLevel;
    const muted = remotePlayer.isMuted;
    
    if (castCallbacks.onVolumeChange) {
        castCallbacks.onVolumeChange(volume, muted);
    }
}

// =============================================================================
// TIME UPDATES (Progress Bar Sync)
// =============================================================================

/**
 * Start polling for time updates
 */
function startCastTimeUpdates() {
    // Clear any existing interval
    stopCastTimeUpdates();
    
    console.log('⏱️ Starting cast time updates');
    
    // Poll every second
    castTimeUpdateInterval = setInterval(() => {
        if (remotePlayer?.isConnected) {
            const currentTime = remotePlayer.currentTime || 0;
            const duration = remotePlayer.duration || 0;
            
            if (castCallbacks.onTimeUpdate) {
                castCallbacks.onTimeUpdate(currentTime, duration);
            }
        }
    }, 1000);
}

/**
 * Stop polling for time updates
 */
function stopCastTimeUpdates() {
    if (castTimeUpdateInterval) {
        clearInterval(castTimeUpdateInterval);
        castTimeUpdateInterval = null;
        console.log('⏹️ Stopped cast time updates');
    }
}

// =============================================================================
// CAST CONTROLS (Export these for playerControls.js to use)
// =============================================================================

/**
 * Play
 */
export function castPlay() {
    console.log('▶️ Cast: Play');
    if (castSession) {
        const mediaSession = castSession.getMediaSession();
        if (mediaSession) {
            mediaSession.play(new chrome.cast.media.PlayRequest());
        }
    }
}

/**
 * Pause
 */
export function castPause() {
    console.log('⏸️ Cast: Pause');
    if (castSession) {
        const mediaSession = castSession.getMediaSession();
        if (mediaSession) {
            mediaSession.pause(new chrome.cast.media.PauseRequest());
        }
    }
}

/**
 * Toggle play/pause
 */
export function castTogglePlayPause() {
    if (remotePlayer?.isPaused) {
        castPlay();
    } else {
        castPause();
    }
}

/**
 * Next track
 */
export function castNext() {
    console.log('⏭️ Cast: Next');
    if (castSession) {
        const mediaSession = castSession.getMediaSession();
        if (mediaSession) {
            mediaSession.queueNext(); // This triggers CURRENT_ITEM_CHANGED event
        }
    }
}

/**
 * Previous track
 */
export function castPrevious() {
    console.log('⏮️ Cast: Previous');
    if (castSession) {
        const mediaSession = castSession.getMediaSession();
        if (mediaSession) {
            mediaSession.queuePrev(); // This triggers CURRENT_ITEM_CHANGED event
        }
    }
}

/**
 * Jump to specific track
 */
export function castJumpToTrack(index) {
    console.log(`🎯 Cast: Jump to track ${index}`);
    
    if (!castSession) {
        console.warn('⚠️ No cast session');
        return;
    }
    
    const mediaSession = castSession.getMediaSession();
    if (!mediaSession) {
        console.warn('⚠️ No media session');
        return;
    }
    
    const items = mediaSession.items || [];
    if (index < 0 || index >= items.length) {
        console.warn(`⚠️ Index ${index} out of range (0-${items.length - 1})`);
        return;
    }
    
    // Jump to item by ID
    const itemId = items[index].itemId;
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(itemId);
    mediaSession.queueJump(jumpRequest);
    
    // This will trigger CURRENT_ITEM_CHANGED event automatically
}

// =============================================================================
// START CASTING (Called when user clicks cast button and selects tracks)
// =============================================================================

/**
 * Load and play a playlist on Chromecast
 * 
 * @param {Array} tracks - Array of track objects: [{url, title, artist, album, coverUrl}, ...]
 * @param {number} startIndex - Index to start playing from (default: 0)
 */
export function loadPlaylistAndCast(tracks, startIndex = 0) {
    console.log(`🎵 Loading ${tracks.length} tracks to Chromecast, starting at ${startIndex}`);
    
    // Store playlist for reference
    currentPlaylist = tracks;
    currentCastIndex = startIndex;
    
    const castSession = cast.framework.CastContext.getInstance().getCurrentSession();
    if (!castSession) {
        console.error('❌ No cast session available');
        return;
    }
    
    // Create queue items
    const queueItems = tracks.map((track, index) => {
        // Create media info for this track
        const mediaInfo = new chrome.cast.media.MediaInfo(track.url, 'audio/mpeg');
        
        // Set metadata
        mediaInfo.metadata = new chrome.cast.media.MusicTrackMediaMetadata();
        mediaInfo.metadata.title = track.title;
        mediaInfo.metadata.artist = track.artist;
        mediaInfo.metadata.albumName = track.album;
        
        if (track.coverUrl) {
            mediaInfo.metadata.images = [
                new chrome.cast.Image(track.coverUrl)
            ];
        }
        
        // Create queue item
        const queueItem = new chrome.cast.media.QueueItem(mediaInfo);
        queueItem.itemId = index; // IMPORTANT: Set itemId to track index
        
        return queueItem;
    });
    
    // Create queue load request
    const queueLoadRequest = new chrome.cast.media.QueueLoadRequest(queueItems);
    queueLoadRequest.startIndex = startIndex;
    queueLoadRequest.repeatMode = chrome.cast.media.RepeatMode.OFF;
    
    // Load the queue
    castSession.loadMedia(queueLoadRequest)
        .then(() => {
            console.log('✅ Playlist loaded to Chromecast');
            lastQueueIndex = startIndex;
        })
        .catch((error) => {
            console.error('❌ Failed to load playlist:', error);
        });
}

// =============================================================================
// HELPER: Extract tracks from DOM (for convenience)
// =============================================================================

/**
 * Helper function to extract tracks from your DOM
 * Call this before loadPlaylistAndCast()
 */
export function extractTracksFromDOM() {
    const trackItems = document.querySelectorAll('.track-item');
    const tracks = [];
    
    trackItems.forEach((item) => {
        const track = {
            url: item.dataset.path, // Adjust based on your HTML structure
            title: item.dataset.title,
            artist: item.dataset.artist,
            album: item.dataset.album,
            coverUrl: item.querySelector('.track-cover')?.src || ''
        };
        tracks.push(track);
    });
    
    console.log(`📋 Extracted ${tracks.length} tracks from DOM`);
    return tracks;
}

/**
 * Stop casting and end the session
 */
export function stopCasting() {
    console.log('🛑 Stopping cast session');
    
    const castContext = cast.framework.CastContext.getInstance();
    const session = castContext.getCurrentSession();
    
    if (session) {
        session.endSession(true);
        console.log('✅ Cast session ended');
    } else {
        console.warn('⚠️ No active cast session to stop');
    }
}

// =============================================================================
// AUTO-INITIALIZE
// =============================================================================

// Initialize when script loads
if (typeof cast !== 'undefined') {
    initializeCast();
} else {
    console.log('⏳ Waiting for Cast SDK to load...');
    // The __onGCastApiAvailable callback will handle initialization
}
