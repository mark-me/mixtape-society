# utils/og_image.py
from io import BytesIO
from pathlib import Path

import cairosvg
from flask import Blueprint, abort, current_app, request, send_file
from PIL import Image, ImageDraw, ImageFilter

from common.logging import Logger, NullLogger


def create_og_cover_blueprint(
    path_logo: Path, logger: Logger | None = None
) -> Blueprint:
    """
    Creates a Flask blueprint for serving cover images with a logo overlay.

    This function sets up routes and logic for handling requests to overlay a logo on cover images,
    including caching and query parameter validation.

    Args:
        logger: An optional Logger instance for logging.

    Returns:
        A Flask Blueprint configured for cover image overlay routes.
    """
    og = Blueprint("og", __name__)

    logger: Logger = logger or NullLogger()

    @og.route("/cover/<path:filename>")
    def cover_with_logo(filename):
        """
        Serves a cover image with a logo overlaid, using query parameters for customization.

        This function locates the requested cover image, validates input parameters, overlays the logo,
        and returns the composited PNG image. Results are cached for performance.

        Args:
            filename: The name of the cover image file.

        Returns:
            A Flask response containing the PNG image with the logo overlaid.

        Raises:
            Aborts with a 404 error if the cover image is not found.
            Aborts with a 400 error if query parameters are invalid.
        """
        cover_path = _get_cover_path(filename)
        _validate_cover_path(cover_path)
        logo_scale, corner, margin = _get_query_params()
        _validate_query_params(logo_scale, corner, margin)
        # TODO: Add redis caching
        # Use cover file modification time for cache key
        # cover_mtime = cover_path.stat().st_mtime
        # cache_key = f"{filename}:{cover_mtime}:{logo_scale}:{corner}:{margin}"
        # if cached := current_app.cache.get(cache_key):
        #     return send_file(BytesIO(cached), mimetype="image/png")
        with open(path_logo, "rb") as f:
            file_logo = f.read()
        result = overlay_logo_bytes(
            cover_bytes=cover_path.read_bytes(),
            svg_bytes=file_logo,
            logo_scale=logo_scale,
            corner=corner,
            margin=margin,
        )
        # current_app.cache.set(cache_key, result, timeout=60 * 60 * 24)
        return send_file(BytesIO(result), mimetype="image/png")

    return og


def _svg_to_png(svg_bytes: bytes, width: int, height: int) -> bytes:
    """Converts an SVG image to PNG format with the specified width and height.

    This function takes SVG image data as bytes and returns PNG image data as bytes.

    Args:
        svg_bytes: The SVG image data as bytes.
        width: The desired output width in pixels.
        height: The desired output height in pixels.

    Returns:
        PNG image data as bytes.
    """
    return cairosvg.svg2png(
        bytestring=svg_bytes, output_width=width, output_height=height
    )


def overlay_logo_bytes(
    cover_bytes: bytes,
    svg_bytes: bytes,
    *,
    logo_scale: float = 0.4,
    corner: str = "bottom_right",
    margin: int = 10,
) -> bytes:
    """Overlays a logo onto a cover image and returns the composited image as PNG bytes.

    This function places a logo, provided as SVG bytes, onto a cover image at a specified corner and scale.

    Args:
        cover_bytes (bytes): The cover image data as bytes.
        svg_bytes (bytes): The SVG logo image data as bytes.
        logo_scale (float): The scale of the logo relative to the shortest side of the cover image.
        corner (str): The corner of the cover image to place the logo ('bottom_right', 'bottom_left', 'top_right', 'top_left').
        margin (int): The margin in pixels between the logo and the edge of the cover image.

    Returns:
        PNG image data as bytes with the logo overlaid.

    Raises:
        ValueError: If an unsupported corner is specified.
    """
    cover = _prepare_cover(cover_bytes)
    canvas = _create_blurred_canvas(cover)

    orig_width, orig_height = cover.size
    img_logo = _prepare_logo(svg_bytes, (orig_width, orig_height), logo_scale)
    x, y = _calculate_logo_position(canvas.size, img_logo.size, corner, margin)

    # Ensure logo has an alpha channel for use as mask
    if img_logo.mode != "RGBA":
        img_logo = img_logo.convert("RGBA")

    canvas.paste(img_logo, (x, y), img_logo)

    return _save_image_to_bytes(canvas)


