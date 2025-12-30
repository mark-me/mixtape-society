import shutil
import threading
from base64 import b64decode
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    stream_with_context,
)
from PIL import Image

from audio_cache import (
    ProgressCallback,
    ProgressStatus,
    get_progress_tracker,
    schedule_mixtape_caching,
)
from auth import require_auth
from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager
from musiclib import MusicCollectionUI


def create_editor_blueprint(
    collection: MusicCollectionUI, logger: Logger | None = None
) -> Blueprint:
    """
    Creates and configures the Flask blueprint for the mixtape editor.

    Sets up routes for creating, editing, searching, and saving mixtapes, and provides helper functions for cover image and JSON handling.

    Args:
        collection (MusicCollection): The music collection instance to use for searching.
        logger (Logger): The logger instance for error reporting.

    Returns:
        Blueprint: The configured Flask blueprint for the editor.
    """
    editor = Blueprint("editor", __name__)

    logger: Logger = logger or NullLogger()

    @editor.route("/")
    @require_auth
    def new_mixtape() -> str:
        """
        Render de pagina voor het aanmaken van een nieuwe mixtape.

        Geeft het HTML-template terug voor het aanmaken van een nieuwe mixtape.

        Returns:
            str: De gerenderde HTML-pagina voor het aanmaken van een nieuwe mixtape.
        """
        empty_mixtape = {
            "title": "",
            "cover": None,
            "liner_notes": "",
            "tracks": [],
            "slug": None,
            "created_at": None,
            "updated_at": None,
        }
        return render_template("editor.html", preload_mixtape=empty_mixtape)

    @editor.route("/<slug>")
    @require_auth
    def edit_mixtape(slug: str) -> str:
        """
        Loads and renders the page for editing an existing mixtape.

        Retrieves the mixtape data from a JSON file and returns the HTML template with the mixtape preloaded.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            str: The rendered HTML page for editing the mixtape.
        """
        mixtape_manager = MixtapeManager(
            path_mixtapes=current_app.config["MIXTAPE_DIR"]
        )
        mixtape = mixtape_manager.get(slug)
        return render_template(
            "editor.html", preload_mixtape=mixtape, editing_slug=slug
        )

    @editor.route("/search")
    @require_auth
    def search() -> object:
        """
        Searches the music collection and returns the results.

        Receives a search query, searches the collection, and returns the results as JSON.

        Returns:
            Response: A JSON response containing the search results.
        """
        query = request.args.get("q", "").strip()
        if len(query) < 3:
            return jsonify([])
        results = collection.search_highlighting(query, limit=50)
        return jsonify(results)

    @editor.route("/artist_details")
    @require_auth
    def artist_details() -> Response:
        """
        Retrieves and returns detailed information about an artist in JSON format.

        Fetches artist details from the music collection using the artist name from the request arguments and returns them as a JSON response.
        Handles missing artist errors and returns an error response if necessary.

        Returns:
            Response: A JSON response containing the artist's details or an error message.
        """
        artist = request.args.get("artist", "").strip()
        if not artist:
            return jsonify({"error": "Missing artist"}), 400
        details = collection.get_artist_details(artist)
        return jsonify(details)

    @editor.route("/album_details")
    @require_auth
    def album_details() -> Response:
        """
        Retrieves and returns detailed information about an album in JSON format.

        Fetches album details from the music collection using the release directory from the request arguments and returns them as a JSON response.
        Handles missing release directory errors and returns an error response if necessary.

        Returns:
            Response: A JSON response containing the album's details or an error message.
        """
        release_dir = request.args.get("release_dir", "").strip()
        if not release_dir:
            return jsonify({"error": "Missing release_dir"}), 400
        details = collection.get_album_details(release_dir)
        return jsonify(details)

    @editor.route("/save", methods=["POST"])
    @require_auth
    def save_mixtape() -> object:
        """
        Saves a new or edited mixtape based on the provided data.

        Handles both creation of new mixtapes and updates to existing ones, including cover image processing and validation.
        Returns a JSON response indicating success or failure.

        Returns:
            Response: A JSON response with the result of the save operation.
        """
        try:
            data = request.get_json()
            if not data or not data.get("tracks"):
                return jsonify({"error": "Empty mixtape"}), 400

            title = data.get("title", "").strip() or "Unnamed Mixtape"
            liner_notes = data.get("liner_notes", "")
            slug = data.get("slug")  # Present only when editing

            # Prepare clean data for the manager
            mixtape_data = {
                "title": title,
                "tracks": data.get("tracks", []),
                "liner_notes": liner_notes,
                "cover": data.get("cover"),
            }

            # Instantiate the manager
            mixtape_manager = MixtapeManager(
                path_mixtapes=current_app.config["MIXTAPE_DIR"], logger=logger
            )

            if slug:
                # Editing
                existing = mixtape_manager.get(slug)
                if not existing:
                    return jsonify({"error": "Mixtape not found"}), 404

                mixtape_data.setdefault("created_at", existing.get("created_at"))
                if mixtape_data["cover"] is None:  # Preserve old cover if no new one
                    mixtape_data["cover"] = existing.get("cover")

                final_slug = mixtape_manager.update(slug, mixtape_data)
            else:
                # Creating
                mixtape_data["created_at"] = datetime.now().isoformat()
                final_slug = mixtape_manager.save(mixtape_data)

            # Trigger background audio caching in a separate thread
            if current_app.config.get("AUDIO_CACHE_PRECACHE_ON_UPLOAD", False):
                # Copy app reference and context for the thread
                app = current_app._get_current_object()

                def run_with_context():
                    with app.app_context():
                        _trigger_audio_caching_async(final_slug, mixtape_manager, bool(slug))

                threading.Thread(
                    target=run_with_context,
                    daemon=True
                ).start()

            return jsonify(
                {
                    "success": True,
                    "title": title,
                    "slug": final_slug,
                    "client_id": mixtape_data.get("client_id"),
                    "url": f"/editor/{final_slug}",
                }
            )
        except Exception as e:
            logger.exception(f"Error saving mixtape: {e}")
            return jsonify({"error": "Server error"}), 500

    @editor.route("/progress/<slug>")
    @require_auth
    def progress_stream(slug: str) -> Response:
        """
        Server-Sent Events endpoint for real-time progress updates.

        Streams progress events during mixtape caching operations.

        Args:
            slug: The mixtape slug to track progress for

        Returns:
            Response: SSE stream of progress events
        """
        tracker = get_progress_tracker(logger)

        def generate():
            try:
                yield from tracker.listen(slug, timeout=300)
            except Exception as e:
                logger.error(f"Progress stream error for {slug}: {e}")
                yield f"data: {{'error': '{str(e)}'}}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Disable nginx buffering
            }
        )

    def _trigger_audio_caching_async(
        slug: str, mixtape_manager: MixtapeManager, is_update: bool = False
    ) -> None:
        """
        Triggers background audio caching with progress tracking.

        This runs in a separate thread to avoid blocking the save response.

        Args:
            slug: The unique identifier for the mixtape.
            mixtape_manager: The MixtapeManager instance to retrieve mixtape data.
            is_update: Whether this is an update to an existing mixtape.
        """
        tracker = get_progress_tracker(logger)

        try:
            # Emit initial event
            tracker.emit(
                task_id=slug,
                step="initializing",
                status=ProgressStatus.IN_PROGRESS,
                message="Starting cache process...",
                current=0,
                total=1
            )

            # Check if audio_cache is available
            if not hasattr(current_app, "audio_cache"):
                tracker.emit(
                    task_id=slug,
                    step="error",
                    status=ProgressStatus.FAILED,
                    message="Audio cache not initialized",
                    current=0,
                    total=0
                )
                logger.warning("Audio cache not initialized, skipping pre-caching")
                return

            # Get the saved mixtape data
            saved_mixtape = mixtape_manager.get(slug)

            if not saved_mixtape or not saved_mixtape.get("tracks"):
                tracker.emit(
                    task_id=slug,
                    step="completed",
                    status=ProgressStatus.COMPLETED,
                    message="No tracks to cache",
                    current=1,
                    total=1
                )
                logger.debug(f"No tracks to cache for mixtape: {slug}")
                return

            tracks = saved_mixtape["tracks"]
            total_tracks = len(tracks)

            # Emit starting cache event
            tracker.emit(
                task_id=slug,
                step="analyzing",
                status=ProgressStatus.IN_PROGRESS,
                message=f"Analyzing {total_tracks} tracks...",
                current=0,
                total=total_tracks
            )

            # Get configuration
            qualities = current_app.config.get(
                "AUDIO_CACHE_PRECACHE_QUALITIES", ["medium"]
            )
            music_root = Path(current_app.config["MUSIC_ROOT"])

            logger.info(
                f"Starting pre-cache for mixtape '{slug}' "
                f"({'update' if is_update else 'new'}) with {total_tracks} tracks"
            )

            # Create progress callback
            progress_callback = ProgressCallback(slug, tracker, total_tracks)

            # Start caching
            results = schedule_mixtape_caching(
                mixtape_tracks=tracks,
                music_root=music_root,
                audio_cache=current_app.audio_cache,
                logger=logger,
                qualities=qualities,
                async_mode=True,
                progress_callback=progress_callback
            )

            # Analyze results
            total_files = len(results)

            if total_files == 0:
                # No results means something went wrong
                tracker.emit(
                    task_id=slug,
                    step="completed",
                    status=ProgressStatus.COMPLETED,
                    message="No files processed (empty results)",
                    current=total_tracks,
                    total=total_tracks
                )
                logger.warning(f"No results returned for mixtape '{slug}'")
                return

            # Count successful operations (cached or skipped)
            cached = sum(1 for r in results.values() if isinstance(r, dict) and any(k != "skipped" and k != "reason" for k in r.keys()))
            skipped = sum(1 for r in results.values() if isinstance(r, dict) and r.get("skipped"))
            failed = total_files - cached - skipped

            # Build completion message
            parts = []
            if cached > 0:
                parts.append(f"{cached} cached")
            if skipped > 0:
                parts.append(f"{skipped} skipped")
            if failed > 0:
                parts.append(f"{failed} failed")

            message = f"Complete! {', '.join(parts) if parts else 'No files processed'}"

            # Emit completion event
            tracker.emit(
                task_id=slug,
                step="completed",
                status=ProgressStatus.COMPLETED,
                message=message,
                current=total_files,
                total=total_files
            )

            logger.info(
                f"Pre-caching completed for '{slug}': "
                f"cached={cached}, skipped={skipped}, failed={failed}"
            )

        except Exception as e:
            # Emit error event
            tracker.emit(
                task_id=slug,
                step="error",
                status=ProgressStatus.FAILED,
                message=f"Caching failed: {str(e)}",
                current=0,
                total=0
            )
            logger.error(f"Pre-caching failed for mixtape '{slug}': {e}")
            logger.exception("Detailed error:")

    # TODO: Either remove or move to MixtapeManager
    def _process_cover(cover_data: str, slug: str) -> str | None:
        """
        Processes and saves a cover image from base64-encoded data.

        Decodes the image data, resizes the image, and saves it as a JPEG file in the covers directory.
        Returns the relative path to the saved cover image, or None if processing fails.

        Args:
            cover_data: The base64-encoded image data string.
            slug: The unique identifier for the mixtape.

        Returns:
            str | None: The relative path to the saved cover image, or None if processing fails.
        """
        if not cover_data or not cover_data.startswith("data:image"):
            return None
        try:
            _, b64data = cover_data.split(",", 1)
            image = Image.open(BytesIO(b64decode(b64data)))
            cover_path = current_app.config["COVER_DIR"] / f"{slug}.jpg"
            image = _cover_resize(image=image)
            image.save(cover_path, "JPEG", quality=100)
            return f"covers/{slug}.jpg"
        except Exception as e:
            logger.error(f"Cover opslaan mislukt voor {slug}: {e}")
            return None

    # TODO: Either remove or move to MixtapeManager
    def _cover_resize(image: Image, new_width: int = 1200) -> Image:
        """
        Resizes the given image to a specified width while maintaining aspect ratio.

        Calculates the new height to preserve the image's proportions and resizes using high-quality Lanczos filtering.

        Args:
            image: The PIL Image object to resize.
            new_width: The desired width of the resized image (default is 1200).

        Returns:
            Image: The resized PIL Image object.
        """
        width, height = image.size
        new_height = int(height * (new_width / width)) if width > new_width else height
        image = image.resize((new_width, new_height), Image.LANCZOS)
        return image

    # TODO: Either remove or move to MixtapeManager
    def _get_default_cover(track_path: str, slug: str) -> str | None:
        """
        Attempts to find and copy a default cover image from the track's album directory.

        Searches for common cover image filenames and copies the first found image to the covers directory. Returns the relative path to the copied image, or None if no cover is found.

        Args:
            track_path: The path to the track file.
            slug: The unique identifier for the mixtape.

        Returns:
            str | None: The relative path to the copied cover image, or None if no cover is found.
        """
        music_root = Path(current_app.config["MUSIC_ROOT"]).resolve()
        full_track_path = music_root / track_path
        album_dir = full_track_path.parent
        possible = [
            "cover.jpg",
            "folder.jpg",
            "album.jpg",
            "front.jpg",
        ]
        for file in album_dir.iterdir():
            if file.is_file() and file.name.lower() in possible:
                dest = current_app.config["COVER_DIR"] / f"{slug}.jpg"
                shutil.copy(file, dest)
                return f"covers/{slug}.jpg"
        for name in possible:
            src = album_dir / name
            if src.exists():
                dest = current_app.config["COVER_DIR"] / f"{slug}.jpg"
                shutil.copy(src, dest)
                return f"covers/{slug}.jpg"
        return None

    return editor
