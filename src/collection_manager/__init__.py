"""
Multi-collection management for Mixtape Society.

This package provides the CollectionManager class that coordinates multiple
MusicCollection instances from the musiclib package. Each collection has its
own database and music root directory.

Key Features:
- Manages multiple independent music collections
- Loads configuration from YAML file
- Provides unified API for accessing collections
- Supports default collection fallback
- Backward compatible with single-collection setups

Usage:
    from collection_manager import CollectionManager
    
    # Initialize from config file
    manager = CollectionManager(
        config_path=Path("collections.yml"),
        logger=logger,
        use_ui_layer=True
    )
    
    # Get specific collection
    jazz = manager.get("jazz-archive")
    results = jazz.search_highlighting("coltrane")
    
    # Get default collection
    default = manager.get_default()
    
    # List all collections
    for info in manager.list_collections():
        print(f"{info['name']}: {info['stats']['track_count']} tracks")
"""

from .manager import CollectionManager
from .exceptions import CollectionNotFoundError, ConfigurationError

__version__ = "1.0.0"

__all__ = [
    "CollectionManager",
    "CollectionNotFoundError",
    "ConfigurationError",
]
