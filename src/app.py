import json
import mimetypes
import secrets
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
)

from logtools import get_logger
from mixtape_manager import MixtapeManager
from musiclib import MusicCollection
from auth import check_auth, require_auth
from routes import browser, play

logger = get_logger(name=__name__)

MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"
MIXTAPE_DIR = Path(__file__).parent.parent / "mixtapes"
COVER_DIR = MIXTAPE_DIR / "covers"
MIXTAPE_DIR.mkdir(exist_ok=True)
COVER_DIR.mkdir(exist_ok=True)
PASSWORD = "password"  # Change this to a secure value or use env var

app = Flask(__name__)
app.secret_key = PASSWORD

collection = MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH)

mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/aac", ".aac")
mimetypes.add_type("audio/ogg", ".ogg")


@app.route("/")
def landing():
    """
    Renders the landing page or redirects authenticated users.

    If the user is authenticated, redirects to the mixtapes page; otherwise, renders the landing.html template.

    Returns:
        Response: A redirect to the mixtapes page or a rendered landing.html template.
    """
    if check_auth():
        return redirect("/mixtapes")
    return render_template("landing.html")


@app.route("/login", methods=["POST"])
def login():
    """
    Authenticates the user based on the submitted password.

    If the password is correct, sets the session as authenticated and redirects to the mixtapes page. Otherwise, flashes an error message and redirects to the home page.

    Returns:
        Response: A redirect to the mixtapes page on success, or to the home page with an error message on failure.
    """
    if request.form.get("password") == PASSWORD:
        session["authenticated"] = True
        return redirect("/mixtapes")
    flash("Verkeerd wachtwoord")
    return redirect("/")


@app.route("/logout")
def logout():
    """
    Logs out the current user by removing authentication from the session.

    Clears the 'authenticated' flag from the session and redirects to the home page.

    Returns:
        Response: A redirect to the home page.
    """
    session.pop("authenticated", None)
    return redirect("/")


@app.route("/search")
def search():
    """
    Searches the music collection for tracks matching the query.

    Retrieves search results with highlighting and returns them as a JSON response.

    Returns:
        Response: A JSON response containing the search results.
    """
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    raw_results = collection.search_highlighting(query, limit=30)
    results = [_finalize_highlight(r) for r in raw_results]
    return jsonify(results)


def _finalize_highlight(item: dict) -> dict:
    """
    Finalizes highlighting for search result items.

    Ensures highlighted tracks are properly formatted for display.

    Args:
        item: A dictionary representing a search result item.

    Returns:
        dict: The processed search result item.
    """
    if item.get("highlighted_tracks"):
        for ht in item["highlighted_tracks"]:
            if "highlighted" in ht:
                pass
    return item


@app.route("/play/<path:file_path>")
def stream_audio(file_path):
    """
    Handles requests to play a music file from the collection.

    Resolves the requested file path, checks for security and existence, determines the correct MIME type, and supports HTTP range requests for seeking.
    Returns the file as a Flask response.

    Args:
        file_path: The relative path of the music file to play.

    Returns:
        Response: A Flask response streaming the requested music file.
    """
    full_path = (MUSIC_ROOT / file_path).resolve()
    _check_path_security(full_path)
    _check_file_exists(full_path)
    mime_type = _get_mime_type(full_path)
    range_header = request.headers.get("Range")
    file_size = full_path.stat().st_size

    if range_header:
        return _send_range_response(full_path, mime_type, range_header, file_size)

    return send_file(
        full_path,
        mimetype=mime_type,
        as_attachment=False,
        download_name=full_path.name,
    )


def _check_path_security(full_path: Path):
    """
    Checks if the given file path is within the allowed music root directory.

    Prevents directory traversal attacks by aborting with a 403 error if the path is outside the music root.

    Args:
        full_path: The absolute path to check.

    Returns:
        None
    """
    try:
        full_path.relative_to(MUSIC_ROOT)
    except ValueError:
        abort(403)


def _check_file_exists(full_path: Path):
    """
    Checks if the given file exists at the specified path.

    Aborts with a 404 error if the file does not exist.

    Args:
        full_path: The absolute path to the file.

    Returns:
        None
    """
    if not full_path.is_file():
        abort(404)


