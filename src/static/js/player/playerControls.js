// static/js/player/playerControls.js

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
    let currentQuality = localStorage.getItem('audioQuality') || DEFAULT_QUALITY;

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

        // If something is playing, reload with new quality
        if (currentIndex >= 0 && player.src) {
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
     */
    function updateMediaSession(track) {
        if (!('mediaSession' in navigator)) return;

        const coverImg = track.querySelector('.track-cover');
        let artwork = [];

        if (coverImg && coverImg.src) {
            // Provide multiple sizes – Chrome on Android prefers 512x512 (256x256 on low-end devices)
            // We'll use the same source for all; the browser will scale as needed
            artwork = [
                { src: coverImg.src, sizes: '96x96',   type: 'image/jpeg' },  // or image/png if your covers are PNG
                { src: coverImg.src, sizes: '128x128', type: 'image/jpeg' },
                { src: coverImg.src, sizes: '192x192', type: 'image/jpeg' },
                { src: coverImg.src, sizes: '256x256', type: 'image/jpeg' },
                { src: coverImg.src, sizes: '384x384', type: 'image/jpeg' },
                { src: coverImg.src, sizes: '512x512', type: 'image/jpeg' }
            ];
        }

        navigator.mediaSession.metadata = new MediaMetadata({
            title: track.dataset.title,
            artist: track.dataset.artist,
            album: track.dataset.album || '',
            artwork: artwork
        });

        // Set action handlers for media controls
        navigator.mediaSession.setActionHandler('play', () => {
            player.play();
        });

        navigator.mediaSession.setActionHandler('pause', () => {
            player.pause();
        });

        navigator.mediaSession.setActionHandler('previoustrack', () => {
            playTrack(currentIndex - 1);
        });

        navigator.mediaSession.setActionHandler('nexttrack', () => {
            playTrack(currentIndex + 1);
        });

        // Update position state when metadata changes
        updatePositionState();
    }

    /**
     * Updates Media Session position state for progress indicator
     */
    function updatePositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;

        // Only update if we have valid duration and position data
        if (player.duration && !isNaN(player.duration) && isFinite(player.duration)) {
            try {
                navigator.mediaSession.setPositionState({
                    duration: player.duration,
                    playbackRate: player.playbackRate || 1.0,
                    position: Math.min(player.currentTime, player.duration) // Ensure position doesn't exceed duration
                });
            } catch (error) {
                // Silently fail if position state can't be set (some browsers don't support it)
                console.debug('Could not set position state:', error);
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
        bottomTitle.textContent = track.dataset.title;
        bottomArtistAlbum.textContent = `${track.dataset.artist} • ${track.dataset.album}`;
        container.style.display = 'block';

        trackItems.forEach(t => t.classList.remove('active-track'));
        track.classList.add('active-track');

        currentIndex = index;

        // Update Media Session metadata for mobile notifications
        updateMediaSession(track);

        player.play().catch(e => console.log('Autoplay prevented:', e));
    }

    /**
     * Stops playback and hides player
     */
    function stopPlayback() {
        player.pause();
        player.src = '';
        container.style.display = 'none';
        trackItems.forEach(t => t.classList.remove('active-track'));
        currentIndex = -1;
    }

    /**
     * Syncs play/pause icon states across all track items
     */
    function syncPlayIcons() {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            const isPlaying = isCurrentTrack && !player.paused;

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
        if (player.paused) {
            player.play().catch(err => console.error("Resume failed:", err));
        } else {
            player.pause();
        }
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
            } else {
                player.play();
            }
        });

        // Player events
        player?.addEventListener('play', syncPlayIcons);
        player?.addEventListener('pause', syncPlayIcons);
        player?.addEventListener('ended', () => {
            syncPlayIcons();
            playTrack(currentIndex + 1);
        });

        // Media Session position updates
        player?.addEventListener('loadedmetadata', updatePositionState);
        player?.addEventListener('play', updatePositionState);
        player?.addEventListener('pause', updatePositionState);
        player?.addEventListener('ratechange', updatePositionState);
        player?.addEventListener('seeked', updatePositionState); // Update immediately after seeking

        // Throttle timeupdate to once per second to avoid excessive updates
        let lastPositionUpdate = 0;
        player?.addEventListener('timeupdate', () => {
            const now = Date.now();
            if (now - lastPositionUpdate >= 1000) {
                updatePositionState();
                lastPositionUpdate = now;
            }
        });

        // Navigation buttons
        prevBtn?.addEventListener('click', () => playTrack(currentIndex - 1));
        nextBtn?.addEventListener('click', () => playTrack(currentIndex + 1));
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
    initEventListeners();
    handleAutoStart();

    // Return public API
    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
