import json
import mimetypes
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

from musiclib import MusicCollection
from routes import browser, play

app = Flask(__name__)
app.register_blueprint(browser)
app.register_blueprint(play)

MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"
MIXTAPE_DIR = Path(__file__).parent.parent / "mixtapes"
COVER_DIR = MIXTAPE_DIR.parent.parent / "covers"
MIXTAPE_DIR.mkdir(exist_ok=True)
COVER_DIR.mkdir(exist_ok=True)

collection = MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH)

mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/aac", ".aac")
mimetypes.add_type("audio/ogg", ".ogg")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    # 1. Haal ruwe resultaten op (geen highlighting nog)
    raw_results = collection.search_highlighting(query, limit=30)

    # 2. Voeg alleen <mark> tags toe waar nodig (dit blijft in Flask)
    def finalize_highlight(item: dict) -> dict:
        # highlighted_tracks krijgen al een kant-en-klare string,
        # maar we zorgen er nog even voor dat alles netjes is
        if item.get("highlighted_tracks"):
            for ht in item["highlighted_tracks"]:
                if "highlighted" in ht:
                    # eventueel nog extra highlighting op artist/album naam
                    pass
        return item

    results = [finalize_highlight(r) for r in raw_results]
    return jsonify(results)


@app.route("/play/<path:file_path>")
def play(file_path):
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
    return {"now": datetime.now(timezone.utc)}


@app.route("/edit/<slug>")
def edit_mixtape(slug):
    json_path = MIXTAPE_DIR / f"{slug}.json"
    if not json_path.exists():
        abort(404)
    with open(json_path, "r", encoding="utf-8") as f:
        mixtape = json.load(f)

    # Render index.html maar met data voor JavaScript
    return render_template("index.html", preload_mixtape=mixtape)


@app.route("/mixtapes/files/<path:filename>")
def mixtape_files(filename):
    return send_from_directory(MIXTAPE_DIR, filename)


@app.route("/save_mixtape", methods=["POST"])
def save_mixtape():
    try:
        data = request.get_json()
        if not data or not data.get("tracks"):
            return jsonify({"error": "Lege of ongeldige playlist"}), 400

        title = data.get("title", "Onbenoemde Playlist").strip()
        if not title:
            title = "Onbenoemde Playlist"

        # Sanitize bestandsnaam (veilig voor filesystem)
        safe_title = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)
        json_path = MIXTAPE_DIR / f"{safe_title}.json"

        # Cover opslaan (base64 → jpg)
        cover_path = None
        if data.get("cover") and data["cover"].startswith("data:image"):
            header, b64data = data["cover"].split(",", 1)
            img_data = b64decode(b64data)
            cover_path = COVER_DIR / f"{safe_title}.jpg"
            with open(cover_path, "wb") as f:
                f.write(img_data)
            data["cover"] = (
                f"covers/{safe_title}.jpg"  # relatief pad voor later gebruik
            )
        else:
            data["cover"] = None

        # Extra metadata
        data["saved_at"] = datetime.now().isoformat()
        data["original_title"] = title  # mooie titel behouden

        # Opslaan als JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return jsonify({"success": True, "title": title, "filename": safe_title})

    except Exception as e:
        print("Fout bij opslaan mixtape:", e)  # zie console
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