def _get_mime_type(full_path: Path):
    """
    Determines the MIME type for a given file path.

    Uses the mimetypes library to guess the MIME type, with a manual fallback for common audio file types.

    Args:
        full_path: The absolute path to the file.

    Returns:
        str: The MIME type for the file.
    """
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        suffix = full_path.suffix.lower()
        mime_type = _get_fallback_mime_type(suffix)
    return mime_type


def _get_fallback_mime_type(suffix):
    """
    Returns a fallback MIME type for common audio file extensions.

    Args:
        suffix: The file extension (including dot).

    Returns:
        str: The fallback MIME type for the file.
    """
    return {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".wma": "audio/x-ms-wma",
    }.get(suffix, "application/octet-stream")


def _send_range_response(full_path: Path, mime_type, range_header, file_size):
    """
    Sends a partial content response for HTTP range requests.

    Parses the range header, prepares the response with appropriate headers, and returns the file as a Flask response.

    Args:
        full_path: The absolute path to the file.
        mime_type: The MIME type of the file.
        range_header: The value of the HTTP Range header.
        file_size: The total size of the file in bytes.

    Returns:
        Response: A Flask response streaming the requested byte range of the file.
    """
    start, end = _parse_range_header(range_header, file_size)
    response = send_file(
        full_path,
        mimetype=mime_type,
        conditional=True,
        as_attachment=False,
        max_age=0,
    )
    response.status_code = 206
    response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Content-Length"] = end - start + 1
    return response


