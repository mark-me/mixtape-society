import mimetypes
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    Response,
    send_file,
    send_from_directory,
    session,
)

from logtools import get_logger
from mixtape_manager import MixtapeManager
from musiclib import MusicCollection
from routes import browser, play, editor  # ← editor toegevoegd

logger = get_logger(name=__name__)

MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"
MIXTAPE_DIR = Path(__file__).parent.parent / "mixtapes"
COVER_DIR = MIXTAPE_DIR / "covers"
MIXTAPE_DIR.mkdir(exist_ok=True)
COVER_DIR.mkdir(exist_ok=True)
PASSWORD = "password"  # Verander dit naar iets veiligs of gebruik een env-var

app = Flask(__name__)
app.secret_key = PASSWORD

collection = MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH)

mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/aac", ".aac")
mimetypes.add_type("audio/ogg", ".ogg")


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
def login() -> Response:
    """
    Handles user login by verifying the submitted password.

    Authenticates the user and redirects to the mixtapes page if the password is correct, otherwise flashes an error and redirects to the landing page.

    Returns:
        Response: The Flask response object for the appropriate redirect.
    """
    if request.form.get("password") == PASSWORD:
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


@app.route("/play/<path:file_path>")
def stream_audio(file_path: str) -> Response:
    """
    Streams an audio file from the music directory to the client.

    Validates the file path, determines the correct MIME type, and supports HTTP range requests for seeking. Returns the requested audio file or an appropriate error if the file is not found or access is denied.

    Args:
        file_path: The relative path to the audio file within the music directory.

    Returns:
        Response: The Flask response object streaming the audio file or an error response.
    """
    full_path = _resolve_and_validate_path(file_path)
    mime_type = _guess_mime_type(full_path)

    if range_header := request.headers.get("Range"):
        return _handle_range_request(full_path, mime_type, range_header)

    return send_file(full_path, mimetype=mime_type, download_name=full_path.name)


def _resolve_and_validate_path(file_path: str) -> Path:
    """
    Resolves and validates the requested file path within the music directory.

    Ensures the file is within the allowed music root and exists as a file. Aborts with an error if validation fails.

    Args:
        file_path: The relative path to the audio file within the music directory.

    Returns:
        Path: The resolved and validated Path object for the requested file.

    Raises:
        403: If the file is outside the music root directory.
        404: If the file does not exist.
    """
    full_path = (MUSIC_ROOT / file_path).resolve()
    try:
        full_path.relative_to(MUSIC_ROOT)
    except ValueError:
        abort(403)
    if not full_path.is_file():
        abort(404)
    return full_path


def _guess_mime_type(full_path: Path) -> str:
    """
    Determines the MIME type for a given file path.

    Returns the appropriate MIME type for the file, using the file extension as a fallback if necessary.

    Args:
        full_path: The Path object representing the file.

    Returns:
        str: The MIME type string for the file.
    """
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        suffix = full_path.suffix.lower()
        mime_type = {
            ".flac": "audio/flac",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".ogg": "audio/ogg",
        }.get(suffix, "application/octet-stream")
    return mime_type


def _handle_range_request(
    full_path: Path, mime_type: str, range_header: str
) -> Response:
    """
    Handles HTTP range requests for partial audio file streaming.

    Reads and returns the requested byte range of the file, setting appropriate headers for partial content responses.

    Args:
        full_path: The Path object representing the audio file.
        mime_type: The MIME type string for the file.
        range_header: The value of the HTTP Range header from the request.

    Returns:
        Response: The Flask response object containing the requested byte range.
    """
    # Range support (voor seeking)
    byte1, byte2 = 0, None
    m = range_header.replace("bytes=", "")
    if "-" in m:
        byte1, byte2 = m.split("-")
        byte1 = int(byte1)
        byte2 = int(byte2) if byte2 else full_path.stat().st_size - 1
    else:
        byte1 = int(m)

    length = byte2 - byte1 + 1 if byte2 else full_path.stat().st_size - byte1
    with open(full_path, "rb") as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 206, mimetype=mime_type, direct_passthrough=True)
    rv.headers.add(
        "Content-Range",
        f"bytes {byte1}-{byte1 + length - 1}/{full_path.stat().st_size}",
    )
    return rv


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
    return send_from_directory(MIXTAPE_DIR, filename)


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
    return send_from_directory(COVER_DIR, filename)


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
    mixtape_manager = MixtapeManager(path_mixtapes=MIXTAPE_DIR)
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    return render_template("play_mixtape.html", mixtape=mixtape, public=True)


# Blueprints registreren
app.register_blueprint(browser)
app.register_blueprint(play)
app.register_blueprint(editor)  # ← nieuwe editor blueprint


if __name__ == "__main__":
    app.run(debug=True)
