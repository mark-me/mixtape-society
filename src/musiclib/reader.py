import re
from pathlib import Path
from threading import Thread
from typing import Any
from sqlite3 import Connection

from common.logging import NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import clear_indexing_status


_STARTUP_DONE = False


class MusicCollection:
    """
    High-level facade around CollectionExtractor (pipeline-based).

    Guarantees:
    - Exactly one SQLite writer (inside CollectionExtractor)
    - Rebuild, resync, and live FS events are serialized
    - No SQLite access from UI / background threads
    """

    def __init__(
        self, music_root: Path | str, db_path: Path | str, logger=None
    ) -> None:
        """
        Initializes the MusicCollection with the specified music root and database path.

        Sets up the music extractor, determines the startup mode (rebuild or resync),
        starts monitoring for file system changes, and schedules the initial background indexing job.

        Args:
            music_root (Path | str): The root directory containing music files.
            db_path (Path | str): The path to the SQLite database file.

        Returns:
            None
        """
        self.music_root = Path(music_root).resolve()
        self.db_path = Path(db_path)

        self._logger = logger or NullLogger()

        self._extractor = CollectionExtractor(
            music_root=self.music_root,
            db_path=self.db_path,
        )

        # Decide startup action
        track_count = self.count()

        if track_count == 0:
            self._logger.info("No tracks in DB — scheduling initial rebuild")
            self._startup_mode = "rebuild"
        else:
            self._startup_mode = "resync"

        self._background_task_running = False

        # Start monitoring immediately
        self._extractor.start_monitoring()

        # Kick background startup job
        self._start_background_startup_job()

    # === Startup logic ===

    def _start_background_startup_job(self) -> None:
        """
        Starts a background thread to perform initial indexing of the music collection.

        Schedules either a full rebuild or a resync of the music database based on its current state, ensuring only one startup job runs at a time.

        Returns:
            None
        """
        global _STARTUP_DONE
        if _STARTUP_DONE:
            return
        if self._background_task_running:
            return
        _STARTUP_DONE = True

        self._background_task_running = True

        def task():
            try:
                if self._startup_mode == "rebuild":
                    self._extractor.rebuild()
                elif self._startup_mode == "resync":
                    self._extractor.resync()
                self._logger.info("Startup indexing scheduled")
            except Exception as e:
                self._logger.error(f"Startup indexing failed: {e}", exc_info=True)
            finally:
                clear_indexing_status(self.music_root)
                self._background_task_running = False

        Thread(target=task, daemon=True).start()

    # === Public maintenance API ===

    def rebuild(self) -> None:
        """Force full rebuild."""
        self._extractor.rebuild()

    def resync(self) -> None:
        """Force resync."""
        self._extractor.resync()

    def close(self) -> None:
        """Shutdown monitoring and writer thread."""
        self._extractor.stop()

    # === Read-only DB helpers ===

    def _get_conn(self) -> Connection:
        """
        Returns a read-only SQLite connection to the music database.

        Provides safe access for querying the database without modifying its contents.

        Returns:
            sqlite3.Connection: The read-only database connection object.
        """
        # READ-ONLY access is allowed
        return self._extractor.get_conn(readonly=True)

    def count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    # === Search API ===

    def search_grouped(
        self, query: str, limit: int = 20
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Searches for artists, albums, and tracks matching the query and groups results by type.

        Returns a dictionary containing lists of matching artists, albums, and tracks, each formatted for further processing or display.

        Args:
            query (str): The search string to match against the music library.
            limit (int): The maximum number of results to return for each category.

        Returns:
            dict[str, list[dict[str, Any]]]: A dictionary with keys 'artists', 'albums', and 'tracks', each containing a list of result dictionaries.
        """
        if not (q := query.strip()):
            return {"artists": [], "albums": [], "tracks": []}

        like = f"%{q}%"
        starts = f"{q}%"

        with self._get_conn() as conn:
            artists = self._search_artists(conn, starts, limit)
            albums = self._search_albums(conn, like, starts, limit, artists)
            tracks = self._search_tracks(conn, like, starts, limit, artists, albums)

        return {
            "artists": artists,
            "albums": albums,
            "tracks": tracks,
        }

    def _search_artists(self, conn: Connection, starts: str, limit: int) -> list[dict]:
        """
        Searches for artists in the database matching the given prefix.

        Returns a list of artist dictionaries, each including associated albums, for use in grouped search results.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            starts (str): The prefix to match artist names.
            limit (int): The maximum number of artists to return.

        Returns:
            list[dict]: A list of artist dictionaries with associated albums.
        """
        cur = conn.execute(
            """
            SELECT DISTINCT artist FROM tracks
            WHERE artist LIKE ? COLLATE NOCASE
            ORDER BY artist LIKE ? DESC, artist COLLATE NOCASE
            LIMIT ?
            """,
            (starts, starts, limit),
        )
        artists = [{"artist": r["artist"]} for r in cur]

        for a in artists:
            a["albums"] = self._search_artist_albums(conn, a["artist"])

        return artists

    def _search_artist_albums(self, conn, artist: str) -> list[dict]:
        """
        Searches for albums by a specific artist in the database.

        Returns a list of album dictionaries, each including associated tracks, for use in grouped search results.

        Args:
            conn: The SQLite database connection.
            artist (str): The artist name to match albums for.

        Returns:
            list[dict]: A list of album dictionaries with associated tracks.
        """
        cur = conn.execute(
            """
            SELECT DISTINCT album FROM tracks
            WHERE artist = ?
            ORDER BY album COLLATE NOCASE
            """,
            (artist,),
        )
        albums = [{"album": r["album"]} for r in cur]

        for a in albums:
            a["tracks"] = self._search_album_tracks(conn, artist, a["album"])

        return albums

    def _search_album_tracks(
        self, conn: Connection, artist: str, album: str
    ) -> list[dict]:
        """
        Searches for tracks in the database by a specific artist and album.

        Returns a list of track dictionaries with title, relative path, filename, and formatted duration for use in search results.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            artist (str): The artist name to match tracks for.
            album (str): The album name to match tracks for.

        Returns:
            list[dict]: A list of track dictionaries with metadata.
        """
        cur = conn.execute(
            """
            SELECT title, path, filename, duration
            FROM tracks
            WHERE artist = ? AND album = ?
            ORDER BY title COLLATE NOCASE
            """,
            (artist, album),
        )
        return [
            {
                "track": r["title"],
                "path": self._relative_path(r["path"]),
                "filename": r["filename"],
                "duration": self._format_duration(r["duration"]),
            }
            for r in cur
        ]

    def _search_albums(
        self, conn: Connection, like: str, starts: str, limit: int, artists: list[dict]
    ) -> list[dict]:
        """
        Searches for albums in the database matching the query, excluding those by already matched artists.

        Returns a list of album dictionaries, each including associated tracks, for use in grouped search results.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            like (str): The SQL LIKE pattern for matching album names.
            starts (str): The SQL LIKE pattern for matching album names at the start.
            limit (int): The maximum number of albums to return.
            artists (list[dict]): A list of artist dictionaries to exclude from results.

        Returns:
            list[dict]: A list of album dictionaries with associated tracks.
        """
        skip = {a["artist"].lower() for a in artists}
        params = [like, starts]

        sql = """
            SELECT DISTINCT artist, album FROM tracks
            WHERE album LIKE ? COLLATE NOCASE
        """
        if skip:
            sql += f" AND lower(artist) NOT IN ({','.join('?' * len(skip))})"
            params.extend(skip)

        sql += " ORDER BY album LIKE ? DESC, album COLLATE NOCASE LIMIT ?"
        params.extend([limit])

        cur = conn.execute(sql, params)
        albums = [{"artist": r["artist"], "album": r["album"]} for r in cur]

        for a in albums:
            a["tracks"] = self._search_album_tracks(conn, a["artist"], a["album"])

        return albums

    def _search_tracks(
        self,
        conn: Connection,
        like: str,
        starts: str,
        limit: int,
        artists: list[dict],
        albums: list[dict],
    ) -> list[dict]:
        """
        Searches for tracks in the database matching the query, excluding those by already matched artists and albums.

        Returns a list of track dictionaries with metadata for use in grouped search results.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            like (str): The SQL LIKE pattern for matching track titles.
            starts (str): The SQL LIKE pattern for matching track titles at the start.
            limit (int): The maximum number of tracks to return.
            artists (list[dict]): A list of artist dictionaries to exclude from results.
            albums (list[dict]): A list of album dictionaries to exclude from results.

        Returns:
            list[dict]: A list of track dictionaries with metadata.
        """
        skip = {a["artist"].lower() for a in artists}
        skip.update(a["artist"].lower() for a in albums)

        params = [like, starts]
        sql = """
            SELECT artist, album, title, path, filename, duration
            FROM tracks
            WHERE title LIKE ? COLLATE NOCASE
        """

        if skip:
            sql += f" AND lower(artist) NOT IN ({','.join('?' * len(skip))})"
            params.extend(skip)

        sql += " ORDER BY title LIKE ? DESC, title COLLATE NOCASE LIMIT ?"
        params.extend([limit])

        cur = conn.execute(sql, params)
        return [
            {
                "artist": r["artist"],
                "album": r["album"],
                "track": r["title"],
                "path": self._relative_path(r["path"]),
                "filename": r["filename"],
                "duration": self._format_duration(r["duration"]),
            }
            for r in cur
        ]

    def search_highlighting(self, query: str, limit: int = 30) -> list[dict]:
        """
        Searches for artists, albums, and tracks matching the query and formats results with highlighted matches.

        Returns a list of formatted result dictionaries for UI display, including highlighted text for matching artists, albums, and tracks.

        Args:
            query (str): The search string to match against the music library.
            limit (int): The maximum number of results to return for each category.

        Returns:
            list[dict]: A list of formatted result dictionaries with highlighted matches.
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
        """
        Highlights occurrences of the search query within the given text.

        Returns the text with all matches of the query wrapped in <mark> tags for UI display.

        Args:
            text (str): The text to search and highlight.
            query_lower (str): The lowercase search query to highlight.

        Returns:
            str: The text with highlighted matches.
        """
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

        Processes a list of artist entries and returns formatted dictionaries including reasons, albums, and highlighted tracks for each artist.

        Args:
            artists (list[dict]): A list of artist dictionaries to format.
            query_lower (str): The lowercase search query for highlighting matches.

        Returns:
            list[dict]: A list of formatted artist result dictionaries for UI display.
        """
        out = []
        for entry in artists:
            artist = entry["artist"]
            artist_matched = query_lower in artist.lower()

            album_list = []
            matched_albums_count = 0
            matched_tracks_count = 0

            for album_entry in entry.get("albums", []):
                album_name = album_entry["album"]
                album_matched = query_lower in album_name.lower()
                if album_matched:
                    matched_albums_count += 1

                processed = self._process_album_tracks(album_entry, query_lower)
                highlighted_count = len(processed["highlighted_tracks"])
                if highlighted_count > 0:
                    matched_tracks_count += highlighted_count

                album_reasons = []
                if album_matched:
                    album_reasons.append({"type": "album", "text": album_name})
                if highlighted_count > 0:
                    album_reasons.append(
                        {"type": "track", "text": f"{highlighted_count} nummer(s)"}
                    )

                album_list.append(
                    {
                        "album": album_name,
                        "reasons": album_reasons,
                        "tracks": processed["displayed_tracks"],
                        "highlighted_tracks": processed["highlighted_tracks"] or None,
                    }
                )

            reasons = []
            if artist_matched:
                reasons.append({"type": "artist", "text": artist})
            if matched_albums_count > 0:
                reasons.append(
                    {"type": "album", "text": f"{matched_albums_count} album(s)"}
                )
            if matched_tracks_count > 0:
                reasons.append(
                    {"type": "track", "text": f"{matched_tracks_count} nummer(s)"}
                )

            out.append(
                {
                    "type": "artist",
                    "artist": artist,
                    "albums": album_list,
                    "reasons": reasons,
                }
            )
        return out

    def _format_album_results(self, albums: list[dict], query_lower: str) -> list[dict]:
        """
        Formats album search results for UI display.

        Processes a list of album entries and returns formatted dictionaries including reasons, tracks, and highlighted tracks for each album.

        Args:
            albums (list[dict]): A list of album dictionaries to format.
            query_lower (str): The lowercase search query for highlighting matches.

        Returns:
            list[dict]: A list of formatted album result dictionaries for UI display.
        """
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
        """
        Processes tracks for a given album entry to prepare search result formatting.

        Returns a dictionary containing displayed tracks and highlighted tracks based on the search query.

        Args:
            album (dict): The album entry containing tracks.
            query_lower (str): The lowercase search query for highlighting matches.

        Returns:
            dict: A dictionary with keys 'displayed_tracks' and 'highlighted_tracks'.
        """
        displayed = []
        highlighted = []

        for track in album.get("tracks", []):
            displayed.append(self._track_display_dict(track))
            if query_lower in track["track"].lower():
                highlighted.append(self._track_highlighted_dict(track, query_lower))

        return {"displayed_tracks": displayed, "highlighted_tracks": highlighted}

    def _format_track_results(self, tracks: list[dict], query_lower: str) -> list[dict]:
        """
        Formats track search results for UI display.

        Processes a list of track entries and returns formatted dictionaries including reasons, tracks, and highlighted tracks for each track.

        Args:
            tracks (list[dict]): A list of track dictionaries to format.
            query_lower (str): The lowercase search query for highlighting matches.

        Returns:
            list[dict]: A list of formatted track result dictionaries for UI display.
        """
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
        """
        Formats a track dictionary for display in search results.

        Returns a dictionary containing the track's title, duration, relative path, and a safe filename for use in the UI.

        Args:
            track (dict): The track dictionary containing metadata.

        Returns:
            dict: A formatted track dictionary for display.
        """
        return {
            "title": track["track"],
            "duration": track.get("duration") or "?:??",
            "path": track["path"],
            "filename": self._safe_filename(track["track"], track["path"]),
        }

    def _track_highlighted_dict(self, track: dict, query_lower: str) -> dict:
        """
        Formats a track dictionary for highlighted display in search results.

        Returns a dictionary containing the original title and duration, the highlighted title, and the match type for UI display.

        Args:
            track (dict): The track dictionary containing metadata.
            query_lower (str): The lowercase search query for highlighting matches.

        Returns:
            dict: A formatted track dictionary with highlighted text for display.
        """
        title = track["track"]
        duration = track.get("duration") or "?:??"
        highlighted_title = self.highlight_text(title, query_lower)

        return {
            "original": {"title": title, "duration": duration},
            "highlighted": highlighted_title,
            "match_type": "track",
        }

    def _safe_filename(self, title: str, path: str) -> str:
        """
        Generates a safe filename for a track title and path.

        Returns a filename string that is sanitized for filesystem use, preserving the original file extension.

        Args:
            title (str): The track title to use for the filename.
            path (str): The original file path to extract the extension.

        Returns:
            str: A safe filename string for the track.
        """
        ext = Path(path).suffix or ""
        safe = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        return f"{safe}{ext}"

    # === Helpers ===

    def _relative_path(self, path: str) -> str:
        """
        Converts an absolute file path to a path relative to the music root directory.

        Returns a string representing the relative path for use in UI display and internal processing.

        Args:
            path (str): The absolute file path to convert.

        Returns:
            str: The path relative to the music root directory.
        """
        return str(Path(path).relative_to(self.music_root))

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        """
        Formats a duration in seconds as a string in MM:SS format.

        Returns a formatted string representing the duration, or "?:??" if the input is None or invalid.

        Args:
            seconds (float | None): The duration in seconds to format.

        Returns:
            str: The formatted duration string.
        """
        if not seconds:
            return "?:??"
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"
