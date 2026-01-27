# Multi-Collection Integration Guide

Complete guide for integrating multi-collection support into Mixtape Society.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Steps](#implementation-steps)
4. [Configuration](#configuration)
5. [Migration](#migration)
6. [Flask API Updates](#flask-api-updates)
7. [Testing](#testing)
8. [Deployment](#deployment)

---

## Overview

### What Changes

- **Single collection** → **Multiple collections**
- Each collection has its own database and music root
- Collections are identified by stable IDs across devices
- Paths are device-specific (defined in `collections.yml`)
- Mixtapes reference collections by ID, not path

### What Stays the Same

- Existing database schema (no changes)
- Existing mixtape JSON format (only adds optional `collection_id` field)
- All existing functionality works with "main" default collection
- Streaming mechanism (receivers don't need collections)

---

## Architecture

### New Components

```
src/
├── collection_manager.py      # NEW: Multi-collection coordinator
├── config/
│   └── config.py              # Updated: Add COLLECTIONS_CONFIG path
├── mixtape_manager/
│   └── mixtape_manager.py     # Updated: Accept CollectionManager
└── app.py                      # Updated: Initialize CollectionManager

data/
├── collections.yml             # NEW: Collection definitions
├── main.db                     # Database for "main" collection
├── jazz.db                     # Database for "jazz" collection (example)
└── mixtapes/
    ├── summer-vibes.json       # Updated: Contains collection_id
    └── covers/
```

### Data Flow

```
User creates mixtape
    ↓
Select collection from UI
    ↓
Mixtape JSON includes collection_id
    ↓
MixtapeManager._verify_against_collection()
    ↓
CollectionManager.get(collection_id)
    ↓
Correct MusicCollection instance
    ↓
Verify tracks against that collection's DB
```

---

## Implementation Steps

### Step 1: Add CollectionManager

Copy `collection_manager.py` to `src/`:

```bash
cp collection_manager.py src/
```

### Step 2: Update config.py

Add to `BaseConfig`:

```python
# Collections configuration
COLLECTIONS_CONFIG = DATA_ROOT / "collections.yml"
```

### Step 3: Update MixtapeManager

Apply the changes described in `MIXTAPE_MANAGER_CHANGES.md`:

1. Change `collection` parameter to `collection_manager`
2. Add `_get_collection_for_mixtape()` helper method
3. Update `_verify_against_collection()` to use the helper

See the detailed diff in `MIXTAPE_MANAGER_CHANGES.md`.

### Step 4: Update Flask app initialization

In `app.py` (or wherever you initialize the Flask app):

```python
# OLD:
from musiclib import MusicCollectionUI
from mixtape_manager import MixtapeManager

collection = MusicCollectionUI(
    music_root=config.MUSIC_ROOT,
    db_path=config.DB_PATH,
    logger=logger
)

mixtape_manager = MixtapeManager(
    path_mixtapes=config.MIXTAPE_DIR,
    collection=collection,
    logger=logger
)

# NEW:
from collection_manager import CollectionManager
from mixtape_manager import MixtapeManager

# Initialize collection manager
collection_manager = CollectionManager(
    config_path=config.COLLECTIONS_CONFIG,
    logger=logger,
    use_ui_layer=True  # Wraps collections in MusicCollectionUI
)

# Initialize mixtape manager with collection manager
mixtape_manager = MixtapeManager(
    path_mixtapes=config.MIXTAPE_DIR,
    collection_manager=collection_manager,  # Changed parameter
    logger=logger
)

# For backward compatibility, you can still access default collection
default_collection = collection_manager.get_default()
```

### Step 5: Add Flask API endpoints

Add new endpoints to expose collections to the frontend:

```python
@app.route('/api/collections', methods=['GET'])
def list_collections():
    """List all available collections with stats."""
    try:
        collections = collection_manager.list_collections()
        return jsonify(collections)
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return jsonify({'error': 'Failed to list collections'}), 500


@app.route('/api/collections/<collection_id>', methods=['GET'])
def get_collection_info(collection_id):
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


@app.route('/api/search', methods=['GET'])
def search():
    """Search within a specific collection or default collection."""
    query = request.args.get('q', '')
    collection_id = request.args.get('collection_id')
    
    # Get collection
    if collection_id:
        collection = collection_manager.get(collection_id)
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
    else:
        collection = collection_manager.get_default()
        if not collection:
            return jsonify({'error': 'No collections available'}), 500
    
    # Perform search
    try:
        results = collection.search_highlighting(query)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500


@app.route('/stream/<path:file_path>')
def stream_file(file_path):
    """Stream audio file from the correct collection.
    
    The collection_id should be provided as a query parameter.
    Falls back to default collection if not specified.
    """
    collection_id = request.args.get('collection_id')
    
    # Get collection
    if collection_id:
        collection = collection_manager.get(collection_id)
        info = collection_manager.get_info(collection_id)
    else:
        collection = collection_manager.get_default()
        default_id = collection_manager._default_id
        info = collection_manager.get_info(default_id) if default_id else None
    
    if not collection or not info:
        return jsonify({'error': 'Collection not found'}), 404
    
    # Construct full path
    full_path = info.music_root / file_path
    
    if not full_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(str(full_path))
```

---

## Configuration

### collections.yml Format

```yaml
version: 1
default_collection: "main"

collections:
  - id: "main"
    name: "Main Collection"
    description: "Primary music library"
    music_root: "/music"
    db_path: "/data/main.db"
  
  - id: "jazz"
    name: "Jazz Archive"
    description: "Complete jazz collection"
    music_root: "/music/jazz"
    db_path: "/data/jazz.db"
```

### Docker Compose Setup

```yaml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    volumes:
      # Music collections
      - /home/mark/Music:/music:ro
      - /home/mark/Music/Jazz:/music/jazz:ro
      
      # Data directory (contains collections.yml and databases)
      - ../collection-data:/app/collection-data
      
      # Mount collections config
      - ./collections.yml:/app/collection-data/collections.yml:ro
    
    environment:
      - MUSIC_ROOT=/music
      - DATA_ROOT=/app/collection-data
      - PASSWORD=yourpassword
```

### Device-Specific Configuration

**Laptop:**
```yaml
version: 1
default_collection: "main"
collections:
  - id: "main"
    music_root: "/home/user/Music"
    db_path: "/home/user/.mixtape/main.db"
```

**NAS:**
```yaml
version: 1
default_collection: "main"
collections:
  - id: "main"
    music_root: "/mnt/storage/music"
    db_path: "/mnt/storage/mixtape/main.db"
```

**Key insight:** Same `id`, different paths per device!

---

## Migration

### Migrate Existing Mixtapes

Run the migration script to add `collection_id` to existing mixtapes:

```bash
# Using defaults from config
python migrate_mixtapes.py

# Specify custom paths
python migrate_mixtapes.py /data/mixtapes main

# Dry run (preview changes)
python migrate_mixtapes.py --dry-run
```

### Migrate Existing Database

No database migration needed! The schema stays the same. Just:

1. Copy your existing `collection.db` to `main.db`
2. Update `collections.yml` to point to `main.db`

```bash
# Backup first
cp collection-data/collection.db collection-data/collection.db.backup

# Rename to main.db
mv collection-data/collection.db collection-data/main.db

# Create collections.yml pointing to main.db
cat > collection-data/collections.yml << EOF
version: 1
default_collection: "main"
collections:
  - id: "main"
    name: "Main Collection"
    music_root: "/music"
    db_path: "/app/collection-data/main.db"
EOF
```

---

## Flask API Updates

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/collections` | GET | List all collections |
| `/api/collections/<id>` | GET | Get collection details |

### Updated Endpoints

| Endpoint | Changes |
|----------|---------|
| `/api/search` | Add optional `collection_id` query param |
| `/stream/<path>` | Add optional `collection_id` query param |
| `/api/mixtapes` | Mixtapes now include `collection_id` field |

### Request Examples

```bash
# List collections
curl http://localhost:5000/api/collections

# Get collection info
curl http://localhost:5000/api/collections/jazz

# Search in specific collection
curl 'http://localhost:5000/api/search?q=coltrane&collection_id=jazz'

# Stream from specific collection
curl 'http://localhost:5000/stream/artist/album/track.mp3?collection_id=jazz'
```

---

## Testing

### Test Single-Collection Mode

```python
# Test backward compatibility
from musiclib import MusicCollection
from mixtape_manager import MixtapeManager

collection = MusicCollection(
    music_root=Path("/music"),
    db_path=Path("/data/db.sqlite")
)

manager = MixtapeManager(
    path_mixtapes=Path("/data/mixtapes"),
    collection_manager=collection  # Single collection works!
)
```

### Test Multi-Collection Mode

```python
# Test new functionality
from collection_manager import CollectionManager
from mixtape_manager import MixtapeManager

collections = CollectionManager(
    config_path=Path("/data/collections.yml")
)

manager = MixtapeManager(
    path_mixtapes=Path("/data/mixtapes"),
    collection_manager=collections
)

# Get default collection
default = collections.get_default()
results = default.search_highlighting("love")

# Get specific collection
jazz = collections.get("jazz")
results = jazz.search_highlighting("coltrane")
```

### Test Mixtape Creation

```python
# Create mixtape with collection_id
mixtape_data = {
    "title": "Jazz Classics",
    "collection_id": "jazz",  # NEW FIELD
    "tracks": [
        {
            "path": "John Coltrane/A Love Supreme/01 Acknowledgement.flac",
            # ... other track fields
        }
    ]
}

slug = manager.save(mixtape_data)
```

---

## Deployment

### Deployment Checklist

- [ ] Copy `collection_manager.py` to `src/`
- [ ] Update `config.py` with `COLLECTIONS_CONFIG`
- [ ] Apply changes to `mixtape_manager.py`
- [ ] Update Flask app initialization
- [ ] Add new API endpoints
- [ ] Create `collections.yml` config file
- [ ] Run mixtape migration script
- [ ] Update `docker-compose.yml` with volume mounts
- [ ] Test collection loading in logs
- [ ] Verify search works across collections
- [ ] Test mixtape creation with collection_id

### Docker Deployment Steps

```bash
# 1. Create collections.yml
cp collections.yml.example collections.yml
nano collections.yml  # Edit paths

# 2. Migrate existing mixtapes
docker exec mixtape-society python migrate_mixtapes.py

# 3. Restart container
docker compose restart mixtape

# 4. Check logs
docker compose logs mixtape | grep "Loaded collection"

# 5. Test API
curl http://localhost:5000/api/collections
```

### Rollback Plan

If something goes wrong:

```bash
# 1. Stop container
docker compose stop

# 2. Restore backup
cp collection-data/collection.db.backup collection-data/collection.db

# 3. Remove collections.yml
rm collection-data/collections.yml

# 4. Restart with old image
docker compose up -d
```

---

## Troubleshooting

### "Collection not found" errors

**Problem:** Mixtape references a collection_id that doesn't exist

**Solution:** 
- Check `collections.yml` has the collection defined
- Check the collection ID matches exactly (case-sensitive)
- Verify collection database and music_root paths exist

### "No default collection" errors

**Problem:** No `default_collection` set or it doesn't exist

**Solution:**
- Set `default_collection: "main"` in `collections.yml`
- Ensure the default collection is actually defined

### Collection not loading

**Problem:** Collection defined but not appearing in logs

**Solution:**
- Check YAML syntax in `collections.yml`
- Verify paths are absolute and exist in container
- Check container logs for error messages
- Ensure volume mounts are correct in docker-compose.yml

### Legacy mixtapes not working

**Problem:** Old mixtapes fail to load

**Solution:**
- Run migration script: `python migrate_mixtapes.py`
- Check migration output for errors
- Verify default collection is configured

---

## Summary

### Key Files Changed

1. **NEW:** `src/collection_manager.py` - Multi-collection coordinator
2. **NEW:** `collections.yml` - Collection definitions
3. **NEW:** `migrate_mixtapes.py` - Migration utility
4. **UPDATED:** `src/config/config.py` - Add COLLECTIONS_CONFIG
5. **UPDATED:** `src/mixtape_manager/mixtape_manager.py` - Accept CollectionManager
6. **UPDATED:** `app.py` - Initialize CollectionManager
7. **UPDATED:** Flask API routes - Add collection endpoints

### Key Benefits

✅ **Backward compatible** - existing single-collection setups work
✅ **Portable** - same collection ID, different paths per device
✅ **Independent** - each collection has own database
✅ **Flexible** - add/remove collections without code changes
✅ **Clean separation** - collections isolated from each other

### Next Steps

1. Review all changes
2. Test locally first
3. Backup production data
4. Deploy to staging
5. Migrate production
6. Monitor logs
7. Update documentation
