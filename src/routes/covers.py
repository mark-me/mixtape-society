from pathlib import Path
from urllib.parse import unquote

from flask import Blueprint, abort, jsonify, request, send_from_directory

from common.logging import Logger, NullLogger
from musiclib import MusicCollectionUI

VALID_SIZES = ["96x96", "128x128", "192x192", "256x256", "384x384", "512x512"]


def create_covers_blueprint(
    collection: MusicCollectionUI,
    data_root: Path,
    logger: Logger | None = None,
) -> Blueprint:
    """
    Creates the Flask blueprint for serving cached album cover images.

    Distinct from the `og` blueprint (routes/logo_on_cover.py), which composites
    a logo onto a cover for social-share images — this blueprint only serves
    the plain cached covers, at their original size or a generated variant.

    Args:
        collection: The shared MusicCollectionUI instance covers are read from.
        data_root: Root directory under which the cover cache lives.
        logger: Optional logger for logging cover-serving events. Uses NullLogger if not provided.

    Returns:
        Blueprint: The configured Flask blueprint for cover routes.
    """
    covers = Blueprint("covers", __name__)
    logger: Logger = logger or NullLogger()
    covers_dir = data_root / "cache" / "covers"

    @covers.route("/covers/<filename>")
    def serve_album_cover(filename):
        """
        Serves extracted album cover images from the cached covers directory.
        Includes explicit CORS and caching headers for car system compatibility.
        """
        # Security: restrict to .jpg (or .jpeg/.png if you extend extraction)
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            abort(404)

        response = send_from_directory(covers_dir, filename)

        # Add explicit headers for car systems (Android Auto, CarPlay, etc.)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "3600"
        response.headers["Cache-Control"] = "public, max-age=86400"  # Cache for 24 hours
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        return response

    @covers.route("/api/covers/<path:release_dir_encoded>")
    def serve_cover_by_size(release_dir_encoded):
        """
        Serves cover art with optional size parameter for Android Auto and responsive clients.
        Supports ?size=WxH query parameter (e.g., ?size=256x256).
        Generates size variants on-demand and caches them for future requests.

        Args:
            release_dir_encoded: URL-encoded release directory path

        Query Parameters:
            size: Optional size in format WxH (e.g., 256x256).
                  Supported sizes: 96x96, 128x128, 192x192, 256x256, 384x384, 512x512

        Returns:
            Image file from cache directory
        """
        release_dir = unquote(release_dir_encoded)
        requested_size = request.args.get("size", "").lower()

        if not requested_size:
            # No size specified, return main cover (existing behavior)
            cover_path = collection.get_or_create_cover(release_dir)
            if cover_path:
                return send_from_directory(covers_dir, cover_path.name)
            abort(404)

        if requested_size not in VALID_SIZES:
            return jsonify({"error": "Invalid size parameter", "valid_sizes": VALID_SIZES}), 400

        cover_path = collection.get_or_create_cover(release_dir, size=requested_size)
        if cover_path:
            return send_from_directory(covers_dir, cover_path.name)

        # Final fallback
        return send_from_directory(covers_dir, "_fallback.jpg")

    return covers
