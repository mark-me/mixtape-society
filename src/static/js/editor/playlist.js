import { escapeHtml } from "./utils.js";

const {Sortable} = window;

export let playlist = [];               // exported so other modules (e.g. notes) can read it
const playlistOl = document.getElementById("playlist");
const playlistCount = document.getElementById("playlist-count");

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
    // Duplicate check
    const isDuplicate = playlist.some(t =>
        t.artist === item.artist &&
        t.album === item.album &&
        t.title === item.title &&
        t.path === item.path
    );
    if (isDuplicate) return;

    playlist.push(item);
    renderPlaylist();
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
        });

    // Sortable.js integration
    new Sortable(playlistOl, {
        animation: 150,
        ghostClass: "playlist-ghost",
        handle: ".drag-handle",
        onEnd: evt => {
            const moved = playlist.splice(evt.oldIndex, 1)[0];
            playlist.splice(evt.newIndex, 0, moved);
            renderPlaylist();
        }
    });
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
    playlistOl.innerHTML = playlist.map((item, idx) => `
        <li class="d-flex align-items-center rounded p-3 mb-2 shadow-sm playlist-item
        bg-body-tertiary border" data-index="${idx}">
            <div class="drag-handle me-3 text-muted">⋮⋮</div>

            <!-- Play knop -->
            <button class="btn btn-success btn-sm me-2 play-track-btn"
                    data-path="${encodeURIComponent(item.path || '')}"
                    ${item.path ? '' : 'disabled title="Geen bestand"'}>
                <i class="bi ${item.path ? 'bi-play-fill' : 'bi-ban'}"></i>
            </button>

            <div class="flex-grow-1">
                <strong>${escapeHtml(item.title)}</strong><br>
                <small class="text-muted">${escapeHtml(item.artist)} • ${escapeHtml(item.album)}</small>
            </div>
            <span class="text-muted me-3">${item.duration || "?:??"}</span>
            <button class="btn btn-danger btn-sm remove-btn" data-index="${idx}">
                <i class="bi bi-trash-fill"></i>
            </button>
        </li>
    `).join('');

    playlistCount.textContent = `(${playlist.length})`;

    // === PLAY BUTTONS ===
    document.querySelectorAll('.play-track-btn').forEach(btn => {
        btn.onclick = function () {
            const { path } = this.dataset;
            if (!path) return;

            const player = document.getElementById('global-audio-player');
            const container = document.getElementById('audio-player-container');

            player.src = `/play/${path}`;
            player.play().catch(e => console.error("Afspelen mislukt:", e));

            container.style.display = 'block';

            // Update titel + highlight
            const item = playlist[this.closest('.playlist-item').dataset.index];
            document.getElementById('now-playing-title').textContent = item.title;
            document.getElementById('now-playing-artist').textContent = `${item.artist} • ${item.album}`;

            document.querySelectorAll('.playlist-item').forEach(el =>
                el.classList.remove('bg-primary', 'text-white')
            );
            this.closest('.playlist-item').classList.add('bg-primary', 'text-white');
        };
    });

    // Delete buttons
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.onclick = () => {
            playlist.splice(btn.dataset.index, 1);
            renderPlaylist();
        };
    });
}

