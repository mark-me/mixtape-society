import re
from pathlib import Path

from .reader import MusicCollection


class MusicCollectionUI(MusicCollection):
    """Extends MusicCollection to provide UI-specific search and highlighting features.
    Adds methods for formatting, escaping, and highlighting search results for user interfaces.
    """
    def __init__(self, music_root, db_path, logger=None):
        """Initializes the MusicCollectionUI with the given music root, database path, and optional logger.
        Sets up the UI-specific extension of the music collection functionality.

        Args:
            music_root: Path to the root directory containing music files.
            db_path: Path to the SQLite database file.
            logger: Optional logger instance.

        Returns:
            None
        """
        super().__init__(music_root, db_path, logger)

    @staticmethod
    def _highlight_text(text: str, terms: list[str]) -> str:
        """Highlights all occurrences of search terms in the given text for UI display.
        Wraps matching terms in <mark> tags to visually emphasize them in the interface.

        Args:
            text: The text to highlight.
            terms: List of search terms to highlight in the text.

        Returns:
            str: The text with matching terms wrapped in <mark> tags.
        """
        if not terms:
            return text
        sorted_terms = sorted(terms, key=len, reverse=True)
        pattern = "|".join(re.escape(t) for t in sorted_terms if t)
        return re.sub(f"({pattern})", r"<mark>\1</mark>", text, flags=re.I)

    def _track_display_dict(self, track: dict) -> dict:
        """Formats a track dictionary for UI display.
        Returns a dictionary with title, duration, path, and a safe filename for the track.

        Args:
            track: Dictionary containing track information.

        Returns:
            dict: Dictionary with formatted track details for UI display.
        """
        return {
            "title": track["title"],
            "duration": track.get("duration") or "?:??",
            "path": track["path"],
            "filename": self._safe_filename(track["title"], track["path"]),
        }

    @staticmethod
    def _safe_filename(title: str, path: str) -> str:
        """Generates a safe filename for a track by sanitizing the title and preserving the file extension.
        Removes unsafe characters from the title and appends the original file extension.

        Args:
            title: The track title to sanitize.
            path: The original file path to extract the extension.

        Returns:
            str: A safe filename suitable for saving or displaying.
        """
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
        """Performs a search and returns results with highlighted matching terms for UI display.
        Groups and highlights artists, albums, and tracks based on the search query and terms.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            list[dict]: List of dictionaries containing highlighted search results for artists, albums, and tracks.
        """
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
                    "raw_artist": artist_name,
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
                "raw_artist": display_artist,
                "artist": highlighted_artist,
                "raw_album": album_name,
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
            track_title = track["title"]
            highlighted_track = self._highlight_text(track_title, all_terms)
            highlighted_artist = self._highlight_text(track["artist"], all_terms)
            highlighted_album = self._highlight_text(track["album"], all_terms)

            results.append(
                {
                    "type": "track",
                    "raw_artist": track["artist"],
                    "artist": highlighted_artist,
                    "raw_album": track["album"],
                    "album": highlighted_album,
                    "reasons": [{"type": "track", "text": track_title}],
                    "tracks": [self._track_display_dict(track)],
                    "highlighted_tracks": [
                        {
                            "original": {
                                "title": track_title,
                                "duration": self._format_duration(track.get("duration")),
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
