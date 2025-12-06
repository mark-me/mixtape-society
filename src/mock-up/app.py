import mimetypes
import re
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from musiclib import MusicCollection

app = Flask(__name__)

MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"

collection = MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH)

mimetypes.add_type('audio/flac', '.flac')
mimetypes.add_type('audio/mp4',  '.m4a')
mimetypes.add_type('audio/aac',  '.aac')
mimetypes.add_type('audio/ogg',  '.ogg')

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    """
    Handles search requests for the music collection.

    Processes the search query, finds matching artists, albums, and tracks, and returns results as a JSON response with highlighting and grouping.

    Returns:
        Response: A Flask JSON response containing the search results.
    """
    query = request.args.get("q", "").lower().strip()
    if len(query) < 2:
        return jsonify([])

    query_lower = query.lower()
    data = collection.search_grouped(query, limit=30)

    results = []
    results.extend(_search_artist_results(data["artists"], query_lower))
    results.extend(_search_album_results(data["albums"], query_lower))
    results.extend(_search_track_results(data["tracks"], query_lower))

    return jsonify(results)


def _search_artist_results(artists, query_lower):
    """
    Processes artist search results and formats them for the response.

    Iterates over artists, processes their albums and tracks, and returns a list of formatted result dictionaries.

    Args:
        artists: List of artist entries from the search.
        query_lower: Lowercase search query string.

    Returns:
        list: A list of formatted artist result dictionaries.
    """
    results = []
    results.extend(
        _format_artist_result(artist_entry, query_lower)
        for artist_entry in artists
    )
    return results

def _format_artist_result(artist_entry, query_lower):
    """
    Formats a single artist's search result for the response.

    Builds a result dictionary for the artist, including reasons, tracks, and highlighted tracks.

    Args:
        artist_entry: The artist entry dictionary from the search results.
        query_lower: Lowercase search query string.

    Returns:
        dict: A formatted artist result dictionary.
    """
    artist = artist_entry["artist"]
    reasons = [{"type": "artist", "text": artist}]
    displayed_tracks, highlighted_tracks = _process_artist_albums(artist_entry, query_lower)
    return {
        "artist": artist,
        "album": "Meerdere albums",
        "reasons": reasons,
        "tracks": displayed_tracks,
        "highlighted_tracks": highlighted_tracks or None,
    }

def _process_artist_albums(artist_entry, query_lower):
    """
    Processes albums and tracks for a given artist entry.

    Iterates through the artist's albums and tracks, building lists of displayed tracks and highlighted tracks for search results.

    Args:
        artist_entry: The artist entry dictionary containing albums and tracks.
        query_lower: Lowercase search query string.

    Returns:
        tuple: A tuple containing the list of displayed tracks and highlighted tracks.
    """
    displayed_tracks = []
    highlighted_tracks = []
    reasons = [{"type": "artist", "text": artist_entry["artist"]}]
    for album_entry in artist_entry.get("albums", []):
        album = album_entry["album"]
        if query_lower in album.lower():
            reasons.append({"type": "album", "text": album})

        for track in album_entry.get("tracks", []):
            title = track["track"]
            duration = track.get("duration") or "?:??"
            rel_path = str(Path(track["path"]).relative_to(MUSIC_ROOT))
            displayed_tracks.append({
                "title": title,
                "duration": duration,
                "path": rel_path,
                "filename": track["filename"]
            })
            if query_lower in title.lower():
                pos = title.lower().find(query_lower)
                before = title[:pos]
                match = title[pos : pos + len(query_lower)]
                after = title[pos + len(query_lower) :]
                highlighted_tracks.append(
                    {
                        "original": {"title": title, "duration": duration},
                        "highlighted": f"{before}<mark>{match}</mark>{after}",
                        "match_type": "track",
                    }
                )
                if {
                    "type": "track",
                    "text": f"{len(highlighted_tracks)} nummer(s)",
                } not in reasons:
                    reasons.append(
                        {
                            "type": "track",
                            "text": f"{len(highlighted_tracks)} nummer(s)",
                        }
                    )
    return displayed_tracks, highlighted_tracks


def _search_album_results(albums, query_lower):
    """
    Processes album search results and formats them for the response.

    Iterates over albums, formats each album's result dictionary, and returns a list of formatted album result dictionaries.

    Args:
        albums: List of album entries from the search.
        query_lower: Lowercase search query string.

    Returns:
        list: A list of formatted album result dictionaries.
    """
    results = []
    for album_entry in albums:
        results.append(_format_album_result(album_entry, query_lower))
    return results

def _format_album_result(album_entry, query_lower):
    """
    Formats a single album's search result for the response.

    Builds a result dictionary for the album, including reasons, tracks, and highlighted tracks.

    Args:
        album_entry: The album entry dictionary from the search results.
        query_lower: Lowercase search query string.

    Returns:
        dict: A formatted album result dictionary.
    """
    artist = album_entry["artist"]
    album = album_entry["album"]
    reasons = _get_album_reasons(artist, album, query_lower)
    displayed_tracks, highlighted_tracks = _process_album_tracks(album_entry, query_lower)
    if highlighted_tracks:
        reasons.append({"type": "track", "text": f"{len(highlighted_tracks)} nummer(s)"})
    return {
        "artist": artist,
        "album": album,
        "reasons": reasons,
        "tracks": displayed_tracks,
        "highlighted_tracks": highlighted_tracks or None,
    }

