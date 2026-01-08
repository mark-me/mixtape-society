"""QR Code generation utilities for mixtape sharing."""

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


def generate_mixtape_qr(
    url: str,
    title: str,
    logo_path: Path | None = None,
    size: int = 400
) -> bytes:
    """
    Generate a stylized QR code for a mixtape share URL.
    
    Args:
        url: The full URL to encode in the QR code
        title: The mixtape title (for branding)
        logo_path: Optional path to logo image to embed in QR center
        size: Size of the QR code in pixels (default 400)
    
    Returns:
        bytes: PNG image data of the generated QR code
    
    Raises:
        ImportError: If qrcode library is not installed
    """
    if not QR_AVAILABLE:
        raise ImportError(
            "qrcode library not installed. "
            "Install with: pip install qrcode[pil] --break-system-packages"
        )
    
    # Create QR code instance with optimal settings
    qr = qrcode.QRCode(
        version=1,  # Auto-adjust version
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for logo
        box_size=10,
        border=2,
    )
    
    qr.add_data(url)
    qr.make(fit=True)
    
    # Generate styled QR code with rounded modules
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(30, 58, 95)  # Navy blue from base.css album color
        )
    )
    
    # Resize to requested size
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Optionally add logo in center
    if logo_path and logo_path.exists():
        img = _add_logo_to_qr(img, logo_path)
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    
    return buffer.getvalue()


def _add_logo_to_qr(qr_img: Image.Image, logo_path: Path) -> Image.Image:
    """
    Add a logo to the center of a QR code.
    
    The logo is placed with a white border for better contrast.
    
    Args:
        qr_img: The QR code PIL Image
        logo_path: Path to the logo image file
    
    Returns:
        PIL Image with logo embedded
    """
    try:
        logo = Image.open(logo_path)
        
        # Calculate logo size (roughly 1/5 of QR size with white border)
        qr_width, qr_height = qr_img.size
        logo_max_size = min(qr_width, qr_height) // 5
        
        # Resize logo maintaining aspect ratio
        logo.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)
        
        # Create white background circle for logo
        logo_bg_size = int(logo_max_size * 1.3)
        logo_bg = Image.new('RGB', (logo_bg_size, logo_bg_size), 'white')
        
        # Create circular mask
        mask = Image.new('L', (logo_bg_size, logo_bg_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, logo_bg_size, logo_bg_size), fill=255)
        
        # Paste white circle onto QR
        logo_bg_pos = (
            (qr_width - logo_bg_size) // 2,
            (qr_height - logo_bg_size) // 2
        )
        qr_img.paste(logo_bg, logo_bg_pos, mask)
        
        # Paste logo onto white circle
        logo_pos = (
            (qr_width - logo.width) // 2,
            (qr_height - logo.height) // 2
        )
        
        # Convert logo to RGBA if needed
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        qr_img.paste(logo, logo_pos, logo)
        
    except Exception as e:
        # If logo fails, just return original QR
        print(f"Failed to add logo to QR code: {e}")
    
    return qr_img


def generate_simple_qr(url: str, size: int = 300) -> bytes:
    """
    Generate a simple black and white QR code.
    
    Fallback function for basic QR generation without styling.
    
    Args:
        url: The URL to encode
        size: Size in pixels (default 300)
    
    Returns:
        bytes: PNG image data
    
    Raises:
        ImportError: If qrcode library is not installed
    """
    if not QR_AVAILABLE:
        raise ImportError(
            "qrcode library not installed. "
            "Install with: pip install qrcode[pil] --break-system-packages"
        )
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer.getvalue()
