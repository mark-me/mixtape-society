import mimetypes
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    render_template,
    request,
    send_file,
    send_from_directory,
)

from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager
from audio_cache import AudioCache, QualityLevel


def create_play_blueprint(mixtape_manager: MixtapeManager, path_audio_cache: Path, logger: Logger | None = None) -> Blueprint:
    """
    Creates and configures the Flask blueprint for mixtape playback and audio streaming.

    Sets up routes for streaming audio files with optional transcoding/caching,
    handling HTTP range requests, and rendering public mixtape playback pages.

    Args:
        mixtape_manager (MixtapeManager): The manager instance for retrieving mixtape data.
        logger (Logger): The logger instance for error reporting.

    Returns:
        Blueprint: The configured Flask blueprint for playback and streaming.
    """
    play = Blueprint("play", __name__)

    logger: Logger = logger or NullLogger()

    mimetypes.add_type("audio/flac", ".flac")
    mimetypes.add_type("audio/mp4", ".m4a")
    mimetypes.add_type("audio/aac", ".aac")
    mimetypes.add_type("audio/ogg", ".ogg")

    # Initialize audio cache
    cache_dir = path_audio_cache
    audio_cache = AudioCache(cache_dir, logger)

    @play.route("/<path:file_path>")
    def stream_audio(file_path: str) -> Response:
        """
        Streams an audio file from the music directory to the client.

        Supports optional quality parameter for transcoded versions. Validates the file path,
        determines the correct MIME type, and supports HTTP range requests for seeking.

        Query Parameters:
            quality: Quality level - "high" (256k), "medium" (192k), "low" (128k), or "original"

        Args:
            file_path: The relative path to the audio file within the music directory.

        Returns:
            Response: The Flask response object streaming the audio file or an error response.
        """
        original_path = _resolve_and_validate_path(file_path)

        # Get quality preference from query parameter
        quality: QualityLevel = request.args.get("quality", "medium")
        if quality not in ["high", "medium", "low", "original"]:
            quality = "medium"

        # Determine which file to serve (cached or original)
        serve_path = _get_serving_path(original_path, quality, audio_cache, logger)

        mime_type = _guess_mime_type(serve_path)
        file_size = serve_path.stat().st_size

        if range_header := request.headers.get("Range"):
            return _handle_range_request(serve_path, mime_type, range_header, file_size)

        # Full file request
        response = send_file(serve_path, mimetype=mime_type, download_name=serve_path.name)
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    def _get_serving_path(
        original_path: Path,
        quality: QualityLevel,
        cache: AudioCache,
        log: Logger
    ) -> Path:
        """
        Determine which file path to serve based on quality and cache availability.

        Args:
            original_path: Path to the original audio file.
            quality: Requested quality level.
            cache: AudioCache instance.
            log: Logger instance.

        Returns:
            Path to the file that should be served.
        """
        # If original quality or format doesn't need transcoding, serve original
        if quality == "original" or not cache.should_transcode(original_path):
            return original_path

        # Check if cached version exists
        if cache.is_cached(original_path, quality):
            cached_path = cache.get_cache_path(original_path, quality)
            log.debug(f"Serving cached {quality} version: {cached_path.name}")
            return cached_path

        # Cache doesn't exist - we have options:
        # Option 1: Serve original (fast, but bandwidth-heavy)
        # Option 2: Transcode on-the-fly (slower first load, but saves bandwidth)

        # Default behavior: serve original and log that cache should be generated
        log.warning(
            f"Cache miss for {original_path.name} at {quality} quality. "
            f"Consider pre-caching this file."
        )

        # Optional: Uncomment to transcode on-demand (will cause delay on first play)
        # try:
        #     return cache.transcode_file(original_path, quality)
        # except Exception as e:
        #     log.error(f"On-demand transcoding failed: {e}")
        #     return original_path

        return original_path

    def _resolve_and_validate_path(file_path: str) -> Path:
        """
        Resolves and validates the requested file path within the music directory.

        Ensures the file is within the allowed music root and exists as a file.

        Args:
            file_path: The relative path to the audio file within the music directory.

        Returns:
            Path: The resolved and validated Path object for the requested file.

        Raises:
            403: If the file is outside the music root directory.
            404: If the file does not exist.
        """
        path_music = Path(current_app.config["MUSIC_ROOT"]).resolve()
        full_path = (path_music / file_path).resolve()
        try:
            full_path.relative_to(path_music)
        except ValueError:
            abort(403)
        if not full_path.is_file():
            abort(404)
        return full_path

    def _guess_mime_type(full_path: Path) -> str:
        """
        Determines the MIME type for a given file path.

        Args:
            full_path: The Path object representing the file.

        Returns:
            str: The MIME type string for the file.
        """
        mime_type, _ = mimetypes.guess_type(str(full_path))
        if mime_type is None:
            suffix = full_path.suffix.lower()
            mime_type = {
                ".flac": "audio/flac",
                ".m4a": "audio/mp4",
                ".aac": "audio/aac",
                ".ogg": "audio/ogg",
                ".mp3": "audio/mpeg",
            }.get(suffix, "application/octet-stream")
        return mime_type

    def _handle_range_request(
        full_path: Path, mime_type: str, range_header: str, file_size: int
    ) -> Response:
        """
        Handle HTTP range requests for audio seeking.

        Args:
            full_path: Path to the audio file.
            mime_type: MIME type of the file.
            range_header: The Range header value from the request.
            file_size: Total size of the file in bytes.

        Returns:
            Response with partial content (206) or error response.
        """
        try:
            range_match = range_header.replace("bytes=", "")
            byte1_str, byte2_str = (range_match.split("-") + [""])[:2]
            byte1 = int(byte1_str) if byte1_str else 0
            byte2 = int(byte2_str) if byte2_str else file_size - 1

            if byte1 >= file_size or byte2 >= file_size or byte1 < 0 or byte2 < byte1:
                return Response("Range Not Satisfiable", 416)

            length = byte2 - byte1 + 1

            with open(full_path, "rb") as f:
                f.seek(byte1)
                data = f.read(length)

            rv = Response(data, 206, mimetype=mime_type, direct_passthrough=True)
            rv.headers.update(
                {
                    "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",
                }
            )
            return rv
        except (ValueError, OSError):
            abort(500)

    @play.route("/share/<slug>")
    def public_play(slug: str) -> Response:
        """
        Renders the public mixtape playback page for a given slug.

        Retrieves the mixtape by slug and displays it for public playback,
        or returns a 404 error if not found.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: The Flask response object containing the rendered mixtape playback page.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)
        return render_template("play_mixtape.html", mixtape=mixtape, public=True)

    @play.route("/covers/<filename>")
    def serve_cover(filename: str) -> Response:
        """
        Serves a cover image file from the covers directory.

        Args:
            filename: The name of the cover image file to serve.

        Returns:
            Response: The Flask response object containing the requested file.
        """
        return send_from_directory(current_app.config["COVER_DIR"], filename)

    # Admin/utility endpoints for cache management

    @play.route("/admin/cache/stats")
    def cache_stats() -> dict:
        """
        Get statistics about the audio cache.

        Returns:
            JSON with cache size and file count.
        """
        cache_size = audio_cache.get_cache_size()
        file_count = len(list(audio_cache.cache_dir.rglob("*.mp3")))

        return {
            "cache_size_bytes": cache_size,
            "cache_size_mb": round(cache_size / (1024 * 1024), 2),
            "cached_files": file_count,
        }

    @play.route("/admin/cache/clear", methods=["POST"])
    def clear_cache() -> dict:
        """
        Clear the audio cache.

        Query Parameters:
            older_than_days: Optional, only delete files older than this many days.

        Returns:
            JSON with number of deleted files.
        """
        older_than = request.args.get("older_than_days", type=int)
        deleted = audio_cache.clear_cache(older_than_days=older_than)

        return {
            "deleted_files": deleted,
            "message": f"Cleared {deleted} cached files",
        }

    return play
