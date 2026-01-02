import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event as ThreadEvent, Thread, Lock
from typing import Iterable, Literal, Optional

from tinytag import TinyTag
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from common.logging import Logger, NullLogger

from .indexing_status import clear_indexing_status, set_indexing_status

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
"""
Represents the type of event for music collection indexing and synchronization.

EventType is a type alias for string literals that specify the kind of operation to perform,
such as indexing a file, deleting a file, clearing the database, or marking the completion of a rebuild or resync.
"""


@dataclass(slots=True)
class IndexEvent:
    """Represents an event for indexing or modifying music files in the collection.

    Used to communicate file indexing, deletion, and database operations between threads in the music collection extractor.

    Args:
        type (EventType): The type of event (e.g., INDEX_FILE, DELETE_FILE).
        path (Optional[Path]): The path to the affected music file, if applicable.
    """

    type: EventType
    path: Optional[Path] = None


class CollectionExtractor:
    """Manages extraction, indexing, and synchronization of music files in a collection.

    Handles database setup, metadata extraction, file system monitoring, and synchronization to keep the music database up to date with the file system.

    Args:
        music_root (Path): The root directory containing music files.
        db_path (Path): The path to the SQLite database file.
    """

    SUPPORTED_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}

    def __init__(
        self, music_root: Path, db_path: Path, logger: Logger | None = None
    ) -> None:
        """Initializes the CollectionExtractor with the given music root, database path, and optional logger.
        Sets up the database, file system monitoring, and background writer thread for music collection management.

        Args:
            music_root: The root directory containing music files.
            db_path: The path to the SQLite database file.
            logger: Optional logger instance for logging events.

        Returns:
            None
        """
        self.music_root = music_root.resolve()
        self.db_path = db_path
        self.data_root = db_path.parent

        self._logger = logger or NullLogger()

        self.data_root.mkdir(parents=True, exist_ok=True)

        self._initial_status_event = ThreadEvent()
        self._processed_count = 0
        self._total_for_current_job = None
        self._current_job_status = None

        self._write_queue: Queue[IndexEvent] = Queue()
        self._writer_stop = ThreadEvent()
        self._observer: Optional[Observer] = None

        self._db_lock = Lock()

        self._init_db()

        self._writer_thread = Thread(
            target=self._db_writer_loop,
            name="sqlite-writer",
            daemon=True,
        )
        self._writer_thread.start()

    # === DB setup ===
    def _init_db(self):
        """Initializes the SQLite database schema for music tracks and full-text search.

        Creates tables, indexes, and triggers required for efficient music metadata storage and search functionality.

        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")  # 10 second timeout

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    artist TEXT,
                    album TEXT,
                    title TEXT,
                    albumartist TEXT,
                    track_number INTEGER,
                    disc_number INTEGER,
                    genre TEXT,
                    year INTEGER,
                    duration REAL,
                    mtime REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_album  ON tracks(album  COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_title  ON tracks(title  COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_album_track ON tracks(album COLLATE NOCASE, disc_number, track_number);"
            )
            # FTS5 virtual table (new)
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    artist,
                    album,
                    title,
                    albumartist,
                    genre,
                    path,
                    filename,
                    duration,
                    disc_number,
                    track_number,
                    content='tracks',
                    content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 1'   -- sensible tokenizer
                );
                """
            )

            # Triggers to mirror changes to fts table
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks
                BEGIN
                    INSERT INTO tracks_fts(rowid, artist, album, title, albumartist, genre, path, filename, duration, disc_number, track_number)
                    VALUES (new.rowid, new.artist, new.album, new.title,
                            new.albumartist, new.genre, new.path, new.filename, new.duration, new.disc_number, new.track_number);
                END;

                CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks
                BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, artist, album, title, albumartist, genre, path, filename, duration,  disc_number, track_number)
                    VALUES('delete', old.rowid, old.artist, old.album, old.title,
                            old.albumartist, old.genre, old.path, old.filename, old.duration, old.disc_number, old.track_number);
                END;

                CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks
                BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, artist, album, title, albumartist, genre, disc_number, track_number)
                    VALUES('delete', old.rowid, old.artist, old.album, old.title,
                            old.albumartist, old.genre, old.path, old.filename, old.duration, old.disc_number, old.track_number);
                    INSERT INTO tracks_fts(rowid, artist, album, title, albumartist, genre, path, filename, duration, disc_number, track_number)
                    VALUES (new.rowid, new.artist, new.album, new.title,
                            new.albumartist, new.genre, new.path, new.filename, new.duration, new.disc_number, new.track_number);
                END;
                """
            )

            # Add metadata table for loading progress
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            # Insert a flag if not exists
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('initial_indexing_done', '0')"
            )

            conn.commit()

    def is_initial_indexing_done(self) -> bool:
        """
        Checks if the initial indexing of the music collection database has been completed.

        Queries the metadata table for the 'initial_indexing_done' flag and returns True if indexing is finished.

        Returns:
            bool: True if initial indexing is done, False otherwise.
        """
        with self.get_conn(readonly=True) as conn:
            cur = conn.execute("SELECT value FROM meta WHERE key = 'initial_indexing_done'")
            row = cur.fetchone()
            return row is not None and row["value"] == "1"

    def set_initial_indexing_done(self) -> None:
        """
        Marks the initial indexing of the music collection database as completed.

        Updates the metadata table to set the 'initial_indexing_done' flag to '1', indicating that initial indexing is finished.

        Returns:
            None
        """
        with self.get_conn() as conn:
            conn.execute("UPDATE meta SET value = '1' WHERE key = 'initial_indexing_done'")
            conn.commit()

    def _populate_fts_if_needed(self):
        """Populates the full-text search (FTS) table if it is currently empty.

        Checks if the FTS table has any rows and, if not, bulk inserts all track metadata from the main tracks table.

        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA busy_timeout=10000;")
            # Quick check – if the FTS table already has rows, skip.
            cnt = conn.execute("SELECT count(*) FROM tracks_fts").fetchone()[0]
            if cnt > 0:
                return

            # Bulk insert using a single INSERT…SELECT statement
            conn.execute(
                """
                INSERT INTO tracks_fts(rowid, artist, album, title, albumartist, genre, path, filename, duration, disc_number, track_number)
                SELECT rowid, artist, album, title, albumartist, genre, path, filename, duration, disc_number, track_number FROM tracks;
                """
            )
            conn.commit()

    def get_conn(self, readonly: bool = False) -> sqlite3.Connection:
        """Creates and returns a SQLite database connection.

        Returns a connection to the music database, optionally in read-only mode. The connection uses row factory for dictionary-like access to results.

        Args:
            readonly (bool): If True, opens the database in read-only mode.

        Returns:
            sqlite3.Connection: The database connection object.
        """
        if readonly:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)

        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    # === Writer loop (ONLY writer) ===

    def _db_writer_loop(self) -> None:
        """Processes database write events from the queue in a dedicated thread.

        Handles indexing, deletion, and commit events to keep the music database up to date and responsive.
        Commits changes periodically and ensures proper cleanup on exit.

        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")

            processed_in_batch = 0

            while not self._writer_stop.is_set():
                try:
                    event = self._write_queue.get(timeout=1.0)
                except Empty:
                    continue

                # CRITICAL FIX: Acquire lock for database operations
                with self._db_lock:
                    try:
                        if event.type == "CLEAR_DB":
                            conn.execute("DELETE FROM tracks")
                            conn.execute("DELETE FROM tracks_fts")  # Clear FTS table as well
                            conn.commit()
                            # CRITICAL FIX: Checkpoint WAL after clearing
                            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                            self._logger.info("Database cleared and checkpointed")

                        elif event.type == "DELETE_FILE":
                            if event.path:
                                rel_path = self._to_relpath(event.path) if event.path.is_absolute() else str(event.path)
                                conn.execute("DELETE FROM tracks WHERE path = ?", (rel_path,))
                            self._processed_count += 1
                            processed_in_batch += 1

                        elif event.type == "INDEX_FILE":
                            if event.path:
                                self._index_file(conn, event.path)
                            self._processed_count += 1
                            processed_in_batch += 1

                        elif event.type in ("REBUILD_DONE", "RESYNC_DONE"):
                            conn.commit()
                            # CRITICAL FIX: Checkpoint WAL after major operations
                            conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                            # Force final 100% progress
                            if self._total_for_current_job is not None:
                                set_indexing_status(
                                    self.data_root,
                                    self._current_job_status,
                                    total=self._total_for_current_job,
                                    current=self._total_for_current_job,
                                )
                            self._total_for_current_job = None
                            self._current_job_status = None
                            self._processed_count = 0
                            self._logger.info("Job completed signal processed and checkpointed")

                        # Commit and update progress periodically (every 50 operations)
                        if processed_in_batch >= 50:
                            conn.commit()
                            if self._total_for_current_job is not None:
                                set_indexing_status(
                                    self.data_root,
                                    self._current_job_status,
                                    total=self._total_for_current_job,
                                    current=self._processed_count,
                                )
                            processed_in_batch = 0

                    except sqlite3.Error as e:
                        self._logger.error(f"Database error during {event.type}: {e}", exc_info=True)
                        conn.rollback()
                        try:
                            conn.execute("PRAGMA integrity_check;")
                        except Exception as check_error:
                            self._logger.error(f"Database integrity check failed: {check_error}")

                self._write_queue.task_done()

            try:
                conn.commit()
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                self._logger.info("Writer loop shutdown: committed and checkpointed")
            except Exception as e:
                self._logger.error(f"Error during writer loop shutdown: {e}")

    # === Metadata extraction ===

    def _index_file(self, conn: sqlite3.Connection, path: Path) -> None:
        """Extracts metadata from a music file and updates the database entry.

        Reads metadata such as artist, album, title, year, and duration from the given file and inserts or updates the corresponding record in the database.

        Args:
            conn (sqlite3.Connection): The database connection to use for the update.
            path (Path): The path to the music file to index.

        Returns:
            None
        """
        try:
            if not path.exists():
                self._logger.warning(f"File no longer exists during indexing: {path}")
                return

            tag = TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            self._logger.warning(f"Failed to read tags from {path}: {e}")
            tag = None

        rel_path = self._to_relpath(path)

        artist = getattr(tag, "artist", None) or getattr(tag, "albumartist", None)
        album = getattr(tag, "album", None)
        title = getattr(tag, "title", None) or path.stem
        track_number = self._parse_number(getattr(tag, "track", None))
        disc_number = self._parse_number(getattr(tag, "disc", None))

        year = None
        try:
            if getattr(tag, "year", None):
                year = int(str(tag.year)[:4])
        except (AttributeError, ValueError):
            year = None

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tracks
                (path, filename, artist, album, title, albumartist, genre,
                year, duration, mtime, track_number, disc_number)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rel_path,
                    path.name,
                    artist or "Unknown",
                    album or "Unknown",
                    title or "Unknown",
                    getattr(tag, "albumartist", None),
                    getattr(tag, "genre", None),
                    year,
                    getattr(tag, "duration", None),
                    path.stat().st_mtime if path.exists() else None,
                    track_number,
                    disc_number,
                ),
            )
        except sqlite3.Error as e:
            self._logger.error(f"Failed to index {path}: {e}")
            raise

    def _parse_number(self, value: Optional[str]) -> Optional[int]:
        """
        Parses a string value and returns its integer component if possible.

        Extracts the first integer from a string (e.g., "3/12" → 3) or returns None if parsing fails.

        Args:
            value (Optional[str]): The string value to parse.

        Returns:
            Optional[int]: The parsed integer, or None if parsing fails.
        """
        if not value:
            return None
        try:
            return int(str(value).split("/")[0])
        except ValueError:
            return None

    # === Loading data main loops ===

    def rebuild(self) -> None:
        """Rebuilds the music collection database from scratch.

        Scans all supported music files in the root directory and reindexes them, updating the database and indexing status throughout the process.

        Returns:
            None
        """
        self._logger.info("Starting full rebuild")

        self._initial_status_event.set()

        set_indexing_status(self.data_root, "rebuilding", total=-1, current=0)
        self._write_queue.put(IndexEvent("CLEAR_DB"))

        self._write_queue.join()

        # Scan files incrementally with progress
        files = []
        found = 0
        for root, _, filenames in os.walk(str(self.music_root)):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in self.SUPPORTED_EXTS:
                    p = Path(root) / fn
                    files.append(p)
                    found += 1
                    if found % 100 == 0:
                        set_indexing_status(self.data_root, "rebuilding", total=-1, current=found)

        set_indexing_status(self.data_root, "rebuilding", total=len(files), current=0)

        # Rebuild: delete nothing (DB already cleared), index everything
        self._queue_file_operations(
            to_delete=[],               # No deletes needed — DB was cleared
            to_index=files,
            job_type="rebuilding",
        )

        self.set_initial_indexing_done()

    def _queue_file_operations(
            self,
            to_delete: Iterable[str],
            to_index: Iterable[Path],
            job_type: Literal["rebuilding", "resyncing"],
        ) -> None:
            """
            Queues delete and index operations with progress tracking.
            Used by both rebuild() and resync().
            """
            delete_list = list(to_delete)
            index_list = list(to_index)

            total_operations = len(delete_list) + len(index_list)
            if total_operations == 0:
                clear_indexing_status(self.data_root)
                self._logger.info(f"No {job_type} operations needed")
                return

            self._processed_count = 0
            self._total_for_current_job = total_operations
            self._current_job_status = job_type
            set_indexing_status(self.data_root, job_type, total=total_operations, current=0)

            # Queue deletes
            for rel_path in delete_list:
                self._write_queue.put(IndexEvent("DELETE_FILE", Path(rel_path)))

            # Queue indexes
            for abs_path in index_list:
                self._write_queue.put(IndexEvent("INDEX_FILE", abs_path))

            # Signal completion
            done_event = "REBUILD_DONE" if job_type == "rebuilding" else "RESYNC_DONE"
            self._write_queue.put(IndexEvent(done_event))
            self._write_queue.join()
            clear_indexing_status(self.data_root)
            self._logger.info(f"{job_type.capitalize()} completed ({total_operations} operations)")

    # === Resync ===

    def resync(self) -> None:
        """Synchronizes the music database with the current state of the file system.

        Identifies new and removed music files, updating the database to reflect additions and deletions.
        Progress is tracked and logged throughout the process.

        Returns:
            None
        """
        self._logger.info("Starting resync")

        set_indexing_status(self.data_root, "resyncing", total=-1, current=0)

        with self._db_lock:
            # Incremental scan with progress
            fs_paths = set()
            found = 0
            for root, _, filenames in os.walk(str(self.music_root)):
                for fn in filenames:
                    if os.path.splitext(fn)[1].lower() in self.SUPPORTED_EXTS:
                        p = Path(root) / fn
                        rel_path = self._to_relpath(p)
                        fs_paths.add(rel_path)
                        found += 1
                        if found % 100 == 0:
                            set_indexing_status(self.data_root, "resyncing", total=-1, current=found)

            with self.get_conn(readonly=True) as conn:
                db_paths = {r["path"] for r in conn.execute("SELECT path FROM tracks")}

        to_add_rel = fs_paths - db_paths
        to_remove_rel = db_paths - fs_paths

        to_add_abs = [self._to_abspath(p) for p in to_add_rel]

        self._logger.info(f"Resync: {len(to_add_rel)} to add, {len(to_remove_rel)} to remove")

        set_indexing_status(self.data_root, "resyncing", total=len(to_add_rel) + len(to_remove_rel), current=0)

        self._queue_file_operations(
            to_delete=to_remove_rel,
            to_index=to_add_abs,
            job_type="resyncing",
        )

    # === Helpers ===

    def wait_for_indexing_start(self, timeout: float = 5.0) -> bool:
        """
        Waits for the initial indexing/rebuild to begin writing status.
        Useful for foreground threads to synchronize before checking indexing_status.json.

        Returns True if indexing started within timeout, False otherwise.
        """
        return self._initial_status_event.wait(timeout=timeout)

    def _to_relpath(self, path: Path) -> str:
        """
        Converts an absolute file path to a relative path with respect to the music root directory.

        Returns the relative path as a POSIX-style string for consistent storage and comparison.

        Args:
            path (Path): The absolute file path to convert.

        Returns:
            str: The relative POSIX path.
        """
        return path.resolve().relative_to(self.music_root).as_posix()

    def _to_abspath(self, relpath: str) -> Path:
        """
        Converts a relative path to an absolute path within the music root directory.

        Returns the absolute Path object by joining the music root with the provided relative path.

        Args:
            relpath (str): The relative path to convert.

        Returns:
            Path: The absolute path within the music root directory.
        """
        return self.music_root / Path(relpath)

    # === Monitoring ===

    def start_monitoring(self) -> None:
        """Starts monitoring the music directory for file system changes.

        Initializes and starts a watchdog observer to track additions, modifications, and deletions of supported music files in real time.

        Returns:
            None
        """
        if self._observer:
            return
        self._observer = Observer()
        self._observer.schedule(_Watcher(self), str(self.music_root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stops the database writer thread and file system observer.

        Signals the writer thread to terminate and waits for it to finish, then stops and joins the observer if it is running.

        Returns:
            None
        """
        self._writer_stop.set()
        self._writer_thread.join(timeout=5)
        if self._observer:
            self._observer.stop()
            self._observer.join()


class _Watcher(FileSystemEventHandler):
    """Handles file system events for the music collection.

    Monitors the music directory for changes and notifies the CollectionExtractor to update the database accordingly.
    """

    def __init__(self, extractor: CollectionExtractor) -> None:
        """Initializes the file system event handler for music collection monitoring.

        Associates the handler with a CollectionExtractor instance to process file system events for supported music files.

        Args:
            extractor (CollectionExtractor): The music collection extractor to notify of file system events.

        Returns:
            None
        """
        self.extractor = extractor

    def on_any_event(self, event: object) -> None:
        """Handles any file system event for supported music files.

        Responds to file creation, modification, or deletion events by updating the music database accordingly.
        Ignores directory events and unsupported file types.

        Args:
            event (object): The file system event to handle.

        Returns:
            None
        """
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in self.extractor.SUPPORTED_EXTS:
            return

        if event.event_type in ("created", "modified"):
            self.extractor._write_queue.put(IndexEvent("INDEX_FILE", path))
        elif event.event_type == "deleted":
            self.extractor._write_queue.put(IndexEvent("DELETE_FILE", path))
