![Utilities](../images/utilities.png){ align=right width="90" }

# Utilities

## Git version utility

![versioning](../images/version.png){ align=right width="90" }

The `version_info.py` file provides utilities to access Git version information of the codebase. imported wherever version information is needed within the application. Its design ensures robust and consistent version reporting across different environments and deployment scenarios.

It attempts to retrieve the latest Git tag, formats the version string to include commit distance and hash when not on a tag, and gracefully falls back to a default value ("dev") if Git is unavailable or an error occurs. This ensures that the application always has a meaningful version identifier, useful for debugging, deployment, and user information.

## API

### ::: src.utils.version_info

---

## Add logo to cover for Open Graph

![versioning](../images/opengraph.png){ align=right width="90" }

The `logo_on_cover.py` file provides a Flask blueprint that dynamically generates cover images with a logo overlaid in a specified corner as an image that can be used for an [Open Graph](https://ogp.me/) . It exposes an HTTP endpoint that takes a cover image filename and optional query parameters (logo scale, corner, margin), composites the logo onto the cover, and returns the resulting PNG image. The file also implements caching to optimize repeated requests for the same parameters.

The main responsibilities of this file are:

- Loading and converting an SVG logo to PNG.
- Overlaying the logo onto a cover image at a configurable position and scale.
- Serving the composited image via a Flask route, with input validation and caching.

### ::: src.utils.logo_on_cover
