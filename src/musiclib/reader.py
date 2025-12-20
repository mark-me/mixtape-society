import re
from pathlib import Path
from threading import Thread
from typing import Any, Callable, Sequence
from sqlite3 import Connection

from common.logging import NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import get_indexing_status, clear_indexing_status


_STARTUP_DONE = False


class MusicCollection:
    """
    Provides search, indexing, and management functionality for a music collection.

    MusicCollection handles database setup, background indexing, and offers flexible search methods for
    artists, albums, and tracks. It supports both full-text search and SQL LIKE queries, and
    manages synchronization between the file system and the music database.
    """

    def __init__(
        self, music_root: Path | str, db_path: Path | str, logger=None
    ) -> None:
        """
        Initializes the MusicCollection with the given music root and database path.

        Sets up the collection extractor, determines startup mode, and starts background monitoring and indexing.

        Args:
            music_root (Path | str): The root directory containing music files.
            db_path (Path | str): The path to the SQLite database file.
            logger: Optional logger instance for logging.
        """
        self.music_root = Path(music_root).resolve()
        self.db_path = Path(db_path)
        self._logger = logger or NullLogger()
        self._extractor = CollectionExtractor(self.music_root, self.db_path)

        track_count = self.count()
        self._startup_mode = "rebuild" if track_count == 0 else "resync"
        self._logger.info(
            "No tracks in DB — scheduling initial rebuild"
            if track_count == 0
            else "Start resync of DB"
        )

        self._background_task_running = False
        self._extractor.start_monitoring()
        self._start_background_startup_job()

    # ==============================
    # === Startup / maintenance ====
    # ==============================
    def is_indexing(self) -> bool:
        """
        Checks if the music collection is currently being indexed or resynced.

        Returns True if the indexing status is 'rebuilding' or 'resyncing', otherwise False.

        Returns:
            bool: True if indexing or resyncing is in progress, False otherwise.
        """
        status = get_indexing_status(self.db_path.parent)
        return status and status.get("status") in ("rebuilding", "resyncing")

    def _start_background_startup_job(self) -> None:
        """
        Starts a background thread to perform initial indexing or resync of the music collection.

        Schedules either a rebuild or resync operation based on the startup mode, and
        ensures only one background task runs at a time.

        Returns:
            None
        """
        global _STARTUP_DONE
        if _STARTUP_DONE or self._background_task_running:
            return
        _STARTUP_DONE = self._background_task_running = True

        def task():
            try:
                (
                    self._extractor.rebuild
                    if self._startup_mode == "rebuild"
                    else self._extractor.resync
                )()
                self._logger.info("Startup indexing scheduled")
            except Exception as e:
                self._logger.error(f"Startup indexing failed: {e}", exc_info=True)
            finally:
                clear_indexing_status(self.music_root)
                self._background_task_running = False

        Thread(target=task, daemon=True).start()

    def rebuild(self) -> None:
        self._extractor.rebuild()

    def resync(self) -> None:
        self._extractor.resync()

    def close(self) -> None:
        self._extractor.stop()

    def _get_conn(self) -> Connection:
        return self._extractor.get_conn(readonly=True)

    def count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    # ================================
    # === Core search abstraction ====
    # ================================
    def _use_fts(self, conn: Connection) -> bool:
        """
        Determines if the full-text search (FTS) table exists in the database.

        Checks for the presence of the 'tracks_fts' table to enable FTS-based search functionality.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.

        Returns:
            bool: True if the FTS table exists, False otherwise.
        """
        return (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'"
            ).fetchone()
            is not None
        )

    def _fts_escape(self, txt: str) -> str:
        """
        Escapes special characters in a string for use in FTS queries.

        Ensures that backslashes and double quotes are properly escaped to prevent query errors.

        Args:
            txt (str): The text string to escape.

        Returns:
            str: The escaped string safe for FTS queries.
        """
        return txt.replace("\\", "\\\\").replace('"', '\\"')

    def _execute_search(
        self,
        conn: Connection,
        field: str,
        terms: Sequence[str],
        limit: int,
        extra_where: str = "",
        extra_params: list[Any] | None = None,
        order_by: str | None = None,
        select_fields: str = "artist, album, title AS track, path, filename, duration",
        table: str = "tracks_fts",
    ) -> list[dict]:
        """
        Executes a search query for artists, albums, or tracks in the music database.

        This method builds and runs either a full-text search (FTS) or SQL LIKE query based on the provided terms and field, returning a list of result dictionaries with post-processed paths and durations.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            field (str): The database field to search (e.g., 'artist', 'album', 'title').
            terms (Sequence[str]): A sequence of search terms.
            limit (int): The maximum number of results to return.
            extra_where (str, optional): Additional SQL WHERE clause conditions.
            extra_params (list[Any] | None, optional): Parameters for the extra WHERE clause.
            order_by (str | None, optional): Field to order results by.
            select_fields (str, optional): Fields to select in the query.
            table (str, optional): The table to query (default is 'tracks_fts').

        Returns:
            list[dict]: A list of result dictionaries with post-processed paths and durations.
        """
        if not terms:
            return []

        if self._use_fts(conn):
            rows = self._execute_search_fts(
                conn,
                field,
                terms,
                limit,
                extra_where,
                extra_params,
                order_by,
                select_fields,
                table,
            )
        else:
            rows = self._execute_search_like(
                conn,
                field,
                terms,
                limit,
                extra_where,
                extra_params,
                order_by,
                select_fields,
            )

        # Post-process paths and durations
        for r in rows:
            if "path" in r:
                r["path"] = self._relative_path(r["path"])
            if "duration" in r and r["duration"] is not None:
                r["duration"] = self._format_duration(r["duration"])
        return rows

    def _execute_search_fts(
        self,
        conn: Connection,
        field: str,
        terms: Sequence[str],
        limit: int,
        extra_where: str = "",
        extra_params: list[Any] | None = None,
        order_by: str | None = None,
        select_fields: str = "artist, album, title AS track, path, filename, duration",
        table: str = "tracks_fts",
    ) -> list[dict]:
        """
        Helper for _execute_search: performs FTS-based search.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            field (str): The database field to search.
            terms (Sequence[str]): A sequence of search terms.
            limit (int): The maximum number of results to return.
            extra_where (str, optional): Additional SQL WHERE clause conditions.
            extra_params (list[Any] | None, optional): Parameters for the extra WHERE clause.
            order_by (str | None, optional): Field to order results by.
            select_fields (str, optional): Fields to select in the query.
            table (str, optional): The table to query.

        Returns:
            list[dict]: A list of result dictionaries.
        """
        params: list[Any] = []
        if len(terms) == 1:
            expr = (
                f'{field}:"^{terms[0].rstrip("%")}"'
                if terms[0].endswith("%")
                else f"{field}:{self._fts_escape(terms[0])}"
            )
        else:
            expr = " OR ".join(f"{field}:{self._fts_escape(t)}" for t in terms)
        sql = f"SELECT DISTINCT {select_fields} FROM {table} WHERE {table} MATCH ?"
        params.append(expr)
        if extra_where:
            sql += f" {extra_where}"
            params.extend(extra_params or [])
        sql += f" ORDER BY {order_by or 'rank'} LIMIT ?"
        params.append(limit)

        cur = conn.execute(sql, params)
        return [dict(r) for r in cur]

    def _execute_search_like(
        self,
        conn: Connection,
        field: str,
        terms: Sequence[str],
        limit: int,
        extra_where: str = "",
        extra_params: list[any] | None = None,
        order_by: str | None = None,
        select_fields: str = "artist, album, title AS track, path, filename, duration",
    ) -> list[dict]:
        """
        Helper for _execute_search: performs LIKE-based search.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            field (str): The database field to search.
            terms (Sequence[str]): A sequence of search terms.
            limit (int): The maximum number of results to return.
            extra_where (str, optional): Additional SQL WHERE clause conditions.
            extra_params (list[Any] | None, optional): Parameters for the extra WHERE clause.
            order_by (str | None, optional): Field to order results by.
            select_fields (str, optional): Fields to select in the query.

        Returns:
            list[dict]: A list of result dictionaries.
        """
        params: list[Any] = []
        like_terms = [f"%{t}%" for t in terms]
        where_clauses = [f"{field} LIKE ? COLLATE NOCASE" for _ in terms]
        sql = f"SELECT DISTINCT {select_fields} FROM tracks WHERE " + " OR ".join(
            where_clauses
        )
        params.extend(like_terms)
        if extra_where:
            sql += f" {extra_where}"
            params.extend(extra_params or [])
        order_clause = order_by or f"{field} COLLATE NOCASE"
        sql += f" ORDER BY {order_clause} LIMIT ?"
        params.append(limit)

        cur = conn.execute(sql, params)
        return [dict(r) for r in cur]

    def _search_artists_multi(
        self, conn: Connection, terms: list[str], limit: int
    ) -> list[dict]:
        """
        Searches for artists in the database matching any of the provided search terms.

        Uses the core search abstraction to find artists matching any term and returns a list of artist dictionaries.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            terms (list[str]): A list of search terms to match against artist names.
            limit (int): The maximum number of artists to return.

        Returns:
            list[dict]: A list of artist dictionaries matching any of the search terms.
        """
        rows = self._execute_search(
            conn, "artist", terms, limit, select_fields="artist"
        )
        return [{"artist": r["artist"]} for r in rows]

    def _search_albums_multi(
        self,
        conn: Connection,
        terms: list[str],
        limit: int,
        skip_artists: set[str] | None = None,
    ) -> list[dict]:
        """
        Searches for albums in the database matching any of the provided search terms, excluding specified artists.

        Uses the core search abstraction to find albums matching any term and returns a list of album dictionaries with associated tracks.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            terms (list[str]): A list of search terms to match against album names.
            limit (int): The maximum number of albums to return.
            skip_artists (set[str] | None): A set of artist names to exclude from results.

        Returns:
            list[dict]: A list of album dictionaries with associated tracks.
        """
        extra_where = ""
        extra_params: list[Any] = []
        if skip_artists:
            placeholders = ",".join("?" for _ in skip_artists)
            extra_where = f"AND lower(artist) NOT IN ({placeholders})"
            extra_params = list(skip_artists)
        rows = self._execute_search(
            conn,
            "album",
            terms,
            limit,
            extra_where=extra_where,
            extra_params=extra_params,
            select_fields="artist, album",
        )
        for album in rows:
            album["tracks"] = self._search_album_tracks(
                conn, album["artist"], album["album"]
            )
        return rows

    def _search_tracks_multi(
        self,
        conn: Connection,
        terms: list[str],
        limit: int,
        skip_artists: set[str] | None = None,
    ) -> list[dict]:
        """
        Searches for tracks in the database matching any of the provided search terms, excluding specified artists.

        Uses the core search abstraction to find tracks matching any term and returns a list of track dictionaries with metadata.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            terms (list[str]): A list of search terms to match against track titles.
            limit (int): The maximum number of tracks to return.
            skip_artists (set[str] | None): A set of artist names to exclude from results.

        Returns:
            list[dict]: A list of track dictionaries matching any of the search terms.
        """
        extra_where = ""
        extra_params: list[Any] = []
        if skip_artists:
            placeholders = ",".join("?" for _ in skip_artists)
            extra_where = f"AND lower(artist) NOT IN ({placeholders})"
            extra_params = list(skip_artists)
        return self._execute_search(
            conn,
            "title",
            terms,
            limit,
            extra_where=extra_where,
            extra_params=extra_params,
            select_fields="artist, album, title AS track, path, filename, duration",
        )

    # Legacy single-phrase variants (used for non-tagged queries)
    def _search_artists(self, conn: Connection, starts: str, limit: int) -> list[dict]:
        """
        Searches for artists in the database matching the given prefix.

        Uses the core search abstraction to find artists matching the prefix and returns a list of artist dictionaries.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            starts (str): The prefix pattern to match artist names.
            limit (int): The maximum number of artists to return.

        Returns:
            list[dict]: A list of artist dictionaries matching the prefix.
        """
        return self._execute_search(
            conn, "artist", [starts], limit, select_fields="artist"
        )

    def _search_albums(
        self, conn: Connection, like: str, starts: str, limit: int, artists: list[dict]
    ) -> list[dict]:
        """
        Searches for albums in the database matching the given prefix, excluding already matched artists.

        Uses the core search abstraction to find albums matching the prefix and returns a list of album dictionaries with associated tracks.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            like (str): The SQL LIKE pattern for matching album names.
            starts (str): The prefix pattern for matching album names.
            limit (int): The maximum number of albums to return.
            artists (list[dict]): A list of artist dictionaries to exclude from results.

        Returns:
            list[dict]: A list of album dictionaries with associated tracks.
        """
        skip = {a["artist"].lower() for a in artists}
        rows = self._execute_search(
            conn,
            "album",
            [starts if self._use_fts(conn) else like],
            limit,
            extra_where=f"AND lower(artist) NOT IN ({','.join('?' * len(skip))})"
            if skip
            else "",
            extra_params=list(skip),
            select_fields="artist, album",
        )
        for a in rows:
            a["tracks"] = self._search_album_tracks(conn, a["artist"], a["album"])
        return rows

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
        Searches for tracks in the database matching the given prefix, excluding already matched artists and albums.

        Uses the core search abstraction to find tracks matching the prefix and returns a list of track dictionaries with metadata.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            like (str): The SQL LIKE pattern for matching track titles.
            starts (str): The prefix pattern for matching track titles.
            limit (int): The maximum number of tracks to return.
            artists (list[dict]): A list of artist dictionaries to exclude from results.
            albums (list[dict]): A list of album dictionaries to exclude from results.

        Returns:
            list[dict]: A list of track dictionaries with metadata.
        """
        skip = {a["artist"].lower() for a in artists} | {
            a["artist"].lower() for a in albums
        }
        term = starts if self._use_fts(conn) else like
        return self._execute_search(
            conn,
            "title",
            [term],
            limit,
            extra_where=f"AND lower(artist) NOT IN ({','.join('?' * len(skip))})"
            if skip
            else "",
            extra_params=list(skip),
        )

    # ================
    # === Helpers ====
    # ================
    def _search_artist_albums(self, conn: Connection, artist: str) -> list[dict]:
        """
        Searches for albums by a specific artist in the database.

        Finds all distinct albums for the given artist and returns a list of album dictionaries, each with associated tracks.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            artist (str): The artist name to search for.

        Returns:
            list[dict]: A list of album dictionaries with associated tracks for the artist.
        """
        cur = conn.execute(
            "SELECT DISTINCT album FROM tracks WHERE artist = ? ORDER BY album COLLATE NOCASE",
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
        Searches for tracks in the database belonging to a specific artist and album.

        Finds all tracks for the given artist and album, returning a list of track dictionaries with metadata.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            artist (str): The artist name to search for.
            album (str): The album name to search for.

        Returns:
            list[dict]: A list of track dictionaries for the specified artist and album.
        """
        cur = conn.execute(
            "SELECT title, path, filename, duration FROM tracks WHERE artist = ? AND album = ? ORDER BY title COLLATE NOCASE",
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

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        """
        Formats a duration in seconds as a string in minutes and seconds.

        Converts the given number of seconds to a string in the format 'M:SS', or returns '?:??' if the input is None or zero.

        Args:
            seconds (float | None): The duration in seconds.

        Returns:
            str: The formatted duration string.
        """
        if seconds is None:
            return "?:??"
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

    def _relative_path(self, path: str) -> str:
        """
        Converts an absolute file path to a path relative to the music collection root.

        Returns the relative path as a string, making it suitable for display or storage in the database.

        Args:
            path (str): The absolute file path to convert.

        Returns:
            str: The path relative to the music collection root.
        """
        return str(Path(path).relative_to(self.music_root))

    # =====================
    # === Public search ===
    # =====================
    def parse_query(self, query: str) -> dict[str, list[str]]:
        """
        Parses a search query string into tagged and general search terms.

        Extracts artist, album, and track tags as well as general terms from the query, returning a dictionary of parsed terms.

        Args:
            query (str): The search query string.

        Returns:
            dict[str, list[str]]: A dictionary containing lists of tagged and general search terms.
        """
        tags = {"artist": [], "album": [], "track": []}
        general: list[str] = []
        # Updated regex to handle escaped quotes inside quoted values
        pattern = r'(artist|album|song):("((?:[^"\\]|\\.)*)"|(\S+))'
        matches = re.finditer(pattern, query, re.IGNORECASE)
        last = 0
        for m in matches:
            tag = m.group(1).lower()
            quoted_value = m.group(3)
            unquoted_value = m.group(4)
            if quoted_value is not None:
                # Unescape any escaped quotes and backslashes
                value = re.sub(r'\\(.)', r'\1', quoted_value)
            else:
                value = unquoted_value
            if tag == "song":
                tag = "track"
            tags[tag].append(value)
            if between := query[last : m.start()].strip():
                general.extend(between.split())
            last = m.end()
        if remaining := query[last:].strip():
            general.extend(remaining.split())
        return {**tags, "general": general}

    def search_grouped(
        self, query: str, limit: int = 20
    ) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
        """
        Searches the music collection for artists, albums, and tracks matching the query and groups results.

        Parses the query for specific tags and general terms, performs grouped searches, and returns results for artists, albums, and tracks along with the parsed search terms.

        Args:
            query (str): The search query string.
            limit (int, optional): The maximum number of results per group (default is 20).

        Returns:
            tuple[dict[str, list[dict]], dict[str, list[str]]]: A tuple containing grouped search results and the parsed search terms.
        """
        if not query.strip():
            return {"artists": [], "albums": [], "tracks": []}, {}

        parsed = self.parse_query(query)
        has_specific = any(parsed[k] for k in ("artist", "album", "track"))
        conn = self._get_conn()

        if not has_specific and parsed["general"]:
            phrase = " ".join(parsed["general"])
            like = f"%{phrase}%"
            starts = f"{phrase}%"
            artists = self._search_artists(conn, starts, limit)
            albums = self._search_albums(conn, like, starts, limit, artists)
            tracks = self._search_tracks(conn, like, starts, limit, artists, albums)
            terms = {"artist": [phrase], "album": [phrase], "track": [phrase]}
        else:
            general = parsed["general"]
            artists = self._search_artists_multi(
                conn, parsed["artist"] + general, limit
            )
            albums = self._search_albums_multi(
                conn,
                parsed["album"] + general,
                limit,
                skip_artists={a["artist"].lower() for a in artists},
            )
            tracks = self._search_tracks_multi(
                conn,
                parsed["track"] + general,
                limit,
                skip_artists={a["artist"].lower() for a in artists + albums},
            )
            terms = {
                "artist": parsed["artist"] + general,
                "album": parsed["album"] + general,
                "track": parsed["track"] + general,
            }

        # Populate sub-items
        for a in artists:
            a["albums"] = self._search_artist_albums(conn, a["artist"])
        for a in albums:
            a["tracks"] = self._search_album_tracks(conn, a["artist"], a["album"])

        return {"artists": artists, "albums": albums, "tracks": tracks}, terms
