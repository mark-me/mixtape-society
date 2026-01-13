// static/js/player/chromecast.js
import { silenceLocalPlayer, clearMediaSession } from './playerUtils.js';

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

// Global casting state - exported so playerControls can check it directly
export let globalCastingState = false;

export function initChromecast() {
    console.log('🎬 Initializing Chromecast...');

    window['__onGCastApiAvailable'] = function(isAvailable) {
        if (isAvailable) {
            console.log('✅ Cast API available');
            initializeCastApi();
        } else {
            console.warn('❌ Google Cast API not available');
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
    console.log('✅ Cast SDK initialized successfully');
    document.dispatchEvent(new CustomEvent('cast:ready'));
}

function onError(error) {
    console.error('❌ Cast initialization failed:', error);
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
    console.log('🔗 New cast session:', session.sessionId);
    currentCastSession = session;

    // CRITICAL: Set global state IMMEDIATELY
    globalCastingState = true;
    console.log(`🎯 globalCastingState set to: ${globalCastingState}`);

    // Fire event and silence player IMMEDIATELY
    onCastSessionStart();

    if (session.media && session.media.length > 0) {
        attachMediaListener(session.media[0]);
    }

    session.addMediaListener(media => {
        console.log('🎵 New media loaded in session');
        attachMediaListener(media);
    });

    session.addUpdateListener(isAlive => {
        if (!isAlive) {
            console.log('💔 Cast session ended');
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            globalCastingState = false;
            console.log(`🎯 globalCastingState set to: ${globalCastingState}`);
            onCastSessionEnd();
        }
    });
}

function attachMediaListener(media) {
    currentMedia = media;
    console.log('🎧 Attached media listener');

    // Setup Media Session for this media immediately
    updateMediaSessionForCast(media);

    media.addUpdateListener(isAlive => {
        if (isAlive) {
            const status = media.playerState;
            const currentTime = media.getEstimatedTime();
            const currentItemId = media.currentItemId;

            // Update cast play state
            castPlayState = status;

            console.log(`📻 Media update - State: ${status}, Time: ${currentTime.toFixed(1)}s, ItemId: ${currentItemId}`);

            // Update Media Session playback state
            updateMediaSessionPlaybackState(status);

            // Update position state
            if (media.media && media.media.duration) {
                updateMediaSessionPosition(currentTime, media.media.duration);
            }

            if (castControlCallbacks.onPlayStateChange) {
                castControlCallbacks.onPlayStateChange(status);
            }

            if (castControlCallbacks.onTimeUpdate) {
                castControlCallbacks.onTimeUpdate(currentTime);
            }

            if (media.media && media.media.queueData) {
                const currentIndex = findCurrentQueueIndex(currentItemId, media.media.queueData.items);
                if (currentIndex !== -1) {
                    // Update Media Session when track changes
                    updateMediaSessionForCast(media);
                    
                    if (castControlCallbacks.onTrackChange) {
                        castControlCallbacks.onTrackChange(currentIndex);
                    }
                }
            }
        }
    });
}

/**
 * Setup/update Media Session API to mirror Chromecast state
 * This creates the unified media control with metadata
 */
function updateMediaSessionForCast(media) {
    if (!('mediaSession' in navigator)) {
        console.log('⚠️ Media Session API not available');
        return;
    }

    if (!media || !media.media || !media.media.metadata) {
        console.log('⚠️ No metadata available for Media Session');
        return;
    }

    const metadata = media.media.metadata;
    
    console.log('🎵 Updating Media Session for Cast:');
    console.log(`   Title: ${metadata.title}`);
    console.log(`   Artist: ${metadata.artist}`);
    console.log(`   Album: ${metadata.albumName}`);

    try {
        // Create MediaMetadata with Chromecast info
        navigator.mediaSession.metadata = new MediaMetadata({
            title: metadata.title || 'Unknown',
            artist: metadata.artist || 'Unknown Artist',
            album: metadata.albumName || '',
            artwork: metadata.images?.map(img => ({
                src: img.url,
                sizes: '512x512',
                type: 'image/jpeg'
            })) || []
        });

        // Set playback state
        const state = media.playerState === 'PLAYING' ? 'playing' : 
                     media.playerState === 'PAUSED' ? 'paused' : 'none';
        navigator.mediaSession.playbackState = state;

        // Setup action handlers that control Chromecast
        navigator.mediaSession.setActionHandler('play', () => {
            console.log('🎮 Media Session: play');
            castPlay();
        });

        navigator.mediaSession.setActionHandler('pause', () => {
            console.log('🎮 Media Session: pause');
            castPause();
        });

        navigator.mediaSession.setActionHandler('previoustrack', () => {
            console.log('🎮 Media Session: previous');
            castPrevious();
        });

        navigator.mediaSession.setActionHandler('nexttrack', () => {
            console.log('🎮 Media Session: next');
            castNext();
        });

        navigator.mediaSession.setActionHandler('seekto', (details) => {
            console.log('🎮 Media Session: seekto', details.seekTime);
            if (details.seekTime !== undefined) {
                castSeek(details.seekTime);
            }
        });

        // Set position state if available
        if (media.media.duration) {
            updateMediaSessionPosition(
                media.getEstimatedTime() || 0,
                media.media.duration
            );
        }

        console.log('✅ Media Session updated for Chromecast');
    } catch (error) {
        console.error('❌ Error updating Media Session:', error);
    }
}

/**
 * Update Media Session playback state
 */
function updateMediaSessionPlaybackState(castState) {
    if (!('mediaSession' in navigator)) return;
    
    const state = castState === 'PLAYING' ? 'playing' : 
                 castState === 'PAUSED' ? 'paused' : 'none';
    
    try {
        navigator.mediaSession.playbackState = state;
    } catch (e) {
        console.warn('Error updating playback state:', e);
    }
}

/**
 * Update Media Session position state
 */
function updateMediaSessionPosition(currentTime, duration, playbackRate = 1.0) {
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
        console.log('📡 Chromecast device found');
        const btn = document.getElementById('cast-button');
        if (btn) btn.hidden = false;
    } else {
        console.log('📡 No Chromecast devices available');
    }
}

function onCastSessionStart() {
    console.log('🎵 CASTING STARTED');
    console.log('🔇 Silencing local player...');

    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.add('connected');
        btn.title = 'Casting to device • Click to stop';
    }

    // Silence local player but DON'T clear Media Session
    // Media Session will be updated with Cast metadata when media loads
    silenceLocalPlayer();

    // Dispatch event after silencing
    document.dispatchEvent(new CustomEvent('cast:started'));
    console.log('✅ cast:started event dispatched');
}

