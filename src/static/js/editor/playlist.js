// static/js/editor/playlist.js
import { escapeHtml } from "./utils.js";

const { Sortable } = window;

export let playlist = [];               // exported so other modules (e.g. notes) can read it
const playlistOl = document.getElementById("playlist");
const playlistCount = document.getElementById("playlist-count");

/* -----------------------------------------------------------------
*  Unsaved‑changes callback
*
*  UI code (ui.js) will register a function that should be called
*  whenever the playlist is mutated (add, clear, remove, reorder).
*  This decouples the playlist module from the UI and avoids a
*  circular import.
* -----------------------------------------------------------------*/
let unsavedCallback = () => { };               // default — no‑op
export function registerUnsavedCallback(cb) {
    if (typeof cb === "function") unsavedCallback = cb;
}

let trackRemovedCallback = () => {};  // new

export function registerTrackRemovedCallback(cb) {
    if (typeof cb === "function") trackRemovedCallback = cb;
}


let trackAddedCallback = () => {};

export function registerTrackAddedCallback(cb) {
    // Registers a callback to be invoked whenever a track is added to the playlist.
    // Allows external modules to hook into playlist growth events, such as updating UI state or metadata.
    if (typeof cb === "function") trackAddedCallback = cb;
}

export function setPlaylist(newTracks) {
    // Replace the current contents atomically
    playlist.length = 0;
    newTracks.forEach(t => playlist.push(t));
}

/**
 * Initializes the playlist UI and event handlers for user interaction.
 * Sets up the playlist display and enables playlist management features.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initPlaylist() {
    renderPlaylist();                  // initial empty render
    attachPlaylistEvents();
    setupAudioPlayerListeners();      // Listen for play/pause events
}

/**
 * Adds a track item to the playlist if it is not already present.
 * Prevents duplicate tracks and updates the playlist display after addition.
 *
 * Args:
 *   item: The track object to add to the playlist.
 *
 * Returns:
 *   None.
 */
export function addToPlaylist(item) {

    // ────────────────────────────────────────────────────────────
    // 1. Safety net: if the item comes from a direct search result,
    //    it might have a "tracks" array instead of being a flat track.
    // ────────────────────────────────────────────────────────────
    if (item.tracks && Array.isArray(item.tracks) && item.tracks.length > 0) {
        const sub = item.tracks[0];
        item = {
            artist: item.raw_artist || item.artist || '',
            album: item.raw_album || item.album || '',
            track: sub.track || '',
            duration: sub.duration || '',
            path: sub.path || '',
            filename: sub.filename || '',
            cover: item.cover || '',
        };
    }

    // ────────────────────────────────────────────────────────────
    // 2. Normalization: guarantee the exact structure we need
    //    Now that we have standardized on 'track' in the backend,
    //    we no longer need the fallback to 'title'.
    // ────────────────────────────────────────────────────────────
    const normalized = {
        artist: item.artist || '',
        album: item.album || '',
        track: item.track || '',
        duration: item.duration || '',
        path: item.path || '',
        filename: item.filename || '',
        cover: item.cover || ''
    };

    // ────────────────────────────────────────────────────────────
    // 3. Duplicate check using the normalized fields
    // ────────────────────────────────────────────────────────────
    const exists = playlist.some(t => t.path === item.path);
    if (exists) return;

    // ────────────────────────────────────────────────────────────
    // 4. Add to playlist and refresh UI
    // ────────────────────────────────────────────────────────────
    playlist.push(normalized);
    renderPlaylist();
    updatePlaylistCount();

    trackAddedCallback();
    unsavedCallback();
}


/**
 * Attaches event handlers for clearing and reordering the playlist in the UI.
 * Enables users to clear all tracks and drag to reorder tracks using Sortable.js.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
function attachPlaylistEvents() {
    document.getElementById("clear-playlist")
        .addEventListener("click", () => {
            playlist = [];
            renderPlaylist();
            unsavedCallback();
        });

    // Sortable.js integration
    Sortable.create(playlistOl, {
        animation: 150,
        handle: '.drag-handle',
        onEnd: () => {
            // Rebuild playlist array from DOM order
            const newOrder = [...playlistOl.children].map(li => {
                const {index} = li.dataset;
                return playlist[index];
            });
            playlist.length = 0;
            newOrder.forEach(t => playlist.push(t));

            renderPlaylist();        // updates data-index attributes
            unsavedCallback();       // ← correct: only unsaved, no toast
        }
    });
}

export function updatePlaylistCount() {
    // Updates the visible playlist count indicator in the UI.
    // Ensures the displayed track count stays in sync with the current playlist length.
    if (playlistCount) {
        playlistCount.textContent = playlist.length;
    }
}

/**
 * Sets up audio player event listeners to sync play/pause button states
 */
