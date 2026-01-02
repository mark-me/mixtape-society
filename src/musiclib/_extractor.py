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

# FTS column list - used in multiple places
FTS_COLUMNS = "rowid, artist, album, title, albumartist, genre, path, filename, duration, disc_number, track_number"

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
    """Configures SQLite connection pragmas for write-ahead logging and responsiveness.

    This function enables WAL mode, adjusts synchronous behavior for a balance between
    durability and performance, and sets a busy timeout to reduce "database is locked"
    errors under contention.

    Args:
        conn (sqlite3.Connection): The SQLite connection to configure.
    """
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")


def checkpoint_wal(conn: sqlite3.Connection, mode: str = "PASSIVE") -> None:
    """Runs a WAL checkpoint on the SQLite database connection.

    This function issues a PRAGMA command to checkpoint the write-ahead log using
    the specified mode, helping to control WAL size and merge changes back into
    the main database file.

    Args:
        conn (sqlite3.Connection): The SQLite connection on which to run the checkpoint.
        mode (str): The checkpoint mode to use (e.g., "PASSIVE", "FULL", "RESTART", "TRUNCATE").
    """
    conn.execute(f"PRAGMA wal_checkpoint({mode});")


# =========================
# Main class
# =========================


class CollectionExtractor:
    """Manages extraction, indexing, and synchronization of music files in a collection."""

    SUPPORTED_EXTS = SUPPORTED_EXTS

    def __init__(
        self, music_root: Path, db_path: Path, logger: Logger | None = None
    ) -> None:
        """Initializes a collection extractor for managing a music library index.

        This constructor prepares filesystem paths, logging, database connections,
        and background worker threads so that music files can be scanned, indexed,
        and kept in sync with the database.

        Args:
            music_root (Path): Root directory on disk where music files are stored.
            db_path (Path): Path to the SQLite database file used for indexing metadata.
            logger (Logger | None): Optional logger for recording indexing and error messages;
                if None, a null logger is used.
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
        """Starts the background writer thread responsible for database updates.

        This method creates a daemon thread bound to the database writer loop and
        starts it so that indexing and maintenance operations can be processed
        asynchronously in the background.

        Returns:
            None
        """
        self._writer_thread = Thread(
            target=self._db_writer_loop,
            name="sqlite-writer",
            daemon=True,
        )
        self._writer_thread.start()

    # === Database setup ===

    def _init_db(self) -> None:
        """Initializes the collection database schema and supporting structures.

        This method opens a writable connection and ensures that core tables,
        indexes, full-text search structures, triggers, and metadata rows exist
        so that the collection can be indexed and queried reliably.

        Returns:
            None
        """
        with self._get_write_conn() as conn:
            self._create_tracks_table(conn)
            self._create_indexes(conn)
            self._create_fts_table(conn)
            self._create_triggers(conn)
            self._create_meta_table(conn)
            conn.commit()

    def _create_tracks_table(self, conn: sqlite3.Connection) -> None:
        """Creates the primary tracks table used to store music metadata.

        This method defines the core schema for track records, including identifying
        path information and descriptive fields such as artist, album, and duration,
        ensuring the table exists before any indexing or querying occurs.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the table.
        """
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

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Creates secondary indexes to speed up common track queries.

        This method defines a set of helpful indexes over artist, album, title,
        and album/track ordering columns so that lookups and sorting operations
        on the tracks table perform efficiently.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the indexes.
        """
        indexes = [
            ("idx_artist", "artist COLLATE NOCASE"),
            ("idx_album", "album COLLATE NOCASE"),
            ("idx_title", "title COLLATE NOCASE"),
            ("idx_album_track", "album COLLATE NOCASE, disc_number, track_number"),
        ]
        for idx_name, idx_cols in indexes:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON tracks({idx_cols})")

    def _create_fts_table(self, conn: sqlite3.Connection) -> None:
        """Creates the full-text search (FTS) virtual table for track metadata.

        This method defines an FTS5 virtual table that mirrors key columns from the
        tracks table, enabling efficient text search over fields like artist, album,
        title, and genre while remaining linked to the primary track records.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the FTS table.
        """
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
                tokenize='unicode61 remove_diacritics 1'
            );
            """
        )

    def _create_triggers(self, conn: sqlite3.Connection) -> None:
        """Creates triggers to keep the FTS table synchronized with the tracks table.

        This method defines insert, delete, and update triggers on the primary tracks
        table so that the corresponding rows in the FTS virtual table are maintained
        automatically as track records change.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create the triggers.
        """
        # Helper to build FTS column references
        new_cols = ", ".join(
            [f"new.{col}" for col in FTS_COLUMNS.replace("rowid, ", "").split(", ")]
        )
        old_cols = ", ".join(
            [f"old.{col}" for col in FTS_COLUMNS.replace("rowid, ", "").split(", ")]
        )

        conn.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks
            BEGIN
                INSERT INTO tracks_fts({FTS_COLUMNS})
                VALUES (new.rowid, {new_cols});
            END;

            CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks
            BEGIN
                INSERT INTO tracks_fts(tracks_fts, {FTS_COLUMNS})
                VALUES('delete', old.rowid, {old_cols});
            END;

            CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks
            BEGIN
                INSERT INTO tracks_fts(tracks_fts, {FTS_COLUMNS})
                VALUES('delete', old.rowid, {old_cols});
                INSERT INTO tracks_fts({FTS_COLUMNS})
                VALUES (new.rowid, {new_cols});
            END;
            """
        )

    def _create_meta_table(self, conn: sqlite3.Connection) -> None:
        """Creates and initializes the meta table used for collection-wide flags.

        This method ensures the meta table exists and seeds it with an
        ``initial_indexing_done`` flag so that the system can track whether a
        full initial index has been completed.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to create and seed the meta table.
        """
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('initial_indexing_done', '0')"
        )

    # === Connection management ===

    @contextmanager
    def _get_write_conn(self):
        """Yields a write-capable SQLite connection configured for this collection.

        This context manager opens a connection with write settings applied and
        ensures it is properly closed after use, allowing callers to perform
        database modifications without managing connection lifecycle manually.

        Yields:
            sqlite3.Connection: A configured SQLite connection ready for write operations.
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

        This method creates either a read-only or read-write connection based on the
        ``readonly`` flag, applies a row factory for dictionary-style access, and sets
        a busy timeout to make concurrent access more resilient.

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
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")
        return conn

    # === Metadata management ===

    def is_initial_indexing_done(self) -> bool:
        """Reports whether the initial full indexing of the music collection has completed.

        This method reads the ``initial_indexing_done`` flag from the meta table
        and returns True only when the stored value indicates that a complete
        initial index has been successfully run.

        Returns:
            bool: True if initial indexing has been marked as done, otherwise False.
        """
        with self.get_conn(readonly=True) as conn:
            cur = conn.execute(
                "SELECT value FROM meta WHERE key = 'initial_indexing_done'"
            )
            row = cur.fetchone()
            return row is not None and row["value"] == "1"

    def set_initial_indexing_done(self) -> None:
        """Marks the initial full indexing of the music collection as completed.

        This method updates the meta table flag so that subsequent calls and
        processes can detect that an initial, complete index has already run.

        Returns:
            None
        """
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE meta SET value = '1' WHERE key = 'initial_indexing_done'"
            )
            conn.commit()

    def _populate_fts_if_needed(self) -> None:
        """Ensures the full-text search index is populated when empty.

        This method checks whether the FTS table already contains rows and, if not,
        bulk-populates it from the existing tracks table so that text search is
        available without requiring a full reindex.

        Returns:
            None
        """
        with self._get_write_conn() as conn:
            cnt = conn.execute("SELECT count(*) FROM tracks_fts").fetchone()[0]
            if cnt > 0:
                return

            conn.execute(
                f"""
                INSERT INTO tracks_fts({FTS_COLUMNS})
                SELECT {FTS_COLUMNS.replace("rowid, ", "rowid, ")} FROM tracks;
                """
            )
            conn.commit()

    # === Writer loop ===

    def _db_writer_loop(self) -> None:
        """Runs the background loop that processes queued database write events.

        This method continuously pulls indexing events from the write queue, applies
        them within a shared database connection under a lock, and periodically
        commits batched changes and updates progress until a shutdown signal is set,
        at which point it performs a final flush and checkpoint.

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
        """Dispatches a single indexing event to the appropriate handler.

        This method examines the event type and routes clear, delete, index, and
        job-completion events to their dedicated helper methods so that database
        updates and progress tracking remain centralized.

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
        """Removes all track data from the database and resets the search index.

        This method deletes every row from the main tracks table and its associated
        full-text search table, commits the changes, and checkpoints the WAL so the
        collection can be rebuilt from a clean state.

        Args:
            conn (sqlite3.Connection): The SQLite connection on which to clear track data.
        """
        conn.execute("DELETE FROM tracks")
        conn.execute("DELETE FROM tracks_fts")
        conn.commit()
        checkpoint_wal(conn, "TRUNCATE")
        self._logger.info("Database cleared and checkpointed")

    def _delete_file(self, conn: sqlite3.Connection, event: IndexEvent) -> None:
        """Deletes a single track record from the database for a given file path.

        This method resolves the event path to the stored relative form when needed,
        issues a delete against the tracks table for that path, and updates the
        processed operation counter used for progress tracking.

        Args:
            conn (sqlite3.Connection): The active database connection used to execute the delete.
            event (IndexEvent): The delete event containing the file path to remove.
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
        """Processes a single index-file event and updates progress counters.

        This method delegates to the low-level file indexing routine when the
        event carries a path, and always increments the processed count so that
        job progress can be tracked consistently.

        Args:
            conn (sqlite3.Connection): The active database connection used during indexing.
            event (IndexEvent): The index event containing the path of the file to index.
        """
        if event.path:
            self._index_file(conn, event.path)
        self._processed_count += 1

    def _handle_job_completion(self, conn: sqlite3.Connection) -> None:
        """Finalizes an indexing job and records its completion.

        This method commits any remaining database changes, runs a WAL checkpoint,
        forces progress reporting to 100% when a job was tracked, and then resets
        internal job state while logging that the completion signal was processed.

        Args:
            conn (sqlite3.Connection): The database connection used for the indexing job.
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
        """Determines whether a given event should count toward the current batch size.

        This method returns 1 for file-level operations that modify the database,
        such as delete and index events, and 0 for control or bookkeeping events
        that should not trigger batch commits.

        Args:
            event (IndexEvent): The indexing event being evaluated.

        Returns:
            int: 1 if the event should increment the processed-in-batch counter, otherwise 0.
        """
        return 1 if event.type in ("DELETE_FILE", "INDEX_FILE") else 0

    def _update_progress_status(self) -> None:
        """Updates external indexing progress to reflect the current job state.

        This method sends the latest processed count and total operation count
        for the active job to the indexing status tracker, if a job is running.
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

        This method resets the total operation count, current job type,
        and processed-operation counter so that subsequent jobs start
        with a clean progress state.
        """
        self._total_for_current_job = None
        self._current_job_status = None
        self._processed_count = 0

    def _handle_database_error(
        self, conn: sqlite3.Connection, event: IndexEvent, error: sqlite3.Error
    ) -> None:
        """Handles database errors that occur during event processing.

        This method logs the original database error, rolls back the current transaction,
        and attempts a SQLite integrity check to detect corruption, logging a secondary
        error if the integrity check itself fails.

        Args:
            conn (sqlite3.Connection): The database connection on which the error occurred.
            event (IndexEvent): The indexing event being processed when the error was raised.
            error (sqlite3.Error): The database error that triggered this handler.
        """
        self._logger.error(
            f"Database error during {event.type}: {error}", exc_info=True
        )
        conn.rollback()
        try:
            conn.execute("PRAGMA integrity_check;")
        except Exception as check_error:
            self._logger.error(f"Database integrity check failed: {check_error}")

    def _shutdown_writer(self, conn: sqlite3.Connection) -> None:
        """Finalizes the writer loop by committing pending work and checkpointing the WAL.

        This method attempts a final commit and WAL checkpoint when the writer thread
        is shutting down, logging either a successful shutdown message or an error
        if any exception occurs.

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
        """Indexes a single music file into the tracks database.

        This method reads tag metadata and file attributes, builds a normalized metadata
        tuple, and inserts or updates the corresponding track record so that the
        database reflects the current state of the file on disk. If the file is
        missing or a database error occurs, it logs the issue and either skips
        indexing or propagates the error.

        Args:
            conn (sqlite3.Connection): An open SQLite connection used to write track metadata.
            path (Path): The absolute filesystem path of the music file to index.

        Raises:
            sqlite3.Error: If the insert or update operation fails at the database layer.
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
        """Reads tag metadata from a music file if possible.

        This method attempts to load tag and duration information for the given file,
        returning None and logging a warning if the file cannot be read or parsed.

        Args:
            path (Path): The absolute filesystem path to the music file whose tags should be read.

        Returns:
            TinyTag | None: A TinyTag instance containing parsed metadata, or None if reading fails.
        """
        try:
            return TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            self._logger.warning(f"Failed to read tags from {path}: {e}")
            return None

    def _extract_metadata(self, tag: TinyTag | None, path: Path) -> tuple:
        """Builds a normalized metadata tuple for a music file.

        This method derives database-ready values from tag information and file attributes,
        applying sensible defaults and fallbacks so that each track has a consistent
        representation even when some tags are missing or incomplete.

        Args:
            tag (TinyTag | None): Parsed tag metadata for the file, or None if metadata could not be read.
            path (Path): The absolute filesystem path of the music file.

        Returns:
            tuple: A tuple containing all track fields in the order expected by the tracks table schema.
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
        """Parses a four-digit year value from tag metadata if available.

        This method reads the year attribute from the tag, converts it to a string,
        and returns the first four characters as an integer, or None if the year
        field is missing or cannot be parsed.

        Args:
            tag (TinyTag | None): A TinyTag instance containing metadata for a music file, or None.

        Returns:
            int | None: The parsed four-digit year, or None if it is not present or invalid.
        """
        try:
            if getattr(tag, "year", None):
                return int(str(tag.year)[:4])
        except (AttributeError, ValueError):
            pass
        return None

    def _parse_number(self, value: str | None) -> int | None:
        """Parses a numeric value from a tag field string.

        This method extracts the leading integer from values that may be in formats like
        "3" or "3/12", returning None if the value is missing or not parseable.

        Args:
            value (str | None): A string representation of a numeric tag value, possibly including a total (e.g., "3/12"), or None.

        Returns:
            int | None: The leading integer parsed from the value, or None if it is empty or invalid.
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

        This method walks the directory tree rooted at the music folder, collects paths
        to files with supported audio extensions, and periodically updates indexing
        progress to reflect how many files have been discovered for the given job type.

        Args:
            job_type (str): A label for the current indexing job, such as "rebuilding" or "resyncing".

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

        This method compares the filesystem under the music root with the paths stored
        in the database, then schedules additions and removals so that the index
        reflects the actual contents of the collection.

        Returns:
            None
        """
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
        """Scans the music root for supported files and returns their relative paths.

        This method walks the filesystem tree under the music root, collects the relative
        database paths of all files with supported extensions, and periodically updates
        resync progress as files are discovered.

        Returns:
            set[str]: A set of POSIX-style relative paths for all supported music files found.
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

        This method materializes delete and index iterables, initializes or skips job
        tracking based on whether there is any work to do, and delegates the actual
        queuing and completion handling of operations to internal helpers.

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
        """Initializes tracking state for a rebuild or resync job.

        This method resets internal counters, records the job type and total operations,
        and updates the external indexing status to reflect a new job starting.

        Args:
            job_type: The type of indexing job being started (e.g., "rebuilding" or "resyncing").
            total_operations: The total number of delete and index operations expected for the job.
        """
        self._processed_count = 0
        self._total_for_current_job = total_operations
        self._current_job_status = job_type
        set_indexing_status(self.data_root, job_type, total=total_operations, current=0)

    def _queue_operations(
        self, delete_list: list[str], index_list: list[Path], job_type: str
    ) -> None:
        """Enqueues database operations for a batch of delete and index tasks.

        This method converts relative delete paths and absolute index paths into queue
        events and appends a final completion event indicating whether the batch belongs
        to a rebuild or resync job.

        Args:
            delete_list (list[str]): Relative paths of tracks to remove from the database.
            index_list (list[Path]): Absolute paths of tracks to index or reindex.
            job_type (str): The type of job these operations belong to, such as "rebuilding" or "resyncing".
        """
        for rel_path in delete_list:
            self._write_queue.put(IndexEvent("DELETE_FILE", Path(rel_path)))

        for abs_path in index_list:
            self._write_queue.put(IndexEvent("INDEX_FILE", abs_path))

        done_event = "REBUILD_DONE" if job_type == "rebuilding" else "RESYNC_DONE"
        self._write_queue.put(IndexEvent(done_event))

    def _wait_for_job_completion(self, job_type: str, total_operations: int) -> None:
        """Waits for all queued operations in the current job to finish.

        This method blocks until the writer queue is drained, then clears indexing status
        and logs a summary of the completed job.

        Args:
            job_type (str): The type of indexing job that is being waited on.
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
        and returns a string suitable for storage in the database.

        Args:
            path (Path): The absolute filesystem path to convert.

        Returns:
            str: The relative POSIX-style path under the music root.
        """
        return path.resolve().relative_to(self.music_root).as_posix()

    def _to_abspath(self, relpath: str) -> Path:
        """Converts a stored relative music path into an absolute filesystem path.

        This method joins the configured music root with the given relative path
        and normalizes it into a Path object for file system operations.

        Args:
            relpath (str): The POSIX-style relative path under the music root.

        Returns:
            Path: The absolute path pointing to the file within the music root.
        """
        return self.music_root / Path(relpath)

    # === Monitoring ===

    def start_monitoring(self) -> None:
        """Starts monitoring the music root directory for file system changes.

        This method initializes a watchdog observer, attaches a watcher for the music root,
        and begins observing so that file events can be translated into indexing operations.

        Returns:
            None
        """
        if self._observer:
            return
        self._observer = Observer()
        self._observer.schedule(_Watcher(self), str(self.music_root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stops background indexing activity and shuts down monitoring.

        This method signals the writer thread to stop, waits briefly for it to terminate,
        and then stops and joins the filesystem observer if monitoring is active.

        Returns:
            None
        """
        self._writer_stop.set()
        self._writer_thread.join(timeout=5)
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def wait_for_indexing_start(self, timeout: float = 5.0) -> bool:
        """Waits until indexing has started or the timeout elapses.

        This method blocks until the internal indexing-start event is set,
        allowing callers to synchronize with the beginning of a rebuild or resync operation.

        Args:
            timeout (float): The maximum number of seconds to wait for indexing to start.

        Returns:
            bool: True if indexing started before the timeout, or False if the timeout expired first.
        """
        return self._initial_status_event.wait(timeout=timeout)


# =========================
# File system watcher
# =========================


class _Watcher(FileSystemEventHandler):
    """Handles file system events for the music collection."""

    def __init__(self, extractor: CollectionExtractor) -> None:
        """Initializes the watcher with a collection extractor to handle file events.

        This constructor stores a reference to the extractor so that relevant filesystem
        events can be translated into indexing operations for the music collection.

        Args:
            extractor (CollectionExtractor): The collection extractor that processes
                index and delete events for music files.
        """
        self.extractor = extractor

    def on_any_event(self, event: object) -> None:
        """Handles any file system event affecting the music collection.

        This method filters out directory changes and non-audio files, then enqueues
        index or delete events so that file creations, modifications, and deletions
        are reflected in the collection index.

        Args:
            event (object): A watchdog-style file system event with ``is_directory``,
                ``src_path``, and ``event_type`` attributes.
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
