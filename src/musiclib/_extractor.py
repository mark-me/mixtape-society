import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event as ThreadEvent, Thread, Lock
from typing import Iterable, Literal

from tinytag import TinyTag
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from common.logging import Logger, NullLogger

from .indexing_status import clear_indexing_status, set_indexing_status

# =========================
# Constants
# =========================

SUPPORTED_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}
BATCH_SIZE = 50
BUSY_TIMEOUT_MS = 10000
PROGRESS_UPDATE_INTERVAL = 100

# Validate constants at module load time
assert isinstance(BUSY_TIMEOUT_MS, int) and BUSY_TIMEOUT_MS > 0, (
    "BUSY_TIMEOUT_MS must be a positive integer"
)
assert isinstance(BATCH_SIZE, int) and BATCH_SIZE > 0, (
    "BATCH_SIZE must be a positive integer"
)
assert isinstance(PROGRESS_UPDATE_INTERVAL, int) and PROGRESS_UPDATE_INTERVAL > 0, (
    "PROGRESS_UPDATE_INTERVAL must be a positive integer"
)

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
    """Represents an event for indexing or modifying music files in the collection."""

    type: EventType
    path: Path | None = None


# =========================
# Database utilities
# =========================


def configure_connection(conn: sqlite3.Connection) -> None:
    """Configures SQLite pragmas for write-ahead logging, durability, and concurrency.

    This function enables WAL mode, tunes the synchronous setting for a balance
    between safety and performance, and sets a busy timeout so concurrent access
    is less likely to result in immediate locking errors.

    Args:
        conn (sqlite3.Connection): The SQLite connection to configure.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # PRAGMA doesn't support parameters, but BUSY_TIMEOUT_MS is validated as int at module load
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def checkpoint_wal(conn: sqlite3.Connection, mode: str = "PASSIVE") -> None:
    """Runs a validated WAL checkpoint on the SQLite database connection.

    This function normalizes and validates the requested checkpoint mode
    against a whitelist, then issues the corresponding PRAGMA to control
    write-ahead log size and merge changes back into the main database file.

    Args:
        conn (sqlite3.Connection): The SQLite connection on which to run the checkpoint.
        mode (str): The checkpoint mode to use (e.g., "PASSIVE", "FULL", "RESTART", "TRUNCATE").

    Raises:
        ValueError: If the provided mode is not one of the allowed checkpoint modes.
    """
    allowed_modes = {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}
    normalized_mode = mode.upper()

    if normalized_mode not in allowed_modes:
        raise ValueError(
            f"Invalid WAL checkpoint mode {mode!r}. "
            f"Expected one of: {', '.join(sorted(allowed_modes))}."
        )

    # Safe: mode is validated against whitelist
    conn.execute(f"PRAGMA wal_checkpoint({normalized_mode})")


# =========================
# Schema definitions (as constants for safety)
# =========================

# These are hardcoded strings, not user input, so they're safe
SCHEMA_TRACKS_TABLE = """
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

SCHEMA_META_TABLE = """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
"""

SCHEMA_FTS_TABLE = """
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
        tokenize='unicode61 remove_diacritics 1'
    )
"""

# Index definitions as tuples (name, columns) - validated before use
INDEX_DEFINITIONS = [
    ("idx_artist", "artist COLLATE NOCASE"),
    ("idx_album", "album COLLATE NOCASE"),
    ("idx_title", "title COLLATE NOCASE"),
    ("idx_album_track", "album COLLATE NOCASE, disc_number, track_number"),
]

# Trigger definitions as complete SQL strings (no interpolation)
TRIGGER_INSERT = """
    CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks
    BEGIN
        INSERT INTO tracks_fts(
            rowid, artist, album, title, albumartist, genre,
            path, filename, duration, disc_number, track_number
        )
        VALUES (
            new.rowid, new.artist, new.album, new.title, new.albumartist,
            new.genre, new.path, new.filename, new.duration,
            new.disc_number, new.track_number
        );
    END
"""

