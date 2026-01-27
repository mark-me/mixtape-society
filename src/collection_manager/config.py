"""
Configuration loading and validation for collection_manager.

Handles:
- Loading collections.yml
- Validating configuration structure
- Creating default configuration
- Configuration data classes
"""

from dataclasses import dataclass
from pathlib import Path
import yaml

from .exceptions import ConfigurationError


@dataclass
class CollectionDefinition:
    """
    Definition of a single music collection.

    Attributes:
        id: Unique identifier for the collection (stable across devices)
        name: Human-readable name
        description: Optional description
        music_root: Path to music files directory
        db_path: Path to SQLite database file
    """

    id: str
    name: str
    description: str
    music_root: Path
    db_path: Path

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if not isinstance(self.music_root, Path):
            self.music_root = Path(self.music_root)
        if not isinstance(self.db_path, Path):
            self.db_path = Path(self.db_path)


@dataclass
class CollectionConfig:
    """
    Complete collection configuration.

    Attributes:
        version: Configuration file version (currently 1)
        default_collection: ID of the default collection
        collections: List of collection definitions
    """

    version: int
    default_collection: str
    collections: list[CollectionDefinition]


def load_config(config_path: Path, logger) -> CollectionConfig:
    """
    Load and parse collections.yml configuration file.

    If the file doesn't exist, creates a default single-collection setup
    for backward compatibility.

    Args:
        config_path: Path to collections.yml
        logger: Logger instance for messages

    Returns:
        CollectionConfig instance

    Raises:
        ConfigurationError: If configuration is invalid
    """
    _ensure_config_exists(config_path, logger)
    data = _read_config_data(config_path)
    _validate_config_or_raise(data)
    collections = _parse_collections(data)
    return _build_collection_config(data, collections)


def _ensure_config_exists(config_path: Path, logger) -> None:
    """Ensure the config file exists, creating a default if necessary."""
    if not config_path.exists():
        logger.info(f"Configuration file not found: {config_path}")
        logger.info("Creating default single-collection configuration")
        create_default_config(config_path, logger)


def _read_config_data(config_path: Path) -> dict:
    """Read and parse the YAML configuration file into a dict."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML syntax in {config_path}", [str(e)])
    except Exception as e:
        raise ConfigurationError(f"Failed to read {config_path}", [str(e)])


def _validate_config_or_raise(data: dict) -> None:
    """Validate configuration data and raise ConfigurationError on failure."""
    is_valid, errors = validate_config_data(data)
    if not is_valid:
        raise ConfigurationError("Invalid configuration", errors)


def _parse_collections(data: dict) -> list[CollectionDefinition]:
    """
    Parse raw collection entries from configuration data into definitions.

    This converts each collection dictionary from the configuration into a
    CollectionDefinition instance with normalized path values.

    Args:
        data: Parsed configuration dictionary containing collection entries

    Returns:
        List of CollectionDefinition objects constructed from the configuration
    """
    collections: list[CollectionDefinition] = []
    collections.extend(
        CollectionDefinition(
            id=coll_dict["id"],
            name=coll_dict.get("name", coll_dict["id"]),
            description=coll_dict.get("description", ""),
            music_root=Path(coll_dict["music_root"]),
            db_path=Path(coll_dict["db_path"]),
        )
        for coll_dict in data.get("collections", [])
    )
    return collections


def _build_collection_config(
    data: dict, collections: list[CollectionDefinition]
) -> CollectionConfig:
    """
    Construct a CollectionConfig object from raw configuration data.

    This wraps the parsed configuration values and collection definitions into
    a single configuration structure used by the rest of the application.

    Args:
        data: Parsed configuration dictionary containing global settings
        collections: List of parsed CollectionDefinition objects

    Returns:
        A CollectionConfig instance built from the provided data.
    """
    return CollectionConfig(
        version=data.get("version", 1),
        default_collection=data.get("default_collection", "main"),
        collections=collections,
    )


def validate_config_data(data: dict) -> tuple[bool, list[str]]:
    """
    Validate configuration data structure.

    Args:
        data: Parsed YAML data

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["Configuration must be a dictionary"]

    _validate_top_level_keys(data, errors)
    collections, collection_ids = _validate_collections_list(data, errors)
    _validate_each_collection(collections, errors, collection_ids)
    _validate_default_collection_reference(data, errors, collection_ids)

    return not errors, errors


def _validate_top_level_keys(data: dict, errors: list[str]) -> None:
    """Validate required top-level keys in the configuration."""
    if "collections" not in data:
        errors.append("Missing required key 'collections'")

    if "default_collection" not in data:
        errors.append("Missing required key 'default_collection'")


def _validate_collections_list(
    data: dict, errors: list[str]
) -> tuple[list[dict], list[str]]:
    """
    Validate the collections list container in the configuration.

    This checks that the collections section exists, is a list, and is not empty
    before individual collection entries are validated.

    Args:
        data: Parsed configuration dictionary containing collections
        errors: List to append validation error messages to

    Returns:
        Tuple of the collections list (or an empty list on failure) and an
        initially empty list of collection IDs to be populated later.
    """
    collections = data.get("collections", [])
    if not isinstance(collections, list):
        errors.append("'collections' must be a list")
        # Return empty to avoid further processing
        return [], []

    if len(collections) == 0:
        errors.append("At least one collection must be defined")

    return collections, []


