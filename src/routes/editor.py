import threading
import time
from datetime import datetime

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
from utils import CoverCompositor


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
            path_mixtapes=current_app.config["MIXTAPE_DIR"], collection=collection
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
        Includes comprehensive error handling to ensure JSON is always returned.

        Returns:
            Response: A JSON response containing the search results or error information.
        """
        try:
            query = request.args.get("q", "").strip()
            if len(query) < 3:
                return jsonify([])
            
            # Log the search query for debugging
            logger.debug(f"Search query: {query}")
            
            results = collection.search_highlighting(query, limit=50)
            return jsonify(results)
            
        except Exception as e:
            # Log the full error with traceback
            logger.error(f"Search error for query '{query}': {e}", exc_info=True)
            
            # Return a proper JSON error response
            return jsonify({
                "error": "Search failed",
                "message": str(e),
                "query": query
            }), 500

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

            # Adding track covers
            tracks = data.get("tracks", [])
            for track in tracks:
                release_dir = collection._get_release_dir(
                    track.get("path", "")
                )  # Reuse existing helper
                track["cover"] = collection.get_cover(release_dir)

            # Prepare clean data for the manager
            mixtape_data = {
                "title": title,
                "tracks": tracks,
                "liner_notes": liner_notes,
                "cover": data.get("cover"),
            }

            # Instantiate the manager
            mixtape_manager = MixtapeManager(
                path_mixtapes=current_app.config["MIXTAPE_DIR"],
                collection=collection,
                logger=logger,
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
                        _trigger_audio_caching_async(
                            final_slug, mixtape_manager, bool(slug)
                        )

                threading.Thread(target=run_with_context, daemon=True).start()

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
            logger.error(f"Mixtape save error: {e}")
            return jsonify({"error": str(e)}), 500

    @editor.route("/progress/<slug>")
    @require_auth
    def progress(slug: str) -> Response:
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
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
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
                total=1,
            )

            # Check if audio_cache is available
            if not hasattr(current_app, "audio_cache"):
                tracker.emit(
                    task_id=slug,
                    step="error",
                    status=ProgressStatus.FAILED,
                    message="Audio cache not initialized",
                    current=0,
                    total=0,
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
                    total=1,
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
                total=total_tracks,
            )

            # Get configuration
            qualities = current_app.config.get(
                "AUDIO_CACHE_PRECACHE_QUALITIES", ["medium"]
            )
            music_root = Path(current_app.config["MUSIC_ROOT"])

            logger.debug(
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
                progress_callback=progress_callback,
            )

            # Small delay to ensure all progress events are queued
            time.sleep(0.2)

            # Analyze results
            total_files = len(results)

            logger.debug(f"Processing completed: {total_files} results returned")

            if total_files == 0:
                # No results means something went wrong
                tracker.emit(
                    task_id=slug,
                    step="completed",
                    status=ProgressStatus.COMPLETED,
                    message="No files processed (empty results)",
                    current=total_tracks,
                    total=total_tracks,
                )
                logger.warning(f"No results returned for mixtape '{slug}'")
                return

            # Count successful operations (cached or skipped)
            cached = sum(
                isinstance(r, dict)
                and any(k not in ["skipped", "reason"] for k in r.keys())
                for r in results.values()
            )
            skipped = sum(
                bool(isinstance(r, dict) and r.get("skipped")) for r in results.values()
            )
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
                total=total_files,
            )

            # Small delay to ensure completion event is queued
            time.sleep(0.1)

            logger.debug(
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
                total=0,
            )
            logger.error(f"Pre-caching failed for mixtape '{slug}': {e}")
            logger.exception("Detailed error:")

    @editor.route("/generate_composite", methods=["POST"])
    @require_auth
    def generate_composite() -> Response:
        """
        Generates a composite cover image from a list of individual cover images.

        Accepts a JSON payload containing cover identifiers, composes them into a grid image, and returns the result as a data URL.
        Validates the input list and returns JSON error responses for invalid requests or generation failures.

        Returns:
            Response: A JSON response containing the composite image data URL or an error message.
        """
        data = request.get_json()
        if not data or not isinstance(data.get("covers"), list):
            return jsonify({"error": "Missing covers list"}), 400

        covers = data["covers"]
        if not covers:
            return jsonify({"error": "No covers provided"}), 400

        try:
            compositor = CoverCompositor(collection.covers_dir)
            data_url = compositor.generate_grid_composite(covers)
            return jsonify({"data_url": data_url})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Composite generation failed: {e}")
            return jsonify({"error": "Failed to generate composite"}), 500

    return editor
