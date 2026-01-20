// static/js/player/playerControls.js
import {
    globalCastingState,
    isCasting,
    castPlay,
    castPause,
    castTogglePlayPause,
    castNext,
    castPrevious,
    castJumpToTrack,
    isCastPlaying,
    setCastControlCallbacks,
} from './chromecast.js';

import {
    detectiOS,
    detectAndroid,
    logDeviceInfo,
    silenceLocalPlayer,
    enableLocalPlayer,
    clearMediaSession,
    setupLocalMediaSession,
    updateMediaSessionPosition,
    extractMetadataFromDOM
} from './playerUtils.js';

import {
    setupAndroidAutoMediaSession,
    clearAndroidAutoMediaSession,
    logAndroidAutoStatus,
    isAndroidAutoConnected
} from './androidAuto.js';

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
const androidInfo = detectAndroid();

/**
 * Show iOS-specific help message for Chromecast
 */
function showiOSCastHelp() {
    if (!iOS || iOSHelpInitialized) return;

    iOSHelpInitialized = true;

    const helpHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert" style="position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; max-width: 90%; width: 400px;">
            <h6 class="alert-heading">📱 Casting from iPhone</h6>
            <small>
                <strong>To cast to Chromecast:</strong><br>
                1. Install Google Home app<br>
                2. Use Chrome browser (not Safari)<br>
                3. Connect to same WiFi network<br>
                <br>
                <strong>For AirPlay (recommended):</strong><br>
                Use Safari and tap the AirPlay icon in audio controls
            </small>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    const castBtn = document.getElementById('cast-button');

    if (castBtn) {
        castBtn.addEventListener('click', () => {
            setTimeout(() => {
                if (!isCasting()) {
                    const existingHelp = document.querySelector('.alert-info');
                    if (!existingHelp) {
                        document.body.insertAdjacentHTML('afterbegin', helpHtml);
                    }
                }
            }, 3000);
        }, { once: true });
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

    // Log device capabilities
    logDeviceInfo();

    // Log Android Auto status if Android device
    if (androidInfo) {
        logAndroidAutoStatus();
    }

    // Show iOS help if needed
    if (iOS) {
        showiOSCastHelp();
    }

    console.log('ðŸŽ® PlayerControls initialized');

    // Player control API for external modules
    const playerControlsAPI = {
        play: () => {
            if (player.paused) {
                player.play().catch(err => console.error("Play failed:", err));
            }
        },
        pause: () => {
            if (!player.paused) {
                player.pause();
            }
        },
        next: () => playTrack(currentIndex + 1),
        previous: () => playTrack(currentIndex - 1),
        jumpTo: (index) => playTrack(index)
    };

    const checkCastingState = () => {
        return globalCastingState || isCurrentlyCasting;
    }

    const onlyWhenNotCasting = (handler) => {
        return function (...args) {
            if (!checkCastingState()) {
                handler.apply(this, args);
            }
        };
    }

    const setupAudioControlInterception = () => {
        player.addEventListener('play', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                player.pause();
                castPlay();
                return false;
            }
        }, true);

        player.addEventListener('pause', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                castPause();
            }
        });

        player.addEventListener('seeking', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);

        player.addEventListener('loadeddata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                player.pause();
            }
        }, true);

        // Block metadata events while casting
        player.addEventListener('loadedmetadata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
            }
        }, true);
    }

    const initQualitySelector = () => {
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

    const updateQualityButtonText = () => {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;

        const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
        qualityBtn.innerHTML = `<i class="bi bi-gear-fill me-1"></i>${qualityLabel}`;
    }

    const updateQualityMenuState = (quality) => {
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

    const changeQuality = (newQuality) => {
        currentQuality = newQuality;
        localStorage.setItem('audioQuality', newQuality);

        updateQualityButtonText();
        updateQualityMenuState(newQuality);

        if (currentIndex >= 0 && player.src && !checkCastingState()) {
            const wasPlaying = !player.paused;
            const {currentTime} = player;

            playTrack(currentIndex);

            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }

        showQualityToast(newQuality);
    }

    const showQualityToast = (quality) => {
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

    const updateLocalMediaSession = (metadata) => {
        if (checkCastingState()) {
            // CRITICAL: Do NOT create Media Session when casting
            console.log('â­ï¸ Skipping Media Session - Chromecast handles it');
            return;
        }

        // Use Android Auto optimized Media Session if connected to car
        if (isAndroidAutoConnected()) {
            console.log('ðŸš— Using Android Auto Media Session');
            setupAndroidAutoMediaSession(metadata, playerControlsAPI, player);
        } else {
            // Standard Media Session for iOS/desktop
            console.log('ðŸ“± Using standard Media Session');
            setupLocalMediaSession(metadata, playerControlsAPI);
        }
    }

    const updatePositionState = () => {
        if (checkCastingState()) return;
        updateMediaSessionPosition(player.currentTime, player.duration, player.playbackRate);
    }

    const buildAudioUrl = (basePath, quality) => {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * Prefetch the next track to ensure smooth playback transitions
     * This will cache the audio file in the browser/service worker
     *
     * Prefetch strategy:
     * - First check if already cached to avoid redundant network traffic
     * - Use a single low-priority GET request (HEAD + GET was redundant)
     * - The service worker will handle caching asynchronously
     */
    const prefetchNextTrack = async (currentIdx) => {
        const nextIdx = currentIdx + 1;

        // Don't prefetch if we're at the last track
        if (nextIdx >= trackItems.length) {
            console.log('🚫 No next track to prefetch (end of playlist)');
            return;
        }

        const nextTrack = trackItems[nextIdx];
        if (!nextTrack) return;

        const audioUrl = buildAudioUrl(nextTrack.dataset.path, currentQuality);

        console.log(`🔥 Prefetching next track (${nextIdx + 1}/${trackItems.length}):`, nextTrack.dataset.title);

        try {
            // Check if already cached (avoid redundant network request)
            if ('caches' in window) {
                try {
                    const cached = await caches.match(audioUrl);
                    if (cached) {
                        console.log('✅ Next track already cached, skipping prefetch');
                        return;
                    }
                } catch (cacheError) {
                    // Non-fatal: fall through to network prefetch
                    console.debug('Cache lookup failed during prefetch:', cacheError);
                }
            }

            // Single low-priority GET request to warm the service worker cache
            // The service worker will cache it asynchronously
            await fetch(audioUrl, {
                method: 'GET',
                credentials: 'include',
                priority: 'low'
            });

            console.log('✅ Next track prefetch initiated');
        } catch (error) {
            console.warn('⚠️ Prefetch failed (not critical):', error.message);
        }
    };

    const playTrack = (index) => {
        console.log(`ðŸŽµ playTrack(${index}), casting: ${checkCastingState()}`);

        if (checkCastingState()) {
            console.log(`ðŸ“¡ Routing to Chromecast`);
            castJumpToTrack(index);
            updateUIForTrack(index);
            // NO Media Session setup - Chromecast handles it
            return;
        }

        console.log(`ðŸ”Š Playing locally`);

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
            } catch (e) { }
        }

        updateUIForTrack(index);

        const metadata = extractMetadataFromDOM(track);
        updateLocalMediaSession(metadata);

        player.play().catch(e => console.log('Autoplay prevented:', e));

        // Prefetch next track for smooth transitions
        prefetchNextTrack(index);
    }

    const updateUIForTrack = (index) => {
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

    const stopPlayback = () => {
        player.pause();
        player.src = '';
        player.load();
        container.style.display = 'none';
        trackItems.forEach(t => t.classList.remove('active-track'));
        currentIndex = -1;

        // Clear appropriate Media Session
        if (isAndroidAutoConnected()) {
            clearAndroidAutoMediaSession();
        } else {
            clearMediaSession();
        }
    }

    const syncPlayIcons = () => {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            const isPlaying = isCurrentTrack && (
                (checkCastingState() && isCastPlaying()) ||
                (!checkCastingState() && !player.paused)
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

    const togglePlayPause = () => {
        if (checkCastingState()) {
            castTogglePlayPause();
        }
        else if (player.paused) {
            player.play().catch(err => console.error("Resume failed:", err));
        }
        else {
            player.pause();
        }
    }

    const updateAudioProgress = () => {
        if (!player.duration || isNaN(player.duration)) return;

        const progress = (player.currentTime / player.duration) * 100;
        player.style.setProperty('--audio-progress', `${progress}%`);
    }

    const initCastListeners = () => {
        document.addEventListener('cast:started', () => {
            isCurrentlyCasting = true;
            silenceLocalPlayer();

            // Clear local Media Session when casting starts
            if (isAndroidAutoConnected()) {
                clearAndroidAutoMediaSession();
            } else {
                clearMediaSession();
            }

            syncPlayIcons();
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            enableLocalPlayer();

            // Restore local Media Session when casting ends
            if (currentIndex >= 0) {
                const track = trackItems[currentIndex];
                const metadata = extractMetadataFromDOM(track);
                updateLocalMediaSession(metadata);
            }

            syncPlayIcons();
        });

        setCastControlCallbacks({
            onTrackChange: (index) => {
                updateUIForTrack(index);
            },
            onPlayStateChange: (state) => {
                syncPlayIcons();
            },
            onTimeUpdate: (time) => {
                // No-op - Chromecast handles progress
            }
        });
    }

    const initEventListeners = () => {
        document.getElementById('big-play-btn')?.addEventListener('click', () => {
            if (trackItems.length === 0) return;
            if (currentIndex === -1) {
                playTrack(0);
            } else if (checkCastingState()) {
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

        // Prefetch next track when current track can play (has buffered enough)
        player?.addEventListener('canplay', onlyWhenNotCasting(() => {
            if (currentIndex >= 0) {
                prefetchNextTrack(currentIndex);
            }
        }));

        player?.addEventListener('ended', () => {
            syncPlayIcons();
            if (!checkCastingState()) {
                // Immediately play next track without delay
                const nextIndex = currentIndex + 1;
                if (nextIndex < trackItems.length) {
                    playTrack(nextIndex);
                }
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
            if (checkCastingState()) {
                castPrevious();
            } else {
                playTrack(currentIndex - 1);
            }
        });

        nextBtn?.addEventListener('click', () => {
            if (checkCastingState()) {
                castNext();
            } else {
                playTrack(currentIndex + 1);
            }
        });

        closeBtn?.addEventListener('click', stopPlayback);

        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                if (i === currentIndex) {
                    togglePlayPause();
                } else {
                    playTrack(i);
                }
            });
        });
    }

    const handleAutoStart = () => {
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
