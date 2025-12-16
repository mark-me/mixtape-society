import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from common.logging import Logger, NullLogger


def set_indexing_status(
    data_root: Path | str, status: str, total: int, current: int
) -> None:
    """Writes the current indexing status to a JSON file.

    Calculates progress, determines the start time, builds the status data, and writes it atomically to the status file for the given data root.

    Args:
        data_root (Path | str): The root directory containing the indexing status file.
        status (str): The current status string (e.g., 'rebuilding', 'resyncing').
        total (int): The total number of items to process.
        current (int): The number of items processed so far.

    Returns:
        None
    """
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    progress = _calculate_progress(total, current)
    started_at = _get_started_at(status_file) or datetime.now(timezone.utc).isoformat()
    data = _build_status_data(status, started_at, total, current, progress)
    _atomic_write_json(status_file, data)


def _atomic_write_json(status_file: Path, data: dict) -> None:
    """Atomically writes the given data as JSON to the status file.

    Writes to a temporary file and then atomically replaces the target file to avoid partial writes.

    Note:
        The atomic replacement requires that both the temporary file and the target status file
        reside on the same filesystem. If they are on different filesystems, atomic replacement may fail.

    Args:
        status_file (Path): The path to the status file.
        data (dict): The data to serialize and write.

    Returns:
        None
    """
    tmp_dir = status_file.parent
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=tmp_dir, delete=False
    ) as tmp_file:
        tmp_file.write(json.dumps(data))
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        temp_path = Path(tmp_file.name)
    # Ensure both files are on the same filesystem for atomic replacement
    if os.stat(temp_path).st_dev != os.stat(status_file.parent).st_dev:
        raise OSError(
            "Atomic replacement requires temp file and status file to be on the same filesystem."
        )
    temp_path.replace(status_file)


def _calculate_progress(total: int, current: int) -> float:
    """Calculates the progress of the indexing operation as a float between 0.0 and 1.0.

    Returns 0.0 if the total is zero or negative, otherwise returns the clamped ratio of current to total.

    Args:
        total (int): The total number of items to process.
        current (int): The number of items processed so far.

    Returns:
        float: The progress value between 0.0 and 1.0.
    """
    return 0.0 if total <= 0 else max(0.0, min(current / total, 1.0))


def _get_started_at(status_file: Path) -> str | None:
    """Retrieves the 'started_at' timestamp from the indexing status file if it exists.

    Attempts to read and parse the status file to extract the original start time of the indexing operation.
    Returns None if the file does not exist or cannot be read.

    Args:
        status_file (Path): The path to the indexing status JSON file.

    Returns:
        str | None: The ISO-formatted start time string, or None if unavailable.
    """
    if status_file.exists():
        try:
            with status_file.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
                return existing_data.get("started_at")
        except Exception:
            return None
    return None


def _build_status_data(
    status: str, started_at: str, total: int, current: int, progress: float
) -> dict:
    """Builds a dictionary representing the current indexing status.

    Constructs a status dictionary with all relevant fields for writing to the status file, including timestamps and progress.

    Args:
        status (str): The current status string (e.g., 'rebuilding', 'resyncing').
        started_at (str): The ISO-formatted timestamp when indexing started.
        total (int): The total number of items to process.
        current (int): The number of items processed so far.
        progress (float): The progress value between 0.0 and 1.0.

    Returns:
        dict: The status data dictionary to be serialized as JSON.
    """
    return {
        "status": status,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "current": current,
        "progress": progress,
    }


def clear_indexing_status(data_root: Path | str) -> None:
    """Removes the indexing status file for the given data root.

    Deletes the indexing status JSON file if it exists, effectively clearing any current indexing progress or state.

    Args:
        data_root (Path | str): The root directory containing the indexing status file.

    Returns:
        None
    """
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"
    status_file.unlink(missing_ok=True)


def get_indexing_status(data_root: Path | str, logger :Logger=None|None) -> dict | None:
    """
    Retrieves the current indexing status from the status file for the given data root.

    Attempts to read and parse the indexing status JSON file, returning its contents as a dictionary.
    Handles missing files and JSON decode errors gracefully, logging errors if a logger is provided.

    Args:
        data_root (Path | str): The root directory containing the indexing status file.
        logger (Logger, optional): Logger for error reporting. Uses NullLogger if not provided.

    Returns:
        dict | None: The indexing status data as a dictionary, or None if the file does not exist or cannot be read.
    """
    logger = logger or NullLogger()
    data_root = Path(data_root)
    status_file = data_root / "indexing_status.json"

    try:
        with status_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {status_file}: {e}")
        return None
    status_file = data_root / "indexing_status.json"
    if not status_file.exists():
        return None
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return None
