# Handling Mixtape Updates in PWA

## 🔄 The Challenge

When a mixtape changes (tracks added/removed/reordered), the cached version becomes stale. Users need to see the latest version without manual cache clearing.

## 📊 Current Implementation Status

### ❌ What's NOT Handled Yet:
- Automatic detection of mixtape changes
- Cache invalidation when mixtape is updated
- Notification to users about updates
- Smart sync of only changed tracks

### ✅ What IS Handled:
- Service worker uses **network-first** strategy for mixtape pages
- Service worker auto-updates when code changes
- Manual cache clearing available

## 🎯 Recommended Solution: Cache Versioning

Here's a comprehensive solution with multiple approaches:

---

## Solution 1: ETag-Based Cache Invalidation (Recommended)

### How It Works:
1. Server sends ETag (hash) of mixtape content
2. Service worker stores ETag with cached response
3. On next request, SW sends If-None-Match header
4. Server returns 304 if unchanged, or new content if changed
5. SW updates cache only when content actually changed

### Implementation:

#### Backend (Update play.py):

```python
# In play.py
import hashlib
import json

@play.route("/share/<slug>")
def public_play(slug: str) -> Response:
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    
    # Generate ETag from mixtape content
    # Include updated_at timestamp and track list in hash
    etag_data = {
        'updated_at': mixtape.get('updated_at'),
        'tracks': [t.get('path') for t in mixtape.get('tracks', [])],
        'liner_notes': mixtape.get('liner_notes', ''),
    }
    etag = hashlib.sha256(
        json.dumps(etag_data, sort_keys=True).encode()
    ).hexdigest()[:16]
    
    # Check if client has current version
    client_etag = request.headers.get('If-None-Match')
    if client_etag and client_etag == etag:
        return Response(status=304)  # Not Modified
    
    response = make_response(
        render_template("play_mixtape.html", mixtape=mixtape, public=True)
    )
    
    # Add cache headers with ETag
    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'public, max-age=300, must-revalidate'
    
    return response
```

#### Service Worker Update:

```javascript
// In service-worker.js, update handleMixtapePage function:

async function handleMixtapePage(request) {
    const cache = await caches.open(CACHE_NAMES.metadata);
    
    // Get cached response with its ETag
    const cachedResponse = await cache.match(request);
    
    try {
        // Always check network with conditional request
        const headers = new Headers(request.headers);
        
        if (cachedResponse) {
            const cachedEtag = cachedResponse.headers.get('ETag');
            if (cachedEtag) {
                headers.set('If-None-Match', cachedEtag);
            }
        }
        
        const networkRequest = new Request(request, { headers });
        const networkResponse = await fetch(networkRequest);
        
        if (networkResponse.status === 304) {
            // Content hasn't changed - use cache
            console.log('[SW] Mixtape unchanged, using cache');
            return cachedResponse;
        }
        
        if (networkResponse.ok) {
            // Content changed - update cache
            console.log('[SW] Mixtape updated, refreshing cache');
            await cache.put(request, networkResponse.clone());
            
            // Notify client about update
            notifyClientsOfUpdate(request.url);
            
            return networkResponse;
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log('[SW] Network failed, using cache');
        
        if (cachedResponse) {
            // Add offline indicator
            return addOfflineHeader(cachedResponse);
        }
        
        return getOfflinePage();
    }
}

// Notify all clients that a mixtape was updated
function notifyClientsOfUpdate(url) {
    self.clients.matchAll().then(clients => {
        clients.forEach(client => {
            client.postMessage({
                type: 'MIXTAPE_UPDATED',
                url: url
            });
        });
    });
}
```

#### Client-Side Notification:

```javascript
// In pwa-manager.js, add message listener:

constructor() {
    // ... existing code ...
    this.setupUpdateListener();
}

setupUpdateListener() {
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'MIXTAPE_UPDATED') {
            this.showUpdateNotification('mixtape');
        }
    });
}

showUpdateNotification(type = 'app') {
    if (type === 'mixtape') {
        const notification = document.createElement('div');
        notification.className = 'update-notification mixtape-update';
        notification.innerHTML = `
            <div class="update-content">
                <i class="bi bi-music-note-beamed me-2"></i>
                <span>This mixtape has been updated</span>
            </div>
            <button class="btn btn-sm btn-light" onclick="window.location.reload()">
                Refresh
            </button>
            <button class="btn btn-sm btn-outline-light ms-2" onclick="this.parentElement.remove()">
                Later
            </button>
        `;
        document.body.appendChild(notification);
        
        // Auto-dismiss after 10 seconds if not clicked
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 10000);
    }
}
```

