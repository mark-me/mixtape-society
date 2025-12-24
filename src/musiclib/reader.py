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
    def _format_duration(duration: float | int | str | None) -> str:
        """Formats a duration in seconds into a MM:SS string.
        Returns a placeholder if the duration is not provided.

        Args:
            duration: The duration in seconds.

        Returns:
            str: The formatted duration as MM:SS or a placeholder if not available.
        """
        if duration is None:
            return "?:??"

        # Already formatted string (e.g. '8:27')
        if isinstance(duration, str):
            duration = duration.strip()
            return duration.lstrip("0") or "0:00" if ":" in duration else "?:??"
        # Numeric seconds
        try:
            total_seconds = int(float(duration))
        except (TypeError, ValueError):
            return "?:??"

        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

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
        query = query.strip()
        if not query:
            return {"artists": [], "albums": [], "tracks": []}, {
                "artist": [],
                "album": [],
                "track": [],
                "general": [],
            }

        terms = self._parse_query(query)
        if not any(terms.values()):
            return {"artists": [], "albums": [], "tracks": []}, terms

        has_artist = bool(terms["artist"])
        has_album = bool(terms["album"])
        has_track = bool(terms["track"])
        has_general = bool(terms["general"])
        is_free_text = not (has_artist or has_album or has_track)

        with self._get_conn() as conn:
            use_fts = self._use_fts(conn)

            # --- fetch rows (same idea as before) ---
            if use_fts:
                fts_terms = terms["artist"] + terms["album"] + terms["track"] + terms["general"]
                fts_query = " OR ".join(f"{self._fts_escape(t)}*" for t in fts_terms) or "1=0"

                sql = """
                    SELECT artist, album, title, path, filename, duration,
                        SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) AS release_dir
                    FROM tracks_fts
                    WHERE tracks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """
                rows = conn.execute(sql, (fts_query, limit * 6)).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT artist, album, title, path, filename, duration,
                        SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) AS release_dir
                    FROM tracks
                    ORDER BY artist, album, title
                    LIMIT ?
                    """,
                    (limit * 6,),
                ).fetchall()

        # =========================================================
        # PASS 1 — collect scored candidates
        # =========================================================

        artist_candidates = {}
        album_candidates = {}
        track_candidates = []

        for row in rows:
            artist = row["artist"] or "Unknown Artist"
            album = row["album"] or "Unknown Album"
            title = row["title"] or ""
            release_dir = row["release_dir"]

            artist_score = 0
            album_score = 0
            track_score = 0

            # --- artist scoring ---
            if has_artist:
                artist_score = self._score_text(artist, terms["artist"]) + self._tag_bonus(True)
            elif is_free_text:
                artist_score = self._score_text(artist, terms["general"])

            # --- album scoring ---
            if has_album:
                album_score = self._score_text(album, terms["album"]) + self._tag_bonus(True)
            elif is_free_text:
                album_score = self._score_text(album, terms["general"])

            # --- track scoring ---
            if has_track or has_general:
                track_score = self._score_text(title, terms["track"] + terms["general"])

            # Register artist
            if artist_score > 0:
                artist_candidates[artist] = max(
                    artist_candidates.get(artist, 0), artist_score
                )

            # Register album
            if album_score > 0:
                album_candidates[release_dir] = {
                    "artist": artist,
                    "album": album,
                    "release_dir": release_dir,
                    "score": max(
                        album_candidates.get(release_dir, {}).get("score", 0),
                        album_score,
                    ),
                }

            # Register track
            if track_score > 0:
                track_candidates.append({
                    "artist": artist,
                    "album": album,
                    "track": title,
                    "path": self._relative_path(row["path"]),
                    "filename": row["filename"],
                    "duration": self._format_duration(row["duration"]),
                    "release_dir": release_dir,
                    "score": track_score,
                })

        # =========================================================
        # PASS 2 — hierarchy + suppression
        # =========================================================

        artists = []
        albums = []
        tracks = []

        covered_artists = set()
        covered_albums = set()

        # --- artists first ---
        for artist, score in sorted(
            artist_candidates.items(), key=lambda x: x[1], reverse=True
        ):
            if len(artists) >= limit:
                break
            artists.append({"artist": artist})
            covered_artists.add(artist)

        # --- albums next ---
        for album in sorted(
            album_candidates.values(), key=lambda x: x["score"], reverse=True
        ):
            if len(albums) >= limit:
                break
            if album["artist"] in covered_artists:
                continue

            albums.append({
                "artist": album["artist"],
                "display_artist": album["artist"],
                "album": album["album"],
                "release_dir": album["release_dir"],
                "is_compilation": False,
            })
            covered_albums.add(album["release_dir"])

        # --- tracks last ---
        for track in sorted(track_candidates, key=lambda x: x["score"], reverse=True):
            if len(tracks) >= limit:
                break
            if track["artist"] in covered_artists:
                continue
            if track["release_dir"] in covered_albums:
                continue

            tracks.append(track)

        return {
            "artists": artists,
            "albums": albums,
            "tracks": tracks,
        }, terms

    def _score_text(self, text: str, terms: list[str]) -> int:
        """Calculates a relevance score for text based on a list of search terms.
        Prioritizes exact, prefix, and substring matches to influence search ranking.

        Args:
            text: The text to evaluate against the search terms.
            terms: A list of search terms to compare with the text.

        Returns:
            int: The highest relevance score assigned based on the best matching term.
        """
        if not text:
            return 0

        text_l = text.lower()
        best = 0

        for term in terms:
            term_l = term.lower()

            if text_l == term_l:
                best = max(best, 100)
            elif text_l.startswith(term_l):
                best = max(best, 70)
            elif term_l in text_l:
                best = max(best, 40)

        return best


    def _tag_bonus(self, has_tag: bool) -> int:
        """Calculates a score bonus when a search term is explicitly tagged.
        Helps prioritize results that match user-specified tags over general matches.

        Args:
            has_tag: Whether the term was provided with an explicit tag (e.g., artist:, album:).

        Returns:
            int: The bonus score to be added when a tag is present.
        """
        return 30 if has_tag else 0

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