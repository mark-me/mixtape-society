import logging
import os
import sys
from datetime import datetime, timezone

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from auth import check_auth
from config import DevelopmentConfig, ProductionConfig, TestConfig
from logtools import get_logger, setup_logging
from musiclib import MusicCollection, get_indexing_status
from routes import browser, editor, play
from version_info import get_version


# === Loading configuration dependent on environment ===
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
}

ENV = os.getenv("APP_ENV", "development")

config = CONFIG_MAP.get(ENV, DevelopmentConfig)
config.ensure_dirs()

# === Set-up logging ====
log_dir = config.DATA_ROOT / "logs"
setup_logging(
    dir_output=str(log_dir),
    base_file="app.log",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)

# === Create Flask app ===
app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour"],
)
app.secret_key = config.PASSWORD
app.config["DATA_ROOT"] = config.DATA_ROOT
CORS(app)  # This adds Access-Control-Allow-Origin: * to ALL responses

# === Flask logging set-up ===
# Put this right after setup_logging(...)
if "gunicorn" in str(type(app)).lower() or "gunicorn" in sys.modules:
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    logging.root.handlers = gunicorn_logger.handlers
    logging.root.setLevel(gunicorn_logger.level)

logger = get_logger(name=__name__)

# === Start collection extraction ===
collection = MusicCollection(
    music_root=config.MUSIC_ROOT, db_path=config.DB_PATH, logger=logger
)

logger.warning(
    "NOTE: This application does not include or distribute any copyrighted media."
)
logger.warning("Users are responsible for the content they load into the system.")


@app.route("/")
def landing() -> Response:
    """
    Renders the landing page, indexing progress, or redirects authenticated users.

    Checks for ongoing indexing and shows progress if active. If no indexing and authenticated, redirects to mixtapes. Otherwise, shows the login page.

    Returns:
        Response: The appropriate rendered template or redirect.
    """
    status = get_indexing_status(config.DATA_ROOT, logger=logger)
    if status and status["status"] in ("rebuilding", "resyncing"):
        return render_template("indexing.html", status=status)
    if check_auth():
        return redirect("/mixtapes")
    return render_template("landing.html")


# === Authentication Routes ===


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
    password = request.form.get("password")
    if password == config.PASSWORD:
        session["authenticated"] = True
    else:
        flash("Invalid password", "danger")
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


# === Blueprints ===

app.register_blueprint(browser)
app.register_blueprint(play, url_prefix="/play")
app.register_blueprint(editor)


# === Server Start ===


def serve(debug: bool = True) -> None:
    """
    Starts the Flask application server.

    Runs the app on host 0.0.0.0 and port 5000, with debugging enabled or disabled based on the argument.

    Args:
        debug: Whether to run the server in debug mode. Defaults to True.
    """
    app.run(debug=debug, use_reloader=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    serve(debug=True)