---

## Solution 2: Version-Based URLs (Alternative)

### How It Works:
1. Add version query parameter to mixtape URLs
2. When mixtape changes, version increments
3. New URL = new cache entry
4. Old cache entry naturally expires

### Implementation:

#### Backend:
```python
# In mixtape_manager.py, add version to mixtape data:

def save(self, mixtape_data: dict) -> str:
    # ... existing code ...
    
    # Increment version on update
    if existing := self._find_by_client_id(client_id):
        existing_version = existing.get('version', 0)
        mixtape_data['version'] = existing_version + 1
    else:
        mixtape_data['version'] = 1
    
    # ... rest of save logic ...
```

#### Share URLs:
```python
# In play.py:
@play.route("/share/<slug>")
def public_play(slug: str) -> Response:
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    
    # Redirect to versioned URL
    version = mixtape.get('version', 1)
    if 'v' not in request.args or int(request.args.get('v', 0)) != version:
        return redirect(f"/play/share/{slug}?v={version}")
    
    return render_template("play_mixtape.html", mixtape=mixtape, public=True)
```

#### Service Worker:
```javascript
// Service worker automatically caches different versions as separate entries
// No changes needed - URLs with different ?v= are treated as different resources
```

---

## Solution 3: Timestamp-Based Validation (Simple)

### How It Works:
1. Include `updated_at` timestamp in API response
2. Service worker stores timestamp with cache
3. On request, SW checks if cached version is "fresh enough"
4. If too old, fetches new version

### Implementation:

#### API Endpoint:
```python
# Add to pwa_routes.py:

@pwa.route('/api/mixtape/<slug>/check-version')
def check_mixtape_version(slug: str):
    """Quick version check without full data"""
    mixtape_manager = current_app.config.get('MIXTAPE_MANAGER')
    mixtape = mixtape_manager.get(slug)
    
    if not mixtape:
        return jsonify({'error': 'Not found'}), 404
    
    return jsonify({
        'slug': slug,
        'updated_at': mixtape.get('updated_at'),
        'version': mixtape.get('version', 1),
        'track_count': len(mixtape.get('tracks', [])),
    })
```

#### Service Worker:
```javascript
async function handleMixtapePage(request) {
    const url = new URL(request.url);
    const slug = url.pathname.split('/share/')[1];
    
    // Check version via API
    try {
        const versionCheck = await fetch(`/api/mixtape/${slug}/check-version`);
        const versionData = await versionCheck.json();
        
        const cache = await caches.open(CACHE_NAMES.metadata);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            // Check if cached version is current
            const cachedMetadata = await getCachedMetadata(slug);
            
            if (cachedMetadata && 
                cachedMetadata.updated_at === versionData.updated_at) {
                console.log('[SW] Cached mixtape is current');
                return cachedResponse;
            }
            
            console.log('[SW] Cached mixtape is outdated, fetching new version');
        }
        
        // Fetch fresh version
        const response = await fetch(request);
        
        if (response.ok) {
            cache.put(request, response.clone());
            storeCachedMetadata(slug, versionData);
        }
        
        return response;
        
    } catch (error) {
        // Network error - use cache if available
        const cachedResponse = await caches.match(request);
        return cachedResponse || getOfflinePage();
    }
}

// Store metadata separately for quick version checks
async function storeCachedMetadata(slug, metadata) {
    const cache = await caches.open(CACHE_NAMES.metadata);
    const metadataUrl = `/api/mixtape/${slug}/metadata`;
    const response = new Response(JSON.stringify(metadata), {
        headers: { 'Content-Type': 'application/json' }
    });
    await cache.put(metadataUrl, response);
}

async function getCachedMetadata(slug) {
    const cache = await caches.open(CACHE_NAMES.metadata);
    const response = await cache.match(`/api/mixtape/${slug}/metadata`);
    return response ? response.json() : null;
}
```

---

## Solution 4: Audio Cache Invalidation