function setupAudioPlayerListeners() {
    const player = document.getElementById('global-audio-player');
    if (!player) return;

    player.addEventListener('play', updatePlayPauseButtons);
    player.addEventListener('pause', updatePlayPauseButtons);
    player.addEventListener('ended', updatePlayPauseButtons);
}

/**
 * Updates all play/pause button states based on current playback
 */
function updatePlayPauseButtons() {
    const player = document.getElementById('global-audio-player');
    const isPlaying = player && !player.paused;

    document.querySelectorAll('.play-track-btn').forEach(btn => {
        const icon = btn.querySelector('i');
        if (!icon) return;

        const trackPath = btn.dataset.path;
        const currentSrc = player.src;

        // Check if this button's track is currently playing
        const isThisTrackPlaying = currentSrc && currentSrc.includes(encodeURIComponent(trackPath));

        if (isThisTrackPlaying && isPlaying) {
            // This track is playing - show pause icon
            icon.classList.remove('bi-play-fill', 'bi-ban');
            icon.classList.add('bi-pause-fill');
        } else {
            // This track is not playing or paused - show play icon
            icon.classList.remove('bi-pause-fill', 'bi-ban');
            icon.classList.add(trackPath ? 'bi-play-fill' : 'bi-ban');
        }
    });
}

// -----------------------------------------------------------------
// Helper — tiny wrapper around escapeHtml so we don't forget any field
// -----------------------------------------------------------------
function esc(value) {
    // Convert undefined/null to empty string first
    if (value == null) return "";
    // For numbers we can just return the string representation
    if (typeof value === "number") return String(value);
    // For everything else we run it through escapeHtml (which creates a div,
    // sets textContent, and returns the escaped HTML).
    return escapeHtml(String(value));
}

