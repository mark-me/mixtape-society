// static/js/player/playerUtils.js

/**
 * Shared utilities for player management
 * Centralizes logic for silencing/enabling local player and Media Session
 */

/**
 * Detect iOS device and version
 */
export function detectiOS() {
    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    
    if (!isIOS) return null;
    
    // Extract iOS version
    const match = ua.match(/OS (\d+)_(\d+)/);
    const major = match ? parseInt(match[1], 10) : 0;
    const minor = match ? parseInt(match[2], 10) : 0;
    
    return {
        isIOS: true,
        version: major,
        versionString: `${major}.${minor}`,
        supportsMediaSession: major >= 15,
        isPWA: window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches
    };
}

/**
 * Log device and feature support
 */
export function logDeviceInfo() {
    const iOS = detectiOS();
    
    if (iOS) {
        console.log('📱 iOS Device Detected');
        console.log(`   Version: iOS ${iOS.versionString}`);
        console.log(`   PWA Mode: ${iOS.isPWA ? 'Yes' : 'No'}`);
        console.log(`   Media Session: ${iOS.supportsMediaSession ? 'Supported ✓' : 'Not Supported (need iOS 15+) ✗'}`);
    } else {
        console.log('📱 Android/Desktop Device');
    }
    
    console.log(`   Media Session API: ${'mediaSession' in navigator ? 'Available ✓' : 'Not Available ✗'}`);
    console.log(`   Cast API: ${typeof chrome !== 'undefined' && chrome.cast ? 'Available ✓' : 'Not Available ✗'}`);
}

/**
 * Completely silence the local player
 * Used when casting starts to prevent duplicate media controls
 * AGGRESSIVELY removes all player attributes
 */
export function silenceLocalPlayer() {
    const player = document.getElementById('main-player');
    if (!player) return;
    
    console.log('🔇 AGGRESSIVELY silencing local player');
    
    // Pause and clear source
    player.pause();
    player.src = '';
    player.load();
    
    // Remove ALL player attributes that could trigger Media Session
    player.removeAttribute('controls');
    player.removeAttribute('autoplay');
    
    // Set volume to 0 as extra safety
    player.volume = 0;
    player.muted = true;
    
    // Remove from tab order
    player.setAttribute('tabindex', '-1');
    
    console.log('✅ Local player completely silenced');
}

/**
 * Re-enable the local player
 * Used when casting ends to restore local playback
 */
export function enableLocalPlayer() {
    const player = document.getElementById('main-player');
    if (!player) return;
    
    console.log('🔊 Re-enabling local player');
    
    // Restore controls
    player.setAttribute('controls', '');
    
    // Restore volume and unmute
    player.volume = 1.0;
    player.muted = false;
    
    // Restore to tab order
    player.removeAttribute('tabindex');
    
    console.log('✅ Local player re-enabled');
}

/**
 * Clear Media Session API completely
 * Removes all metadata and action handlers
 * AGGRESSIVELY prevents re-creation
 */
export function clearMediaSession() {
    if (!('mediaSession' in navigator)) return;
    
    try {
        console.log('🧹 AGGRESSIVELY clearing Media Session');
        
        // Set playback state to 'none' FIRST
        navigator.mediaSession.playbackState = 'none';
        
        // Clear metadata
        navigator.mediaSession.metadata = null;
        
        // Remove ALL action handlers (including seek and stop)
        const actions = [
            'play', 'pause', 'stop',
            'previoustrack', 'nexttrack',
            'seekbackward', 'seekforward',
            'seekto'
        ];
        
        actions.forEach(action => {
            try {
                navigator.mediaSession.setActionHandler(action, null);
            } catch (e) {
                // Action may not be supported, that's fine
            }
        });
        
        // Try to clear position state
        try {
            navigator.mediaSession.setPositionState(null);
        } catch (e) {
            // May not be supported
        }
        
        console.log('✅ Media Session cleared completely');
    } catch (error) {
        console.warn('Error clearing Media Session:', error);
    }
}

/**
 * REMOVED: setupCastMediaSession
 * When casting, we DO NOT create our own Media Session.
 * The Chromecast creates its own native media control with all features.
 * We only create Media Session for LOCAL playback.
 */

/**
 * Setup Media Session for local player control
 */
export function setupLocalMediaSession(metadata, playerControls) {
    if (!('mediaSession' in navigator)) return;

    try {
        console.log('🎵 Setting up Media Session for LOCAL playback');
        
        navigator.mediaSession.metadata = new MediaMetadata({
            title: metadata.title,
            artist: metadata.artist,
            album: metadata.album,
            artwork: metadata.artwork
        });

        navigator.mediaSession.setActionHandler('play', () => {
            playerControls.play();
        });

        navigator.mediaSession.setActionHandler('pause', () => {
            playerControls.pause();
        });

        navigator.mediaSession.setActionHandler('previoustrack', () => {
            playerControls.previous();
        });

        navigator.mediaSession.setActionHandler('nexttrack', () => {
            playerControls.next();
        });
    } catch (error) {
        console.warn('Error updating Media Session:', error);
    }
}

/**
 * Update Media Session position state
 */
export function updateMediaSessionPosition(currentTime, duration, playbackRate = 1.0) {
    if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;

    if (duration && !isNaN(duration) && isFinite(duration) && duration > 0) {
        try {
            navigator.mediaSession.setPositionState({
                duration: duration,
                playbackRate: playbackRate,
                position: Math.min(currentTime, duration)
            });
        } catch (error) {
            console.debug('Could not set position state:', error);
        }
    }
}

/**
 * Update Media Session playback state
 */
export function updateMediaSessionPlaybackState(state) {
    if (!('mediaSession' in navigator)) return;
    
    try {
        navigator.mediaSession.playbackState = state; // 'none', 'paused', 'playing'
    } catch (e) {
        console.warn('Error updating playback state:', e);
    }
}

/**
 * Get MIME type from URL extension
 */
export function getMimeTypeFromUrl(url) {
    const extension = url.split('.').pop().toLowerCase();
    const mimeMap = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
    };
    return mimeMap[extension] || 'image/jpeg';
}

/**
 * Extract metadata from DOM track element with iOS-optimized artwork sizes
 */
export function extractMetadataFromDOM(trackElement) {
    const iOS = detectiOS();
    const coverImg = trackElement.querySelector('.track-cover');
    let artwork = [];

    if (coverImg && coverImg.src) {
        const mimeType = getMimeTypeFromUrl(coverImg.src);
        const absoluteSrc = new URL(coverImg.src, window.location.origin).href;
        
        // iOS prefers specific sizes, with 512x512 being most reliable
        if (iOS) {
            artwork = [
                { src: absoluteSrc, sizes: '512x512', type: mimeType }, // Primary for iOS
                { src: absoluteSrc, sizes: '256x256', type: mimeType },
                { src: absoluteSrc, sizes: '128x128', type: mimeType }
            ];
        } else {
            // Android supports more sizes
            artwork = [
                { src: absoluteSrc, sizes: '96x96',   type: mimeType },
                { src: absoluteSrc, sizes: '128x128', type: mimeType },
                { src: absoluteSrc, sizes: '192x192', type: mimeType },
                { src: absoluteSrc, sizes: '256x256', type: mimeType },
                { src: absoluteSrc, sizes: '384x384', type: mimeType },
                { src: absoluteSrc, sizes: '512x512', type: mimeType }
            ];
        }
    }

    return {
        title: trackElement.dataset.title || 'Unknown',
        artist: trackElement.dataset.artist || 'Unknown Artist',
        album: trackElement.dataset.album || '',
        artwork: artwork
    };
}
