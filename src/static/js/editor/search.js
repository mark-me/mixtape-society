// static/js/editor/search.js
import { escapeHtml, highlightText } from "./utils.js";
import { addToPlaylist } from "./playlist.js";

let timeoutId;
let resultIndex;  // Add this declaration to avoid undeclared variable errors
const searchInput = document.getElementById("searchInput");
const resultsDiv   = document.getElementById("results");

/**
 * Initializes the search input to trigger a debounced search request as the user types.
 * Ensures that search results are updated responsively while minimizing unnecessary requests.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initSearch() {
    searchInput.addEventListener("input", () => {
        clearTimeout(timeoutId);
        document.getElementById("loading").classList.remove("visually-hidden");
        timeoutId = setTimeout(doSearch, 300);
    });
}

/**
 * Performs a search request based on the user's input and updates the results display.
 * Handles both the minimum query length requirement and the asynchronous fetch of search results.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
function doSearch() {
    const q = searchInput.value.trim();
    if (q.length < 2) {
        resultsDiv.innerHTML = '<p class="text-muted text-center my-5">Typ minimaal 2 tekens om te zoeken…</p>';
        document.getElementById("loading").classList.add("visually-hidden");
        return;
    }
    fetch(`/editor/search?q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById("loading").classList.add("visually-hidden");
            renderResults(data);
        })
        .catch(err => {
            console.error(err);
            document.getElementById("loading").classList.add("visually-hidden");
        });
}

/**
 * Renders the search results in the UI and attaches add-to-playlist event listeners to result items.
 * Updates the results display based on the provided data and enables playlist management functionality.
 *
 * Args:
 *   data: The array of search result entries to render.
 *
 * Returns:
 *   None.
 */
