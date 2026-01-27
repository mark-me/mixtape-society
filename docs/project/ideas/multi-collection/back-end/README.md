# Multi-Collection Support for Mixtape Society

Complete implementation package for adding multi-collection support to Mixtape Society.

## 📦 What's Included

This package contains everything you need to implement multi-collection support:

### Core Files

1. **`collection_manager.py`** - Main collection management class
   - Manages multiple MusicCollection instances
   - Loads from YAML configuration
   - Provides default collection fallback
   - Fully documented with examples

2. **`migrate_mixtapes.py`** - Migration utility
   - Adds `collection_id` to existing mixtapes
   - Dry-run mode for safety
   - Handles errors gracefully
   - Preserves existing data

3. **`collections.yml.example`** - Configuration template
   - Well-commented examples
   - Device-specific setup instructions
   - Multiple collection examples

4. **`docker-compose-multicollection.yml`** - Docker setup example
   - Multi-volume mount configuration
   - Comprehensive comments
   - Sync instructions

### Documentation

5. **`MIXTAPE_MANAGER_CHANGES.md`** - Code changes guide
   - Detailed before/after examples
   - Helper method implementation
   - Backward compatibility notes

6. **`INTEGRATION_GUIDE.md`** - Complete integration guide
   - Step-by-step instructions
   - API endpoint updates
   - Testing procedures
   - Deployment checklist
   - Troubleshooting section

7. **`config_updated.py`** - Updated config.py
   - Adds COLLECTIONS_CONFIG path
   - Maintains backward compatibility

## 🎯 Quick Start

### 1. Copy Core Files

```bash
# Copy collection manager
cp collection_manager.py src/

# Copy migration script
cp migrate_mixtapes.py scripts/

# Copy example config
cp collections.yml.example collections.yml
```

### 2. Update Existing Code

Apply changes from `MIXTAPE_MANAGER_CHANGES.md` to `src/mixtape_manager/mixtape_manager.py`:

- Change `collection` parameter to `collection_manager`
- Add `_get_collection_for_mixtape()` helper method
- Update `_verify_against_collection()` to use helper

Update `src/config/config.py` using `config_updated.py` as reference.

### 3. Configure Collections

Edit `collections.yml`:

```yaml
version: 1
default_collection: "main"

collections:
  - id: "main"
    name: "Main Collection"
    music_root: "/music"
    db_path: "/data/main.db"
```

### 4. Initialize in App

Update your Flask app initialization:

```python
from collection_manager import CollectionManager

# Initialize collection manager
collection_manager = CollectionManager(
    config_path=config.COLLECTIONS_CONFIG,
    logger=logger,
    use_ui_layer=True
)

# Update mixtape manager
mixtape_manager = MixtapeManager(
    path_mixtapes=config.MIXTAPE_DIR,
    collection_manager=collection_manager,  # Changed!
    logger=logger
)
```

### 5. Migrate Existing Data

```bash
# Dry run first
python scripts/migrate_mixtapes.py --dry-run

# Then actually migrate
python scripts/migrate_mixtapes.py
```

## ✨ Features

### For You (Creator/Maintainer)

- ✅ **Multiple independent collections** - Each with own music and database
- ✅ **Portable across devices** - Same collection ID, different paths
- ✅ **Easy sync** - Just rsync music + database
- ✅ **No code changes** - Add collections via config file
- ✅ **Backward compatible** - Existing single collection works

### For Receivers

- ✅ **No changes needed** - They still just stream
- ✅ **No collection knowledge required** - Everything handled server-side

## 📖 Architecture

```
┌─────────────────────────────────────────┐
│        CollectionManager                │
│  ┌────────────┬────────────┬──────────┐ │
│  │    main    │    jazz    │ classical│ │
│  │ Collection │ Collection │Collection│ │
│  │            │            │          │ │
│  │ /music     │/music/jazz │/music/cl │ │
│  │ main.db    │ jazz.db    │ class.db │ │
│  └────────────┴────────────┴──────────┘ │
└─────────────────────────────────────────┘
                    ▲
                    │
         ┌──────────┴──────────┐
         │                     │
  ┌──────▼───────┐    ┌───────▼────────┐
  │   Mixtape    │    │  Search/Stream │
  │   Manager    │    │   Endpoints    │
  └──────────────┘    └────────────────┘
```

## 🔄 How It Works

### Creating a Mixtape

1. User selects collection in UI (e.g., "jazz")
2. Searches within that collection
3. Adds tracks to mixtape
4. Mixtape saved with `collection_id: "jazz"`

### Playing a Mixtape

1. Receiver requests mixtape
2. Server reads `collection_id` from mixtape
3. `CollectionManager.get("jazz")` returns correct collection
4. Track paths resolved against jazz collection's `music_root`
5. Audio streamed to receiver

### Syncing to Another Device

1. Copy collection files:
   ```bash
   rsync -av /music/jazz/ user@nas:/nas/music/jazz/
   rsync -av /data/jazz.db user@nas:/nas/data/jazz.db
   ```

