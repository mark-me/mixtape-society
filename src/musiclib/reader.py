# Updated reader.py with lazy loading for both artists and albums
# No automatic population of albums for artists or tracks for albums
import re
from collections import defaultdict
from pathlib import Path
from sqlite3 import Connection
from threading import Thread

from common.logging import NullLogger

from ._extractor import CollectionExtractor
from .indexing_status import clear_indexing_status, get_indexing_status

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
        return txt.replace('"', '""')

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

        # Fixed regex: unquoted values stop before the next tag
        pattern = r'(artist|album|song)\s*:\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|(\S+(?:\s+(?!\s*(artist|album|song)\s*:\s*)\S+)*))'

        matches = re.finditer(pattern, query, re.IGNORECASE)
        last_end = 0

        for match in matches:
            # Text between previous match and this one → general terms
            between = query[last_end:match.start()].strip()
            if between:
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

        # Remaining text after last match
        remaining = query[last_end:].strip()
        if remaining:
            general.extend(remaining.split())

        return {**tags, "general": general}

    def search_grouped(self, query: str, limit: int = 20) -> tuple[dict[str, list[dict]], dict[str, list[str]]]:
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
                        "path": self._relative_path(row["path"]),
                        "filename": row["filename"],
                        "duration": self._format_duration(row["duration"]),
                    }
                )

            albums = []
            for release_dir, tracks in sorted(releases_map.items(), key=lambda x: x[0]["album"]):
                album_name = tracks[0]["album"]  # Assume consistent
                albums.append({"album": album_name, "tracks": tracks, "release_dir": release_dir})

            return {"artist": artist, "albums": albums}

    def get_album_details(self, release_dir: str) -> dict:
        """
        Fetch full track list for a release identified by its directory.
        Includes per-track artist for multi-artist releases.
        """
        with self._get_conn() as conn:
            # Use SQL expr to match directory (handles trailing / consistency)
            cur = conn.execute(
                f"""
                SELECT artist, title, path, filename, duration, album
                FROM tracks
                WHERE {self._sql_release_dir_expr()} = ?
                ORDER BY discnumber, tracknumber, title COLLATE NOCASE
                """,
                (f"{release_dir}/",),  # Add trailing / to match SQL expr
            )
            tracks = cur.fetchall()

            if not tracks:
                return {"artist": "", "album": "", "tracks": [], "is_compilation": False}

            # Assume album name is consistent per directory (take first)
            album_name = tracks[0]["album"] if tracks else ""

            # Per-track details
            track_list = [
                {
                    "artist": row["artist"],
                    "track": row["title"],
                    "path": self._relative_path(row["path"]),
                    "filename": row["filename"],
                    "duration": self._format_duration(row["duration"]),
                }
                for row in tracks
            ]

            # Determine display artist and compilation
            artists_in_release = {t["artist"] for t in track_list}
            is_compilation = len(artists_in_release) > 3
            display_artist = "Various Artists" if is_compilation else next(iter(artists_in_release))

            return {
                "artist": display_artist,
                "album": album_name,
                "tracks": track_list,
                "is_compilation": is_compilation,
                "release_dir": release_dir,  # Include for reference
            }

    def _get_release_dir(self, path: str) -> str:
        """Compute the release directory from a track path (relative to music_root)."""
        full_path = Path(path)
        relative_path = full_path.relative_to(self.music_root) if full_path.is_absolute() else full_path
        return str(relative_path.parent)  # e.g., 'artist/album'

    def _sql_release_dir_expr(self) -> str:
        """SQL expression to compute release_dir in queries."""
        return "SUBSTR(path, 1, LENGTH(path) - LENGTH(filename))"  # e.g., 'artist/album/' (with trailing /)