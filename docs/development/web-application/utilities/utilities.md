![Utilities](../images/utilities.png){ align=right width="90" }

# Utilities

## 🔖 Git version utility

![versioning](../images/version.png){ align=right width="70" }

The `version_info.py` file provides `get_version()` to access Git version information of the codebase. imported wherever version information is needed within the application. Its design ensures robust and consistent version reporting across different environments and deployment scenarios.

It attempts to retrieve the latest Git tag, formats the version string to include commit distance and hash when not on a tag, and gracefully falls back to a default value ("dev") if Git is unavailable or an error occurs. This ensures that the application always has a meaningful version identifier, useful for debugging, deployment, and user information.

### API `get_version`

#### ::: src.utils.version_info

## 🖼️ Cover image compositor

![cover composition](../images/album_cover.png){ align=right width="70" }

This file `cover_compositor.py` defines a `CoverCompositor` utility that generates a composite “collage” image from a set of album cover images. It:

- Takes a directory of cover images and a list of cover filenames (with possible duplicates).
- Builds a square grid (N×N) of cover tiles sized 400×400 pixels each.
- Uses cover frequency (duplicates) to influence which covers are repeated when filling the grid.
- Performs basic image processing (center square crop, slight contrast boost).
- Outputs the final composite as a base64-encoded JPEG data URL (`data:image/jpeg;base64,...`), suitable for embedding directly in HTML or APIs without separate image hosting.

### API `CoverCompositor`

#### ::: src.utils.cover_compositor.CoverCompositor
