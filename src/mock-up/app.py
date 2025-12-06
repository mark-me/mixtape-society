from pathlib import Path

from flask import Flask, jsonify, render_template, request

from musiclib import MusicCollection

app = Flask(__name__)

MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"

collection = MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH)

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

                displayed_tracks.append({
                    "title": title,
                    "duration": duration
                })

                # Highlighting van track-titel
                if query_lower in title.lower():
                    pos = title.lower().lower().find(query_lower)
                    before = title[:pos]
                    match = title[pos:pos+len(query)]
                    after = title[pos+len(query):]
                    highlighted_tracks.append({
                        "original": {"title": title, "duration": duration},
                        "highlighted": f"{before}<mark>{match}</mark>{after}",
                        "match_type": "track"
                    })
                    if {"type": "track", "text": f"{len(highlighted_tracks)} nummer(s)"} not in reasons:
                        reasons.append({"type": "track", "text": f"{len(highlighted_tracks)} nummer(s)"})

        if reasons:
            results.append({
                "artist": artist,
                "album": "Meerdere albums",   # we tonen geen enkel album want het zijn er meerdere
                "reasons": reasons,
                "tracks": displayed_tracks,
                "highlighted_tracks": highlighted_tracks or None
            })

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
            displayed_tracks.append({"title": title, "duration": duration})

            if query_lower in title.lower():
                pos = title.lower().find(query_lower)
                before = title[:pos]
                match = title[pos:pos + len(query)]
                after = title[pos + len(query):]
                highlighted_tracks.append({
                    "original": {"title": title, "duration": duration},
                    "highlighted": f"{before}<mark>{match}</mark>{after}",
                    "match_type": "track"
                })

        if highlighted_tracks:
            reasons.append({"type": "track", "text": f"{len(highlighted_tracks)} nummer(s)"})

        results.append({
            "artist": artist,
            "album": album,
            "reasons": reasons,
            "tracks": displayed_tracks,
            "highlighted_tracks": highlighted_tracks or None
        })

    # ==== Losse tracks (artiest/albums nog niet getoond) ====
    for track_entry in data["tracks"]:
        artist = track_entry["artist"]
        album = track_entry["album"]
        title = track_entry["track"]

        reasons = [{"type": "track", "text": title}]

        # We maken een enkele track tonen
        duration = track_entry.get("duration", "?:??")
        results.append({
            "artist": artist,
            "album": album,
            "reasons": reasons,
            "tracks": [{"title": title, "duration": duration}],
            "highlighted_tracks": [{
                "original": {"title": title, "duration": duration},
                "highlighted": title.lower().replace(query_lower, f"<mark>{query}</mark>"),
                "match_type": "track"
            }]
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)