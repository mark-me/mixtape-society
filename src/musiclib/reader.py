import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from threading import Thread
from time import time

from tinytag import TinyTag

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

        self._last_search_session: SearchSession | None = None

        self.covers_dir = self.db_path.parent / "collection_covers"
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def is_indexing(self) -> bool:
        status = get_indexing_status(self.db_path.parent)

        # If status file exists and indicates active job → yes
        if status and status.get("status") in ("rebuilding", "resyncing"):
            return True

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
            dict: The track dictionary.
        """
        return {
            "artist": artist or row["artist"],
            "track": row["title"],
            "path": self._relative_path(row["path"]),
            "filename": row["filename"],
            "duration": self._format_duration(row["duration"]),
            "album": album or row["album"],
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
            list[str]: Cleaned list of terms.
        """
        cleaned = []
        for term in term_list:
            term = term.strip()
            if not term:
                continue
            # Remove standalone wildcard '*' or terms that are just '*'
            if term == "*":
                continue
            # Optionally: normalize wildcard usage:
            # - Drop standalone '*' terms entirely (handled above)
            # - Strip all leading '*' while keeping any trailing '*' (prefix search like "beat*")
            # - Collapse multiple internal '*' into a single '*' to avoid surprising patterns
            if term.startswith("*") and len(term) > 1:
                # strip all leading '*', keep "les*" → "les*", "**beat*" → "beat*"
                term = term.lstrip("*")
            # collapse multiple '*' in the middle to a single '*', e.g. "be**at*" → "be*at*"
            while "**" in term:
                term = term.replace("**", "*")
            if (
                term.endswith("*") or term.isalpha() or " " in term
            ):  # phrases or normal words
                cleaned.append(term)
            elif term:  # fallback: include if not empty
                cleaned.append(term)
        return cleaned

    def search_grouped(self, query: str, limit: int = 20) -> tuple[dict, dict]:
        """Searches the music collection and returns grouped artist, album, and track results.
        Parses the query, reuses cached sessions when possible, and builds hierarchical search results.

        Args:
            query: The raw search query string entered by the user.
            limit: The maximum number of results to return in each group.

        Returns:
            tuple[dict, dict]: A tuple containing grouped search results and the parsed query terms.
        """
        terms = self._prepare_terms(query)
        if not any(terms.values()):
            return {"artists": [], "albums": [], "tracks": []}, terms

        has_artist = bool(terms["artist"])
        has_album = bool(terms["album"])
        has_track = bool(terms["track"])
        is_free_text = not (has_artist or has_album or has_track)

        reuse_session = (
            self._last_search_session
            if self._can_reuse_session(self._last_search_session, query.strip(), terms)
            else None
        )

        (
            artist_candidates,
            album_candidates,
            track_candidates,
        ) = self._get_pass_one_candidates(
            terms=terms,
            limit=limit,
            has_artist=has_artist,
            has_album=has_album,
            is_free_text=is_free_text,
            reuse_session=reuse_session,
        )

        self._last_search_session = SearchSession(
            query=query.strip(),
            terms=terms,
            artist_candidates=artist_candidates,
            album_candidates=album_candidates,
            track_candidates=track_candidates,
            timestamp=time(),
        )

        return self._build_hierarchical_results(
            artist_candidates, album_candidates, track_candidates, limit
        ), terms

    def _prepare_terms(self, query: str) -> dict[str, list[str]]:
        """Normalizes and parses the raw query string into structured search terms.
        Handles empty or whitespace-only queries by returning an initialized terms dictionary.

        Args:
            query: The raw search query string entered by the user.

        Returns:
            dict[str, list[str]]: Parsed terms grouped into artist, album, track, and general categories.
        """
        if query := query.strip():
            return self._parse_query(query)
        else:
            return {
                "artist": [],
                "album": [],
                "track": [],
                "general": [],
            }

    def _get_pass_one_candidates(
        self,
        terms: dict,
        limit: int,
        has_artist: bool,
        has_album: bool,
        is_free_text: bool,
        reuse_session: SearchSession | None,
    ) -> tuple[dict[str, int], dict[str, dict], list[dict]]:
        """Collects first-pass search candidates using either a previous session or a fresh database query.
        Chooses between reusing cached candidates and querying the database, returning scored artists, albums, and tracks.

        Args:
            terms: Parsed search terms grouped by category.
            limit: Base limit used to bound the number of rows fetched from the database.
            has_artist: Whether the query includes explicit artist terms.
            has_album: Whether the query includes explicit album terms.
            is_free_text: Whether the query is purely free-text without explicit tags.
            reuse_session: Optional previous search session to reuse candidates from.

        Returns:
            tuple[dict[str, int], dict[str, dict], list[dict]]: Mappings of artist and album candidates,
                and a list of track candidates, each with associated relevance scores.
        """
        artist_candidates: dict[str, int] = {}
        album_candidates: dict[str, dict] = {}
        track_candidates: list[dict] = []

        if reuse_session:
            artist_candidates, album_candidates, track_candidates = (
                self._reuse_pass_one_candidates(
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

        return artist_candidates, album_candidates, track_candidates

    def _reuse_pass_one_candidates(
        self,
        reuse_session: SearchSession,
        terms: dict,
        has_artist: bool,
        has_album: bool,
        is_free_text: bool,
    ) -> tuple[dict[str, int], dict[str, dict], list[dict]]:
        """Recomputes candidate scores from a previous search session for a refined query.
        Reuses cached artists, albums, and tracks while applying the new term filters and scoring rules.

        Args:
            reuse_session: The previous search session whose candidates should be reused.
            terms: Parsed search terms for the current query.
            has_artist: Whether the query includes explicit artist terms.
            has_album: Whether the query includes explicit album terms.
            is_free_text: Whether the query is purely free-text without explicit tags.

        Returns:
            tuple[dict[str, int], dict[str, dict], list[dict]]: Updated artist and album candidate mappings,
                and a list of track candidates with recalculated relevance scores.
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
            if use_fts := self._use_fts(conn):
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

            albums.append(
                {
                    "artist": album["artist"],
                    "display_artist": album["artist"],
                    "album": album["album"],
                    "release_dir": album["release_dir"],
                    "is_compilation": False,
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
                albums.append(
                    {
                        "album": album_name,
                        "cover": album_cover,
                        "tracks": tracks,
                        "release_dir": release_dir,
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
            album_cover = self.get_cover(release_dir)

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

    def get_cover(self, release_dir: str) -> str | None:
        """Retrieves or generates the cover image path for a given album release directory.
        Returns a relative path to a cached or newly extracted cover image if available.

        Args:
            release_dir: The release directory identifier used to locate or derive the cover image.

        Returns:
            str | None: Relative path to the cover image within the covers directory, or None if not found.
        """
        if not release_dir:
            return None

        # Sanitize to a safe filename slug
        slug = self._sanitize_release_dir(release_dir)
        cover_path = self.covers_dir / f"{slug}.jpg"

        if cover_path.exists():
            return f"covers/{slug}.jpg"

        # Extract on demand
        if self._extract_cover(release_dir, cover_path):
            return f"covers/{slug}.jpg"

        return None

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
        Searches for existing image files or embedded artwork and writes a normalized copy to the target path.

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
                    with open(img_path, "rb") as src, open(target_path, "wb") as dst:
                        dst.write(src.read())
                    self._logger.info(f"Copied cover from {img_path} for {release_dir}")
                    return True
                except OSError as e:
                    self._logger.error(f"Failed to copy cover {img_path}: {e}")
                    continue

        # Step 2: Extract embedded art from audio files
        for file in abs_dir.iterdir():
            if file.suffix.lower() in CollectionExtractor.SUPPORTED_EXTS:
                try:
                    tag = TinyTag.get(str(file), image=True)
                    if img_data := tag.get_image():
                        with open(target_path, "wb") as f:
                            f.write(img_data)
                        self._logger.info(
                            f"Extracted embedded cover from {file} for {release_dir}"
                        )
                        return True
                except Exception as e:
                    self._logger.warning(f"Failed to extract from {file}: {e}")
                    continue

        self._logger.info(f"No cover found for {release_dir}")
        return False
