// static/js/player/androidAuto.js

/**
 * Android Auto optimized Media Session management
 * Provides reliable controls and metadata for in-car experience
 */

// Track which audio element has listeners attached
// This prevents duplicates while allowing reattachment to new elements
let listenersAttachedTo = null;

const ANDROID_AUTO_ARTWORK_SIZES = [
    { size: '96x96', type: 'image/jpeg' },    // Required minimum
    { size: '128x128', type: 'image/jpeg' },  // Recommended
    { size: '192x192', type: 'image/jpeg' },  // Optimal
    { size: '256x256', type: 'image/jpeg' },  // High quality
    { size: '512x512', type: 'image/jpeg' }   // Maximum
];

/**
 * Detect Android Auto connection
 */
export function isAndroidAutoConnected() {
    // Android Auto sets specific user agent strings
    const ua = navigator.userAgent.toLowerCase();
    const isAndroidAuto = ua.includes('android') && (
        ua.includes('vehicle') || 
        ua.includes('automotive') ||
        document.referrer.includes('android-auto')
    );
    
    // Also check for Android Auto specific APIs
    const hasAutoAPIs = 'getInstalledRelatedApps' in navigator;
    
    return isAndroidAuto || hasAutoAPIs;
}

/**
 * Setup comprehensive Media Session for Android Auto
 */
export function setupAndroidAutoMediaSession(metadata, playerControls, audioElement) {
    if (!('mediaSession' in navigator)) {
        console.warn('Media Session API not available');
        return;
    }

    console.log('🚗 Setting up Android Auto Media Session');

    // 1. Set metadata with optimized artwork
    const artwork = prepareArtwork(metadata.artwork);
    
    navigator.mediaSession.metadata = new MediaMetadata({
        title: metadata.title || 'Unknown Track',
        artist: metadata.artist || 'Unknown Artist',
        album: metadata.album || 'Mixtape',
        artwork: artwork
    });

    // 2. Set playback state
    navigator.mediaSession.playbackState = audioElement.paused ? 'paused' : 'playing';

    // 3. Set all action handlers
    setupActionHandlers(playerControls, audioElement);

    // 4. Set position state
    updatePositionState(audioElement);

    // 5. Listen for audio events to keep state in sync
    setupAudioEventListeners(audioElement);

    console.log('✅ Android Auto Media Session ready');
}

/**
 * Prepare artwork in multiple sizes for Android Auto
 */
function prepareArtwork(originalArtwork) {
    if (!originalArtwork || originalArtwork.length === 0) {
        return [];
    }

    // Get the first artwork URL
    const artworkUrl = originalArtwork[0].src;
    
    // Android Auto requires multiple sizes
    // Return same image at different declared sizes
    return ANDROID_AUTO_ARTWORK_SIZES.map(spec => ({
        src: artworkUrl,
        sizes: spec.size,
        type: spec.type
    }));
}

/**
 * Setup all Media Session action handlers
 */
function setupActionHandlers(playerControls, audioElement) {
    // Basic playback controls
    navigator.mediaSession.setActionHandler('play', () => {
        console.log('🚗 Android Auto: Play');
        playerControls.play();
    });

    navigator.mediaSession.setActionHandler('pause', () => {
        console.log('🚗 Android Auto: Pause');
        playerControls.pause();
    });

    navigator.mediaSession.setActionHandler('stop', () => {
        console.log('🚗 Android Auto: Stop');
        playerControls.pause();
        audioElement.currentTime = 0;
    });

    // Track navigation
    navigator.mediaSession.setActionHandler('previoustrack', () => {
        console.log('🚗 Android Auto: Previous track');
        playerControls.previous();
    });

    navigator.mediaSession.setActionHandler('nexttrack', () => {
        console.log('🚗 Android Auto: Next track');
        playerControls.next();
    });

    // Seeking (CRITICAL for Android Auto)
    navigator.mediaSession.setActionHandler('seekto', (details) => {
        console.log('🚗 Android Auto: Seek to', details.seekTime);
        if (details.seekTime !== undefined) {
            audioElement.currentTime = details.seekTime;
            updatePositionState(audioElement);
        }
    });

    // Optional: Seek forward/backward (10 seconds)
    navigator.mediaSession.setActionHandler('seekforward', () => {
        console.log('🚗 Android Auto: Seek forward');
        audioElement.currentTime = Math.min(
            audioElement.currentTime + 10,
            audioElement.duration
        );
        updatePositionState(audioElement);
    });

    navigator.mediaSession.setActionHandler('seekbackward', () => {
        console.log('🚗 Android Auto: Seek backward');
        audioElement.currentTime = Math.max(
            audioElement.currentTime - 10,
            0
        );
        updatePositionState(audioElement);
    });
}