2. Update `collections.yml` on NAS:
   ```yaml
   - id: "jazz"  # Same ID!
     music_root: "/nas/music/jazz"  # Different path!
     db_path: "/nas/data/jazz.db"
   ```

3. Done! Mixtapes work on both devices

## 🔍 Key Design Decisions

### Why collection_id Instead of Paths?

- ✅ Portable: Same ID across devices
- ✅ Stable: Doesn't change when you reorganize files
- ✅ Simple: Just one string field

### Why YAML Config Instead of Database?

- ✅ Easy to edit by hand
- ✅ Can be version controlled
- ✅ Device-specific (not synced with collection)
- ✅ No schema migrations needed

### Why CollectionManager Instead of Direct Access?

- ✅ Single source of truth
- ✅ Handles fallbacks (default collection)
- ✅ Validates collection existence
- ✅ Clean separation of concerns

## 🧪 Testing

### Test Single Collection (Backward Compat)

```python
from musiclib import MusicCollection
from mixtape_manager import MixtapeManager

collection = MusicCollection(
    music_root=Path("/music"),
    db_path=Path("/data/db.sqlite")
)

manager = MixtapeManager(
    path_mixtapes=Path("/data/mixtapes"),
    collection_manager=collection  # Old style still works!
)
```

### Test Multiple Collections

```python
from collection_manager import CollectionManager

manager = CollectionManager(
    config_path=Path("/data/collections.yml")
)

# List all
for info in manager.list_collections():
    print(f"{info['name']}: {info['stats']['track_count']} tracks")

# Get specific
jazz = manager.get("jazz")
results = jazz.search_highlighting("coltrane")

# Get default
default = manager.get_default()
```

## 📋 Implementation Checklist

- [ ] Read `INTEGRATION_GUIDE.md` completely
- [ ] Backup all production data
- [ ] Copy `collection_manager.py` to `src/`
- [ ] Update `config.py` (add COLLECTIONS_CONFIG)
- [ ] Update `mixtape_manager.py` (see MIXTAPE_MANAGER_CHANGES.md)
- [ ] Update Flask app initialization
- [ ] Add new API endpoints (see INTEGRATION_GUIDE.md)
- [ ] Create `collections.yml` from example
- [ ] Test locally with default collection
- [ ] Run migration script on test data
- [ ] Test with multiple collections locally
- [ ] Update `docker-compose.yml` volume mounts
- [ ] Deploy to staging
- [ ] Run migration in staging
- [ ] Test thoroughly in staging
- [ ] Deploy to production
- [ ] Monitor logs for "Loaded collection" messages

## 🚀 Deployment

### Docker Deployment

1. **Update docker-compose.yml:**
   ```yaml
   volumes:
     - /host/music/main:/music:ro
     - /host/music/jazz:/music/jazz:ro
     - ./collections.yml:/app/collection-data/collections.yml:ro
   ```

2. **Create collections.yml:**
   ```bash
   cp collections.yml.example collections.yml
   nano collections.yml  # Edit paths
   ```

3. **Rebuild and restart:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify:**
   ```bash
   docker compose logs mixtape | grep "Loaded collection"
   curl http://localhost:5000/api/collections
   ```

## 📚 Documentation

- **`INTEGRATION_GUIDE.md`** - Complete step-by-step guide
- **`MIXTAPE_MANAGER_CHANGES.md`** - Code changes detail
- **`collections.yml.example`** - Config file reference

## 🐛 Troubleshooting

### Collection not loading

Check:
1. YAML syntax in `collections.yml`
2. Paths exist and are accessible
3. Docker volume mounts match config paths
4. Container logs: `docker compose logs mixtape`

### Mixtapes not working

Check:
1. Run migration script: `python migrate_mixtapes.py`
2. Verify `collection_id` field exists in JSON
3. Check collection ID matches `collections.yml`
4. Verify default collection is configured

### "No collection available" errors

Check:
1. `default_collection` is set in `collections.yml`
2. Default collection actually exists in collections list
3. `CollectionManager` initialized in Flask app

Full troubleshooting in `INTEGRATION_GUIDE.md`.

## 🤝 Support

Questions? Check the docs:
- `INTEGRATION_GUIDE.md` - Full implementation guide
- `MIXTAPE_MANAGER_CHANGES.md` - Code-level changes
- Inline code comments - All classes documented

## 📄 License

Same as Mixtape Society.

---

## Summary

This package provides:

1. ✅ **Production-ready code** - Fully tested and documented
2. ✅ **Backward compatible** - Existing setups work unchanged
3. ✅ **Well documented** - Comprehensive guides and examples
4. ✅ **Migration tools** - Safe data migration utilities
5. ✅ **Docker support** - Updated compose configuration
6. ✅ **Minimal changes** - Only touch what's necessary

**Result:** Your existing Mixtape Society installation can seamlessly support multiple music collections with device-portable configuration.
