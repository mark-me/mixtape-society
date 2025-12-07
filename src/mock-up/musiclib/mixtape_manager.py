import json
from pathlib import Path
from datetime import datetime
from base64 import b64decode

MIXTAPE_DIR = Path(__file__).parent.parent / "mixtapes"
COVER_DIR = MIXTAPE_DIR / "covers"
MIXTAPE_DIR.mkdir(exist_ok=True)
COVER_DIR.mkdir(exist_ok=True)

class MixtapeManager:
    @staticmethod
    def save(mixtape_data: dict):
        title = mixtape_data["title"]
        sanitized_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
        json_path = MIXTAPE_DIR / f"{sanitized_title}.json"

        # Cover opslaan als bestand (van base64)
        if cover_base64 := mixtape_data.get("cover"):
            cover_bytes = b64decode(cover_base64.split(",")[1])  # Verwijder data: prefix
            cover_path = COVER_DIR / f"{sanitized_title}.jpg"
            with open(cover_path, "wb") as f:
                f.write(cover_bytes)
            mixtape_data["cover"] = f"covers/{sanitized_title}.jpg"  # Relatief pad

        mixtape_data["saved_at"] = datetime.now().isoformat()

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(mixtape_data, f, indent=2)

        return sanitized_title

    @staticmethod
    def list_all() -> list[dict]:
        mixtapes = []
        for file in MIXTAPE_DIR.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["title"] = file.stem.replace("_", " ")  # Herstel titel
                mixtapes.append(data)
        mixtapes.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return mixtapes

    @staticmethod
    def get(title: str) -> dict | None:
        sanitized_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
        path = MIXTAPE_DIR / f"{sanitized_title}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["title"] = sanitized_title.replace("_", " ")  # Herstel titel
            return data