def _get_album_reasons(artist, album, query_lower):
    """
    Determines the reasons for an album match based on the search query.

    Checks if the query matches the artist or album name and returns a list of reason dictionaries.

    Args:
        artist: The artist name.
        album: The album name.
        query_lower: Lowercase search query string.

    Returns:
        list: A list of reason dictionaries for the album match.
    """
    reasons = []
    if query_lower in artist.lower():
        reasons.append({"type": "artist", "text": artist})
    if query_lower in album.lower():
        reasons.append({"type": "album", "text": album})
    return reasons

def _process_album_tracks(album_entry, query_lower):
    """
    Processes tracks for a given album entry.

    Iterates through the album's tracks, building lists of displayed tracks and highlighted tracks for search results.

    Args:
        album_entry: The album entry dictionary containing tracks.
        query_lower: Lowercase search query string.

    Returns:
        tuple: A tuple containing the list of displayed tracks and highlighted tracks.
    """
    displayed_tracks = []
    highlighted_tracks = []
    for track in album_entry.get("tracks", []):
        title = track["track"]
        duration = track.get("duration", "?:??")
        rel_path = str(Path(track["path"]).relative_to(MUSIC_ROOT))
        displayed_tracks.append({
            "title": title,
            "duration": duration,
            "path": rel_path,
            "filename": track["filename"]
        })
        if query_lower in title.lower():
            pos = title.lower().find(query_lower)
            before = title[:pos]
            match = title[pos : pos + len(query_lower)]
            after = title[pos + len(query_lower) :]
            highlighted_tracks.append(
                {
                    "original": {"title": title, "duration": duration},
                    "highlighted": f"{before}<mark>{match}</mark>{after}",
                    "match_type": "track",
                }
            )
    return displayed_tracks, highlighted_tracks


def _search_track_results(tracks, query_lower):
    """
    Processes track search results and formats them for the response.

    Iterates over tracks, formats each track's result dictionary, and returns a list of formatted track result dictionaries.

    Args:
        tracks: List of track entries from the search.
        query_lower: Lowercase search query string.

    Returns:
        list: A list of formatted track result dictionaries.
    """
    results = []
    results.extend(
        _format_track_result(track_entry, query_lower)
        for track_entry in tracks
    )
    return results

def _format_track_result(track_entry, query_lower):
    """
    Formats a single track's search result for the response.

    Builds a result dictionary for the track, including reasons, track details, and highlighted track information.

    Args:
        track_entry: The track entry dictionary from the search results.
        query_lower: Lowercase search query string.

    Returns:
        dict: A formatted track result dictionary.
    """
    artist = track_entry["artist"]
    album = track_entry["album"]
    title = track_entry["track"]
    reasons = [{"type": "track", "text": title}]
    duration = track_entry.get("duration", "?:??")
    track_path = track_entry.get("path", "")
    filename = _get_track_filename(track_entry, title, track_path)
    highlighted = _highlight_track_title(title, duration, query_lower)
    return {
        "artist": artist,
        "album": album,
        "reasons": reasons,
        "tracks": [
            {
                "title": title,
                "duration": duration,
                "path": track_path,
                "filename": filename,
            }
        ],
        "highlighted_tracks": [highlighted],
    }

def _get_track_filename(track_entry, title, track_path):
    """
    Determines the filename for a track entry.

    Uses the filename from the track entry if available, otherwise constructs it from the title and file extension.

    Args:
        track_entry: The track entry dictionary.
        title: The track title.
        track_path: The track's file path.

    Returns:
        str: The filename for the track.
    """
    return track_entry.get(
        "filename",
        title + (Path(track_path).suffix or ".mp3"),
    )

def _highlight_track_title(title, duration, query_lower):
    """
    Highlights the search query within a track title for the response.

    Returns a dictionary containing the original title and duration, the highlighted title, and the match type.

    Args:
        title: The track title.
        duration: The track duration.
        query_lower: Lowercase search query string.

    Returns:
        dict: A dictionary with original and highlighted track information.
    """
    def highlight_query(text, query):
        # Use re.IGNORECASE to find all case-insensitive matches and wrap them in <mark>
        def repl(match):
            return f"<mark>{match.group(0)}</mark>"
        return re.sub(re.escape(query), repl, text, flags=re.IGNORECASE)

    highlighted_title = highlight_query(title, query_lower)
    return {
        "original": {"title": title, "duration": duration},
        "highlighted": highlighted_title,
        "match_type": "track",
    }


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
    range_header = request.headers.get('Range')
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
        '.mp3':  'audio/mpeg',
        '.flac': 'audio/flac',
        '.m4a':  'audio/mp4',
        '.aac':  'audio/aac',
        '.ogg':  'audio/ogg',
        '.wav':  'audio/wav',
        '.wma':  'audio/x-ms-wma',
    }.get(suffix, 'application/octet-stream')

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
    response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Length'] = end - start + 1
    return response

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
    if range_header.startswith('bytes='):
        parts = range_header[6:].split('-')
        if parts[0]:
            start = int(parts[0])
        if len(parts) > 1 and parts[1]:
            end = int(parts[1])
    return start, end


if __name__ == "__main__":
    app.run(debug=True)
