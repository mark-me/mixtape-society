# Changes to MixtapeManager for Multi-Collection Support

This document describes the minimal changes needed to `mixtape_manager.py` to support
multiple collections via the `CollectionManager`.

## Change 1: Update imports

```python
# OLD:
from musiclib import MusicCollection

# NEW:
from musiclib import MusicCollection
# Import CollectionManager will be added by main app, not here
```

## Change 2: Update __init__ signature and attribute

```python
# OLD:
def __init__(
    self,
    path_mixtapes: Path,
    collection: MusicCollection,  # Single collection
    logger: Logger | None = None,
) -> None:
    # ...
    self.collection = collection

# NEW:
def __init__(
    self,
    path_mixtapes: Path,
    collection_manager,  # Now takes CollectionManager (or single MusicCollection for backward compat)
    logger: Logger | None = None,
) -> None:
    """Initializes the MixtapeManager with paths for mixtapes and covers.

    Sets up the directory structure for storing mixtape JSON files and cover images.

    Args:
        path_mixtapes (Path): Path to the directory where mixtapes are stored.
        collection_manager: CollectionManager instance for multi-collection support,
                          or MusicCollection for backward compatibility
        logger (Logger): Optional logger instance for logging actions.
    """
    self._logger: Logger = logger or NullLogger()
    self.path_mixtapes: Path = path_mixtapes
    self.path_cover: Path = path_mixtapes / "covers"
    self.path_mixtapes.mkdir(exist_ok=True)
    self.path_cover.mkdir(exist_ok=True)
    
    # Support both CollectionManager and single MusicCollection for backward compatibility
    self.collection_manager = collection_manager
```

## Change 3: Update _verify_against_collection method

This is the key change - it now looks up the correct collection based on collection_id:

```python
# OLD:
def _verify_against_collection(self, data: dict) -> tuple[dict, bool | None]:
    """Verifies and refreshes mixtape track metadata against the music collection.
    
    # ... docstring ...
    """
    if not (tracks := data["tracks"]):
        return False, None
    has_changes = False
    for track in tracks:
        track_collection = self.collection.get_track(path=Path(track["path"]))  # Always used single collection
        # ... rest of method ...

# NEW:
def _verify_against_collection(self, data: dict) -> tuple[dict, bool | None]:
    """Verifies and refreshes mixtape track metadata against the music collection.

    Now supports multi-collection setups by using the collection_id field in the mixtape.
    Falls back to default collection for legacy mixtapes without collection_id.

    Args:
        data (dict): The mixtape data dictionary containing a "tracks" list to validate.
                    May contain optional "collection_id" field.

    Returns:
        tuple[dict, bool | None]: A tuple of the updated tracks list and a flag indicating 
        whether any changes were made, or (False, None) if there are no tracks to verify.
    """
    if not (tracks := data["tracks"]):
        return False, None
    
    # Get the appropriate collection
    collection = self._get_collection_for_mixtape(data)
    if not collection:
        self._logger.warning("No collection available for mixtape verification")
        return data, None
    
    has_changes = False
    for track in tracks:
        track_collection = collection.get_track(path=Path(track["path"]))
        keys = [
            "filename",
            "artist",
            "album",
            "track",
            "duration",
            "cover",
        ]
        for key in keys:
            if key not in track or track[key] != track_collection.get(key):
                has_changes = True
                track[key] = track_collection.get(key)
    return data, has_changes
```

## Change 4: Add helper method _get_collection_for_mixtape

```python
def _get_collection_for_mixtape(self, data: dict):
    """Get the appropriate MusicCollection for a mixtape.
    
    Handles both multi-collection (CollectionManager) and single-collection setups.
    
    Args:
        data: Mixtape data dictionary (may contain collection_id)
    
    Returns:
        MusicCollection instance, or None if collection not found
    """
    # Check if we have a CollectionManager (multi-collection mode)
    if hasattr(self.collection_manager, 'get'):
        # Multi-collection mode
        collection_id = data.get('collection_id')
        
        if collection_id:
            # Get specific collection
            collection = self.collection_manager.get(collection_id)
            if not collection:
                self._logger.error(f"Collection '{collection_id}' not found")
                return None
            return collection
        else:
            # Legacy mixtape without collection_id - use default
            self._logger.info(
                "Mixtape missing collection_id, using default collection"
            )
            return self.collection_manager.get_default()
    else:
        # Single-collection mode (backward compatibility)
        return self.collection_manager
```

## Change 5: Update docstring for __init__

Add note about multi-collection support to the class docstring:

```python
class MixtapeManager:
    """Manages mixtape files and their associated cover images.

    Provides functionality to create, update, delete, list, and retrieve mixtapes stored on disk.
    
    Supports both single-collection and multi-collection setups:
    - Single collection: Pass a MusicCollection instance
    - Multi-collection: Pass a CollectionManager instance
    
    Mixtapes store a collection_id field to identify which collection they use.
    Legacy mixtapes without collection_id will use the default collection.
    """
```

## Summary of Changes

1. **Renamed attribute**: `self.collection` → `self.collection_manager`
2. **Added helper method**: `_get_collection_for_mixtape()` to resolve the correct collection
3. **Updated `_verify_against_collection()`**: Now uses helper to get collection
4. **Backward compatible**: Still works with single MusicCollection instance

## Testing the Changes

```python
# Test single-collection mode (backward compatible)
collection = MusicCollection(music_root="/music", db_path="/data/db.sqlite")
manager = MixtapeManager(path_mixtapes=Path("/data/mixtapes"), collection_manager=collection)

# Test multi-collection mode
from collection_manager import CollectionManager
collections = CollectionManager(config_path=Path("/data/collections.yml"))
manager = MixtapeManager(path_mixtapes=Path("/data/mixtapes"), collection_manager=collections)
```

## Migration Notes

- Existing code that passes a `MusicCollection` will continue to work
- New code should pass a `CollectionManager` for multi-collection support
- The parameter name change from `collection` to `collection_manager` is intentional
  to signal the API change, but the code is backward compatible
