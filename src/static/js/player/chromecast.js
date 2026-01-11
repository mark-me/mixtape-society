// static/js/player/chromecast.js

const CAST_APP_ID = 'CC1AD845';

let currentCastSession = null;

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

    session.addUpdateListener(isAlive => {
        if (!isAlive) {
            currentCastSession = null;
            onCastSessionEnd();
            console.log('Cast session ended');
        }
    });
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
        // Change tooltip/text
        btn.title = 'Casting to device • Click to stop';
    }
}

function onCastSessionEnd() {
    const btn = document.querySelector('#cast-button');
    if (btn) {
        btn.classList.remove('connected');
        btn.title = 'Cast to device';
    }
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
        const mediaInfo = new chrome.cast.media.MediaInfo(
            `${baseUrl}${encodeURIComponent(track.path)}?quality=${quality}`
        );
        mediaInfo.contentType = getAudioMimeFromPath(track.path, quality);

        const metadata = new chrome.cast.media.MusicTrackMediaMetadata();
        metadata.title = track.track || 'Unknown Title';
        metadata.artist = track.artist || 'Unknown Artist';
        metadata.albumName = track.album || '';

        if (track.cover) {
            const coverUrl = new URL(track.cover, window.location.origin).href;
            metadata.images = [{ url: coverUrl }];
        }

        mediaInfo.metadata = metadata;

        const queueItem = new chrome.cast.media.QueueItem(mediaInfo);
        queueItem.startTime = 0;
        return queueItem;
    });

    //Create the queue request
    const queueRequest = new chrome.cast.media.QueueLoadRequest(queueItems);
    queueRequest.repeatMode = chrome.cast.media.RepeatMode.OFF;

    let startIndex = Number.isInteger(window.currentTrackIndex) ? window.currentTrackIndex: 0;
    if (startIndex < 0 || startIndex >= queueItems.length) {
        startIndex = 0;
    }
    queueRequest.startIndex = startIndex;

    // Load the queue
    session.queueLoad(queueRequest, () => {
        console.log('Playlist successfully queued on Chromecast');
        // pause the local HTML5 player when casting starts
        const localPlayer = document.getElementById('main-player');
        if (localPlayer) localPlayer.pause();
        session.addMessageListener('urn:x-cast:com.google.cast.media', (namespace, message) => {
        const msg = JSON.parse(message);
        console.log('Cast receiver message:', msg);
        if (msg.type === 'MEDIA_STATUS' && msg.status.playerState === 'IDLE' && msg.status.idleReason === 'ERROR') {
            console.error('Media load error on Chromecast:', msg.status.errorCode);
        }
    });
    }, (error) => {
        console.error('Failed to load queue on Chromecast:', error);
    });
}

// Stop casting
export function stopCasting() {
    if (currentCastSession) {
        currentCastSession.stop(() => {
            currentCastSession = null;
            onCastSessionEnd();
        }, onError);
    }
}