TRIGGER_DELETE = """
    CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks
    BEGIN
        INSERT INTO tracks_fts(
            tracks_fts, rowid, artist, album, title, albumartist, genre,
            path, filename, duration, disc_number, track_number
        )
        VALUES (
            'delete', old.rowid, old.artist, old.album, old.title,
            old.albumartist, old.genre, old.path, old.filename,
            old.duration, old.disc_number, old.track_number
        );
    END
"""

TRIGGER_UPDATE = """
    CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks
    BEGIN
        INSERT INTO tracks_fts(
            tracks_fts, rowid, artist, album, title, albumartist, genre,
            path, filename, duration, disc_number, track_number
        )
        VALUES (
            'delete', old.rowid, old.artist, old.album, old.title,
            old.albumartist, old.genre, old.path, old.filename,
            old.duration, old.disc_number, old.track_number
        );
        INSERT INTO tracks_fts(
            rowid, artist, album, title, albumartist, genre,
            path, filename, duration, disc_number, track_number
        )
        VALUES (
            new.rowid, new.artist, new.album, new.title, new.albumartist,
            new.genre, new.path, new.filename, new.duration,
            new.disc_number, new.track_number
        );
    END
"""

# FTS population query
FTS_POPULATE_QUERY = """
    INSERT INTO tracks_fts(
        rowid, artist, album, title, albumartist, genre,
        path, filename, duration, disc_number, track_number
    )
    SELECT
        rowid, artist, album, title, albumartist, genre,
        path, filename, duration, disc_number, track_number
    FROM tracks
"""


# =========================
# Main class
# =========================


