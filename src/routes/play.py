import mimetypes
from pathlib import Path

from flask import Blueprint, Response, abort, render_template, request, send_file

from config import BaseConfig as Config
from mixtape_manager import MixtapeManager

play = Blueprint("play", __name__, template_folder="templates")

mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/aac", ".aac")
mimetypes.add_type("audio/ogg", ".ogg")


@play.route("/<path:file_path>")
def stream_audio(file_path: str) -> Response:
    """
    Streams an audio file from the music directory to the client.

    Validates the file path, determines the correct MIME type, and supports HTTP range requests for seeking.
    Returns the requested audio file or an appropriate error if the file is not found or access is denied.

    Args:
        file_path: The relative path to the audio file within the music directory.

    Returns:
        Response: The Flask response object streaming the audio file or an error response.
    """
    full_path = _resolve_and_validate_path(file_path)
    mime_type = _guess_mime_type(full_path)
    file_size = full_path.stat().st_size

    if range_header := request.headers.get("Range"):
        return _handle_range_request(full_path, mime_type, range_header, file_size)

    # Full file request
    response = send_file(full_path, mimetype=mime_type, download_name=full_path.name)
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-cache"
    return response


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
    full_path: Path, mime_type: str, range_header: str, file_size: int
) -> Response:
    try:
        range_match = range_header.replace("bytes=", "")
        byte1_str, byte2_str = (range_match.split("-") + [""])[:2]
        byte1 = int(byte1_str) if byte1_str else 0
        byte2 = int(byte2_str) if byte2_str else file_size - 1

        if byte1 >= file_size or byte2 >= file_size or byte1 < 0:
            return Response("Range Not Satisfiable", 416)

        length = byte2 - byte1 + 1

        with open(full_path, "rb") as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data, 206, mimetype=mime_type, direct_passthrough=True)
        rv.headers.update(
            {
                "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            }
        )
        return rv
    except Exception:
        abort(500)


@play.route("/share/<slug>")
def public_play(slug: str) -> Response:
    """
    Renders the public mixtape playback page for a given slug.

    Retrieves the mixtape by slug and displays it for public playback, or returns a 404 error if not found.

    Args:
        slug: The unique identifier for the mixtape.

    Returns:
        Response: The Flask response object containing the rendered mixtape playback page.
    """
    mixtape_manager = MixtapeManager(path_mixtapes=Config.MIXTAPE_DIR)
    mixtape = mixtape_manager.get(slug)
    if not mixtape:
        abort(404)
    return render_template("play_mixtape.html", mixtape=mixtape, public=True)
