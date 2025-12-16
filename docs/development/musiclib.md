# Music Collection handling

![Musiclib](../images/music-library.png){ align=right width="90" }

The `musiclib` module provides the `MusicCollection` class, which serves as a high-level interface for managing and querying a local music library. It abstracts the complexities of synchronizing a music collection stored on the filesystem with a backing SQLite database, providing search, indexing, and live monitoring capabilities. The class is designed to be used as the main entry point for applications or services that need to interact with a user's music library, offering methods for searching artists, albums, and tracks, as well as for maintaining the integrity and synchronization of the library.

Creating/maintaining the music collection database

```mermaid
sequenceDiagram
    actor User
    participant FlaskApp
    participant MusicCollection
    participant CollectionExtractor
    participant WriterThread
    participant IndexingStatus
    participant SQLiteDB as SQLite_DB

    User->>FlaskApp: create MusicCollection(music_root, db_path)
    FlaskApp->>MusicCollection: __init__
    MusicCollection->>CollectionExtractor: __init__(music_root, db_path)
    CollectionExtractor->>CollectionExtractor: _init_db()
    CollectionExtractor->>WriterThread: start sqlite-writer
    MusicCollection->>MusicCollection: count()
    MusicCollection->>CollectionExtractor: get_conn(readonly=True)
    CollectionExtractor-->>MusicCollection: Connection
    MusicCollection->>SQLiteDB: SELECT COUNT(*) FROM tracks
    SQLiteDB-->>MusicCollection: track_count
    alt track_count == 0
        MusicCollection->>MusicCollection: _startup_mode = rebuild
    else track_count > 0
        MusicCollection->>MusicCollection: _startup_mode = resync
    end

    MusicCollection->>CollectionExtractor: start_monitoring()
    MusicCollection->>MusicCollection: _start_background_startup_job()
    MusicCollection->>MusicCollection: spawn background Thread

    par BackgroundThread
        MusicCollection->>CollectionExtractor: rebuild() or resync()
        alt rebuild
            CollectionExtractor->>IndexingStatus: set_indexing_status(data_root, rebuilding, total, 0)
            CollectionExtractor->>WriterThread: enqueue CLEAR_DB
            loop for each file
                CollectionExtractor->>WriterThread: enqueue INDEX_FILE(path)
                CollectionExtractor->>IndexingStatus: set_indexing_status(... current)
            end
            CollectionExtractor->>WriterThread: enqueue REBUILD_DONE
        else resync
            CollectionExtractor->>IndexingStatus: set_indexing_status(data_root, resyncing, total, 0)
            loop removed paths
                CollectionExtractor->>WriterThread: enqueue DELETE_FILE(path)
                CollectionExtractor->>IndexingStatus: set_indexing_status(... current)
            end
            loop new paths
                CollectionExtractor->>WriterThread: enqueue INDEX_FILE(path)
                CollectionExtractor->>IndexingStatus: set_indexing_status(... current)
            end
            CollectionExtractor->>WriterThread: enqueue RESYNC_DONE
        end

        WriterThread->>SQLiteDB: apply queued operations
        WriterThread->>SQLiteDB: COMMIT on *_DONE
        WriterThread-->>CollectionExtractor: done
        CollectionExtractor->>IndexingStatus: clear_indexing_status(data_root)
    end
```

Real-time file system monitoring and database update

```mermaid
sequenceDiagram
    participant FS as FileSystem
    participant Observer
    participant Watcher as _Watcher
    participant CollectionExtractor
    participant WriterThread
    participant SQLiteDB as SQLite_DB

    FS-->>Observer: file created/modified/deleted
    Observer-->>Watcher: on_any_event(event)

    Watcher->>Watcher: ignore if directory or unsupported extension
    alt supported file
        alt event == created or modified
            Watcher->>CollectionExtractor: _write_queue.put(INDEX_FILE, path)
        else event == deleted
            Watcher->>CollectionExtractor: _write_queue.put(DELETE_FILE, path)
        end
    end

    loop in sqlite-writer thread
        WriterThread->>CollectionExtractor: get IndexEvent from _write_queue
        alt INDEX_FILE
            WriterThread->>CollectionExtractor: _index_file(conn, path)
            CollectionExtractor->>SQLiteDB: INSERT OR REPLACE INTO tracks(...)
        else DELETE_FILE
            WriterThread->>SQLiteDB: DELETE FROM tracks WHERE path = path
        else CLEAR_DB
            WriterThread->>SQLiteDB: DELETE FROM tracks
        end
        WriterThread->>SQLiteDB: periodic COMMIT
    end
```

## Key Components

