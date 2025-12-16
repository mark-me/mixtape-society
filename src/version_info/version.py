import re
import subprocess
from logtools import get_logger

logger = get_logger(__name__)

def get_version() -> str:
    """
    Returns the current version string for the application.

    Retrieves the version from the latest Git tag, formatting it to include commit distance and hash if not on a tag.
    Returns "dev" if Git is unavailable or an error occurs.

    Returns:
        str: The formatted version string or "dev" if unavailable.
    """
    try:
        result = _get_git_describe()
        return "dev" if result is None else _parse_and_format_version(result)
    except (subprocess.CalledProcessError, Exception):
        return "dev"

def _get_git_describe() -> str | None:
    """
    Runs the Git describe command and returns its output as a string.

    Attempts to retrieve the current version description from Git. Returns None if Git is not available or an error occurs.

    Returns:
        str | None: The Git describe output string, or None if unavailable.
    """
    git_args = ["git", "describe", "--tags", "--abbrev=8", "--always"]
    try:
        result = subprocess.check_output(
            git_args,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5
        )
        return result.strip()
    except FileNotFoundError:
        logger.warning("Git is not installed or not found in PATH.")
        return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git command failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error while running git command: {e}")
        return None

def _parse_and_format_version(result: str) -> str:
    """
    Parses and formats a Git describe string into a version string.

    Converts the raw output from `git describe` into a standardized version string, handling tags, commit distances, and hashes.

    Args:
        result (str): The raw version string from Git.

    Returns:
        str: The formatted version string.
    """
    version_pattern = re.compile(r"^v?\d+\.\d+\.\d+([-\+].*)?$")
    version = _strip_v_prefix_if_tagged(result, version_pattern)
    if "-" in version:
        version = _format_dash_version(version)
    return version

def _strip_v_prefix_if_tagged(result: str, version_pattern: re.Pattern) -> str:
    """
    Removes the leading 'v' from a version string if present and matched by the pattern.

    Checks if the version string matches the expected tag pattern and strips the 'v' prefix if it exists.

    Args:
        result (str): The version string to process.
        version_pattern (re.Pattern): The compiled regex pattern for version tags.

    Returns:
        str: The version string without a leading 'v', if applicable.
    """
    if version_pattern.match(result):
        has_v_prefix = result.startswith("v")
        return result[1:] if has_v_prefix else result
    return result

def _format_dash_version(version: str) -> str:
    """
    Formats a version string containing dashes into a standardized version format.

    Converts a dash-separated version string into a plus-separated format, handling commit distances and hashes for development versions.

    Args:
        version (str): The dash-separated version string.

    Returns:
        str: The formatted version string.
    """
    parts = version.split("-")
    if len(parts) >= 3:
        part1 = parts[1]
        part2 = parts[2]
        return f"{parts[0]}+{part1}.{part2}"
    elif len(parts) >= 2:
        part1 = parts[1]
        return f"{parts[0]}+dev.{part1}"
    else:
        return f"{parts[0]}+unknown"