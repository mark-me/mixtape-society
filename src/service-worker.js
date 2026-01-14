// service-worker.js
// Progressive Web App service worker for Mixtape Society
// Provides offline support with smart caching strategies

const CACHE_VERSION = 'v1.0.1';  // Bumped version for fix
const CACHE_NAMES = {
    static: `mixtape-static-${CACHE_VERSION}`,
    audio: `mixtape-audio-${CACHE_VERSION}`,
    images: `mixtape-images-${CACHE_VERSION}`,
    metadata: `mixtape-metadata-${CACHE_VERSION}`,
};

// Files to cache immediately on install (PUBLIC PLAYER ONLY)
const STATIC_ASSETS = [
    '/static/css/base.css',
    '/static/css/play_mixtape.css',
    '/static/css/cassette.css',
    '/static/js/player/index.js',
    '/static/js/player/playerControls.js',
    '/static/js/player/linerNotes.js',
    '/static/js/player/adaptiveTheming.js',
    '/static/js/player/cassettePlayer.js',
    '/static/logo.svg',
    '/static/favicon.svg',
];

// External CDN resources (cache with fallback)
const CDN_ASSETS = [
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
    'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
    'https://cdn.jsdelivr.net/npm/dompurify@3.3.1/dist/purify.min.js',
    'https://cdn.jsdelivr.net/npm/node-vibrant@3.2.1-alpha.1/dist/vibrant.min.js',
];

// ======================
// Installation
// ======================

self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
        Promise.all([
            // Cache static app shell
            caches.open(CACHE_NAMES.static).then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS).catch(err => {
                    console.warn('[SW] Some static assets failed to cache:', err);
                });
            }),
            // Cache CDN resources
            caches.open(CACHE_NAMES.static).then((cache) => {
                console.log('[SW] Caching CDN assets');
                return Promise.allSettled(
                    CDN_ASSETS.map(url => cache.add(url).catch(err => {
                        console.warn(`[SW] Failed to cache ${url}:`, err);
                    }))
                );
            })
        ]).then(() => {
            console.log('[SW] Installation complete');
            // Immediately activate this worker
            return self.skipWaiting();
        })
    );
});

// ======================
// Activation
// ======================

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches
            caches.keys().then((cacheNames) => {
                const validCacheNames = Object.values(CACHE_NAMES);
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (!validCacheNames.includes(cacheName)) {
                            console.log('[SW] Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Take control of all clients immediately
            self.clients.claim()
        ]).then(() => {
            console.log('[SW] Activation complete');
        })
    );
});

// ======================
// Fetch Strategy
// ======================

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // ONLY handle /play/ routes - ignore everything else
    if (!url.pathname.startsWith('/play/')) {
        // Let authenticated routes (/mixtapes, /editor, etc.) always hit network
        // They need fresh data from database
        return;
    }

    // Route to appropriate strategy for /play/ routes only
    // FIXED: Check for specific patterns in correct order
    
    // 1. Mixtape share pages (HTML pages)
    if (url.pathname.startsWith('/play/share/')) {
        event.respondWith(handleMixtapePage(request));
    }
    // 2. Cover images
    else if (url.pathname.startsWith('/play/covers/')) {
        event.respondWith(handleStaticAsset(request));
    }
    // 3. CDN resources (external domains)
    else if (url.hostname !== self.location.hostname) {
        event.respondWith(handleCDNResource(request));
    }
    // 4. Audio files with caching support
    // Audio paths look like: /play/Artist/Album/Track.mp3
    else if (isAudioFile(url.pathname)) {
        event.respondWith(handleAudioRequest(request));
    }
    // 5. Static assets (fallback for anything else)
    else {
        event.respondWith(handleStaticAsset(request));
    }
});

/**
 * Determines if a URL pathname is an audio file
 */
function isAudioFile(pathname) {
    const audioExtensions = ['.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wav', '.opus'];
    const lowerPath = pathname.toLowerCase();
    return audioExtensions.some(ext => lowerPath.endsWith(ext));
}

// ======================
// Strategy Implementations
// ======================

/**
 * Handles audio file requests with proper Range request support
 * 
 * Strategy:
 * 1. For Range requests: Fetch from cache if available, otherwise network
 * 2. For full requests: Cache-first with network fallback
 * 3. Always cache full (200) responses for offline support
 * 
 * Range requests are critical for audio seeking and must be handled correctly.
 */
