import os
import subprocess
import re
from logtools import get_logger

logger = get_logger(__name__)

def get_version() -> str:
    """Get the application version string for the current environment.

    This function prefers a pre-baked version from the environment and falls
    back to querying Git metadata when available.

    Args:
        APP_VERSION: Optional environment variable containing a pre-baked
            version string.

    Returns:
        The resolved version string, or "dev" when no version information can
        be determined.
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
            version = _parse_and_format_version(result)
            os.environ["APP_VERSION"] = version
            return version
    except Exception as e:
        logger.warning(f"Git version detection failed: {e}")

    return "dev"


def _parse_and_format_version(result: str) -> str:
    """Normalize a raw version string into a standardized application format.

    This helper focuses on cleaning tag prefixes and encoding additional build
    metadata into a consistent representation.

    Args:
        result: The raw version string, typically produced by Git describe.

    Returns:
        A normalized version string that adheres to the application's expected
        version format.
    """
    version_pattern = re.compile(r"^v?\d+\.\d+\.\d+([-\+].*)?$")
    version = result
    if version.startswith("v"):
        match = version_pattern.match(version)
        if match:
            version = version[1:]

    if "-" in version:
        parts = version.split("-")
        if len(parts) >= 3:
            return f"{parts[0]}+{parts[1]}.{parts[2]}"
        elif len(parts) >= 2:
            return f"{parts[0]}+dev.{parts[1]}"

    return version