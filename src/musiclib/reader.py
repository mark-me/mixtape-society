# Updated reader.py with lazy loading for both artists and albums
# No automatic population of albums for artists or tracks for albums
import re
from collections import defaultdict
from pathlib import Path
from sqlite3 import Connection
from threading import Thread

from common.logging import NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import get_indexing_status

class MusicCollection:
    """Manages a music collection database and provides search and detail retrieval functionality.
    Handles lazy loading, background indexing, and query parsing for artists, albums, and tracks.
    """
    def __init__(
        self, music_root: Path | str, db_path: Path | str, logger=None
    ) -> None:
        """Initializes the MusicCollection with the given music root and database path.
        Sets up logging, extraction, and schedules background indexing or resync as needed.

        Args:
            music_root: Path to the root directory containing music files.
            db_path: Path to the SQLite database file.
            logger: Optional logger instance.

        Returns:
            None
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
        if track_count == 0:
            self._extractor.wait_for_indexing_start()

    def is_indexing(self) -> bool:
        status = get_indexing_status(self.db_path.parent)

        # If status file exists and indicates active job → yes
        if status and status.get("status") in ("rebuilding", "resyncing"):
            return True

        # If status file doesn't exist yet, but DB is empty → initial rebuild is queued
        # and will start shortly → treat as indexing to allow waiting
        if status is None and self.count() == 0:
            return True

        # Otherwise: either done, or no job needed
        return False

    def _start_background_startup_job(self) -> None:
        """Starts a background thread to perform initial indexing or resync of the music collection.
        Ensures that only one background startup job runs at a time.

        Returns:
            None
        """
        if self._background_task_running:
            return

        # Only start initial rebuild if not already marked as done
        if self._extractor.is_initial_indexing_done():
            return

        self._background_task_running = True

        def task():
            try:
                self._extractor.rebuild()  # This will set status, etc.
                self._extractor.set_initial_indexing_done()
                self._logger.info("Initial indexing completed and marked as done")
            except Exception as e:
                self._logger.error(f"Initial indexing failed: {e}", exc_info=True)
            finally:
                self._background_task_running = False

        Thread(target=task, daemon=True).start()

    def rebuild(self) -> None:
        """Triggers a full rebuild of the music collection database.
        Rebuilds the database from scratch using the current music files.

        Returns:
            None
        """
        self._extractor.rebuild()

    def resync(self) -> None:
        """Performs a resync of the music collection database.
        Updates the database to reflect changes in the music files without a full rebuild.

        Returns:
            None
        """
        self._extractor.resync()

    def close(self) -> None:
        """Stops monitoring and closes resources associated with the music collection.
        Cleans up background tasks and releases any held resources.

        Returns:
            None
        """
        self._extractor.stop()

    def _get_conn(self) -> Connection:
        """Returns a read-only SQLite connection to the music collection database.
        Used internally for executing queries against the database.

        Returns:
            Connection: A read-only SQLite database connection.
        """
        return self._extractor.get_conn(readonly=True)

    def count(self) -> int:
        """Returns the total number of tracks in the music collection database.
        Executes a query to count all tracks currently indexed.

        Returns:
            int: The number of tracks in the database.
        """
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    def _use_fts(self, conn: Connection) -> bool:
        """Checks if the full-text search (FTS) table exists in the database.
        Determines whether FTS-based queries can be used for searching tracks.

        Args:
            conn: SQLite database connection.

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
        """Escapes double quotes in a string for use in full-text search queries.
        Ensures that input text is safely formatted for FTS operations.

        Args:
            txt: The input string to escape.

        Returns:
            str: The escaped string with double quotes replaced.
        """
        return txt.replace('"', '""')

    def _search_album_tracks(
        self, conn: Connection, artist: str, album: str
    ) -> list[dict[str, str]]:
        """Fetches all tracks for a given artist and album from the database.
        Returns a list of track details including title, path, filename, and duration.

        Args:
            conn: SQLite database connection.
            artist: Name of the artist.
            album: Name of the album.

        Returns:
            list[dict[str, str]]: List of dictionaries containing track details.
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
        """Formats a duration in seconds into a MM:SS string.
        Returns a placeholder if the duration is not provided.

        Args:
            seconds: The duration in seconds.

        Returns:
            str: The formatted duration as MM:SS or a placeholder if not available.
        """
        if not seconds:
            return "?:??"
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

    def _relative_path(self, path: str) -> str:
        """Converts an absolute track path to a path relative to the music root directory.
        Used to display or store paths in a consistent, relative format.

        Args:
            path: The absolute path to the track file.

        Returns:
            str: The path relative to the music root directory.
        """
        p = Path(path)
        if p.is_absolute():
            try:
                return str(p.relative_to(self.music_root))
            except ValueError:
                # Fallback if not a subpath (shouldn't happen normally)
                self._logger.warning(f"Path {path} not under music_root {self.music_root}")
                return str(p)
        else:
            # Already relative – return unchanged
            return str(p)

    def _parse_query(self, query: str) -> dict[str, list[str]]:
        """Parses a search query string into tagged and general search terms.
        Extracts artist, album, track tags and general terms for advanced search functionality.

        Args:
            query: The search query string to parse.

        Returns:
            dict[str, list[str]]: Dictionary containing lists of terms for 'artist', 'album', 'track', and 'general'.
        """
        query = query.strip()
        if not query:
            return {"artist": [], "album": [], "track": [], "general": []}

        terms = {
            "artist": [],
            "album": [],
            "track": [],   # also used for 'song:'
            "general": [],
        }

        # Regex to match: tag:"quoted phrase" or tag:word
        tag_pattern = re.compile(
            r'(artist|album|track|song):"([^"]+)"|(artist|album|track|song):([^\s]+)',
            re.IGNORECASE
        )

        # Find all tagged terms first
        tagged_matches = list(tag_pattern.finditer(query))

        # Process tagged terms (from right to left to avoid index shifting)
        last_end = len(query)
        for match in reversed(tagged_matches):
            full_match = match.group(0)
            tag_type = (match.group(1) or match.group(3)).lower()
            value = match.group(2) or match.group(4)

            if tag_type == "song":
                tag_type = "track"

            if value.strip():
                terms[tag_type].append(value.strip())

            # Remove this tagged part from the query
            start, end = match.span()
            query = query[:start] + query[end:]

        # What's left is the free-text / general part
        remaining = query.strip()

        # Split remaining into words, but preserve quoted phrases
        parts = []
        i = 0
        while i < len(remaining):
            if remaining[i] == '"':
                # Find closing quote
                j = remaining.find('"', i + 1)
                if j == -1:
                    j = len(remaining)
                phrase = remaining[i + 1:j]
                if phrase.strip():
                    parts.append(phrase.strip())
                i = j + 1
            elif remaining[i].isspace():
                i += 1
            else:
                # Find end of word
                j = i
                while j < len(remaining) and not remaining[j].isspace():
                    j += 1
                word = remaining[i:j]
                if word.strip():
                    parts.append(word.strip())
                i = j

        # Add non-empty general terms
        terms["general"].extend([p for p in parts if p])

        for key in terms:
            cleaned = []
            for term in terms[key]:
                term = term.strip()
                if not term:
                    continue
                # Remove standalone wildcard '*' or terms that are just '*'
                if term == "*":
                    continue
                # Optionally: strip leading/trailing wildcards if you don't want prefix/suffix matching
                # But usually prefix * is useful (e.g., "beat*"), so we keep trailing *
                # Only remove if it's *alone* or leading * with nothing else
                if term.startswith("*") and len(term) > 1:
                    term = term[1:]  # strip leading *, keep "les*" → "les*"
                if term.endswith("*") or term.isalpha() or " " in term:  # phrases or normal words
                    cleaned.append(term)
                elif term:  # fallback: include if not empty
                    cleaned.append(term)
            terms[key] = cleaned

        return terms

    def search_grouped(self, query: str, limit: int = 20) -> tuple[dict, dict]:
        """
        Performs a grouped search returning artists, albums, and tracks that match the query.
        Uses FTS where available, falls back to LIKE queries.
        Limits the total number of results and prevents invalid FTS queries.

        Args:
            query: The search query string.
            limit: Maximum number of grouped results to return (artists + albums + tracks).

        Returns:
            tuple: (grouped results dict, parsed terms dict)
        """
        query = query.strip()
        if not query:
            return {"artists": [], "albums": [], "tracks": []}, {
                "artist": [],
                "album": [],
                "track": [],
                "general": [],
            }

        terms = self._parse_query(query)

        # === Critical safety check: if no valid terms after parsing, return empty ===
        if not any(terms.values()):
            return {"artists": [], "albums": [], "tracks": []}, terms

        with self._get_conn() as conn:
            use_fts = self._use_fts(conn)

            artists = []
            albums = []
            tracks = []

            has_artist = bool(terms["artist"])
            has_album = bool(terms["album"])
            has_track = bool(terms["track"])
            has_general = bool(terms["general"])
            has_specific = has_artist or has_album or has_track

            # Build FTS query parts safely
            fts_conditions = []
            fts_params = []

            if use_fts:
                if has_artist:
                    for term in terms["artist"]:
                        # For exact artist match, use column filter + prefix if needed
                        fts_conditions.append("artist: " + self._fts_escape(term) + "*")
                if has_album:
                    for term in terms["album"]:
                        fts_conditions.append("album: " + self._fts_escape(term) + "*")
                if has_track or has_general:
                    general_terms = terms["track"] + terms["general"]
                    for term in general_terms:
                        escaped = self._fts_escape(term)
                        if escaped:  # double-check after escape
                            fts_conditions.append(escaped + "*")

                if fts_conditions:
                    fts_query = " OR ".join(fts_conditions)
                else:
                    fts_query = "1 = 0"  # impossible, fallback to empty

                sql = f"""
                    SELECT artist, album, title, path, filename, duration,
                        SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) AS release_dir
                    FROM tracks_fts
                    WHERE tracks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (fts_query, limit * 3)  # fetch extra to allow filtering
            else:
                # Fallback LIKE-based query
                conditions = []
                params = []

                if has_artist:
                    for term in terms["artist"]:
                        conditions.append("artist LIKE ?")
                        params.append(f"%{term}%")
                if has_album:
                    for term in terms["album"]:
                        conditions.append("album LIKE ?")
                        params.append(f"%{term}%")
                if has_track or has_general:
                    general_terms = terms["track"] + terms["general"]
                    for term in general_terms:
                        conditions.append("(title LIKE ? OR artist LIKE ? OR album LIKE ?)")
                        params.extend([f"%{term}%", f"%{term}%", f"%{term}%"])

                where_clause = " AND ".join(conditions) if conditions else "1=1"

                sql = f"""
                    SELECT artist, album, title, path, filename, duration,
                        SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) AS release_dir
                    FROM tracks
                    WHERE {where_clause}
                    ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, title COLLATE NOCASE
                    LIMIT ?
                """
                params.append(limit * 3)

            cur = conn.execute(sql, params)
            all_rows = cur.fetchall()

            # Group results
            artist_set = set()
            album_set = set()
            track_list = []

            for row in all_rows:
                artist = row["artist"] or "Unknown Artist"
                album = row["album"] or "Unknown Album"
                release_dir = row["release_dir"]

                # === Artist inclusion ===
                include_artist = True
                if has_specific and has_artist:
                    include_artist = any(t.lower() in artist.lower() for t in terms["artist"])

                if include_artist and artist not in artist_set:
                    artists.append({"artist": artist})
                    artist_set.add(artist)

                # === Album inclusion ===
                if has_artist:
                    include_album = False  # Suppress top-level albums when searching by artist
                else:
                    include_album = True
                    if has_specific and has_album:
                        if not any(t.lower() in album.lower() for t in terms["album"]):
                            include_album = False

                if include_album and release_dir not in album_set:
                    albums.append({
                        "artist": artist,
                        "display_artist": artist,
                        "album": album,
                        "release_dir": release_dir,
                        "is_compilation": False,
                    })
                    album_set.add(release_dir)

                # === Track collection ===
                if len(track_list) < limit:
                    track_list.append(dict(row))

            # Final limits
            artists = artists[:limit]
            albums = albums[:limit]
            tracks = track_list[:limit]

            # Post-process: detect compilations in albums
            for album in albums:
                release_dir = album["release_dir"]
                album_tracks = [t for t in track_list if t["release_dir"] == release_dir]
                if album_tracks:
                    unique_artists = {t["artist"] for t in album_tracks if t["artist"]}
                    album["is_compilation"] = len(unique_artists) > 3
                    if album["is_compilation"]:
                        album["display_artist"] = "Various Artists"

            return {"artists": artists, "albums": albums, "tracks": tracks}, terms

    def get_artist_details(self, artist: str) -> dict:
        """Retrieves detailed information about an artist, including their albums and tracks.
        Returns a dictionary with the artist name and a list of albums containing track details.

        Args:
            artist: The name of the artist to retrieve details for.

        Returns:
            dict: Dictionary containing the artist name and a list of albums with track information.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT album, title, path, filename, duration
                FROM tracks
                WHERE artist = ?
                ORDER BY album COLLATE NOCASE, title COLLATE NOCASE
                """,
                (artist,),
            )
            releases_map = defaultdict(list)
            for row in cur:
                release_dir = self._get_release_dir(row["path"])
                releases_map[release_dir].append(
                    {
                        "track": row["title"],
                        "album": row["album"],
                        "path": self._relative_path(row["path"]),
                        "filename": row["filename"],
                        "duration": self._format_duration(row["duration"]),
                    }
                )

            albums = []
            for release_dir, tracks in sorted(
                releases_map.items(),
                key=lambda x: x[1][0].get("album", "") if x[1] else ""
            ):
                album_name = tracks[0].get("album", "Unknown Album") if tracks else "Unknown Album"
                albums.append({"album": album_name, "tracks": tracks, "release_dir": release_dir})

            return {"artist": artist, "albums": albums}

    def get_album_details(self, release_dir: str) -> dict:
        """Retrieves detailed information about an album given its release directory.
        Returns a dictionary with album details, including artist, tracks, compilation status, and release directory.

        Args:
            release_dir: The release directory relative to the music root.

        Returns:
            dict: Dictionary containing album details, track list, and compilation status.
        """
