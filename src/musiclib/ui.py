import re
from pathlib import Path

from .reader import MusicCollection
from common.logging import Logger


class MusicCollectionUI(MusicCollection):
    """Extends MusicCollection to provide UI-specific search and highlighting features.
    Adds methods for formatting, escaping, and highlighting search results for user interfaces.
    """

    def __init__(self, music_root: Path, db_path: Path, logger: Logger = None) -> None:
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
        Returns a dictionary with title, duration, path, cover, and a safe filename for the track.

        Args:
            track: Dictionary containing track information.

        Returns:
            dict: Dictionary with formatted track details for UI display.
        """
        return {
            "artist": track.get("artist", ""),
            "album": track.get("album", ""),
            "track": track["track"],
            "duration": track.get("duration") or "?:??",
            "path": track["path"],
            "filename": self._safe_filename(track["track"], track["path"]),
            "cover": track.get("cover"),
        }

    @staticmethod
    def _safe_filename(track: str, path: str) -> str:
        """Generates a safe filename for a track by sanitizing the title and preserving the file extension.
        Removes unsafe characters from the title and appends the original file extension.

        Args:
            track: The track title to sanitize.
            path: The original file path to extract the extension.

        Returns:
            str: A safe filename suitable for saving or displaying.
        """
        ext = Path(path).suffix or ""
        safe = "".join(c for c in track if c.isalnum() or c in " _-").strip()
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

    def _should_filter_strict(self, terms: dict) -> tuple[bool, bool]:
        """Determines if strict filtering should be applied based on search terms.

        Args:
            terms: Dictionary of parsed search terms.

        Returns:
            tuple[bool, bool]: (filter_artists, filter_albums) flags.
        """
        has_track_terms = bool(terms.get("track") or terms.get("song"))
        return has_track_terms, has_track_terms

    def _matches_artist_terms(
        self, artist_name: str, artist_terms: list[str], query_lower: str
    ) -> bool:
        """Checks if an artist name matches the specified artist search terms.

        Args:
            artist_name: The artist name to check.
            artist_terms: List of artist-specific search terms.
            query_lower: Lowercase version of the full query.

        Returns:
            bool: True if the artist matches the terms, False otherwise.
        """
        artist_lower = artist_name.lower()
        for term in artist_terms:
            term_lower = term.lower()
            # Prefer exact quoted match
            if (
                f'"{term_lower}"' in query_lower
                and artist_lower == term_lower
                or f'"{term_lower}"' not in query_lower
                and term_lower in artist_lower
            ):
                return True
        return False

    def _matches_album_terms(
        self, album_name: str, album_terms: list[str], query_lower: str
    ) -> bool:
        """Checks if an album name matches the specified album search terms.

        Args:
            album_name: The album name to check.
            album_terms: List of album-specific search terms.
            query_lower: Lowercase version of the full query.

        Returns:
            bool: True if the album matches the terms, False otherwise.
        """
        album_lower = album_name.lower()
        for term in album_terms:
            term_lower = term.lower()
            if (
                f'"{term_lower}"' in query_lower
                and album_lower == term_lower
                or f'"{term_lower}"' not in query_lower
                and term_lower in album_lower
            ):
                return True
        return False

    def _get_artist_match_counts(
        self, artist_name: str, query_lower: str
    ) -> tuple[int, int]:
        """Gets the count of matched albums and tracks for an artist.

        Args:
            artist_name: The artist name to query.
            query_lower: Lowercase version of the search query.

        Returns:
            tuple[int, int]: (matched_albums, matched_tracks) counts.
        """
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

        return matched_albums, matched_tracks

    def _build_artist_reasons(
        self,
        artist_name: str,
        query_lower: str,
        matched_albums: int,
        matched_tracks: int,
    ) -> list[dict]:
        """Builds the list of reasons why an artist was matched.

        Args:
            artist_name: The artist name.
            query_lower: Lowercase version of the search query.
            matched_albums: Number of matched albums.
            matched_tracks: Number of matched tracks.

        Returns:
            list[dict]: List of reason dictionaries with type and text.
        """
        reasons = []
        if query_lower in artist_name.lower():
            reasons.append({"type": "artist", "text": artist_name})
        if matched_albums:
            reasons.append({"type": "album", "text": f"{matched_albums} album(s)"})
        if matched_tracks:
            reasons.append({"type": "track", "text": f"{matched_tracks} track(s)"})
        return reasons

    def _process_artist_result(
        self, artist: dict, terms: dict, all_terms: list[str], query_lower: str
    ) -> dict | None:
        """Processes a single artist result for search highlighting.

        Args:
            artist: Dictionary containing artist information.
            terms: Dictionary of parsed search terms.
            all_terms: Combined list of all search terms.
            query_lower: Lowercase version of the search query.

        Returns:
            dict | None: Processed artist result dictionary, or None if filtered out.
        """
        artist_name = artist["artist"]

        # Filter if artist-specific terms don't match
        if terms.get("artist") and not self._matches_artist_terms(
            artist_name, terms["artist"], query_lower
        ):
            return None

        highlighted_artist = self._highlight_text(artist_name, all_terms)
        matched_albums, matched_tracks = self._get_artist_match_counts(
            artist_name, query_lower
        )
        reasons = self._build_artist_reasons(
            artist_name, query_lower, matched_albums, matched_tracks
        )

        return {
            "type": "artist",
            "raw_artist": artist_name,
            "artist": highlighted_artist,
            "reasons": reasons,
            "num_albums": artist["num_albums"],
            "albums": [],
            "load_on_demand": True,
            "clickable": True,
            "click_query": f"artist:{self._escape_for_query(artist['artist'])}",
        }

    def _get_album_matched_track_count(self, release_dir: str, query_lower: str) -> int:
        """Gets the count of matched tracks for an album.

        Args:
            release_dir: The release directory path.
            query_lower: Lowercase version of the search query.

        Returns:
            int: Number of matched tracks.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT COUNT(*) FROM tracks
                WHERE SUBSTR(path, 1, LENGTH(path) - LENGTH(filename)) = ?
                AND title LIKE ?
                """,
                (f"{release_dir}/", f"%{query_lower}%"),
            )
            return cur.fetchone()[0] or 0

    def _build_album_reasons(
        self,
        display_artist: str,
        album_name: str,
        query_lower: str,
        matched_tracks: int,
        is_compilation: bool,
    ) -> list[dict]:
        """Builds the list of reasons why an album was matched.

        Args:
            display_artist: The artist name to display.
            album_name: The album name.
            query_lower: Lowercase version of the search query.
            matched_tracks: Number of matched tracks.
            is_compilation: Whether this is a compilation album.

        Returns:
            list[dict]: List of reason dictionaries with type and text.
        """
        reasons = []
        if query_lower in display_artist.lower() and not is_compilation:
            reasons.append({"type": "artist", "text": display_artist})
        if query_lower in album_name.lower():
            reasons.append({"type": "album", "text": album_name})
        if matched_tracks:
            reasons.append({"type": "track", "text": f"{matched_tracks} nummer(s)"})
        return reasons

    def _process_album_result(
        self, album: dict, terms: dict, all_terms: list[str], query_lower: str
    ) -> dict | None:
        """Processes a single album result for search highlighting.

        Args:
            album: Dictionary containing album information.
            terms: Dictionary of parsed search terms.
            all_terms: Combined list of all search terms.
            query_lower: Lowercase version of the search query.

        Returns:
            dict | None: Processed album result dictionary, or None if filtered out.
        """
        album_name = album["album"]

        # Filter if album-specific terms don't match
        if terms.get("album") and not self._matches_album_terms(
            album_name, terms["album"], query_lower
        ):
            return None

        display_artist = album["display_artist"]
        is_compilation = album["is_compilation"]
        release_dir = album["release_dir"]

        highlighted_artist = (
            "Various Artists"
            if is_compilation
            else self._highlight_text(display_artist, all_terms)
        )
        highlighted_album = self._highlight_text(album_name, all_terms)

        matched_tracks = self._get_album_matched_track_count(release_dir, query_lower)
        reasons = self._build_album_reasons(
            display_artist, album_name, query_lower, matched_tracks, is_compilation
        )

        return {
            "type": "album",
            "raw_artist": display_artist,
            "artist": highlighted_artist,
            "raw_album": album_name,
            "album": highlighted_album,
            "reasons": reasons,
            "num_tracks": album["num_tracks"],
            "tracks": [],
            "highlighted_tracks": None,
            "load_on_demand": True,
            "is_compilation": is_compilation,
            "clickable": True,
            "click_query": f"release_dir:{self._escape_for_query(release_dir)}",
            "artist_click_query": None
            if is_compilation
            else f"artist:{self._escape_for_query(display_artist)}",
            "release_dir": release_dir,
            "cover": self.get_cover(release_dir),
        }

    def _process_track_result(self, track: dict, all_terms: list[str]) -> dict:
        """Processes a single track result for search highlighting.

        Args:
            track: Dictionary containing track information.
            all_terms: Combined list of all search terms.

        Returns:
            dict: Processed track result dictionary.
        """
        track_name = track["track"]
        highlighted_tracks = self._highlight_text(track_name, all_terms)
        highlighted_artist = self._highlight_text(track["artist"], all_terms)
        highlighted_album = self._highlight_text(track["album"], all_terms)
        release_dir = self._get_release_dir(track["path"])
        track["cover"] = self.get_cover(release_dir)

        return {
            "type": "track",
            "raw_artist": track["artist"],
            "artist": highlighted_artist,
            "raw_album": track["album"],
            "album": highlighted_album,
            "reasons": [{"type": "track", "text": track_name}],
            "tracks": [self._track_display_dict(track)],
            "highlighted_tracks": [
                {
                    "original": {
                        "track": track_name,
                        "duration": self._format_duration(track.get("duration")),
                    },
                    "highlighted": highlighted_tracks,
                    "match_type": "track",
                }
            ],
            "artist_click_query": f"artist:{self._escape_for_query(track['artist'])}",
            "album_click_query": f"album:{self._escape_for_query(track['album'])}",
        }

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

        # Combine all search terms for highlighting
        all_terms = (
            terms.get("artist", [])
            + terms.get("album", [])
            + terms.get("track", [])
            + terms.get("general", [])
        )
        query_lower = query.lower()

        # Apply strict filtering for tagged searches
        filter_artists, filter_albums = self._should_filter_strict(terms)
        if filter_artists:
            grouped["artists"] = []
        if filter_albums:
            grouped["albums"] = []

        results = []

        # Process artists
        for artist in grouped["artists"]:
            if artist_result := self._process_artist_result(
                artist, terms, all_terms, query_lower
            ):
                results.append(artist_result)

        # Process albums
        for album in grouped["albums"]:
            if album_result := self._process_album_result(
                album, terms, all_terms, query_lower
            ):
                results.append(album_result)

        # Process tracks
        for track in grouped["tracks"]:
            track_result = self._process_track_result(track, all_terms)
            results.append(track_result)

        return results
