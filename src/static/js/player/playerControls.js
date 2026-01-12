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
 * Guesses the MIME type based on the file extension in the URL
 * @param {string} url - The image URL
 * @returns {string} MIME type (falls back to 'image/jpeg')
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
     * Initialize quality selector dropdown and event handlers
     */
    function initQualitySelector() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');

        if (!qualityBtn || !qualityMenu) return;

        updateQualityButtonText();

        // Toggle dropdown
        qualityBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            qualityMenu.classList.toggle('show');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!qualityBtn.contains(e.target) && !qualityMenu.contains(e.target)) {
                qualityMenu.classList.remove('show');
            }
        });

        // Handle quality selection
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

    /**
     * Updates quality button text to show current quality
     */
    function updateQualityButtonText() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;

        const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
        qualityBtn.innerHTML = `<i class="bi bi-gear-fill me-1"></i>${qualityLabel}`;
    }

    /**
     * Updates active state of quality menu options
     */
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

    /**
     * Changes audio quality and reloads current track if playing
     */
    function changeQuality(newQuality) {
        currentQuality = newQuality;
        localStorage.setItem('audioQuality', newQuality);

        updateQualityButtonText();
        updateQualityMenuState(newQuality);

        // If something is playing locally, reload with new quality
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

    /**
     * Shows toast notification for quality change
     */
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

    /**
     * Updates Media Session API metadata for mobile notifications
     * When casting, this controls the unified notification
     */
    function updateMediaSession(track, isCast = false) {
        if (!('mediaSession' in navigator)) return;

        let artwork = [];
        
        if (isCast) {
            // Get artwork from cast metadata
            const castMetadata = getCurrentCastMetadata();
            if (castMetadata && castMetadata.artwork && castMetadata.artwork.length > 0) {
                artwork = castMetadata.artwork.map(img => ({
                    src: img.url,
                    sizes: '512x512',
                    type: 'image/png'
                }));
            }
        } else {
            // Get artwork from DOM
            const coverImg = track.querySelector('.track-cover');
            if (coverImg && coverImg.src) {
                const mimeType = getMimeTypeFromUrl(coverImg.src);
                artwork = [
                    { src: coverImg.src, sizes: '96x96',   type: mimeType },
                    { src: coverImg.src, sizes: '128x128', type: mimeType },
                    { src: coverImg.src, sizes: '192x192', type: mimeType },
                    { src: coverImg.src, sizes: '256x256', type: mimeType },
                    { src: coverImg.src, sizes: '384x384', type: mimeType },
                    { src: coverImg.src, sizes: '512x512', type: mimeType }
                ];
            }
        }

        const metadata = new MediaMetadata({
            title: track.dataset ? track.dataset.title : track.title || 'Unknown',
            artist: track.dataset ? track.dataset.artist : track.artist || 'Unknown Artist',
            album: track.dataset ? (track.dataset.album || '') : (track.album || ''),
            artwork: artwork
        });

        navigator.mediaSession.metadata = metadata;

        // Set action handlers for media controls
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

        // Update position state
        if (isCurrentlyCasting) {
            updateCastPositionState();
        } else {
            updatePositionState();
        }
    }

    /**
     * Updates Media Session position state for local player
     */
    function updatePositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
        if (isCurrentlyCasting) return; // Don't update for local player when casting

        // Only update if we have valid duration and position data
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

    /**
     * Updates Media Session position state for Chromecast
     */
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

    /**
     * Builds audio source URL with quality parameter
     */
    function buildAudioUrl(basePath, quality) {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * Plays track at given index with current quality setting
     */
    function playTrack(index) {
        // If casting, use cast controls instead
        if (isCurrentlyCasting) {
            castJumpToTrack(index);
            updateUIForTrack(index);
            return;
        }

        // If index is same as current, don't reload the source
        if (index === currentIndex && player.src !== '') {
            player.play().catch(e => console.log('Autoplay prevented:', e));
            return;
        }

        // Handle bounds and stopping
        if (index < 0 || index >= trackItems.length) {
            stopPlayback();
            return;
        }

        const track = trackItems[index];

        player.src = buildAudioUrl(track.dataset.path, currentQuality);
        if ('mediaSession' in navigator && 'setPositionState' in navigator.mediaSession) {
            try {
                navigator.mediaSession.setPositionState(); // Clear state
            } catch (e) {
                // Catch browser error if there is no state yet
            }
        }

        updateUIForTrack(index);

        // Update Media Session metadata for mobile notifications
        updateMediaSession(track, false);

        player.play().catch(e => console.log('Autoplay prevented:', e));
    }

    /**
     * Updates UI elements for a given track index
     */
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

    /**
     * Stops playback and hides player
     */
    function stopPlayback() {
        player.pause();
        player.src = '';
        player.load(); // Reset player
        container.style.display = 'none';
        trackItems.forEach(t => t.classList.remove('active-track'));
        currentIndex = -1;
        
        // Clear Media Session
        if ('mediaSession' in navigator) {
            navigator.mediaSession.metadata = null;
        }
    }

    /**
     * Syncs play/pause icon states across all track items
     */
    function syncPlayIcons() {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            // Check if playing: either casting and playing, or local player playing
            const isPlaying = isCurrentTrack && (
                (isCurrentlyCasting && isCastPlaying()) || 
                (!isCurrentlyCasting && !player.paused)
            );

            // Update icon
            if (isPlaying) {
                icon.classList.remove('bi-play-fill');
                icon.classList.add('bi-pause-fill');
            } else {
                icon.classList.remove('bi-pause-fill');
                icon.classList.add('bi-play-fill');
            }

            // Update track item state
            if (isPlaying) {
                item.classList.add('playing');
            } else {
                item.classList.remove('playing');
            }
        });
    }

    /**
     * Toggles play/pause for the current track
     */
    function togglePlayPause() {
        if (isCurrentlyCasting) {
            // Use proper toggle for Chromecast that checks play state
            castTogglePlayPause();
        } else {
            // Local player toggle
            if (player.paused) {
                player.play().catch(err => console.error("Resume failed:", err));
            } else {
                player.pause();
            }
        }
    }

    /**
     * Updates audio player progress bar coloring
     */
    function updateAudioProgress() {
        if (!player.duration || isNaN(player.duration)) return;

        const progress = (player.currentTime / player.duration) * 100;
        player.style.setProperty('--audio-progress', `${progress}%`);
    }

    /**
     * Setup Chromecast event listeners
     */
    function initCastListeners() {
        // Listen for casting state changes
        document.addEventListener('cast:started', () => {
            isCurrentlyCasting = true;
            console.log('Casting started - controls now route to Chromecast');
            
            // CRITICAL: Stop local player completely to avoid duplicate notifications
            if (!player.paused) {
                player.pause();
            }
            player.src = '';
            player.load();
            
            syncPlayIcons();
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            console.log('Casting ended - controls back to local player');
            syncPlayIcons();
            
            // Clear Media Session
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = null;
            }
        });

        // Register callbacks for Chromecast events
        setCastControlCallbacks({
            onTrackChange: (index) => {
                console.log(`Cast track changed to index: ${index}`);
                updateUIForTrack(index);
                
                // Update media session with cast metadata
                if (index >= 0 && index < trackItems.length) {
                    const track = trackItems[index];
                    updateMediaSession(track, true);
                }
            },
            onPlayStateChange: (state) => {
                console.log(`Cast play state: ${state}`);
                // Sync icons when cast play state changes
                syncPlayIcons();
                
                // Update playback state in Media Session
                if ('mediaSession' in navigator) {
                    navigator.mediaSession.playbackState = 
                        state === 'PLAYING' ? 'playing' : 
                        state === 'PAUSED' ? 'paused' : 'none';
                }
            },
            onTimeUpdate: (time) => {
                // Update position state periodically for cast
                updateCastPositionState();
            }
        });
    }

    /**
     * Initializes all event listeners
     */
    function initEventListeners() {
        // Big play button
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

        // Player events - only for local playback
        player?.addEventListener('play', () => {
            if (!isCurrentlyCasting) syncPlayIcons();
        });
        
        player?.addEventListener('pause', () => {
            if (!isCurrentlyCasting) syncPlayIcons();
        });
        
        player?.addEventListener('ended', () => {
            syncPlayIcons();
            if (!isCurrentlyCasting) {
                playTrack(currentIndex + 1);
            }
        });

        // Audio progress for adaptive theming - only when not casting
        player?.addEventListener('timeupdate', () => {
            if (!isCurrentlyCasting) updateAudioProgress();
        });
        player?.addEventListener('loadedmetadata', () => {
            if (!isCurrentlyCasting) updateAudioProgress();
        });
        player?.addEventListener('seeked', () => {
            if (!isCurrentlyCasting) updateAudioProgress();
        });

        // Media Session position updates - only for local playback
        player?.addEventListener('loadedmetadata', () => {
            if (!isCurrentlyCasting) updatePositionState();
        });
        player?.addEventListener('play', () => {
            if (!isCurrentlyCasting) updatePositionState();
        });
        player?.addEventListener('pause', () => {
            if (!isCurrentlyCasting) updatePositionState();
        });
        player?.addEventListener('ratechange', () => {
            if (!isCurrentlyCasting) updatePositionState();
        });
        player?.addEventListener('seeked', () => {
            if (!isCurrentlyCasting) updatePositionState();
        });

        // Throttle timeupdate to once per second
        let lastPositionUpdate = 0;
        player?.addEventListener('timeupdate', () => {
            if (isCurrentlyCasting) return; // Don't update when casting
            
            const now = Date.now();
            if (now - lastPositionUpdate >= 1000) {
                updatePositionState();
                lastPositionUpdate = now;
            }
        });

        // Navigation buttons - now work for both local and cast
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

        // Track item play buttons
        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (i === currentIndex) {
                    togglePlayPause();
                } else {
                    playTrack(i);
                }
            });
        });
    }

    /**
     * Handles auto-start scenarios (hash or session storage)
     */
    function handleAutoStart() {
        if (trackItems.length === 0) return;

        if (window.location.hash === '#play') {
            setTimeout(() => playTrack(0), 500);
        } else if (sessionStorage.getItem('startPlaybackNow')) {
            sessionStorage.removeItem('startPlaybackNow');
            playTrack(0);
        }
    }

    // Initialize everything
    initQualitySelector();
    initCastListeners();
    initEventListeners();
    handleAutoStart();

    // Return public API
    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