async function handleAudioRequest(request) {
    const url = new URL(request.url);
    const cacheKey = url.toString(); // Full URL including query params
    const isRangeRequest = request.headers.has('Range');
    
    console.log('[SW] Audio request:', {
        path: url.pathname.split('/').pop(),
        quality: url.searchParams.get('quality'),
        isRange: isRangeRequest
    });
    
    try {
        const cache = await caches.open(CACHE_NAMES.audio);
        
        // Try to get full file from cache (we only cache 200 responses, not 206)
        const cachedResponse = await cache.match(cacheKey);
        
        if (cachedResponse) {
            console.log('[SW] Found cached audio file');
            
            // If this is a range request, we need to slice the cached response
            if (isRangeRequest) {
                return createRangeResponse(cachedResponse, request.headers.get('Range'));
            }
            
            // For non-range requests, return the full cached file
            return cachedResponse;
        }
        
        // Not in cache - fetch from network
        console.log('[SW] Fetching from network...');
        
        // If it's a range request, we need to fetch the full file first to cache it
        // Then serve the range from that full file
        if (isRangeRequest) {
            // Clone the request and remove the Range header to get full file
            // This preserves all auth, cookies, and custom headers
            const headers = new Headers(request.headers);
            headers.delete('Range');
            
            const fullRequest = new Request(request, {
                headers: headers
            });
            
            try {
                const fullResponse = await fetch(fullRequest);
                
                if (fullResponse.ok && fullResponse.status === 200) {
                    // Cache the full file for future use
                    cache.put(cacheKey, fullResponse.clone());
                    console.log('[SW] Cached full audio file');
                    
                    // Create range response from the full file
                    return createRangeResponse(fullResponse, request.headers.get('Range'));
                }
            } catch (fullFetchError) {
                console.log('[SW] Could not fetch full file, falling back to range request');
            }
            
            // If full file fetch failed, fall back to original range request
            return fetch(request);
        }
        
        // For non-range requests, just fetch and cache
        const response = await fetch(request);
        
        if (response.ok && response.status === 200) {
            cache.put(cacheKey, response.clone());
            console.log('[SW] Cached audio file');
        }
        
        return response;
        
    } catch (error) {
        console.error('[SW] Audio request error:', error.message);
        
        // Final fallback: try direct network request
        try {
            return await fetch(request);
        } catch (fallbackError) {
            return new Response('Audio unavailable', {
                status: 503,
                statusText: 'Service Unavailable'
            });
        }
    }
}

/**
 * Creates a 206 Partial Content response from a full cached response
 * This allows serving range requests from cached full files
 */
async function createRangeResponse(fullResponse, rangeHeader) {
    const fullResponseClone = fullResponse.clone();
    const arrayBuffer = await fullResponseClone.arrayBuffer();
    const fullLength = arrayBuffer.byteLength;
    
    // Parse range header: "bytes=0-1023" or "bytes=1024-"
    const rangeMatch = rangeHeader.match(/bytes=(\d+)-(\d*)/);
    if (!rangeMatch) {
        // Invalid range header, return full response
        return fullResponse;
    }
    
    const start = parseInt(rangeMatch[1], 10);
    const end = rangeMatch[2] ? parseInt(rangeMatch[2], 10) : fullLength - 1;
    
    // Validate range
    if (start >= fullLength || end >= fullLength || start > end) {
        return new Response('Range Not Satisfiable', {
            status: 416,
            headers: {
                'Content-Range': `bytes */${fullLength}`
            }
        });
    }
    
    // Slice the requested range
    const rangeBuffer = arrayBuffer.slice(start, end + 1);
    const rangeLength = rangeBuffer.byteLength;
    
    // Create 206 Partial Content response
    const headers = new Headers(fullResponse.headers);
    headers.set('Content-Length', rangeLength.toString());
    headers.set('Content-Range', `bytes ${start}-${end}/${fullLength}`);
    headers.set('Accept-Ranges', 'bytes');
    
    return new Response(rangeBuffer, {
        status: 206,
        statusText: 'Partial Content',
        headers: headers
    });
}

/**
 * Handles static assets (images, CSS, JS)
 * Strategy: Cache first, fallback to network
 */