When tracks are added/removed/reordered, the audio cache also needs updating:

### Smart Audio Cache Management:

```javascript
// In service-worker.js

async function handleMixtapeUpdate(slug, oldTracks, newTracks) {
    const audioCache = await caches.open(CACHE_NAMES.audio);
    
    // Get lists of track paths
    const oldPaths = new Set(oldTracks.map(t => t.path));
    const newPaths = new Set(newTracks.map(t => t.path));
    
    // Find removed tracks
    const removedTracks = [...oldPaths].filter(path => !newPaths.has(path));
    
    // Find added tracks
    const addedTracks = [...newPaths].filter(path => !oldPaths.has(path));
    
    // Remove cached audio for deleted tracks
    for (const path of removedTracks) {
        const qualities = ['high', 'medium', 'low'];
        for (const quality of qualities) {
            const cacheKey = `${path}-${quality}`;
            await audioCache.delete(cacheKey);
            console.log('[SW] Removed cached audio:', cacheKey);
        }
    }
    
    // Notify client about changes
    notifyAudioCacheUpdate(slug, addedTracks.length, removedTracks.length);
}

function notifyAudioCacheUpdate(slug, added, removed) {
    self.clients.matchAll().then(clients => {
        clients.forEach(client => {
            client.postMessage({
                type: 'AUDIO_CACHE_UPDATED',
                slug: slug,
                added: added,
                removed: removed
            });
        });
    });
}
```

### Client Notification:

```javascript
// In pwa-manager.js

setupUpdateListener() {
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'AUDIO_CACHE_UPDATED') {
            const { slug, added, removed } = event.data;
            
            let message = 'Audio cache updated: ';
            if (added > 0) message += `${added} new tracks added`;
            if (removed > 0) {
                if (added > 0) message += ', ';
                message += `${removed} tracks removed`;
            }
            
            this.showToast(message, 'info');
            
            // Update download button state
            this.updateDownloadButtonState(slug);
        }
    });
}

async updateDownloadButtonState(slug) {
    // Check if all tracks are still cached
    const mixtapeData = window.__mixtapeData;
    if (!mixtapeData) return;
    
    const cachedCount = await this.getCachedTrackCount(mixtapeData.tracks);
    const totalCount = mixtapeData.tracks.length;
    
    const downloadBtn = document.getElementById('download-mixtape-btn');
    if (downloadBtn) {
        if (cachedCount === totalCount) {
            downloadBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>All Tracks Cached';
            downloadBtn.classList.remove('btn-success');
            downloadBtn.classList.add('btn-outline-success');
        } else if (cachedCount > 0) {
            downloadBtn.innerHTML = `<i class="bi bi-download me-2"></i>Download Remaining (${totalCount - cachedCount})`;
            downloadBtn.classList.add('btn-success');
            downloadBtn.classList.remove('btn-outline-success');
        } else {
            downloadBtn.innerHTML = '<i class="bi bi-download me-2"></i>Download for Offline';
        }
    }
}
```

---

## Solution 5: Background Sync (Future Enhancement)

For more advanced update handling:

```javascript
// Register for background sync when mixtape is viewed
async function registerMixtapeSync(slug) {
    if ('sync' in self.registration) {
        try {
            await self.registration.sync.register(`sync-mixtape-${slug}`);
            console.log('[SW] Registered background sync for:', slug);
        } catch (error) {
            console.log('[SW] Background sync registration failed:', error);
        }
    }
}

// Handle sync event
self.addEventListener('sync', (event) => {
    if (event.tag.startsWith('sync-mixtape-')) {
        const slug = event.tag.replace('sync-mixtape-', '');
        event.waitUntil(syncMixtape(slug));
    }
});

async function syncMixtape(slug) {
    // Fetch latest version
    const response = await fetch(`/play/share/${slug}`);
    
    if (response.ok) {
        const cache = await caches.open(CACHE_NAMES.metadata);
        await cache.put(`/play/share/${slug}`, response);
        
        // Notify clients
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'MIXTAPE_SYNCED',
                slug: slug
            });
        });
    }
}
```

---

## 📋 Comparison of Solutions

