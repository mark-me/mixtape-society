// static/js/player/chromecast.js

const CAST_APP_ID = 'CC1AD845';

let currentCastSession = null;
let currentMedia = null;
let castControlCallbacks = {
    onTrackChange: null,
    onPlayStateChange: null,
    onTimeUpdate: null
};

export function initChromecast() {
    window['__onGCastApiAvailable'] = function(isAvailable) {
        if (isAvailable) {
            initializeCastApi();
        } else {
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
    console.log('Cast SDK initialized successfully');

    // Fire the event so other modules know the API is ready
    document.dispatchEvent(new CustomEvent('cast:ready'));
}

function onError(error) {
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
        // Add more if your collection has them
    };
    return mimeMap[ext] || 'audio/mpeg';  // Fallback
}

/**
 * Session & Receiver handling
*/

function sessionListener(session) {
    console.log('New session:', session.sessionId);
    currentCastSession = session;

    // This is the moment we consider casting "started/connected"
    onCastSessionStart();

    // Set up media listener for the session
    if (session.media && session.media.length > 0) {
        attachMediaListener(session.media[0]);
    }

    // Listen for new media being loaded
    session.addMediaListener(media => {
        console.log('New media loaded in session');
        attachMediaListener(media);
    });

    session.addUpdateListener(isAlive => {
        if (!isAlive) {
            currentCastSession = null;
            currentMedia = null;
            onCastSessionEnd();
            console.log('Cast session ended');
        }
    });
}

function attachMediaListener(media) {
    currentMedia = media;
    console.log('Attached media listener');

    media.addUpdateListener(isAlive => {
        if (isAlive) {
            // Update UI based on media status
            const status = media.playerState;
            const currentTime = media.getEstimatedTime();
            const currentItemId = media.currentItemId;

            // Notify callbacks about state changes
            if (castControlCallbacks.onPlayStateChange) {
                castControlCallbacks.onPlayStateChange(status);
            }

            if (castControlCallbacks.onTimeUpdate) {
                castControlCallbacks.onTimeUpdate(currentTime);
            }

            // Check if track changed
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

function receiverListener(availability) {
    if (availability === chrome.cast.ReceiverAvailability.AVAILABLE) {
        // Show cast button when at least one device is available
        const btn = document.getElementById('cast-button');
        if (btn) btn.hidden = false;
    }
}

/**
 *   UI state management
 */
function onCastSessionStart() {
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.add('connected');
        btn.title = 'Casting to device • Click to stop';
    }
    
    // Dispatch event so other modules know casting started
    document.dispatchEvent(new CustomEvent('cast:started'));
}

function onCastSessionEnd() {
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.remove('connected');
        btn.title = 'Cast to device';
    }
    
    // Dispatch event so other modules know casting ended
    document.dispatchEvent(new CustomEvent('cast:ended'));
}

/**
 * Register callbacks for cast control events
 */
export function setCastControlCallbacks(callbacks) {
    castControlCallbacks = { ...castControlCallbacks, ...callbacks };
}

/**
 * Check if currently casting
 */
export function isCasting() {
    return currentCastSession !== null && currentMedia !== null;
}

/**
 * Get current cast media controller
 */
function getMediaController() {
    if (!currentMedia) {
        console.warn('No active cast media');
        return null;
    }
    return new chrome.cast.media.MediaController(currentMedia);
}

/**
 * Control functions that can be called from player UI
 */
export function castPlay() {
    if (!currentMedia) return;
    
    const playRequest = new chrome.cast.media.PlayRequest();
    currentMedia.play(playRequest, 
        () => console.log('Cast play success'),
        error => console.error('Cast play error:', error)
    );
}

export function castPause() {
    if (!currentMedia) return;
    
    const pauseRequest = new chrome.cast.media.PauseRequest();
    currentMedia.pause(pauseRequest,
        () => console.log('Cast pause success'),
        error => console.error('Cast pause error:', error)
    );
}

export function castSeek(currentTime) {
    if (!currentMedia) return;
    
    const seekRequest = new chrome.cast.media.SeekRequest();
    seekRequest.currentTime = currentTime;
    
    currentMedia.seek(seekRequest,
        () => console.log('Cast seek success'),
        error => console.error('Cast seek error:', error)
    );
}

export function castNext() {
    if (!currentMedia) return;
    
    const queueNextRequest = new chrome.cast.media.QueueJumpRequest(1);
    currentMedia.queueJumpToItem(queueNextRequest,
        () => console.log('Cast next track success'),
        error => console.error('Cast next track error:', error)
    );
}

export function castPrevious() {
    if (!currentMedia) return;
    
    const queuePrevRequest = new chrome.cast.media.QueueJumpRequest(-1);
    currentMedia.queueJumpToItem(queuePrevRequest,
        () => console.log('Cast previous track success'),
        error => console.error('Cast previous track error:', error)
    );
}

export function castJumpToTrack(index) {
    if (!currentMedia || !currentMedia.media || !currentMedia.media.queueData) return;
    
    const items = currentMedia.media.queueData.items;
    if (index < 0 || index >= items.length) return;
    
    const targetItemId = items[index].itemId;
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(targetItemId);
    
    currentMedia.queueJumpToItem(jumpRequest,
        () => console.log(`Cast jumped to track ${index}`),
        error => console.error('Cast jump to track error:', error)
    );
}

/**
**  Main casting function
*/

export function castMixtapePlaylist() {
    if (currentCastSession) {
        loadQueue(currentCastSession);
        return;
    }

    chrome.cast.requestSession(
        session => {
            currentCastSession = session;
            loadQueue(session);
        },
        onError
    );
}

function loadQueue(session) {
    const tracks = window.__mixtapeData?.tracks || [];
    if (tracks.length === 0) {
        console.warn('No tracks available to cast');
        return;
    }

    const quality = localStorage.getItem('audioQuality') || 'medium';
    const baseUrl = window.__mixtapeData?.baseUrl || window.location.origin + '/play/';

    // Build the queue items
    const queueItems = tracks.map((track, index) => {
        const trackUrl = `${baseUrl}${encodeURIComponent(track.path)}?quality=${quality}`;
        const contentType = getAudioMimeFromPath(track.path, quality);
        
        // Create MediaInfo with proper constructor
        const mediaInfo = new chrome.cast.media.MediaInfo(trackUrl, contentType);
        
        // Set stream type explicitly
        mediaInfo.streamType = chrome.cast.media.StreamType.BUFFERED;
        
        // Create metadata
        const metadata = new chrome.cast.media.MusicTrackMediaMetadata();
        metadata.title = track.track || 'Unknown Title';
        metadata.artist = track.artist || 'Unknown Artist';
        metadata.albumName = track.album || '';

        if (track.cover) {
            const coverUrl = new URL(track.cover, window.location.origin).href;
            metadata.images = [new chrome.cast.Image(coverUrl)];
        }

        mediaInfo.metadata = metadata;

        // Create queue item
        const queueItem = new chrome.cast.media.QueueItem(mediaInfo);
        queueItem.autoplay = true;
        queueItem.preloadTime = 5; // Preload 5 seconds before track ends
        
        return queueItem;
    });

    // Create the queue request
    const queueRequest = new chrome.cast.media.QueueLoadRequest(queueItems);
    queueRequest.repeatMode = chrome.cast.media.RepeatMode.OFF;

    // Determine start index
    let startIndex = 0;
    if (Number.isInteger(window.currentTrackIndex) && 
        window.currentTrackIndex >= 0 && 
        window.currentTrackIndex < queueItems.length) {
        startIndex = window.currentTrackIndex;
    }
    queueRequest.startIndex = startIndex;

    console.log(`Loading queue with ${queueItems.length} tracks, starting at index ${startIndex}`);

    // Load the queue
    session.queueLoad(
        queueRequest,
        () => {
            console.log('Playlist successfully queued on Chromecast');
            // Pause the local HTML5 player when casting starts
            const localPlayer = document.getElementById('main-player');
            if (localPlayer) localPlayer.pause();
        },
        (error) => {
            console.error('Failed to load queue on Chromecast:', error);
            console.error('Error details:', JSON.stringify(error));
        }
    );
}

// Stop casting
export function stopCasting() {
    if (currentCastSession) {
        currentCastSession.stop(() => {
            currentCastSession = null;
            currentMedia = null;
            onCastSessionEnd();
        }, onError);
    }
}
