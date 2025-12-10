import json
from pathlib import Path
from datetime import datetime
from base64 import b64decode


class MixtapeManager:
    """
    Manages the storage and retrieval of mixtapes and their cover images.

    Handles saving, listing, and loading mixtape data from disk, including cover image processing and metadata management.
    """
    def __init__(self, path_mixtapes: Path):
        self.path_mixtapes = path_mixtapes
        self.path_cover = path_mixtapes / "covers"
        self.path_mixtapes.mkdir(exist_ok=True)
        self.path_cover.mkdir(exist_ok=True)

    def save(self, mixtape_data: dict):
        """
        Saves a mixtape and its cover image to disk.

        Stores the mixtape data as a JSON file and saves the cover image if provided. Returns the sanitized title used as the slug.

        Args:
            mixtape_data: The dictionary containing mixtape information.

        Returns:
            str: The sanitized title used as the slug for the mixtape.
        """
        title = mixtape_data["title"]
        sanitized_title = "".join(
            c if c.isalnum() or c in "-_ " else "_" for c in title
        )
        json_path = self.path_mixtapes / f"{sanitized_title}.json"

        # Cover opslaan als bestand (van base64)
        if cover_base64 := mixtape_data.get("cover"):
            cover_bytes = b64decode(
                cover_base64.split(",")[1]
            )  # Verwijder data: prefix
            cover_path = self.path_cover / f"{sanitized_title}.jpg"
            with open(cover_path, "wb") as f:
                f.write(cover_bytes)
            mixtape_data["cover"] = f"covers/{sanitized_title}.jpg"  # Relatief pad

        mixtape_data["saved_at"] = datetime.now().isoformat()

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(mixtape_data, f, indent=2)

        return sanitized_title

    def delete(self) -> None:
        """
        Deletes a mixtape and its associated cover image from disk.

        Removes the mixtape JSON file and cover image if they exist.

        Returns:
            None
        """
        pass  # TODO: Implementation would go here

    def list_all(self) -> list[dict]:
        """
        Lists all saved mixtapes with their metadata.

        Reads all mixtape JSON files, adds their slug, and returns a sorted list of mixtape dictionaries.

        Returns:
            list[dict]: A list of dictionaries containing mixtape data.
        """
        mixtapes = []
        for file in self.path_mixtapes.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            slug = file.stem # Sanitized title = slug (bestandsnaam zonder .json)
            data["slug"] = slug
            mixtapes.append(data)

        mixtapes.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return mixtapes

    def get(self, slug: str) -> dict | None:
        """
        Retrieves a mixtape by its slug.

        Loads the mixtape data from disk if it exists and returns it as a dictionary, or None if not found.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            dict | None: The mixtape data dictionary, or None if the mixtape does not exist.
        """
        path = self.path_mixtapes / f"{slug}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["slug"] = slug
        return data
