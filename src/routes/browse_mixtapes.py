from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from auth import check_auth, require_auth, Response
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


@browser.before_request
def blueprint_require_auth() -> Response:
    if request.endpoint in ["browse_mixtapes.browse", "browse_mixtapes.play"] and not check_auth():
        return redirect(url_for("landing"))
