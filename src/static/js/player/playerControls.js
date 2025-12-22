// static/js/player/playerControls.js
export function initPlayerControls() {
    const player = document.getElementById('main-player');
    const container = document.getElementById('bottom-player-container');
    const closeBtn = document.getElementById('close-bottom-player');
    const prevBtn = document.getElementById('prev-btn-bottom');
    const nextBtn = document.getElementById('next-btn-bottom');
    const trackItems = document.querySelectorAll('.track-item');
    const bottomTitle = document.getElementById('bottom-now-title');
    const bottomArtistAlbum = document.getElementById('bottom-now-artist-album');

    let currentIndex = -1;   // –1 means nothing playing

    /* -----------------------------------------------------------------
       Core playback logic (unchanged)
       ----------------------------------------------------------------- */
    function playTrack(index) {
        if (index < 0 || index >= trackItems.length) {
            player.pause();
            player.src = '';
            container.style.display = 'none';
            trackItems.forEach(t => t.classList.remove('active-track'));
            currentIndex = -1;
            return;
        }

        const track = trackItems[index];
        player.src = track.dataset.path;

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

    prevBtn?.addEventListener('click', () => playTrack(currentIndex - 1));
    nextBtn?.addEventListener('click', () => playTrack(currentIndex + 1));
    player?.addEventListener('ended', () => playTrack(currentIndex + 1));

    trackItems.forEach((item, i) => {
        item.addEventListener('click', () => playTrack(i));
        item.querySelector('.play-this-track')?.addEventListener('click', e => {
            e.stopPropagation();
            playTrack(i);
        });
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
       Icon‑sync helper – this is the piece that used to live in the
       global `updatePlayButtons` function.
       ----------------------------------------------------------------- */
    function syncPlayIcons() {
        // Reset every button to the “play” icon
        trackItems.forEach(item => {
            const icon = item.querySelector('.play-this-track i');
            if (icon) {
                icon.classList.remove('bi-pause-fill', 'bi-play-fill');
                icon.classList.add('bi-play-fill');
            }
        });

        // If something is playing, turn the active row’s icon into “pause”
        if (currentIndex >= 0 && !player.paused) {
            const activeIcon = trackItems[currentIndex]
                .querySelector('.play-this-track i');
            if (activeIcon) {
                activeIcon.classList.replace('bi-play-fill', 'bi-pause-fill');
            }
        }
    }

    /* -----------------------------------------------------------------
       Return the tiny public API that other modules can use.
       ----------------------------------------------------------------- */
    return {
        playTrack,          // (optional – you can call it from elsewhere)
        syncPlayIcons,
        // expose the DOM elements only if you really need them elsewhere
        // (kept private by default)
    };
}