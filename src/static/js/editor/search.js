// static/js/editor/search.js
import { addToPlaylist } from "./playlist.js";
import { getSelectedCollectionId } from "./collectionManager.js";

const searchInput = document.getElementById("searchInput");
const resultsDiv = document.getElementById("results");
let timeoutId;

const STORAGE_KEY = "mixtape_editor_search_query";

/**
 * DOM Element Creation Helpers
 * These functions create DOM elements safely without string concatenation
 */

/**
 * Creates an element with optional classes, attributes, and text content
 */
function createElement(tag, options = {}) {
    const element = document.createElement(tag);

    if (options.className) {
        element.className = options.className;
    }

    if (options.textContent) {
        element.textContent = options.textContent;
    }

    if (options.innerHTML) {
        // Only allow innerHTML for static, trusted content
        element.innerHTML = options.innerHTML;
    }

    if (options.attributes) {
        Object.entries(options.attributes).forEach(([key, value]) => {
            element.setAttribute(key, value);
        });
    }

    if (options.children) {
        options.children.forEach(child => {
            if (child) element.appendChild(child);
        });
    }

    if (options.onclick) {
        element.onclick = options.onclick;
    }

    return element;
}

/**
 * Creates an icon element
 */
function createIcon(iconClass) {
    return createElement('i', { className: iconClass });
}

/**
 * Creates a button with icon
 */
function createButton(options = {}) {
    const button = createElement('button', {
        className: options.className || 'btn',
        attributes: options.attributes || {},
        onclick: options.onclick
    });

    if (options.icon) {
        button.appendChild(createIcon(options.icon));
    }

    if (options.textContent) {
        if (options.icon) {
            button.appendChild(document.createTextNode(' ' + options.textContent));
        } else {
            button.textContent = options.textContent;
        }
    }

    return button;
}

function getCurrentQuery() {
    return searchInput.value.trim();
}

function attachAccordionLoader({
    collapse,
    body,
    load,
    emptyMessage = null
}) {
    if (!collapse || !body) return;

    // Prevent duplicate listeners
    if (collapse.dataset.loaderAttached === 'true') return;
    collapse.dataset.loaderAttached = 'true';

    body.dataset.loaded = 'false';
    body.dataset.loading = 'false';

    collapse.addEventListener('show.bs.collapse', async () => {
        if (body.dataset.loaded === 'true' || body.dataset.loading === 'true') {
            return;
        }

        body.dataset.loading = 'true';
        body.innerHTML = '<p class="text-muted">Loading…</p>';

        try {
            const result = await load();

            if (!result || (Array.isArray(result) && result.length === 0)) {
                body.textContent = '';
                if (emptyMessage) {
                    const p = createElement('p', {
                        className: 'text-muted',
                        textContent: emptyMessage
                    });
                    body.appendChild(p);
                }
                body.dataset.loaded = 'true';
                return;
            }

            body.dataset.loaded = 'true';
        } catch (err) {
            console.error('Accordion load failed:', err);
            body.innerHTML = '<p class="text-danger">Failed to load data</p>';
        } finally {
            body.dataset.loading = 'false';
        }
    });
}


/**
 * Performs a search query against the server and renders results
 */
function performSearch() {
    const query = getCurrentQuery();
    localStorage.setItem(STORAGE_KEY, query);

    if (query.length < 2) {
        resultsDiv.innerHTML = '<p class="text-muted text-center my-5">Type at least 2 characters to start searching…</p>';
        return;
    }

    // Get collection ID if in multi-collection mode
    const collectionId = getSelectedCollectionId();

    // Build URL with collection parameter
    const url = new URL('/editor/search', window.location.origin);
    url.searchParams.set('q', query);
    if (collectionId) {
        url.searchParams.set('collection_id', collectionId);
    }

    document.getElementById("loading").classList.remove("visually-hidden");
    fetch(url)
        .then(async response => {
            // Check if the response is actually JSON
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error(`Server returned ${response.status}: ${await response.text()}`);
            }

            if (!response.ok) {
                throw new Error(`Search failed: ${response.status} ${response.statusText}`);
            }

            return response.json();
        })
        .then(renderResults)
        .catch(error => {
            console.error("Search error:", error);
            resultsDiv.textContent = '';

            const errorDiv = createElement('div', {
                className: 'alert alert-danger m-3',
                attributes: { role: 'alert' },
                children: [
                    createIcon('bi bi-exclamation-triangle-fill me-2'),
                    createElement('strong', { textContent: 'Search failed:' }),
                    document.createTextNode(' ' + error.message),
                    createElement('br'),
                    createElement('small', {
                        textContent: 'Try a different search term or report an issue if this persists.'
                    })
                ]
            });

            resultsDiv.appendChild(errorDiv);
        })
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
 * Creates an artist accordion element
 */
