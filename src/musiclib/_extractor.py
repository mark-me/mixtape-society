import sqlite3
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Literal, Optional

from tinytag import TinyTag
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from logtools import get_logger
from .indexing_status import set_indexing_status, clear_indexing_status

logger = get_logger(__name__)

# =========================
# Event model
# =========================

EventType = Literal[
    "INDEX_FILE",
    "DELETE_FILE",
    "CLEAR_DB",
    "REBUILD_DONE",
    "RESYNC_DONE",
]


@dataclass(slots=True)
class IndexEvent:
    type: EventType
    path: Optional[Path] = None


# =========================
# CollectionExtractor
# =========================


class CollectionExtractor:
    SUPPORTED_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}

    def __init__(self, music_root: Path, db_path: Path):
        self.music_root = music_root.resolve()
        self.db_path = db_path
        self.data_root = db_path.parent

        self.data_root.mkdir(parents=True, exist_ok=True)

        self._write_queue: Queue[IndexEvent] = Queue()
        self._writer_stop = Event()
        self._observer: Optional[Observer] = None

        self._init_db()

        self._writer_thread = Thread(
            target=self._db_writer_loop,
            name="sqlite-writer",
            daemon=True,
        )
        self._writer_thread.start()

    # =========================
    # DB setup
    # =========================

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    artist TEXT,
                    album TEXT,
                    title TEXT,
                    albumartist TEXT,
                    genre TEXT,
                    year INTEGER,
                    duration REAL,
                    mtime REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist COLLATE NOCASE)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_album  ON tracks(album  COLLATE NOCASE)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_title  ON tracks(title  COLLATE NOCASE)")

    def get_conn(self, readonly: bool = False) -> sqlite3.Connection:
        if readonly:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)

        conn.row_factory = sqlite3.Row
        return conn

    # =========================
    # Writer loop (ONLY writer)
    # =========================

    def _db_writer_loop(self):
        conn = self.get_conn()
        conn.execute("PRAGMA busy_timeout = 60000")
        pending = 0

        try:
            while not self._writer_stop.is_set():
                try:
                    event = self._write_queue.get(timeout=0.5)
                except Empty:
                    continue

                try:
                    if event.type == "CLEAR_DB":
                        conn.execute("DELETE FROM tracks")

                    elif event.type == "INDEX_FILE" and event.path:
                        self._index_file(conn, event.path)

                    elif event.type == "DELETE_FILE" and event.path:
                        conn.execute("DELETE FROM tracks WHERE path = ?", (str(event.path),))

                    elif event.type in ("REBUILD_DONE", "RESYNC_DONE"):
                        conn.commit()

                    pending += 1
                    if pending >= 500:
                        conn.commit()
                        pending = 0

                except Exception as e:
                    logger.error(f"Writer error: {e}", exc_info=True)

                finally:
                    self._write_queue.task_done()

        finally:
            conn.commit()
            conn.close()

    # =========================
    # Metadata extraction
    # =========================

    def _index_file(self, conn: sqlite3.Connection, path: Path):
        try:
            tag = TinyTag.get(path, tags=True, duration=True)
        except Exception:
            tag = None

        artist = getattr(tag, "artist", None) or getattr(tag, "albumartist", None)
        album = getattr(tag, "album", None)
        title = getattr(tag, "title", None) or path.stem

        year = None
        try:
            if getattr(tag, "year", None):
                year = int(str(tag.year)[:4])
        except Exception:
            pass

        conn.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, filename, artist, album, title, albumartist, genre, year, duration, mtime)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(path),
                path.name,
                artist or "Unknown",
                album or "Unknown",
                title or "Unknown",
                getattr(tag, "albumartist", None),
                getattr(tag, "genre", None),
                year,
                getattr(tag, "duration", None),
                path.stat().st_mtime,
            ),
        )

    # =========================
    # Rebuild
    # =========================

    def rebuild(self):
        logger.info("Starting full rebuild")

        files = [
            p for p in self.music_root.rglob("*")
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
        ]

        total = len(files)
        set_indexing_status(self.data_root, "rebuilding", total=total, current=0)

        self._write_queue.put(IndexEvent("CLEAR_DB"))

        for i, path in enumerate(files, start=1):
            self._write_queue.put(IndexEvent("INDEX_FILE", path))

            if i % 100 == 0:
                set_indexing_status(self.data_root, "rebuilding", total, i)

        self._write_queue.put(IndexEvent("REBUILD_DONE"))
        self._write_queue.join()
        clear_indexing_status(self.data_root)
        logger.info("Rebuild queued")

    # =========================
    # Resync (NEW)
    # =========================

    def resync(self):
        logger.info("Starting resync")

        fs_paths = {
            str(p)
            for p in self.music_root.rglob("*")
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
        }

        with self.get_conn() as conn:
            db_paths = {r["path"] for r in conn.execute("SELECT path FROM tracks")}

        to_add = fs_paths - db_paths
        to_remove = db_paths - fs_paths

        total = len(to_add) + len(to_remove)
        set_indexing_status(self.data_root, "resyncing", total=total, current=0)

        progress = 0

        for path in to_remove:
            self._write_queue.put(IndexEvent("DELETE_FILE", Path(path)))
            progress += 1
            if progress % 100 == 0:
                set_indexing_status(self.data_root, "resyncing", total, progress)

        for path in to_add:
            self._write_queue.put(IndexEvent("INDEX_FILE", Path(path)))
            progress += 1
            if progress % 100 == 0:
                set_indexing_status(self.data_root, "resyncing", total, progress)

        self._write_queue.put(IndexEvent("RESYNC_DONE"))
        clear_indexing_status(self.data_root)
        logger.info(f"Resync queued (+{len(to_add)} / -{len(to_remove)})")

    # =========================
    # Monitoring
    # =========================

    def start_monitoring(self):
        if self._observer:
            return
        self._observer = Observer()
        self._observer.schedule(_Watcher(self), str(self.music_root), recursive=True)
        self._observer.start()

    def stop(self):
        self._writer_stop.set()
        self._writer_thread.join(timeout=5)
        if self._observer:
            self._observer.stop()
            self._observer.join()


# =========================
# Watchdog handler
# =========================


class _Watcher(FileSystemEventHandler):
    def __init__(self, extractor: CollectionExtractor):
        self.extractor = extractor

    def on_any_event(self, event):
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in self.extractor.SUPPORTED_EXTS:
            return

        if event.event_type in ("created", "modified"):
            self.extractor._write_queue.put(IndexEvent("INDEX_FILE", path))
        elif event.event_type == "deleted":
            self.extractor._write_queue.put(IndexEvent("DELETE_FILE", path))
