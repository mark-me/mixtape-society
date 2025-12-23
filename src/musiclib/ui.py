import re
from pathlib import Path

from .reader import MusicCollection


class MusicCollectionUI(MusicCollection):
    def __init__(self, music_root, db_path, logger=None):
        super().__init__(music_root, db_path, logger)

    @staticmethod
    def _highlight_text(text: str, terms: list[str]) -> str:
        if not terms:
            return text
        sorted_terms = sorted(terms, key=len, reverse=True)
        pattern = "|".join(re.escape(t) for t in sorted_terms if t)
        return re.sub(f"({pattern})", r"<mark>\1</mark>", text, flags=re.I)

    def _track_display_dict(self, track: dict) -> dict:
        return {
            "title": track["track"],
            "duration": track.get("duration") or "?:??",
            "path": track["path"],
            "filename": self._safe_filename(track["track"], track["path"]),
        }

    @staticmethod
    def _safe_filename(title: str, path: str) -> str:
        ext = Path(path).suffix or ""
        safe = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        return f"{safe}{ext}"

    @staticmethod
    def _escape_for_query(name: str) -> str:
        """Escapes a string for use in a search query.

        Returns the input string wrapped in single quotes unless it contains a single quote,
        in which case it is wrapped in double quotes with any double quotes escaped.

        Args:
            name: The string to escape for query usage.

        Returns:
            The escaped string suitable for use in a search query.
        """
        # Prefer single quotes; if name has single quote, fall back to escaped double
        return f"'{name}'" if "'" not in name else f""""{name.replace('"', '"')}\""""

    def search_highlighting(self, query: str, limit: int = 30) -> list[dict]:
        if not query.strip():
            return []

        grouped, terms = self.search_grouped(query, limit=limit)

        all_terms = (
            terms.get("artist", [])
            + terms.get("album", [])
            + terms.get("track", [])
            + terms.get("general", [])
        )
        query_lower = query.lower()
        results = []

        # Artists (summary with match counts, clickable for artist)
        for artist in grouped["artists"]:
            artist_name = artist["artist"]
            highlighted_artist = self._highlight_text(artist_name, all_terms)

            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT COUNT(DISTINCT album) FROM tracks WHERE artist = ? AND (album LIKE ? OR title LIKE ?)",
                    (artist_name, f"%{query_lower}%", f"%{query_lower}%"),
                )
                matched_albums = cur.fetchone()[0] or 0

                cur = conn.execute(
                    "SELECT COUNT(*) FROM tracks WHERE artist = ? AND title LIKE ?",
                    (artist_name, f"%{query_lower}%"),
                )
                matched_tracks = cur.fetchone()[0] or 0

            reasons = []
            if query_lower in artist_name.lower():
                reasons.append({"type": "artist", "text": artist_name})
            if matched_albums:
                reasons.append({"type": "album", "text": f"{matched_albums} album(s)"})
            if matched_tracks:
                reasons.append({"type": "track", "text": f"{matched_tracks} nummer(s)"})

            results.append(
                {
                    "type": "artist",
                    "artist": highlighted_artist,
                    "reasons": reasons,
                    "albums": [],
                    "load_on_demand": True,
                    "clickable": True,
                    "click_query": f"artist:{self._escape_for_query(artist['artist'])}",
                }
            )

        # Albums (summary with match counts, no tracks, clickable for album)
        for album in grouped["albums"]:
            display_artist = album["display_artist"]
            album_name = album["album"]
            is_compilation = album["is_compilation"]
            release_dir = album["release_dir"]

            highlighted_artist = "Various Artists" if is_compilation else self._highlight_text(display_artist, all_terms)
            highlighted_album = self._highlight_text(album_name, all_terms)

            with self._get_conn() as conn:
                cur = conn.execute(
                    """
                    SELECT COUNT(*) FROM tracks
                    WHERE SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) = ?
                    AND title LIKE ?
                    """,
                    (f"{release_dir}/", f"%{query_lower}%"),
                )
                matched_tracks = cur.fetchone()[0] or 0

            reasons = []
            if query_lower in display_artist.lower() and not is_compilation:
                reasons.append({"type": "artist", "text": display_artist})
            if query_lower in album_name.lower():
                reasons.append({"type": "album", "text": album_name})
            if matched_tracks:
                reasons.append({"type": "track", "text": f"{matched_tracks} nummer(s)"})

            results.append({
                "type": "album",
                "artist": highlighted_artist,
                "album": highlighted_album,
                "reasons": reasons,
                "tracks": [],
                "highlighted_tracks": None,
                "load_on_demand": True,
                "is_compilation": is_compilation,
                "clickable": True,
                "click_query": f'release_dir:{self._escape_for_query(release_dir)}',  # Or just provide release_dir
                "artist_click_query": None if is_compilation else f'artist:{self._escape_for_query(display_artist)}',
                "release_dir": release_dir  # For UI to use in lazy load call
            })

        # Tracks (fully populated, with clickable artist and album)
        for track in grouped["tracks"]:
            track_title = track["track"]
            highlighted_track = self._highlight_text(track_title, all_terms)
            highlighted_artist = self._highlight_text(track["artist"], all_terms)
            highlighted_album = self._highlight_text(track["album"], all_terms)

            results.append(
                {
                    "type": "track",
                    "artist": highlighted_artist,
                    "album": highlighted_album,
                    "reasons": [{"type": "track", "text": track_title}],
                    "tracks": [self._track_display_dict(track)],
                    "highlighted_tracks": [
                        {
                            "original": {
                                "title": track_title,
                                "duration": track.get("duration") or "?:??",
                            },
                            "highlighted": highlighted_track,
                            "match_type": "track",
                        }
                    ],
                    "artist_click_query": f"artist:{self._escape_for_query(track['artist'])}",
                    "album_click_query": f"album:{self._escape_for_query(track['album'])}",
                }
            )

        return results
