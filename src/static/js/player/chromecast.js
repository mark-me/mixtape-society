// static/js/player/chromecast.js

const CAST_APP_ID = 'CC1AD845';

let currentCastSession = null;
let currentMedia = null;
let castControlCallbacks = {
    onTrackChange: null,
    onPlayStateChange: null,
    onTimeUpdate: null
};

// Track current cast play state
let castPlayState = 'IDLE'; // IDLE, PLAYING, PAUSED, BUFFERING

// Debug overlay for mobile
let debugOverlay = null;
let debugMessages = [];

function initDebugOverlay() {
    if (debugOverlay) return;
    
    debugOverlay = document.createElement('div');
    debugOverlay.id = 'cast-debug-overlay';
    debugOverlay.style.cssText = `
        position: fixed;
        bottom: 80px;
        right: 10px;
        max-width: 90%;
        max-height: 300px;
        overflow-y: auto;
        background: rgba(0, 0, 0, 0.9);
        color: #0f0;
        font-family: monospace;
        font-size: 10px;
        padding: 10px;
        border-radius: 5px;
        z-index: 9999;
        display: none;
    `;
    document.body.appendChild(debugOverlay);
    
    // Add toggle button
    const toggleBtn = document.createElement('button');
    toggleBtn.textContent = '🐛';
    toggleBtn.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 10px;
        z-index: 10000;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #007bff;
        color: white;
        border: none;
        font-size: 20px;
        cursor: pointer;
    `;
    toggleBtn.onclick = () => {
        debugOverlay.style.display = debugOverlay.style.display === 'none' ? 'block' : 'none';
    };
    document.body.appendChild(toggleBtn);
}

function debugLog(message, data = null) {
    const timestamp = new Date().toLocaleTimeString();
    const fullMessage = `[${timestamp}] ${message}`;
    
    console.log(fullMessage, data || '');
    
    debugMessages.unshift(fullMessage);
    if (data) {
        debugMessages.unshift('  → ' + JSON.stringify(data));
    }
    
    if (debugMessages.length > 50) {
        debugMessages = debugMessages.slice(0, 50);
    }
    
    if (debugOverlay) {
        debugOverlay.innerHTML = debugMessages.join('<br>');
    }
}

export function initChromecast() {
    initDebugOverlay();
    debugLog('Initializing Chromecast...');
    
    window['__onGCastApiAvailable'] = function(isAvailable) {
        if (isAvailable) {
            debugLog('Cast API available ✓');
            initializeCastApi();
        } else {
            debugLog('Cast API NOT available ✗');
            console.warn('Google Cast API not available');
        }
    };
}

function initializeCastApi() {
    const sessionRequest = new chrome.cast.SessionRequest(CAST_APP_ID);
    const apiConfig = new chrome.cast.ApiConfig(
        sessionRequest,
        sessionListener,
        receiverListener,
        chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED
    );

    chrome.cast.initialize(apiConfig, onInitSuccess, onError);
}

function onInitSuccess() {
    debugLog('Cast SDK initialized ✓');
    console.log('Cast SDK initialized successfully');

    // Fire the event so other modules know the API is ready
    document.dispatchEvent(new CustomEvent('cast:ready'));
}

function onError(error) {
    debugLog('Cast error', error);
    console.error('Cast initialization failed:', error);
}

function getAudioMimeFromPath(path, quality) {
    let ext = path.split('.').pop().toLowerCase();
    if (quality !== 'original') {
        ext = 'mp3';  // Transcoded files are MP3 from AudioCache
    }
    const mimeMap = {
        'mp3': 'audio/mpeg',
        'm4a': 'audio/mp4',
        'aac': 'audio/aac',
        'flac': 'audio/flac',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
    };
    return mimeMap[ext] || 'audio/mpeg';
}

/**
 * Session & Receiver handling
*/

function sessionListener(session) {
    debugLog('New session', session.sessionId);
    console.log('New session:', session.sessionId);
    currentCastSession = session;

    onCastSessionStart();

    if (session.media && session.media.length > 0) {
        attachMediaListener(session.media[0]);
    }

    session.addMediaListener(media => {
        debugLog('New media loaded');
        console.log('New media loaded in session');
        attachMediaListener(media);
    });

    session.addUpdateListener(isAlive => {
        if (!isAlive) {
            debugLog('Session ended');
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            onCastSessionEnd();
            console.log('Cast session ended');
        }
    });
}

function attachMediaListener(media) {
    currentMedia = media;
    debugLog('Media listener attached');
    console.log('Attached media listener');

    media.addUpdateListener(isAlive => {
        if (isAlive) {
            const status = media.playerState;
            const currentTime = media.getEstimatedTime();
            const currentItemId = media.currentItemId;

            // Update cast play state
            castPlayState = status;

            debugLog(`State: ${status}, Time: ${currentTime}s`);
            console.log(`Media update - State: ${status}, Time: ${currentTime}, ItemId: ${currentItemId}`);

            if (castControlCallbacks.onPlayStateChange) {
                castControlCallbacks.onPlayStateChange(status);
            }

            if (castControlCallbacks.onTimeUpdate) {
                castControlCallbacks.onTimeUpdate(currentTime);
            }

            if (media.media && media.media.queueData) {
                const currentIndex = findCurrentQueueIndex(currentItemId, media.media.queueData.items);
                if (currentIndex !== -1 && castControlCallbacks.onTrackChange) {
                    castControlCallbacks.onTrackChange(currentIndex);
                }
            }
        }
    });
}

function findCurrentQueueIndex(itemId, queueItems) {
    if (!queueItems) return -1;
    return queueItems.findIndex(item => item.itemId === itemId);
}

/**
 * Get the current queue index from the media
 */
function getCurrentQueueIndex() {
    if (!currentMedia || !currentMedia.media || !currentMedia.media.queueData) {
        return -1;
    }
    
    const currentItemId = currentMedia.currentItemId;
    return findCurrentQueueIndex(currentItemId, currentMedia.media.queueData.items);
}

/**
 * Get item ID for a specific queue index
 */
function getItemIdForIndex(index) {
    if (!currentMedia || !currentMedia.media || !currentMedia.media.queueData) {
        return null;
    }
    
    const items = currentMedia.media.queueData.items;
    if (index < 0 || index >= items.length) {
        return null;
    }
    
    return items[index].itemId;
}

function receiverListener(availability) {
    if (availability === chrome.cast.ReceiverAvailability.AVAILABLE) {
        debugLog('Chromecast device found ✓');
        const btn = document.getElementById('cast-button');
        if (btn) btn.hidden = false;
    } else {
        debugLog('No Chromecast devices');
    }
}

function onCastSessionStart() {
    debugLog('Casting started ✓');
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.add('connected');
        btn.title = 'Casting to device • Click to stop';
    }
    
    document.dispatchEvent(new CustomEvent('cast:started'));
}

function onCastSessionEnd() {
    debugLog('Casting ended');
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.remove('connected');
        btn.title = 'Cast to device';
    }
    
    document.dispatchEvent(new CustomEvent('cast:ended'));
}

export function setCastControlCallbacks(callbacks) {
    castControlCallbacks = { ...castControlCallbacks, ...callbacks };
}

export function isCasting() {
    return currentCastSession !== null && currentMedia !== null;
}

/**
 * Get current cast play state
 */
export function getCastPlayState() {
    return castPlayState;
}

/**
 * Check if cast is currently playing (not paused)
 */
export function isCastPlaying() {
    return castPlayState === 'PLAYING';
}

/**
 * Control functions that can be called from player UI
 */
export function castPlay() {
    if (!currentMedia) return;
    
    const playRequest = new chrome.cast.media.PlayRequest();
    currentMedia.play(playRequest, 
        () => debugLog('Play command sent ✓'),
        error => debugLog('Play failed', error)
    );
}

export function castPause() {
    if (!currentMedia) return;
    
    const pauseRequest = new chrome.cast.media.PauseRequest();
    currentMedia.pause(pauseRequest,
        () => debugLog('Pause command sent ✓'),
        error => debugLog('Pause failed', error)
    );
}

/**
 * Toggle play/pause state for Chromecast
 */
export function castTogglePlayPause() {
    if (!currentMedia) return;
    
    if (isCastPlaying()) {
        castPause();
    } else {
        castPlay();
    }
}

export function castSeek(currentTime) {
    if (!currentMedia) return;
    
    const seekRequest = new chrome.cast.media.SeekRequest();
    seekRequest.currentTime = currentTime;
    
    currentMedia.seek(seekRequest,
        () => debugLog(`Seek to ${currentTime}s ✓`),
        error => debugLog('Seek failed', error)
    );
}

/**
 * Navigate to next track in queue
 * Correctly computes the next itemId and jumps to it
 */
export function castNext() {
    if (!currentMedia) return;
    
    const currentIndex = getCurrentQueueIndex();
    if (currentIndex === -1) {
        debugLog('Cannot get current index for next');
        return;
    }
    
    const nextIndex = currentIndex + 1;
    const nextItemId = getItemIdForIndex(nextIndex);
    
    if (nextItemId === null) {
        debugLog('No next track available');
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(nextItemId);
    currentMedia.queueJumpToItem(jumpRequest,
        () => debugLog(`Next track (index ${nextIndex}) ✓`),
        error => debugLog('Next failed', error)
    );
}

/**
 * Navigate to previous track in queue
 * Correctly computes the previous itemId and jumps to it
 */
export function castPrevious() {
    if (!currentMedia) return;
    
    const currentIndex = getCurrentQueueIndex();
    if (currentIndex === -1) {
        debugLog('Cannot get current index for previous');
        return;
    }
    
    const prevIndex = currentIndex - 1;
    const prevItemId = getItemIdForIndex(prevIndex);
    
    if (prevItemId === null) {
        debugLog('No previous track available');
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(prevItemId);
    currentMedia.queueJumpToItem(jumpRequest,
        () => debugLog(`Previous track (index ${prevIndex}) ✓`),
        error => debugLog('Previous failed', error)
    );
}

/**
 * Jump to a specific track by index
 */
export function castJumpToTrack(index) {
    if (!currentMedia) return;
    
    const targetItemId = getItemIdForIndex(index);
    
    if (targetItemId === null) {
        debugLog(`Cannot jump to index ${index} - out of bounds`);
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(targetItemId);
    
    currentMedia.queueJumpToItem(jumpRequest,
        () => debugLog(`Jumped to track ${index} ✓`),
        error => debugLog('Jump failed', error)
    );
}

/**
 * Build proper audio URL from track data
 * 
 * Strategy:
 * 1. Prefer DOM data-path (already has full encoded URL from Flask url_for)
 * 2. Fallback: construct from baseUrl + encoded path
 * 
 * Note: track.path is a RAW file path (e.g., "Artist/Album/01 - Song.mp3")
 *       It must be encoded before concatenating with baseUrl
 */
function buildTrackUrl(track, quality) {
    const trackItems = document.querySelectorAll('.track-item');
    
    // Try to find the matching track item in the DOM to get its pre-encoded data-path
    for (let item of trackItems) {
        if (item.dataset.title === track.track && item.dataset.artist === track.artist) {
            // Found matching track - use its data-path which is already a full URL from Flask
            // data-path format: "/play/Artist%2FAlbum%2F01%20Song.mp3" (already encoded)
            const basePath = item.dataset.path;
            
            // Add quality parameter
            // Check if URL already has query params
            const separator = basePath.includes('?') ? '&' : '?';
            const url = `${basePath}${separator}quality=${quality}`;
            
            debugLog(`URL from DOM: ${url.substring(0, 60)}...`);
            return url;
        }
    }
    
    // Fallback: construct URL from raw path
    // IMPORTANT: track.path is RAW and needs encoding
    // Example: "Artist/Album/01 - Song.mp3" -> "Artist%2FAlbum%2F01%20-%20Song.mp3"
    const baseUrl = window.__mixtapeData?.baseUrl || window.location.origin + '/play/';
    const encodedPath = encodeURIComponent(track.path);
    const trackUrl = `${baseUrl}${encodedPath}?quality=${quality}`;
    
    debugLog(`Constructed URL: ${trackUrl.substring(0, 60)}...`);
    return trackUrl;
}

export function castMixtapePlaylist() {
    debugLog('Starting cast request...');
    
    if (currentCastSession) {
        loadQueue(currentCastSession);
        return;
    }

    chrome.cast.requestSession(
        session => {
            currentCastSession = session;
            loadQueue(session);
        },
        error => debugLog('Session request failed', error)
    );
}

function loadQueue(session) {
    const tracks = window.__mixtapeData?.tracks || [];
    if (tracks.length === 0) {
        debugLog('No tracks found! ✗');
        console.warn('No tracks available to cast');
        return;
    }

    debugLog(`Loading ${tracks.length} tracks...`);
    console.log('Loading queue with tracks:', tracks);

    const quality = localStorage.getItem('audioQuality') || 'medium';
    debugLog(`Quality: ${quality}`);

    const queueItems = tracks.map((track, index) => {
        const trackUrl = buildTrackUrl(track, quality);
        const contentType = getAudioMimeFromPath(track.path, quality);
        
        if (index === 0) {
            // Only log first track in detail to avoid clutter
            debugLog(`Track 0: ${track.track}`);
            debugLog(`Type: ${contentType}`);
        }
        
        console.log(`Track ${index}: ${track.track}`);
        console.log(`  URL: ${trackUrl}`);
        console.log(`  Content-Type: ${contentType}`);
        
        const mediaInfo = new chrome.cast.media.MediaInfo(trackUrl, contentType);
        mediaInfo.streamType = chrome.cast.media.StreamType.BUFFERED;
        
        if (track.duration) {
            mediaInfo.duration = track.duration;
        }
        
        const metadata = new chrome.cast.media.MusicTrackMediaMetadata();
        metadata.title = track.track || 'Unknown Title';
        metadata.artist = track.artist || 'Unknown Artist';
        metadata.albumName = track.album || '';
        metadata.trackNumber = index + 1;

        if (track.cover) {
            const coverUrl = new URL(track.cover, window.location.origin).href;
            metadata.images = [new chrome.cast.Image(coverUrl)];
        }

        mediaInfo.metadata = metadata;

        const queueItem = new chrome.cast.media.QueueItem(mediaInfo);
        queueItem.autoplay = true;
        queueItem.preloadTime = 5;
        
        return queueItem;
    });

    const queueRequest = new chrome.cast.media.QueueLoadRequest(queueItems);
    queueRequest.repeatMode = chrome.cast.media.RepeatMode.OFF;

    let startIndex = 0;
    if (Number.isInteger(window.currentTrackIndex) && 
        window.currentTrackIndex >= 0 && 
        window.currentTrackIndex < queueItems.length) {
        startIndex = window.currentTrackIndex;
    }
    queueRequest.startIndex = startIndex;

    debugLog(`Queue load: ${queueItems.length} tracks, start at ${startIndex}`);
    console.log(`Loading queue with ${queueItems.length} tracks, starting at index ${startIndex}`);

    session.queueLoad(
        queueRequest,
        () => {
            debugLog('Queue loaded successfully! ✓');
            console.log('Playlist successfully queued on Chromecast');
            const localPlayer = document.getElementById('main-player');
            if (localPlayer) localPlayer.pause();
        },
        (error) => {
            debugLog('Queue load FAILED ✗', {
                code: error.code,
                desc: error.description
            });
            console.error('Failed to load queue on Chromecast:', error);
            console.error('Error code:', error.code);
            console.error('Error description:', error.description);
            console.error('Error details:', JSON.stringify(error));
        }
    );
}

export function stopCasting() {
    if (currentCastSession) {
        debugLog('Stopping cast...');
        currentCastSession.stop(() => {
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            onCastSessionEnd();
        }, onError);
    }
}