# Construct the expected directory pattern with trailing slash
        expected_dir = release_dir if release_dir.endswith("/") else release_dir + "/"

        with self._get_conn() as conn:
            cur = conn.execute(
                f"""
                SELECT artist, title, path, filename, duration, album
                FROM tracks
                WHERE {self._sql_release_dir_expr()} = ?
                ORDER BY title COLLATE NOCASE
                """,
                (expected_dir,),
            )
            rows = cur.fetchall()

            if not rows:
                return {
                    "artist": "",
                    "album": "",
                    "tracks": [],
                    "is_compilation": False,
                    "release_dir": release_dir
                }

            # Album name from first row
            album_name = rows[0]["album"] or "Unknown Album"

            # Build track list
            track_list = [
                {
                    "artist": row["artist"],
                    "track": row["title"],
                    "path": self._relative_path(row["path"]),
                    "filename": row["filename"],
                    "duration": self._format_duration(row["duration"]),
                    "album": row["album"],  # optional: include for consistency
                }
                for row in rows
            ]

            # Detect compilation
            artists = {t["artist"] for t in track_list if t["artist"]}
            is_compilation = len(artists) > 3
            display_artist = "Various Artists" if is_compilation else next(iter(artists))

            return {
                "artist": display_artist,
                "album": album_name,
                "tracks": track_list,
                "is_compilation": is_compilation,
                "release_dir": release_dir,
            }

    def _get_release_dir(self, path: str) -> str:
        """Computes the release directory for a given track path relative to the music root.
        Returns the parent directory path, typically representing 'artist/album'.

        Args:
            path: The path to the track file.

        Returns:
            str: The release directory relative to the music root.
        """
        full_path = Path(path)
        relative_path = full_path.relative_to(self.music_root) if full_path.is_absolute() else full_path
        return str(relative_path.parent) + "/" # e.g., 'artist/album'

    def _sql_release_dir_expr(self) -> str:
        """Returns the SQL expression to extract the release directory from a track's path.
        Used to match and group tracks by their release directory in database queries.

        Returns:
            str: SQL expression for extracting the release directory from the path.
        """
        return "SUBSTR(path, 1, LENGTH(path) - LENGTH(filename))"  # e.g., 'artist/album/' (with trailing /)