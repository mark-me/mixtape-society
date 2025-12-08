import re
import contextlib
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from ._extractor import CollectionExtractor  # internal implementation


class MusicCollection:
    """
    High-level interface to a music library.

    As long as an instance exists:
    - The database is kept in sync with the filesystem
    - Live file monitoring is active
    - At startup, any drift is automatically repaired

    Usage:
        collection = MusicCollection("/home/user/Music")
        for track in collection.search(artist="Radiohead"):
            print(track["title"])
    """

    def __init__(
        self,
        music_root: Path | str,
        db_path: Path | str,
    ):
        """
        Initializes a MusicCollection instance for managing a music library.

        Sets up the music root directory, database path, and ensures the database is in sync with the filesystem. Starts live monitoring and repairs any drift on startup.

        Args:
            music_root: The root directory containing music files.
            db_path: Optional path to the SQLite database file. If not provided, a default path is used.
        """
        self._extractor = CollectionExtractor(
            music_root=Path(music_root),
            db_path=Path(db_path) if db_path else None,
        )
        self.music_root = Path(music_root)

        track_count = self._extractor.count_tracks()
        if track_count == 0:
            # Brand new database — force full indexing
            print("No tracks in database — performing initial scan...")
            self._extractor.rebuild()
        elif not self._extractor.is_synced_with_filesystem():
            print("Database out of sync — repairing...")
            self._extractor.resync()
        # Start background monitoring (will stop on __del__ or close())
        self._extractor.start_monitoring()

        # Ensure DB is in sync with filesystem on startup
        if not self._extractor.is_synced_with_filesystem():
            print("Database out of sync with filesystem — repairing...")
            self._extractor.resync()

    def search_highlighting(self, query: str, limit: int = 30) -> list:
        """
        Searches for artists, albums, and tracks for UI display based on a query.

        Returns a combined list of formatted search results for artists, albums, and tracks, suitable for user interface presentation.

        Args:
            query: The search string to match against the music library.
            limit: The maximum number of results to return for each category.

        Returns:
            list: A list of formatted search result dictionaries for UI display.
        """
        if not (q := query.strip()):
            return []

        data = self.search_grouped(q, limit=limit)

        results = []
        results.extend(self._format_artist_results(data["artists"], q.lower()))
        results.extend(self._format_album_results(data["albums"], q.lower()))
        results.extend(self._format_track_results(data["tracks"], q.lower()))

        return results

    @staticmethod
    def highlight_text(text: str, query_lower: str) -> str:
        """Case-insensitive highlight van alle voorkomens van query_lower."""
        if not query_lower:
            return text

        def repl(match: re.Match) -> str:
            return f"<mark>{match[0]}</mark>"

        return re.sub(re.escape(query_lower), repl, text, flags=re.IGNORECASE)

    def _format_artist_results(
        self, artists: list[dict], query_lower: str
    ) -> list[dict]:
        """
        Formats artist search results for UI display.

        Processes a list of artist entries and returns formatted dictionaries including reasons, tracks, and highlighted tracks for each artist.

        Args:
            artists: A list of artist dictionaries to format.
            query_lower: The lowercase search query for highlighting matches.

        Returns:
            list[dict]: A list of formatted artist result dictionaries for UI display.
        """
        out = []
        for entry in artists:
            artist = entry["artist"]
            processed = self._process_artist_albums(entry, query_lower)

            out.append(
                {
                    "type": "artist",
                    "artist": artist,
                    "album": "Meerdere albums",
                    "reasons": processed["reasons"],
                    "tracks": processed["displayed_tracks"],
                    "highlighted_tracks": processed["highlighted_tracks"] or None,
                }
            )
        return out

    def _process_artist_albums(self, entry: dict, query_lower: str) -> dict:
        displayed = []
        highlighted = []
        reasons = [{"type": "artist", "text": entry["artist"]}]

        for album_entry in entry.get("albums", []):
            album_name = album_entry["album"]
            if query_lower in album_name.lower():
                reasons.append({"type": "album", "text": album_name})

            for track in album_entry.get("tracks", []):
                displayed.append(self._track_display_dict(track))

                if query_lower in track["track"].lower():
                    highlighted.append(self._track_highlighted_dict(track, query_lower))

        if highlighted:
            reasons.append({"type": "track", "text": f"{len(highlighted)} nummer(s)"})

        return {
            "reasons": reasons,
            "displayed_tracks": displayed,
            "highlighted_tracks": highlighted,
        }

    def _format_album_results(self, albums: list[dict], query_lower: str) -> list[dict]:
        out = []
        for album in albums:
            artist = album["artist"]
            album_name = album["album"]
            processed = self._process_album_tracks(album, query_lower)

            reasons = []
            if query_lower in artist.lower():
                reasons.append({"type": "artist", "text": artist})
            if query_lower in album_name.lower():
                reasons.append({"type": "album", "text": album_name})
            if processed["highlighted_tracks"]:
                reasons.append(
                    {
                        "type": "track",
                        "text": f"{len(processed['highlighted_tracks'])} nummer(s)",
                    }
                )

            out.append(
                {
                    "type": "album",
                    "artist": artist,
                    "album": album_name,
                    "reasons": reasons,
                    "tracks": processed["displayed_tracks"],
                    "highlighted_tracks": processed["highlighted_tracks"] or None,
                }
            )
        return out

    def _process_album_tracks(self, album: dict, query_lower: str) -> dict:
        displayed = []
        highlighted = []

        for track in album.get("tracks", []):
            displayed.append(self._track_display_dict(track))
            if query_lower in track["track"].lower():
                highlighted.append(self._track_highlighted_dict(track, query_lower))

        return {"displayed_tracks": displayed, "highlighted_tracks": highlighted}

    def _format_track_results(self, tracks: list[dict], query_lower: str) -> list[dict]:
        out = [
            {
                "type": "track",
                "artist": t["artist"],
                "album": t["album"],
                "reasons": [{"type": "track", "text": t["track"]}],
                "tracks": [self._track_display_dict(t)],
                "highlighted_tracks": [self._track_highlighted_dict(t, query_lower)],
            }
            for t in tracks
        ]
        return out

    def _track_display_dict(self, track: dict) -> dict:
        return {
            "title": track["track"],
            "duration": track.get("duration") or "?:??",
            "path": track["path"],
            "filename": self._safe_filename(track["track"], track["path"]),
        }

    def _track_highlighted_dict(self, track: dict, query_lower: str) -> dict:
        title = track["track"]
        duration = track.get("duration") or "?:??"
        highlighted_title = self.highlight_text(title, query_lower)

        return {
            "original": {"title": title, "duration": duration},
            "highlighted": highlighted_title,
            "match_type": "track",
        }

    def _safe_filename(self, title: str, path: str) -> str:
        ext = Path(path).suffix or ""
        safe = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        return f"{safe}{ext}"

    def count(self) -> int:
        """Return total number of tracks."""
        return self._extractor.count_tracks()

    def search_grouped(self, query: str, limit: int = 20):
        """Searches for artists, albums, and tracks matching the given query.

        Returns a dictionary grouping the search results into artists, albums, and tracks. The number of results in each group is limited by the specified limit.

        Args:
            query: The search string to match against artists, albums, and tracks.
            limit: The maximum number of results to return for each group.

        Returns:
            dict: A dictionary with keys 'artists', 'albums', and 'tracks', each containing a list of matching results.
        """
        if not (q := query.strip()):
            return {"artists": [], "albums": [], "tracks": []}

        like_pat = f"%{q}%"
        starts_pat = f"{q}%"

        with self._extractor.get_conn() as conn:
            result = {
                "artists": self._search_artists(conn, starts_pat, limit),
                "albums": [],
                "tracks": [],
            }
            result["albums"] = self._search_albums(
                conn, like_pat, starts_pat, limit, result["artists"]
            )
            result["tracks"] = self._search_tracks(
                conn, like_pat, starts_pat, limit, result["artists"], result["albums"]
            )
        return result

    def _search_artists(
        self, conn: Connection, starts_pat: str, limit: int
    ) -> list[dict[str, Any]]:
        """Searches for artists whose names match the given pattern.

        Returns a list of artist dictionaries matching the search criteria. The search is case-insensitive and limited to the specified number of results.

        Args:
            conn: The SQLite database connection.
            starts_pat: The pattern to match artist names that start with the query.
            limit: The maximum number of results to return.

        Returns:
            List[dict]: A list of dictionaries, each containing an artist name.
        """

        cur = conn.execute(
            """
            SELECT DISTINCT artist FROM tracks
            WHERE artist LIKE ? COLLATE NOCASE
            ORDER BY artist LIKE ? DESC, artist COLLATE NOCASE
            LIMIT ?
        """,
            (starts_pat, starts_pat, limit),
        )
        artists = [{"artist": r["artist"]} for r in cur]
        for artist in artists:
            artist.update(
                {
                    "albums": self._search_artist_albums(
                        conn=conn, artist=artist["artist"]
                    )
                }
            )
        return artists

    def _search_artist_albums(self, conn: Connection, artist: str):
        """Searches for albums by a specific artist.

        Returns a list of album dictionaries for the given artist, each including its tracks. The search is case-insensitive and results are ordered by album name.

        Args:
            conn: The SQLite database connection.
            artist: The artist name to search for.

        Returns:
            list[dict]: A list of dictionaries, each containing an album name and its tracks.
        """
        sql = """
                SELECT DISTINCT artist, album FROM tracks
                WHERE artist = ?
                ORDER BY album
            """
        cur = conn.execute(sql, (artist,))
        albums = [{"album": r["album"]} for r in cur]
        for album in albums:
            album.update(
                {
                    "tracks": self._search_album_tracks(
                        conn=conn, artist=artist, album=album["album"]
                    )
                }
            )
        return albums

    def _search_album_tracks(
        self, conn: Connection, artist: str, album: str
    ) -> list[dict]:
        """Searches for tracks in a specific album by a specific artist.

        Returns a list of track dictionaries for the given artist and album, including track title, filename, and path.

        Args:
            conn: The SQLite database connection.
            artist: The artist name to search for.
            album: The album name to search for.

        Returns:
            list[dict]: A list of dictionaries, each containing track title, filename, and path.
        """
        sql = """
            SELECT DISTINCT title as track, path, filename, duration
            FROM tracks
            WHERE artist = ? AND album = ?
            ORDER BY album;
            """
        cur = conn.execute(sql, (artist, album))
        tracks = [
            {
                "track": r["track"],
                "filename": r["filename"],
                "path": self._format_relative_path(r["path"]),
                "duration": self._format_duration(r["duration"]),
            }
            for r in cur
        ]
        return tracks

    def _format_relative_path(self, path: str) -> str:
        """
        Returns the relative path of a music file with respect to the music root directory.

        Converts an absolute or full path to a path relative to the music collection's root directory.

        Args:
            path: The absolute or full path to the music file.

        Returns:
            str: The relative path from the music root directory.
        """
        return str(Path(path).relative_to(self.music_root))

    def _format_duration(self, seconds: float) -> str:
        """
        Converts a duration in seconds to a MM:SS string format.

        Returns a string representing the duration in minutes and seconds, or "?:??" if the input is invalid.

        Args:
            seconds: The duration in seconds.

        Returns:
            str: The formatted duration as MM:SS, or "?:??" if seconds is not provided.
        """
        if not seconds:
            return "?:??"
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def _search_albums(
        self,
        conn: Connection,
        like_pat: str,
        starts_pat: str,
        limit: int,
        artists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Searches for albums whose names match the given pattern.

        Returns a list of album dictionaries matching the search criteria, excluding artists already found in previous searches. The search is case-insensitive and limited to the specified number of results.

        Args:
            conn: The SQLite database connection.
            like_pat: The pattern to match album names.
            starts_pat: The pattern to match album names that start with the query.
            limit: The maximum number of results to return.
            artists: A list of artist dictionaries to exclude from the search.

        Returns:
            List[dict]: A list of dictionaries, each containing artist and album name.
        """
        if skip := {a["artist"].lower() for a in artists}:
            placeholders = ",".join("?" for _ in skip)
            sql = f"""
                SELECT DISTINCT artist, album FROM tracks
                WHERE album LIKE ? COLLATE NOCASE
                    AND lower(artist) NOT IN ({placeholders})
                ORDER BY album LIKE ? DESC, album COLLATE NOCASE
                LIMIT ?
            """
            params = (like_pat, starts_pat, *skip, limit)
        else:
            sql = """
                SELECT DISTINCT artist, album FROM tracks
                WHERE album LIKE ? COLLATE NOCASE
                ORDER BY album LIKE ? DESC, album COLLATE NOCASE
                LIMIT ?
            """
            params = (like_pat, starts_pat, limit)
        cur = conn.execute(sql, params)
        albums = [{"artist": r["artist"], "album": r["album"]} for r in cur]
        for album in albums:
            album.update(
                {
                    "tracks": self._search_album_tracks(
                        conn=conn, artist=album["artist"], album=album["album"]
                    )
                }
            )
        return albums

    def _search_tracks(
        self,
        conn: Connection,
        like_pat: str,
        starts_pat: str,
        limit: int,
        artists: list[dict[str, Any]],
        albums: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Searches for tracks whose titles match the given pattern.

        Returns a list of track dictionaries matching the search criteria, excluding artists already found in previous searches. The search is case-insensitive and limited to the specified number of results.

        Args:
            conn: The SQLite database connection.
            like_pat: The pattern to match track titles.
            starts_pat: The pattern to match track titles that start with the query.
            limit: The maximum number of results to return.
            artists: A list of artist dictionaries to exclude from the search.
            albums: A list of album dictionaries whose artists should also be excluded.

        Returns:
            List[dict]: A list of dictionaries, each containing artist, album, and track name.
        """
        skip = {a["artist"].lower() for a in artists}
        skip.update(a["artist"].lower() for a in albums)
        if skip:
            placeholders = ",".join("?" for _ in skip)
            sql = f"""
                SELECT artist, album, title AS track, path, filename, duration
                FROM tracks
                WHERE title LIKE ? COLLATE NOCASE
                    AND lower(artist) NOT IN ({placeholders})
                ORDER BY title LIKE ? DESC, title COLLATE NOCASE
                LIMIT ?
            """
            cur = conn.execute(sql, (like_pat, starts_pat, *skip, limit))
        else:
            cur = conn.execute(
                """
                SELECT artist, album, title AS track, path, filename, duration
                FROM tracks
                WHERE title LIKE ? COLLATE NOCASE
                ORDER BY title LIKE ? DESC, title COLLATE NOCASE
                LIMIT ?
            """,
                (like_pat, starts_pat, limit),
            )
        return [
            {
                "artist": r["artist"],
                "album": r["album"],
                "track": r["track"],
                "filename": r["filename"],
                "path": self._format_relative_path(r["path"]),
                "duration": self._format_duration(r["duration"]),
            }
            for r in cur
        ]

    # ====================== Maintenance ======================

    def rebuild(self) -> None:
        """Force full reindex (useful if metadata changed a lot)."""
        self._extractor.rebuild()

    def close(self) -> None:
        """Stop background monitoring. Call explicitly if needed."""
        self._extractor.stop_monitoring()

    def __del__(self):
        # Best effort to stop observer
        with contextlib.suppress(Exception):
            self._extractor.stop_monitoring()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