function createArtistAccordion(entry) {
    const safeArtist = safeId(entry.raw_artist || entry.artist);

    const accordion = createElement('div', {
        className: 'accordion mb-3',
        attributes: { id: `accordion-artist-${safeArtist}` }
    });

    const accordionItem = createElement('div', { className: 'accordion-item' });

    const header = createElement('h2', { className: 'accordion-header' });

    const artistNameSpan = createElement('span', {
        className: 'flex-grow-1'
    });
    artistNameSpan.innerHTML = entry.artist;  // May contain <mark> tags from search

    const button = createElement('button', {
        className: 'accordion-button collapsed bg-artist',
        attributes: {
            'type': 'button',
            'data-bs-toggle': 'collapse',
            'data-bs-target': `#collapse-artist-${safeArtist}`,
            'data-raw-artist': entry.raw_artist || entry.artist
        },
        children: [
            createIcon('bi bi-person-fill me-2'),
            artistNameSpan,
            createElement('span', {
                className: 'ms-auto small',
                children: [
                    createIcon('bi bi-disc-fill me-1'),
                    document.createTextNode(String(entry.num_albums || 0))
                ]
            })
        ]
    });

    header.appendChild(button);

    const collapse = createElement('div', {
        className: 'accordion-collapse collapse',
        attributes: {
            'id': `collapse-artist-${safeArtist}`,
            'data-artist': entry.raw_artist || entry.artist
        }
    });

    const body = createElement('div', {
        className: 'accordion-body',
        attributes: { 'data-loading': 'true' },
        innerHTML: '<p class="text-muted">Loading…</p>'
    });

    collapse.appendChild(body);
    accordionItem.appendChild(header);
    accordionItem.appendChild(collapse);
    accordion.appendChild(accordionItem);

    return accordion;
}

/**
 * Creates an album accordion element
 */
function createAlbumAccordion(entry) {
    const safeReleaseDir = safeId(entry.release_dir);

    const accordion = createElement('div', {
        className: 'accordion mb-3',
        attributes: { id: `accordion-album-${safeReleaseDir}` }
    });

    const accordionItem = createElement('div', { className: 'accordion-item' });

    const header = createElement('h2', { className: 'accordion-header' });

    const buttonChildren = [];

    // Add cover thumbnail if available
    if (entry.cover) {
        const thumbDiv = createElement('div', {
            className: 'album-thumb me-2'
        });
        const img = createElement('img', {
            className: 'rounded',
            attributes: {
                'src': '/' + entry.cover,
                'alt': 'Album Cover'
            }
        });
        thumbDiv.appendChild(img);
        buttonChildren.push(thumbDiv);
    }

    // Add album title and artist
    // These may contain highlighting markup from search results
    const albumTitleDiv = createElement('div', {
        className: 'album-title text-truncate'
    });
    albumTitleDiv.innerHTML = entry.album;  // May contain <mark> tags

    const artistDiv = createElement('div', {
        className: 'album-artist text-truncate small text-muted'
    });
    artistDiv.innerHTML = entry.artist;  // May contain <mark> tags

    const textDiv = createElement('div', {
        className: 'flex-grow-1 min-w-0',
        children: [albumTitleDiv, artistDiv]
    });
    buttonChildren.push(textDiv);

    // Add track count
    buttonChildren.push(
        createElement('span', {
            className: 'ms-auto small',
            children: [
                createIcon('bi bi-music-note-beamed me-1'),
                document.createTextNode(String(entry.num_tracks || 0))
            ]
        })
    );

    const button = createElement('button', {
        className: 'accordion-button collapsed bg-album',
        attributes: {
            'type': 'button',
            'data-bs-toggle': 'collapse',
            'data-bs-target': `#collapse-album-${safeReleaseDir}`,
            'data-raw-album': entry.raw_album || entry.album,
            'data-raw-artist': entry.raw_artist || entry.artist
        },
        children: buttonChildren
    });

    header.appendChild(button);

    const collapse = createElement('div', {
        className: 'accordion-collapse collapse',
        attributes: {
            'id': `collapse-album-${safeReleaseDir}`,
            'data-release_dir': entry.release_dir,
            'data-cover': entry.cover || ''
        }
    });

    const body = createElement('div', {
        className: 'accordion-body',
        attributes: { 'data-loading': 'true' },
        innerHTML: '<p class="text-muted">Loading…</p>'
    });

    collapse.appendChild(body);
    accordionItem.appendChild(header);
    accordionItem.appendChild(collapse);
    accordion.appendChild(accordionItem);

    return accordion;
}

