import hashlib
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from threading import Thread
from time import time

from tinytag import TinyTag
from PIL import Image

from common.logging import Logger, NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import get_indexing_status


@dataclass
class SearchSession:
    """Represents the state of a single search operation within the music collection.
    Stores the original query, parsed terms, candidate results, and timing information for the search.

    Attributes:
        query: The raw search query string entered by the user.
        terms: A dictionary of parsed search terms grouped by category (e.g., artist, album, track, general).
        artist_candidates: A mapping of artist names to their computed relevance scores.
        album_candidates: A mapping of album identifiers to their associated metadata and relevance scores.
        track_candidates: A list of track candidate entries considered during scoring.
        timestamp: The time at which the search session was created or last updated.
    """

    query: str
    terms: dict
    artist_candidates: dict
    album_candidates: dict
    track_candidates: list
    timestamp: float


class MusicCollection:
    """Manages a music collection database and provides search and detail retrieval functionality.
    Handles lazy loading, background indexing, and query parsing for artists, albums, and tracks.
    """

    EXACT_MATCH_SCORE = 100
    PREFIX_MATCH_SCORE = 70
    SUBSTRING_MATCH_SCORE = 40
    TAG_BONUS = 30

    def __init__(
        self, music_root: Path | str, db_path: Path | str, logger: Logger = None
    ) -> None:
        """Initializes a MusicCollection backed by a SQLite database and music root directory.
        Sets up logging, collection extraction, and schedules any required initial indexing or resync operations.

        Args:
            music_root: The root directory containing the music files to be indexed.
            db_path: The path to the SQLite database file used to store collection metadata.
            logger: Optional logger instance for recording informational and error messages.
        """
        self.music_root = Path(music_root).resolve()
        self.db_path = Path(db_path)
        self._logger = logger or NullLogger()
        self._extractor = CollectionExtractor(self.music_root, self.db_path, logger=logger)

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

        self._last_search_session: SearchSession | None = None

        self.covers_dir = self.db_path.parent / "cache" / "covers"
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self._setup_fallback_cover()

    def is_indexing(self) -> bool:
        status = get_indexing_status(self.db_path.parent)

        # If status file exists and indicates active job → yes
        if status and status.get("status") in ("rebuilding", "resyncing"):
            return True

        return status is None and self.count() == 0

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
        """Converts a duration value into a human-readable minutes and seconds string.
        Handles numeric seconds, pre-formatted strings, and missing or invalid values gracefully.

        Args:
            duration: The duration value as seconds, a pre-formatted string, or None.

        Returns:
            str: A string in the format 'M:SS' or a placeholder such as '?:??' when unknown.
        """
        if duration is None:
            return "?:??"

        # Already formatted string (e.g. '8:27')
        if isinstance(duration, str):
            duration = duration.strip()
            # If it's a time-like string, preserve it, but handle degenerate values
            if ":" in duration:
                # Remove a single leading '0' from the minutes part (e.g. '08:27' -> '8:27')
                normalized = duration.lstrip("0")
                # If everything was zeros (e.g. '00:00', '0:00'), fall back to a clear zero duration
                return normalized or "0:00"
            # Non time-like strings are treated as unknown duration
            return duration.lstrip("0") or "0:00" if ":" in duration else "?:??"
        # Numeric seconds
        try:
            total_seconds = int(float(duration))
        except (TypeError, ValueError):
            return "?:??"

        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def _build_track_dict(
        self, row: dict, artist: str | None = None, album: str | None = None
    ) -> dict:
        """Builds a track dictionary from a database row.

        Args:
            row: The database row.
            artist: Optional artist override.
            album: Optional album override.

        Returns:
            dict: The track dictionary with cover information.
        """
        # Get the release directory to fetch the cover
        release_dir = self._get_release_dir(row["path"])

        return {
            "artist": artist or row["artist"],
            "track": row["title"],
            "path": self._relative_path(row["path"]),
            "filename": row["filename"],
            "duration": self._format_duration(row["duration"]),
            "album": album or row["album"],
            "cover": self.get_cover(release_dir),
        }

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
                self._logger.warning(
                    f"Path {path} not under music_root {self.music_root}"
                )
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

        tagged_terms, remaining = self._parse_tagged_terms(query)
        general_terms = self._parse_general_terms(remaining)
        tagged_terms["general"].extend([p for p in general_terms if p])

        for key in tagged_terms:
            tagged_terms[key] = self._clean_term_list(tagged_terms[key])

        return tagged_terms

    def _parse_tagged_terms(self, query: str) -> tuple[dict[str, list[str]], str]:
        """Extracts tagged terms from the query using regex and removes them, returning the terms and remaining query.

        Args:
            query: The search query string to parse.

        Returns:
            tuple[dict[str, list[str]], str]: Tagged terms grouped by category and the remaining query string.
        """
        terms = {
            "artist": [],
            "album": [],
            "track": [],  # also used for 'song:'
            "general": [],
        }

        # Regex to match: tag:"quoted phrase" or tag:word
        tag_pattern = re.compile(
            r'(artist|album|track|song):"([^"]+)"|(artist|album|track|song):([^\s]+)',
            re.IGNORECASE,
        )

        # Find all tagged terms first
        tagged_matches = list(tag_pattern.finditer(query))

        # Process tagged terms (from right to left to avoid index shifting)
        for match in reversed(tagged_matches):
            tag_type = (match.group(1) or match.group(3)).lower()
            value = match.group(2) or match.group(4)

            if tag_type == "song":
                tag_type = "track"

            if value.strip():
                terms[tag_type].append(value.strip())

            # Remove this tagged part from the query
            start, end = match.span()
            query = query[:start] + query[end:]

        return terms, query.strip()

    def _parse_general_terms(self, remaining: str) -> list[str]:
        """Parses the remaining query into general terms, preserving quoted phrases and splitting words.

        Args:
            remaining: The remaining query string after tagged terms are removed.

        Returns:
            list[str]: List of general terms.
        """
        parts = []
        i = 0
        while i < len(remaining):
            if remaining[i] == '"':
                # Find closing quote
                j = remaining.find('"', i + 1)
                if j == -1:
                    j = len(remaining)
                phrase = remaining[i + 1 : j]
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
        return parts

    def _clean_term_list(self, term_list: list[str]) -> list[str]:
        """Cleans a list of terms by stripping, removing invalid wildcards, and normalizing.

        Args:
            term_list: List of terms to clean.

        Returns:
            list[str]: Cleaned and normalized list of terms.
        """
        cleaned = []
        for term in term_list:
            term = term.strip()
            # Remove standalone wildcards
            if term in ("*", "%"):
                continue
            # Remove leading/trailing wildcards
            term = term.strip("*%")
            if term:
                cleaned.append(term)
        return cleaned

    def search_grouped(self, query: str, limit: int = 30) -> tuple[dict, dict]:
        """Searches the music collection and returns grouped results by artists, albums, and tracks.
        Also returns the parsed terms for highlighting.

        Args:
            query: The search query string.
            limit: Maximum number of results to return per group.

        Returns:
            tuple[dict, dict]: A tuple of (grouped results, parsed terms).
        """
        if not query.strip():
            return {"artists": [], "albums": [], "tracks": []}, {}

        terms = self._parse_query(query)
        has_artist = bool(terms["artist"])
        has_album = bool(terms["album"])
        is_free_text = not has_artist and not has_album and not terms["track"]

        reuse_session = self._last_search_session
        can_reuse = self._can_reuse_session(reuse_session, query, terms)

        if can_reuse:
            artist_candidates, album_candidates, track_candidates = (
                self._collect_pass_two_candidates(
                    reuse_session=reuse_session,
                    terms=terms,
                    has_artist=has_artist,
                    has_album=has_album,
                    is_free_text=is_free_text,
                )
            )
        else:
            artist_candidates, album_candidates, track_candidates = (
                self._collect_pass_one_candidates(
                    terms=terms,
                    limit=limit,
                    has_artist=has_artist,
                    has_album=has_album,
                    is_free_text=is_free_text,
                )
            )

        grouped = self._build_hierarchical_results(
            artist_candidates=artist_candidates,
            album_candidates=album_candidates,
            track_candidates=track_candidates,
            limit=limit,
        )

        self._last_search_session = SearchSession(
            query=query,
            terms=terms,
            artist_candidates=artist_candidates,
            album_candidates=album_candidates,
            track_candidates=track_candidates,
            timestamp=time(),
        )

        return grouped, terms

    def _collect_pass_two_candidates(
        self,
        reuse_session: SearchSession,
        terms: dict,
        has_artist: bool,
        has_album: bool,
        is_free_text: bool,
    ) -> tuple[dict[str, int], dict[str, dict], list[dict]]:
        """Refines existing search session candidates by rescoring them with new terms.
        Avoids re-querying the database when the query is a refinement of a previous search.

        Args:
            reuse_session: The previous search session to reuse.
            terms: The new parsed search terms.
            has_artist: Whether the query includes explicit artist terms.
            has_album: Whether the query includes explicit album terms.
            is_free_text: Whether the query is purely free-text without explicit tags.

        Returns:
            tuple[dict[str, int], dict[str, dict], list[dict]]: Updated mappings of artist, album, and track candidates.
        """
        artist_candidates: dict[str, int] = {}
        album_candidates: dict[str, dict] = {}
        track_candidates: list[dict] = []

        for artist, _ in reuse_session.artist_candidates.items():
            score = self._score_artist(artist, terms, has_artist, is_free_text)
            if score > 0:
                artist_candidates[artist] = score

        for release_dir, album in reuse_session.album_candidates.items():
            score = self._score_album(album["album"], terms, has_album, is_free_text)
            if score > 0:
                album_candidates[release_dir] = {
                    **album,
                    "score": score,
                }

        for track in reuse_session.track_candidates:
            score = self._score_track(track["track"], terms)
            if score > 0:
                t = dict(track)
                t["score"] = score
                track_candidates.append(t)

        return artist_candidates, album_candidates, track_candidates

    def _collect_pass_one_candidates(
        self,
        terms: dict,
        limit: int,
        has_artist: bool,
        has_album: bool,
        is_free_text: bool,
    ) -> tuple[dict[str, int], dict[str, dict], list[dict]]:
        """Collects and scores artist, album, and track candidates for the first search pass.
        Queries the database using FTS when available and converts matching rows into scored result candidates.

        Args:
            terms: Parsed search terms grouped by category.
            limit: Base limit used to bound the number of rows fetched from the database.
            has_artist: Whether the query includes explicit artist terms.
            has_album: Whether the query includes explicit album terms.
            is_free_text: Whether the query is purely free-text without explicit tags.

        Returns:
            tuple[dict[str, int], dict[str, dict], list[dict]]: Mappings of artist and album candidates,
                and a list of track candidates, each with associated relevance scores.
        """
        artist_candidates: dict[str, int] = {}
        album_candidates: dict[str, dict] = {}
        track_candidates: list[dict] = []

        rows = self._fetch_candidate_rows(terms, limit)

        for row in rows:
            self._score_row_candidates(
                row=row,
                terms=terms,
                has_artist=has_artist,
                has_album=has_album,
                is_free_text=is_free_text,
                artist_candidates=artist_candidates,
                album_candidates=album_candidates,
                track_candidates=track_candidates,
            )

        return artist_candidates, album_candidates, track_candidates

    def _fetch_candidate_rows(
        self, terms: dict, limit: int
    ) -> list[dict[str, str | float]]:
        """Fetches raw candidate rows from the database for the first search pass.
        Uses full-text search when available, falling back to ordered scans otherwise.

        Args:
            terms: Parsed search terms grouped by category.
            limit: Base limit used to bound the number of rows fetched from the database.

        Returns:
            list[dict[str, str | float]]: A sequence of database rows containing artist, album, title, path, filename, duration, and release_dir.
        """
        with self._get_conn() as conn:
            if use_fts := self._use_fts(conn):  # noqa: F841
                all_terms = (
                    terms["artist"] + terms["album"] + terms["track"] + terms["general"]
                )
                fts_query = (
                    " OR ".join(f"{self._fts_escape(t)}*" for t in all_terms)
                    if all_terms
                    else "1=0"
                )

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
                    ORDER BY artist COLLATE NOCASE,
                            album COLLATE NOCASE,
                            title COLLATE NOCASE
                    LIMIT ?
                    """,
                    (limit * 6,),
                ).fetchall()

        return rows

    def _score_row_candidates(
        self,
        row,
        terms: dict,
        has_artist: bool,
        has_album: bool,
        is_free_text: bool,
        artist_candidates: dict[str, int],
        album_candidates: dict[str, dict],
        track_candidates: list[dict],
    ) -> None:
        """Scores a single database row and updates artist, album, and track candidate collections.
        Computes relevance scores for each level and appends or updates candidates when they match.

        Args:
            row: A database row containing track metadata and release directory.
            terms: Parsed search terms grouped by category.
            has_artist: Whether the query includes explicit artist terms.
            has_album: Whether the query includes explicit album terms.
            is_free_text: Whether the query is purely free-text without explicit tags.
            artist_candidates: Mapping of artist names to their current best scores.
            album_candidates: Mapping of release directories to album metadata and scores.
            track_candidates: List of track candidate dictionaries to be appended to.
        """
        artist = row["artist"] or "Unknown Artist"
        album = row["album"] or "Unknown Album"
        title = row["title"] or ""
        release_dir = row["release_dir"]

        artist_score = self._score_artist(artist, terms, has_artist, is_free_text)
        if artist_score > 0:
            artist_candidates[artist] = max(
                artist_candidates.get(artist, 0), artist_score
            )

        album_score = self._score_album(album, terms, has_album, is_free_text)
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

        track_score = self._score_track(title, terms)
        if track_score > 0:
            track_candidates.append(
                {
                    "artist": artist,
                    "album": album,
                    "track": title,
                    "path": self._relative_path(row["path"]),
                    "filename": row["filename"],
                    "duration": self._format_duration(row["duration"]),
                    "release_dir": release_dir,
                    "score": track_score,
                }
            )

    def _is_compilation_album(self, release_dir: str) -> bool:
        """Determines if an album is a compilation by checking the number of unique artists.

        Args:
            release_dir: The release directory to check.

        Returns:
            bool: True if the album has more than 3 unique artists, False otherwise.
        """
        expected_dir = release_dir if release_dir.endswith("/") else f"{release_dir}/"

        with self._get_conn() as conn:
            cur = conn.execute(
                f"""
                SELECT COUNT(DISTINCT artist) as artist_count
                FROM tracks
                WHERE {self._sql_release_dir_expr()} = ?
                """,
                (expected_dir,),
            )
            row = cur.fetchone()
            artist_count = row["artist_count"] if row else 0
            return artist_count > 3

    def _build_hierarchical_results(
        self,
        artist_candidates: dict[str, int],
        album_candidates: dict[str, dict],
        track_candidates: list[dict],
        limit: int,
    ) -> dict:
        """Builds grouped artist, album, and track results from flat candidate scores.
        Applies hierarchical suppression so that higher-level matches hide lower-level ones from the same scope.

        Args:
            artist_candidates: Mapping of artist names to their relevance scores.
            album_candidates: Mapping of release directories to album metadata and relevance scores.
            track_candidates: List of track candidate dictionaries including scores and metadata.
            limit: Maximum number of items to include per result group.

        Returns:
            dict: A dictionary with grouped 'artists', 'albums', and 'tracks' search results.
        """
        artists, covered_artists = self._build_artist_results(
            artist_candidates=artist_candidates,
            limit=limit,
        )

        albums, covered_albums = self._build_album_results(
            album_candidates=album_candidates,
            covered_artists=covered_artists,
            limit=limit,
        )

        tracks = self._build_track_results(
            track_candidates=track_candidates,
            covered_artists=covered_artists,
            covered_albums=covered_albums,
            limit=limit,
        )
        with self._get_conn() as conn:
            # Add album counts for each artist result
            for artist in artists:
                count_query = (
                    "SELECT COUNT(DISTINCT album) FROM tracks WHERE artist = ?"
                )
                artist["num_albums"] = (
                    conn.execute(count_query, (artist["artist"],)).fetchone()[0] or 0
                )

            # Add track counts for each album result
            for album in albums:
                expr = (
                    self._sql_release_dir_expr()
                )  # Reuses your existing method for release_dir expression
                count_query = f"SELECT COUNT(*) FROM tracks WHERE {expr} = ?"
                album["num_tracks"] = (
                    conn.execute(count_query, (album["release_dir"],)).fetchone()[0]
                    or 0
                )

        return {
            "artists": artists,
            "albums": albums,
            "tracks": tracks,
        }

    def _build_artist_results(
        self,
        artist_candidates: dict[str, int],
        limit: int,
    ) -> tuple[list[dict], set[str]]:
        """Builds the ordered list of artist results from artist candidates.
        Tracks which artists are covered so albums and tracks can be suppressed accordingly.

        Args:
            artist_candidates: Mapping of artist names to their relevance scores.
            limit: Maximum number of artist items to include.

        Returns:
            tuple[list[dict], set[str]]: The artist result list and the set of covered artist names.
        """
        artists: list[dict] = []
        covered_artists: set[str] = set()

        for artist, score in sorted(
            artist_candidates.items(), key=lambda x: x[1], reverse=True
        ):
            if len(artists) >= limit:
                break
            artists.append({"artist": artist})
            covered_artists.add(artist)

        return artists, covered_artists

    def _build_album_results(
        self,
        album_candidates: dict[str, dict],
        covered_artists: set[str],
        limit: int,
    ) -> tuple[list[dict], set[str]]:
        """Builds the ordered list of album results from album candidates.
        Skips albums whose artist is already covered by an artist result and tracks covered release directories.

        Args:
            album_candidates: Mapping of release directories to album metadata and relevance scores.
            covered_artists: Set of artist names already represented in artist results.
            limit: Maximum number of album items to include.

        Returns:
            tuple[list[dict], set[str]]: The album result list and the set of covered release directory identifiers.
        """
        albums: list[dict] = []
        covered_albums: set[str] = set()

        for album in sorted(
            album_candidates.values(), key=lambda x: x["score"], reverse=True
        ):
            if len(albums) >= limit:
                break
            if album["artist"] in covered_artists:
                continue

            # Check if this is a compilation album
            is_compilation = self._is_compilation_album(album["release_dir"])
            display_artist = "Various Artists" if is_compilation else album["artist"]

            albums.append(
                {
                    "artist": album["artist"],
                    "display_artist": display_artist,
                    "album": album["album"],
                    "release_dir": album["release_dir"],
                    "is_compilation": is_compilation,
                    "cover": self.get_cover(album["release_dir"])
                }
            )
            covered_albums.add(album["release_dir"])

        return albums, covered_albums

    def _build_track_results(
        self,
        track_candidates: list[dict],
        covered_artists: set[str],
        covered_albums: set[str],
        limit: int,
    ) -> list[dict]:
        """Builds the ordered list of track results from track candidates.
        Skips tracks whose artist or release directory is already covered by higher-level results.

        Args:
            track_candidates: List of track candidate dictionaries including scores and metadata.
            covered_artists: Set of artist names already represented in artist results.
            covered_albums: Set of release directory identifiers already represented in album results.
            limit: Maximum number of track items to include.

        Returns:
            list[dict]: The final list of track result dictionaries.
        """
        tracks: list[dict] = []

        for track in sorted(track_candidates, key=lambda x: x["score"], reverse=True):
            if len(tracks) >= limit:
                break
            if track["artist"] in covered_artists:
                continue
            if track["release_dir"] in covered_albums:
                continue

            tracks.append(track)

        return tracks

    def _terms_compatible(self, old: dict, new: dict) -> bool:
        """Checks whether a new set of parsed search terms is compatible with a previous set.
        Ensures the new terms only refine the old terms without introducing independent new prefixes.

        Args:
            old: The previous set of parsed terms grouped by category.
            new: The new set of parsed terms to compare against the previous set.

        Returns:
            bool: True if the new terms are compatible refinements of the old terms, False otherwise.
        """
        for key in ("artist", "album", "track", "general"):
            old_terms = old.get(key, [])
            new_terms = new.get(key, [])

            # cannot add new independent terms
            if len(new_terms) < len(old_terms):
                return False

            for i, old_term in enumerate(old_terms):
                if not new_terms[i].startswith(old_term):
                    return False

        return True

    def _can_reuse_session(
        self, session: SearchSession, query: str, terms: dict
    ) -> bool:
        """Determines whether a previous search session can be reused for the current query.
        Checks that the new query extends the previous one and that the term structure remains compatible.

        Args:
            session: The previous search session to compare against.
            query: The new search query string.
            terms: The parsed terms for the new query.

        Returns:
            bool: True if the previous session can be reused, False otherwise.
        """
        if not session:
            return False

        if not query.startswith(session.query):
            return False

        # Same tag structure
        for key in ("artist", "album", "track"):
            if bool(session.terms[key]) != bool(terms[key]):
                return False

        return self._terms_compatible(session.terms, terms)

    def _score_text(self, text: str, terms: list[str]) -> int:
        # sourcery skip: assign-if-exp, reintroduce-else
        """Calculates a relevance score for text based on a list of search terms.
        Prioritizes exact, prefix, and substring matches to influence search ranking.

        Args:
            text: The text to evaluate against the search terms.
            terms: A list of search terms to compare with the text.

        Returns:
            int: The highest relevance score assigned based on the best matching term.
        """
        if not text or not terms:
            return 0

        text_l = text.lower()
        best = 0
        matched_terms = 0

        for term in terms:
            term_l = term.lower()
            term_matched = False

            if text_l == term_l:
                best = max(best, self.EXACT_MATCH_SCORE)
                term_matched = True
            elif text_l.startswith(term_l):
                best = max(best, self.PREFIX_MATCH_SCORE)
                term_matched = True
            elif term_l in text_l:
                best = max(best, self.SUBSTRING_MATCH_SCORE)
                term_matched = True

            if term_matched:
                matched_terms += 1

        # For multi-word queries, ALL terms must match
        if len(terms) > 1 and matched_terms < len(terms):
            return 0

        return best

    def _score_artist(
        self, artist: str, terms: dict, has_artist: bool, is_free_text: bool
    ) -> int:
        """Computes the score for an artist based on terms.

        Args:
            artist: The artist name to score.
            terms: Parsed search terms.
            has_artist: Whether explicit artist terms are present.
            is_free_text: Whether the query is free-text.

        Returns:
            int: The computed score.
        """
        score = 0
        if has_artist:
            score = self._score_text(artist, terms["artist"]) + self._tag_bonus(True)
        elif is_free_text:
            score = self._score_text(artist, terms["general"])
        return score

    def _score_album(
        self, album_name: str, terms: dict, has_album: bool, is_free_text: bool
    ) -> int:
        """Computes the score for an album based on terms.

        Args:
            album_name: The album name to score.
            terms: Parsed search terms.
            has_album: Whether explicit album terms are present.
            is_free_text: Whether the query is free-text.

        Returns:
            int: The computed score.
        """
        score = 0
        if has_album:
            score = self._score_text(album_name, terms["album"]) + self._tag_bonus(True)
        elif is_free_text:
            score = self._score_text(album_name, terms["general"])
        return score

    def _score_track(self, track_name: str, terms: dict) -> int:
        """Computes the score for a track based on terms.

        Args:
            track_name: The track name to score.
            terms: Parsed search terms.

        Returns:
            int: The computed score.
        """
        return self._score_text(track_name, terms["track"] + terms["general"])

    def _tag_bonus(self, has_tag: bool) -> int:
        """Calculates a score bonus when a search term is explicitly tagged.
        Helps prioritize results that match user-specified tags over general matches.

        Args:
            has_tag: Whether the term was provided with an explicit tag (e.g., artist:, album:).

        Returns:
            int: The bonus score to be added when a tag is present.
        """
        return self.TAG_BONUS if has_tag else 0

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
                SELECT album, title, path, filename, duration, disc_number, track_number
                FROM tracks
                WHERE artist = ?
                ORDER BY album COLLATE NOCASE, disc_number, track_number, title COLLATE NOCASE
                """,
                (artist,),
            )
            releases_map = defaultdict(list)
            for row in cur:
                release_dir = self._get_release_dir(row["path"])
                releases_map[release_dir].append(
                    self._build_track_dict(row, artist=artist, album=row["album"])
                )

            albums = []
            for release_dir, tracks in sorted(
                releases_map.items(),
                key=lambda x: x[1][0].get("album", "") if x[1] else "",
            ):
                album_name = (
                    tracks[0].get("album", "Unknown Album")
                    if tracks
                    else "Unknown Album"
                )
                album_cover = self.get_cover(release_dir)

                # Check if this is a compilation album
                is_compilation = self._is_compilation_album(release_dir)

                albums.append(
                    {
                        "album": album_name,
                        "cover": album_cover,
                        "tracks": tracks,
                        "release_dir": release_dir,
                        "is_compilation": is_compilation,
                    }
                )

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
        expected_dir = release_dir if release_dir.endswith("/") else f"{release_dir}/"

        with self._get_conn() as conn:
            cur = conn.execute(
                f"""
                SELECT artist, title, path, filename, duration, album
                FROM tracks
                WHERE {self._sql_release_dir_expr()} = ?
                ORDER BY disc_number, track_number, title COLLATE NOCASE
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
                    "release_dir": release_dir,
                }

            # Album name from first row
            album_name = rows[0]["album"] or "Unknown Album"

            # Build track list
            track_list = [self._build_track_dict(row) for row in rows]

            # Detect compilation
            artists = {t["artist"] for t in track_list if t["artist"]}
            is_compilation = len(artists) > 3
            display_artist = (
                "Various Artists" if is_compilation else next(iter(artists))
            )

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
        relative_path = (
            full_path.relative_to(self.music_root)
            if full_path.is_absolute()
            else full_path
        )
        return f"{str(relative_path.parent)}/"

    def _sql_release_dir_expr(self) -> str:
        """Returns the SQL expression to extract the release directory from a track's path.
        Used to match and group tracks by their release directory in database queries.

        Returns:
            str: SQL expression for extracting the release directory from the path.
        """
        return "SUBSTR(path, 1, LENGTH(path) - LENGTH(filename))"  # e.g., 'artist/album/' (with trailing /)

    def get_track(self, path: Path) -> dict | None:
        """Retrieves metadata for a single track identified by its path.

        Queries the music library database for the track and returns a normalized metadata dictionary if found.

        Args:
            path: The full or relative path of the track to look up.

        Returns:
            dict | None: A dictionary of track metadata if the track exists, otherwise None.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT path, filename, artist, album, title, albumartist, track_number, disc_number, duration, mtime
                FROM tracks
                WHERE path = ?
                """,
                (str(path),),
            )
            if rows := cur.fetchall():
                track = rows[0]
                # Get the release directory to fetch the cover
                release_dir = self._get_release_dir(track["path"])

                return {
                    "path": Path(path),
                    "filename": track["filename"],
                    "artist": track["artist"],
                    "album": track["album"],
                    "track": track["title"],
                    "albumartist": track["albumartist"],
                    "track_number": track["track_number"],
                    "disc_number": track["disc_number"],
                    "duration": self._format_duration(track["duration"]),
                    "time_added": track["mtime"],
                    "cover": self.get_cover(release_dir),
                }
            else:
                return None


    def get_cover(self, release_dir: str) -> str | None:
        """Retrieves or generates the cover image path for a given album release directory.
        Returns a relative path to a cached or newly extracted cover image if available,
        or a fallback image path if no cover is found.

        Args:
            release_dir: The release directory identifier used to locate or derive the cover image.

        Returns:
            str | None: Relative path to the cover image within the covers directory, or fallback image path if not found.
        """
        if not release_dir:
            return "covers/_fallback.jpg"

        # Sanitize to a safe filename slug
        slug = self._sanitize_release_dir(release_dir)
        cover_path = self.covers_dir / f"{slug}.jpg"

        if cover_path.exists():
            return f"covers/{slug}.jpg"

        # Extract on demand
        if self._extract_cover(release_dir, cover_path):
            return f"covers/{slug}.jpg"

        return "covers/_fallback.jpg"

    def _setup_fallback_cover(self) -> None:
        """Ensures the fallback cover image exists in the covers directory.
        Copies the fallback image from static directory if it doesn't already exist.

        Returns:
            None
        """
        fallback_path = self.covers_dir / "_fallback.jpg"

        # If fallback already exists, we're done
        if fallback_path.exists():
            return

        if (
            source_path := Path(__file__).parent.parent
            / "static"
            / "cover-art-text.jpg"
        ):
            try:
                # Copy the fallback image to covers directory
                import shutil
                shutil.copy2(source_path, fallback_path)
                self._logger.info(f"Copied fallback cover from {source_path} to {fallback_path}")
            except Exception as e:
                self._logger.warning(f"Failed to copy fallback cover: {e}")
        else:
            self._logger.warning(
                "Fallback cover image 'cover-art-text.jpg' not found in static directory. "
                "Tracks without covers will not display properly."
            )

    def _sanitize_release_dir(self, release_dir: str) -> str:
        """Normalizes a release directory string into a safe filename slug.
        Produces a stable, filesystem-friendly identifier suitable for use in cover cache filenames.

        Args:
            release_dir: The release directory identifier to sanitize.

        Returns:
            str: A normalized slug representation of the release directory.
        """
        clean = (
            "".join(c if c.isalnum() or c in "-_ /" else "_" for c in release_dir)
            .strip("/")
            .replace("/", "_")
        )
        if len(clean) > 200:  # Truncate long paths
            clean = f"{clean[:100]}_{hashlib.md5(release_dir.encode()).hexdigest()[:8]}"
        return clean

    def _extract_cover(self, release_dir: str, target_path: Path) -> bool:
        """Attempts to locate or extract a cover image for a given release directory.
        Searches for existing image files or embedded artwork, resizes them to a reasonable size,
        and writes an optimized copy to the target path.

        Args:
            release_dir: The release directory relative to the music root where audio and image files are stored.
            target_path: The filesystem path where the discovered or extracted cover image should be written.

        Returns:
            bool: True if a cover image was successfully found and written, otherwise False.
        """
        abs_dir = self.music_root / release_dir.rstrip("/")
        if not abs_dir.is_dir():
            self._logger.warning(f"Release directory not found: {abs_dir}")
            return False

        # Configuration for cover optimization
        MAX_SIZE = 800  # Maximum width/height in pixels
        JPEG_QUALITY = 85  # JPEG quality (1-100)
        MAX_FILE_SIZE = 500 * 1024  # 500KB max file size

        # Step 1: Check for common image files in the folder
        common_cover_names = [
            "cover.jpg",
            "folder.jpg",
            "album.jpg",
            "front.jpg",
            "cover.png",
            "folder.png",
        ]

        for name in common_cover_names:
            img_path = abs_dir / name
            if img_path.exists():
                try:
                    if self._resize_and_save_cover(img_path, target_path, MAX_SIZE, JPEG_QUALITY, MAX_FILE_SIZE):
                        self._logger.info(f"Processed cover from {img_path} for {release_dir}")
                        return True
                except Exception as e:
                    self._logger.error(f"Failed to process cover {img_path}: {e}")
                    continue

        # Step 2: Extract embedded art from audio files
        for file in abs_dir.iterdir():
            if file.suffix.lower() in CollectionExtractor.SUPPORTED_EXTS:
                try:
                    tag = TinyTag.get(str(file), image=True)
                    if img_data := tag.get_image():
                        if self._resize_and_save_cover_from_bytes(img_data, target_path, MAX_SIZE, JPEG_QUALITY, MAX_FILE_SIZE):
                            self._logger.info(
                                f"Extracted and processed embedded cover from {file} for {release_dir}"
                            )
                            return True
                except Exception as e:
                    self._logger.warning(f"Failed to extract from {file}: {e}")
                    continue

        self._logger.info(f"No cover found for {release_dir}")
        return False

    def _resize_and_save_cover(
        self,
        source_path: Path,
        target_path: Path,
        max_size: int,
        quality: int,
        max_file_size: int
    ) -> bool:
        """Resize and optimize a cover image from a file path.

        Args:
            source_path: Path to the source image file.
            target_path: Path where the optimized image should be saved.
            max_size: Maximum dimension (width or height) in pixels.
            quality: JPEG quality (1-100).
            max_file_size: Maximum file size in bytes.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            with Image.open(source_path) as img:
                return self._process_and_save_image(img, target_path, max_size, quality, max_file_size)
        except Exception as e:
            self._logger.error(f"Failed to resize cover from {source_path}: {e}")
            return False

    def _resize_and_save_cover_from_bytes(
        self,
        img_data: bytes,
        target_path: Path,
        max_size: int,
        quality: int,
        max_file_size: int
    ) -> bool:
        """Resize and optimize a cover image from raw bytes.

        Args:
            img_data: Raw image data bytes.
            target_path: Path where the optimized image should be saved.
            max_size: Maximum dimension (width or height) in pixels.
            quality: JPEG quality (1-100).
            max_file_size: Maximum file size in bytes.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            with Image.open(io.BytesIO(img_data)) as img:
                return self._process_and_save_image(img, target_path, max_size, quality, max_file_size)
        except Exception as e:
            self._logger.error(f"Failed to resize cover from bytes: {e}")
            return False

    def _process_and_save_image(
        self,
        img: Image.Image,
        target_path: Path,
        max_size: int,
        quality: int,
        max_file_size: int
    ) -> bool:
        """Process and save an image with resizing and optimization.

        Args:
            img: PIL Image object to process.
            target_path: Path where the optimized image should be saved.
            max_size: Maximum dimension (width or height) in pixels.
            quality: JPEG quality (1-100).
            max_file_size: Maximum file size in bytes.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Convert to RGB if necessary (handles RGBA, P mode, etc.)
            if img.mode not in ('RGB', 'L'):
                # Handle transparency by compositing on white background
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                    img = background
                else:
                    img = img.convert('RGB')

            # Resize if needed
            original_size = img.size
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                self._logger.debug(f"Resized cover from {original_size} to {img.size}")

            # Save with optimization
            # Try with the specified quality first
            img.save(target_path, 'JPEG', quality=quality, optimize=True)

            # If still too large, reduce quality iteratively
            current_quality = quality
            while target_path.stat().st_size > max_file_size and current_quality > 50:
                current_quality -= 10
                img.save(target_path, 'JPEG', quality=current_quality, optimize=True)
                self._logger.debug(f"Reduced quality to {current_quality} to meet size limit")

            final_size = target_path.stat().st_size
            self._logger.debug(
                f"Saved cover: {img.size[0]}x{img.size[1]}, "
                f"{final_size / 1024:.1f}KB, quality={current_quality}"
            )

            return True
        except Exception as e:
            self._logger.error(f"Failed to process and save image: {e}")
            return False

    def get_collection_stats(self) -> dict:
        """Returns high-level statistics about the music collection.

        This method queries the tracks table to compute aggregate counts of
        distinct artists, distinct artist/album combinations, total tracks, and
        the timestamp of the most recently added track.

        Returns:
            dict: A dictionary containing ``qty_tracks``, ``qty_artists``,
            ``qty_albums``, and ``last_added`` (or None when no tracks exist).
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT COUNT(DISTINCT artist) as qty_artists,
                    COUNT(DISTINCT artist || album) as qty_albums,
                    COUNT(*) AS qty_tracks,
                    SUM(duration) AS total_duration,
                    MAX(mtime) AS time_lastadded
                FROM tracks
                """
            )
            if rows := cur.fetchall():
                return {
                        "num_tracks": rows[0]["qty_tracks"],
                        "num_artists": rows[0]["qty_artists"],
                        "num_albums": rows[0]["qty_albums"],
                        "total_duration": rows[0]["total_duration"],
                        "last_added": rows[0]["time_lastadded"],
                    }
            else:
                return {
                    "num_tracks": 0,
                    "num_artists": 0,
                    "num_albums": 0,
                    "total_duration": 0,
                    "last_added": None,
                }
