![versioning](../../images/opengraph.png){ align=right width="90" }

# Add logo to cover for Open Graph

The `logo_on_cover.py` file provides a Flask blueprint that dynamically generates cover images with a logo overlaid in a specified corner as an image that can be used for an [Open Graph](https://ogp.me/) . It exposes an HTTP endpoint that takes a cover image filename and optional query parameters (logo scale, corner, margin), composites the logo onto the cover, and returns the resulting PNG image. The file also implements caching to optimize repeated requests for the same parameters.

The main responsibilities of this file are:

- Loading and converting an SVG logo to PNG.
- Overlaying the logo onto a cover image at a configurable position and scale.
- Serving the composited image via a Flask route, with input validation and caching.

## 🔌 API

### ::: src.routes.logo_on_cover
