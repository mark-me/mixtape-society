from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

from auth import check_auth, require_auth
from config import BaseConfig as Config
from mixtape_manager import MixtapeManager

browser = Blueprint("browse_mixtapes", __name__, template_folder="../templates")


@browser.route("/mixtapes")
@require_auth
def browse() -> Response:
    """
    Renders the browse mixtapes page with a list of all available mixtapes.

    Retrieves all mixtapes using the MixtapeManager and passes them to the template for display.

    Returns:
        Response: A rendered template displaying the list of mixtapes.
    """
    mixtape_manager = MixtapeManager(path_mixtapes=Config.MIXTAPE_DIR)
    mixtapes = mixtape_manager.list_all()
    return render_template("browse_mixtapes.html", mixtapes=mixtapes)


@browser.route("/mixtapes/play/<slug>")
@require_auth
def play(slug: str) -> Response:
    """
    Redirects to the public play page for a given mixtape slug.

    Takes the mixtape slug and redirects the user to the corresponding public play route.

    Args:
        slug: The unique identifier for the mixtape.

    Returns:
        Response: A redirect response to the public play page for the mixtape.
    """
    return redirect(url_for("public_play", slug=slug))


@browser.route("/mixtapes/files/<path:filename>")
@require_auth
def files(filename: str) -> Response:
    """
    Serves a mixtape file from the mixtape directory.

    Returns the requested file as a Flask response for download or display.

    Args:
        filename: The path to the mixtape file within the mixtape directory.

    Returns:
        Response: A Flask response serving the requested file.
    """
    return send_from_directory(Config.MIXTAPE_DIR, filename)

@browser.route("/mixtapes/delete/<slug>", methods=["POST"])
@require_auth
def delete_mixtape(slug: str) -> Response:
    """
    Deletes a mixtape and its associated cover image.

    Removes the mixtape JSON file and cover image from disk if they exist. Returns a 200 response on success or 404 if the mixtape is not found.

    Args:
        slug: The unique identifier for the mixtape to delete.

    Returns:
        Response: An empty response with status 200 if successful, or 404 if the mixtape does not exist.
    """
    mixtape_manager = MixtapeManager(path_mixtapes=Config.MIXTAPE_DIR)
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)

    # Delete JSON file
    json_file = Config.MIXTAPE_DIR / f"{slug}.json"
    json_file.unlink(missing_ok=True)

    # Delete cover image if it exists
    if mixtape.get("cover"):
        cover_path = Config.COVER_DIR / Path(mixtape["cover"]).name
        cover_path.unlink(missing_ok=True)

    return "", 200

@browser.before_request
def blueprint_require_auth() -> Response | None:
    """
    Ensures authentication for all routes in the browse_mixtapes blueprint.

    Checks if the user is authenticated before allowing access to any route in this blueprint. Redirects unauthenticated users to the landing page.

    Returns:
        Response or None: A redirect response to the landing page if not authenticated, otherwise None.
    """
    # Protect everything in this blueprint
    if not check_auth():
        return redirect(url_for("landing"))
