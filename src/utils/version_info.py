import os
import subprocess
import re
from logtools import get_logger

logger = get_logger(__name__)

def get_version() -> str:
    """
    Returns the application version.

    Priority:
    1. APP_VERSION environment variable (set at build time) → used in Docker
    2. Fallback to git describe (only useful in local dev)
    3. Default to "dev"
    """
    if baked_version := os.getenv("APP_VERSION"):
        return baked_version

    # Local development fallback
    try:
        if result := subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=8", "--always"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip():
            return _parse_and_format_version(result)
    except Exception as e:
        logger.debug(f"Git version detection failed: {e}")

    return "dev"


def _parse_and_format_version(result: str) -> str:
    # Keep your existing parsing logic, but simplified since we mostly rely on baked version
    version_pattern = re.compile(r"^v?\d+\.\d+\.\d+([-\+].*)?$")
    version = result
    if version.startswith("v"):
        match = version_pattern.match(version)
        if match:
            version = version[1:]  # strip leading v only if it's a proper tag

    if "-" in version:
        parts = version.split("-")
        if len(parts) >= 3:
            return f"{parts[0]}+{parts[1]}.{parts[2]}"
        elif len(parts) >= 2:
            return f"{parts[0]}+dev.{parts[1]}"

    return version