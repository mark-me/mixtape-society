// static/js/editor/search.js
import { escapeHtml } from "./utils.js";
import { addToPlaylist } from "./playlist.js";

const searchInput = document.getElementById("searchInput");
const resultsDiv = document.getElementById("results");
let timeoutId;

const STORAGE_KEY = "mixtape_editor_search_query";

function getCurrentQuery() {
    return searchInput.value.trim();
}

/**
 * Performs a search query against the server and renders results
 */
function performSearch() {
    const query = getCurrentQuery();
    localStorage.setItem(STORAGE_KEY, query);

    if (query.length < 2) {
        resultsDiv.innerHTML = '<p class="text-muted text-center my-5">Type at least 3 characters to start searching…</p>';
        return;
    }

    document.getElementById("loading").classList.remove("visually-hidden");
    fetch(`/editor/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(renderResults)
        .finally(() => document.getElementById("loading").classList.add("visually-hidden"));
}

/**
 * Creates safe DOM IDs by replacing invalid characters with underscores
 */
function safeId(str) {
    if (!str) return 'unknown';
    return str
        .replace(/[^a-zA-Z0-9_-]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
}

/**
 * Formats duration from raw seconds or MM:SS string
 */
function formatDuration(duration) {
    if (typeof duration === 'string' && duration.includes(':')) return duration;
    const totalSeconds = parseFloat(duration);
    if (isNaN(totalSeconds)) return "?:??";
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Renders search results grouped by type (artists, albums, tracks)
 */
function renderResults(data) {
    if (data.length === 0) {
        resultsDiv.innerHTML = '<p class="text-center text-muted my-5">No results.</p>';
        return;
    }

    // Group by type
    const grouped = { artists: [], albums: [], tracks: [] };
    data.forEach(entry => {
        if (entry.type === 'artist') grouped.artists.push(entry);
        if (entry.type === 'album') grouped.albums.push(entry);
        if (entry.type === 'track') grouped.tracks.push(entry);
    });

    // Sort artists and albums alphabetically
    grouped.artists.sort((a, b) => (a.raw_artist || a.artist).localeCompare(b.raw_artist || b.artist));
    grouped.albums.sort((a, b) => (a.raw_album || a.album).localeCompare(b.raw_album || b.album));

    let html = '';

    // Render artists section
    if (grouped.artists.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Artists</h5>';
        html += grouped.artists.map(entry => {
            const safeArtist = safeId(entry.raw_artist || entry.artist);
            return `
                <div class="accordion mb-3" id="accordion-artist-${safeArtist}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-artist" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-artist-${safeArtist}"
                                    data-raw-artist="${escapeHtml(entry.raw_artist || entry.artist)}">
                                <i class="bi bi-person-fill me-2"></i>
                                <span class="flex-grow-1">${entry.artist}</span>
                                <span class="ms-auto small">
                                    <i class="bi bi-disc-fill me-1"></i>${entry.num_albums || 0}
                                </span>
                            </button>
                        </h2>
                        <div id="collapse-artist-${safeArtist}"
                            class="accordion-collapse collapse"
                            data-artist="${escapeHtml(entry.raw_artist || entry.artist)}">
                            <div class="accordion-body" data-loading="true">
                                <p class="text-muted">Loading…</p>
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    // Render albums section
    if (grouped.albums.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Albums</h5>';
        html += grouped.albums.map(entry => {
            const safeReleaseDir = safeId(entry.release_dir);
            const coverThumb = entry.cover ? `
                <div class="album-thumb me-2">
                    <img src="/${entry.cover}" alt="Album Cover" class="rounded">
                </div>` : '';

            return `
                <div class="accordion mb-3" id="accordion-album-${safeReleaseDir}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-album" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-album-${safeReleaseDir}"
                                    data-raw-album="${escapeHtml(entry.raw_album || entry.album)}"
                                    data-raw-artist="${escapeHtml(entry.raw_artist || entry.artist)}">
                                ${coverThumb}
                                <div class="flex-grow-1 min-w-0">
                                    <div class="album-title text-truncate">${entry.album}</div>
                                    <div class="album-artist text-truncate small text-muted">${entry.artist}</div>
                                </div>
                                <span class="ms-auto small">
                                    <i class="bi bi-music-note-beamed me-1"></i>${entry.num_tracks || 0}
                                </span>
                            </button>
                        </h2>
                        <div id="collapse-album-${safeReleaseDir}"
                            class="accordion-collapse collapse"
                            data-release_dir="${escapeHtml(entry.release_dir)}"
                            data-cover="${escapeHtml(entry.cover || '')}">
                            <div class="accordion-body" data-loading="true">
                                <p class="text-muted">Loading…</p>
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    // Render tracks section
    if (grouped.tracks.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Tracks</h5>';
        html += '<ul class="list-group">';
        html += grouped.tracks.map(entry => {
            const track = entry.tracks[0];
            return `
                <li class="list-group-item d-flex justify-content-between align-items-center mb-2 border rounded">
                    <div class="d-flex align-items-center flex-grow-1 gap-3 min-w-0">
                        ${track.cover ? `
                            <img src="/${track.cover}" alt="Track Cover" class="rounded" style="width: 50px; height: 50px; object-fit: cover; flex-shrink: 0;">
                        ` : ''}
                        <div class="flex-grow-1 min-w-0">
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <i class="bi bi-music-note-beamed text-track flex-shrink-0"></i>
                                <strong class="text-truncate">${entry.highlighted_tracks ? entry.highlighted_tracks[0].highlighted : escapeHtml(track.track)}</strong>
                            </div>
                            <small class="text-muted d-block text-truncate">${entry.artist}</small>
                            <small class="text-muted d-block text-truncate">${entry.album}</small>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-shrink-0 ms-2">
                        <span class="text-muted" style="min-width: 45px; text-align: right;">${formatDuration(track.duration || "?:??")}</span>
                        <button class="btn btn-track btn-sm preview-btn"
                                data-path="${escapeHtml(track.path)}"
                                data-title="${escapeHtml(track.track)}"
                                data-artist="${escapeHtml(entry.artist)}"
                                data-album="${escapeHtml(entry.album)}"
                                data-cover="${escapeHtml(track.cover || '')}">
                            <i class="bi bi-play-fill"></i>
                        </button>
                        <button class="btn btn-success btn-sm add-btn" data-item="${escapeHtml(JSON.stringify(track))}">
                            <i class="bi bi-plus-circle"></i>
                        </button>
                    </div>
                </li>`;
        }).join('');
        html += '</ul>';
    }

    resultsDiv.innerHTML = html;

    attachAddButtons();
    attachPreviewButtons();
    attachAccordionListeners();
}

/**
 * Lazy loading for artist and album accordion panels
 */
function attachAccordionListeners() {
    document.querySelectorAll('.accordion-collapse').forEach(collapse => {
        collapse.addEventListener('shown.bs.collapse', function () {
            const body = this.querySelector('.accordion-body');
            if (body.dataset.loading !== 'true') return;

            const artist = this.dataset.artist;
            const releaseDir = this.dataset.release_dir;
            const cover = this.dataset.cover;

            if (artist) {
                loadArtistDetails(artist, body);
            } else if (releaseDir) {
                loadAlbumDetails(releaseDir, cover, body);
            }
        });
    });
}

/**
 * Loads artist details (albums) via AJAX
 */
function loadArtistDetails(artist, body) {
    fetch(`/editor/artist_details?artist=${encodeURIComponent(artist)}`)
        .then(r => r.json())
        .then(details => {
            if (!details.albums || details.albums.length === 0) {
                body.innerHTML = '<p class="text-muted">No albums found.</p>';
                body.dataset.loading = 'false';
                return;
            }

            let html = '<div class="accordion accordion-flush" id="artist-albums-accordion">';
            details.albums.forEach((album, index) => {
                const albumId = safeId(album.album + '-' + index);
                const coverThumb = album.cover ? `
                    <div class="album-thumb me-2">
                        <img src="/${album.cover}" alt="Album Cover" class="rounded">
                    </div>` : '';
                
                // Show "Various Artists" subtitle for compilation albums
                const subtitle = album.is_compilation ? 
                    '<div class="album-artist text-truncate small text-muted">Various Artists</div>' : '';

                html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-album" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-album-${albumId}">
                                ${coverThumb}
                                <div class="flex-grow-1 min-w-0">
                                    <strong class="text-truncate d-block">${escapeHtml(album.album)}</strong>
                                    ${subtitle}
                                </div>
                                <span class="ms-auto small">
                                    <i class="bi bi-music-note-beamed me-1"></i>${album.tracks.length}
                                </span>
                            </button>
                        </h2>
                        <div id="collapse-album-${albumId}"
                            class="accordion-collapse collapse">
                            <div class="accordion-body">
                                <button class="btn btn-success btn-sm mb-3 add-album-btn"
                                        data-tracks="${escapeHtml(JSON.stringify(album.tracks))}">
                                    <i class="bi bi-plus-circle me-2"></i>Add whole album
                                </button>
                                <ul class="list-group">
                                    ${album.tracks.map(track => `
                                        <li class="list-group-item d-flex justify-content-between align-items-center">
                                            <div class="flex-grow-1 min-w-0">
                                                <span class="text-truncate d-block">${escapeHtml(track.track)}</span>
                                                <small class="text-muted">${formatDuration(track.duration || "?:??")}</small>
                                            </div>
                                            <div class="track-actions d-flex align-items-center gap-2 flex-shrink-0 ms-2">
                                                <button class="btn btn-track btn-sm preview-btn"
                                                        data-path="${escapeHtml(track.path)}"
                                                        data-title="${escapeHtml(track.track)}"
                                                        data-artist="${escapeHtml(track.artist)}"
                                                        data-album="${escapeHtml(track.album)}"
                                                        data-cover="${escapeHtml(album.cover || '')}">
                                                    <i class="bi bi-play-fill"></i>
                                                </button>
                                                <button class="btn btn-success btn-sm add-btn"
                                                        data-item="${escapeHtml(JSON.stringify(track))}">
                                                    <i class="bi bi-plus-circle"></i>
                                                </button>
                                            </div>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';

            body.innerHTML = html;
            body.dataset.loading = 'false';

            attachAddButtons();
            attachPreviewButtons();
        })
        .catch(err => {
            body.innerHTML = '<p class="text-danger">Failed to load albums.</p>';
            console.error(err);
        });
}

/**
 * Loads album details (tracks) via AJAX
 */
function loadAlbumDetails(releaseDir, cover, body) {
    fetch(`/editor/album_details?release_dir=${encodeURIComponent(releaseDir)}`)
        .then(r => r.json())
        .then(details => {
            // Use cover from accordion data if details.cover is not available
            const albumCover = details.cover || cover || '';

            const coverDisplay = albumCover ? `
                <div class="album-detail-cover mb-3">
                    <img src="/${albumCover}" alt="Album Cover" class="rounded shadow-sm">
                </div>` : '';

            const html = `
                ${coverDisplay}
                <h5 class="mb-1">${escapeHtml(details.album)}</h5>
                <p class="text-muted mb-3">${escapeHtml(details.artist)}</p>
                <button class="btn btn-success mb-3 add-album-btn"
                        data-tracks="${escapeHtml(JSON.stringify(details.tracks))}">
                    <i class="bi bi-plus-circle me-2"></i>Add whole album
                </button>
                <ul class="list-group">
                    ${details.tracks.map(track => `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <div class="flex-grow-1 min-w-0">
                                <span class="text-truncate d-block">${escapeHtml(track.track)}</span>
                                ${details.is_compilation ? 
                                    `<small class="text-muted">${escapeHtml(track.artist)} • ${formatDuration(track.duration || "?:??")}</small>` :
                                    `<small class="text-muted">${formatDuration(track.duration || "?:??")}</small>`
                                }
                            </div>
                            <div class="track-actions d-flex align-items-center gap-2 flex-shrink-0 ms-2">
                                <button class="btn btn-track btn-sm preview-btn"
                                        data-path="${escapeHtml(track.path)}"
                                        data-title="${escapeHtml(track.track)}"
                                        data-artist="${escapeHtml(details.artist)}"
                                        data-album="${escapeHtml(details.album)}"
                                        data-cover="${escapeHtml(albumCover)}">
                                    <i class="bi bi-play-fill"></i>
                                </button>
                                <button class="btn btn-success btn-sm add-btn"
                                        data-item="${escapeHtml(JSON.stringify(track))}">
                                    <i class="bi bi-plus-circle"></i>
                                </button>
                            </div>
                        </li>
                    `).join('')}
                </ul>`;
            body.innerHTML = html;
            body.dataset.loading = 'false';

            attachAddButtons();
            attachPreviewButtons();
        })
        .catch(err => {
            body.innerHTML = '<p class="text-danger">Loading failed.</p>';
            console.error(err);
        });
}

/**
 * Attaches click handlers to add buttons (single tracks and entire albums)
 */
function attachAddButtons() {
    document.querySelectorAll('.add-btn').forEach(btn => {
        btn.onclick = () => {
            const item = JSON.parse(btn.dataset.item);
            addToPlaylist(item);
        };
    });

    document.querySelectorAll('.add-album-btn').forEach(btn => {
        btn.onclick = () => {
            const tracks = JSON.parse(btn.dataset.tracks);
            tracks.forEach(addToPlaylist);
        };
    });
}

/**
 * Attaches click handlers to preview buttons with play/pause toggle
 */
function attachPreviewButtons() {
    // Remove old listeners by cloning nodes
    document.querySelectorAll('.preview-btn').forEach(btn => {
        btn.replaceWith(btn.cloneNode(true));
    });

    document.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const {path, title, artist, album, cover} = this.dataset;
            const trackName = title || 'Preview';
            const artistAlbum = (artist && album) ? `${artist} • ${album}` : (artist || album || 'Preview');

            if (!path) return;

            const player = document.getElementById('global-audio-player');
            const container = document.getElementById('audio-player-container');

            // Check if this button is already playing
            const isThisButtonPlaying = window.currentPreviewBtn === this;

            if (isThisButtonPlaying) {
                // Toggle play/pause for this track
                if (player.paused) {
                    player.play().catch(e => console.error("Preview failed:", e));
                    this.innerHTML = '<i class="bi bi-pause-fill"></i>';
                    this.classList.remove('btn-track');
                    this.classList.add('btn-warning');
                } else {
                    player.pause();
                    this.innerHTML = '<i class="bi bi-play-fill"></i>';
                    this.classList.remove('btn-warning');
                    this.classList.add('btn-track');
                }
                return;
            }

            // Stop any currently playing preview
            if (window.currentPreviewBtn && window.currentPreviewBtn !== this) {
                stopPreview();
            }

            player.src = `/play/${path}`;
            player.play().catch(e => console.error("Preview failed:", e));
            container.style.display = 'block';

            // Update now-playing info
            document.getElementById('now-playing-title').textContent = trackName;
            document.getElementById('now-playing-artist').textContent = artistAlbum;

            // Update player cover
            const playerCover = document.getElementById('now-playing-cover');
            if (cover && cover.trim()) {
                playerCover.src = `/${cover}`;
                playerCover.style.display = 'block';
            } else {
                playerCover.style.display = 'none';
            }

            // Visual feedback: change to pause icon
            this.innerHTML = '<i class="bi bi-pause-fill"></i>';
            this.classList.remove('btn-track');
            this.classList.add('btn-warning');

            window.currentPreviewBtn = this;
        });
    });
}

