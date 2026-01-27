"""
Custom exceptions for the collection_manager package.
"""


class CollectionManagerError(Exception):
    """Base exception for all collection_manager errors."""
    pass


class CollectionNotFoundError(CollectionManagerError):
    """Raised when a requested collection ID does not exist."""
    
    def __init__(self, collection_id: str):
        self.collection_id = collection_id
        super().__init__(f"Collection '{collection_id}' not found")


class ConfigurationError(CollectionManagerError):
    """Raised when the configuration file is invalid or cannot be loaded."""
    
    def __init__(self, message: str, errors: list[str] | None = None):
        self.errors = errors or []
        full_message = message
        if self.errors:
            full_message += f": {', '.join(self.errors)}"
        super().__init__(full_message)


class CollectionInitializationError(CollectionManagerError):
    """Raised when a collection fails to initialize."""
    
    def __init__(self, collection_id: str, reason: str):
        self.collection_id = collection_id
        self.reason = reason
        super().__init__(f"Failed to initialize collection '{collection_id}': {reason}")
