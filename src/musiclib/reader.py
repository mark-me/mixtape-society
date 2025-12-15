import re
from pathlib import Path
from threading import Thread
from typing import Any

from logtools import get_logger

from ._extractor import CollectionExtractor
from .indexing_status import clear_indexing_status

logger = get_logger(__name__)

_STARTUP_DONE = False

class MusicCollection:
    """
    High-level facade around CollectionExtractor (pipeline-based).

    Guarantees:
    - Exactly one SQLite writer (inside CollectionExtractor)
    - Rebuild, resync, and live FS events are serialized
    - No SQLite access from UI / background threads
    """

    def __init__(self, music_root: Path | str, db_path: Path | str):
        self.music_root = Path(music_root).resolve()
        self.db_path = Path(db_path)

        self._extractor = CollectionExtractor(
            music_root=self.music_root,
            db_path=self.db_path,
        )

        # Decide startup action
        track_count = self.count()

        if track_count == 0:
            logger.info("No tracks in DB — scheduling initial rebuild")
            self._startup_mode = "rebuild"
        else:
            self._startup_mode = "resync"

        self._background_task_running = False

        # Start monitoring immediately
        self._extractor.start_monitoring()

        # Kick background startup job
        self._start_background_startup_job()

    # =========================
    # Startup logic
    # =========================

    def _start_background_startup_job(self):
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
                logger.info("Startup indexing scheduled")
            except Exception as e:
                logger.error(f"Startup indexing failed: {e}", exc_info=True)
            finally:
                clear_indexing_status(self.music_root)
                self._background_task_running = False

        Thread(target=task, daemon=True).start()


    # =========================
    # Public maintenance API
    # =========================

    def rebuild(self) -> None:
        """Force full rebuild."""
        self._extractor.rebuild()

    def resync(self) -> None:
        """Force resync."""
        self._extractor.resync()

    def close(self) -> None:
        """Shutdown monitoring and writer thread."""
        self._extractor.stop()

    # =========================
    # Read-only DB helpers
    # =========================

    def _get_conn(self):
        # READ-ONLY access is allowed
        return self._extractor.get_conn(readonly=True)

    def count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    # =========================
    # Search API (unchanged semantics)
    # =========================

    def search_grouped(self, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
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

    def _search_artists(self, conn, starts: str, limit: int):
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

    def _search_artist_albums(self, conn, artist: str):
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

    def _search_album_tracks(self, conn, artist: str, album: str):
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

    def _search_albums(self, conn, like, starts, limit, artists):
        skip = {a["artist"].lower() for a in artists}
        params = [like, starts]

        sql = """
            SELECT DISTINCT artist, album FROM tracks
            WHERE album LIKE ? COLLATE NOCASE
        """
        if skip:
            sql += f' AND lower(artist) NOT IN ({",".join("?" * len(skip))})'
            params.extend(skip)

        sql += " ORDER BY album LIKE ? DESC, album COLLATE NOCASE LIMIT ?"
        params.extend([limit])

        cur = conn.execute(sql, params)
        albums = [{"artist": r["artist"], "album": r["album"]} for r in cur]

        for a in albums:
            a["tracks"] = self._search_album_tracks(conn, a["artist"], a["album"])

        return albums

    def _search_tracks(self, conn, like, starts, limit, artists, albums):
        skip = {a["artist"].lower() for a in artists}
        skip.update(a["artist"].lower() for a in albums)

        params = [like, starts]
        sql = """
            SELECT artist, album, title, path, filename, duration
            FROM tracks
            WHERE title LIKE ? COLLATE NOCASE
        """

        if skip:
            sql += f' AND lower(artist) NOT IN ({",".join("?" * len(skip))})'
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

    # =========================
    # Helpers
    # =========================

    def _relative_path(self, path: str) -> str:
        return str(Path(path).relative_to(self.music_root))

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if not seconds:
            return "?:??"
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"