/**
 * Renders the current playlist in the UI and attaches event handlers for playback and removal.
 * Updates the playlist display, enables track playback, and allows users to remove tracks from the playlist.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function renderPlaylist() {
    // Build the markup safely — every dynamic piece goes through `esc()`.
    playlistOl.innerHTML = playlist.map((item, idx) => `
        <li class="d-flex align-items-center rounded p-3 mb-2 shadow-sm playlist-item bg-body-tertiary border"
            data-index="${esc(idx)}">

            <div class="drag-handle me-3 text-muted">⋮⋮</div>

            <!-- Cover wrapper -->
            <div class="track-cover-wrapper me-3">
                ${item.cover
                    ? `<img src="/${esc(item.cover)}" alt="Cover" class="track-cover">`
                    : `<div class="track-cover-placeholder"></div>`
                }
                <button class="btn play-overlay-btn"
                        data-path="${esc(encodeURIComponent(item.path || ""))}"
                        ${item.path ? "" : 'disabled'}>
                    <i class="bi bi-play-fill"></i>
                </button>
            </div>

            <!-- Text content — critical: min-w-0 enables truncation in flex -->
            <div class="flex-grow-1 min-w-0 me-3">
                <strong class="text-truncate">${esc(item.track)}</strong>
                <small class="text-muted text-truncate">${esc(item.artist)} • ${esc(item.album)}</small>
            </div>

            <!-- Duration — fixed width to prevent squeeze -->
            <span class="text-muted me-3 flex-shrink-0" style="min-width: 50px; text-align: right;">
                ${esc(item.duration) || "?:??"}
            </span>

            <!-- Delete button — always visible -->
            <button class="btn btn-danger btn-sm flex-shrink-0 remove-btn" data-index="${esc(idx)}">
                <i class="bi bi-trash-fill"></i>
            </button>
        </li>
    `).join("");

    playlistCount.textContent = `(${playlist.length})`;

    document.querySelectorAll('.play-overlay-btn').forEach(btn => {
        btn.onclick = function (e) {
            e.stopPropagation();

            const {path} = this.dataset;
            if (!path) return;

            const player = document.getElementById('global-audio-player');
            const container = document.getElementById('audio-player-container');
            const playlistItem = this.closest('.playlist-item');
            const icon = this.querySelector('i');

            // Get current source (safely)
            const currentSrc = player.src ? player.src.split('/').pop() : '';
            const isThisTrack = currentSrc === path;

            // Remove 'playing' class from all items
            document.querySelectorAll('.playlist-item.playing').forEach(el => {
                el.classList.remove('playing');
                // Reset icon to play when not playing
                const btnIcon = el.querySelector('.play-overlay-btn i');
                if (btnIcon) {
                    btnIcon.classList.replace('bi-pause-fill', 'bi-play-fill');
                }
            });

            if (isThisTrack) {
                // Same track clicked
                if (player.paused) {
                    // Was paused → resume
                    player.play().catch(err => console.error("Resume failed:", err));
                    playlistItem.classList.add('playing');
                    icon.classList.replace('bi-play-fill', 'bi-pause-fill');
                } else {
                    // Was playing → pause
                    player.pause();
                    playlistItem.classList.remove('playing');
                    icon.classList.replace('bi-pause-fill', 'bi-play-fill');
                }
            } else {
                // Different track → load and play
                player.src = `/play/${path}`;
                player.play().catch(err => console.error("Play failed:", err));
                container.style.display = 'block';

                // Mark as playing
                playlistItem.classList.add('playing');
                icon.classList.replace('bi-play-fill', 'bi-pause-fill');

                // Update now-playing info
                const item = playlist[playlistItem.dataset.index];
                document.getElementById('now-playing-title').textContent = item.track;
                document.getElementById('now-playing-artist').textContent = `${item.artist} • ${item.album}`;

                // Update player cover
                const playerCover = document.getElementById('now-playing-cover');
                if (item.cover) {
                    playerCover.src = `/${item.cover}`;
                    playerCover.style.display = 'block';
                } else {
                    playerCover.style.display = 'none';
                }
            }
        };
    });
    // === PLAY/PAUSE BUTTONS ===
    document.querySelectorAll('.play-track-btn').forEach(btn => {
        btn.onclick = function () {
            const { path } = this.dataset;
            if (!path) return;

            const player = document.getElementById('global-audio-player');
            const container = document.getElementById('audio-player-container');
            const currentSrc = player.src;
            const isThisTrackPlaying = currentSrc && currentSrc.includes(path);

            // If this track is already playing, toggle play/pause
            if (isThisTrackPlaying) {
                if (player.paused) {
                    player.play().catch(e => console.error("Play failed:", e));
                } else {
                    player.pause();
                }
                return;
            }

            // Otherwise, load and play this track
            player.src = `/play/${path}`;
            player.play().catch(e => console.error("Play failed:", e));

            container.style.display = 'block';

            // Update title + highlight with theme-aware classes
            const item = playlist[this.closest('.playlist-item').dataset.index];
            document.getElementById('now-playing-title').textContent = item.track;
            document.getElementById('now-playing-artist').textContent = `${item.artist} • ${item.album}`;

            // Set player cover
            const playerCover = document.getElementById('now-playing-cover');
            if (item.cover) {
                playerCover.src = `/${item.cover}`;
                playerCover.style.display = 'block';
            } else {
                playerCover.style.display = 'none';
            }

            // Remove highlight from all items
            document.querySelectorAll('.playlist-item').forEach(el => {
                el.classList.remove('bg-track', 'text-white', 'bg-track-subtle', 'border-track');
            });

            // Add theme-aware highlight to current item
            const playlistItem = this.closest('.playlist-item');
            playlistItem.classList.add('bg-track-subtle', 'border-track');
        };
    });

    // Delete buttons
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.onclick = () => {
            const index = Number(btn.dataset.index);
            playlist.splice(index, 1);
            renderPlaylist();
            trackRemovedCallback();
            unsavedCallback();
        };
    });

    // Update play/pause button states after rendering
    updatePlayPauseButtons();
}
