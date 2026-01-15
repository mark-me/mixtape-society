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
from musiclib import DatabaseCorruptionError, MusicCollectionUI, get_indexing_status
from routes import (
    create_authentication_blueprint,
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
                "origins": "*",  # Allow all origins (adjust if you need restriction)
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
                "max_age": 3600,  # Cache preflight for 1 hour
            }
        },
    )

    limiter = Limiter(
        get_remote_address,
        default_limits=["1000 per day", "300 per hour"],
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

    # === Start collection extraction ===
    collection = MusicCollectionUI(
        music_root=config_cls.MUSIC_ROOT, db_path=config_cls.DB_PATH, logger=logger
    )

    # Initialize audio cache
    audio_cache = AudioCache(cache_dir=app.config["AUDIO_CACHE_DIR"], logger=logger)
    app.audio_cache = audio_cache

    mixtape_manager = MixtapeManager(
        path_mixtapes=config_cls.MIXTAPE_DIR, collection=collection
    )

    @app.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(
            app.root_path,  # Serves from app root directory
            "service-worker.js",
            mimetype="application/javascript",
        )
        # Prevent caching so updates work
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        # Scope to /play/ only
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
        """Handles database corruption errors and returns a structured JSON response.
        Logs the error and informs the client that the music library database must be rebuilt.

        Args:
            e: The DatabaseCorruptionError instance that was raised.

        Returns:
            tuple[Response, int]: A JSON response describing the error and the HTTP 500 status code.
        """
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
        """Check if indexing is in progress and redirect authenticated users."""

        logger.debug(f"🔍 CHECK: {request.path}")
        # Skip these paths
        # bypass_paths = [
        #      '/indexing-status', '/',
        #     '/reset-database', '/check-database-health'
        # ]
        bypass_paths = [
            "/static",
            "/play",
            "/indexing-status",
            "/check-database-health",
        ]

        for path in bypass_paths:
            if request.path.startswith(path):
                logger.debug(f"  ↪ BYPASS: {path}")
                return None

        is_auth = check_auth()
        logger.debug(f"  Auth: {is_auth}")
        if not is_auth:
            return None

        status = get_indexing_status(config_cls.DATA_ROOT, logger=logger)
        logger.debug(f"  Status: {status}")

        if status and status["status"] in ("rebuilding", "resyncing"):
            return render_template("indexing.html", status=status)

        return None

    @app.route("/")
    def landing() -> Response:
        """
        Renders the landing page, indexing progress, or redirects authenticated users.

        Checks for ongoing indexing and shows progress if active. If no indexing and authenticated, redirects to mixtapes. Otherwise, shows the login page.

        Returns:
            Response: The appropriate rendered template or redirect.
        """
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
        Used by the indexing page for AJAX polling.
        """
        status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
        if not status:
            # No indexing in progress → redirect to landing behavior
            return {"done": True}

        return {
            "done": False,
            "status": status.get("status"),
            "current": status.get("current", 0),
            "total": status.get("total", 0),
            "started_at": status.get("started_at"),  # ISO string
        }

    @app.route("/collection-stats")
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

    @app.route("/resync", methods=["POST"])
    @require_auth
    def resync_library():
        """
        Triggers a resync of the music library.
        Only accessible to authenticated users.
        Returns JSON with success status or error message.
        """
        try:
            # Check if indexing is already in progress
            status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            # Trigger resync in background
            import threading

            def run_resync():
                try:
                    collection.resync()
                    logger.info("Music library resync completed successfully")
                except Exception as e:
                    logger.exception(f"Error during resync: {e}")

            thread = threading.Thread(target=run_resync, daemon=True)
            thread.start()

            logger.info("Music library resync initiated by user")
            return jsonify({"success": True})

        except Exception as e:
            logger.exception(f"Error initiating resync: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/robots.txt")
    def robots_txt():
        """
        Serves a robots.txt file that disallows all web crawlers. This helps prevent search engines from indexing the site.

        Returns:
            Response: A plain text HTTP response containing the robots.txt directives.
        """
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    @app.route("/covers/<filename>")
    def serve_album_cover(filename):
        """
        Serves extracted album cover images from the cached covers directory.
        """
        covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"
        # Security: restrict to .jpg (or .jpeg/.png if you extend extraction)
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            abort(404)
        return send_from_directory(covers_dir, filename)

    @app.route("/api/covers/<path:release_dir_encoded>")
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
        from urllib.parse import unquote

        # Decode the release directory
        release_dir = unquote(release_dir_encoded)

        # Get requested size from query parameter
        requested_size = request.args.get('size', '').lower()

        # Validate size format and allowed values
        valid_sizes = ['96x96', '128x128', '192x192', '256x256', '384x384', '512x512']

        covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"

        if not requested_size:
            # No size specified, return main cover (existing behavior)
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

        # If size variant doesn't exist, generate it
        if not size_path.exists():
            # Ensure main cover exists first
            main_path = covers_dir / f"{slug}.jpg"
            if not main_path.exists():
                collection._extract_cover(release_dir, main_path)

            # Generate variants (will create the requested size)
            if main_path.exists():
                collection._generate_cover_variants(release_dir, slug)

        # Serve the size-specific cover if it exists
        if size_path.exists():
            return send_from_directory(covers_dir, size_filename)

        # Fallback: try to serve main cover
        main_filename = f"{slug}.jpg"
        main_path = covers_dir / main_filename
        if main_path.exists():
            return send_from_directory(covers_dir, main_filename)

        # Final fallback
        return send_from_directory(covers_dir, "_fallback.jpg")

    @app.route("/reset-database", methods=["POST"])
    @require_auth
    def reset_database():
        """Resets the corrupted database and triggers rebuild."""
        try:
            # Check if indexing already in progress
            status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
            if status and status["status"] in ("rebuilding", "resyncing"):
                return jsonify(
                    {"success": False, "error": "Indexing already in progress"}
                ), 409

            logger.warning("Database reset requested by authenticated user")

            # Close collection
            try:
                collection.close()
                logger.info("Collection closed before database reset")
            except Exception as e:
                logger.warning(f"Error closing collection: {e}")

            # Delete database files
            db_path = Path(config_cls.DB_PATH)
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

            # Reinitialize collection (triggers rebuild)
            def reinitialize():
                try:
                    global collection
                    logger.info("Reinitializing music collection")
                    collection = MusicCollectionUI(
                        music_root=config_cls.MUSIC_ROOT,
                        db_path=config_cls.DB_PATH,
                        logger=logger,
                    )
                    logger.info("Collection reinitialized")
                except Exception as e:
                    logger.exception(f"Error reinitializing: {e}")

            thread = threading.Thread(target=reinitialize, daemon=True)
            thread.start()

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

    @app.route("/check-database-health")
    @require_auth
    def check_database_health():
        """Checks database health proactively."""
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

    # === Context Processors ===

    @app.context_processor
    def inject_version() -> dict:
        """
        Injects the application version into the template context.

        This allows templates to access the current app version using the 'app_version' variable.

        Returns:
            dict: A dictionary with the application version under the key 'app_version'.
        """
        return {"app_version": get_version()}

    @app.context_processor
    def inject_now() -> dict:
        """
        Injects the current UTC datetime into the template context.

        This allows templates to access the current time using the 'now' variable.

        Returns:
            dict: A dictionary with the current UTC datetime under the key 'now'.
        """
        return {"now": datetime.now(timezone.utc)}

    @app.context_processor
    def inject_auth_status() -> dict:
        """
        Injects the authentication status into the template context.

        This allows templates to conditionally render content based on whether
        the user is authenticated.

        Returns:
            dict: A dictionary with the authentication status under 'is_authenticated'.
        """
        return {"is_authenticated": check_auth()}

    @app.context_processor
    def inject_indexing_status() -> dict:
        """
        Injects the current indexing status into the template context.

        This allows templates to know if indexing is in progress and conditionally
        disable UI elements.

        Returns:
            dict: A dictionary with the indexing status flag under 'is_indexing'.
        """
        status = get_indexing_status(config_cls.DATA_ROOT, logger=app.logger)
        is_indexing = status and status["status"] in ("rebuilding", "resyncing")
        return {"is_indexing": is_indexing}

    @app.template_filter("to_datetime")
    def to_datetime_filter(s, fmt="%Y-%m-%d %H:%M:%S"):
        """
        Converts a string timestamp into a datetime object for template usage. Provides a robust parser that supports a custom format and ISO 8601 strings.

        Attempts to parse the input string using the provided format first, then falls back to ISO format parsing if needed. Returns None when the input is empty or falsy.

        Args:
            s: The input timestamp string to convert.
            fmt: The expected datetime format string used for initial parsing.

        Returns:
            datetime | None: A datetime object if parsing succeeds, otherwise None for empty input.
        """
        if not s:
            return None
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            # Fallback: try ISO format
            return datetime.fromisoformat(s.replace("Z", "+00:00"))

    # === Blueprints ===
    app.register_blueprint(
        create_authentication_blueprint(logger=logger, limiter=limiter),
        url_prefix="/auth",
    )
    app.register_blueprint(
        create_browser_blueprint(
            mixtape_manager=mixtape_manager,
            func_processing_status=get_indexing_status,
            logger=logger,
        ),
        url_prefix="/mixtapes",
    )
    app.register_blueprint(
        create_play_blueprint(
            mixtape_manager=mixtape_manager,
            path_audio_cache=app.config["AUDIO_CACHE_DIR"],
            logger=logger,
        ),
        url_prefix="/play",
    )
    app.register_blueprint(
        create_editor_blueprint(collection=collection, logger=logger),
        url_prefix="/editor",
    )
    app.register_blueprint(
        create_og_cover_blueprint(
            path_logo=Path(__file__).parent / "static" / "logo.svg", logger=logger
        ),
        url_prefix="/og",
    )
    app.register_blueprint(
        create_qr_blueprint(mixtape_manager=mixtape_manager, logger=logger)
    )

    return app


def get_configuration() -> BaseConfig:
    """
    Determines and returns the appropriate configuration class for the current environment.

    Selects the configuration based on the APP_ENV environment variable,
    ensures necessary directories exist, and returns the configuration object.

    Returns:
        BaseConfig: The configuration object for the current environment.
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
    """
    Starts the Flask application server.

    Runs the app on host 0.0.0.0 and port 5000, with debugging enabled or disabled based on the argument.

    Args:
        debug: Whether to run the server in debug mode. Defaults to True.
    """
    app = create_app()
    app.run(debug=debug, use_reloader=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    serve(debug=True)