* **`MusicCollection` Class**: Manages the music library, initialized with paths to music directories. It loads music files, extracts metadata, and provides methods for searching and retrieving tracks. Responsibilities include:
    * **Search Methods**
        * `search_highlighting(query, limit)`: Returns UI-friendly, highlighted search results for artists, albums, and tracks matching the query.
        * `search_grouped(query, limit)`: Returns grouped search results (artists, albums, tracks) as dictionaries, suitable for further processing or display.
        * Internal helper methods (`_search_artists`, `_search_albums`, `_search_tracks`, etc.) perform efficient, case-insensitive SQL queries and structure the results.
    * **Result Formatting**:
    Several private methods (`_format_artist_results`, `_format_album_results`, `_format_track_results`, etc.) process and format search results for UI consumption, including text highlighting and reason annotation.
    * **Utility Methods**:
        * `highlight_text`: Highlights occurrences of the search query in result strings.
        * `_format_relative_path`, `_format_duration`, `_safe_filename`: Helpers for formatting file paths, durations, and filenames for display or download.
    * **Maintenance & Lifecycle**:
        * `rebuild()`: Forces a full reindex of the music library.
        * `close()`: Stops background monitoring.
        * Context manager support (`__enter__`, `__exit__`) and destructor (`__del__`) ensure resources are cleaned up properly.
* **`CollectionExtractor` Class**:  Central class for managing the extraction, indexing, and synchronization of music metadata from the file system to a SQLite database. Responsibilities include:
    * Initializes and ensures the database schema.
    * Scans the music directory and indexes supported music files.
    * Extracts metadata (artist, album, title, year, duration, etc.) using the TinyTag library.
    * Provides methods for counting tracks, checking sync status, resyncing, and rebuilding the index.
    * Supports live monitoring of the music directory using the watchdog library.
* **`Watcher` Class**:  Handles file system events and updates the music database in response to changes. Responsibilities include:
    * Listens for file creation, modification, movement, and deletion events in the music directory.
    * Updates the database by adding, updating, or removing track records as needed.
    * Uses watchdog to observe changes in the music directory and trigger database updates in real time.

## Class diagrams

```mermaid
classDiagram
    class MusicCollection {
        -music_root: Path
        -db_path: Path
        -_extractor: CollectionExtractor
        -_startup_mode: str
        -_background_task_running: bool
        +MusicCollection(music_root: Path|str, db_path: Path|str)
        +rebuild() None
        +resync() None
        +close() None
        +count() int
        +search_grouped(query: str, limit: int) dict~str, list~dict~~~~
        +search_highlighting(query: str, limit: int) list~dict~
        -_start_background_startup_job() None
        -_get_conn() Connection
        -_search_artists(conn: Connection, starts: str, limit: int) list~dict~
        -_search_artist_albums(conn: Connection, artist: str, logger) list~dict~
        -_search_album_tracks(conn: Connection, artist: str, album: str) list~dict~
        -_search_albums(conn: Connection, like: str, starts: str, limit: int, artists: list~dict~) list~dict~
        -_search_tracks(conn: Connection, like: str, starts: str, limit: int, artists: list~dict~, albums: list~dict~) list~dict~
        -_relative_path(path: str) str
        -_format_duration(seconds: float|None) str
    }

    class CollectionExtractor {
        +SUPPORTED_EXTS: set~str~
        -music_root: Path
        -db_path: Path
        -data_root: Path
        -_write_queue: Queue~IndexEvent~
        -_writer_stop: Event
        -_writer_thread: Thread
        -_observer: Observer
        +CollectionExtractor(music_root: Path, db_path: Path)
        +get_conn(readonly: bool) sqlite3.Connection
        +rebuild() None
        +resync() None
        +start_monitoring() None
        +stop() None
        -_init_db() None
        -_db_writer_loop() None
        -_index_file(conn: sqlite3.Connection, path: Path) None
    }

    class IndexEvent {
        +type: EventType
        +path: Path
    }

    class _Watcher {
        -extractor: CollectionExtractor
        +_Watcher(extractor: CollectionExtractor)
        +on_any_event(event: object) None
    }

    class indexing_status_module {
        +set_indexing_status(data_root: Path|str, status: str, total: int, current: int) None
        +clear_indexing_status(data_root: Path|str) None
        +get_indexing_status(data_root: Path|str) dict
        -_atomic_write_json(status_file: Path, data: dict) None
        -_calculate_progress(total: int, current: int) float
        -_get_started_at(status_file: Path) str
        -_build_status_data(status: str, started_at: str, total: int, current: int, progress: float) dict
    }

    class MixtapeManager {
        -path_mixtapes: Path
        +delete(slug: str) None
        +list_all() list~dict~
        +save(mixtape_data: dict) str
    }

    class EventType {
    }

    MusicCollection --> CollectionExtractor : uses
    MusicCollection --> "1" indexing_status_module : uses
    CollectionExtractor --> IndexEvent : enqueues
    CollectionExtractor --> _Watcher : creates
    _Watcher --> CollectionExtractor : notifies
    CollectionExtractor --> indexing_status_module : reports_progress
    MixtapeManager <.. browse_mixtapes_route : used_by
    IndexEvent --> EventType : type
```

## API

### ::: src.musiclib.reader.MusicCollection

### ::: src.musiclib._extractor.EventType

### ::: src.musiclib._extractor.IndexEvent

### ::: src.musiclib._extractor.CollectionExtractor

### ::: src.musiclib.indexing_status

### ::: src.musiclib._extractor._Watcher
