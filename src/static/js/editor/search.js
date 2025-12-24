// static/js/editor/search.js
import { escapeHtml, highlightText } from "./utils.js";
import { addToPlaylist } from "./playlist.js";

const searchInput = document.getElementById("searchInput");
const badgesContainer = document.getElementById("searchBadges");
const resultsDiv = document.getElementById("results");
let timeoutId;

const TAG_COLORS = {
    artist: "bg-success",
    album:  "bg-warning",
    track:  "bg-primary",
    song:   "bg-primary"
};

const STORAGE_KEY = "mixtape_editor_search_query";

// ---------- Badge management ----------
function createBadge(tagType, value) {
    const badge = document.createElement("span");
    badge.className = `badge ${TAG_COLORS[tagType]} text-white me-1`;
    badge.textContent = `${tagType}:${value}`;
    badge.dataset.type = tagType;
    badge.dataset.value = value;
    badge.tabIndex = 0;
    badge.role = "button";
    badge.ariaLabel = `Remove tag ${tagType}:${value}`;

    const close = document.createElement("span");
    close.className = "ms-2";
    close.innerHTML = "&times;";
    close.style.cursor = "pointer";
    close.onclick = (e) => {
        e.stopPropagation();
        badge.remove();
        performSearch();
    };
    badge.appendChild(close);

    badge.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            badge.remove();
            performSearch();
        }
    });

    badgesContainer.appendChild(badge);
    badgesContainer.style.pointerEvents = "auto";
}

function rebuildBadgesFromQuery(query) {
    badgesContainer.innerHTML = "";
    const tagRegex = /(artist|album|track|song):"([^"]+)"|(artist|album|track|song):([^\s]+)/g;
    let match;
    while ((match = tagRegex.exec(query))) {
        const type = match[1] || match[3];
        const value = match[2] || match[4];
        createBadge(type, value);
    }
}

function getCurrentQuery() {
    const input = searchInput.value.trim();
    const badges = Array.from(badgesContainer.querySelectorAll(".badge"));
    const tagParts = badges.map(b => `${b.dataset.type}:"${b.dataset.value}"`);
    return [...tagParts, input].filter(Boolean).join(" ");
}

