import json
import re
from base64 import b64decode
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from common.logging import Logger, NullLogger
from musiclib import MusicCollection


class MixtapeManager:
    """Manages mixtape files and their associated cover images.

    Provides functionality to create, update, delete, list, and retrieve mixtapes stored on disk.
    """

    def __init__(
        self,
        path_mixtapes: Path,
        collection: MusicCollection,
        logger: Logger | None = None,
    ) -> None:
        """Initializes the MixtapeManager with paths for mixtapes and covers.

        Sets up the directory structure for storing mixtape JSON files and cover images.

        Args:
            path_mixtapes: Path to the directory where mixtapes are stored.
            collection: Access to the collection's metadata
            logger: Optional logger instance for logging actions.
        """
        self._logger: Logger = logger or NullLogger()
        self.path_mixtapes: Path = path_mixtapes
        self.path_cover: Path = path_mixtapes / "covers"
        self.path_mixtapes.mkdir(exist_ok=True)
        self.path_cover.mkdir(exist_ok=True)
        self.collection = collection

    def _sanitize_title(self, title: str) -> str:
        """Convert title to a URL-safe slug."""
        # Convert to lowercase
        slug = title.lower()

        # Replace spaces and underscores with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)

        # Remove non-alphanumeric characters (except hyphens)
        slug = re.sub(r'[^a-z0-9-]', '', slug)

        # Remove duplicate hyphens
        slug = re.sub(r'-+', '-', slug)

        # Strip leading/trailing hyphens
        slug = slug.strip('-')

        return slug or "untitled"

    def _generate_unique_slug(
        self, base_slug: str, current_slug: Optional[str] = None
    ) -> str:
        """Generates a unique slug for a mixtape based on the provided base slug.

        Ensures the slug does not conflict with existing mixtape files, allowing reuse of the current slug if updating.

        Args:
            base_slug: The base string to use for the slug.
            current_slug: The current slug, if updating an existing mixtape.

        Returns:
            str: A unique slug string.
        """
        if not base_slug:
            base_slug = "untitled"

        slug = base_slug
        counter = 1
        while True:
            json_path = self.path_mixtapes / f"{slug}.json"
            if not json_path.exists() or (current_slug and slug == current_slug):
                return slug
            slug = f"{base_slug}-{counter}"
            counter += 1

    def save(self, mixtape_data: dict) -> str:
        """Creates a new mixtape or updates an existing one based on client identity.

        Reuses an existing mixtape when a matching client_id is found, otherwise generates a fresh mixtape entry.

        Args:
            mixtape_data: Dictionary containing mixtape information, including optional client_id, title, and tracks.

        Returns:
            str: The slug of the created or updated mixtape.
        """
        client_id = mixtape_data.get("client_id")
        now = datetime.now().isoformat()

        if existing := self._find_by_client_id(client_id):
            slug = existing["slug"]
            self._logger.info(
                f"Found existing mixtape for client_id {client_id}, updating slug {slug}"
            )
            return self.update(slug, mixtape_data)

        # New creation
        title = mixtape_data.get("title", "Untitled Mixtape")
        base_slug = self._sanitize_title(title)
        slug = self._generate_unique_slug(base_slug)

        # Preserve the client_id in the saved data
        if client_id:
            mixtape_data["client_id"] = client_id

        # Set both timestamps on first save
        mixtape_data["created_at"] = now
        mixtape_data["updated_at"] = now

        # Ensure gift flow fields have defaults if not provided
        mixtape_data.setdefault("creator_name", "")
        mixtape_data.setdefault("gift_flow_enabled", False)
        mixtape_data.setdefault("unwrap_style", "playful")
        mixtape_data.setdefault("show_tracklist_after_completion", True)

        return self._save_with_slug(mixtape_data=mixtape_data, title=title, slug=slug)

    def _find_by_client_id(self, client_id: str | None) -> dict | None:
        """Finds the first mixtape associated with a given client identifier.

        Scans stored mixtapes to locate a matching client_id and returns its data in a convenient format.

        Args:
            client_id: The identifier used to associate a client with a mixtape.

        Returns:
            dict | None: The mixtape data including its slug if found, otherwise None.
        """
        if not client_id:
            return None

        for file in self.path_mixtapes.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("client_id") == client_id:
                    data["slug"] = file.stem
                    return data
            except (json.JSONDecodeError, OSError) as e:
                self._logger.warning(f"Skipping corrupted mixtape file {file}: {e}")
                continue
        return None

    def update(self, slug: str, updated_data: dict) -> str:
        """Updates an existing mixtape's data while preserving key metadata.

        Loads the stored mixtape, applies changes only to allowed fields, maintains backward compatibility, and
        refreshes the update timestamp before saving.

        Args:
            slug: The slug of the mixtape to update.
            updated_data: A dictionary of fields to update on the mixtape.

        Returns:
            str: The slug of the updated mixtape.

        Raises:
            FileNotFoundError: If a mixtape with the given slug does not exist.
        """
        existing_data = self._load_existing_mixtape(slug)
        updated_data = self._preserve_client_id(existing_data, updated_data)
        existing_data = self._apply_allowed_updates(existing_data, updated_data)
        existing_data = self._ensure_required_fields(existing_data)
        existing_data["updated_at"] = datetime.now().isoformat()

        return self._save_with_slug(
            mixtape_data=existing_data, title=existing_data["title"], slug=slug
        )

    def _load_existing_mixtape(self, slug: str) -> dict:
        """Loads existing mixtape data for the given slug.

        Reads the mixtape JSON file from disk and returns its contents as a dictionary.

        Args:
            slug: The slug of the mixtape to load.

        Returns:
            dict: The loaded mixtape data.

        Raises:
            FileNotFoundError: If a mixtape with the given slug does not exist.
        """
        old_json_path = self.path_mixtapes / f"{slug}.json"
        if not old_json_path.exists():
            raise FileNotFoundError(f"Mixtape with slug '{slug}' not found.")

        with open(old_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _preserve_client_id(self, existing_data: dict, updated_data: dict) -> dict:
        """Ensures client_id is preserved when not provided in updated data.

        Copies the client_id from the existing mixtape data if it is missing in the updated payload.

        Args:
            existing_data: The currently stored mixtape data.
            updated_data: The incoming mixtape update payload.

        Returns:
            dict: The updated data with client_id preserved when applicable.
        """
        if "client_id" not in updated_data and "client_id" in existing_data:
            updated_data["client_id"] = existing_data["client_id"]
        return updated_data

    def _apply_allowed_updates(self, existing_data: dict, updated_data: dict) -> dict:
        """Applies only allowed field updates to an existing mixtape.

        Iterates over a whitelist of fields and updates them when present, avoiding unintended null overwrites.

        Args:
            existing_data: The currently stored mixtape data.
            updated_data: The incoming mixtape update payload.

        Returns:
            dict: The mixtape data with allowed fields updated.
        """
        allowed_fields = [
            "title",
            "tracks",
            "liner_notes",
            "cover",
            "creator_name",
            "gift_flow_enabled",
            "unwrap_style",
            "show_tracklist_after_completion",
            "client_id",
        ]

        for field in allowed_fields:
            if field in updated_data:
                if updated_data[field] is not None or field == "cover":
                    existing_data[field] = updated_data[field]
        return existing_data

    def _ensure_required_fields(self, existing_data: dict) -> dict:
        """Ensures required and backward-compatible fields are present on a mixtape.

        Sets default values for core fields such as title, liner notes, and gift flow options when missing.

        Args:
            existing_data: The mixtape data to normalize.

        Returns:
            dict: The mixtape data with all required fields populated.
        """
        existing_data["title"] = existing_data.get("title", "Untitled Mixtape")
        if "liner_notes" not in existing_data:
            existing_data["liner_notes"] = ""

        existing_data.setdefault("creator_name", "")
        existing_data.setdefault("gift_flow_enabled", False)
        existing_data.setdefault("unwrap_style", "playful")
        existing_data.setdefault("show_tracklist_after_completion", True)

        return existing_data

    def _save_with_slug(self, mixtape_data: dict, title: str, slug: str) -> str:
        """Saves mixtape data and its cover image using a specific slug.

        Persists the mixtape JSON file and optional cover image to disk so it can be retrieved later.

        Args:
            mixtape_data: The mixtape metadata and track information to be stored.
            title: The human-readable title of the mixtape used for logging.
            slug: The filesystem-safe identifier used as the mixtape filename.

        Returns:
            str: The slug under which the mixtape was saved.
        """
        json_path = self.path_mixtapes / f"{slug}.json"

        if cover_value := mixtape_data.pop("cover", None):
            if cover_value.startswith("data:image"):
                try:
                    if path_cover := self._process_cover(
                        cover_data=cover_value, slug=slug
                    ):
                        mixtape_data["cover"] = path_cover
                except Exception as e:
                    self._logger.error(f"Failed to save new cover for {slug}: {e}")
            else:
                mixtape_data["cover"] = cover_value

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(mixtape_data, f, indent=2, ensure_ascii=False)

        self._logger.info(f"Saved mixtape '{title}' as '{slug}'")
        return slug

    def _process_cover(self, cover_data: str, slug: str) -> str | None:
        """
        Processes and saves a cover image from base64-encoded data.

        Decodes the image data, resizes the image, and saves it as a JPEG file in the covers directory.
        Returns the relative path to the saved cover image, or None if processing fails.

        Args:
            cover_data: The base64-encoded image data string.
            slug: The unique identifier for the mixtape.

        Returns:
            str | None: The relative path to the saved cover image, or None if processing fails.
        """
        if not cover_data or not cover_data.startswith("data:image"):
            return None
        try:
            _, b64data = cover_data.split(",", 1)
            image = Image.open(BytesIO(b64decode(b64data)))

            # Convert to RGB mode for JPEG compatibility
            # Handle transparency by adding white background
            if image.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                # Paste image on white background using alpha channel as mask
                if image.mode in ("RGBA", "LA"):
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            image = self._cover_resize(image=image)
            file_cover = self.path_cover / f"{slug}.jpg"
            image.save(file_cover, "JPEG", quality=95, optimize=True)
            return f"covers/{file_cover.name}"
        except Exception as e:
            self._logger.exception(f"Cover opslaan mislukt voor {slug}: {e}")
            return None

    def _cover_resize(self, image: Image, new_width: int = 1200) -> Image:
        """
        Resizes the given image to a specified width while maintaining aspect ratio.

        Calculates the new height to preserve the image's proportions and resizes using high-quality Lanczos filtering.
        If the image width is 1200 or smaller, the original image is returned unchanged.

        Args:
            image: The PIL Image object to resize.
            new_width: The desired width of the resized image (default is 1200).

        Returns:
            Image: The resized PIL Image object, or the original if width <= new_width.
        """
        width, height = image.size
        if width <= new_width:
            return image
        new_height = int(height * (new_width / width))
        image = image.resize((new_width, new_height), Image.LANCZOS)
        return image

    def delete(self, slug: str) -> None:
        """
        Deletes a mixtape and its associated cover image by slug.

        Removes the mixtape JSON file and cover image from disk if they exist.

        Args:
            slug: The slug of the mixtape to delete.
        """
        json_path = self.path_mixtapes / f"{slug}.json"
        json_path.unlink(missing_ok=True)

        cover_path = self.path_cover / f"{slug}.jpg"
        cover_path.unlink(missing_ok=True)

    def list_all(self) -> list[dict]:
        """
        Lists all mixtapes stored on disk.

        Returns a list of dictionaries containing mixtape data, sorted by update or save time.

        Returns:
            list[dict]: List of all mixtape data dictionaries.
        """
        mixtapes = []
        for file in self.path_mixtapes.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                self._logger.warning(f"Skipping corrupted mixtape file {file}: {e}")
                continue

            slug = file.stem
            data["slug"] = slug
            if "liner_notes" not in data:
                data["liner_notes"] = ""
            if "client_id" not in data:
                data["client_id"] = None

            # Normalize timestamps (will also handle legacy saved_at)
            data = self._normalize_timestamps(data)

            mixtapes.append(data)

        # Sort by most recently updated first
        mixtapes.sort(
            key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True
        )
        return mixtapes

    def get(self, slug: str) -> dict | None:
        """Retrieves a single mixtape by its slug if it exists and is valid.

        Loads the mixtape from disk, validates its tracks against the collection, and normalizes optional fields.

        Args:
            slug: The slug identifier of the mixtape to retrieve.

        Returns:
            dict | None: The validated and normalized mixtape data, or None if the mixtape is missing or invalid.
        """
        path = self.path_mixtapes / f"{slug}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self._logger.error(f"Failed to read mixtape {slug}: {e}")
            return None

        try:
            data_verified, has_changed = self._verify_against_collection(data=data)
            if data_verified:
                data_verified = self._verify_mixtape_metadata(data=data_verified)
                data_verified["slug"] = slug
                return data_verified
            else:
                return None
        except Exception as e:
            # Database unavailable (corruption, indexing, etc.)
            # Just use the mixtape data as-is from the JSON file
            self._logger.warning(
                f"Could not verify mixtape {slug} against collection: {e}. "
                f"Using cached data from JSON."
            )

        # Always normalize metadata
        data = self._verify_mixtape_metadata(data=data)
        data["slug"] = slug
        return data

    def _verify_against_collection(self, data: dict) -> tuple[dict, bool | None]:
        """Verifies and refreshes mixtape track metadata against the music collection.

        Compares each track entry with current collection data and updates fields when differences are detected.

        Args:
            data: The mixtape data dictionary containing a "tracks" list to validate.

        Returns:
            tuple[dict, bool | None]: A tuple of the updated tracks list and a flag indicating whether any changes
            were made, or (False, None) if there are no tracks to verify.
        """
        if not (tracks := data["tracks"]):
            return False, None
        has_changes = False
        for track in tracks:
            track_collection = self.collection.get_track(path=Path(track["path"]))
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

    def _verify_mixtape_metadata(self, data: dict) -> dict:
        """Normalizes and completes metadata fields for a mixtape.

        Converts legacy structures, ensures optional fields are present, and standardizes timestamps for consistency.

        Args:
            data: The raw mixtape data dictionary to validate and normalize.

        Returns:
            dict: The updated mixtape data dictionary with normalized metadata and timestamps.
        """
        data = self._convert_old_mixtape(data)
        if "liner_notes" not in data:
            data["liner_notes"] = ""
        if "client_id" not in data:
            data["client_id"] = None

        # Normalize gift flow fields (backward compatibility)
        if "creator_name" not in data:
            data["creator_name"] = ""
        if "gift_flow_enabled" not in data:
            data["gift_flow_enabled"] = False
        if "unwrap_style" not in data:
            data["unwrap_style"] = "playful"
        if "show_tracklist_after_completion" not in data:
            data["show_tracklist_after_completion"] = True

        data = self._normalize_timestamps(data)

        return data

    def _normalize_timestamps(self, data: dict) -> dict:
        """Normalizes timestamp fields on mixtape data for consistency.

        Fills in missing created_at and updated_at values and migrates legacy fields to the current schema.

        Args:
            data: The mixtape data dictionary whose timestamps should be normalized.

        Returns:
            dict: The updated mixtape data dictionary with normalized timestamps.
        """
        now = datetime.now().isoformat()

        # Migrate legacy saved_at â†’ updated_at
        if "saved_at" in data and "updated_at" not in data:
            data["updated_at"] = data.pop("saved_at")
        if "created_at" not in data:
            data["created_at"] = None
        if "updated_at" not in data:
            data["updated_at"] = data["created_at"] or now

        return data

    def _convert_old_mixtape(self, data: dict) -> dict:
        """Converts legacy mixtape data into the current schema.

        Renames outdated track fields so older mixtapes can be handled consistently with newer ones.

        Args:
            data: The raw mixtape data dictionary that may use legacy field names.

        Returns:
            dict: The updated mixtape data dictionary using the current field names.
        """
        for track in data.get("tracks", []):
            if "title" in track:
                track["track"] = track.pop("title")
        return data
