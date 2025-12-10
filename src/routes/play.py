import mimetypes
from pathlib import Path

from flask import Blueprint, Response, abort, request, send_file

from config import BaseConfig as Config

play = Blueprint("play", __name__, template_folder="templates")


@play.route("/<path:file_path>")
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
    full_path = (Config.MUSIC_ROOT / file_path).resolve()
    try:
        full_path.relative_to(Config.MUSIC_ROOT)
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


# @play.route("/<title>")
# def play_mixtape(title):
#     """
#     Renders the playback page for a mixtape with the given title.

#     Loads the mixtape by title, adds full file paths for streaming, and renders the playback template. Returns a 404 error if the mixtape is not found.

#     Args:
#         title: The title of the mixtape to play.

#     Returns:
#         Response: The rendered playback page or a 404 error if not found.
#     """
#     music_collection = MusicCollection(
#         music_root=Config.MUSIC_ROOT, db_path=Config.DB_PATH
#     )
#     mixtapes = music_collection.load_mixtapes()
#     mixtape = next((m for m in mixtapes if m["title"] == title), None)
#     if not mixtape:
#         return "Mixtape not found", 404

#     # Voeg full paths toe voor streaming
#     for track in mixtape["tracks"]:
#         track["full_path"] = Config.MUSIC_ROOT / track["path"]

#     return render_template("play.html", mixtape=mixtape)
