from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, send_from_directory
from flask_limiter import Limiter

from auth import require_auth
from common.logging import Logger, NullLogger
from musiclib import DatabaseCorruptionError, MusicCollectionUI, get_indexing_status


def create_system_blueprint(
    collection: MusicCollectionUI,
    data_root: Path,
    limiter: Limiter,
    logger: Logger | None = None,
) -> Blueprint:
    """
    Creates the Flask blueprint for app- and library-level housekeeping routes.

    Covers PWA support files, indexing/health status, and destructive
    library-maintenance actions (resync, reset). Kept separate from the
    mixtape/browsing/editing blueprints since these routes operate on the
    collection as a whole rather than on any single mixtape.

    Args:
        collection: The shared MusicCollectionUI instance to inspect and maintain.
        data_root: Root directory under which the database and its cache live.
        logger: Optional logger for logging system events. Uses NullLogger if not provided.

    Returns:
        Blueprint: The configured Flask blueprint for system routes.
    """
    system = Blueprint("system", __name__)
    logger: Logger = logger or NullLogger()
    db_path = data_root / "collection.db"

    @system.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(
            current_app.root_path,  # Serves from app root directory
            "service-worker.js",
            mimetype="application/javascript",
        )
        # Prevent caching so updates work
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        # Scope to /play/ only
        response.headers["Service-Worker-Allowed"] = "/play/"
        return response

    @system.route("/manifest.json")
    def manifest():
        """Serve PWA manifest"""
        return send_from_directory(
            current_app.root_path, "manifest.json", mimetype="application/manifest+json"
        )

    @system.route("/robots.txt")
    def robots_txt():
        """
        Serves a robots.txt file that disallows all web crawlers. This helps prevent search engines from indexing the site.

        Returns:
            Response: A plain text HTTP response containing the robots.txt directives.
        """
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    @system.route("/indexing-status")
    @limiter.exempt
    def indexing_status_json():
        """
        Returns the current indexing status as JSON.
        Used by the indexing page for AJAX polling.
        """
        status = get_indexing_status(data_root, logger=logger)
        if not status:
            # No indexing in progress - redirect to landing behavior
            return {"done": True}

        return {
            "done": False,
            "status": status.get("status"),
            "current": status.get("current", 0),
            "total": status.get("total", 0),
            "started_at": status.get("started_at"),  # ISO string
        }

    @system.route("/collection-stats")
    @require_auth
    def collection_stats_json():
        """
        Returns collection statistics as JSON.
        Used by the collection stats modal.
        """
        try:
            stats = collection.get_collection_stats()
            return jsonify(stats)
        except Exception as e:
            logger.exception(f"Error fetching collection stats: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @system.route("/resync", methods=["POST"])
    @require_auth
    def resync_library():
        """
        Triggers a resync of the music library.
        Only accessible to authenticated users.
        Returns JSON with success status or error message.
        """
        import threading

        try:
            status = get_indexing_status(data_root, logger=logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            def run_resync():
                try:
                    collection.resync()
                    logger.info("Music library resync completed successfully")
                except Exception as e:
                    logger.exception(f"Error during resync: {e}")

            threading.Thread(target=run_resync, daemon=True).start()

            logger.info("Music library resync initiated by user")
            return jsonify({"success": True})

        except Exception as e:
            logger.exception(f"Error initiating resync: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @system.route("/reset-database", methods=["POST"])
    @require_auth
    def reset_database():
        """
        Resets the music library database and triggers a rebuild in the background.
        Deletes existing database files, then reloads the collection in place and
        returns JSON with the operation result.

        Returns:
            Response: A JSON response indicating success, failure, or conflict if indexing is already in progress.
        """
        import threading

        try:
            status = get_indexing_status(data_root, logger=logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            logger.warning("Database reset requested by authenticated user")

            try:
                collection.close()
                logger.info("Collection closed before database reset")
            except Exception as e:
                logger.warning(f"Error closing collection: {e}")

            deleted_files = []
            for suffix in ["", "-wal", "-shm", "-journal"]:
                file_path = Path(str(db_path) + suffix)
                if file_path.exists():
                    try:
                        file_path.unlink()
                        deleted_files.append(file_path.name)
                        logger.debug(f"Deleted: {file_path}")
                    except Exception as e:
                        logger.exception(f"Failed to delete {file_path}: {e}")
                        return jsonify(
                            {
                                "success": False,
                                "error": f"Failed to delete database: {e}",
                            }
                        ), 500

            def reinitialize():
                try:
                    logger.info("Reloading music collection")
                    # reload() re-opens the *same* collection object in place,
                    # so every blueprint holding a reference to `collection`
                    # (registered once, at app startup) sees the fresh state —
                    # no rebinding, no stale references.
                    collection.reload()
                    logger.info("Collection reloaded")
                except Exception as e:
                    logger.exception(f"Error reloading collection: {e}")

            threading.Thread(target=reinitialize, daemon=True).start()

            return jsonify(
                {
                    "success": True,
                    "message": "Database reset. Rebuild started.",
                    "deleted_files": deleted_files,
                }
            )

        except Exception as e:
            logger.error(f"Error during reset: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @system.route("/check-database-health")
    @require_auth
    def check_database_health():
        """
        Checks the health of the music library database and returns the result as JSON.

        Uses a quick integrity check and track count to determine if the database is healthy or requires a reset.

        Returns:
            Response: A JSON response containing health status, track count, and check result or error details.
        """
        try:
            count = collection.count()

            with collection._extractor.get_conn(readonly=True) as conn:
                result = conn.execute("PRAGMA quick_check").fetchone()[0]
                is_healthy = result == "ok"

            return jsonify(
                {"healthy": is_healthy, "track_count": count, "check_result": result}
            )

        except DatabaseCorruptionError:
            return jsonify(
                {
                    "healthy": False,
                    "error": "Database corruption detected",
                    "requires_reset": True,
                }
            )
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return jsonify({"healthy": False, "error": str(e)}), 500

    return system