async function handleStaticAsset(request) {
    try {
        const cache = await caches.open(CACHE_NAMES.images);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Not in cache - fetch from network
        const response = await fetch(request);
        
        if (response.ok) {
            // Cache for next time
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        console.error('[SW] Static asset fetch failed:', error);
        
        // Try to find in any cache as last resort
        const response = await caches.match(request);
        if (response) {
            return response;
        }
        
        // Return placeholder for images
        if (request.destination === 'image') {
            return new Response(
                '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect fill="#ddd" width="200" height="200"/><text x="50%" y="50%" text-anchor="middle" fill="#999">Offline</text></svg>',
                { headers: { 'Content-Type': 'image/svg+xml' } }
            );
        }
        
        return new Response('Offline', { status: 503 });
    }
}

/**
 * Handles mixtape page requests
 * Strategy: Network first with cache fallback
 */
async function handleMixtapePage(request) {
    try {
        // Try network first
        const response = await fetch(request);
        
        if (response.ok) {
            // Cache successful response
            const cache = await caches.open(CACHE_NAMES.metadata);
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);
        
        // Network failed - try cache
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            // Add offline indicator header
            const headers = new Headers(cachedResponse.headers);
            headers.set('X-Offline-Mode', 'true');
            
            return new Response(cachedResponse.body, {
                status: cachedResponse.status,
                statusText: cachedResponse.statusText,
                headers
            });
        }
        
        // No cache available - return offline page
        return getOfflinePage();
    }
}

/**
 * Handles CDN resources
 * Strategy: Cache first
 */
async function handleCDNResource(request) {
    const cache = await caches.open(CACHE_NAMES.static);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        const response = await fetch(request);
        
        if (response.ok) {
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        console.error('[SW] CDN fetch failed:', error);
        return new Response('Offline: Resource not available', { status: 503 });
    }
}

/**
 * Returns a basic offline page
 */
function getOfflinePage() {
    const html = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Offline - Mixtape Society</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-align: center;
                    padding: 20px;
                }
                .offline-container {
                    max-width: 500px;
                }
                h1 { font-size: 3rem; margin: 0 0 1rem; }
                p { font-size: 1.2rem; opacity: 0.9; }
                button {
                    background: white;
                    color: #667eea;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    margin-top: 1rem;
                }
                button:hover { opacity: 0.9; }
            </style>
        </head>
        <body>
            <div class="offline-container">
                <h1>📻</h1>
                <h2>You're Offline</h2>
                <p>This page isn't available offline yet. Check your connection and try again.</p>
                <button onclick="window.location.reload()">Try Again</button>
            </div>
        </body>
        </html>
    `;
    
    return new Response(html, {
        status: 503,
        headers: { 'Content-Type': 'text/html' }
    });
}

// ======================
// Background Sync (for future use)
// ======================

self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-mixtapes') {
        event.waitUntil(syncMixtapes());
    }
});

async function syncMixtapes() {
    // Placeholder for future sync functionality
    console.log('[SW] Background sync triggered');
}

// ======================
// Message Handler (for cache management)
// ======================

self.addEventListener('message', (event) => {
    const { action, data } = event.data;
    
    switch (action) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'CACHE_AUDIO':
            cacheAudioFile(data.url, data.quality)
                .then(() => {
                    event.ports[0].postMessage({ success: true });
                })
                .catch(err => {
                    event.ports[0].postMessage({ success: false, error: err.message });
                });
            break;
            
        case 'CLEAR_CACHE':
            clearCaches(data.type)
                .then(() => {
                    event.ports[0].postMessage({ success: true });
                })
                .catch(err => {
                    event.ports[0].postMessage({ success: false, error: err.message });
                });
            break;
            
        case 'GET_CACHE_SIZE':
            getCacheSize()
                .then(size => {
                    event.ports[0].postMessage({ success: true, size });
                })
                .catch(err => {
                    event.ports[0].postMessage({ success: false, error: err.message });
                });
            break;
    }
});

/**
 * Manually cache an audio file
 */
async function cacheAudioFile(url, quality) {
    const cache = await caches.open(CACHE_NAMES.audio);
    const fullUrl = `${url}?quality=${quality || 'medium'}`;
    const cacheKey = new Request(fullUrl);
    const response = await fetch(fullUrl);
    
    if (response.ok && response.status === 200) {
        await cache.put(cacheKey, response);
        console.log('[SW] Manually cached audio:', fullUrl);
    }
}

/**
 * Clear specific cache type or all caches
 */
async function clearCaches(type) {
    if (type === 'all') {
        const cacheNames = Object.values(CACHE_NAMES);
        await Promise.all(cacheNames.map(name => caches.delete(name)));
        console.log('[SW] Cleared all caches');
    } else if (CACHE_NAMES[type]) {
        await caches.delete(CACHE_NAMES[type]);
        console.log(`[SW] Cleared ${type} cache`);
    }
}

/**
 * Calculate total cache size
 */
async function getCacheSize() {
    if (!navigator.storage || !navigator.storage.estimate) {
        return null;
    }
    
    const estimate = await navigator.storage.estimate();
    return {
        usage: estimate.usage,
        quota: estimate.quota,
        percentage: ((estimate.usage / estimate.quota) * 100).toFixed(2)
    };
}