def _prepare_cover(cover_bytes: bytes) -> Image.Image:
    """Prepares a cover image for use as an Open Graph image background.

    This function loads the cover image from bytes, resizes it to cover the target dimensions,
    and center-crops it to the fixed Open Graph aspect ratio.

    Args:
        cover_bytes: The raw cover image data as bytes.

    Returns:
        A PIL Image object resized and cropped to the Open Graph target size.
    """
    TARGET_WIDTH = 1200
    TARGET_HEIGHT = 630
    TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT  # ~1.90476

    cover = _load_cover_image(cover_bytes)
    orig_width, orig_height = cover.size
    orig_ratio = orig_width / orig_height

    # Resize to cover the target (scale so smaller side matches or exceeds target)
    if orig_ratio > TARGET_RATIO:  # Original is wider → match height
        new_height = TARGET_HEIGHT
        new_width = int(round(new_height * orig_ratio))
    else:  # Original is taller or square → match width
        new_width = TARGET_WIDTH
        new_height = int(round(new_width / orig_ratio))

    cover = cover.resize((new_width, new_height), Image.LANCZOS)

    # Center crop to exactly 1200x630
    left = (new_width - TARGET_WIDTH) // 2
    top = (new_height - TARGET_HEIGHT) // 2
    return cover.crop((left, top, left + TARGET_WIDTH, top + TARGET_HEIGHT))


def _create_blurred_canvas(cover: Image.Image) -> Image.Image:
    """Creates a blurred background canvas from a cover image.

    This function blurs a copy of the cover image and overlays the original image on top to create a subtle background effect.

    Args:
        cover: The PIL Image object representing the prepared cover.

    Returns:
        A PIL Image object with the blurred background and sharp cover overlay.
    """
    blurred = cover.copy()
    blurred = blurred.filter(ImageFilter.GaussianBlur(radius=30))
    canvas = blurred
    canvas.paste(cover, (0, 0), cover)
    return canvas


def _prepare_logo(
    svg_bytes: bytes, cover_size: tuple[int, int], logo_scale: float
) -> Image.Image:
    """Prepares a logo image for overlay on a cover.

    This function loads the logo from SVG bytes, scales it relative to the cover size, and adds a visual backdrop for better contrast.

    Args:
        svg_bytes: The SVG logo image data as bytes.
        cover_size: The (width, height) of the cover image the logo will be placed on.
        logo_scale: The scale of the logo relative to the shortest side of the cover image.

    Returns:
        A PIL Image object of the prepared logo with backdrop applied.
    """
    img_logo = _load_logo_image(svg_bytes, cover_size, logo_scale)
    return _add_logo_backdrop(img_logo=img_logo)


def _load_cover_image(cover_bytes: bytes) -> Image.Image:
    """Loads a cover image from bytes and converts it to RGBA format.

    This function opens the image from the provided bytes and ensures it is in RGBA mode.

    Args:
        cover_bytes: The cover image data as bytes.

    Returns:
        A PIL Image object in RGBA format.
    """
    return Image.open(BytesIO(cover_bytes)).convert("RGBA")


def _load_logo_image(
    svg_bytes: bytes, cover_size: tuple[int, int], logo_scale: float
) -> Image.Image:
    """Loads and scales a logo image from SVG bytes to fit the cover image.

    This function converts SVG logo bytes to a PNG image, scaled according to the cover image size and logo scale.

    Args:
        svg_bytes (bytes): The SVG logo image data as bytes.
        cover_size (tuple[int, int]): The (width, height) of the cover image.
        logo_scale (float): The scale of the logo relative to the shortest side of the cover image.

    Returns:
        A PIL Image object of the logo in RGBA format.
    """
    width_cover, height_cover = cover_size
    short_side = min(width_cover, height_cover)
    max_len = int(short_side * logo_scale)
    temp_png = cairosvg.svg2png(bytestring=svg_bytes)
    with Image.open(BytesIO(temp_png)) as tmp_img:
        orig_w, orig_h = tmp_img.size
    scale_factor = max_len / orig_w if orig_w >= orig_h else max_len / orig_h

    final_w = max(1, int(round(orig_w * scale_factor)))
    final_h = max(1, int(round(orig_h * scale_factor)))
    logo_png = cairosvg.svg2png(
        bytestring=svg_bytes, output_width=final_w, output_height=final_h
    )
    logo_img = Image.open(BytesIO(logo_png)).convert("RGBA")
    return logo_img


