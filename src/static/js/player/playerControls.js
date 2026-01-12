// static/js/player/playerControls.js
import { 
    isCasting, 
    castPlay, 
    castPause, 
    castTogglePlayPause,
    castNext, 
    castPrevious, 
    castJumpToTrack,
    isCastPlaying,
    setCastControlCallbacks,
    getCurrentCastMetadata,
    getCurrentCastTime
} from './chromecast.js';

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
 * Normalized metadata structure
 * @typedef {Object} TrackMetadata
 * @property {string} title
 * @property {string} artist
 * @property {string} album
 * @property {Array<{src: string, sizes: string, type: string}>} artwork
 */

/**
 * Guesses the MIME type based on the file extension in the URL
 */
function getMimeTypeFromUrl(url) {
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
 * Extracts normalized metadata from a DOM track element
 */
function extractMetadataFromDOM(trackElement) {
    const coverImg = trackElement.querySelector('.track-cover');
    let artwork = [];

    if (coverImg && coverImg.src) {
        const mimeType = getMimeTypeFromUrl(coverImg.src);
        const absoluteSrc = new URL(coverImg.src, window.location.origin).href;
        
        artwork = [
            { src: absoluteSrc, sizes: '96x96',   type: mimeType },
            { src: absoluteSrc, sizes: '128x128', type: mimeType },
            { src: absoluteSrc, sizes: '192x192', type: mimeType },
            { src: absoluteSrc, sizes: '256x256', type: mimeType },
            { src: absoluteSrc, sizes: '384x384', type: mimeType },
            { src: absoluteSrc, sizes: '512x512', type: mimeType }
        ];
    }

    return {
        title: trackElement.dataset.title || 'Unknown',
        artist: trackElement.dataset.artist || 'Unknown Artist',
        album: trackElement.dataset.album || '',
        artwork: artwork
    };
}

/**
 * Extracts normalized metadata from Chromecast
 */
function extractMetadataFromCast() {
    const castMetadata = getCurrentCastMetadata();
    
    if (!castMetadata) {
        return {
            title: 'Unknown',
            artist: 'Unknown Artist',
            album: '',
            artwork: []
        };
    }

    const artwork = castMetadata.artwork.map(img => ({
        src: img.url,
        sizes: '512x512',
        type: 'image/png'
    }));

    return {
        title: castMetadata.title,
        artist: castMetadata.artist,
        album: castMetadata.album,
        artwork: artwork
    };
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
    let currentQuality = localStorage.getItem('audioQuality') || DEFAULT_QUALITY;
    let isCurrentlyCasting = false;

    /**
     * Wrapper for player event handlers that should only run when NOT casting
     */
    function onlyWhenNotCasting(handler) {
        return function(...args) {
            if (!isCurrentlyCasting) {
                handler.apply(this, args);
            }
        };
    }

    /**
     * Intercept native audio player controls to route to Chromecast when casting
     */
    function setupAudioControlInterception() {
        player.addEventListener('play', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
                player.pause();
                castPlay();
                return false;
            }
        }, true);

        player.addEventListener('pause', (e) => {
            if (isCurrentlyCasting) {
                castPause();
            }
        });

        player.addEventListener('seeking', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
            }
        }, true);
    }

    function initQualitySelector() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');

        if (!qualityBtn || !qualityMenu) return;

        updateQualityButtonText();

        qualityBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            qualityMenu.classList.toggle('show');
        });

        document.addEventListener('click', (e) => {
            if (!qualityBtn.contains(e.target) && !qualityMenu.contains(e.target)) {
                qualityMenu.classList.remove('show');
            }
        });

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

    function updateQualityButtonText() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;

        const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
        qualityBtn.innerHTML = `<i class="bi bi-gear-fill me-1"></i>${qualityLabel}`;
    }

    function updateQualityMenuState(quality) {
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

    function changeQuality(newQuality) {
        currentQuality = newQuality;
        localStorage.setItem('audioQuality', newQuality);

        updateQualityButtonText();
        updateQualityMenuState(newQuality);

        if (currentIndex >= 0 && player.src && !isCurrentlyCasting) {
            const wasPlaying = !player.paused;
            const currentTime = player.currentTime;

            playTrack(currentIndex);

            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }

        showQualityToast(newQuality);
    }

    function showQualityToast(quality) {
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

    function updateMediaSession(metadata) {
        if (!('mediaSession' in navigator)) return;

        navigator.mediaSession.metadata = new MediaMetadata({
            title: metadata.title,
            artist: metadata.artist,
            album: metadata.album,
            artwork: metadata.artwork
        });

        navigator.mediaSession.setActionHandler('play', () => {
            if (isCurrentlyCasting) {
                castPlay();
            } else {
                player.play().catch(e => console.log('Media Session play failed:', e));
            }
        });

        navigator.mediaSession.setActionHandler('pause', () => {
            if (isCurrentlyCasting) {
                castPause();
            } else {
                player.pause();
            }
        });

        navigator.mediaSession.setActionHandler('previoustrack', () => {
            if (isCurrentlyCasting) {
                castPrevious();
            } else {
                playTrack(currentIndex - 1);
            }
        });

        navigator.mediaSession.setActionHandler('nexttrack', () => {
            if (isCurrentlyCasting) {
                castNext();
            } else {
                playTrack(currentIndex + 1);
            }
        });

        if (isCurrentlyCasting) {
            updateCastPositionState();
        } else {
            updatePositionState();
        }
    }

    function updatePositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
        if (isCurrentlyCasting) return;

        if (player.duration && !isNaN(player.duration) && isFinite(player.duration)) {
            try {
                navigator.mediaSession.setPositionState({
                    duration: player.duration,
                    playbackRate: player.playbackRate || 1.0,
                    position: Math.min(player.currentTime, player.duration)
                });
            } catch (error) {
                console.debug('Could not set position state:', error);
            }
        }
    }

    function updateCastPositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
        if (!isCurrentlyCasting) return;

        const timeInfo = getCurrentCastTime();
        
        if (timeInfo.duration && !isNaN(timeInfo.duration) && isFinite(timeInfo.duration) && timeInfo.duration > 0) {
            try {
                navigator.mediaSession.setPositionState({
                    duration: timeInfo.duration,
                    playbackRate: 1.0,
                    position: Math.min(timeInfo.currentTime, timeInfo.duration)
                });
            } catch (error) {
                console.debug('Could not set cast position state:', error);
            }
        }
    }

    function buildAudioUrl(basePath, quality) {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * Plays track at given index - routes to Chromecast if casting
     */
    function playTrack(index) {
        // CRITICAL: Route to Chromecast if currently casting
        if (isCurrentlyCasting) {
            console.log(`▶️ Routing track ${index} to Chromecast`);
            castJumpToTrack(index);
            updateUIForTrack(index);
            
            // Update Media Session with cast metadata (will update when cast changes track)
            setTimeout(() => {
                const metadata = extractMetadataFromCast();
                updateMediaSession(metadata);
            }, 100);
            return;
        }

        // Local playback
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
            } catch (e) {}
        }

        updateUIForTrack(index);

        const metadata = extractMetadataFromDOM(track);
        updateMediaSession(metadata);

        player.play().catch(e => console.log('Autoplay prevented:', e));
    }

    function updateUIForTrack(index) {
        if (index < 0 || index >= trackItems.length) return;

        const track = trackItems[index];
        
        bottomTitle.textContent = track.dataset.title;
        bottomArtistAlbum.textContent = `${track.dataset.artist} • ${track.dataset.album}`;
        container.style.display = 'block';

        trackItems.forEach(t => t.classList.remove('active-track'));
        track.classList.add('active-track');

        currentIndex = index;
        window.currentTrackIndex = index;
    }

    function stopPlayback() {
        player.pause();
        player.src = '';
        player.load();
        container.style.display = 'none';
        trackItems.forEach(t => t.classList.remove('active-track'));
        currentIndex = -1;
        
        if ('mediaSession' in navigator) {
            navigator.mediaSession.metadata = null;
        }
    }

    function syncPlayIcons() {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            const isPlaying = isCurrentTrack && (
                (isCurrentlyCasting && isCastPlaying()) || 
                (!isCurrentlyCasting && !player.paused)
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

    function togglePlayPause() {
        if (isCurrentlyCasting) {
            castTogglePlayPause();
        } else {
            if (player.paused) {
                player.play().catch(err => console.error("Resume failed:", err));
            } else {
                player.pause();
            }
        }
    }

    function updateAudioProgress() {
        if (!player.duration || isNaN(player.duration)) return;

        const progress = (player.currentTime / player.duration) * 100;
        player.style.setProperty('--audio-progress', `${progress}%`);
    }

    function initCastListeners() {
        document.addEventListener('cast:started', () => {
            isCurrentlyCasting = true;
            console.log('🎵 Casting started - app now controls Chromecast');
            
            if (!player.paused) {
                player.pause();
            }
            player.src = '';
            player.load();
            
            syncPlayIcons();
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            console.log('🎵 Casting ended - controls back to local player');
            syncPlayIcons();
            
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = null;
            }
        });

        setCastControlCallbacks({
            onTrackChange: (index) => {
                console.log(`Cast track changed to index: ${index}`);
                updateUIForTrack(index);
                
                const metadata = extractMetadataFromCast();
                updateMediaSession(metadata);
            },
            onPlayStateChange: (state) => {
                console.log(`Cast play state: ${state}`);
                syncPlayIcons();
                
                if ('mediaSession' in navigator) {
                    navigator.mediaSession.playbackState = 
                        state === 'PLAYING' ? 'playing' : 
                        state === 'PAUSED' ? 'paused' : 'none';
                }
            },
            onTimeUpdate: (time) => {
                updateCastPositionState();
            }
        });
    }

    function initEventListeners() {
        document.getElementById('big-play-btn')?.addEventListener('click', () => {
            if (trackItems.length === 0) return;
            if (currentIndex === -1) {
                playTrack(0);
            } else if (isCurrentlyCasting) {
                castPlay();
            } else {
                player.play();
            }
        });

        player?.addEventListener('play', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));
        
        player?.addEventListener('pause', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));
        
        player?.addEventListener('ended', () => {
            syncPlayIcons();
            if (!isCurrentlyCasting) {
                playTrack(currentIndex + 1);
            }
        });

        const handleAudioProgress = onlyWhenNotCasting(updateAudioProgress);
        player?.addEventListener('timeupdate', handleAudioProgress);
        player?.addEventListener('loadedmetadata', handleAudioProgress);
        player?.addEventListener('seeked', handleAudioProgress);

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

        prevBtn?.addEventListener('click', () => {
            if (isCurrentlyCasting) {
                castPrevious();
            } else {
                playTrack(currentIndex - 1);
            }
        });

        nextBtn?.addEventListener('click', () => {
            if (isCurrentlyCasting) {
                castNext();
            } else {
                playTrack(currentIndex + 1);
            }
        });

        closeBtn?.addEventListener('click', stopPlayback);

        // Track item click handlers - route to cast when casting
        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                
                if (i === currentIndex) {
                    // Same track - toggle play/pause
                    togglePlayPause();
                } else {
                    // Different track - play it (routes to cast if casting)
                    console.log(`Track ${i} clicked`);
                    playTrack(i);
                }
            });
        });
    }

    function handleAutoStart() {
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
    handleAutoStart();

    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