// ---------- Search ----------
function performSearch() {
    const query = getCurrentQuery();
    localStorage.setItem(STORAGE_KEY, query);

    if (query.length < 2) {
        resultsDiv.innerHTML = '<p class="text-muted text-center my-5">Typ minimaal 2 tekens…</p>';
        return;
    }

    document.getElementById("loading").classList.remove("visually-hidden");
    fetch(`/editor/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(renderResults)
        .finally(() => document.getElementById("loading").classList.add("visually-hidden"));
}

// ---------- Rendering ----------
function renderResults(data) {
    if (data.length === 0) {
        resultsDiv.innerHTML = '<p class="text-center text-muted my-5">Geen resultaten gevonden.</p>';
        return;
    }

    resultsDiv.innerHTML = data.map(entry => {
        // Helper: create a safe ID by replacing invalid chars with underscores
        const safeId = (str) => str
            .replace(/[^a-zA-Z0-9_-]/g, '_')     // Replace everything except letters, numbers, - and _
            .replace(/_+/g, '_')                  // Collapse multiple underscores
            .replace(/^_+/g, '')                  // Remove leading underscores
            .replace(/_+$/g, '');                 // Remove trailing underscores

        if (entry.type === "artist") {
            const safeArtist = safeId(entry.artist);
            return `
                <div class="accordion mb-3" id="accordion-artist-${safeArtist}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-success text-white" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-artist-${safeArtist}">
                                <i class="bi bi-person-fill me-2"></i>
                                Artist: ${entry.artist}
                                <span class="ms-auto small opacity-75">${entry.reasons.map(r => r.text).join(" • ")}</span>
                            </button>
                        </h2>
                        <div id="collapse-artist-${safeArtist}"
                             class="accordion-collapse collapse"
                             data-artist="${escapeHtml(entry.artist)}">
                            <div class="accordion-body" data-loading="true">
                                <p class="text-muted">Laden…</p>
                            </div>
                        </div>
                    </div>
                </div>`;
        }

        if (entry.type === "album") {
            const safeReleaseDir = safeId(entry.release_dir);
            const artistText = entry.is_compilation ? "Various Artists" : entry.artist;
            return `
                <div class="accordion mb-3" id="accordion-album-${safeReleaseDir}">
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed bg-warning text-dark" type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#collapse-album-${safeReleaseDir}">
                                <i class="bi bi-disc-fill me-2"></i>
                                Album: ${entry.album} — ${artistText}
                                <span class="ms-auto small opacity-75">${entry.reasons.map(r => r.text).join(" • ")}</span>
                            </button>
                        </h2>
                        <div id="collapse-album-${safeReleaseDir}"
                             class="accordion-collapse collapse"
                             data-release-dir="${escapeHtml(entry.release_dir)}">
                            <div class="accordion-body" data-loading="true">
                                <p class="text-muted">Laden…</p>
                            </div>
                        </div>
                    </div>
                </div>`;
        }

        // Track entry (no accordion needed)
        if (entry.type === "track") {
            const track = entry.tracks[0];  // already prepared by backend
            const cleanArtist = entry.artist.replace(/<[^>]*>/g, '');
            const cleanAlbum  = entry.album.replace(/<[^>]*>/g, '');

            return `
                <div class="card mb-3 shadow-sm">
                    <div class="card-body d-flex justify-content-between align-items-center py-3">
                        <div class="flex-grow-1">
                            <strong>${escapeHtml(track.title)}</strong><br>
                            <small class="text-muted">${escapeHtml(cleanArtist)} • ${escapeHtml(cleanAlbum)}</small>
                            <small class="text-muted ms-3">(${track.duration || "?:??"})</small>
                        </div>
                        <div>
                            <button class="btn btn-primary btn-sm preview-btn me-2"
                                    data-path="${escapeHtml(track.path)}"
                                    data-title="${escapeHtml(track.title)}">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-success btn-sm add-btn"
                                    data-item='${escapeHtml(JSON.stringify({
                                        artist: cleanArtist,
                                        album:  cleanAlbum,
                                        title:  track.title,
                                        path:   track.path,
                                        duration: track.duration,
                                        filename: track.filename || ""
                                    }))}'>
                                <i class="bi bi-plus-circle"></i>
                            </button>
                        </div>
                    </div>
                </div>`;
        }
    }).join("");

    attachAddButtons();
    attachPreviewButtons();
    attachAccordionLazyLoad();
    attachRefineLinks();
}

// static/js/editor/search.js
function attachAccordionLazyLoad() {
    document.querySelectorAll('.accordion-collapse').forEach(coll => {
        coll.addEventListener('shown.bs.collapse', function () {
            const body = this.querySelector('.accordion-body');
            if (body.dataset.loading !== "true") return;

            body.dataset.loading = "false";
            body.innerHTML = '<p class="text-muted">Laden…</p>';

            let url, param, value;
            if (this.dataset.artist) {
                url = "/editor/artist_details";
                param = "artist";
                value = this.dataset.artist;
            } else if (this.dataset.releaseDir) {
                url = "/editor/album_details";
                param = "release_dir";
                value = this.dataset.releaseDir;
            } else return;

            fetch(`${url}?${param}=${encodeURIComponent(value)}`)
                .then(r => r.json())
                .then(data => {
                    let html = '';

                    if (data.artist) {
                        // === ARTIST DETAILS ===
                        html = data.albums.map(alb => `
                            <div class="mb-4 p-3 border rounded bg-transparent">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <strong class="fs-5">${escapeHtml(alb.album)}</strong>
                                    <button class="btn btn-warning btn-sm add-album-btn"
                                            data-tracks='${escapeHtml(JSON.stringify(alb.tracks))}'>
                                        <i class="bi bi-plus-circle me-1"></i> Add whole album
                                    </button>
                                </div>
                                <ul class="list-group">
                                    ${alb.tracks.map(track => `
                                        <li class="list-group-item d-flex justify-content-between align-items-center">
                                            <div>
                                                <span class="fw-medium">${escapeHtml(track.track)}</span>
                                                <small class="text-muted ms-2">(${track.duration || "?:??"})</small>
                                            </div>
                                            <div>
                                                <button class="btn btn-primary btn-sm preview-btn me-2"
                                                        data-path="${escapeHtml(track.path)}"
                                                        data-title="${escapeHtml(track.track)}">
                                                    <i class="bi bi-play-fill"></i>
                                                </button>
                                                <button class="btn btn-success btn-sm add-btn"
                                                        data-item='${escapeHtml(JSON.stringify(track))}'>
                                                    <i class="bi bi-plus-circle"></i>
                                                </button>
                                            </div>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        `).join('');

                    } else {
                        // === SINGLE ALBUM DETAILS ===
                        const tracks = data.tracks || [];
                        html = `
                            <div class="mb-3">
                                <button class="btn btn-warning btn-sm add-album-btn"
                                        data-tracks='${escapeHtml(JSON.stringify(tracks))}'>
                                    <i class="bi bi-plus-circle me-1"></i> Add whole album
                                </button>
                            </div>
                            <ul class="list-group">
                                ${tracks.map(track => `
                                    <li class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <span class="fw-medium">${escapeHtml(track.artist || data.artist)} - ${escapeHtml(track.track)}</span>
                                            <small class="text-muted ms-2">(${track.duration || "?:??"})</small>
                                        </div>
                                        <div>
                                            <button class="btn btn-primary btn-sm preview-btn me-2"
                                                    data-path="${escapeHtml(track.path)}"
                                                    data-title="${escapeHtml(track.track)}">
                                                <i class="bi bi-play-fill"></i>
                                            </button>
                                            <button class="btn btn-success btn-sm add-btn"
                                                    data-item='${escapeHtml(JSON.stringify(track))}'>
                                                <i class="bi bi-plus-circle"></i>
                                            </button>
                                        </div>
                                    </li>
                                `).join('')}
                            </ul>`;
                    }

                    body.innerHTML = html;

                    // Re-attach buttons after new content is inserted
                    attachAddButtons();
                    attachPreviewButtons();  // Important: re-attach preview handlers
                })
                .catch(err => {
                    body.innerHTML = '<p class="text-danger">Loading failed.</p>';
                    console.error(err);
                });
        });
    });
}