function onCastSessionEnd() {
    console.log('🎵 CASTING ENDED');
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.remove('connected');
        btn.title = 'Cast to device';
    }

    // Clear Media Session when casting ends
    // Local playback will set it up again if needed
    clearMediaSession();

    document.dispatchEvent(new CustomEvent('cast:ended'));
    console.log('✅ cast:ended event dispatched');
}

export function setCastControlCallbacks(callbacks) {
    castControlCallbacks = { ...castControlCallbacks, ...callbacks };
    console.log('✅ Cast control callbacks registered');
}

export function isCasting() {
    const casting = currentCastSession !== null && currentMedia !== null;
    console.log(`🔍 isCasting() called: ${casting} (session: ${!!currentCastSession}, media: ${!!currentMedia})`);
    return casting;
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
    console.log('▶️ castPlay() called');
    if (!currentMedia) {
        console.warn('⚠️ Cannot play - no media loaded');
        console.warn(`   currentMedia: ${currentMedia}`);
        console.warn(`   currentCastSession: ${currentCastSession}`);
        return;
    }

    const playRequest = new chrome.cast.media.PlayRequest();
    currentMedia.play(playRequest,
        () => console.log('✅ Play command sent to Chromecast'),
        error => console.error('❌ Play failed:', error)
    );
}

export function castPause() {
    console.log('⏸️ castPause() called');
    if (!currentMedia) {
        console.warn('⚠️ Cannot pause - no media loaded');
        console.warn(`   currentMedia: ${currentMedia}`);
        console.warn(`   currentCastSession: ${currentCastSession}`);
        return;
    }

    const pauseRequest = new chrome.cast.media.PauseRequest();
    currentMedia.pause(pauseRequest,
        () => console.log('✅ Pause command sent to Chromecast'),
        error => console.error('❌ Pause failed:', error)
    );
}

/**
 * Toggle play/pause state for Chromecast
 */
export function castTogglePlayPause() {
    console.log('⏯️ castTogglePlayPause() called');
    if (!currentMedia) {
        console.warn('⚠️ Cannot toggle - no media loaded');
        return;
    }

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
        () => console.log(`✅ Seek to ${currentTime}s`),
        error => console.error('❌ Seek failed:', error)
    );
}

/**
 * Navigate to next track in queue
 */
