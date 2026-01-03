import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event as ThreadEvent, Thread, Lock
from typing import Iterable, Literal

from tinytag import TinyTag
from watchdog.observers import Observer

from common.logging import Logger, NullLogger

from .indexing_status import clear_indexing_status, set_indexing_status
from ._watcher import EnhancedWatcher as _Watcher

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

    This function enables WAL mode, tunes the synchronous setting for maximum
    safety during bulk operations, and sets a busy timeout so concurrent access
    is less likely to result in immediate locking errors.

    Args:
        conn (sqlite3.Connection): The SQLite connection to configure.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")  # Changed from NORMAL for maximum safety
    # PRAGMA doesn't support parameters, but BUSY_TIMEOUT_MS is validated as int at module load
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")


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

        try:
            self._init_db()
        except sqlite3.DatabaseError as e:
            if (
                'malformed' not in str(e).lower()
                and 'corrupt' not in str(e).lower()
            ):
                raise
            self._logger.error(f"Corruption detected: {e}")
            self._delete_database_files()
            self._init_db()  # Retry
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

    def _delete_database_files(self) -> None:
        """Deletes corrupted database files."""
        for suffix in ['', '-wal', '-shm', '-journal']:
            file_path = Path(str(self.db_path) + suffix)
            if file_path.exists():
                file_path.unlink()

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
        """Clears all track data from the database and resets the full-text index.

        This method deletes every row from the main tracks table and its FTS
        mirror, commits the changes, and runs a truncating WAL checkpoint so
        the collection can be rebuilt from a clean, compact state.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to remove all track data.
        """
        conn.execute("DELETE FROM tracks")
        conn.execute("DELETE FROM tracks_fts")
        conn.commit()
        checkpoint_wal(conn, "TRUNCATE")
        self._logger.info("Database cleared and checkpointed")

    def _delete_file(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Removes a single track record from the database for the given event path.

        This method normalizes the event path to the stored relative form when needed,
        executes a delete against the tracks table for that path, and increments the
        processed operation counter used for job progress tracking.

        Args:
            conn (sqlite3.Connection): The active SQLite connection used to apply the deletion.
            event (IndexEvent): The delete event containing the path of the track to remove.
        """
        if event.path:
            rel_path = (
                self._to_relpath(event.path)
                if event.path.is_absolute()
                else str(event.path)
            )
            conn.execute("DELETE FROM tracks WHERE path = ?", (rel_path,))
        self._processed_count += 1

    def _handle_index_file(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Processes an index-file event and advances job progress.

        This method delegates the actual metadata extraction and database update
        to the low-level file indexer when a path is present on the event, then
        increments the processed-operation counter so that job progress tracking
        remains accurate regardless of whether the file was indexable.

        Args:
            conn (sqlite3.Connection): The active database connection used during indexing.
            event (IndexEvent): The index event describing which file should be indexed.
        """
        if event.path:
            self._index_file(conn, event.path)
        self._processed_count += 1

    def _handle_job_completion(self, conn: sqlite3.Connection) -> None:
        """Finalizes an indexing job and records its completion.

        This method commits any remaining database changes, checkpoints the WAL in
        PASSIVE mode, forces external progress reporting to 100% if a job was
        being tracked, and then clears job state while logging that the completion
        signal was processed.

        Args:
            conn (sqlite3.Connection): The database connection used throughout the indexing job.
        """
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
        """Determines whether an event should contribute to the current batch size.

        This method returns 1 for file-level operations that modify the tracks
        table, such as delete and index events, and 0 for control events that
        should not trigger batch commits.

        Args:
            event (IndexEvent): The indexing event being evaluated.

        Returns:
            int: 1 if the event should increment the processed-in-batch counter, otherwise 0.
        """
        return 1 if event.type in ("DELETE_FILE", "INDEX_FILE") else 0

    def _update_progress_status(self) -> None:
        """Updates external indexing progress based on the current job counters.

        This method sends the latest processed and total operation counts for
        the active job to the indexing status helper so that UIs can display
        up-to-date progress information while rebuild or resync tasks run.

        Returns:
            None
        """
        if self._total_for_current_job is not None:
            set_indexing_status(
                self.data_root,
                self._current_job_status,
                total=self._total_for_current_job,
                current=self._processed_count,
            )

    def _reset_job_state(self) -> None:
        """Clears internal tracking state for the current indexing job.

        This method resets the total operation count, current job status label,
        and processed-operation counter so that subsequent jobs start with a
        clean progress state.
        """
        self._total_for_current_job = None
        self._current_job_status = None
        self._processed_count = 0

    def _handle_database_error(
        self, conn: sqlite3.Connection, event: IndexEvent, error: sqlite3.Error
    ) -> None:
        """Logs and recovers from a database error encountered during event processing.

        This method records the original SQLite error with context, rolls back the
        current transaction to maintain consistency, and then attempts an integrity
        check on the database, logging a secondary error if the check itself fails.

        Args:
            conn (sqlite3.Connection): The database connection on which the error occurred.
            event (IndexEvent): The indexing event being processed when the error was raised.
            error (sqlite3.Error): The SQLite error that triggered this handler.
        """
        self._logger.error(
            f"Database error during {event.type}: {error}", exc_info=True
        )
        conn.rollback()
        try:
            conn.execute("PRAGMA integrity_check")
        except Exception as check_error:
            self._logger.error(f"Database integrity check failed: {check_error}")

    def _shutdown_writer(self, conn: sqlite3.Connection) -> None:
        """Cleanly shuts down the writer loop by flushing pending work to disk.

        This method attempts a final commit and WAL checkpoint before the writer
        thread exits, logging either a successful shutdown message or an error
        if flushing changes fails.

        Args:
            conn (sqlite3.Connection): The SQLite connection used by the writer loop.
        """
        try:
            conn.commit()
            checkpoint_wal(conn, "TRUNCATE")
            self._logger.info("Writer loop shutdown: committed and checkpointed")
        except Exception as e:
            self._logger.error(f"Error during writer loop shutdown: {e}")

    # === Metadata extraction ===

    def _index_file(self, conn: sqlite3.Connection, path: Path) -> None:
        """Indexes a single music file into the tracks table.

        This method reads tags and file metadata for the given path and upserts
        a normalized record into the tracks table so the database reflects the
        current state of the file on disk. If the file disappears during
        processing, it logs a warning and skips indexing; if a database error
        occurs, it logs the failure and re-raises the exception.

        Args:
            conn (sqlite3.Connection): The SQLite connection used to write track metadata.
            path (Path): The absolute path of the music file to index.

        Raises:
            sqlite3.Error: If the INSERT OR REPLACE operation fails at the database layer.
        """
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
        """Reads tag metadata from an audio file, returning None if parsing fails.

        This method attempts to load tag and duration information for the given
        path and logs a warning when the file cannot be read or parsed so that
        callers can continue indexing without raising errors.

        Args:
            path (Path): The absolute filesystem path to the audio file whose tags should be read.

        Returns:
            TinyTag | None: A TinyTag instance containing parsed metadata, or None if reading fails.
        """
        try:
            return TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            self._logger.warning(f"Failed to read tags from {path}: {e}")
            return None

    def _extract_metadata(self, tag: TinyTag | None, path: Path) -> tuple:
        """Builds a normalized metadata tuple for a music file from tags and file attributes.

        This method combines TinyTag metadata with filesystem information and
        sensible fallbacks to produce a stable representation of a track that
        can be stored in the database even when some tags are missing or
        malformed.

        Args:
            tag (TinyTag | None): Parsed tag metadata for the file, or None if tags could not be read.
            path (Path): The absolute filesystem path of the music file.

        Returns:
            tuple: A tuple of track fields in the order expected by the ``tracks`` table schema.
        """
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
        """Parses a year value from tag metadata and returns it as a four-digit integer.

        This method inspects the ``year`` attribute on the tag, normalizes it to a
        string, and extracts the first four characters as an integer, returning
        None if the attribute is missing or cannot be parsed.

        Args:
            tag (TinyTag | None): Tag metadata object that may contain a year attribute, or None.

        Returns:
            int | None: The four-digit year if successfully parsed, otherwise None.
        """
        try:
            if getattr(tag, "year", None):
                return int(str(tag.year)[:4])
        except (AttributeError, ValueError):
            pass
        return None

    def _parse_number(self, value: str | None) -> int | None:
        """Parses an integer from a numeric tag field string.

        This method extracts the leading integer component from values that may
        be in forms like ``"3"`` or ``"3/12"``, returning None when the input
        is empty or cannot be converted to an integer.

        Args:
            value (str | None): Raw tag value that should represent a number, optionally with a total (e.g., ``"3/12"``), or None.

        Returns:
            int | None: The parsed leading integer, or None if the input is missing or invalid.
        """
        if not value:
            return None
        try:
            return int(str(value).split("/")[0])
        except ValueError:
            return None

    # === File scanning ===

    def _scan_music_files(self, job_type: str) -> list[Path]:
        """Discovers all supported music files under the music root for an indexing job.

        This method walks the directory tree rooted at the music folder, collects
        absolute paths to files with supported audio extensions, and periodically
        updates indexing status so callers can observe discovery progress for the
        specified job type.

        Args:
            job_type (str): Label for the current indexing job, such as "rebuilding" or "resyncing".

        Returns:
            list[Path]: A list of absolute paths to all discovered music files.
        """
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
        """Performs a full rebuild of the music collection index from the current filesystem state.

        This method clears existing track data, scans the music root for all supported files,
        and queues indexing operations so that the database is fully regenerated to match
        the contents of the collection.

        Returns:
            None
        """
        self._logger.info("Starting full rebuild")
        self._initial_status_event.set()

        # Pause file monitoring to prevent race conditions with watcher
        with self._pause_observer():
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
        """Synchronizes the database with the current set of music files on disk.

        This method compares the filesystem under the music root with the paths
        stored in the database, then enqueues add and delete operations so that
        the index reflects files that have been created, removed, or renamed
        since the last run.

        Returns:
            None
        """
        self._logger.info("Starting resync")

        # Pause file monitoring to prevent race conditions with watcher
        with self._pause_observer():
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
        """Scans the music root on disk and returns the set of all supported file paths.

        This method walks the filesystem tree under the music root, collects
        POSIX-style relative paths for files with supported extensions, and
        periodically updates resync progress as files are discovered.

        Returns:
            set[str]: A set of relative paths for all supported music files currently on disk.
        """
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
        """Returns the set of all track paths currently stored in the database.

        This method queries the tracks table for the path column and collects all
        stored relative paths into a set for efficient comparison with filesystem state.

        Returns:
            set[str]: A set of relative track paths as stored in the database.
        """
        with self.get_conn(readonly=True) as conn:
            return {r["path"] for r in conn.execute("SELECT path FROM tracks")}

    def _queue_file_operations(
        self,
        to_delete: Iterable[str],
        to_index: Iterable[Path],
        job_type: Literal["rebuilding", "resyncing"],
    ) -> None:
        """Coordinates and dispatches all file operations for a rebuild or resync job.

        This method materializes the delete and index iterables, decides whether
        there is any work to perform, and when there is, starts job tracking,
        enqueues all operations, and blocks until the writer thread has finished
        processing them.

        Args:
            to_delete (Iterable[str]): Relative paths of tracks that should be removed from the database.
            to_index (Iterable[Path]): Absolute paths of files that should be indexed or reindexed.
            job_type (Literal["rebuilding", "resyncing"]): The type of indexing job these operations belong to.
        """
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
        """Initializes tracking state for a rebuild or resync indexing job.

        This method resets internal progress counters, records the job type and
        total number of operations to perform, and writes an initial status entry
        so external callers can monitor the job from the moment it starts.

        Args:
            job_type (str): Label for the indexing job being started, such as "rebuilding" or "resyncing".
            total_operations (int): Total number of delete and index operations expected for this job.
        """
        self._processed_count = 0
        self._total_for_current_job = total_operations
        self._current_job_status = job_type
        set_indexing_status(self.data_root, job_type, total=total_operations, current=0)

    def _queue_operations(
        self, delete_list: list[str], index_list: list[Path], job_type: str
    ) -> None:
        """Enqueues delete and index events for all operations in the current job.

        This method converts relative delete paths and absolute index paths into
        queue events for the writer thread, then appends a final completion event
        indicating whether the batch belongs to a rebuild or resync job.

        Args:
            delete_list (list[str]): Relative paths of tracks that should be removed from the database.
            index_list (list[Path]): Absolute paths of tracks that should be indexed or reindexed.
            job_type (str): The type of job being processed, such as "rebuilding" or "resyncing".
        """
        for rel_path in delete_list:
            self._write_queue.put(IndexEvent("DELETE_FILE", Path(rel_path)))

        for abs_path in index_list:
            self._write_queue.put(IndexEvent("INDEX_FILE", abs_path))

        done_event = "REBUILD_DONE" if job_type == "rebuilding" else "RESYNC_DONE"
        self._write_queue.put(IndexEvent(done_event))

    def _wait_for_job_completion(self, job_type: str, total_operations: int) -> None:
        """Blocks until all queued operations for the current job have been processed.

        This method waits for the writer queue to drain, then clears the external
        indexing status and logs a summary message indicating that the job type
        has completed along with the total number of operations performed.

        Args:
            job_type (str): The type of indexing job being waited on, such as "rebuilding" or "resyncing".
            total_operations (int): The total number of operations that were scheduled for the job.
        """
        self._write_queue.join()
        clear_indexing_status(self.data_root)
        self._logger.info(
            f"{job_type.capitalize()} completed ({total_operations} operations)"
        )

    # === Path utilities ===

    def _to_relpath(self, path: Path) -> str:
        """Converts an absolute path to a POSIX-style path relative to the music root.

        This method normalizes the given path, strips the music root prefix,
        and returns a string suitable for stable storage and comparison in the database.

        Args:
            path (Path): The absolute filesystem path to convert.

        Returns:
            str: The relative POSIX-style path under the music root.
        """
        return path.resolve().relative_to(self.music_root).as_posix()

    def _to_abspath(self, relpath: str) -> Path:
        """Converts a stored relative music path into an absolute filesystem path.

        This method joins the configured music root with the given relative path
        and returns a Path object that can be used for file system operations.

        Args:
            relpath (str): The POSIX-style relative path under the music root.

        Returns:
            Path: The absolute path pointing to the file within the music root.
        """
        return self.music_root / Path(relpath)

    # === Monitoring ===

    def start_monitoring(self) -> None:
        """Starts monitoring the music directory for file system changes."""
        if self._observer:
            return
        self._observer = Observer()
        self._observer.schedule(_Watcher(self), str(self.music_root), recursive=True)
        self._observer.start()

    def stop(self, timeout: float = 30.0) -> None:
        """Stops the database writer thread and file system observer.

        Args:
            timeout: Maximum time to wait for shutdown (seconds).
        """
        # Shutdown watcher first to flush pending events
        if self._observer:
            for handler_list in self._observer._handlers.values():
                for handler in handler_list:
                    if hasattr(handler, 'shutdown'):
                        handler.shutdown()
            self._observer.stop()
            self._observer.join(timeout=5)

        # Stop writer thread
        self._writer_stop.set()
        self._writer_thread.join(timeout=5)

    def _pause_observer(self):
        """Context manager to temporarily pause file monitoring.

        This prevents race conditions during rebuild/resync operations by ensuring
        the file watcher doesn't queue duplicate events while these operations
        are scanning the filesystem and queueing their own events.

        Returns:
            Context manager that pauses monitoring on entry and resumes on exit,
            reusing the standard observer setup logic in ``start_monitoring``.
        """

        @contextmanager
        def pause():
            # Check if observer is running
            was_monitoring = self._observer is not None and self._observer.is_alive()

            if was_monitoring:
                # Stop the observer completely
                self._observer.stop()
                self._observer.join(timeout=2)
                self._logger.info("File monitoring paused for rebuild/resync")

            try:
                yield
            finally:
                # Restart monitoring if it was active
                if was_monitoring:
                    # Re-create and start observer from scratch
                    from watchdog.observers import Observer
                    from ._watcher import EnhancedWatcher as _Watcher

                    self._observer = Observer()
                    handler = _Watcher(self)
                    self._observer.schedule(handler, str(self.music_root), recursive=True)
                    self._observer.start()

                    self._logger.info("File monitoring resumed")

        return pause()

    def enable_bulk_edit_mode(self) -> None:
        """Enables bulk edit mode by pausing file system monitoring.

        Call this before performing bulk file operations (e.g., tagging 100+ files)
        to prevent event flooding. File changes will not be indexed in real-time
        while bulk edit mode is active.

        Example:
            extractor.enable_bulk_edit_mode()
            try:
                # Perform bulk file operations here
                for file in files:
                    update_tags(file)
            finally:
                extractor.disable_bulk_edit_mode()
        """
        if self._observer:
            self._observer.unschedule_all()
            self._logger.info("File monitoring paused for bulk edit mode")

    def disable_bulk_edit_mode(self) -> None:
        """Disables bulk edit mode and resyncs the database.

        Call this after completing bulk file operations. This will resume file
        system monitoring and trigger a resync to catch all changes made during
        bulk edit mode.
        """
        if self._observer:
            # Resume monitoring with a new watcher instance
            watcher = _Watcher(self)
            self._observer.schedule(watcher, str(self.music_root), recursive=True)
            self._logger.info("File monitoring resumed, triggering resync")

        # Trigger resync to catch all changes
        self.resync()

    def wait_for_indexing_start(self, timeout: float = 5.0) -> bool:
        """Waits until indexing has started or the specified timeout elapses.

        This method blocks until the internal event indicating the beginning of
        a rebuild or resync job is set, allowing callers to synchronize with the
        start of indexing work.

        Args:
            timeout (float): The maximum number of seconds to wait for indexing to start.

        Returns:
            bool: True if indexing started before the timeout, or False if the timeout expired first.
        """
        return self._initial_status_event.wait(timeout=timeout)
