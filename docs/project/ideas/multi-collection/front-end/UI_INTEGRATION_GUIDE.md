# UI Integration Guide: Multi-Collection Support

Complete guide for integrating multi-collection functionality into the Mixtape Society user interface.

## Table of Contents

1. [Overview](#overview)
2. [UI/UX Design Principles](#uiux-design-principles)
3. [Browser View Changes](#browser-view-changes)
4. [Editor View Changes](#editor-view-changes)
5. [Backend API Changes](#backend-api-changes)
6. [Frontend Implementation](#frontend-implementation)
7. [User Flows](#user-flows)

---

## Overview

### Current Architecture

**Browser View** (`/mixtapes`):
- Lists all mixtapes
- Shows title, cover, track count, dates
- Search by title or deep search in tracks
- Sort by various fields
- No collection awareness

**Editor View** (`/editor`):
- Search music collection
- Build mixtape from search results
- Add metadata (title, cover, notes)
- Save mixtape
- No collection selection

### Target Architecture

**Browser View** (updated):
- Show collection badge on each mixtape
- Filter by collection
- Group by collection (optional)
- Collection info in mixtape details

**Editor View** (updated):
- Collection selector before/during search
- Collection indicator in search results
- Collection locked once tracks added
- Collection stored in mixtape metadata

---

## UI/UX Design Principles

### 1. **Progressive Disclosure**
Don't overwhelm users with collections if they only have one:
- Hide collection UI if only one collection exists
- Show collection selector only when relevant
- Use subtle badges instead of prominent labels

### 2. **Minimal Disruption**
- Single-collection setups should look/feel unchanged
- Multi-collection features should feel natural, not bolted-on
- Preserve existing workflows

### 3. **Clear Visual Hierarchy**
- Collection info should be visible but not dominant
- Use consistent color coding or badges
- Make collection-switching obvious

### 4. **Error Prevention**
- Warn before mixing collections (if needed)
- Validate collection availability before saving
- Clear error messages about missing collections

---

## Browser View Changes

### 1. Collection Badge on Mixtape Cards

**Current:**
```html
<div class="mixtape-item">
    <div class="mixtape-header">
        <h5>Summer Vibes</h5>
        <span class="badge">12 tracks</span>
    </div>
</div>
```

**Updated:**
```html
<div class="mixtape-item">
    <div class="mixtape-header">
        <h5>Summer Vibes</h5>
        <div class="badges">
            <!-- NEW: Collection badge (only shown if multiple collections) -->
            <span class="badge bg-primary" data-bs-toggle="tooltip" 
                  title="From Jazz Archive collection">
                <i class="bi bi-collection"></i> Jazz Archive
            </span>
            <span class="badge bg-secondary">12 tracks</span>
        </div>
    </div>
</div>
```

**CSS:**
```css
.mixtape-item .badges {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.badge.bg-primary {
    background-color: #0d6efd !important;
}

/* Different colors for different collections (optional) */
.badge.collection-main { background-color: #0d6efd; }
.badge.collection-jazz { background-color: #6f42c1; }
.badge.collection-classical { background-color: #d63384; }
```

### 2. Collection Filter Bar

**Add above search bar** (only if multiple collections exist):

```html
<!-- Collection Filter (shown only if multiple collections) -->
{% if collections|length > 1 %}
<div class="card mb-3 shadow-sm">
    <div class="card-body p-2">
        <div class="d-flex align-items-center gap-2">
            <span class="text-muted small">
                <i class="bi bi-collection"></i> Collection:
            </span>
            <div class="btn-group btn-group-sm" role="group">
                <input type="radio" class="btn-check" name="collectionFilter" 
                       id="filter-all" value="" autocomplete="off" checked>
                <label class="btn btn-outline-primary" for="filter-all">
                    All ({{ mixtapes|length }})
                </label>
                
                {% for collection in collections %}
                <input type="radio" class="btn-check" name="collectionFilter" 
                       id="filter-{{ collection.id }}" 
                       value="{{ collection.id }}" 
                       autocomplete="off">
                <label class="btn btn-outline-primary" 
                       for="filter-{{ collection.id }}">
                    {{ collection.name }} ({{ collection.count }})
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endif %}
```

### 3. Mixtape Details Modal

**Add collection info to existing details display:**

```html
<!-- In mixtape details modal/tooltip -->
<div class="mixtape-details">
    <dl class="row">
        <dt class="col-sm-4">Title:</dt>
        <dd class="col-sm-8">{{ mixtape.title }}</dd>
        
        <!-- NEW: Show collection if multiple exist -->
        {% if collections|length > 1 %}
        <dt class="col-sm-4">Collection:</dt>
        <dd class="col-sm-8">
            <span class="badge bg-primary">
                {{ mixtape.collection_name }}
            </span>
        </dd>
        {% endif %}
        
        <dt class="col-sm-4">Tracks:</dt>
        <dd class="col-sm-8">{{ mixtape.tracks|length }}</dd>
        
        <dt class="col-sm-4">Created:</dt>
        <dd class="col-sm-8">{{ mixtape.created_at|format_date }}</dd>
    </dl>
</div>
```

---

## Editor View Changes

### 1. Collection Selector (Top of Editor)

**Add above search bar**, hidden if only one collection:

```html
<!-- Collection Selector -->
{% if collections|length > 1 %}
<div class="card mb-3 shadow-sm" id="collectionSelector">
    <div class="card-body p-3">
        <label for="collectionSelect" class="form-label mb-2">
            <i class="bi bi-collection"></i> <strong>Select Collection</strong>
        </label>
        <select id="collectionSelect" class="form-select" required>
            <option value="" disabled selected>Choose a music collection...</option>
            {% for collection in collections %}
            <option value="{{ collection.id }}" 
                    data-name="{{ collection.name }}"
                    data-track-count="{{ collection.stats.track_count }}"
                    data-artist-count="{{ collection.stats.artist_count }}">
                {{ collection.name }} 
                ({{ collection.stats.track_count }} tracks, 
                 {{ collection.stats.artist_count }} artists)
            </option>
            {% endfor %}
        </select>
        
        <!-- Collection Info Panel (shown after selection) -->
        <div id="selectedCollectionInfo" class="alert alert-info mt-3" style="display: none;">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h6 class="alert-heading mb-1">
                        <i class="bi bi-info-circle"></i> Using Collection: 
                        <span id="selectedCollectionName"></span>
                    </h6>
                    <small id="selectedCollectionStats" class="text-muted"></small>
                </div>
                <button type="button" class="btn btn-sm btn-outline-primary" 
                        id="changeCollection" style="display: none;">
                    Change
                </button>
            </div>
        </div>
    </div>
</div>
{% endif %}
```

### 2. Updated Search Bar

**Disable search until collection selected** (if multiple collections):

```html
<!-- Search Input -->
<div class="card mb-3 shadow-sm">
    <div class="card-body p-3">
        <div class="input-group">
            <span class="input-group-text">
                <i class="bi bi-search"></i>
            </span>
            <input type="text" 
                   id="searchInput" 
                   class="form-control" 
                   placeholder="{% if collections|length > 1 %}Select a collection first...{% else %}Search your music...{% endif %}"
                   {% if collections|length > 1 %}disabled{% endif %}
                   autocomplete="off">
        </div>
        
        <!-- Collection locked indicator (shown after tracks added) -->
        <div id="collectionLockNotice" class="alert alert-warning mt-2 mb-0" style="display: none;">
            <i class="bi bi-lock"></i> 
            <small>Collection locked to <strong id="lockedCollectionName"></strong> 
                   (tracks already added from this collection)
            </small>
        </div>
    </div>
</div>
```

### 3. Search Results with Collection Context

**Add collection indicator to search results**:

```javascript
// In search.js - when rendering results
function renderSearchResult(result) {
    const resultDiv = createElement('div', {
        className: 'search-result-item',
        children: [
            // Existing content...
            
            // NEW: Collection indicator (if multiple collections)
            hasMultipleCollections ? createElement('span', {
                className: 'badge bg-light text-dark',
                innerHTML: `<i class="bi bi-collection"></i> ${currentCollectionName}`
            }) : null
        ]
    });
    
    return resultDiv;
}
```

---

## Backend API Changes

### 1. New Endpoints

```python
# List collections (for UI dropdowns)
@app.route('/api/collections', methods=['GET'])
@require_auth
def list_collections():
    """Get all available collections with stats."""
    collections = collection_manager.list_collections()
    return jsonify(collections)


# Get collection details
@app.route('/api/collections/<collection_id>', methods=['GET'])
@require_auth
def get_collection_details(collection_id):
    """Get detailed info about a specific collection."""
    info = collection_manager.get_info(collection_id)
    if not info:
        return jsonify({'error': 'Collection not found'}), 404
    
    collection = collection_manager.get(collection_id)
    stats = collection.get_collection_stats() if collection else {}
    
    return jsonify({
        'id': info.id,
        'name': info.name,
        'description': info.description,
        'stats': stats
    })
```

### 2. Updated Endpoints

```python
# Update search to accept collection_id
@editor.route("/search")
@require_auth
def search():
    """Search within a specific collection."""
    query = request.args.get("q", "").strip()
    collection_id = request.args.get("collection_id")  # NEW
    
    if len(query) < 2:
        return jsonify([])
    
    # Get appropriate collection
    if collection_id:
        collection = collection_manager.get(collection_id)
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
    else:
        collection = collection_manager.get_default()
    
    results = collection.search_highlighting(query, limit=50)
    return jsonify(results)


# Update browse to include collection info
@browser.route("/")
@require_auth
def browse():
    """Browse mixtapes with optional collection filtering."""
    collection_filter = request.args.get('collection')  # NEW
    
    mixtapes = mixtape_manager.list_all()
    
    # Filter by collection if specified
    if collection_filter:
        mixtapes = [m for m in mixtapes 
                   if m.get('collection_id') == collection_filter]
    
    # Enrich mixtapes with collection names
    collections_info = collection_manager.list_collections()
    collection_names = {c['id']: c['name'] for c in collections_info}
    
    for mixtape in mixtapes:
        mixtape['collection_name'] = collection_names.get(
            mixtape.get('collection_id'), 
            'Unknown'
        )
    
    return render_template(
        "browse_mixtapes.html",
        mixtapes=mixtapes,
        collections=collections_info,  # NEW
        has_multiple_collections=len(collections_info) > 1  # NEW
    )
```

---

## Frontend Implementation

### 1. Browser JavaScript Updates

Create `static/js/browser/collections.js`:

```javascript
// Collection filtering
export function initCollectionFilter() {
    const filterButtons = document.querySelectorAll('[name="collectionFilter"]');
    
    if (filterButtons.length === 0) {
        // Single collection, no filtering needed
        return;
    }
    
    filterButtons.forEach(button => {
        button.addEventListener('change', (e) => {
            const collectionId = e.target.value;
            const url = new URL(window.location);
            
            if (collectionId) {
                url.searchParams.set('collection', collectionId);
            } else {
                url.searchParams.delete('collection');
            }
            
            // Preserve other params (search, sort, etc.)
            window.location.href = url.toString();
        });
    });
}

// Collection badge coloring
export function colorizeCollectionBadges() {
    const badges = document.querySelectorAll('.badge[data-collection-id]');
    const colors = {
        'main': '#0d6efd',
        'jazz': '#6f42c1',
        'classical': '#d63384',
        'default': '#6c757d'
    };
    
    badges.forEach(badge => {
        const collectionId = badge.dataset.collectionId;
        badge.style.backgroundColor = colors[collectionId] || colors.default;
    });
}
```

Update `static/js/browser/index.js`:

```javascript
import { initCollectionFilter, colorizeCollectionBadges } from './collections.js';

document.addEventListener('DOMContentLoaded', () => {
    // Existing initialization...
    
    // NEW: Initialize collection features
    initCollectionFilter();
    colorizeCollectionBadges();
});
```

### 2. Editor JavaScript Updates

Create `static/js/editor/collectionSelector.js`:

```javascript
// Collection selection management
let selectedCollectionId = null;
let collectionLocked = false;

export function initCollectionSelector() {
    const collectionSelect = document.getElementById('collectionSelect');
    const searchInput = document.getElementById('searchInput');
    const selectedInfo = document.getElementById('selectedCollectionInfo');
    
    // Single collection - auto-select and hide selector
    if (!collectionSelect) {
        // Get default collection from hidden input or data attribute
        selectedCollectionId = document.body.dataset.defaultCollection;
        return;
    }
    
    // Multiple collections - require selection
    collectionSelect.addEventListener('change', (e) => {
        selectedCollectionId = e.target.value;
        const option = e.target.selectedOptions[0];
        
        // Show collection info
        document.getElementById('selectedCollectionName').textContent = 
            option.dataset.name;
        document.getElementById('selectedCollectionStats').textContent = 
            `${option.dataset.trackCount} tracks, ${option.dataset.artistCount} artists`;
        
        selectedInfo.style.display = 'block';
        
        // Enable search
        searchInput.disabled = false;
        searchInput.placeholder = 'Search your music...';
        searchInput.focus();
    });
}

export function getSelectedCollectionId() {
    return selectedCollectionId;
}

export function lockCollection() {
    collectionLocked = true;
    
    const collectionSelect = document.getElementById('collectionSelect');
    if (collectionSelect) {
        collectionSelect.disabled = true;
    }
    
    const changeBtn = document.getElementById('changeCollection');
    if (changeBtn) {
        changeBtn.style.display = 'none';
    }
    
    // Show lock notice
    const lockNotice = document.getElementById('collectionLockNotice');
    if (lockNotice) {
        const collectionName = document.getElementById('selectedCollectionName').textContent;
        document.getElementById('lockedCollectionName').textContent = collectionName;
        lockNotice.style.display = 'block';
    }
}

export function isCollectionLocked() {
    return collectionLocked;
}
```

Update `static/js/editor/search.js`:

```javascript
import { 
    getSelectedCollectionId, 
    lockCollection, 
    isCollectionLocked 
} from './collectionSelector.js';

// Update search function to include collection_id
async function performSearch(query) {
    if (!query || query.length < 2) {
        return;
    }
    
    const collectionId = getSelectedCollectionId();
    
    // Build URL with collection parameter
    const url = new URL('/editor/search', window.location.origin);
    url.searchParams.set('q', query);
    if (collectionId) {
        url.searchParams.set('collection_id', collectionId);
    }
    
    try {
        const response = await fetch(url);
        const results = await response.json();
        displayResults(results);
    } catch (error) {
        console.error('Search error:', error);
    }
}
```

Update `static/js/editor/playlist.js`:

```javascript
import { lockCollection, getSelectedCollectionId } from './collectionSelector.js';

// Lock collection when first track is added
export function addToPlaylist(track) {
    const currentPlaylist = getPlaylist();
    
    // Lock collection on first track
    if (currentPlaylist.length === 0) {
        lockCollection();
    }
    
    currentPlaylist.push(track);
    savePlaylist(currentPlaylist);
    updatePlaylistUI();
}

// Include collection_id when saving mixtape
export function saveMixtape(mixtapeData) {
    const collectionId = getSelectedCollectionId();
    
    const dataToSave = {
        ...mixtapeData,
        collection_id: collectionId  // NEW
    };
    
    // Rest of save logic...
}
```

---

## User Flows

### Flow 1: Creating Mixtape (Single Collection)

1. User clicks "New Mixtape"
2. Editor loads with no collection selector visible
3. Search bar is enabled immediately
4. User searches and adds tracks as normal
5. No collection UI shown anywhere
6. Mixtape saved with `collection_id: "main"` automatically

**User sees:** Exactly the same experience as before

---

### Flow 2: Creating Mixtape (Multiple Collections)

1. User clicks "New Mixtape"
2. Editor loads with collection selector shown
3. Search bar is **disabled** with placeholder "Select a collection first..."
4. User selects "Jazz Archive" from dropdown
5. Collection info panel appears showing stats
6. Search bar **enables** with placeholder "Search your music..."
7. User searches (only Jazz collection searched)
8. Search results show "Jazz Archive" badge
9. User adds first track → Collection **locked** (can't change)
10. Lock notice appears: "Collection locked to Jazz Archive"
11. User continues adding tracks from Jazz collection
12. User saves → Mixtape has `collection_id: "jazz"`

**User sees:** Clear collection selection, locked after first track

---

### Flow 3: Browsing Mixtapes (Multiple Collections)

1. User visits `/mixtapes`
2. Collection filter bar shown at top
3. All mixtapes shown by default
4. Each mixtape card shows collection badge
5. User clicks "Jazz Archive" filter button
6. Page reloads showing only Jazz mixtapes
7. URL updates: `/mixtapes?collection=jazz`
8. Filter state persists through search/sort

**User sees:** Clear filtering by collection, badges on cards

---

### Flow 4: Editing Existing Mixtape

1. User clicks "Edit" on a mixtape
2. Editor loads with mixtape data
3. Collection is **pre-selected** based on mixtape's `collection_id`
4. Collection is **immediately locked** (can't change)
5. Lock notice shows: "Collection locked to [name]"
6. Search only searches that collection
7. User can add/remove tracks from same collection
8. Save preserves original `collection_id`

**User sees:** Can't accidentally mix collections when editing

---

## Summary

### Key UI Principles

1. **Hide complexity when unnecessary** - Single collection = no UI changes
2. **Progressive disclosure** - Multi-collection features appear only when needed
3. **Lock early** - Prevent mixing collections by locking after first track
4. **Visual feedback** - Badges, indicators, lock notices keep user informed
5. **Preserve workflow** - Existing users see minimal changes

### Implementation Priority

**Phase 1: Backend** (from previous implementation)
- ✅ CollectionManager
- ✅ Updated MixtapeManager
- ✅ Migration scripts
- ✅ New API endpoints

**Phase 2: Minimal UI** (this guide - recommended first)
- Collection badges on mixtape cards (browser)
- Collection selector in editor
- Collection locking after first track
- Updated search with collection_id parameter

**Phase 3: Enhanced UI** (optional later)
- Collection filtering in browser
- Collection color coding
- Collection statistics dashboard
- Bulk operations by collection

### Testing Checklist

- [ ] Single collection: No UI changes visible
- [ ] Multiple collections: Selector appears
- [ ] Can't search without selecting collection
- [ ] Collection locks after adding first track
- [ ] Can't change collection when editing mixtape
- [ ] Badges appear on mixtape cards
- [ ] Filtering by collection works
- [ ] Search respects selected collection
- [ ] Save includes collection_id
- [ ] Migration adds collection_id to old mixtapes

This guide provides a complete, production-ready approach to integrating multi-collection support into your UI while maintaining the excellent user experience you've already built!
