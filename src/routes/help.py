from pathlib import Path

from flask import Blueprint, redirect, send_from_directory, url_for

ONLINE = "https://mark-me.github.io/mixtape-society/"


def create_help_blueprint(help_dir: Path) -> Blueprint:
    """
    Creates the Flask blueprint that serves the documentation site as the app's help.

    The Docker image carries the built site, so the help always belongs to the version
    that runs and works without internet. Where no built site is found, such as a local
    run before `zensical build`, the help is taken from GitHub Pages instead.

    Args:
        help_dir: Directory holding the built documentation site.

    Returns:
        Blueprint: The configured Flask blueprint for the help pages.
    """
    help_pages = Blueprint("help", __name__)
    help_dir = Path(help_dir)

    @help_pages.route("/", defaults={"path": ""})
    @help_pages.route("/<path:path>")
    def page(path: str):
        """
        Serves a page of the help, from the built site or else from GitHub Pages.

        Args:
            path: The page, relative to the root of the documentation site.

        Returns:
            Response: The requested file, or a redirect.
        """
        if not (help_dir / "index.html").is_file():
            return redirect(ONLINE + path)
        if path == "" or path.endswith("/"):
            path += "index.html"
        elif (help_dir / path).is_dir():
            return redirect(url_for("help.page", path=f"{path}/"))
        return send_from_directory(help_dir, path)

    return help_pages