// ---------- Refine search by clicking result headers ----------
function attachRefineLinks() {
    document.querySelectorAll('.accordion-button').forEach(btn => {
        btn.style.cursor = "pointer";
        btn.addEventListener("click", function (e) {
            if (e.target.closest("[data-bs-toggle]")) return; // let accordion work
            const headerText = this.textContent.trim();
            const isArtist = this.classList.contains("bg-success");
            const isAlbum = this.classList.contains("bg-warning");

            if (isArtist) {
                const artist = headerText.replace(/^Artist:\s*/, "").split(" ")[0];
                searchInput.value = "";
                badgesContainer.innerHTML = "";
                createBadge("artist", artist.trim());
            } else if (isAlbum) {
                const album = headerText.replace(/^Album:\s*/, "").split(" — ")[0];
                searchInput.value = "";
                badgesContainer.innerHTML = "";
                createBadge("album", album.trim());
            }
            performSearch();
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

// Preview handling (unchanged, just re-attach)
function attachPreviewButtons() {
    document.querySelectorAll('.preview-btn').forEach(btn => {
        // Remove any old listener to prevent duplicates
        btn.replaceWith(btn.cloneNode(true));
    });

    document.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const {path} = this.dataset;
            const title = this.dataset.title || 'Preview';

            if (!path) return;

            // Use your existing global player logic here
            const player = document.getElementById('global-audio-player');
            const container = document.getElementById('audio-player-container');

            // Stop any currently playing preview
            if (window.currentPreviewBtn && window.currentPreviewBtn !== this) {
                stopPreview();
            }

            player.src = `/play/${path}`;
            player.play().catch(e => console.error("Preview failed:", e));
            container.style.display = 'block';

            document.getElementById('now-playing-title').textContent = title;
            document.getElementById('now-playing-artist').textContent = 'Preview';

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
        rebuildBadgesFromQuery(saved);
        performSearch();
    }

    searchInput.addEventListener("input", () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(performSearch, 300);
    });

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && searchInput.value === "" && badgesContainer.children.length > 0) {
            badgesContainer.lastChild.remove();
            performSearch();
        }
    });

    // Initial popover
    new bootstrap.Popover(document.getElementById("searchHint"));
}