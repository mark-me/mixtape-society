import json
from pathlib import Path
from datetime import datetime
from base64 import b64decode
from typing import Optional

from common.logging import Logger, NullLogger


class MixtapeManager:
    """Manages mixtape files and their associated cover images.

    Provides functionality to create, update, delete, list, and retrieve mixtapes stored on disk.
    """
    def __init__(self, path_mixtapes: Path, logger: Logger | None = None) -> None:
        """Initializes the MixtapeManager with paths for mixtapes and covers.

        Sets up the directory structure for storing mixtape JSON files and cover images.

        Args:
            path_mixtapes: Path to the directory where mixtapes are stored.
            logger: Optional logger instance for logging actions.
        """
        self._logger: Logger = logger or NullLogger()
        self.path_mixtapes: Path = path_mixtapes
        self.path_cover: Path = path_mixtapes / "covers"
        self.path_mixtapes.mkdir(exist_ok=True)
        self.path_cover.mkdir(exist_ok=True)

    def _sanitize_title(self, title: str) -> str:
        """Convert title to a filesystem-safe slug."""
        return "".join(c if c.isalnum() or c in "-_ " else "_" for c in title).strip()

    def _generate_unique_slug(self, base_slug: str, current_slug: Optional[str] = None) -> str:
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
        """
        Saves a new mixtape to disk and generates a unique slug for it.

        Creates a new mixtape JSON file and cover image if provided, returning the slug used for storage.

        Args:
            mixtape_data: Dictionary containing mixtape information, including title and optional cover.

        Returns:
            str: The slug used to save the mixtape.
        """
        title = mixtape_data.get("title", "Untitled Mixtape")
        base_slug = self._sanitize_title(title)
        slug = self._generate_unique_slug(base_slug)

        return self._save_with_slug(mixtape_data, title, slug)

    def update(self, slug: str, updated_data: dict) -> str:
        """
        Update an existing mixtape by slug.

        Args:
            slug (str): Current slug of the mixtape to update.
            updated_data (dict): Dictionary with fields to update.
                          Must include 'title' if you want to change the title/slug.
                          May include 'cover' (new base64 image), and any other fields.

        Returns:
            str: The new slug (may be different if title changed).

        Raises:
            FileNotFoundError: If the mixtape doesn't exist.
        """
        old_json_path = self.path_mixtapes / f"{slug}.json"
        if not old_json_path.exists():
            raise FileNotFoundError(f"Mixtape with slug '{slug}' not found.")

        # Load existing data
        with open(old_json_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

        # Determine new title and whether slug will change
        new_title = updated_data.get("title", existing_data.get("title", "Untitled Mixtape"))
        new_base_slug = self._sanitize_title(new_title)

        # Generate potential new slug (allow reusing current one if title unchanged)
        new_slug = self._generate_unique_slug(new_base_slug, current_slug=slug)

        # Merge data
        existing_data.update(updated_data)

        # Ensure liner_notes exists (backward compatibility)
        if "liner_notes" not in existing_data:
            existing_data["liner_notes"] = ""

        # Set final title (in case it was missing)
        existing_data["title"] = new_title

        # Add/update timestamp
        existing_data["updated_at"] = datetime.now().isoformat()
        # Preserve original saved_at if it exists
        if "saved_at" not in existing_data:
            existing_data["saved_at"] = existing_data["updated_at"]

        # Save with the (possibly new) slug
        final_slug = self._save_with_slug(existing_data, new_title, new_slug)

        # If slug changed, clean up old files
        if new_slug != slug:
            self._logger.info(f"Slug changed from '{slug}' to '{new_slug}'. Deleting old files.")
            old_json_path.unlink(missing_ok=True)
            old_cover_path = self.path_cover / f"{slug}.jpg"
            old_cover_path.unlink(missing_ok=True)

        return final_slug

    def _save_with_slug(self, mixtape_data: dict, title: str, slug: str) -> str:
        """
        Saves mixtape data and cover image to disk using the provided slug.

        Writes the mixtape JSON file and handles cover image encoding and storage.

        Args:
            mixtape_data: Dictionary containing mixtape information.
            title: Title of the mixtape.
            slug: Slug to use for saving the mixtape.

        Returns:
            str: The slug used to save the mixtape.
        """
        json_path = self.path_mixtapes / f"{slug}.json"

        # Handle cover
        if cover_base64 := mixtape_data.pop("cover", None):  # Remove temp base64 field
            try:
                cover_bytes = b64decode(cover_base64.split(",")[1])
                cover_path = self.path_cover / f"{slug}.jpg"
                with open(cover_path, "wb") as f:
                    f.write(cover_bytes)
                mixtape_data["cover"] = f"covers/{slug}.jpg"
            except Exception as e:
                self._logger.error(f"Failed to save cover for {slug}: {e}")
                mixtape_data.pop("cover", None)  # Remove broken cover reference
        else:
            # Preserve existing cover path if it exists
            existing_cover = mixtape_data.get("cover")
            if existing_cover and Path(existing_cover).name != f"{slug}.jpg":
                # Old cover from previous slug — optionally rename or leave as-is
                # Here we just keep the old path (simpler)
                pass
            elif not existing_cover:
                # Ensure cover is None if not present
                mixtape_data.pop("cover", None)

        # Final save
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(mixtape_data, f, indent=2)

        self._logger.info(f"Saved mixtape '{title}' as '{slug}'")
        return slug

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
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            slug = file.stem
            data["slug"] = slug
            if "liner_notes" not in data:
                data["liner_notes"] = ""
            mixtapes.append(data)

        mixtapes.sort(key=lambda x: x.get("updated_at", x.get("saved_at", "")), reverse=True)
        return mixtapes

    def get(self, slug: str) -> dict | None:
        """
        Retrieves a mixtape's data by its slug.

        Returns the mixtape data dictionary if found, or None if the mixtape does not exist.

        Args:
            slug: The slug of the mixtape to retrieve.

        Returns:
            dict | None: The mixtape data dictionary, or None if not found.
        """
        path = self.path_mixtapes / f"{slug}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data = self._convert_old_mixtape(data)
        if "liner_notes" not in data:
            data["liner_notes"] = ""
        data["slug"] = slug
        return data

    def _convert_old_mixtape(self, data: dict) -> dict:
        """Normalizes legacy mixtape data to the current schema.
        Renames old track fields so that consumers can work with a consistent structure.

        Args:
            data: The mixtape data dictionary potentially using an older field format.

        Returns:
            dict: The updated mixtape data dictionary with normalized track keys.
        """
        for track in data["tracks"]:
            if "title" in track:
                track["track"] = track.pop("title")
        return data