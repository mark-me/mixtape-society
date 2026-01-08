from pathlib import Path

from flask import Blueprint, Response, abort, current_app, request, url_for

from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager
from qr_generator import generate_mixtape_qr, generate_mixtape_qr_with_cover


def create_qr_blueprint(
    mixtape_manager: MixtapeManager, logger: Logger | None = None
) -> Blueprint:
    """
    Creates Flask blueprint for QR code generation.

    Args:
        mixtape_manager: MixtapeManager instance for retrieving mixtape data
        logger: Logger instance for error reporting

    Returns:
        Blueprint: Configured Flask blueprint for QR endpoints
    """
    qr = Blueprint("qr", __name__)
    logger: Logger = logger or NullLogger()

    @qr.route("/qr/<slug>.png")
    def generate_qr(slug: str) -> Response:
        """
        Generate a simple QR code PNG for a mixtape share URL.

        Query parameters:
            size: QR code size in pixels (default 400, max 800)
            logo: Include logo in center (default true)

        Args:
            slug: The mixtape slug identifier

        Returns:
            Response: PNG image of the QR code
        """
        # Verify mixtape exists
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404, description="Mixtape not found")

        # Get parameters
        size = min(int(request.args.get("size", 400)), 800)
        include_logo = request.args.get("logo", "true").lower() != "false"

        # Build the full share URL
        from flask import url_for

        share_url = url_for("play.public_play", slug=slug, _external=True)

        # Generate QR code
        try:
            # Get logo path if requested
            logo_path = None
            if include_logo:
                logo_path = Path(current_app.static_folder) / "logo.svg"
                if not logo_path.exists():
                    logo_path = Path(current_app.static_folder) / "logo.png"
                    if not logo_path.exists():
                        logo_path = None

            qr_bytes = generate_mixtape_qr(
                url=share_url,
                title=mixtape.get("title", "Mixtape"),
                logo_path=logo_path,
                size=size,
            )

            response = Response(qr_bytes, mimetype="image/png")
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["Content-Disposition"] = (
                f'inline; filename="{slug}-qr.png"'
            )

            return response

        except ImportError as e:
            logger.error(f"QR code generation failed - library not installed: {e}")
            abort(
                500,
                description="QR code generation not available. Install qrcode library.",
            )
        except Exception as e:
            logger.exception(f"QR code generation failed: {e}")
            abort(500, description="Failed to generate QR code")

    @qr.route("/qr/<slug>/download")
    def download_qr(slug: str) -> Response:
        """
        Download enhanced QR code with cover art and title.

        Query parameters:
            size: QR code size in pixels (default 800, max 1200)
            include_cover: Include mixtape cover art (default true)
            include_title: Include mixtape title banner (default true)

        Args:
            slug: The mixtape slug identifier

        Returns:
            Response: PNG image as downloadable attachment
        """
        # Verify mixtape exists
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404, description="Mixtape not found")

        # Get parameters
        qr_size = min(int(request.args.get("size", 800)), 1200)
        include_cover = request.args.get("include_cover", "true").lower() != "false"
        include_title = request.args.get("include_title", "true").lower() != "false"

        share_url = url_for("play.public_play", slug=slug, _external=True)

        try:
            # Get logo path
            logo_path = Path(current_app.static_folder) / "logo.svg"
            if not logo_path.exists():
                logo_path = Path(current_app.static_folder) / "logo.png"
                if not logo_path.exists():
                    logo_path = None

            # Get cover path if requested
            cover_path = None
            if include_cover and mixtape.get("cover"):
                cover_filename = mixtape["cover"].split("/")[-1]
                cover_path = Path(current_app.config["COVER_DIR"]) / cover_filename
                if not cover_path.exists():
                    cover_path = None

            # Generate enhanced QR code
            qr_bytes = generate_mixtape_qr_with_cover(
                url=share_url,
                title=mixtape.get("title", "Mixtape"),
                cover_path=cover_path,
                logo_path=logo_path,
                qr_size=qr_size,
                include_title=include_title,
            )

            # Sanitize title for filename
            title = mixtape.get("title", "mixtape")
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
            filename = f"{safe_title}-qr-code.png"

            response = Response(qr_bytes, mimetype="image/png")
            response.headers["Content-Disposition"] = (
                f'attachment; filename="{filename}"'
            )

            return response

        except ImportError as e:
            logger.error(f"QR code generation failed - library not installed: {e}")
            abort(
                500,
                description="QR code generation not available. Install qrcode library.",
            )
        except Exception as e:
            logger.exception(f"QR code download failed: {e}")
            abort(500, description="Failed to generate QR code")

    return qr
