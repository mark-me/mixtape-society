import mimetypes
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
    query = request.args.get("q", "").lower().strip()
    if len(query) < 2:
        return jsonify([])

    query_lower = query.lower()

    results = []

    data = collection.search_grouped(query, limit=30)

    # ==== Artiesten die matchen ====
    for artist_entry in data["artists"]:
        artist = artist_entry["artist"]

        reasons = [{"type": "artist", "text": artist}]

        # Alle albums van deze artiest (met hun tracks)
        displayed_tracks = []
        highlighted_tracks = []

        for album_entry in artist_entry.get("albums", []):
            album = album_entry["album"]
            if query_lower in album.lower():
                reasons.append({"type": "album", "text": album})

            for track in album_entry.get("tracks", []):
                title = track["track"]
                duration = track.get("duration")
                if not duration:  # fallback als tinytag geen duur kon lezen
                    duration = "?:??"

                rel_path = str(Path(track["path"]).relative_to(MUSIC_ROOT))

                displayed_tracks.append({
                    "title": title,
                    "duration": duration,
                    "path": rel_path,
                    "filename": track["filename"]
                })

                # Highlighting van track-titel
                if query_lower in title.lower():
                    pos = title.lower().lower().find(query_lower)
                    before = title[:pos]
                    match = title[pos : pos + len(query)]
                    after = title[pos + len(query) :]
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

        if reasons:
            results.append(
                {
                    "artist": artist,
                    "album": "Meerdere albums",  # we tonen geen enkel album want het zijn er meerdere
                    "reasons": reasons,
                    "tracks": displayed_tracks,
                    "highlighted_tracks": highlighted_tracks or None,
                }
            )

    # ==== Albums die matchen (maar artiest nog niet getoond) ====
    for album_entry in data["albums"]:
        artist = album_entry["artist"]
        album = album_entry["album"]

        reasons = []
        if query_lower in artist.lower():
            reasons.append({"type": "artist", "text": artist})
        if query_lower in album.lower():
            reasons.append({"type": "album", "text": album})

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
                match = title[pos : pos + len(query)]
                after = title[pos + len(query) :]
                highlighted_tracks.append(
                    {
                        "original": {"title": title, "duration": duration},
                        "highlighted": f"{before}<mark>{match}</mark>{after}",
                        "match_type": "track",
                    }
                )

        if highlighted_tracks:
            reasons.append(
                {"type": "track", "text": f"{len(highlighted_tracks)} nummer(s)"}
            )

        results.append(
            {
                "artist": artist,
                "album": album,
                "reasons": reasons,
                "tracks": displayed_tracks,
                "highlighted_tracks": highlighted_tracks or None,
            }
        )

    # ==== Losse tracks (artiest/albums nog niet getoond) ====
    for track_entry in data["tracks"]:
        artist = track_entry["artist"]
        album = track_entry["album"]
        title = track_entry["track"]

        reasons = [{"type": "track", "text": title}]

        # We maken een enkele track tonen
        duration = track_entry.get("duration", "?:??")
        results.append(
            {
                "artist": artist,
                "album": album,
                "reasons": reasons,
                "tracks": [
                    {
                        "title": title,
                        "duration": duration,
                        "path": track_entry.get("path", ""),
                        "filename": track_entry.get(
                            "filename",
                            title
                            + (Path(track_entry.get("path", "")).suffix or ".mp3"),
                        ),
                    }
                ],
                "highlighted_tracks": [
                    {
                        "original": {"title": title, "duration": duration},
                        "highlighted": title.lower().replace(
                            query_lower, f"<mark>{query}</mark>"
                        ),
                        "match_type": "track",
                    }
                ],
            }
        )

    return jsonify(results)


@app.route("/play/<path:file_path>")
def play(file_path):
    full_path = (MUSIC_ROOT / file_path).resolve()

    # Security: voorkom directory traversal
    try:
        full_path.relative_to(MUSIC_ROOT)
    except ValueError:
        abort(403)

    if not full_path.is_file():
        abort(404)

    # MIME-type correct afleiden (cruciaal!)
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        # Handmatige fallback voor veelvoorkomende types
        suffix = full_path.suffix.lower()
        mime_type = {
            '.mp3':  'audio/mpeg',
            '.flac': 'audio/flac',
            '.m4a':  'audio/mp4',
            '.aac':  'audio/aac',
            '.ogg':  'audio/ogg',
            '.wav':  'audio/wav',
            '.wma':  'audio/x-ms-wma',
        }.get(suffix, 'application/octet-stream')

    # Range requests ondersteunen (noodzakelijk voor seeking)
    range_header = request.headers.get('Range')
    file_size = full_path.stat().st_size

    if range_header:
        # Voorbeeld Range: "bytes=0-" of "bytes=1048576-"
        start = 0
        end = file_size - 1
        if range_header.startswith('bytes='):
            parts = range_header[6:].split('-')
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])

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

    # Normale request
    return send_file(
        full_path,
        mimetype=mime_type,
        as_attachment=False,
        download_name=full_path.name,
    )


if __name__ == "__main__":
    app.run(debug=True)