class CollectionExtractor:
    """Manages extraction, indexing, and synchronization of music files in a collection."""

    SUPPORTED_EXTS = SUPPORTED_EXTS

    def __init__(
        self, music_root: Path, db_path: Path, logger: Logger | None = None
    ) -> None:
        """Creates a new collection extractor for managing a music library index.

        This initializer wires together filesystem paths, logging, database schema,
        and background worker infrastructure so that music files can be scanned,
        indexed, and kept in sync with the underlying SQLite database.

        Args:
            music_root (Path): Root directory containing the music files to be indexed.
            db_path (Path): Path to the SQLite database file storing track metadata and search index.
            logger (Logger | None): Optional logger for recording indexing progress and errors;
                if omitted, a NullLogger is used.
        """
        self.music_root = music_root.resolve()
        self.db_path = db_path
        self.data_root = db_path.parent
        self._logger = logger or NullLogger()

        self.data_root.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self._initial_status_event = ThreadEvent()
        self._processed_count = 0
        self._total_for_current_job = None
        self._current_job_status = None

        # Threading
        self._write_queue: Queue[IndexEvent] = Queue()
        self._writer_stop = ThreadEvent()
        self._observer: Observer | None = None
        self._db_lock = Lock()

        self._init_db()
        self._start_writer_thread()

    def _start_writer_thread(self) -> None:
        """Starts the background database writer thread."""
        self._writer_thread = Thread(
            target=self._db_writer_loop,
            name="sqlite-writer",
            daemon=True,
        )
        self._writer_thread.start()

    # === Database setup ===

    def _init_db(self) -> None:
        """Initializes the SQLite database schema for music tracks and full-text search."""
        with self._get_write_conn() as conn:
            self._create_tracks_table(conn)
            self._create_indexes(conn)
            self._create_fts_table(conn)
            self._create_triggers(conn)
            self._create_meta_table(conn)
            conn.commit()

    def _create_tracks_table(self, conn: sqlite3.Connection) -> None:
        """Ensures the core tracks table exists for storing music metadata.

        This method executes the predefined schema statement to create the tracks
        table if it is missing, providing a durable home for per-file metadata and
        avoiding recreation when the table is already present.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the table.
        """
        conn.execute(SCHEMA_TRACKS_TABLE)

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Creates secondary indexes on the tracks table to speed up common queries.

        This method validates index names for safety, then creates indexes for
        artist, album, title, and album/track ordering columns so lookups and
        sorting over track metadata perform efficiently.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the indexes.
        """
        # Validate index names contain only safe characters
        for idx_name, idx_cols in INDEX_DEFINITIONS:
            # Validate index name is alphanumeric and underscores only
            if not idx_name.replace("_", "").isalnum():
                raise ValueError(f"Invalid index name: {idx_name}")

            # Create index - idx_name is validated, idx_cols is from trusted constant
            sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON tracks({idx_cols})"
            conn.execute(sql)

    def _create_fts_table(self, conn: sqlite3.Connection) -> None:
        """Ensures the full-text search (FTS) virtual table exists for track metadata.

        This method executes the predefined FTS schema so that searchable views
        of artist, album, title, and related fields are available and remain
        linked to the primary tracks table.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the FTS table.
        """
        conn.execute(SCHEMA_FTS_TABLE)

    def _create_triggers(self, conn: sqlite3.Connection) -> None:
        """Ensures triggers exist to keep the FTS table synchronized with track changes.

        This method installs insert, delete, and update triggers on the tracks table
        so that corresponding rows in the FTS virtual table are automatically created,
        removed, or updated whenever track metadata changes.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the triggers.
        """
        conn.execute(TRIGGER_INSERT)
        conn.execute(TRIGGER_DELETE)
        conn.execute(TRIGGER_UPDATE)

    def _create_meta_table(self, conn: sqlite3.Connection) -> None:
        """Ensures the meta table exists and seeds it with collection-wide flags.

        This method creates the meta table if needed and inserts the
        ``initial_indexing_done`` flag with a default value so that callers can
        track whether a full initial index of the collection has been completed.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create and seed the meta table.
        """
        conn.execute(SCHEMA_META_TABLE)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("initial_indexing_done", "0"),
        )

    # === Connection management ===

    @contextmanager
    def _get_write_conn(self):
        """Provides a configured write-capable SQLite connection as a context manager.

        This method opens a connection with collection-specific pragmas applied,
        yields it for write operations, and guarantees that the connection is
        closed when the context exits, even if an error occurs.

        Yields:
            sqlite3.Connection: A SQLite connection configured for writing to the collection database.
        """
        conn = sqlite3.connect(self.db_path)
        configure_connection(conn)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_conn(self, readonly: bool = False) -> sqlite3.Connection:
        """Opens and returns a configured SQLite connection for this collection.

        This method creates either a read-only or read-write connection depending
        on the ``readonly`` flag, applies a row factory for dict-like row access,
        and sets a busy timeout to make concurrent access more robust.

        Args:
            readonly (bool): Whether to open the connection in read-only mode. Defaults to False.

        Returns:
            sqlite3.Connection: A SQLite connection configured with an appropriate busy timeout.
        """
        if readonly:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)

        conn.row_factory = sqlite3.Row
        # PRAGMA doesn't support parameters, but BUSY_TIMEOUT_MS is validated as int at module load
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        return conn

    # === Metadata management ===

    def is_initial_indexing_done(self) -> bool:
        """Checks whether an initial full indexing pass has been completed.

        This method looks up the ``initial_indexing_done`` flag in the meta table
        and interprets a stored value of "1" as meaning the first full index has
        successfully run.

        Returns:
            bool: True if initial indexing has been marked as done, otherwise False.
        """
        with self.get_conn(readonly=True) as conn:
            cur = conn.execute(
                "SELECT value FROM meta WHERE key = ?", ("initial_indexing_done",)
            )
            row = cur.fetchone()
            return row is not None and row["value"] == "1"

    def set_initial_indexing_done(self) -> None:
        """Marks that the initial full indexing pass has completed successfully.

        This method updates the meta table flag so future runs and external
        callers can detect that a complete initial index of the collection is
        already in place.

        Returns:
            None
        """
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = ?",
                ("1", "initial_indexing_done"),
            )
            conn.commit()

    def _populate_fts_if_needed(self) -> None:
        """Populates the full-text search (FTS) table if it is currently empty."""
        with self._get_write_conn() as conn:
            cnt = conn.execute("SELECT count(*) FROM tracks_fts").fetchone()[0]
            if cnt > 0:
                return

            conn.execute(FTS_POPULATE_QUERY)
            conn.commit()

    # === Writer loop ===

    def _db_writer_loop(self) -> None:
        """Populates the full-text search (FTS) table when it has no entries.

        This method checks whether the FTS table is empty and, if so, bulk-copies
        all existing track rows into it so full-text search becomes available
        without requiring a separate rebuild step.

        Returns:
            None
        """
        with self._get_write_conn() as conn:
            processed_in_batch = 0

            while not self._writer_stop.is_set():
                try:
                    event = self._write_queue.get(timeout=1.0)
                except Empty:
                    continue

                with self._db_lock:
                    try:
                        self._process_event(conn, event)

                        # Periodic commit and progress update
                        processed_in_batch += self._should_increment_batch(event)
                        if processed_in_batch >= BATCH_SIZE:
                            conn.commit()
                            self._update_progress_status()
                            processed_in_batch = 0

                    except sqlite3.Error as e:
                        self._handle_database_error(conn, event, e)

                self._write_queue.task_done()

            self._shutdown_writer(conn)

    def _process_event(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Routes a single indexing event to the appropriate handler based on its type.

        This method inspects the event type and delegates to clear, delete,
        index, or job-completion handlers so that all write operations and job
        lifecycle changes are applied consistently through a single dispatch
        point.

        Args:
            conn (sqlite3.Connection): The active database connection used to apply the event.
            event (IndexEvent): The indexing event describing the operation to perform.
        """
        if event.type == "CLEAR_DB":
            self._clear_database(conn)

        elif event.type == "DELETE_FILE":
            self._delete_file(conn, event)

        elif event.type == "INDEX_FILE":
            self._handle_index_file(conn, event)

        elif event.type in ("REBUILD_DONE", "RESYNC_DONE"):
            self._handle_job_completion(conn)

    def _clear_database(self, conn: sqlite3.Connection) -> None:
        """Clears all tracks from the database."""
        conn.execute("DELETE FROM tracks")
        conn.execute("DELETE FROM tracks_fts")
        conn.commit()
        checkpoint_wal(conn, "TRUNCATE")
        self._logger.info("Database cleared and checkpointed")

    def _delete_file(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Deletes a file from the database."""
        if event.path:
            rel_path = (
                self._to_relpath(event.path)
                if event.path.is_absolute()
                else str(event.path)
            )
            conn.execute("DELETE FROM tracks WHERE path = ?", (rel_path,))
        self._processed_count += 1

    def _handle_index_file(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Handles indexing a single file."""
        if event.path:
            self._index_file(conn, event.path)
        self._processed_count += 1

    def _handle_job_completion(self, conn: sqlite3.Connection) -> None:
        """Handles completion of a rebuild or resync job."""
        conn.commit()
        checkpoint_wal(conn, "PASSIVE")

        # Force final 100% progress
        if self._total_for_current_job is not None:
            set_indexing_status(
                self.data_root,
                self._current_job_status,
                total=self._total_for_current_job,
                current=self._total_for_current_job,
            )

        self._reset_job_state()
        self._logger.info("Job completed signal processed and checkpointed")

    def _should_increment_batch(self, event: IndexEvent) -> int:
        """Returns 1 if the event should increment the batch counter, 0 otherwise."""
        return 1 if event.type in ("DELETE_FILE", "INDEX_FILE") else 0

    def _update_progress_status(self) -> None:
        """Updates the indexing status with current progress."""
        if self._total_for_current_job is not None:
            set_indexing_status(
                self.data_root,
                self._current_job_status,
                total=self._total_for_current_job,
                current=self._processed_count,
            )

    def _reset_job_state(self) -> None:
        """Resets job tracking state."""
        self._total_for_current_job = None
        self._current_job_status = None
        self._processed_count = 0

    def _handle_database_error(
        self, conn: sqlite3.Connection, event: IndexEvent, error: sqlite3.Error
    ) -> None:
        """Handles database errors gracefully."""
        self._logger.error(
            f"Database error during {event.type}: {error}", exc_info=True
        )
        conn.rollback()
        try:
            conn.execute("PRAGMA integrity_check")
        except Exception as check_error:
            self._logger.error(f"Database integrity check failed: {check_error}")

    def _shutdown_writer(self, conn: sqlite3.Connection) -> None:
        """Performs final commit and checkpoint on writer thread shutdown."""
        try:
            conn.commit()
            checkpoint_wal(conn, "TRUNCATE")
            self._logger.info("Writer loop shutdown: committed and checkpointed")
        except Exception as e:
            self._logger.error(f"Error during writer loop shutdown: {e}")

    # === Metadata extraction ===

    def _index_file(self, conn: sqlite3.Connection, path: Path) -> None:
        """Extracts metadata from a music file and updates the database entry."""
        if not path.exists():
            self._logger.warning(f"File no longer exists during indexing: {path}")
            return

        tag = self._read_tags(path)
        metadata = self._extract_metadata(tag, path)

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tracks
                (path, filename, artist, album, title, albumartist, genre,
                year, duration, mtime, track_number, disc_number)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                metadata,
            )
        except sqlite3.Error as e:
            self._logger.error(f"Failed to index {path}: {e}")
            raise

    def _read_tags(self, path: Path) -> TinyTag | None:
        """Reads tags from a music file, returning None if it fails."""
        try:
            return TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            self._logger.warning(f"Failed to read tags from {path}: {e}")
            return None

    def _extract_metadata(self, tag: TinyTag | None, path: Path) -> tuple:
        """Extracts metadata from tags into a tuple for database insertion."""
        rel_path = self._to_relpath(path)
        artist = getattr(tag, "artist", None) or getattr(tag, "albumartist", None)
        album = getattr(tag, "album", None)
        title = getattr(tag, "title", None) or path.stem
        track_number = self._parse_number(getattr(tag, "track", None))
        disc_number = self._parse_number(getattr(tag, "disc", None))
        year = self._parse_year(tag)

        return (
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
        )

    def _parse_year(self, tag: TinyTag | None) -> int | None:
        """Parses the year from tags."""
        try:
            if getattr(tag, "year", None):
                return int(str(tag.year)[:4])
        except (AttributeError, ValueError):
            pass
        return None

    def _parse_number(self, value: str | None) -> int | None:
        """Parses a string value and returns its integer component if possible."""
        if not value:
            return None
        try:
            return int(str(value).split("/")[0])
        except ValueError:
            return None

    # === File scanning ===

    def _scan_music_files(self, job_type: str) -> list[Path]:
        """Scans the music root for all supported audio files with progress tracking."""
        files = []
        found = 0

        for root, _, filenames in os.walk(str(self.music_root)):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in self.SUPPORTED_EXTS:
                    files.append(Path(root) / fn)
                    found += 1
                    if found % PROGRESS_UPDATE_INTERVAL == 0:
                        set_indexing_status(
                            self.data_root, job_type, total=-1, current=found
                        )

        return files

    # === Main operations ===

    def rebuild(self) -> None:
        """Rebuilds the music collection database from scratch."""
        self._logger.info("Starting full rebuild")
        self._initial_status_event.set()

        set_indexing_status(self.data_root, "rebuilding", total=-1, current=0)
        self._write_queue.put(IndexEvent("CLEAR_DB"))
        self._write_queue.join()

        files = self._scan_music_files("rebuilding")
        set_indexing_status(self.data_root, "rebuilding", total=len(files), current=0)

        self._queue_file_operations(
            to_delete=[],
            to_index=files,
            job_type="rebuilding",
        )

        self.set_initial_indexing_done()

    def resync(self) -> None:
        """Synchronizes the music database with the current state of the file system."""
        self._logger.info("Starting resync")
        set_indexing_status(self.data_root, "resyncing", total=-1, current=0)

        with self._db_lock:
            fs_paths = self._scan_filesystem_paths()
            db_paths = self._get_database_paths()

        to_add_rel = fs_paths - db_paths
        to_remove_rel = db_paths - fs_paths
        to_add_abs = [self._to_abspath(p) for p in to_add_rel]

        self._logger.info(
            f"Resync: {len(to_add_rel)} to add, {len(to_remove_rel)} to remove"
        )
        set_indexing_status(
            self.data_root,
            "resyncing",
            total=len(to_add_rel) + len(to_remove_rel),
            current=0,
        )

        self._queue_file_operations(
            to_delete=to_remove_rel,
            to_index=to_add_abs,
            job_type="resyncing",
        )

    def _scan_filesystem_paths(self) -> set[str]:
        """Scans the filesystem and returns a set of relative paths to music files."""
        fs_paths = set()
        found = 0

        for root, _, filenames in os.walk(str(self.music_root)):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in self.SUPPORTED_EXTS:
                    rel_path = self._to_relpath(Path(root) / fn)
                    fs_paths.add(rel_path)
                    found += 1
                    if found % PROGRESS_UPDATE_INTERVAL == 0:
                        set_indexing_status(
                            self.data_root, "resyncing", total=-1, current=found
                        )

        return fs_paths

    def _get_database_paths(self) -> set[str]:
        """Gets all paths currently in the database."""
        with self.get_conn(readonly=True) as conn:
            return {r["path"] for r in conn.execute("SELECT path FROM tracks")}

    def _queue_file_operations(
        self,
        to_delete: Iterable[str],
        to_index: Iterable[Path],
        job_type: Literal["rebuilding", "resyncing"],
    ) -> None:
        """Queues delete and index operations with progress tracking."""
        delete_list = list(to_delete)
        index_list = list(to_index)
        total_operations = len(delete_list) + len(index_list)

        if total_operations == 0:
            clear_indexing_status(self.data_root)
            self._logger.info(f"No {job_type} operations needed")
            return

        self._start_job(job_type, total_operations)
        self._queue_operations(delete_list, index_list, job_type)
        self._wait_for_job_completion(job_type, total_operations)

    def _start_job(self, job_type: str, total_operations: int) -> None:
        """Initializes job tracking state."""
        self._processed_count = 0
        self._total_for_current_job = total_operations
        self._current_job_status = job_type
        set_indexing_status(self.data_root, job_type, total=total_operations, current=0)

    def _queue_operations(
        self, delete_list: list[str], index_list: list[Path], job_type: str
    ) -> None:
        """Queues all delete and index operations."""
        for rel_path in delete_list:
            self._write_queue.put(IndexEvent("DELETE_FILE", Path(rel_path)))

        for abs_path in index_list:
            self._write_queue.put(IndexEvent("INDEX_FILE", abs_path))

        done_event = "REBUILD_DONE" if job_type == "rebuilding" else "RESYNC_DONE"
        self._write_queue.put(IndexEvent(done_event))

    def _wait_for_job_completion(self, job_type: str, total_operations: int) -> None:
        """Waits for the job to complete and cleans up."""
        self._write_queue.join()
        clear_indexing_status(self.data_root)
        self._logger.info(
            f"{job_type.capitalize()} completed ({total_operations} operations)"
        )

    # === Path utilities ===

    def _to_relpath(self, path: Path) -> str:
        """Converts an absolute file path to a relative path with respect to the music root directory."""
        return path.resolve().relative_to(self.music_root).as_posix()

    def _to_abspath(self, relpath: str) -> Path:
        """Converts a relative path to an absolute path within the music root directory."""
        return self.music_root / Path(relpath)

    # === Monitoring ===

    def start_monitoring(self) -> None:
        """Starts monitoring the music directory for file system changes."""
        if self._observer:
            return
        self._observer = Observer()
        self._observer.schedule(_Watcher(self), str(self.music_root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stops the database writer thread and file system observer."""
        self._writer_stop.set()
        self._writer_thread.join(timeout=5)
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def wait_for_indexing_start(self, timeout: float = 5.0) -> bool:
        """Waits for the initial indexing/rebuild to begin writing status."""
        return self._initial_status_event.wait(timeout=timeout)


# =========================
# File system watcher
# =========================


class _Watcher(FileSystemEventHandler):
    """Handles file system events for the music collection."""

    def __init__(self, extractor: CollectionExtractor) -> None:
        """Initializes the file system event handler for music collection monitoring."""
        self.extractor = extractor

    def on_any_event(self, event: object) -> None:
        """Handles any file system event for supported music files."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in self.extractor.SUPPORTED_EXTS:
            return

        if event.event_type in ("created", "modified"):
            self.extractor._write_queue.put(IndexEvent("INDEX_FILE", path))
        elif event.event_type == "deleted":
            self.extractor._write_queue.put(IndexEvent("DELETE_FILE", path))
