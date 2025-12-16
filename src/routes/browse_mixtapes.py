from flask import (
    Blueprint,
    Response,
    current_app,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

from auth import check_auth, require_auth
from mixtape_manager import MixtapeManager


def create_browser_blueprint(
    mixtape_manager: MixtapeManager, func_processing_status, logger
) -> Blueprint:
    """
    Creates and configures the Flask blueprint for browsing, playing, and managing mixtapes.

    Sets up routes for listing mixtapes, serving cover images and files, deleting mixtapes, and handling authentication for all routes in the blueprint.

    Args:
        mixtape_manager (MixtapeManager): The manager instance for retrieving and managing mixtapes.
        func_processing_status: A function to check the current indexing or processing status.
        logger: The logger instance for error reporting.

    Returns:
        Blueprint: The configured Flask blueprint for browsing and managing mixtapes.
    """
    browser = Blueprint("browse_mixtapes", __name__, template_folder="../templates")

    @browser.route("/")
    @require_auth
    def browse() -> Response:
        """
        Renders the browse mixtapes page or indexing progress if active.

        Checks for ongoing indexing and shows progress if active. Otherwise, lists all mixtapes.

        Returns:
            Response: The rendered template for mixtapes or indexing progress.
        """
        status = func_processing_status(current_app.config["DATA_ROOT"], logger=logger)
        if status and status["status"] in ("rebuilding", "resyncing"):
            return render_template("indexing.html", status=status)

        mixtapes = mixtape_manager.list_all()
        return render_template("browse_mixtapes.html", mixtapes=mixtapes)

    @browser.route("/play/<slug>")
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

    @browser.route("/covers/<filename>")
    def serve_cover(filename: str) -> Response:
        """
        Serves a cover image file from the covers directory.

        Returns the requested cover image file if it exists, or raises a 404 error if not found.

        Args:
            filename: The name of the cover image file to serve.

        Returns:
            Response: The Flask response object containing the requested file.
        """
        return send_from_directory(current_app.config["COVER_DIR"], filename)

    @browser.route("/files/<path:filename>")
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
        return send_from_directory(current_app.config["MIXTAPE_DIR"], filename)

    @browser.route("/delete/<slug>", methods=["POST"])
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
        mixtape_manager = MixtapeManager(
            path_mixtapes=current_app.config["MIXTAPE_DIR"]
        )
        mixtape_manager.delete(slug)

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

    return browser
