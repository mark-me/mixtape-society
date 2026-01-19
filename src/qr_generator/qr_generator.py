"""Enhanced QR Code generation with mixtape cover art and title."""

import io
from pathlib import Path

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask

    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

from PIL import Image, ImageDraw, ImageFont


def generate_mixtape_qr_with_cover(
    url: str,
    title: str,
    cover_path: Path | None = None,
    logo_path: Path | None = None,
    qr_size: int = 400,
    include_title: bool = True,
) -> bytes:
    """
    Generate a branded QR code with mixtape cover art and title.

    Creates a composite image with:
    - Mixtape cover art at the top
    - Title banner below cover
    - QR code at the bottom
    - Optional logo in QR center

    Args:
        url: The full URL to encode in the QR code
        title: The mixtape title to display
        cover_path: Path to mixtape cover image
        logo_path: Optional path to logo for QR center
        qr_size: Size of the QR code portion (default 400)
        include_title: Whether to include title banner (default True)

    Returns:
        bytes: PNG image data of the complete branded QR code

    Raises:
        ImportError: If qrcode library is not installed
    """
    if not QR_AVAILABLE:
        raise ImportError(
            "qrcode library not installed. Install with: uv add qrcode pillow"
        )

    # Generate base QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )

    qr.add_data(url)
    qr.make(fit=True)

    # Create styled QR code
    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(30, 58, 95),  # Navy blue
        ),
    )

    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    # Add logo to QR center if provided
    if logo_path and logo_path.exists():
        qr_img = _add_logo_to_qr(qr_img, logo_path)

    # Create composite image with cover and title
    composite = _create_composite_image(
        qr_img=qr_img, title=title, cover_path=cover_path, include_title=include_title
    )

    # Convert to bytes
    buffer = io.BytesIO()
    composite.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return buffer.getvalue()


def _create_composite_image(
    qr_img: Image.Image,
    title: str,
    cover_path: Path | None = None,
    include_title: bool = True,
) -> Image.Image:
    """
    Create composite image with cover, title, and QR code.

    Layout:
    ┌─────────────┐
    │   Cover     │ (square, same width as QR)
    ├─────────────┤
    │   Title     │ (banner with padding)
    ├─────────────┤
    │   QR Code   │
    └─────────────┘
    """
    qr_width, qr_height = qr_img.size

    # Dimensions
    cover_size = qr_width
    title_height = 80 if include_title else 0
    padding = 20

    # Calculate total height
    total_height = 0
    if cover_path and cover_path.exists():
        total_height += cover_size
    if include_title:
        total_height += title_height
    total_height += qr_height
    total_height += padding * 2  # Top and bottom padding

    # Create white background
    composite = Image.new("RGB", (qr_width, total_height), "white")
    draw = ImageDraw.Draw(composite)

    current_y = padding

    # Add cover art if available
    if cover_path and cover_path.exists():
        try:
            cover = Image.open(cover_path)
            cover = cover.convert("RGB")

            # Resize cover to match QR width (square)
            cover = _resize_cover(cover, cover_size)

            # Add subtle shadow effect
            composite.paste(cover, (0, current_y))
            current_y += cover_size

        except Exception as e:
            print(f"Failed to load cover: {e}")

    # Add title banner
    if include_title:
        # Background for title
        title_bg_color = (30, 58, 95)  # Navy blue
        draw.rectangle(
            [(0, current_y), (qr_width, current_y + title_height)], fill=title_bg_color
        )

        # Draw title text
        _draw_title_text(draw, title, qr_width, current_y, title_height)
        current_y += title_height

    # Add QR code at bottom
    composite.paste(qr_img, (0, current_y))

    return composite


def _resize_cover(cover: Image.Image, target_size: int) -> Image.Image:
    """Resize and crop cover to square format."""
    width, height = cover.size

    # Crop to square (center crop)
    if width != height:
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        cover = cover.crop((left, top, left + size, top + size))

    # Resize to target size
    cover = cover.resize((target_size, target_size), Image.Resampling.LANCZOS)

    return cover


def _draw_title_text(
    draw: ImageDraw.Draw, title: str, width: int, y_offset: int, height: int
):
    """Draw mixtape title centered in the banner."""
    # Try to use a nice font, fall back to default
    font_size = 32
    try:
        # Try common system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]

        font = None
        for font_path in font_paths:
            if Path(font_path).exists():
                font = ImageFont.truetype(font_path, font_size)
                break

        if font is None:
            # Last resort: use default font
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Truncate title if too long
    max_chars = 30
    display_title = title if len(title) <= max_chars else f"{title[: max_chars - 3]}..."

    # Get text bounding box
    bbox = draw.textbbox((0, 0), display_title, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center text
    x = (width - text_width) // 2
    y = y_offset + (height - text_height) // 2

    # Draw text with white color
    draw.text((x, y), display_title, fill="white", font=font)


def _add_logo_to_qr(qr_img: Image.Image, logo_path: Path) -> Image.Image:
    """Add a logo to the center of a QR code."""
    try:
        logo = Image.open(logo_path)

        # Calculate logo size (roughly 1/5 of QR size)
        qr_width, qr_height = qr_img.size
        logo_max_size = min(qr_width, qr_height) // 5

        # Resize logo maintaining aspect ratio
        logo.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)

        # Create white background circle for logo
        logo_bg_size = int(logo_max_size * 1.3)
        logo_bg = Image.new("RGB", (logo_bg_size, logo_bg_size), "white")

        # Create circular mask
        mask = Image.new("L", (logo_bg_size, logo_bg_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, logo_bg_size, logo_bg_size), fill=255)

        # Paste white circle onto QR
        logo_bg_pos = ((qr_width - logo_bg_size) // 2, (qr_height - logo_bg_size) // 2)
        qr_img.paste(logo_bg, logo_bg_pos, mask)

        # Paste logo onto white circle
        logo_pos = ((qr_width - logo.width) // 2, (qr_height - logo.height) // 2)

        # Convert logo to RGBA if needed
        if logo.mode != "RGBA":
            logo = logo.convert("RGBA")

        qr_img.paste(logo, logo_pos, logo)

    except Exception as e:
        print(f"Failed to add logo to QR code: {e}")

    return qr_img


def generate_mixtape_qr(
    url: str, title: str, logo_path: Path | None = None, size: int = 400
) -> bytes:
    """
    Generate a simple QR code (backward compatibility).

    This is the original function for basic QR generation.
    """
    if not QR_AVAILABLE:
        raise ImportError(
            "qrcode library not installed. Install with: uv add qrcode pillow"
        )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255), front_color=(30, 58, 95)
        ),
    )

    img = img.resize((size, size), Image.Resampling.LANCZOS)

    if logo_path and logo_path.exists():
        img = _add_logo_to_qr(img, logo_path)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return buffer.getvalue()
