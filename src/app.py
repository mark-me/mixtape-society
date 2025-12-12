import logging
import mimetypes
import os
import sys
from datetime import datetime, timezone

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import DevelopmentConfig, ProductionConfig, TestConfig
from logtools import get_logger, setup_logging
from mixtape_manager import MixtapeManager
from musiclib import MusicCollection
from routes import browser, editor, play
from version_info import get_version

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
}

ENV = os.getenv("APP_ENV", "development")

config = CONFIG_MAP.get(ENV, DevelopmentConfig)
config.ensure_dirs()

log_dir = config.DATA_ROOT / "logs"
setup_logging(
    dir_output=str(log_dir),
    base_file="app.log",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
)
app.secret_key = config.PASSWORD
CORS(app)  # This adds Access-Control-Allow-Origin: * to ALL responses

# Put this right after setup_logging(...)
if "gunicorn" in str(type(app)).lower() or "gunicorn" in sys.modules:
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    logging.root.handlers = gunicorn_logger.handlers
    logging.root.setLevel(gunicorn_logger.level)

logger = get_logger(name=__name__)

collection = MusicCollection(music_root=config.MUSIC_ROOT, db_path=config.DB_PATH)

mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/aac", ".aac")
mimetypes.add_type("audio/ogg", ".ogg")

logger.warning("NOTE: This application does not include or distribute any copyrighted media.")
logger.warning("Users are responsible for the content they load into the system.")

@app.route("/")
def landing() -> Response:
    """
    Renders the landing page of the application.

    Returns the landing page template for the root URL.

    Returns:
        Response: The Flask response object containing the rendered landing page.
    """
    return render_template("landing.html")


@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login() -> Response:
    """
    Authenticates a user based on the submitted password.

    Checks the provided password against the configured password and sets the session as authenticated if correct.
    Redirects to the mixtapes page on success or flashes an error and redirects to the landing page on failure.

    Returns:
        Response: The Flask response object for the appropriate redirect.
    """
    if request.form.get("password") == config.PASSWORD:
        session["authenticated"] = True
        return redirect("/mixtapes")
    flash("Verkeerd wachtwoord")
    return redirect("/")


@app.route("/logout")
def logout() -> Response:
    """
    Logs out the current user by removing authentication from the session.

    Clears the user's session and redirects to the landing page.

    Returns:
        Response: The Flask response object for the redirect to the landing page.
    """
    session.pop("authenticated", None)
    return redirect("/")


@app.route("/mixtapes/files/<path:filename>")
def mixtape_files(filename: str) -> Response:
    """
    Serves a mixtape file from the mixtapes directory.

    Returns the requested mixtape file if it exists, or raises a 404 error if not found.

    Args:
        filename: The name of the mixtape file to serve.

    Returns:
        Response: The Flask response object containing the requested file.
    """
    return send_from_directory(config.MIXTAPE_DIR, filename)


@app.route("/covers/<filename>")
def serve_cover(filename: str) -> Response:
    """
    Serves a cover image file from the covers directory.

    Returns the requested cover image file if it exists, or raises a 404 error if not found.

    Args:
        filename: The name of the cover image file to serve.

    Returns:
        Response: The Flask response object containing the requested file.
    """
    return send_from_directory(config.COVER_DIR, filename)


@app.route("/share/<slug>")
def public_play(slug: str) -> Response:
    """
    Renders the public mixtape playback page for a given slug.

    Retrieves the mixtape by slug and displays it for public playback, or returns a 404 error if not found.

    Args:
        slug: The unique identifier for the mixtape.

    Returns:
        Response: The Flask response object containing the rendered mixtape playback page.
    """
    mixtape_manager = MixtapeManager(path_mixtapes=config.MIXTAPE_DIR)
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    return render_template("play_mixtape.html", mixtape=mixtape, public=True)


@app.context_processor
def inject_version():
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


# Blueprints
app.register_blueprint(browser)
app.register_blueprint(play, url_prefix="/play")
app.register_blueprint(editor)


def serve(debug: bool = True) -> None:
    """
    Starts the Flask application server.

    Runs the app on host 0.0.0.0 and port 5000, with debugging enabled or disabled based on the argument.

    Args:
        debug: Whether to run the server in debug mode. Defaults to True.
    """
    app.run(debug=debug, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    serve(debug=True)
