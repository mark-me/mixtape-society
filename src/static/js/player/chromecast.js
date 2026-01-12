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

export function initChromecast() {
    console.log('Initializing Chromecast...');
    
    window['__onGCastApiAvailable'] = function(isAvailable) {
        if (isAvailable) {
            console.log('Cast API available');
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
    };
    return mimeMap[ext] || 'audio/mpeg';
}

/**
 * Session & Receiver handling
*/

function sessionListener(session) {
    console.log('New session:', session.sessionId);
    currentCastSession = session;

    onCastSessionStart();

    if (session.media && session.media.length > 0) {
        attachMediaListener(session.media[0]);
    }

    session.addMediaListener(media => {
        console.log('New media loaded in session');
        attachMediaListener(media);
    });

    session.addUpdateListener(isAlive => {
        if (!isAlive) {
            console.log('Cast session ended');
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            onCastSessionEnd();
        }
    });
}

function attachMediaListener(media) {
    currentMedia = media;
    console.log('Attached media listener');

    media.addUpdateListener(isAlive => {
        if (isAlive) {
            const status = media.playerState;
            const currentTime = media.getEstimatedTime();
            const currentItemId = media.currentItemId;

            // Update cast play state
            castPlayState = status;

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

/**
 * Get current cast media metadata
 */
export function getCurrentCastMetadata() {
    if (!currentMedia || !currentMedia.media || !currentMedia.media.metadata) {
        return null;
    }
    
    return {
        title: currentMedia.media.metadata.title || 'Unknown',
        artist: currentMedia.media.metadata.artist || 'Unknown Artist',
        album: currentMedia.media.metadata.albumName || '',
        artwork: currentMedia.media.metadata.images || []
    };
}

/**
 * Get current cast time and duration
 */
export function getCurrentCastTime() {
    if (!currentMedia) {
        return { currentTime: 0, duration: 0 };
    }
    
    return {
        currentTime: currentMedia.getEstimatedTime() || 0,
        duration: currentMedia.media?.duration || 0
    };
}

function receiverListener(availability) {
    if (availability === chrome.cast.ReceiverAvailability.AVAILABLE) {
        console.log('Chromecast device found');
        const btn = document.getElementById('cast-button');
        if (btn) btn.hidden = false;
    } else {
        console.log('No Chromecast devices available');
    }
}

function onCastSessionStart() {
    console.log('Casting started');
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.add('connected');
        btn.title = 'Casting to device • Click to stop';
    }
    
    document.dispatchEvent(new CustomEvent('cast:started'));
}

function onCastSessionEnd() {
    console.log('Casting ended');
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
        () => console.log('Play command sent'),
        error => console.error('Play failed:', error)
    );
}

export function castPause() {
    if (!currentMedia) return;
    
    const pauseRequest = new chrome.cast.media.PauseRequest();
    currentMedia.pause(pauseRequest,
        () => console.log('Pause command sent'),
        error => console.error('Pause failed:', error)
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
        () => console.log(`Seek to ${currentTime}s`),
        error => console.error('Seek failed:', error)
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
        console.warn('Cannot get current index for next');
        return;
    }
    
    const nextIndex = currentIndex + 1;
    const nextItemId = getItemIdForIndex(nextIndex);
    
    if (nextItemId === null) {
        console.warn('No next track available');
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(nextItemId);
    currentMedia.queueJumpToItem(jumpRequest,
        () => console.log(`Next track (index ${nextIndex})`),
        error => console.error('Next failed:', error)
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
        console.warn('Cannot get current index for previous');
        return;
    }
    
    const prevIndex = currentIndex - 1;
    const prevItemId = getItemIdForIndex(prevIndex);
    
    if (prevItemId === null) {
        console.warn('No previous track available');
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(prevItemId);
    currentMedia.queueJumpToItem(jumpRequest,
        () => console.log(`Previous track (index ${prevIndex})`),
        error => console.error('Previous failed:', error)
    );
}

/**
 * Jump to a specific track by index
 */
export function castJumpToTrack(index) {
    if (!currentMedia) return;
    
    const targetItemId = getItemIdForIndex(index);
    
    if (targetItemId === null) {
        console.warn(`Cannot jump to index ${index} - out of bounds`);
        return;
    }
    
    const jumpRequest = new chrome.cast.media.QueueJumpRequest(targetItemId);
    
    currentMedia.queueJumpToItem(jumpRequest,
        () => console.log(`Jumped to track ${index}`),
        error => console.error('Jump failed:', error)
    );
}

/**
 * Build proper audio URL from track data
 * 
 * CRITICAL: Chromecast requires FULL absolute URLs (including protocol and domain)
 * Relative paths like "/play/..." will NOT work - they must be "https://example.com/play/..."
 * 
 * Strategy:
 * 1. Prefer DOM data-path (already has full encoded URL from Flask url_for)
 * 2. Fallback: construct from baseUrl + encoded path
 * 3. Convert to absolute URL using window.location.origin
 * 
 * Note: track.path is a RAW file path (e.g., "Artist/Album/01 - Song.mp3")
 *       It must be encoded before concatenating with baseUrl
 */
function buildTrackUrl(track, quality) {
    const trackItems = document.querySelectorAll('.track-item');
    
    let relativePath = null;
    
    // Try to find the matching track item in the DOM to get its pre-encoded data-path
    for (let item of trackItems) {
        if (item.dataset.title === track.track && item.dataset.artist === track.artist) {
            // Found matching track - use its data-path which is already a full URL from Flask
            // data-path format: "/play/Artist%2FAlbum%2F01%20Song.mp3" (already encoded)
            relativePath = item.dataset.path;
            
            // Add quality parameter
            // Check if URL already has query params
            const separator = relativePath.includes('?') ? '&' : '?';
            relativePath = `${relativePath}${separator}quality=${quality}`;
            
            break;
        }
    }
    
    // Fallback: construct URL from raw path
    if (!relativePath) {
        // IMPORTANT: track.path is RAW and needs encoding
        // Example: "Artist/Album/01 - Song.mp3" -> "Artist%2FAlbum%2F01%20-%20Song.mp3"
        const baseUrl = window.__mixtapeData?.baseUrl || '/play/';
        const encodedPath = encodeURIComponent(track.path);
        relativePath = `${baseUrl}${encodedPath}?quality=${quality}`;
    }
    
    // Convert to absolute URL
    // This handles protocol and domain: "/play/..." -> "https://example.com/play/..."
    const absoluteUrl = new URL(relativePath, window.location.origin).href;
    
    console.log(`Built URL: ${absoluteUrl}`);
    
    return absoluteUrl;
}

export function castMixtapePlaylist() {
    console.log('Starting cast request...');
    
    if (currentCastSession) {
        loadQueue(currentCastSession);
        return;
    }

    chrome.cast.requestSession(
        session => {
            currentCastSession = session;
            loadQueue(session);
        },
        error => console.error('Session request failed:', error)
    );
}

function loadQueue(session) {
    const tracks = window.__mixtapeData?.tracks || [];
    if (tracks.length === 0) {
        console.warn('No tracks available to cast');
        return;
    }

    console.log(`Loading queue with ${tracks.length} tracks`);

    const quality = localStorage.getItem('audioQuality') || 'medium';
    console.log(`Quality: ${quality}`);

    const queueItems = tracks.map((track, index) => {
        const trackUrl = buildTrackUrl(track, quality);
        const contentType = getAudioMimeFromPath(track.path, quality);
        
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

    console.log(`Queue load starting at index ${startIndex}`);

    session.queueLoad(
        queueRequest,
        () => {
            console.log('Playlist successfully queued on Chromecast');
            
            // CRITICAL: Stop and clear the local player completely
            const localPlayer = document.getElementById('main-player');
            if (localPlayer) {
                localPlayer.pause();
                localPlayer.src = '';  // Clear source to stop media session
                localPlayer.load();     // Reset the player
            }
        },
        (error) => {
            console.error('Failed to load queue on Chromecast:', error);
            console.error('Error code:', error.code);
            console.error('Error description:', error.description);
        }
    );
}

export function stopCasting() {
    if (currentCastSession) {
        console.log('Stopping cast...');
        currentCastSession.stop(() => {
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            onCastSessionEnd();
        }, onError);
    }
}
