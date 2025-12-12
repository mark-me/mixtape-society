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
        # Run git describe --tags --abbrev=8
        # This returns something like: v1.2.3-5-gabc12345 or just v1.2.3 if on a tag
        git_args = ["git", "describe", "--tags", "--abbrev=8", "--always"]
        try:
            result = subprocess.check_output(
                git_args,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5
            )
            result = result.strip()
        except FileNotFoundError:
            logger.warning("Git is not installed or not found in PATH.")
            return "dev"

        has_v_prefix = result.startswith("v")
        version = result[1:] if has_v_prefix else result

        has_dash = "-" in version
        if has_dash:
            parts = version.split("-")
            has_three_parts = len(parts) >= 3

            if has_three_parts:
                part1 = parts[1]
                part2 = parts[2]
                version = f"{parts[0]}+{part1}.{part2}"
            elif len(parts) >= 2:
                part1 = parts[1]
                version = f"{parts[0]}+dev.{part1}"
            else:
                # Unexpected format, fallback to original result or safe default
                version = f"{parts[0]}+unknown"
        return version

    except (subprocess.CalledProcessError, Exception):
        return "dev"