/**
 * Creates a track list item element
 */
function createTrackListItem(entry) {
    const track = entry.tracks[0];

    const li = createElement('li', {
        className: 'list-group-item d-flex justify-content-between align-items-center mb-2 border rounded'
    });

    const leftDiv = createElement('div', {
        className: 'd-flex align-items-center flex-grow-1 gap-3 min-w-0'
    });

    // Add cover if available
    if (track.cover) {
        const img = createElement('img', {
            className: 'rounded',
            attributes: {
                'src': '/' + track.cover,
                'alt': 'Track Cover',
                'style': 'width: 50px; height: 50px; object-fit: cover; flex-shrink: 0;'
            }
        });
        leftDiv.appendChild(img);
    }

    const infoDiv = createElement('div', {
        className: 'flex-grow-1 min-w-0'
    });

    const titleDiv = createElement('div', {
        className: 'd-flex align-items-center gap-2 mb-1',
        children: [
            createIcon('bi bi-music-note-beamed text-track flex-shrink-0')
        ]
    });

    const trackTitle = createElement('strong', {
        className: 'text-truncate'
    });

    // Handle highlighted tracks
    // Note: highlighted content comes from the server's search highlighting function
    // It contains safe <mark> tags for highlighting search terms
    // This is the ONLY place we use innerHTML for user-related data, and it's safe
    // because the highlighting is server-controlled, not user input
    if (entry.highlighted_tracks && entry.highlighted_tracks[0] && entry.highlighted_tracks[0].highlighted) {
        // Server returns HTML like: "Track <mark>Name</mark> Here"
        trackTitle.innerHTML = entry.highlighted_tracks[0].highlighted;
    } else {
        // No highlighting - use safe textContent
        trackTitle.textContent = track.track;
    }

    titleDiv.appendChild(trackTitle);
    infoDiv.appendChild(titleDiv);

    // Artist and album may also contain highlighting from search
    // Use innerHTML to preserve <mark> tags
    const artistSmall = createElement('small', {
        className: 'text-muted d-block text-truncate'
    });
    artistSmall.innerHTML = entry.artist;  // May contain <mark> tags

    const albumSmall = createElement('small', {
        className: 'text-muted d-block text-truncate'
    });
    albumSmall.innerHTML = entry.album;  // May contain <mark> tags

    infoDiv.appendChild(artistSmall);
    infoDiv.appendChild(albumSmall);

    leftDiv.appendChild(infoDiv);
    li.appendChild(leftDiv);

    const rightDiv = createElement('div', {
        className: 'd-flex align-items-center gap-2 flex-shrink-0 ms-2',
        children: [
            createElement('span', {
                className: 'text-muted',
                attributes: { 'style': 'min-width: 45px; text-align: right;' },
                textContent: formatDuration(track.duration || "?:??")
            }),
            createButton({
                className: 'btn btn-track btn-sm preview-btn',
                icon: 'bi bi-play-fill',
                attributes: {
                    'data-path': track.path,
                    'data-title': track.track,
                    'data-artist': entry.artist,
                    'data-album': entry.album,
                    'data-cover': track.cover || ''
                }
            }),
            createButton({
                className: 'btn btn-success btn-sm add-btn',
                icon: 'bi bi-plus-circle',
                attributes: {
                    'data-item': JSON.stringify(track)
                }
            })
        ]
    });

    li.appendChild(rightDiv);

    return li;
}