/**
 * Stops the current preview and resets button state
 */
function stopPreview() {
    const player = document.getElementById('global-audio-player');
    player.pause();
    player.src = '';
    if (window.currentPreviewBtn) {
        window.currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
        window.currentPreviewBtn.classList.remove('btn-warning');
        window.currentPreviewBtn.classList.add('btn-track');
        window.currentPreviewBtn = null;
    }
}

/**
 * Syncs the preview button state with the audio player
 */
function syncPreviewButtonState() {
    const player = document.getElementById('global-audio-player');
    if (!player || !window.currentPreviewBtn) return;

    const isPlaying = !player.paused && player.src;

    if (isPlaying) {
        window.currentPreviewBtn.innerHTML = '<i class="bi bi-pause-fill"></i>';
        window.currentPreviewBtn.classList.remove('btn-track');
        window.currentPreviewBtn.classList.add('btn-warning');
    } else {
        window.currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
        window.currentPreviewBtn.classList.remove('btn-warning');
        window.currentPreviewBtn.classList.add('btn-track');
    }
}

/**
 * Sets up audio player event listeners to keep preview button in sync
 */
function setupAudioPlayerSync() {
    const player = document.getElementById('global-audio-player');
    if (!player) return;

    player.addEventListener('play', syncPreviewButtonState);
    player.addEventListener('pause', syncPreviewButtonState);
    player.addEventListener('ended', () => {
        stopPreview();
    });
}

/**
 * Initializes the search functionality
 */
export function initSearch() {
    // Restore persisted query
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        searchInput.value = saved.trim();
        performSearch();
    }

    searchInput.addEventListener("input", () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(performSearch, 300);
    });

    // Initialize search hint popover
    new bootstrap.Popover(document.getElementById("searchHint"));

    // Set up audio player event listeners to keep preview button in sync
    setupAudioPlayerSync();
}