function renderResults(data) {
    resultIndex = 0;

    if (data.length === 0) {
        resultsDiv.innerHTML = '<p class="text-center text-muted my-5">Geen resultaten gevonden.</p>';
        return;
    }

    resultsDiv.innerHTML = data.map(entry => {
        resultIndex++;
        const {type} = entry;
        const query = searchInput.value;
        const highlightedArtist = highlightText(entry.artist, query);
        const icons = { artist: 'bi-person-fill', album: 'bi-disc-fill', track: 'bi-music-note' };
        const colors = { artist: 'success', album: 'warning', track: 'primary' };
        const badges = entry.reasons.map(r => {
            return `<span class="badge bg-secondary me-1 mb-1">${escapeHtml(r)}</span>`;
        }).join('');

        if (type === 'artist') {
            return `
                <div class="card mb-3 shadow-sm">
                    <div class="card-header bg-${colors.artist} text-white">
                        <h3 class="h6 mb-0"><i class="bi ${icons.artist} me-1"></i>Artist: ${highlightedArtist}</h3>
                    </div>
                    <div class="card-body p-0">
                        <ul class="list-group list-group-flush">
                            ${entry.albums.map(album => {
                                const highlightedAlbum = highlightText(album.album, query);
                                return `
                                    <li class="list-group-item">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>${highlightedAlbum}</strong><br>
                                                <small class="text-muted">${album.year || 'Unknown year'}</small>
                                            </div>
                                            <button class="btn btn-sm btn-${colors.album} add-album-btn" data-tracks='${escapeHtml(JSON.stringify(album.tracks))}'>
                                                <i class="bi bi-plus-circle"></i> Add album
                                            </button>
                                        </div>
                                        <ul class="list-group mt-2">
                                            ${renderTracks(album.tracks, 'album')}
                                        </ul>
                                    </li>
                                `;
                            }).join('')}
                        </ul>
                    </div>
                </div>
            `;
        } else if (type === 'album') {
            const highlightedAlbum = highlightText(entry.album, query);
            return `
                <div class="card mb-3 shadow-sm">
                    <div class="card-header bg-${colors.album} text-white">
                        <h3 class="h6 mb-0"><i class="bi ${icons.album} me-1"></i>Album: ${highlightedAlbum} (${entry.year || 'Unknown year'}) – ${highlightedArtist}</h3>
                    </div>
                    <div class="card-body p-0">
                        <ul class="list-group list-group-flush">
                            ${renderTracks(entry.tracks, 'album')}
                        </ul>
                    </div>
                </div>
            `;
        } else if (type === 'track') {
            const highlightedTitle = highlightText(entry.track, query);
            const highlightedAlbum = highlightText(entry.album, query);
            const item = { artist: entry.artist, album: entry.album, title: entry.track, path: entry.path, duration: entry.duration };
            return `
                <div class="card mb-3 shadow-sm">
                    <div class="card-header bg-${colors.track} text-white">
                        <h3 class="h6 mb-0"><i class="bi ${icons.track} me-1"></i>Track: ${highlightedTitle} – ${highlightedArtist}</h3>
                    </div>
                    <div class="card-body d-flex justify-content-between align-items-center">
                        <div>
                            <small class="text-muted">From album: ${highlightedAlbum}</small><br>
                            <small class="text-muted">Duration: ${entry.duration || "?:??"}</small>
                        </div>
                        <div>
                            <button class="btn btn-sm btn-primary preview-btn"
                                    data-path="${encodeURIComponent(entry.path)}"
                                    data-title="${escapeHtml(entry.track)}">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-success add-btn"
                                    data-item='${escapeHtml(JSON.stringify(item))}'>
                                <i class="bi bi-plus-circle"></i> Add
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }).join('');

    // Attach add-to-playlist buttons (for individual tracks and albums)
    document.querySelectorAll('.add-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = JSON.parse(btn.dataset.item);
            addToPlaylist(item);
        });
    });

    document.querySelectorAll('.add-album-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tracks = JSON.parse(btn.dataset.tracks);
            tracks.forEach(track => addToPlaylist(track));
        });
    });

    // Local helper to render track lists (for albums)
    function renderTracks(tracks, type) {
        return tracks.map(track => {
            const highlightedTitle = highlightText(track.title, searchInput.value);
            const item = {
                artist: track.artist,
                album: track.album,
                title: track.title,
                path: track.path,
                duration: track.duration
            };
            return `
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <span class="track-title">${highlightedTitle}</span>
                        <small class="text-muted">(${track.duration || "?:??"})</small>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-primary preview-btn"
                                data-path="${encodeURIComponent(track.path)}"
                                data-title="${escapeHtml(track.title)}">
                            <i class="bi bi-play-fill"></i>
                        </button>
                        <button class="btn btn-sm btn-success add-btn"
                                data-item='${escapeHtml(JSON.stringify(item))}'>
                            <i class="bi bi-plus-circle"></i>
                        </button>
                    </div>
                </li>
            `;
        }).join('');
    }

    // Attach preview listeners
    attachPreviewListeners();  // Call here to re-attach after rendering
}

// Preview button handling
function attachPreviewListeners() {
    document.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const { path, title } = this.dataset;
            if (!path) return;

            // Toggle pause if the same button is already playing
            if (currentPreviewBtn === this && !player.paused) {
                stopPreview();
                return;
            }

            // Stop any other preview that might be playing
            stopPreview();

            // Start the new preview
            player.src = `/play/${path}`;
            player.play().catch(e => console.error("Preview mislukt:", e));

            container.style.display = 'block';

            // Change button appearance to “pause”
            this.innerHTML = '<i class="bi bi-pause-fill"></i>';
            this.classList.remove('btn-primary');
            this.classList.add('btn-warning');

            currentPreviewBtn = this;

            // ------- FUTURE‑PROOF TITLE ----------
            const nowPlayingTitle = title ||
                (this.closest('li')?.querySelector('.track-title')?.textContent?.trim() ?? '');

            document.getElementById('now-playing-title').textContent = nowPlayingTitle;
            document.getElementById('now-playing-artist').textContent = 'Preview';

            // Reset button when the preview finishes
            player.onended = stopPreview;
        });
    });
}

const player = document.getElementById('global-audio-player');
const container = document.getElementById('audio-player-container');
let currentPreviewBtn = null;

/**
 * Stops audio preview playback and resets the preview button state in the UI.
 * Ensures that any ongoing track preview is halted and the player interface is updated.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
function stopPreview() {
    player.pause();
    player.src = '';
    if (currentPreviewBtn) {
        currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
        currentPreviewBtn.classList.remove('btn-warning');
        currentPreviewBtn.classList.add('btn-primary');
        currentPreviewBtn = null;
    }
    // Optional: hide player if no playlist track is playing
    // (existing close button already handles pause/hide)
}
