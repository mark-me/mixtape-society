import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, redirect, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from auth import check_auth
from config import DevelopmentConfig, ProductionConfig, TestConfig, BaseConfig
from logtools import get_logger, setup_logging
from musiclib import MusicCollectionUI, get_indexing_status
from mixtape_manager import MixtapeManager
from routes import (
    create_browser_blueprint,
    create_editor_blueprint,
    create_play_blueprint,
    create_download_blueprint,
    create_authentication_blueprint,
)
from utils import get_version, create_og_cover_blueprint


def create_app() -> Flask:
    config_cls = get_configuration()

    # === Create Flask app ===
    app = Flask(__name__)

    app.secret_key = config_cls.PASSWORD
    app.config.from_object(config_cls)
    CORS(app)  # This adds Access-Control-Allow-Origin: * to ALL responses

    limiter = Limiter(
        get_remote_address,
        default_limits=["500 per day", "100 per hour"],
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
    mixtape_manager = MixtapeManager(path_mixtapes=config_cls.MIXTAPE_DIR)

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

    @app.route("/robots.txt")
    def robots_txt():
        """
        Serves a robots.txt file that disallows all web crawlers. This helps prevent search engines from indexing the site.

        Returns:
            Response: A plain text HTTP response containing the robots.txt directives.
        """
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

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
        create_play_blueprint(mixtape_manager=mixtape_manager, logger=logger),
        url_prefix="/play",
    )
    app.register_blueprint(
        create_download_blueprint(mixtape_manager=mixtape_manager, logger=logger),
        url_prefix="/download",
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
