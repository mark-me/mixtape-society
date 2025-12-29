![Utilities](../images/utilities.png){ align=right width="90" }

# Utilities

## Git version utility

![versioning](../images/version.png){ align=right width="90" }

The `version_info.py` file provides utilities to access Git version information of the codebase. imported wherever version information is needed within the application. Its design ensures robust and consistent version reporting across different environments and deployment scenarios.

It attempts to retrieve the latest Git tag, formats the version string to include commit distance and hash when not on a tag, and gracefully falls back to a default value ("dev") if Git is unavailable or an error occurs. This ensures that the application always has a meaningful version identifier, useful for debugging, deployment, and user information.

## API

### ::: src.utils.version_info


