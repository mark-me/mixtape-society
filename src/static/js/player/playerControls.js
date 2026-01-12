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

import {
    detectiOS,
    logDeviceInfo,
    silenceLocalPlayer,
    enableLocalPlayer,
    clearMediaSession,
    setupCastMediaSession,
    setupLocalMediaSession,
    updateMediaSessionPosition,
    updateMediaSessionPlaybackState,
    extractMetadataFromDOM
} from './playerUtils.js';

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

// Global flag to prevent duplicate iOS help setup
let iOSHelpInitialized = false;

const iOS = detectiOS();

/**
 * Extract metadata from Chromecast
 */
function extractMetadataFromCast() {
    const castMetadata = getCurrentCastMetadata();
    
    if (!castMetadata) {
        return null;
    }

    // Convert cast artwork format to MediaMetadata format
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

/**
 * Show iOS-specific help message if Chromecast isn't working
 * Only initializes once per page lifecycle
 */
function showiOSCastHelp() {
    if (!iOS || iOSHelpInitialized) return;
    
    iOSHelpInitialized = true; // Prevent duplicate initialization
    
    const helpHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert" style="position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; max-width: 90%; width: 400px;">
            <h6 class="alert-heading">📱 Casting from iPhone</h6>
            <small>
                <strong>To cast to Chromecast:</strong><br>
                1. Install Google Home app<br>
                2. Use Chrome browser (not Safari)<br>
                3. Connect to same WiFi network<br>
                <br>
                <strong>For best experience:</strong><br>
                Add this page to your Home Screen (PWA mode)
            </small>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Show help after 3 seconds if cast button is clicked but no devices found
    let castButtonClicked = false;
    const castBtn = document.getElementById('cast-button');
    
    if (castBtn) {
        // Use once: true to automatically remove listener after first call
        castBtn.addEventListener('click', () => {
            castButtonClicked = true;
            
            setTimeout(() => {
                // If still no session, show help
                if (castButtonClicked && !isCasting()) {
                    const existingHelp = document.querySelector('.alert-info');
                    if (!existingHelp) {
                        document.body.insertAdjacentHTML('afterbegin', helpHtml);
                    }
                }
            }, 3000);
        }, { once: true }); // Prevents duplicate listeners
    }
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

    // Log device info on initialization
    logDeviceInfo();
    
    // Show iOS cast help if needed (only once)
    if (iOS) {
        showiOSCastHelp();
    }

    function onlyWhenNotCasting(handler) {
        return function(...args) {
            if (!isCurrentlyCasting) {
                handler.apply(this, args);
            }
        };
    }

    function setupAudioControlInterception() {
        player.addEventListener('play', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
                e.stopPropagation();
                player.pause();
                castPlay();
                return false;
            }
        }, true);

        player.addEventListener('pause', (e) => {
            if (isCurrentlyCasting) {
                e.stopPropagation();
                castPause();
            }
        });

        player.addEventListener('seeking', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
                e.stopPropagation();
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

    function updateLocalMediaSession(metadata) {
        if (isCurrentlyCasting) return; // Don't update when casting
        
        setupLocalMediaSession(metadata, {
            play: () => player.play().catch(e => console.log('Media Session play failed:', e)),
            pause: () => player.pause(),
            previous: () => playTrack(currentIndex - 1),
            next: () => playTrack(currentIndex + 1)
        });
        
        updatePositionState();
    }

    function updatePositionState() {
        if (isCurrentlyCasting) return;
        updateMediaSessionPosition(player.currentTime, player.duration, player.playbackRate || 1.0);
    }

    function updateCastPositionState() {
        if (!isCurrentlyCasting) return;
        
        const timeInfo = getCurrentCastTime();
        updateMediaSessionPosition(timeInfo.currentTime, timeInfo.duration, 1.0);
    }

    function buildAudioUrl(basePath, quality) {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * CRITICAL: playTrack must check casting state FIRST
     */
    function playTrack(index) {
        console.log(`🎵 playTrack called with index: ${index}, casting: ${isCurrentlyCasting}`);
        
        // CRITICAL: Route to Chromecast if currently casting
        if (isCurrentlyCasting) {
            console.log(`📡 Routing track ${index} to Chromecast`);
            castJumpToTrack(index);
            updateUIForTrack(index);
            
            // Update Media Session with cast metadata after a brief delay
            // iOS needs a bit more time for metadata to propagate
            const delay = iOS ? 800 : 500;
            setTimeout(() => {
                const metadata = extractMetadataFromCast();
                if (metadata) {
                    setupCastMediaSession(metadata, {
                        play: castPlay,
                        pause: castPause,
                        previous: castPrevious,
                        next: castNext
                    });
                }
            }, delay);
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
        updateLocalMediaSession(metadata);

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
        
        clearMediaSession();
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
            console.log('🎵 Casting started');
            
            // Use shared utility to silence local player
            silenceLocalPlayer();
            syncPlayIcons();
            
            // Setup initial Media Session for the first track
            if (currentIndex >= 0 && currentIndex < trackItems.length) {
                const track = trackItems[currentIndex];
                const metadata = extractMetadataFromDOM(track);
                setupCastMediaSession(metadata, {
                    play: castPlay,
                    pause: castPause,
                    previous: castPrevious,
                    next: castNext
                });
            }
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            console.log('🎵 Casting ended');
            
            // Use shared utilities to re-enable local player
            enableLocalPlayer();
            clearMediaSession();
            syncPlayIcons();
        });

        setCastControlCallbacks({
            onTrackChange: (index) => {
                console.log(`📻 Cast track changed to index: ${index}`);
                updateUIForTrack(index);
                
                // Update Media Session with new track metadata
                const metadata = extractMetadataFromCast();
                if (metadata) {
                    setupCastMediaSession(metadata, {
                        play: castPlay,
                        pause: castPause,
                        previous: castPrevious,
                        next: castNext
                    });
                }
            },
            onPlayStateChange: (state) => {
                console.log(`Cast play state: ${state}`);
                syncPlayIcons();
                
                // Update playback state in Media Session
                const playbackState = state === 'PLAYING' ? 'playing' : 
                                     state === 'PAUSED' ? 'paused' : 'none';
                updateMediaSessionPlaybackState(playbackState);
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

        // Track item click handlers
        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                console.log(`🖱️ Track ${i} button clicked, casting: ${isCurrentlyCasting}`);
                
                if (i === currentIndex) {
                    togglePlayPause();
                } else {
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