/**
 * Renders search results grouped by type (artists, albums, tracks)
 */
function renderResults(data) {
    resultsDiv.textContent = '';

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

    // Render artists section
    if (grouped.artists.length > 0) {
        const heading = createElement('h5', {
            className: 'mt-4 mb-2 text-muted',
            textContent: 'Artists'
        });
        resultsDiv.appendChild(heading);

        grouped.artists.forEach(entry => {
            resultsDiv.appendChild(createArtistAccordion(entry));
        });
    }

    // Render albums section
    if (grouped.albums.length > 0) {
        const heading = createElement('h5', {
            className: 'mt-4 mb-2 text-muted',
            textContent: 'Albums'
        });
        resultsDiv.appendChild(heading);

        grouped.albums.forEach(entry => {
            resultsDiv.appendChild(createAlbumAccordion(entry));
        });
    }

    // Render tracks section
    if (grouped.tracks.length > 0) {
        const heading = createElement('h5', {
            className: 'mt-4 mb-2 text-muted',
            textContent: 'Tracks'
        });
        resultsDiv.appendChild(heading);

        const trackList = createElement('ul', { className: 'list-group' });
        grouped.tracks.forEach(entry => {
            trackList.appendChild(createTrackListItem(entry));
        });
        resultsDiv.appendChild(trackList);
    }

    attachAddButtons();
    attachPreviewButtons();

    // Attach artist accordion loaders
    attachArtistAccordionLoaders();

    // Attach standalone album accordion loaders
    attachAlbumAccordionLoaders();
}

/**
 * Attaches loaders for artist accordions
 */