def _validate_each_collection(
    collections: list[dict], errors: list[str], collection_ids: list[str]
) -> None:
    """
    Validate each collection entry in the configuration.

    This checks that each collection has the required fields, valid values,
    and that collection identifiers are unique.

    Args:
        collections: List of raw collection dictionaries from the configuration
        errors: List to append validation error messages to
        collection_ids: List that will be populated with validated collection IDs
    """
    for i, coll in enumerate(collections):
        prefix = f"Collection {i + 1}"

        if not isinstance(coll, dict):
            errors.append(f"{prefix}: Must be a dictionary")
            continue

        # Check required fields
        if "id" not in coll:
            errors.append(f"{prefix}: Missing required field 'id'")
        else:
            coll_id = coll["id"]
            if not isinstance(coll_id, str) or not coll_id.strip():
                errors.append(f"{prefix}: 'id' must be a non-empty string")
            elif coll_id in collection_ids:
                errors.append(f"{prefix}: Duplicate collection id '{coll_id}'")
            else:
                collection_ids.append(coll_id)

        if "music_root" not in coll:
            errors.append(f"{prefix}: Missing required field 'music_root'")

        if "db_path" not in coll:
            errors.append(f"{prefix}: Missing required field 'db_path'")


def _validate_default_collection_reference(
    data: dict, errors: list[str], collection_ids: list[str]
) -> None:
    """
    Validate that the default collection ID refers to a defined collection.

    This ensures the default_collection entry matches one of the configured
    collection identifiers before the configuration is used.

    Args:
        data: Parsed configuration dictionary containing default_collection
        errors: List to append validation error messages to
        collection_ids: List of known collection IDs from the configuration
    """
    default = data.get("default_collection")
    if default and collection_ids and default not in collection_ids:
        errors.append(
            f"default_collection '{default}' does not match any collection id. "
            f"Available: {', '.join(collection_ids)}"
        )


def validate_config_file(config_path: Path) -> tuple[bool, list[str]]:
    """
    Validate a configuration file without loading it into CollectionManager.

    Useful for pre-flight checks before reloading configuration.

    Args:
        config_path: Path to collections.yml

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    if not config_path.exists():
        return False, [f"Configuration file not found: {config_path}"]

    data_result = _read_config_file_for_validation(config_path)
    if not data_result[0]:
        # data_result is (False, [errors])
        return data_result

    data = data_result[1]
    errors, warnings = _validate_config_structure_and_paths(data)

    all_messages = errors + warnings
    return not errors, all_messages


def _read_config_file_for_validation(
    config_path: Path,
) -> tuple[bool, list[str] | dict]:
    """
    Read and parse the configuration file for validation.

    Returns a tuple where the first element indicates success and the
    second element is either the parsed data or a list of error messages.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return True, data
    except yaml.YAMLError as e:
        return False, [f"Invalid YAML syntax: {e}"]
    except Exception as e:
        return False, [f"Failed to read file: {e}"]


def _validate_config_structure_and_paths(
    data: dict,
) -> tuple[list[str], list[str]]:
    """
    Validate configuration structure and check that important paths exist.

    Returns separate lists of errors and warnings collected during validation.
    """
    errors: list[str] = []

    # Validate structure
    is_valid, validation_errors = validate_config_data(data)
    if not is_valid:
        errors.extend(validation_errors)

    # Check that paths exist (warnings, not errors)
    warnings: list[str] = []
    for coll in data.get("collections", []):
        coll_id = coll.get("id", "unknown")

        music_root = Path(coll.get("music_root", ""))
        if not music_root.exists():
            warnings.append(
                f"Collection '{coll_id}': music_root does not exist: {music_root}"
            )

        db_path = Path(coll.get("db_path", ""))
        db_dir = db_path.parent
        if not db_dir.exists():
            warnings.append(
                f"Collection '{coll_id}': database directory does not exist: {db_dir}"
            )

    return errors, warnings


def create_default_config(config_path: Path, logger=None):
    """
    Create a default single-collection configuration file.

    This provides backward compatibility for existing single-collection setups.
    The default configuration uses the MUSIC_ROOT and DB_PATH from BaseConfig.

    Args:
        config_path: Path where collections.yml should be created
        logger: Optional logger for messages
    """
    # Import here to avoid circular dependency
    try:
        from config.config import BaseConfig

        music_root = str(BaseConfig.MUSIC_ROOT)
        db_path = str(BaseConfig.DB_PATH)
    except ImportError:
        # Fallback if config module not available
        music_root = "/music"
        db_path = "/data/collection.db"
        if logger:
            logger.warning("Could not import BaseConfig, using fallback paths")

    default_config = {
        "version": 1,
        "default_collection": "main",
        "collections": [
            {
                "id": "main",
                "name": "Main Collection",
                "description": "Primary music library",
                "music_root": music_root,
                "db_path": db_path,
            }
        ],
    }

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write configuration
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            default_config,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    if logger:
        logger.info(f"Created default configuration at {config_path}")


def get_collection_by_id(
    config: CollectionConfig, collection_id: str
) -> CollectionDefinition | None:
    """
    Get a collection definition by ID.

    Args:
        config: CollectionConfig instance
        collection_id: Collection ID to find

    Returns:
        CollectionDefinition or None if not found
    """
    return next(
        (coll for coll in config.collections if coll.id == collection_id), None
    )
