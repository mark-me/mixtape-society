// static/js/player/playerControls.js

/**
 * Quality settings for audio playback
 * - high: 256kbps MP3 (better quality, more bandwidth)
 * - medium: 192kbps MP3 (good balance - DEFAULT)
 * - low: 128kbps MP3 (lower quality, less bandwidth)
 * - original: Original file format (FLAC/WAV - highest quality, most bandwidth)
 */
const QUALITY_LEVELS = {
    high: { label: 'High (256k)', bandwidth: 'high' },
    medium: { label: 'Medium (192k)', bandwidth: 'medium' },
    low: { label: 'Low (128k)', bandwidth: 'low' },
    original: { label: 'Original', bandwidth: 'highest' }
};

export function initPlayerControls() {
    const player = document.getElementById('main-player');
    const container = document.getElementById('bottom-player-container');
    const closeBtn = document.getElementById('close-bottom-player');
    const prevBtn = document.getElementById('prev-btn-bottom');
    const nextBtn = document.getElementById('next-btn-bottom');
    const trackItems = document.querySelectorAll('.track-item');
    const bottomTitle = document.getElementById('bottom-now-title');
    const bottomArtistAlbum = document.getElementById('bottom-now-artist-album');

    let currentIndex = -1;   // −1 means nothing playing
    let currentQuality = localStorage.getItem('audioQuality') || 'medium';

    /* -----------------------------------------------------------------
       Quality selector initialization
       ----------------------------------------------------------------- */
    function initQualitySelector() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');

        if (!qualityBtn || !qualityMenu) return;

        // Update button text to show current quality
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

    function updateQualityButtonText() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (qualityBtn) {
            const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
            qualityBtn.innerHTML = `<i class="bi bi-gear-fill me-1"></i>${qualityLabel}`;
        }
    }

    function changeQuality(newQuality) {
        currentQuality = newQuality;
        localStorage.setItem('audioQuality', newQuality);

        updateQualityButtonText();

        // Mark all quality options
        document.querySelectorAll('.quality-option').forEach(opt => {
            if (opt.dataset.quality === newQuality) {
                opt.classList.add('active');
            } else {
                opt.classList.remove('active');
            }
        });

        // If something is playing, reload with new quality
        if (currentIndex >= 0 && player.src) {
            const wasPlaying = !player.paused;
            const currentTime = player.currentTime;

            playTrack(currentIndex);

            // Try to resume at the same position
            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }

        // Show toast notification
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

    /* -----------------------------------------------------------------
       Core playback logic (with quality parameter)
       ----------------------------------------------------------------- */
    function playTrack(index) {
        // 1. If index is same as current, don't reload the source
        if (index === currentIndex && player.src !== '') {
            player.play().catch(e => console.log('Autoplay prevented:', e));
            return;
        }

        // 2. Handle bounds and stopping
        if (index < 0 || index >= trackItems.length) {
            player.pause();
            player.src = '';
            container.style.display = 'none';
            trackItems.forEach(t => t.classList.remove('active-track'));
            currentIndex = -1;
            return;
        }

        const track = trackItems[index];

        // Build URL with quality parameter
        const basePath = track.dataset.path;
        const urlParams = new URLSearchParams();
        urlParams.set('quality', currentQuality);

        player.src = `${basePath}?${urlParams.toString()}`;

        bottomTitle.textContent = track.dataset.title;
        bottomArtistAlbum.textContent = `${track.dataset.artist} • ${track.dataset.album}`;
        container.style.display = 'block';

        trackItems.forEach(t => t.classList.remove('active-track'));
        track.classList.add('active-track');

        currentIndex = index;
        player.play().catch(e => console.log('Autoplay prevented:', e));
    }

    /* -----------------------------------------------------------------
       UI helpers (close, navigation, big‑play, auto‑start)
       ----------------------------------------------------------------- */
    document.getElementById('big-play-btn')?.addEventListener('click', () => {
        if (trackItems.length === 0) return;
        if (currentIndex === -1) playTrack(0);
        else player.play();
    });
    player?.addEventListener('play', syncPlayIcons);
    player?.addEventListener('pause', syncPlayIcons);
    prevBtn?.addEventListener('click', () => playTrack(currentIndex - 1));
    nextBtn?.addEventListener('click', () => playTrack(currentIndex + 1));
    player?.addEventListener('ended', () => {
        syncPlayIcons();
        playTrack(currentIndex + 1);
    });

    trackItems.forEach((item, i) => {
        const overlayBtn = item.querySelector('.play-overlay-btn');
        if (overlayBtn) {
            overlayBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (i === currentIndex) {
                    // Same track: toggle pause/resume
                    if (player.paused) {
                        player.play().catch(err => console.error("Resume failed:", err));
                    } else {
                        player.pause();
                    }
                } else {
                    // New track: load and play
                    playTrack(i);
                }
            });
        }
    });

    closeBtn?.addEventListener('click', () => {
        player.pause();
        container.style.display = 'none';
    });

    if (window.location.hash === '#play' && trackItems.length > 0) {
        setTimeout(() => playTrack(0), 500);
    }
    if (sessionStorage.getItem('startPlaybackNow') && trackItems.length > 0) {
        sessionStorage.removeItem('startPlaybackNow');
        playTrack(0);
    }

    /* -----------------------------------------------------------------
       Icon‑sync helper
       ----------------------------------------------------------------- */
    function syncPlayIcons() {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (icon) {
                icon.classList.remove('bi-pause-fill');
                icon.classList.add('bi-play-fill');
            }
            item.classList.remove('playing');
        });

        if (currentIndex >= 0 && !player.paused) {
            const activeItem = trackItems[currentIndex];
            if (activeItem) {
                activeItem.classList.add('playing');
                const activeIcon = activeItem.querySelector('.play-overlay-btn i');
                if (activeIcon) {
                    activeIcon.classList.remove('bi-play-fill');
                    activeIcon.classList.add('bi-pause-fill');
                }
            }
        } else if (currentIndex >= 0 && player.paused) {
            // Paused: show play icon on active
            const activeItem = trackItems[currentIndex];
            if (activeItem) {
                activeItem.classList.remove('playing');  // Remove green if paused
            }
        }
    }

    // Initialize quality selector
    initQualitySelector();

    /* -----------------------------------------------------------------
       Return the tiny public API that other modules can use.
       ----------------------------------------------------------------- */
    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