function attachArtistAccordionLoaders() {
    document
        .querySelectorAll('.accordion-collapse[data-artist]')
        .forEach(collapse => {
            const body = collapse.querySelector('.accordion-body');
            const artist = collapse.dataset.artist;

            attachAccordionLoader({
                collapse,
                body,
                emptyMessage: 'No albums found.',
                load: async () => {
                    // Get collection ID
                    const collectionId = getSelectedCollectionId();

                    // Build URL with collection parameter
                    const url = new URL('/editor/artist_details', window.location.origin);
                    url.searchParams.set('artist', artist);
                    if (collectionId) {
                        url.searchParams.set('collection_id', collectionId);
                    }

                    const res = await fetch(url);
                    const details = await res.json();

                    if (!details.albums || details.albums.length === 0) {
                        return [];
                    }

                    // Create accordion container
                    const accordionContainer = createElement('div', {
                        className: 'accordion accordion-flush'
                    });

                    details.albums.forEach((album, index) => {
                        const albumId = safeId(album.album + '-' + index);

                        const item = createElement('div', { className: 'accordion-item' });

                        const header = createElement('h2', { className: 'accordion-header' });

                        const buttonChildren = [];

                        // Cover thumbnail
                        if (album.cover) {
                            const thumbDiv = createElement('div', {
                                className: 'album-thumb me-2'
                            });
                            thumbDiv.appendChild(createElement('img', {
                                className: 'rounded',
                                attributes: { 'src': '/' + album.cover }
                            }));
                            buttonChildren.push(thumbDiv);
                        }

                        // Album title
                        const textDiv = createElement('div', {
                            className: 'flex-grow-1 min-w-0'
                        });

                        textDiv.appendChild(createElement('strong', {
                            className: 'd-block text-truncate',
                            textContent: album.album
                        }));

                        if (album.is_compilation) {
                            textDiv.appendChild(createElement('div', {
                                className: 'album-artist small text-muted',
                                textContent: 'Various Artists'
                            }));
                        }

                        buttonChildren.push(textDiv);

                        // Track count
                        buttonChildren.push(createElement('span', {
                            className: 'ms-auto small',
                            children: [
                                createIcon('bi bi-music-note-beamed me-1'),
                                document.createTextNode(String(album.tracks.length))
                            ]
                        }));

                        const button = createElement('button', {
                            className: 'accordion-button collapsed bg-album',
                            attributes: {
                                'data-bs-toggle': 'collapse',
                                'data-bs-target': `#collapse-album-${albumId}`
                            },
                            children: buttonChildren
                        });

                        header.appendChild(button);

                        const collapseDiv = createElement('div', {
                            className: 'accordion-collapse collapse',
                            attributes: { 'id': `collapse-album-${albumId}` }
                        });

                        const bodyDiv = createElement('div', { className: 'accordion-body' });

                        // Album cover (large)
                        if (album.cover) {
                            bodyDiv.appendChild(createElement('img', {
                                className: 'img-fluid rounded mb-3',
                                attributes: { 'src': '/' + album.cover }
                            }));
                        }

                        // Add all button
                        bodyDiv.appendChild(createButton({
                            className: 'btn btn-success btn-sm mb-3 add-album-btn',
                            icon: 'bi bi-plus-circle me-2',
                            textContent: 'Add whole album',
                            attributes: {
                                'data-tracks': JSON.stringify(album.tracks)
                            }
                        }));

                        // Track list
                        const trackList = createElement('ul', { className: 'list-group' });

                        album.tracks.forEach(track => {
                            const trackLi = createElement('li', {
                                className: 'list-group-item d-flex justify-content-between'
                            });

                            trackLi.appendChild(createElement('span', {
                                className: 'text-truncate',
                                textContent: track.track
                            }));

                            const buttonGroup = createElement('div', {
                                className: 'd-flex gap-2',
                                children: [
                                    createButton({
                                        className: 'btn btn-track btn-sm preview-btn',
                                        icon: 'bi bi-play-fill',
                                        attributes: {
                                            'data-path': track.path,
                                            'data-title': track.track,
                                            'data-artist': track.artist,
                                            'data-album': track.album,
                                            'data-cover': album.cover || ''
                                        }
                                    }),
                                    createButton({
                                        className: 'btn btn-success btn-sm add-btn',
                                        icon: 'bi bi-plus-circle',
                                        attributes: {
                                            'data-item': JSON.stringify(track)
                                        }
                                    })
                                ]
                            });

                            trackLi.appendChild(buttonGroup);
                            trackList.appendChild(trackLi);
                        });

                        bodyDiv.appendChild(trackList);
                        collapseDiv.appendChild(bodyDiv);
                        item.appendChild(header);
                        item.appendChild(collapseDiv);
                        accordionContainer.appendChild(item);
                    });

                    body.textContent = '';
                    body.appendChild(accordionContainer);
                    attachAddButtons();
                    attachPreviewButtons();

                    return details.albums;
                }
            });
        });
}

/**
 * Attaches loaders for standalone album accordions
 */