| Solution | Complexity | Network Usage | Update Speed | Offline Support |
|----------|-----------|---------------|--------------|-----------------|
| **ETag** | Medium | Low (304 responses) | Fast | ✅ Full |
| **Versioned URLs** | Low | Medium | Instant | ✅ Full |
| **Timestamp** | Low | Low | Medium | ✅ Full |
| **Background Sync** | High | Low | Automatic | ✅ Full |

---

## 🎯 Recommended Approach: Hybrid

Combine multiple solutions for best results:

### Phase 1: Immediate (ETag + Timestamp)
```javascript
// Service Worker Strategy:
1. Check timestamp API endpoint (fast, small)
2. If changed, use ETag for conditional request
3. Return cached version if unchanged
4. Show update notification if changed
```

### Phase 2: Smart Cache (Audio Diffing)
```javascript
// When mixtape updates:
1. Compare old vs new track lists
2. Remove deleted tracks from audio cache
3. Keep unchanged tracks cached
4. Only download new tracks
```

### Phase 3: Background Sync (Future)
```javascript
// Automatic updates when:
1. User opens app
2. Device goes online
3. Periodic sync (if registered)
```

---

## 🎨 User Experience Enhancements

### Update Notification UI:

```html
<!-- Add to play_mixtape.html -->
<div id="mixtape-update-notification" 
     class="alert alert-info alert-dismissible fade show" 
     style="display: none; position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; min-width: 300px;">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Mixtape Updated</strong>
    <div class="mt-2 small">
        <span id="update-details"></span>
    </div>
    <div class="mt-2">
        <button class="btn btn-sm btn-primary me-2" onclick="location.reload()">
            Refresh Now
        </button>
        <button class="btn btn-sm btn-outline-secondary" 
                data-bs-dismiss="alert">
            Later
        </button>
    </div>
</div>

<style>
#mixtape-update-notification {
    animation: slideDown 0.3s ease;
}

@keyframes slideDown {
    from {
        transform: translateX(-50%) translateY(-100px);
        opacity: 0;
    }
    to {
        transform: translateX(-50%) translateY(0);
        opacity: 1;
    }
}
</style>
```

### Update Details:

```javascript
function showMixtapeUpdateDetails(oldMixtape, newMixtape) {
    const oldTracks = oldMixtape.tracks.map(t => t.path);
    const newTracks = newMixtape.tracks.map(t => t.path);
    
    const added = newTracks.filter(t => !oldTracks.includes(t)).length;
    const removed = oldTracks.filter(t => !newTracks.includes(t)).length;
    const reordered = oldTracks.length === newTracks.length && 
                     added === 0 && removed === 0 &&
                     JSON.stringify(oldTracks) !== JSON.stringify(newTracks);
    
    let details = [];
    if (added > 0) details.push(`${added} track(s) added`);
    if (removed > 0) details.push(`${removed} track(s) removed`);
    if (reordered) details.push('Track order changed');
    
    document.getElementById('update-details').textContent = details.join(', ');
    document.getElementById('mixtape-update-notification').style.display = 'block';
}
```

---

## ✅ Testing Update Scenarios

### Test Case 1: Add Track
```python
# 1. User caches mixtape with 10 tracks
# 2. Creator adds track 11
# 3. User reopens mixtape
# Expected: Update notification shown, track 11 available
```

### Test Case 2: Remove Track
```python
# 1. User downloads all tracks
# 2. Creator removes track 5
# 3. User goes offline and opens mixtape
# Expected: Track 5 removed from list, cached audio cleaned up
```

### Test Case 3: Reorder Tracks
```python
# 1. User has mixtape cached
# 2. Creator reorders tracks
# 3. User refreshes page
# Expected: New order shown, no re-download needed
```

### Test Case 4: Update Liner Notes
```python
# 1. User has mixtape cached
# 2. Creator updates liner notes
# 3. User reopens mixtape
# Expected: New liner notes shown
```

---

## 🚀 Implementation Priority

### Week 1: Basic ETag Support
- Add ETag generation to backend
- Update service worker for ETag checks
- Add simple update notification

### Week 2: Smart Audio Cache
- Implement track diffing
- Clean up removed tracks
- Update download button state

### Week 3: Polish
- Add detailed update notifications
- Implement auto-refresh option
- Add update preferences (auto/manual)

---

This comprehensive solution ensures users always see the latest version while maintaining excellent offline support!