def _add_logo_backdrop(
    img_logo: Image, backdrop_opacity: float = 0.6, backdrop_padding: int = 2
):
    """
    Adds a semi-transparent white backdrop behind a logo image.

    This function creates a new image with a white rectangle as a backdrop and pastes the logo image on top, providing padding and adjustable opacity.

    Args:
        img_logo (Image): The PIL Image object of the logo.
        backdrop_opacity (float): The opacity of the backdrop (0.0 to 1.0).
        backdrop_padding (int): The padding in pixels around the logo.

    Returns:
        Image: A new PIL Image object with the logo and backdrop.
    """
    width_logo, height_logo = img_logo.size
    width_backdrop = width_logo + 2 * backdrop_padding
    height_backdrop = height_logo + 2 * backdrop_padding
    composite = Image.new("RGBA", (width_backdrop, height_backdrop), (0, 0, 0, 0))
    draw = ImageDraw.Draw(composite)
    backdrop = (0, 0, 0, int(255 * backdrop_opacity))
    draw.rectangle(
        [(0, 0), (width_backdrop - 1, height_backdrop - 1)],  # inclusive bounds
        fill=backdrop,
    )
    composite.paste(img_logo, (backdrop_padding, backdrop_padding), img_logo)
    return composite


def _calculate_logo_position(
    cover_size: tuple[int, int], logo_size: tuple[int, int], corner: str, margin: int
) -> tuple[int, int]:
    """Calculates the position to place the logo on the cover image.

    This function determines the (x, y) coordinates for the logo based on the specified corner and margin.

    Args:
        cover_size (tuple[int, int]): The (width, height) of the cover image.
        logo_size (tuple[int, int]): The (width, height) of the logo image.
        corner (str): The corner of the cover image to place the logo ('bottom_right', 'bottom_left', 'top_right', 'top_left').
        margin (int): The margin in pixels between the logo and the edge of the cover image.

    Returns:
        A tuple (x, y) representing the coordinates for the logo placement.

    Raises:
        ValueError: If an unsupported corner is specified.
    """
    width_cover, height_cover = cover_size
    width_logo, height_logo = logo_size
    if corner == "bottom_right":
        return width_cover - width_logo - margin, height_cover - height_logo - margin
    elif corner == "bottom_left":
        return margin, height_cover - height_logo - margin
    elif corner == "top_right":
        return width_cover - width_logo - margin, margin
    elif corner == "top_left":
        return margin, margin
    else:
        raise ValueError(f"Unsupported corner: {corner}")


def _save_image_to_bytes(image: Image.Image) -> bytes:
    """Converts a PIL Image object to PNG bytes.

    This function saves the provided image in PNG format and returns the image data as bytes.

    Args:
        image: The PIL Image object to convert.

    Returns:
        PNG image data as bytes.
    """
    out = BytesIO()
    image.save(out, format="PNG")
    out.seek(0)
    return out.read()


def _get_cover_path(filename: str) -> Path:
    """
    Constructs the file path for a cover image based on the provided filename.

    This function returns the absolute path to the cover image within the static/cover directory.

    Args:
        filename: The name of the cover image file.

    Returns:
        A Path object representing the cover image file location.
    """
    return current_app.config["COVER_DIR"] / Path(filename).name


def _validate_cover_path(cover_path: Path) -> None:
    """
    Checks if the cover image file exists at the specified path.

    This function aborts the request with a 404 error if the cover image file does not exist.

    Args:
        cover_path: The path to the cover image file.

    Raises:
        Aborts with a 404 error if the file is not found.
    """
    if not cover_path.is_file():
        abort(404, description="Cover image not found")


def _get_query_params():
    """
    Extracts and returns logo overlay parameters from the request query string.

    This function reads the scale, corner, and margin parameters from the request query string,
    providing sensible defaults if they are not specified.

    Returns:
        A tuple containing (logo_scale, corner, margin).

    Raises:
        Aborts with a 400 error if query parameters are invalid.
    """
    try:
        logo_scale = float(request.args.get("scale", 0.15))
        corner = request.args.get("corner", "bottom_right")
        margin = int(request.args.get("margin", 10))
    except ValueError:
        abort(400, description="Invalid query parameters")
    return logo_scale, corner, margin


def _validate_query_params(logo_scale: float, corner: str, margin: int) -> None:
    """
    Validates the logo overlay query parameters for scale, corner, and margin.

    This function aborts the request with a 400 error if any parameter is invalid.

    Args:
        logo_scale: The scale of the logo relative to the cover image.
        corner: The corner of the cover image to place the logo.
        margin: The margin in pixels between the logo and the edge of the cover image.

    Raises:
        Aborts with a 400 error if any parameter is invalid.
    """
    if logo_scale <= 0:
        abort(400, description="Scale must be positive")
    if margin < 0:
        abort(400, description="Margin must be non-negative")
    allowed_corners = {"bottom_right", "bottom_left", "top_right", "top_left"}
    if corner not in allowed_corners:
        abort(400, description=f"Corner must be one of {', '.join(allowed_corners)}")
