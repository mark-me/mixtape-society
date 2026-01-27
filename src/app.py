import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audio_cache import AudioCache
from auth import check_auth, require_auth
from config import BaseConfig, DevelopmentConfig, ProductionConfig, TestConfig
from logtools import get_logger, setup_logging
from mixtape_manager import MixtapeManager
from musiclib import DatabaseCorruptionError, get_indexing_status

# NEW: Import CollectionManager instead of direct MusicCollectionUI
from collection_manager import CollectionManager, CollectionNotFoundError

from routes import (
    create_authentication_blueprint,
    create_collections_blueprint,
    create_browser_blueprint,
    create_editor_blueprint,
    create_og_cover_blueprint,
    create_play_blueprint,
    create_qr_blueprint,
)
from utils import get_version


def create_app() -> Flask:
    config_cls = get_configuration()

    # === Create Flask app ===
    app = Flask(__name__)

    app.secret_key = config_cls.PASSWORD
    app.config.from_object(config_cls)
    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Requested-With",
                    "Accept",
                    "Origin",
                    "Access-Control-Request-Method",
                    "Access-Control-Request-Headers",
                    "Range",  # Important for audio seeking
                ],
                "expose_headers": [
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                ],
                "supports_credentials": False,
                "max_age": 3600,
            }
        },
    )

    limiter = Limiter(
        get_remote_address,
    )
    limiter.init_app(app=app)

    logger_setup(config=config_cls)
    # Setup Flask logging
    if "gunicorn" in str(type(app)).lower() or "gunicorn" in sys.modules:
        gunicorn_logger = logging.getLogger("gunicorn.error")
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
        logging.root.handlers = gunicorn_logger.handlers
        logging.root.setLevel(gunicorn_logger.level)

    logger = get_logger(name=__name__)

    # ========================================================================
    # COLLECTION INITIALIZATION - MULTI-COLLECTION SUPPORT
    # ========================================================================
    # The CollectionManager coordinates multiple music collections.
    # Each collection has its own:
    # - music_root directory (where audio files are stored)
    # - database file (SQLite with indexed metadata)
    # - file system watcher (monitors for changes)
    # - indexing queue (for background processing)
    #
    # Key behaviors:
    # - On first run, auto-creates collections.yml with single "main" collection
    # - Each collection independently monitors its music_root for changes
    # - Rebuilding/resyncing operates per-collection
    # - Collections can be added/removed by editing collections.yml and restarting
    # ========================================================================

    logger.info("Initializing CollectionManager")

    try:
        collection_manager = CollectionManager(
            config_path=config_cls.COLLECTIONS_CONFIG,
            logger=logger,
            use_ui_layer=True  # Wrap collections in MusicCollectionUI for UI features
        )
    except Exception as e:
        logger.error(f"Failed to initialize CollectionManager: {e}", exc_info=True)
        raise

    # Get default collection for backward compatibility with existing routes
    # This is used for routes that don't yet have collection-specific logic
    default_collection = collection_manager.get_default()

    if not default_collection:
        logger.error("No default collection available!")
        raise RuntimeError("No collections configured")

    logger.info(
        f"Default collection: {collection_manager._default_id} "
        f"({len(collection_manager.get_collection_ids())} total collection(s))"
    )

    # Initialize audio cache
    audio_cache = AudioCache(cache_dir=app.config["AUDIO_CACHE_DIR"], logger=logger)
    app.audio_cache = audio_cache

    # ========================================================================
    # MIXTAPE MANAGER INITIALIZATION
    # ========================================================================
    # MixtapeManager now receives collection_manager instead of single collection.
    # This allows mixtapes to reference specific collections via collection_id.
    #
    # When verifying tracks:
    # - Looks up collection_id from mixtape JSON
    # - Gets corresponding collection from collection_manager
    # - Verifies tracks against that collection's database
    # ========================================================================

    mixtape_manager = MixtapeManager(
        path_mixtapes=config_cls.MIXTAPE_DIR,
        collection_manager=collection_manager,  # CHANGED: was collection=collection
        logger=logger
    )

    # Store on app for access in blueprints and routes
    app.collection_manager = collection_manager
    app.mixtape_manager = mixtape_manager

    @app.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(
            app.root_path,
            "service-worker.js",
            mimetype="application/javascript",
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Service-Worker-Allowed"] = "/play/"
        return response

    @app.route("/manifest.json")
    def manifest():
        """Serve PWA manifest"""
        return send_from_directory(
            app.root_path, "manifest.json", mimetype="application/manifest+json"
        )

    @app.errorhandler(DatabaseCorruptionError)
    def handle_database_corruption(e: DatabaseCorruptionError) -> tuple[Response, int]:
        """Handles database corruption errors and returns a structured JSON response."""
        logger.error(f"Database corruption detected: {e}")

        # Detect if AJAX request
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.headers.get("Accept", "").startswith("application/json")
            or request.is_json
        )

        if is_ajax:
            return jsonify(
                {
                    "error": "database_corrupted",
                    "message": "The music library database needs to be rebuilt.",
                    "requires_reset": True,
                }
            ), 500
        else:
            return render_template("database_error.html"), 500

    @app.before_request
    def check_indexing_before_request():
        """
        Check if indexing is in progress and redirect authenticated users.

        NOTE: With multi-collection, this checks the default collection's status.
        In the future, could be enhanced to show status for all collections.
        """
        logger.debug(f"🔍 CHECK: {request.path}")
        bypass_paths = [
            "/static",
            "/play",
            "/indexing-status",
            "/check-database-health",
            "/api/collections",  # NEW: Allow collection API during indexing
        ]

        for path in bypass_paths:
            if request.path.startswith(path):
                logger.debug(f"  ↪ BYPASS: {path}")
                return None

        is_auth = check_auth()
        logger.debug(f"  Auth: {is_auth}")
        if not is_auth:
            return None

        # NOTE: Currently checks default collection's indexing status
        # With multiple collections, each has independent indexing status
        status = get_indexing_status(config_cls.DATA_ROOT, logger=logger)
        logger.debug(f"  Status: {status}")

        if status and status["status"] in ("rebuilding", "resyncing"):
            return render_template("indexing.html", status=status)

        return None

    @app.route("/")
    def landing() -> Response:
        """Renders the landing page or redirects authenticated users."""
        status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
        if status and status["status"] in ("rebuilding", "resyncing"):
            return render_template("indexing.html", status=status)
        if check_auth():
            return redirect("/mixtapes")
        return render_template("landing.html")

    @app.route("/indexing-status")
    @limiter.exempt
    def indexing_status_json():
        """
        Returns the current indexing status as JSON.

        NOTE: Currently returns default collection's status.
        With multiple collections, consider returning status for all collections
        or accepting a collection_id parameter.
        """
        status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
        if not status:
            return {"done": True}

        return {
            "done": False,
            "status": status.get("status"),
            "current": status.get("current", 0),
            "total": status.get("total", 0),
            "started_at": status.get("started_at"),
        }

    @app.route("/collection-stats")
    @require_auth
    def collection_stats_json():
        """
        Returns collection statistics as JSON.

        UPDATED: Now uses default collection by default.
        Can be enhanced to accept collection_id parameter for specific collection stats.
        """
        try:
            # Optional: Get collection_id from query parameter
            collection_id = request.args.get('collection_id')

            if collection_id:
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({"error": "Collection not found"}), 404
            else:
                collection = default_collection

            stats = collection.get_collection_stats()
            return jsonify(stats)
        except Exception as e:
            logger.exception(f"Error fetching collection stats: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    # ========================================================================
    # RESYNC ENDPOINT - MULTI-COLLECTION AWARE
    # ========================================================================
    # Resyncing now supports both:
    # 1. Default collection (backward compatible)
    # 2. Specific collection via collection_id parameter
    #
    # Each collection's resync is independent:
    # - Scans that collection's music_root only
    # - Updates that collection's database only
    # - Uses that collection's indexing_status.json
    #
    # Multiple collections can be resynced sequentially by calling this
    # endpoint multiple times with different collection_ids.
    # ========================================================================

    @app.route("/resync", methods=["POST"])
    @require_auth
    def resync_library():
        """
        Triggers a resync of a music collection.

        UPDATED: Now accepts optional collection_id parameter.
        - No collection_id: Resyncs default collection (backward compatible)
        - With collection_id: Resyncs specific collection

        Request body (JSON):
            {
                "collection_id": "jazz"  # Optional
            }
        """
        try:
            # Get collection_id from request
            collection_id = None
            if request.is_json:
                collection_id = request.json.get('collection_id')

            # Get the appropriate collection
            if collection_id:
                logger.info(f"Resync requested for collection: {collection_id}")
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({
                        "success": False,
                        "error": f"Collection '{collection_id}' not found"
                    }), 404
            else:
                logger.info("Resync requested for default collection")
                collection = default_collection
                collection_id = collection_manager._default_id

            # Check if indexing is already in progress for this collection
            # NOTE: Currently uses shared indexing_status.json
            # Future enhancement: Per-collection status tracking
            status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            # Trigger resync in background
            def run_resync():
                try:
                    collection.resync()
                    logger.info(f"Music library resync completed for collection '{collection_id}'")
                except Exception as e:
                    logger.exception(f"Error during resync of collection '{collection_id}': {e}")

            thread = threading.Thread(target=run_resync, daemon=True)
            thread.start()

            logger.info(f"Music library resync initiated for collection '{collection_id}'")
            return jsonify({
                "success": True,
                "collection_id": collection_id,
                "message": f"Resync started for collection '{collection_id}'"
            })

        except Exception as e:
            logger.exception(f"Error initiating resync: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/robots.txt")
    def robots_txt():
        """Serves robots.txt to prevent search engine indexing."""
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    @app.route("/covers/<filename>")
    def serve_album_cover(filename):
        """
        Serves extracted album cover images.

        NOTE: Covers are stored in DATA_ROOT/cache/covers which is shared
        across all collections. Cover filenames include sanitized release_dir
        to avoid collisions between collections.
        """
        covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            abort(404)

        response = send_from_directory(covers_dir, filename)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Max-Age'] = '3600'
        response.headers['Cache-Control'] = 'public, max-age=86400'
        response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'

        return response

    @app.route("/api/covers/<path:release_dir_encoded>")
    def serve_cover_by_size(release_dir_encoded):
        """
        Serves cover art with optional size parameter.

        Query Parameters:
            size: Optional size in format WxH (e.g., 256x256)
            collection_id: Optional collection to get cover from

        UPDATED: Now accepts collection_id parameter to get cover from
        specific collection. Defaults to default collection.
        """
        from urllib.parse import unquote

        release_dir = unquote(release_dir_encoded)
        requested_size = request.args.get('size', '').lower()
        collection_id = request.args.get('collection_id')

        # Get appropriate collection
        if collection_id:
            collection = collection_manager.get(collection_id)
            if not collection:
                return jsonify({"error": "Collection not found"}), 404
        else:
            collection = default_collection

        valid_sizes = ['96x96', '128x128', '192x192', '256x256', '384x384', '512x512']
        covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"

        if not requested_size:
            # No size specified, return main cover
            cover_url = collection.get_cover(release_dir)
            if cover_url:
                filename = cover_url.split('/')[-1]
                return send_from_directory(covers_dir, filename)
            abort(404)

        # Validate size parameter
        if requested_size not in valid_sizes:
            return jsonify({
                "error": "Invalid size parameter",
                "valid_sizes": valid_sizes
            }), 400

        # Get or generate size-specific cover
        slug = collection._sanitize_release_dir(release_dir)
        size_filename = f"{slug}_{requested_size}.jpg"
        size_path = covers_dir / size_filename

        if not size_path.exists():
            main_path = covers_dir / f"{slug}.jpg"
            if not main_path.exists():
                collection._extract_cover(release_dir, main_path)

            if main_path.exists():
                collection._generate_cover_variants(release_dir, slug)

        if size_path.exists():
            return send_from_directory(covers_dir, size_filename)

        main_filename = f"{slug}.jpg"
        main_path = covers_dir / main_filename
        if main_path.exists():
            return send_from_directory(covers_dir, main_filename)

        return send_from_directory(covers_dir, "_fallback.jpg")

    # ========================================================================
    # RESET DATABASE ENDPOINT - MULTI-COLLECTION AWARE
    # ========================================================================
    # Database reset now supports:
    # 1. Resetting default collection (backward compatible)
    # 2. Resetting specific collection via collection_id parameter
    # 3. Resetting ALL collections via collection_id="all"
    #
    # IMPORTANT: Each collection's database is independent, so resetting
    # one collection does not affect others.
    # ========================================================================

    @app.route("/reset-database", methods=["POST"])
    @require_auth
    def reset_database():
        """
        Resets music library database(s) and triggers rebuild.

        UPDATED: Now supports multi-collection reset.

        Request body (JSON):
            {
                "collection_id": "jazz"  # Optional: specific collection
                                        # or "all" to reset all collections
                                        # or omit for default collection
            }

        Returns:
            JSON with success status, collection(s) reset, and files deleted
        """
        try:
            # Get collection_id from request
            collection_id = None
            if request.is_json:
                collection_id = request.json.get('collection_id')

            # Check if indexing already in progress
            status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            logger.warning(f"Database reset requested for collection: {collection_id or 'default'}")

            # Determine which collections to reset
            if collection_id == "all":
                # Reset all collections
                collections_to_reset = [
                    (coll_id, collection_manager.get(coll_id))
                    for coll_id in collection_manager.get_collection_ids()
                ]
                logger.warning("Resetting ALL collections")
            elif collection_id:
                # Reset specific collection
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({
                        "success": False,
                        "error": f"Collection '{collection_id}' not found"
                    }), 404
                collections_to_reset = [(collection_id, collection)]
            else:
                # Reset default collection (backward compatible)
                default_id = collection_manager._default_id
                collections_to_reset = [(default_id, default_collection)]

            all_deleted_files = []

            # Reset each collection
            for coll_id, coll in collections_to_reset:
                logger.info(f"Resetting collection: {coll_id}")

                # Close collection
                try:
                    coll.close()
                    logger.info(f"Collection '{coll_id}' closed")
                except Exception as e:
                    logger.warning(f"Error closing collection '{coll_id}': {e}")

                # Get database path for this collection
                coll_info = collection_manager.get_info(coll_id)
                db_path = Path(coll_info['db_path'])

                # Delete database files
                deleted_files = []
                for suffix in ["", "-wal", "-shm", "-journal"]:
                    file_path = Path(str(db_path) + suffix)
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            deleted_files.append(f"{coll_id}:{file_path.name}")
                            logger.debug(f"Deleted: {file_path}")
                        except Exception as e:
                            logger.exception(f"Failed to delete {file_path}: {e}")
                            return jsonify({
                                "success": False,
                                "error": f"Failed to delete {file_path}: {e}",
                            }), 500

                all_deleted_files.extend(deleted_files)

            # Reinitialize collections in background
            def reinitialize():
                try:
                    logger.info("Reinitializing collection manager")
                    collection_manager.reload_config()
                    logger.info("Collections reinitialized successfully")
                except Exception as e:
                    logger.exception(f"Error reinitializing collections: {e}")

            thread = threading.Thread(target=reinitialize, daemon=True)
            thread.start()

            return jsonify({
                "success": True,
                "message": f"Database reset. Rebuild started for {len(collections_to_reset)} collection(s).",
                "collections_reset": [coll_id for coll_id, _ in collections_to_reset],
                "deleted_files": all_deleted_files,
            })

        except Exception as e:
            logger.error(f"Error during reset: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/check-database-health")
    @require_auth
    def check_database_health():
        """
        Checks the health of music library database(s).

        UPDATED: Can check specific collection or default collection.

        Query Parameters:
            collection_id: Optional collection to check (defaults to default collection)

        Returns:
            JSON with health status, track count, and check result
        """
        try:
            collection_id = request.args.get('collection_id')

            if collection_id:
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({"error": "Collection not found"}), 404
            else:
                collection = default_collection
                collection_id = collection_manager._default_id

            count = collection.count()

            with collection._extractor.get_conn(readonly=True) as conn:
                result = conn.execute("PRAGMA quick_check").fetchone()[0]
                is_healthy = result == "ok"

            return jsonify({
                "healthy": is_healthy,
                "track_count": count,
                "check_result": result,
                "collection_id": collection_id
            })

        except DatabaseCorruptionError:
            return jsonify({
                "healthy": False,
                "error": "Database corruption detected",
                "requires_reset": True,
                "collection_id": collection_id
            })
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return jsonify({"healthy": False, "error": str(e)}), 500

    # === Context Processors ===

    @app.context_processor
    def inject_version() -> dict:
        """Injects the application version into the template context."""
        return {"app_version": get_version()}

    @app.context_processor
    def inject_copyright() -> dict:
        """Injects the current year for copyright notices."""
        return {"current_year": datetime.now(timezone.utc).year}

    # ========================================================================
    # BLUEPRINT REGISTRATION
    # ========================================================================

    app.register_blueprint(
        create_authentication_blueprint(limiter=limiter, logger=logger),
    )

    # Browser blueprint - unchanged, still gets mixtape_manager
    app.register_blueprint(
        create_browser_blueprint(
            mixtape_manager=mixtape_manager,
            func_processing_status=get_indexing_status,
            logger=logger,
        ),
        url_prefix="/mixtapes",
    )

    # Play blueprint - unchanged
    app.register_blueprint(
        create_play_blueprint(
            mixtape_manager=mixtape_manager,
            path_audio_cache=app.config["AUDIO_CACHE_DIR"],
            logger=logger,
        ),
        url_prefix="/play",
    )

    # UPDATED: Editor blueprint now gets collection_manager
    app.register_blueprint(
        create_editor_blueprint(
            collection_manager=collection_manager,  # CHANGED: was collection=collection
            logger=logger
        ),
        url_prefix="/editor",
    )

    app.register_blueprint(
        create_og_cover_blueprint(
            path_logo=Path(__file__).parent / "static" / "images" / "logo.svg",
            logger=logger
        ),
        url_prefix="/og",
    )

    app.register_blueprint(
        create_qr_blueprint(mixtape_manager=mixtape_manager, logger=logger)
    )

    # NEW: Collections API blueprint (optional - add when needed)
    # from routes.collections import create_collections_blueprint
    # app.register_blueprint(
    #     create_collections_blueprint(
    #         collection_manager=collection_manager,
    #         logger=logger
    #     ),
    #     url_prefix="/api/collections"
    # )

    return app


def get_configuration() -> BaseConfig:
    """
    Determines and returns the appropriate configuration class.
    """
    CONFIG_MAP = {
        "development": DevelopmentConfig,
        "test": TestConfig,
        "production": ProductionConfig,
    }

    ENV = os.getenv("APP_ENV", "development")

    config = CONFIG_MAP.get(ENV, DevelopmentConfig)
    config.ensure_dirs()
    return config


def logger_setup(config):
    log_dir = config.DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(
        dir_output=str(log_dir),
        base_file="app.log",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def serve(debug: bool = True) -> None:
    """Starts the Flask application server."""
    app = create_app()
    app.run(debug=debug, use_reloader=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    serve(debug=True)
