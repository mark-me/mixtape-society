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

// ---------- Search ----------
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

// Helper to create safe DOM IDs (replaces invalid chars with underscores)
function safeId(str) {
    if (!str) return 'unknown';
    return str
        .replace(/[^a-zA-Z0-9_-]/g, '_')     // Replace invalid chars
        .replace(/_+/g, '_')                  // Collapse multiple underscores
        .replace(/^_+|_+$/g, '');             // Trim leading/trailing underscores
}

// Helper to format duration from raw seconds or MM:SS
function formatDuration(duration) {
    if (typeof duration === 'string' && duration.includes(':')) return duration;  // Already formatted
    const totalSeconds = parseFloat(duration);
    if (isNaN(totalSeconds)) return "?:??";
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// ---------- Rendering ----------
function renderResults(data) {
    if (data.length === 0) {
        resultsDiv.innerHTML = '<p class="text-center text-muted my-5">No results.</p>';
        return;
    }

    // Group by type to avoid repetition and sort
    const grouped = { artists: [], albums: [], tracks: [] };
    data.forEach(entry => {
        if (entry.type === 'artist') grouped.artists.push(entry);
        if (entry.type === 'album') grouped.albums.push(entry);
        if (entry.type === 'track') grouped.tracks.push(entry);
    });

    // Sort artists and albums alphabetically
    grouped.artists.sort((a, b) => (a.raw_artist || a.artist).localeCompare(b.raw_artist || b.artist));
    grouped.albums.sort((a, b) => (a.raw_album || a.album).localeCompare(b.raw_album || b.album));

    // Render grouped sections with headings for clarity
    let html = '';
    if (grouped.artists.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Artists</h5>';
        html += grouped.artists.map(entry => {
            const safeArtist = safeId(entry.raw_artist || entry.artist);

            return `
                <div class="accordion mb-3" id="accordion-artist-${safeArtist}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-success" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-artist-${safeArtist}"
                                    data-raw-artist="${escapeHtml(entry.raw_artist || entry.artist)}">
                                <i class="bi bi-person-fill me-2"></i>
                                ${entry.artist}
                                <span class="ms-auto small">
                                    <i class="bi bi-disc-fill me-2"></i>#${entry.num_albums || 0}
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

    if (grouped.albums.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Albums</h5>';
        html += grouped.albums.map(entry => {
            const safeReleaseDir = safeId(entry.release_dir);

            return `
                <div class="accordion mb-3" id="accordion-album-${safeReleaseDir}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-warning" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-album-${safeReleaseDir}"
                                    data-raw-album="${escapeHtml(entry.raw_album || entry.album)}"
                                    data-raw-artist="${escapeHtml(entry.raw_artist || entry.artist)}">
                                <i class="bi bi-disc-fill me-2"></i>
                                ${entry.album}
                                <span class="ms-auto small">
                                    <i class="bi bi-music-note-beamed me-2"></i>#${entry.num_tracks || 0}
                                </span>
                            </button>
                        </h2>
                        <div id="collapse-album-${safeReleaseDir}"
                             class="accordion-collapse collapse"
                             data-release_dir="${escapeHtml(entry.release_dir)}">
                            <div class="accordion-body" data-loading="true">
                                <p class="text-muted">Loading…</p>
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    if (grouped.tracks.length > 0) {
        html += '<h5 class="mt-4 mb-2 text-muted">Tracks</h5>';
        html += '<ul class="list-group">';
        html += grouped.tracks.map(entry => {
            const track = entry.tracks[0];
            return `
                <li class="list-group-item d-flex justify-content-between align-items-center mb-2 border rounded">
                    <div class="flex-grow-1">
                        <i class="bi bi-music-note-beamed me-2 text-primary"></i>
                        <strong>${entry.highlighted_tracks ? entry.highlighted_tracks[0].highlighted : escapeHtml(track.track)}</strong><br>
                        <small class="text-muted">
                            ${entry.artist} • ${entry.album}
                        </small>
                    </div>
                    <div class="d-flex align-items-center">
                        <div class="track-actions d-flex align-items-center gap-2">
                            <span class="text-muted me-3">${formatDuration(track.duration || "?:??")}</span>
                            <button class="btn btn-primary btn-sm preview-btn" 
                                    data-path="${escapeHtml(track.path)}" 
                                    data-title="${escapeHtml(track.track)}"
                                    data-artist="${escapeHtml(entry.artist)}"
                                    data-album="${escapeHtml(entry.album)}">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-success btn-sm add-btn" data-item="${escapeHtml(JSON.stringify(track))}">
                                <i class="bi bi-plus-circle"></i>
                            </button>
                        </div>
                    </div>
                </li>`;
        }).join('');
        html += '</ul>';
    }

    resultsDiv.innerHTML = html;

    attachAddButtons();
    attachPreviewButtons();
    attachAccordionListeners();
    attachRefineLinks();
}

// ---------- Lazy loading for artists and albums ----------
function attachAccordionListeners() {
    document.querySelectorAll('.accordion-collapse').forEach(collapse => {
        collapse.addEventListener('shown.bs.collapse', function () {
            const body = this.querySelector('.accordion-body');
            if (body.dataset.loading !== 'true') return;

            if (this.dataset.artist) {  // Artist details
                loadArtistDetails(this);
            } else if (this.dataset.release_dir) {  // Album details
                loadAlbumDetails(this);
            }
        });
    });
}

function loadArtistDetails(collapse) {
    const {artist} = collapse.dataset;
    const body = collapse.querySelector('.accordion-body');

    fetch(`/editor/artist_details?artist=${encodeURIComponent(artist)}`)
        .then(r => r.json())
        .then(details => {
            if (details.albums.length === 0) {
                body.innerHTML = '<p class="text-muted">No albums found.</p>';
                body.dataset.loading = 'false';
                return;
            }

            let html = '<div class="accordion accordion-flush" id="artist-albums-accordion">';
            details.albums.forEach((album, index) => {
                const albumId = safeId(album.album + '-' + index);  // Unique ID using safeId
                html += `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-warning" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-album-${albumId}">
                                <i class="bi bi-disc-fill me-2"></i>
                                <strong>${escapeHtml(album.album)}</strong>
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
                                            <div>
                                                ${escapeHtml(track.track)}
                                                <small class="text-muted ms-2">(${formatDuration(track.duration || "?:??")})</small>
                                            </div>
                                            <div>
                                                <div class="track-actions d-flex align-items-center gap-2">
                                                    <button class="btn btn-primary btn-sm preview-btn me-2"
                                                            data-path="${escapeHtml(track.path)}"
                                                            data-title="${escapeHtml(track.track)}"
                                                            data-artist="${escapeHtml(track.artist)}"
                                                            data-album="${escapeHtml(track.album)}">
                                                        <i class="bi bi-play-fill"></i>
                                                    </button>
                                                    <button class="btn btn-success btn-sm add-btn"
                                                            data-item="${escapeHtml(JSON.stringify(track))}">
                                                        <i class="bi bi-plus-circle"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>`;
            });
            html += '</div>';

            body.innerHTML = html;
            body.dataset.loading = 'false';

            // Re-attach buttons after dynamic content
            attachAddButtons();
            attachPreviewButtons();
        })
        .catch(err => {
            body.innerHTML = '<p class="text-danger">Failed to load albums.</p>';
            console.error(err);
        });
}

function loadAlbumDetails(collapse) {
    const {release_dir} = collapse.dataset;
    const body = collapse.querySelector('.accordion-body');

    fetch(`/editor/album_details?release_dir=${encodeURIComponent(release_dir)}`)
        .then(r => r.json())
        .then(details => {
            let html = `
                <h5>${escapeHtml(details.album)} — ${escapeHtml(details.artist)}</h5>
                <button class="btn btn-success mb-3 add-album-btn"
                        data-tracks="${escapeHtml(JSON.stringify(details.tracks))}">
                    Add whole album
                </button>
                <ul class="list-group">
                    ${details.tracks.map(track => `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                ${escapeHtml(track.track)}
                                <small class="text-muted ms-2">(${formatDuration(track.duration || "?:??")})</small>
                            </div>
                            <div>
                                <div class="track-actions d-flex align-items-center gap-2">
                                    <button class="btn btn-primary btn-sm preview-btn me-2"
                                            data-path="${escapeHtml(track.path)}"
                                            data-title="${escapeHtml(track.track)}"
                                            data-artist="${escapeHtml(track.artist)}"
                                            data-album="${escapeHtml(track.album)}">
                                        <i class="bi bi-play-fill"></i>
                                    </button>
                                    <button class="btn btn-success btn-sm add-btn"
                                            data-item="${escapeHtml(JSON.stringify(track))}">
                                        <i class="bi bi-plus-circle"></i>
                                    </button>
                                </div>
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

// ---------- Refine search by clicking result headers ----------
function attachRefineLinks() {
    document.querySelectorAll('.accordion-button').forEach(btn => {
        btn.style.cursor = "pointer";
        btn.addEventListener("click", function (e) {
            if (e.target.closest("[data-bs-toggle]")) return; // let accordion work
            const isArtist = this.classList.contains("bg-success");
            const isAlbum = this.classList.contains("bg-warning");

            if (isArtist) {
                const artist = this.dataset.rawArtist;  // Use raw_artist (handles spaces)
                if (artist) {
                    searchInput.value = "";
                    performSearch();
                }
            } else if (isAlbum) {
                const album = this.dataset.rawAlbum;  // Use raw_album (handles special chars/spaces)
                if (album) {
                    searchInput.value = "";
                    performSearch();
                }
            }
        });
    });
}

// ---------- Add to playlist ----------
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

// Preview handling
function attachPreviewButtons() {
    document.querySelectorAll('.preview-btn').forEach(btn => {
        // Remove any old listener to prevent duplicates
        btn.replaceWith(btn.cloneNode(true));
    });

    document.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const {path, title, artist, album} = this.dataset;
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
                    this.classList.remove('btn-primary');
                    this.classList.add('btn-warning');
                } else {
                    player.pause();
                    this.innerHTML = '<i class="bi bi-play-fill"></i>';
                    this.classList.remove('btn-warning');
                    this.classList.add('btn-primary');
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

            // Use the helper function from ui.js to update track info
            if (window.updatePlayerTrackInfo) {
                window.updatePlayerTrackInfo(trackName, artistAlbum);
            } else {
                // Fallback if the helper function isn't available yet
                document.getElementById('now-playing-title').textContent = trackName;
                document.getElementById('now-playing-artist').textContent = artistAlbum;
            }

            // Visual feedback: change to pause icon
            this.innerHTML = '<i class="bi bi-pause-fill"></i>';
            this.classList.remove('btn-primary');
            this.classList.add('btn-warning');

            window.currentPreviewBtn = this;

            player.onended = () => stopPreview();
        });
    });
}

function stopPreview() {
    const player = document.getElementById('global-audio-player');
    player.pause();
    player.src = '';
    if (window.currentPreviewBtn) {
        window.currentPreviewBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
        window.currentPreviewBtn.classList.remove('btn-warning');
        window.currentPreviewBtn.classList.add('btn-primary');
        window.currentPreviewBtn = null;
    }
}

// ---------- Init ----------
export function initSearch() {
    // Restore persisted query
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        searchInput.value = saved.replace(/^(.*?)\s*$/, ""); // extract free text
        performSearch();
    }

    searchInput.addEventListener("input", () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(performSearch, 300);
    });

    // Initial popover
    new bootstrap.Popover(document.getElementById("searchHint"));
}