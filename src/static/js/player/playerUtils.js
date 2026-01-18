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
 * Detect Android device and version
 */
export function detectAndroid() {
    const ua = navigator.userAgent;
    const isAndroid = /android/i.test(ua);

    if (!isAndroid) return null;

    // Extract Android version
    const match = ua.match(/Android (\d+)\.?(\d+)?/);
    const major = match ? parseInt(match[1], 10) : 0;
    const minor = match ? parseInt(match[2], 10) : 0;

    // Check for Android Auto indicators
    const isAndroidAuto = ua.toLowerCase().includes('vehicle') ||
                         ua.toLowerCase().includes('automotive');

    return {
        isAndroid: true,
        version: major,
        versionString: `${major}.${minor}`,
        supportsMediaSession: major >= 5, // Android 5.0+
        isAndroidAuto: isAndroidAuto,
        isPWA: window.matchMedia('(display-mode: standalone)').matches
    };
}

/**
 * Log device and feature support
 */
export function logDeviceInfo() {
    const iOS = detectiOS();
    const android = detectAndroid();

    if (iOS) {
        console.log('📱 iOS Device Detected');
        console.log(`   Version: iOS ${iOS.versionString}`);
        console.log(`   PWA Mode: ${iOS.isPWA ? 'Yes' : 'No'}`);
        console.log(`   Media Session: ${iOS.supportsMediaSession ? 'Supported ✅' : 'Not Supported (need iOS 15+) ❌'}`);
    } else if (android) {
        console.log('🤖 Android Device Detected');
        console.log(`   Version: Android ${android.versionString}`);
        console.log(`   PWA Mode: ${android.isPWA ? 'Yes' : 'No'}`);
        console.log(`   Android Auto: ${android.isAndroidAuto ? 'Connected ✅' : 'Not Connected'}`);
        console.log(`   Media Session: ${android.supportsMediaSession ? 'Supported ✅' : 'Not Supported ❌'}`);
    } else {
        console.log('💻 Desktop/Other Device');
    }

    console.log(`   Media Session API: ${'mediaSession' in navigator ? 'Available ✅' : 'Not Available ❌'}`);
    console.log(`   Cast API: ${typeof chrome !== 'undefined' && chrome.cast ? 'Available ✅' : 'Not Available ❌'}`);
}

/**
 * Completely silence the local player
 * Used when casting starts to prevent duplicate media controls
 */
export function silenceLocalPlayer() {
    const player = document.getElementById('main-player');
    if (!player) return;

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
}

/**
 * Re-enable the local player
 * Used when casting ends to restore local playback
 */
export function enableLocalPlayer() {
    const player = document.getElementById('main-player');
    if (!player) return;

    // Restore controls
    player.setAttribute('controls', '');

    // Restore volume and unmute
    player.volume = 1.0;
    player.muted = false;

    // Restore to tab order
    player.removeAttribute('tabindex');
}

/**
 * Clear Media Session API completely
 * Removes all metadata and action handlers
 */
export function clearMediaSession() {
    if (!('mediaSession' in navigator)) return;

    try {
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
    } catch (error) {
        console.warn('Error clearing Media Session:', error);
    }
}

/**
 * Setup Media Session for local player control
 * This is for basic iOS/desktop support
 * Android Auto uses its own optimized version in androidAuto.js
 */
export function setupLocalMediaSession(metadata, playerControls) {
    if (!('mediaSession' in navigator)) return;

    try {
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

        // Basic seeking support
        navigator.mediaSession.setActionHandler('seekto', (details) => {
            if (details.seekTime !== undefined) {
                const player = document.getElementById('main-player');
                if (player) {
                    player.currentTime = details.seekTime;
                }
            }
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
    const extension = url.split('.').pop().split('?')[0].toLowerCase(); // Handle query params
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
 * Extract metadata from DOM track element with platform-optimized artwork sizes
 * Uses the new size-optimized cover API endpoints
 */
export function extractMetadataFromDOM(trackElement) {
    const iOS = detectiOS();
    const android = detectAndroid();
    const coverImg = trackElement.querySelector('.track-cover');
    let artwork = [];

    if (coverImg && coverImg.src) {
        const mimeType = getMimeTypeFromUrl(coverImg.src);

        // Parse the cover URL to extract the slug
        // Assuming covers are served as: /covers/slug.jpg or /covers/slug_NxN.jpg
        const coverUrl = new URL(coverImg.src, window.location.origin);
        const coverPath = coverUrl.pathname; // e.g., /covers/artist_album.jpg
        const slug = coverPath.split('/').pop().replace('.jpg', '').replace(/_\d+x\d+$/, '');

        // Build size-optimized artwork URLs using the new backend
        // CRITICAL: Car systems require absolute HTTPS URLs
        const baseUrl = window.location.origin;

        if (iOS) {
            // iOS optimization - prefers larger sizes for lock screen
            artwork = [
                {
                    src: `${baseUrl}/covers/${slug}_512x512.jpg`,
                    sizes: '512x512',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_256x256.jpg`,
                    sizes: '256x256',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_192x192.jpg`,
                    sizes: '192x192',
                    type: mimeType
                }
            ];
        } else if (android && android.isAndroidAuto) {
            // Android Auto - requires full size spectrum with absolute URLs
            artwork = [
                {
                    src: `${baseUrl}/covers/${slug}_96x96.jpg`,
                    sizes: '96x96',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_128x128.jpg`,
                    sizes: '128x128',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_192x192.jpg`,
                    sizes: '192x192',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_256x256.jpg`,
                    sizes: '256x256',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_512x512.jpg`,
                    sizes: '512x512',
                    type: mimeType
                }
            ];
        } else {
            // Desktop/other - simpler set
            artwork = [
                {
                    src: `${baseUrl}/covers/${slug}_192x192.jpg`,
                    sizes: '192x192',
                    type: mimeType
                },
                {
                    src: `${baseUrl}/covers/${slug}_512x512.jpg`,
                    sizes: '512x512',
                    type: mimeType
                }
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