def _parse_range_header(range_header, file_size):
    """
    Parses the HTTP Range header to determine the start and end byte positions.

    Extracts the byte range from the header for partial file serving. Returns None if the header is malformed.

    Args:
        range_header: The value of the HTTP Range header.
        file_size: The total size of the file in bytes.

    Returns:
        tuple: (start, end) byte positions, or None if the header is malformed.
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    try:
        range_spec = range_header.split("=")[1]
        start_str, end_str = range_spec.split("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        if start > end or end >= file_size or start < 0:
            return None
        return (start, end)
    except Exception:
        return None


def _parse_range_header(range_header, file_size):
    """
    Parses the HTTP Range header to determine the start and end byte positions.

    Extracts the byte range from the header for partial file serving, defaulting to the full file if not specified.

    Args:
        range_header: The value of the HTTP Range header.
        file_size: The total size of the file in bytes.

    Returns:
        tuple: A tuple (start, end) representing the byte range to serve.
    """
    start = 0
    end = file_size - 1
    if range_header.startswith("bytes="):
        try:
            parts = range_header[6:].split("-")
            if len(parts) != 2:
                raise ValueError("Malformed Range header: wrong number of parts")
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])
            if start > end or start < 0 or end >= file_size:
                raise ValueError("Malformed Range header: invalid range values")
        except (ValueError, IndexError):
            # Fallback to full file if header is malformed
            start = 0
            end = file_size - 1
    return start, end


@app.context_processor
def inject_now():
    """
    Injects the current UTC datetime into the template context.

    This allows templates to access the current time using the 'now' variable.

    Returns:
        dict: A dictionary with the current UTC datetime under the key 'now'.
    """
    return {"now": datetime.now(timezone.utc)}


@app.route("/edit/<slug>")
@require_auth
def edit_mixtape(slug):
    """
    Loads a mixtape by its slug and renders the index page with its data.

    Retrieves the mixtape JSON file, aborts with 404 if not found, and passes the mixtape data to the template for JavaScript use.

    Args:
        slug: The unique identifier for the mixtape.

    Returns:
        Response: A rendered template with the mixtape data preloaded.
    """
    json_path = MIXTAPE_DIR / f"{slug}.json"
    if not json_path.exists():
        abort(404)
    with open(json_path, "r", encoding="utf-8") as f:
        mixtape = json.load(f)
    return render_template("index.html", preload_mixtape=mixtape)


@app.route("/mixtapes/files/<path:filename>")
def mixtape_files(filename):
    """
    Serves a mixtape file from the mixtape directory.

    Returns the requested file as a Flask response for download or streaming.

    Args:
        filename: The path to the mixtape file within the mixtape directory.

    Returns:
        Response: A Flask response serving the requested file.
    """
    return send_from_directory(MIXTAPE_DIR, filename)


@app.route("/save_mixtape", methods=["POST"])
def save_mixtape():
    """
    Saves a mixtape sent via POST request to the server.

    Validates the mixtape data, generates a unique slug, processes the cover image if present, adds metadata, and stores the mixtape as a JSON file.
    Returns a success response with the mixtape's details or an error message if saving fails.

    Returns:
        Response: A JSON response indicating success or failure, including the mixtape title, slug, and edit URL on success.
    """
    try:
        data = request.get_json()
        if not data or not data.get("tracks"):
            return jsonify({"error": "Lege playlist"}), 400

        original_title = (
            data.get("title", "Onbenoemde Playlist").strip() or "Onbenoemde Playlist"
        )

        # ALTIJD UNIEK — geen overschrijven meer!
        slug = _generate_slug(original_title)  # ← dit is nieuw en veilig
        json_path = MIXTAPE_DIR / f"{slug}.json"

        # Cover opslaan (ook met unieke naam)
        data["cover"] = _process_cover(data.get("cover"), slug)

        # Metadata
        data["title"] = original_title
        data["slug"] = slug
        data["saved_at"] = datetime.now().isoformat()

        _save_mixtape_json(json_path, data)

        return jsonify(
            {
                "success": True,
                "title": original_title,
                "slug": slug,
                "url": f"/edit/{slug}",  # handige directe link
            }
        )

    except Exception as e:
        logger.exception("Fout bij opslaan mixtape")
        return jsonify({"error": "Serverfout bij opslaan"}), 500


def _generate_slug(title: str) -> str:
    """
    Generates a unique slug for a mixtape based on its title.

    Sanitizes the title for safe use, appends a timestamp and a random token to ensure uniqueness.

    Args:
        title: The mixtape title to base the slug on.

    Returns:
        str: A unique, sanitized slug for the mixtape.
    """
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title.strip())
    safe = safe.strip("_- ") or "mixtape"
    token = secrets.token_urlsafe(8)
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{safe}_{timestamp}_{token}"


def _process_cover(cover_data, slug: str):
    """
    Processes the cover image data and saves it as a JPEG file.

    Decodes the base64 image data and writes it to the covers directory if present. Returns the relative path to the saved cover image or None if no valid image is provided.

    Args:
        cover_data: The base64-encoded image data string.
        slug: The sanitized title or slug used for the filename.

    Returns:
        str or None: The relative path to the saved cover image, or None if not applicable.
    """
    if not cover_data or not cover_data.startswith("data:image"):
        return None

    try:
        header, b64data = cover_data.split(",", 1)
        img_data = b64decode(b64data)

        cover_path = COVER_DIR / f"{slug}.jpg"
        with open(cover_path, "wb") as f:
            f.write(img_data)

        return f"covers/{slug}.jpg"
    except Exception as e:
        logger.error(f"Cover opslaan mislukt voor {slug}: {e}")
        return None


@app.route("/covers/<filename>")
def serve_cover(filename):
    """
    Serves a cover image file from the covers directory.

    Returns the requested cover image as a Flask response for download or display.

    Args:
        filename: The name of the cover image file to serve.

    Returns:
        Response: A Flask response serving the requested cover image file.
    """
    return send_from_directory(COVER_DIR, filename)


def _save_mixtape_json(json_path, data):
    """
    Saves the mixtape data as a JSON file at the specified path.

    Writes the provided data dictionary to a file in JSON format with UTF-8 encoding.

    Args:
        json_path: The path where the JSON file will be saved.
        data: The mixtape data to serialize and save.

    Returns:
        None
    """
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# === Publieke share route (NIEUW!) ===
@app.route("/share/<slug>")
def public_play(slug):
    mixtape_manager = MixtapeManager(path_mixtapes=MIXTAPE_DIR)
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    return render_template("play_mixtape.html", mixtape=mixtape, public=True)


# === Register blueprints ===
app.register_blueprint(browser)
app.register_blueprint(play)


if __name__ == "__main__":
    app.run(debug=True)
