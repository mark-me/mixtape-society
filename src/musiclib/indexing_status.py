import json
from datetime import datetime, timezone
from pathlib import Path
from config import config as Config # assuming config is accessible

#STATUS_FILE = Path(Config.DATA_ROOT) / "indexing_status.json"

def set_indexing_status(data_root: Path | str, status: str, **extra):
    """Write current indexing status to a JSON file."""
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "status": status,
        "started_at": datetime.now(timezone.utc).isoformat(),
        **extra
    }
    status_file.write_text(json.dumps(data), encoding="utf-8")

def clear_indexing_status(data_root: Path | str):
    """Remove the indexing status file."""
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"
    status_file.unlink(missing_ok=True)

def get_indexing_status(data_root: Path | str):
    """Read current indexing status, or return None if not indexing."""
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"
    if not status_file.exists():
        return None
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return None