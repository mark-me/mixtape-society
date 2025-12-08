import json
from pathlib import Path
from datetime import datetime
from base64 import b64decode


class MixtapeManager:
    def __init__(self, path_mixtapes: Path):
        self.path_mixtapes = path_mixtapes
        self.path_cover = path_mixtapes / "covers"
        self.path_mixtapes.mkdir(exist_ok=True)
        self.path_cover.mkdir(exist_ok=True)

    def save(self, mixtape_data: dict):
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

    def list_all(self) -> list[dict]:
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
        path = self.path_mixtapes / f"{slug}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["slug"] = slug
        return data
