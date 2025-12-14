import sqlite3
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Optional

from tinytag import TinyTag
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from logtools import get_logger

from .indexing_status import clear_indexing_status, set_indexing_status

logger = get_logger(__name__)


class CollectionExtractor:
    """Manages extraction and synchronization of music metadata from a file system.

    Handles scanning, indexing, and monitoring of a music collection, storing metadata in a SQLite database for efficient access and updates.
    """

    SUPPORTED_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}

    def __init__(self, music_root: Path, db_path: Path):
        """Initializes a CollectionExtractor for managing a music library.

        Sets up the music root directory, database path, and prepares the database schema for storing music metadata.

        Args:
            music_root (Path): The root directory containing music files.
            db_path (Path): Path to the SQLite database file.
        """
        self.music_root = music_root.resolve()
        self.data_root = Path(db_path).parent
        self.db_path = db_path
        if not self.db_path.exists():
            logger.warning(
                f"Database file {self.db_path} does not exist and will be created."
            )
        else:
            logger.info(f"Using existing database at {self.db_path}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Related to background indexing and monitoring
        self._stop_event = Event()
        self._observer: Observer | None = None
        self._observer_lock = Lock()
        self._observer_paused = False
        self._observer_pause_lock = Lock()

        # Queue and thread for processing filesystem events
        self._event_queue: Queue = Queue()
        self._worker_thread: Optional[Thread] = None
        self._worker_thread = Thread(target=self._process_queue, daemon=True)
        self._ensure_schema()
        self._start_worker()


    # --- Monitoring and Worker Management ---

    def start_monitoring(self) -> None:
        """Starts live monitoring of the music directory for file system changes.

        Sets up a file system observer to watch for changes in the music collection and updates the database in real time.

        Returns:
            None
        """
        with self._observer_lock:
            if self._observer is not None:
                if self._observer.is_alive():
                    logger.debug(
                        "Filesystem monitoring already active; skipping restart."
                    )
                    return
                else:
                    logger.warning(
                        "Found stopped filesystem observer; restarting."
                    )
                    with suppress(Exception):
                        self._observer.stop()
                        self._observer.join(timeout=5.0)
                    self._observer = None

            if not self.music_root.exists():
                logger.warning(
                    f"Music root {self.music_root} does not exist - skipping filesystem monitoring"
                )
                return

            self._observer = Observer()
            self._observer.schedule(
                Watcher(self),
                str(self.music_root),
                recursive=True
            )
            self._observer.start()
            logger.info("Live filesystem monitoring started")

    def pause_monitoring(self) -> None:
        """Pauses live monitoring of the music directory for file system changes.

        Temporarily disables the file system observer, preventing updates to the database until monitoring is resumed.

        Returns:
            None
        """
        with self._observer_pause_lock:
            self._observer_paused = True
            logger.info("Filesystem monitoring paused")

    def resume_monitoring(self) -> None:
        """Resumes live monitoring of the music directory for file system changes.

        Re-enables the file system observer, allowing updates to the database to continue after being paused.

        Returns:
            None
        """
        with self._observer_pause_lock:
            self._observer_paused = False
            logger.info("Filesystem monitoring resumed")

    def stop_monitoring(self) -> None:
        """
        Stops live monitoring of the music directory and background worker thread.

        Shuts down the file system observer and the background metadata worker if they are running,
        releasing associated resources and logging the shutdown.

        Returns:
            None
        """
        with self._observer_lock:
            if self._observer is not None:
                with suppress(Exception):
                    self._observer.stop()
                    self._observer.join(timeout=5.0)
                self._observer = None
                logger.info("Filesystem monitoring stopped")

        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
            logger.info("Background metadata worker stopped")

    def _start_worker(self) -> None:
        """
        Starts the background worker thread for processing filesystem events.

        Initializes and starts a daemon thread that processes the event queue for metadata extraction and database updates.
        """
        self._worker_thread.start()
        if getattr(self, "_background_task_running", False):
            return
        self._background_task_running = True

        def indexing_task():
            try:
                if getattr(self, "_needs_initial_index", False):
                    self._run_background_rebuild()
                elif getattr(self, "_needs_resync", False):
                    self._run_background_resync()
                clear_indexing_status(self.data_root)  # Clear status after completion
                logger.info("Background indexing complete.")
            except Exception as e:
                logger.error(f"Background indexing failed: {e}")
                clear_indexing_status(self.data_root)  # Clear on error too
            finally:
                self._background_task_running = False

        Thread(target=indexing_task, daemon=True).start()

    def _process_queue(self) -> None:
        """Processes the event queue for file system changes and indexes supported files.

        Continuously retrieves file system events from the queue, checks if the file extension is supported,
        and enqueues the file for indexing until stopped.

        Returns:
            None
        """
        while not self._stop_event.is_set():
            try:
                event = self._event_queue.get(timeout=1)
            except Empty:
                continue
            path = Path(event.src_path)

            if path.suffix.lower() in self.SUPPORTED_EXTS:
                self._enqueue_index_file(path)

            self._event_queue.task_done()

    # --- Database and Schema Management ---

    def get_conn(self) -> sqlite3.Connection:
        """Creates and returns a new SQLite database connection.

        Opens a connection to the music collection database and sets the row factory for named access. Returns the connection object for use in database operations.

        Returns:
            sqlite3.Connection: A connection object to the music collection database.
        """
        conn = sqlite3.connect(
            self.db_path, timeout=30.0
        )  # Increase timeout further as backup
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _ensure_schema(self) -> None:
        """Ensures the database schema for the music collection exists.

        Creates the tracks table and necessary indexes if they do not already exist in the database. Adds the mtime column for sync checking if it is missing.

        Returns:
            None
        """
        with self.get_conn() as conn:
            conn.execute("""
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
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_album  ON tracks(album  COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_title  ON tracks(title  COLLATE NOCASE)"
            )

            # Add mtime column if not exists (for sync checking)
            with suppress(sqlite3.OperationalError):
                conn.execute("ALTER TABLE tracks ADD COLUMN mtime REAL")

    def count_tracks(self) -> int:
        """Returns the total number of tracks in the music collection.

        Counts and returns the number of track records currently stored in the database.

        Returns:
            int: The total number of tracks in the collection.
        """
        with self.get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    # --- Indexing and Synchronization ---

    def rebuild(self) -> None:
        """Performs a full rebuild of the music collection database.

        Scans the music directory for all supported files, clears the existing database, indexes all found tracks, and restarts monitoring after completion.

        Returns:
            None
        """
        logger.info(
            "Full rebuild started - This could take a while for large collections..."
        )
        with self.rebuild_context():
            set_indexing_status(
                data_root=self.data_root,
                status="rebuilding",
                total=0,
                current=0,
            )
            start = time.time()
            files = [
                p
                for p in self.music_root.rglob("*")
                if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
            ]
            logger.info(f"→ {len(files):,} music files found. Start indexing...")
            with self.get_conn() as conn:
                self._clear_tracks_table(conn)
                count = self._index_files_for_rebuild(files)
                conn.commit()

        clear_indexing_status(data_root=self.data_root)
        logger.info(
            f"Full rebuild complete: {count:,} tracks in {time.time() - start:.1f}s"
        )

    def resync(self) -> None:
        """Synchronizes the database with the current state of the file system.

        Compares the database records with the files present in the music directory, adding new files and removing records for deleted files.
        Logs the number of tracks added and removed.

        Returns:
            None
        """
        start = time.time()
        db_paths = self._get_db_paths()
        fs_paths = self._get_fs_paths()

        to_add = fs_paths - db_paths
        to_remove = db_paths - fs_paths

        self._remove_missing_tracks(to_remove)
        self._add_new_tracks(to_add)

        added = len(to_add)
        removed = len(to_remove)
        logger.info(
            f"Sync complete: +{added:,} / -{removed:,} tracks ({time.time() - start:.1f}s)"
        )

    def is_synced_with_filesystem(self, sample_size: int = 200) -> bool:
        """Checks if the database is in sync with the file system.

        Randomly samples tracks from the database and verifies that each file exists and its modification time matches the stored value.
        Returns True if all sampled files are in sync, otherwise False.

        Args:
            sample_size (int): The number of tracks to sample for sync checking.

        Returns:
            bool: True if the sampled files are in sync with the database, False otherwise.
        """
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT path, mtime FROM tracks ORDER BY RANDOM() LIMIT ?",
                (sample_size,),
            ).fetchall()
            for row in rows:
                path = Path(row["path"])
                if not path.exists():
                    return False
                if row["mtime"] is None or path.stat().st_mtime != row["mtime"]:
                    return False
        return True

    def _run_background_rebuild(self):
        """
        Runs a full rebuild of the music collection in the background.

        Triggers the status update, performs the rebuild, and updates the internal state.
        """
        logger.info("Starting background full rebuild...")
        self._trigger_status("rebuilding")
        self._extractor.rebuild()
        self._needs_initial_index = False

    def _run_background_resync(self) -> None:
        """
        Runs a resynchronization of the music collection in the background.

        Triggers the status update, performs the resync, and updates the internal state.
        """
        logger.info("Starting background resync...")
        self._trigger_status("resyncing")
        self._extractor.resync()
        self._needs_resync = False

    def _trigger_status(self, status: str):
        """
        Triggers the indexing status update.

        Sets the initial status in the JSON file before starting indexing.
        """
        set_indexing_status(data_root=self.data_root, status=status, total=0, current=0)

    # --- File Indexing Helpers ---

    def _index_file_direct(self, path: Path) -> None:
        """Indexes a single music file directly and updates the database with its metadata.

        Extracts metadata from the given file and inserts or updates the corresponding record in the tracks table.
        If metadata extraction fails, the file is still processed with available information.

        Args:
            path (Path): The path to the music file to index.

        Returns:
            None
        """
        tag = self._get_tag_for_path(path)
        artist = self._extract_artist(tag, path)
        album = self._extract_album(tag, path)
        title = self._extract_title(tag, path)
        year = self._safe_int_year(getattr(tag, "year", None))
        duration = getattr(tag, "duration", None)
        albumartist = getattr(tag, "albumartist", None)
        genre = getattr(tag, "genre", None)
        mtime = path.stat().st_mtime

        values = (
            str(path),
            path.name,
            artist,
            album,
            title,
            albumartist,
            genre,
            year,
            duration,
            mtime,
        )

        self._insert_track_record(values)

    def _get_tag_for_path(self, path: Path):
        """Attempts to extract tags from a file, returning None on failure."""
        try:
            return TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            logger.warning(f"Failed to extract tags from {path}: {e}")
            return None

    def _insert_track_record(self, values: tuple):
        """Inserts or replaces a track record in the database."""
        conn = self.get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tracks
                (path, filename, artist, album, title, albumartist, genre, year, duration, mtime)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            conn.commit()
        finally:
            conn.close()

    def _index_file_path_queued(self, path: Path) -> None:
        """
        Indexes a music file and updates the database with its metadata.

        Extracts metadata from the given file and inserts or updates the corresponding record in the tracks table.
        If metadata extraction fails, the file is skipped.

        Args:
            path: The path to the music file to index.

        Returns:
            None
        """
        tag = None
        try:
            tag = TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            logger.warning(f"Failed to extract tags from {path}: {e}")

        artist = self._extract_artist(tag, path)
        album = self._extract_album(tag, path)
        title = self._extract_title(tag, path)
        year = self._safe_int_year(getattr(tag, "year", None))
        duration = getattr(tag, "duration", None)
        albumartist = getattr(tag, "albumartist", None)
        genre = getattr(tag, "genre", None)
        mtime = path.stat().st_mtime

        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tracks
                (path, filename, artist, album, title, albumartist, genre, year, duration, mtime)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    str(path),
                    path.name,
                    artist,
                    album,
                    title,
                    albumartist,
                    genre,
                    year,
                    duration,
                    mtime,
                ),
            )
            conn.commit()

    def _index_file(self, conn: Optional[sqlite3.Connection], path: Path) -> None:

        if conn is None:
            conn = self.get_conn()
            should_close = True
        else:
            should_close = False
        tag = None
        try:
            tag = TinyTag.get(path, tags=True, duration=True)
        except Exception as e:
            logger.warning(
                f"Failed to extract tags from {path}: {type(e).__name__}: {e}",
                exc_info=True,
            )

        artist = self._extract_artist(tag, path)
        album = self._extract_album(tag, path)
        title = self._extract_title(tag, path)
        year = self._safe_int_year(getattr(tag, "year", None))
        duration = getattr(tag, "duration", None)
        albumartist = getattr(tag, "albumartist", None)
        genre = getattr(tag, "genre", None)
        mtime = path.stat().st_mtime

        conn.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, filename, artist, album, title, albumartist, genre, year, duration, mtime)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
            (
                str(path),
                path.name,
                artist,
                album,
                title,
                albumartist,
                genre,
                year,
                duration,
                mtime,
            ),
        )
        if should_close:
            conn.commit()
            conn.close()

    # --- Synchronization Helpers ---

    def _get_db_paths(self) -> set:
        """
        Returns a set of all file paths currently in the database.

        Queries the tracks table and collects all stored file paths for synchronization purposes.

        Returns:
            set: A set of file path strings present in the database.
        """
        with self.get_conn() as conn:
            return {row["path"] for row in conn.execute("SELECT path FROM tracks")}

    def _get_fs_paths(self) -> set:
        """
        Returns a set of all supported file paths currently in the filesystem.

        Scans the music root directory for files with supported extensions and collects their paths for synchronization.

        Returns:
            set: A set of file path strings present in the filesystem.
        """
        return {
            str(p)
            for p in self.music_root.rglob("*")
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
        }

    def _remove_missing_tracks(self, to_remove: set) -> None:
        """
        Removes tracks from the database that no longer exist in the filesystem.

        Deletes records from the tracks table for each file path in the to_remove set.

        Args:
            to_remove: A set of file path strings to remove from the database.

        Returns:
            None
        """
        if not to_remove:
            return
        with self.get_conn() as conn:
            conn.executemany(
                "DELETE FROM tracks WHERE path = ?", [(p,) for p in to_remove]
            )
            conn.commit()

    def _add_new_tracks(self, to_add: set) -> None:
        """
        Adds new tracks from the filesystem to the database.

        Indexes each file path in the to_add set and inserts its metadata into the database. Logs a warning if indexing fails for any file.

        Args:
            to_add: A set of file path strings to add to the database.

        Returns:
            None
        """
        logger.info("Adding newly found tracks...")
        set_indexing_status(
            data_root=self.data_root, status="rebuilding", total=0, current=0
        )
        if not to_add:
            return
        with self.get_conn() as conn:
            for i, path_str in enumerate(to_add):
                try:
                    self._index_file(conn=conn, path=Path(path_str))
                except Exception as e:
                    logger.warning(f"Failed to index {path_str}: {e}")
                if i % 200 == 0:  # update every 200 files
                    set_indexing_status(
                        data_root=self.data_root,
                        status="rebuilding",
                        total=len(to_add),
                        current=i,
                    )
            conn.commit()
            clear_indexing_status()

    def _clear_tracks_table(self, conn: sqlite3.Connection) -> None:
        """
        Removes all existing track records from the database.

        Executes a SQL command to delete all rows from the tracks table, preparing the database for a full rebuild.

        Args:
            conn: The SQLite database connection.

        Returns:
            None
        """
        conn.execute("DELETE FROM tracks")

    def _index_files_for_rebuild(self, files: list[Path]) -> int:
        """
        Indexes all files for the rebuild process and returns the count of indexed tracks.

        Iterates through the provided files, indexing supported music files and updating progress status.
        Logs progress at regular intervals and returns the total count of indexed tracks.

        Args:
            conn: The SQLite database connection.
            files: A list of Path objects representing files to index.

        Returns:
            int: The total number of tracks indexed.
        """
        count = 0
        conn = self.get_conn()
        total_files = len(files)
        for i, path_file in enumerate(files):
            indexed = self._try_index_file(conn, path_file)
            count += indexed
            if count % 5000 == 0:
                logger.info(f"Indexed {count:,} tracks...")
            if i % 100 == 0:
                self._update_rebuild_status(total_files, i)
        conn.commit()
        conn.close()
        return count

    def _try_index_file(self, conn: sqlite3.Connection, path_file: Path) -> int:
        """Attempts to index a single file and logs any exception.

        Tries to index the given file using the provided database connection. Returns 1 if successful, or 0 if an exception occurs.

        Args:
            conn (sqlite3.Connection): The SQLite database connection.
            path_file (Path): The path to the music file to index.

        Returns:
            int: 1 if indexing succeeded, 0 otherwise.
        """
        try:
            self._index_file(conn=conn, path=path_file)
            return 1
        except Exception as e:
            logger.warning(f"Skip {path_file}: {e}")
            return 0

    def _update_rebuild_status(self, total: int, current: int) -> None:
        """Updates the indexing status during a rebuild."""
        set_indexing_status(
            data_root=self.data_root,
            status="rebuilding",
            total=total,
            current=current,
        )

    # --- Metadata Extraction Helpers ---

    def _safe_int_year(self, value) -> int | None:
        """Converts a value to an integer year if possible.

        Attempts to extract and return a valid integer year from the input value. Returns None if the value cannot be interpreted as a year.

        Args:
            value: The value to convert to an integer year.

        Returns:
            int or None: The extracted year as an integer, or None if conversion is not possible.
        """
        if not value:
            return None
        try:
            return int(str(value).strip().split("-", 1)[0].split(".", 1)[0])
        except ValueError:
            return None

    def _extract_artist(self, tag: object, path: Path) -> str:
        """Extracts the artist name from tag or path.

        Returns the artist name as a string, using tag metadata or directory names as fallback. If no artist is found, returns 'Unknown'.

        Args:
            tag: The metadata tag object from TinyTag.
            path: The path to the music file.

        Returns:
            str: The extracted artist name.
        """
        artist = getattr(tag, "artist", None) or getattr(tag, "albumartist", None)
        if not artist and len(path.parents) >= 3:
            artist = path.parent.parent.name
        return (artist or "Unknown").strip()

    def _extract_album(self, tag: object, path: Path) -> str:
        """Extracts the album name from tag or path.

        Returns the album name as a string, using tag metadata or directory names as fallback. If no album is found, returns 'Unknown'.

        Args:
            tag: The metadata tag object from TinyTag.
            path: The path to the music file.

        Returns:
            str: The extracted album name.
        """
        # Configurable set of ignored directory names for album extraction fallback
        ignored_album_dirs = getattr(self, "ignored_album_dirs", {"", ".", "..", "Music", "music"})
        album = getattr(tag, "album", None)
        if not album:
            album = path.parent.name
            # Expand fallback to use configurable set, allowing for localization/customization
            if album in ignored_album_dirs and len(path.parents) >= 3:
                album = path.parent.parent.name
        return (album or "Unknown").strip()

    def _extract_title(self, tag: object, path: Path) -> str:
        """
        Extracts the track title from tag or path.

        Returns the track title as a string, using tag metadata or the file stem as fallback. If no title is found, returns 'Unknown'.

        Args:
            tag: The metadata tag object from TinyTag.
            path: The path to the music file.

        Returns:
            str: The extracted track title.
        """
        return (getattr(tag, "title", None) or path.stem or "Unknown").strip()

    # --- Context Managers ---
    @contextmanager
    def rebuild_context(self):
        """Context manager for safely rebuilding the music collection database.

        Pauses live monitoring during the rebuild process and ensures monitoring is resumed after completion, even if an error occurs.

        Yields:
            None
        """
        logger.info("Entering rebuild context")
        self.pause_monitoring()

        try:
            yield
        finally:
            self.resume_monitoring()
            logger.info("Exiting rebuild context")


class Watcher(FileSystemEventHandler):
    """Handles file system events for the music collection and updates the database.

    Monitors file changes in the music directory and synchronizes the music database by adding, updating, or removing track records as needed.
    """

    def __init__(self, extractor: CollectionExtractor):
        """Initializes a Watcher to handle file system events for a music collection.

        Associates the watcher with a CollectionExtractor instance to synchronize the database with file changes.

        Args:
            extractor: The CollectionExtractor instance to monitor and update.
        """
        self.extractor = extractor
        super().__init__()


    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handles any file system event and queues it for processing.

        Checks if monitoring is paused and, if not, adds the event to the extractor's event queue for further handling.

        Args:
            event (FileSystemEvent): The file system event to handle.

        Returns:
            None
        """
        if self.extractor._observer_paused:
            return

        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() in self.extractor.SUPPORTED_EXTS:
            # Index directly on the watchdog thread — it's safe and simple
            self.extractor._index_file_direct(path)
