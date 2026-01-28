"""
CollectionManager - Main class for managing multiple music collections.

This module provides the CollectionManager class that coordinates multiple
MusicCollection instances from the musiclib package.
"""

from pathlib import Path

from musiclib import MusicCollection, MusicCollectionUI
from common.logging import Logger, NullLogger

from .config import (
    CollectionConfig,
    CollectionDefinition,
    load_config,
    validate_config_file,
    get_collection_by_id
)
from .exceptions import (
    CollectionNotFoundError,
    CollectionInitializationError,
    ConfigurationError
)


class CollectionManager:
    """
    Manages multiple music collections.

    Each collection has:
    - A unique ID (stable across devices)
    - Its own music_root directory
    - Its own SQLite database
    - Independent indexing and search

    The manager provides a unified API for accessing collections and handles
    configuration loading, validation, and collection lifecycle.

    Example:
        # Initialize from config
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

        # Cleanup on shutdown
        manager.close_all()

    Attributes:
        config_path: Path to collections.yml configuration file
        use_ui_layer: Whether to wrap collections in MusicCollectionUI
    """

    def __init__(
        self,
        config_path: Path,
        logger: Logger | None = None,
        use_ui_layer: bool = True
    ):
        """
        Initialize the collection manager.

        Loads configuration from collections.yml and initializes all defined
        collections. If the configuration file doesn't exist, creates a default
        single-collection setup for backward compatibility.

        Args:
            config_path: Path to collections.yml configuration file
            logger: Optional logger instance (defaults to NullLogger)
            use_ui_layer: If True, wrap collections in MusicCollectionUI for UI features;
                         if False, use base MusicCollection class

        Raises:
            ConfigurationError: If configuration is invalid
            CollectionInitializationError: If a collection fails to initialize
        """
        self.config_path = Path(config_path)
        self._logger = logger or NullLogger()
        self.use_ui_layer = use_ui_layer

        # Collection instances keyed by ID
        self._collections: dict[str, MusicCollection | MusicCollectionUI] = {}

        # Configuration
        self._config: CollectionConfig | None = None
        self._default_id: str | None = None

        # Load and initialize
        self._load_and_initialize()

    def _load_and_initialize(self):
        """Load configuration and initialize all collections."""
        self._logger.info(f"Loading collection configuration from {self.config_path}")

        # Load configuration
        self._config = load_config(self.config_path, self._logger)
        self._default_id = self._config.default_collection

        self._logger.info(
            f"Loaded configuration: {len(self._config.collections)} collection(s), "
            f"default='{self._default_id}'"
        )

        # Initialize each collection
        for coll_def in self._config.collections:
            try:
                self._initialize_collection(coll_def)
            except Exception as e:
                self._logger.error(
                    f"Failed to initialize collection '{coll_def.id}': {e}",
                    exc_info=True
                )
                # Continue with other collections rather than failing completely
                # raise CollectionInitializationError(coll_def.id, str(e))

    def _initialize_collection(self, coll_def: CollectionDefinition):
        """
        Initialize a single collection.

        Creates either a MusicCollection or MusicCollectionUI instance
        based on the use_ui_layer setting.

        Args:
            coll_def: Collection definition from configuration

        Raises:
            CollectionInitializationError: If initialization fails
        """
        coll_id = coll_def.id

        try:
            if self.use_ui_layer:
                collection = MusicCollectionUI(
                    music_root=coll_def.music_root,
                    db_path=coll_def.db_path,
                    logger=self._logger
                )
            else:
                collection = MusicCollection(
                    music_root=coll_def.music_root,
                    db_path=coll_def.db_path,
                    logger=self._logger
                )

            self._collections[coll_id] = collection

            self._logger.info(
                f"Initialized collection '{coll_id}' "
                f"(music_root={coll_def.music_root}, db={coll_def.db_path})"
            )

        except Exception as e:
            raise CollectionInitializationError(coll_id, str(e))

    def get(self, collection_id: str) -> MusicCollection | MusicCollectionUI | None:
        """
        Get a collection by ID.

        Args:
            collection_id: Unique identifier for the collection

        Returns:
            MusicCollection or MusicCollectionUI instance, or None if not found

        Example:
            jazz = manager.get("jazz-archive")
            if jazz:
                results = jazz.search_highlighting("coltrane")
        """
        return self._collections.get(collection_id)

    def get_or_raise(self, collection_id: str) -> MusicCollection | MusicCollectionUI:
        """
        Get a collection by ID, raising an exception if not found.

        Args:
            collection_id: Unique identifier for the collection

        Returns:
            MusicCollection or MusicCollectionUI instance

        Raises:
            CollectionNotFoundError: If collection doesn't exist

        Example:
            try:
                jazz = manager.get_or_raise("jazz-archive")
                results = jazz.search_highlighting("coltrane")
            except CollectionNotFoundError:
                print("Jazz collection not available")
        """
        collection = self._collections.get(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)
        return collection

    def get_default(self) -> MusicCollection | MusicCollectionUI | None:
        """
        Get the default collection.

        Returns the collection specified as default in the configuration,
        or the first available collection if no default is set,
        or None if no collections are available.

        Returns:
            MusicCollection or MusicCollectionUI instance, or None

        Example:
            default = manager.get_default()
            if default:
                results = default.search_highlighting("love")
        """
        if self._default_id:
            return self.get(self._default_id)

        # Fallback: return first collection if no default set
        if self._collections:
            return next(iter(self._collections.values()))

        return None

    def list_collections(self) -> list[dict]:
        """
        List all available collections with their metadata and statistics.

        Returns a list of dictionaries containing collection information
        including ID, name, description, paths, and statistics from the
        music database (track count, artist count, etc.).

        Returns:
            List of collection info dictionaries

        Example:
            for info in manager.list_collections():
                print(f"{info['name']}")
                print(f"  Tracks: {info['stats']['track_count']}")
                print(f"  Artists: {info['stats']['artist_count']}")
                print(f"  Default: {info['is_default']}")
        """
        result = []

        for coll_id, collection in self._collections.items():
            # Get collection definition
            coll_def = get_collection_by_id(self._config, coll_id)
            if not coll_def:
                continue

            # Get statistics from collection
            try:
                stats = collection.get_collection_stats()
            except Exception as e:
                self._logger.error(
                    f"Failed to get stats for collection '{coll_id}': {e}"
                )
                stats = {
                    'track_count': 0,
                    'artist_count': 0,
                    'album_count': 0,
                    'error': str(e)
                }

            result.append({
                'id': coll_def.id,
                'name': coll_def.name,
                'description': coll_def.description,
                'music_root': str(coll_def.music_root),
                'db_path': str(coll_def.db_path),
                'is_default': (coll_id == self._default_id),
                'stats': stats
            })

        return result

    def get_info(self, collection_id: str) -> dict | None:
        """
        Get metadata about a collection without accessing the database.

        This is faster than list_collections() as it doesn't query the
        database for statistics. Useful for quick lookups.

        Args:
            collection_id: Unique identifier for the collection

        Returns:
            Collection info dictionary or None if not found

        Example:
            info = manager.get_info("jazz-archive")
            if info:
                print(f"Music at: {info['music_root']}")
        """
        coll_def = get_collection_by_id(self._config, collection_id)
        if not coll_def:
            return None

        return {
            'id': coll_def.id,
            'name': coll_def.name,
            'description': coll_def.description,
            'music_root': str(coll_def.music_root),
            'db_path': str(coll_def.db_path),
            'is_default': (collection_id == self._default_id)
        }

    def has_collection(self, collection_id: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection_id: Unique identifier for the collection

        Returns:
            True if collection exists, False otherwise

        Example:
            if manager.has_collection("jazz-archive"):
                jazz = manager.get("jazz-archive")
        """
        return collection_id in self._collections

    def get_collection_ids(self) -> list[str]:
        """
        Get list of all collection IDs.

        Returns:
            List of collection ID strings

        Example:
            ids = manager.get_collection_ids()
            print(f"Available collections: {', '.join(ids)}")
        """
        return list(self._collections.keys())

    def close_all(self):
        """
        Close all collections (stop monitoring, close DB connections).

        This should be called when shutting down the application to ensure
        all resources are properly released. After calling this, the
        CollectionManager instance should not be used.

        Example:
            try:
                # Use collections...
                pass
            finally:
                manager.close_all()
        """
        self._logger.info("Closing all collections")

        for coll_id, collection in self._collections.items():
            try:
                collection.close()
                self._logger.info(f"Closed collection '{coll_id}'")
            except Exception as e:
                self._logger.error(
                    f"Error closing collection '{coll_id}': {e}",
                    exc_info=True
                )

    def reload_config(self):
        """
        Reload the configuration file and reinitialize collections.

        WARNING: This closes all existing collections and recreates them.
        Any references to old collection objects will become invalid.

        This is useful for adding/removing collections without restarting
        the application, but should be used carefully as it will interrupt
        any ongoing operations.

        Raises:
            ConfigurationError: If the new configuration is invalid
            CollectionInitializationError: If collections fail to initialize

        Example:
            # User edits collections.yml
            try:
                manager.reload_config()
                print("Configuration reloaded successfully")
            except ConfigurationError as e:
                print(f"Invalid configuration: {e}")
        """
        self._logger.info("Reloading collection configuration")

        # Validate new configuration before closing existing collections
        is_valid, errors = validate_config_file(self.config_path)
        if not is_valid:
            raise ConfigurationError("Invalid configuration", errors)

        # Close existing collections
        self.close_all()

        # Clear state
        self._collections.clear()
        self._config = None
        self._default_id = None

        # Reload
        self._load_and_initialize()

        self._logger.info("Collection configuration reloaded successfully")

    def __repr__(self) -> str:
        """String representation of CollectionManager."""
        num_collections = len(self._collections)
        default = self._default_id or "none"
        return (
            f"CollectionManager(collections={num_collections}, "
            f"default='{default}', config={self.config_path})"
        )
