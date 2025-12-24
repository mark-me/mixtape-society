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
        return str(Path(path).relative_to(self.music_root))

    def parse_query(self, query: str) -> dict[str, list[str]]:
        """Parses a search query string into tagged and general search terms.
        Extracts artist, album, track tags and general terms for advanced search functionality.

        Args:
            query: The search query string to parse.

        Returns:
            dict[str, list[str]]: Dictionary containing lists of terms for 'artist', 'album', 'track', and 'general'.
        """
        tags = {"artist": [], "album": [], "track": []}
        general: list[str] = []

        # Fixed regex: unquoted values stop before the next tag
        pattern = r'(artist|album|song)\s*:\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|(\S+(?:\s+(?!\s*(artist|album|song)\s*:\s*)\S+)*))'

        matches = re.finditer(pattern, query, re.IGNORECASE)
        last_end = 0

        for match in matches:
            if between := query[last_end : match.start()].strip():
                general.extend(between.split())

            tag_name = match.group(1).lower()
            if tag_name == "song":
                tag_name = "track"

            # Extract value from one of the three possible groups
            value = next(g for g in match.groups()[1:] if g is not None)

            # Unescape (handles \" , \' , \\ etc.)
            value = re.sub(r'\\(.)', r'\1', value)

            tags[tag_name].append(value.strip())

            last_end = match.end()

        if remaining := query[last_end:].strip():
            general.extend(remaining.split())

        return {**tags, "general": general}

    def search_grouped(self, query: str, limit: int = 20) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
        """Searches the music collection for artists, albums, and tracks matching the query.
        Returns grouped search results and the parsed search terms for further processing.

        Args:
            query: The search query string.
            limit: Maximum number of results to return for each group.

        Returns:
            tuple[dict[str, list[dict]], dict[str, list[str]]]: A tuple containing grouped search results and parsed terms.
        """
        if not query.strip():
            return {"artists": [], "albums": [], "tracks": []}, {}

        parsed = self.parse_query(query)
        has_specific = any(parsed[k] for k in ("artist", "album", "track"))
        conn = self._get_conn()
        use_fts = self._use_fts(conn)

        # Build column-specific expressions for tags
        expr_parts = []
        terms = {"artist": [], "album": [], "track": []}  # Renamed to terms for consistency

        for field_map, tag_key in [("artist", "artist"), ("album", "album"), ("title", "track")]:
            tag_terms = parsed.get(tag_key, [])
            if tag_terms:
                field_exprs = []
                for t in tag_terms:
                    escaped = self._fts_escape(t)
                    tokens = [tok for tok in escaped.split() if tok]
                    if not tokens:
                        continue
                    if len(tokens) > 1:
                        # Stricter: require ALL words for tagged multi-word searches
                        token_matches = [f'{tok}*' for tok in tokens]
                        field_exprs.append(f'({" AND ".join(token_matches)})')
                    else:
                        field_exprs.append(f'{escaped}*')
                # Still OR for multiple separate tags (e.g. song:"Weeping Song" song:"Mercy Seat")
                combined = " OR ".join(field_exprs)
                expr_parts.append(f'{field_map}:({combined})')
                terms[tag_key].extend(tag_terms)

        # Add general terms as OR across all fields
        if parsed["general"]:
            general_tokens = parsed["general"]
            general_exprs = [f'{tok}*' for tok in general_tokens]
            general_combined = " OR ".join(general_exprs)
            all_fields = f'(artist:({general_combined}) OR album:({general_combined}) OR title:({general_combined}))'
            expr_parts.append(all_fields)
            terms["artist"].extend(general_tokens)
            terms["album"].extend(general_tokens)
            terms["track"].extend(general_tokens)

        if not expr_parts:
            return {"artists": [], "albums": [], "tracks": []}, terms

        # Final expression: AND for different tag types (or general), OR if no specific tags
        join_op = " AND " if has_specific else " OR "
        final_expr = join_op.join(expr_parts)

        if use_fts:
            sql = """
                SELECT DISTINCT artist, album, title AS track, path, filename, duration
                FROM tracks_fts
                WHERE tracks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params = [final_expr, limit * 3]  # Buffer for grouping
        else:
            # Fallback LIKE (approximate)
            where_parts = []
            params = []
            for field_map, tag_key in [("artist", "artist"), ("album", "album"), ("title", "track")]:
                tag_terms = parsed.get(tag_key, [])
                if tag_terms:
                    likes = " OR ".join(f"lower({field_map}) LIKE ?" for _ in tag_terms)
                    where_parts.append(f"({likes})")
                    params.extend(f"%{t.lower()}%" for t in tag_terms)
            if parsed["general"]:
                gen_likes = " OR ".join("lower(artist) LIKE ? OR lower(album) LIKE ? OR lower(title) LIKE ?" for _ in parsed["general"])
                where_parts.append(f"({gen_likes})")
                for t in parsed["general"]:
                    tl = f"%{t.lower()}%"
                    params.extend([tl, tl, tl])

            if not where_parts:
                return {"artists": [], "albums": [], "tracks": []}, terms

            join_op = " AND " if has_specific else " OR "
            sql = f"""
                SELECT DISTINCT artist, album, title AS track, path, filename, duration
                FROM tracks
                WHERE {' '.join(where_parts) if join_op == ' OR ' else join_op.join(where_parts)}
                LIMIT ?
            """
            params.append(limit * 3)

        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur]

        # Post-process
        releases_by_dir = defaultdict(list)
        for row in rows:
            release_dir = self._get_release_dir(row["path"])
            releases_by_dir[release_dir].append(row)

        # Extract unique artists, albums, and tracks
        matched_artists = set()
        matched_releases = []  # List of dicts for releases
        all_tracks = []

        for release_dir, group in releases_by_dir.items():
            # Derive release info from group (assume consistent album/artist where possible)
            album_name = group[0]["album"]  # Assume uniform
            artists = {r["artist"] for r in group}
            is_compilation = len(artists) > 3
            display_artist = "Various Artists" if is_compilation else group[0]["artist"]

            matched_artists.update(artists)
            matched_releases.append({
                "display_artist": display_artist,
                "album": album_name,
                "is_compilation": is_compilation,
                "release_dir": release_dir,
            })
            all_tracks.extend(group)

        # Sort releases by album name
        matched_releases.sort(key=lambda x: x["album"])

        # Determine which types to include based on tags
        include_artists = bool(parsed["artist"]) or not has_specific
        include_albums = bool(parsed["album"]) or not has_specific
        include_tracks = bool(parsed["track"]) or not has_specific

        artists = []
        albums = []
        tracks = []

        # Build lists conditionally
        if include_artists:
            artists_list = sorted(matched_artists)[:limit]
            artists = [{"artist": a} for a in artists_list]

        if include_albums:
            # In tagged searches: suppress albums from shown artists
            excluded_artists = set(a["artist"] for a in artists) if has_specific and include_artists else set()
            albums_to_show = [
                r for r in matched_releases
                if r["display_artist"] not in excluded_artists
            ]
            albums = albums_to_show[:limit]

        if include_tracks:
            # In tagged searches: suppress tracks from shown artists/albums
            # In general searches: allow tracks even from shown artists (title matches are valuable)
            excluded_artists = (
                {a["artist"] for a in artists}
                if has_specific and include_artists
                else set()
            )
            excluded_albums = set((a["artist"], a["album"]) for a in albums) if has_specific and include_albums else set()

            tracks_to_show = []
            for row in all_tracks:
                if len(tracks_to_show) >= limit:
                    break
                a, al = row["artist"], row["album"]
                if has_specific and (a in excluded_artists or (a, al) in excluded_albums):
                    continue
                tracks_to_show.append(row)
            tracks = tracks_to_show

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
        expected_dir = f"{release_dir}/"

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
        return str(relative_path.parent)  # e.g., 'artist/album'

    def _sql_release_dir_expr(self) -> str:
        """Returns the SQL expression to extract the release directory from a track's path.
        Used to match and group tracks by their release directory in database queries.

        Returns:
            str: SQL expression for extracting the release directory from the path.
        """
        return "SUBSTR(path, 1, LENGTH(path) - LENGTH(filename))"  # e.g., 'artist/album/' (with trailing /)