/**
 * Update Media Session position state
 */
function updatePositionState(audioElement) {
    if (!('setPositionState' in navigator.mediaSession)) return;
    
    if (audioElement.duration && 
        !isNaN(audioElement.duration) && 
        isFinite(audioElement.duration) && 
        audioElement.duration > 0) {
        
        try {
            navigator.mediaSession.setPositionState({
                duration: audioElement.duration,
                playbackRate: audioElement.playbackRate,
                position: Math.min(audioElement.currentTime, audioElement.duration)
            });
        } catch (error) {
            console.warn('Could not set position state:', error);
        }
    }
}

/**
 * Setup audio element event listeners to keep Media Session in sync
 */
function setupAudioEventListeners(audioElement) {
    // Check if listeners are already attached to this specific element
    if (listenersAttachedTo === audioElement) {
        console.log('🚗 Event listeners already attached to this audio element');
        return;
    }
    
    // If we had listeners on a different element, we could detach them here
    // (Not necessary for this use case since we only have one player element)
    
    // Mark this element as having listeners
    listenersAttachedTo = audioElement;
    console.log('🚗 Installing Android Auto event listeners');
    
    // Update playback state
    audioElement.addEventListener('play', () => {
        navigator.mediaSession.playbackState = 'playing';
        console.log('🚗 Playback state: playing');
    });

    audioElement.addEventListener('pause', () => {
        navigator.mediaSession.playbackState = 'paused';
        console.log('🚗 Playback state: paused');
    });

    audioElement.addEventListener('ended', () => {
        navigator.mediaSession.playbackState = 'none';
        console.log('🚗 Playback state: none');
    });

    // Update position every second during playback
    let positionUpdateInterval;
    
    audioElement.addEventListener('play', () => {
        // Update position state every second
        positionUpdateInterval = setInterval(() => {
            updatePositionState(audioElement);
        }, 1000);
    });

    audioElement.addEventListener('pause', () => {
        clearInterval(positionUpdateInterval);
    });

    audioElement.addEventListener('ended', () => {
        clearInterval(positionUpdateInterval);
    });

    // Update when seeking
    audioElement.addEventListener('seeked', () => {
        updatePositionState(audioElement);
    });

    // Update when duration becomes available
    audioElement.addEventListener('durationchange', () => {
        updatePositionState(audioElement);
    });

    // Update when playback rate changes
    audioElement.addEventListener('ratechange', () => {
        updatePositionState(audioElement);
    });
}

/**
 * Clear Media Session (when switching modes, e.g., to Chromecast)
 */
export function clearAndroidAutoMediaSession() {
    if (!('mediaSession' in navigator)) return;

    console.log('🚗 Clearing Android Auto Media Session');
    
    navigator.mediaSession.playbackState = 'none';
    navigator.mediaSession.metadata = null;
    
    const actions = [
        'play', 'pause', 'stop',
        'previoustrack', 'nexttrack',
        'seekbackward', 'seekforward', 'seekto'
    ];
    
    actions.forEach(action => {
        try {
            navigator.mediaSession.setActionHandler(action, null);
        } catch (e) {
            // Action may not be supported, that's fine
        }
    });
}

/**
 * Log Android Auto connection status
 */
export function logAndroidAutoStatus() {
    const isConnected = isAndroidAutoConnected();
    
    console.log('🚗 Android Auto Status:');
    console.log(`   Connected: ${isConnected ? 'Yes ✅' : 'No'}`);
    console.log(`   Media Session API: ${'mediaSession' in navigator ? 'Available ✅' : 'Not Available ❌'}`);
    console.log(`   User Agent: ${navigator.userAgent}`);
    
    if (isConnected) {
        console.log('💡 Tip: Keep phone screen unlocked for best Android Auto experience');
    }
}