export function castNext() {
    console.log('⏭️ castNext() called');
    if (!currentMedia) {
        console.warn('⚠️ Cannot go to next - no media loaded');
        return;
    }

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
        () => console.log(`✅ Next track (index ${nextIndex})`),
        error => console.error('❌ Next failed:', error)
    );
}

/**
 * Navigate to previous track in queue
 */
export function castPrevious() {
    console.log('⏮️ castPrevious() called');
    if (!currentMedia) {
        console.warn('⚠️ Cannot go to previous - no media loaded');
        return;
    }

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
        () => console.log(`✅ Previous track (index ${prevIndex})`),
        error => console.error('❌ Previous failed:', error)
    );
}

/**
 * Jump to a specific track by index
 */
export function castJumpToTrack(index) {
    console.log(`🎯 castJumpToTrack(${index}) called`);
    if (!currentMedia) {
        console.warn('⚠️ Cannot jump to track - no media loaded');
        return;
    }

    const targetItemId = getItemIdForIndex(index);

    if (targetItemId === null) {
        console.warn(`Cannot jump to index ${index} - out of bounds`);
        return;
    }

    const jumpRequest = new chrome.cast.media.QueueJumpRequest(targetItemId);

    currentMedia.queueJumpToItem(jumpRequest,
        () => console.log(`✅ Jumped to track ${index}`),
        error => console.error('❌ Jump failed:', error)
    );
}

/**
 * Build proper audio URL from track data
 */
function buildTrackUrl(track, quality) {
    const trackItems = document.querySelectorAll('.track-item');

    let relativePath = null;

    // Try to find matching track in DOM
    for (let item of trackItems) {
        if (item.dataset.title === track.track && item.dataset.artist === track.artist) {
            relativePath = item.dataset.path;
            const separator = relativePath.includes('?') ? '&' : '?';
            relativePath = `${relativePath}${separator}quality=${quality}`;
            break;
        }
    }

    // Fallback: construct URL from raw path
    if (!relativePath) {
        const baseUrl = window.__mixtapeData?.baseUrl || '/play/';
        const encodedPath = encodeURIComponent(track.path);
        relativePath = `${baseUrl}${encodedPath}?quality=${quality}`;
    }

    // Convert to absolute URL for Chromecast
    const absoluteUrl = new URL(relativePath, window.location.origin).href;
    console.log(`🔗 Built URL: ${absoluteUrl}`);

    return absoluteUrl;
}

export function castMixtapePlaylist() {
    console.log('🎬 Starting cast request...');

    if (currentCastSession) {
        loadQueue(currentCastSession);
        return;
    }

    chrome.cast.requestSession(
        session => {
            currentCastSession = session;
            loadQueue(session);
        },
        error => console.error('❌ Session request failed:', error)
    );
}

function loadQueue(session) {
    const tracks = window.__mixtapeData?.tracks || [];
    if (tracks.length === 0) {
        console.warn('⚠️ No tracks available to cast');
        return;
    }

    console.log(`📀 Loading queue with ${tracks.length} tracks`);

    const quality = localStorage.getItem('audioQuality') || 'medium';
    console.log(`🎚️ Quality: ${quality}`);

    const queueItems = tracks.map((track, index) => {
        const trackUrl = buildTrackUrl(track, quality);
        const contentType = getAudioMimeFromPath(track.path, quality);

        if (index === 0 || index === tracks.length - 1) {
            console.log(`Track ${index}: ${track.track}`);
            console.log(`  URL: ${trackUrl}`);
            console.log(`  Content-Type: ${contentType}`);
        }

        const mediaInfo = new chrome.cast.media.MediaInfo(trackUrl, contentType);
        mediaInfo.metadataType = chrome.cast.media.MetadataType.MUSIC_TRACK;
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

    console.log(`▶️ Queue load starting at index ${startIndex}`);

    session.queueLoad(
        queueRequest,
        () => {
            console.log('✅ Playlist successfully queued on Chromecast');

            // Silence local player (Media Session will update when media loads)
            silenceLocalPlayer();
        },
        (error) => {
            console.error('❌ Failed to load queue on Chromecast:', error);
            console.error('Error code:', error.code);
            console.error('Error description:', error.description);
        }
    );
}

export function stopCasting() {
    if (currentCastSession) {
        console.log('🛑 Stopping cast...');
        currentCastSession.stop(() => {
            currentCastSession = null;
            currentMedia = null;
            castPlayState = 'IDLE';
            globalCastingState = false;
            onCastSessionEnd();
        }, onError);
    }
}
