# Updated reader.py with lazy loading for both artists and albums
# No automatic population of albums for artists or tracks for albums
import re
from pathlib import Path
from threading import Thread
from typing import Any, Sequence
from sqlite3 import Connection

from common.logging import NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import get_indexing_status, clear_indexing_status

_STARTUP_DONE = False


class MusicCollection:
    def __init__(
        self, music_root: Path | str, db_path: Path | str, logger=None
    ) -> None:
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

    def is_indexing(self) -> bool:
        status = get_indexing_status(self.db_path.parent)
        return status and status.get("status") in ("rebuilding", "resyncing")

    def _start_background_startup_job(self) -> None:
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

    def _use_fts(self, conn: Connection) -> bool:
        return (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'"
            ).fetchone()
            is not None
        )

    def _fts_escape(self, txt: str) -> str:
        return txt.replace("\\", "\\\\").replace('"', '\\"')

    def _execute_search(
        self,
        conn: Connection,
        field: str,
        terms: Sequence[str],
        limit: int,
        extra_where: str = "",
        extra_params: list[Any] | None = None,
        select_fields: str = "artist, album, title AS track, path, filename, duration",
        contains_match: bool = False,  # True = substring/contains, False = prefix/exact
    ) -> list[dict]:
        if not terms:
            return []

        params: list[Any] = []
        use_fts = self._use_fts(conn)

        if use_fts:
            expr_parts = []
            for t in terms:
                escaped = self._fts_escape(t)
                if contains_match:
                    # For contains: use wildcard * at end (substring match)
                    expr_parts.append(f'{field}:{escaped}*')
                else:
                    # For prefix/exact: use prefix ^ if it was a starts-with, otherwise exact
                    if t.endswith("%"):
                        expr_parts.append(f'{field}:"^{escaped.rstrip("%")}"')
                    else:
                        expr_parts.append(f'{field}:{escaped}')
            expr = " OR ".join(expr_parts)
            sql = f"SELECT DISTINCT {select_fields} FROM tracks_fts WHERE tracks_fts MATCH ?"
            params.append(expr)
        else:
            # Fallback LIKE always uses contains (%term%)
            like_terms = [f"%{t}%" for t in terms]
            where_clause = " OR ".join(f"{field} LIKE ? COLLATE NOCASE" for _ in terms)
            sql = f"SELECT DISTINCT {select_fields} FROM tracks WHERE {where_clause}"
            params.extend(like_terms)

        if extra_where:
            sql += f" {extra_where}"
            params.extend(extra_params or [])

        order_by = 'rank' if use_fts else f'{field} COLLATE NOCASE'
        sql += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)

        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur]

        # Post-process
        for r in rows:
            if "path" in r:
                r["path"] = self._relative_path(r["path"])
            if "duration" in r:
                r["duration"] = self._format_duration(r["duration"])
        return rows

    def _search_artists_multi(
        self,
        conn: Connection,
        terms: list[str],
        limit: int,
        contains_match: bool = False,  # <-- add this
    ) -> list[dict]:
        rows = self._execute_search(
            conn,
            "artist",
            terms,
            limit,
            select_fields="artist",
            contains_match=contains_match,
        )
        return [{"artist": r["artist"]} for r in rows]


    def _search_albums_multi(
        self,
        conn: Connection,
        terms: list[str],
        limit: int,
        skip_artists: set[str] | None = None,
        contains_match: bool = False,  # <-- add this
    ) -> list[dict]:
        extra_where = ""
        extra_params: list[Any] = []
        if skip_artists:
            placeholders = ",".join("?" for _ in skip_artists)
            extra_where = f" AND lower(artist) NOT IN ({placeholders})"
            extra_params = list(skip_artists)

        rows = self._execute_search(
            conn,
            "album",
            terms,
            limit,
            extra_where=extra_where,
            extra_params=extra_params,
            select_fields="artist, album",
            contains_match=contains_match,  # <-- pass it
        )
        return rows


    def _search_tracks_multi(
        self,
        conn: Connection,
        terms: list[str],
        limit: int,
        skip_artists: set[str] | None = None,
        contains_match: bool = False,  # <-- add this
    ) -> list[dict]:
        extra_where = ""
        extra_params: list[Any] = []
        if skip_artists:
            placeholders = ",".join("?" for _ in skip_artists)
            extra_where = f" AND lower(artist) NOT IN ({placeholders})"
            extra_params = list(skip_artists)

        return self._execute_search(
            conn,
            "title",
            terms,
            limit,
            extra_where=extra_where,
            extra_params=extra_params,
            contains_match=contains_match,  # <-- pass it
        )

    def _search_album_tracks(
        self, conn: Connection, artist: str, album: str
    ) -> list[dict]:
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
        if not seconds:
            return "?:??"
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

    def _relative_path(self, path: str) -> str:
        return str(Path(path).relative_to(self.music_root))

    def parse_query(self, query: str) -> dict[str, list[str]]:
        tags = {"artist": [], "album": [], "track": []}
        general: list[str] = []
        pattern = r'(artist|album|song)\s*:\s*("((?:[^"\\]|\\.)*)"|(\S+))'
        matches = re.finditer(pattern, query, re.IGNORECASE)
        last = 0
        for m in matches:
            tag = m.group(1).lower()
            quoted_value = m.group(2)  # inside quotes (already unescaped below)
            unquoted_value = m.group(3)
            if quoted_value is not None:
                value = re.sub(r"\\(.)", r"\1", quoted_value)
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

    def search_grouped(self, query: str, limit: int = 20) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
        if not query.strip():
            return {"artists": [], "albums": [], "tracks": []}, {}

        parsed = self.parse_query(query)
        has_specific = any(parsed[k] for k in ("artist", "album", "track"))
        conn = self._get_conn()

        if not has_specific and parsed["general"]:
            phrase = " ".join(parsed["general"])
            like = f"%{phrase}%"
            starts = f"{phrase}%"
            term = starts if self._use_fts(conn) else like
            artists = self._search_artists_multi(conn, [term], limit, contains_match=False)
            albums = self._search_albums_multi(conn, [term], limit,
                                            skip_artists={a["artist"].lower() for a in artists},
                                            contains_match=False)
            tracks = self._search_tracks_multi(conn, [term], limit,
                                            skip_artists={a["artist"].lower() for a in artists + albums},
                                            contains_match=False)
            terms = {"artist": [phrase], "album": [phrase], "track": [phrase]}
        else:
            general = parsed["general"]
            artist_terms = parsed["artist"] + general
            album_terms = parsed["album"] + general
            track_terms = parsed["track"] + general

            artists = self._search_artists_multi(conn, artist_terms, limit, contains_match=True) if artist_terms else []
            albums = self._search_albums_multi(conn, album_terms, limit,
                                            skip_artists={a["artist"].lower() for a in artists},
                                            contains_match=True) if album_terms else []
            tracks = self._search_tracks_multi(conn, track_terms, limit,
                                            skip_artists={a["artist"].lower() for a in artists + albums},
                                            contains_match=True) if track_terms else []

            terms = {
                "artist": artist_terms,
                "album": album_terms,
                "track": track_terms,
            }

        # No population of sub-items – all lazy now (fast initial search)
        return {"artists": artists, "albums": albums, "tracks": tracks}, terms

    def get_artist_details(self, artist: str) -> dict:
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
            albums_map = {}
            for row in cur:
                album = row["album"]
                if album not in albums_map:
                    albums_map[album] = []
                albums_map[album].append(
                    {
                        "track": row["title"],
                        "path": self._relative_path(row["path"]),
                        "filename": row["filename"],
                        "duration": self._format_duration(row["duration"]),
                    }
                )

            albums = [
                {"album": album, "tracks": tracks}
                for album, tracks in sorted(albums_map.items())
            ]

            return {"artist": artist, "albums": albums}

    def get_album_details(self, album: str) -> dict:
        """
        Fetch full track list for an album (identified by name).
        Includes per-track artist for multi-artist albums.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT artist, title, path, filename, duration
                FROM tracks
                WHERE album = ?
                ORDER BY discnumber, tracknumber, title COLLATE NOCASE
                """,
                (album,),
            )
            tracks = [
                {
                    "artist": row["artist"],  # per-track artist
                    "track": row["title"],
                    "path": self._relative_path(row["path"]),
                    "filename": row["filename"],
                    "duration": self._format_duration(row["duration"]),
                }
                for row in cur
            ]

            # Determine display artist
            artists_in_album = {t["artist"] for t in tracks}
            display_artist = (
                "Various Artists"
                if len(artists_in_album) > 3
                else next(iter(artists_in_album))
            )

            return {
                "artist": display_artist,
                "album": album,
                "tracks": tracks,
                "is_compilation": len(artists_in_album) > 3,
            }