function attachAlbumAccordionLoaders() {
    document
        .querySelectorAll('.accordion-collapse[data-release_dir]')
        .forEach(collapse => {
            const body = collapse.querySelector('.accordion-body');
            const releaseDir = collapse.dataset.release_dir;
            const coverPath = collapse.dataset.cover;

            attachAccordionLoader({
                collapse,
                body,
                load: async () => {
                    // Get collection ID
                    const collectionId = getSelectedCollectionId();

                    // Build URL with collection parameter
                    const url = new URL('/editor/album_details', window.location.origin);
                    url.searchParams.set('release_dir', releaseDir);
                    if (collectionId) {
                        url.searchParams.set('collection_id', collectionId);
                    }

                    const res = await fetch(url);
                    const details = await res.json();

                    body.textContent = '';

                    // Album cover
                    if (coverPath) {
                        const coverDiv = createElement('div', {
                            className: 'mb-3 text-center'
                        });
                        coverDiv.appendChild(createElement('img', {
                            className: 'img-thumbnail',
                            attributes: {
                                'src': '/' + coverPath,
                                'style': 'max-width: 200px;'
                            }
                        }));
                        body.appendChild(coverDiv);
                    }

                    // Header with track count and add all button
                    const headerDiv = createElement('div', {
                        className: 'd-flex justify-content-between mb-3'
                    });

                    headerDiv.appendChild(createElement('h6', {
                        textContent: `${details.num_tracks} tracks`
                    }));

                    headerDiv.appendChild(createButton({
                        className: 'btn btn-success btn-sm add-album-btn',
                        icon: 'bi bi-plus-circle',
                        textContent: ' Add All',
                        attributes: {
                            'data-tracks': JSON.stringify(details.tracks)
                        }
                    }));

                    body.appendChild(headerDiv);

                    // Track list
                    const trackList = createElement('ul', { className: 'list-group' });

                    const isVariousArtists = details.artist === 'Various Artists';

                    details.tracks.forEach((track, i) => {
                        const trackLi = createElement('li', {
                            className: 'list-group-item d-flex justify-content-between'
                        });

                        const trackSpan = createElement('span');
                        trackSpan.textContent = `${i + 1}. ${track.track}`;

                        // For Various Artists albums, show the individual track artist
                        if (isVariousArtists && track.artist) {
                            trackSpan.appendChild(document.createTextNode(' '));
                            const artistSpan = createElement('span', {
                                className: 'text-muted',
                                textContent: `– ${track.artist}`
                            });
                            trackSpan.appendChild(artistSpan);
                        }

                        trackLi.appendChild(trackSpan);

                        const buttonGroup = createElement('div', {
                            className: 'd-flex gap-2',
                            children: [
                                createElement('span', {
                                    className: 'text-muted',
                                    textContent: formatDuration(track.duration)
                                }),
                                createButton({
                                    className: 'btn btn-track btn-sm preview-btn',
                                    icon: 'bi bi-play-fill',
                                    attributes: {
                                        'data-path': track.path,
                                        'data-title': track.track,
                                        'data-artist': track.artist || details.artist,
                                        'data-album': details.album,
                                        'data-cover': coverPath || ''
                                    }
                                }),
                                createButton({
                                    className: 'btn btn-success btn-sm add-btn',
                                    icon: 'bi bi-plus-circle',
                                    attributes: {
                                        'data-item': JSON.stringify(track)
                                    }
                                })
                            ]
                        });

                        trackLi.appendChild(buttonGroup);
                        trackList.appendChild(trackLi);
                    });

                    body.appendChild(trackList);
                    attachAddButtons();
                    attachPreviewButtons();

                    return details;
                }
            });
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
    const clearBtn = document.getElementById('clearSearch');

    // Restore persisted query
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        searchInput.value = saved.trim();
        if (clearBtn && saved.trim()) {
            clearBtn.style.display = 'block';
        }
        performSearch();
    }

    // Handle input changes
    searchInput.addEventListener("input", () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(performSearch, 300);

        // Show/hide clear button
        if (clearBtn) {
            clearBtn.style.display = searchInput.value.trim() ? 'block' : 'none';
        }
    });

    // Handle clear button click
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.style.display = 'none';
            localStorage.removeItem(STORAGE_KEY);
            resultsDiv.innerHTML = '<p class="text-muted text-center my-5">Type at least 2 characters to start searching…</p>';
        });
    }

    // Initialize search hint tooltip (not popover)
    const searchHintBtn = document.getElementById("searchHint");
    if (searchHintBtn) {
        new bootstrap.Tooltip(searchHintBtn);
    }

    // Set up audio player event listeners to keep preview button in sync
    setupAudioPlayerSync();
}
