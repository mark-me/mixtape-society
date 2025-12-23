![Musiclib](../images/music-library.png){ align=right width="90" }

# 🎵 Musiclib - Music Collection handling

## Overview and introduction

The musiclib package is the heart of the mixtape music‑collection service.
It turns a plain directory tree of audio files into a searchable, fully‑indexed library that can be queried instantly from the UI.

Below is a concise, high‑level walkthrough of the module’s responsibilities, its main components, and how they interact to deliver a robust “scan‑once‑search‑forever” experience.

---

### 1. What the module does

| Goal                         | How it’s achieved                                                                                                                                                     |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Detect every supported audio file | A **watchdog observer** monitors the `music_root` directory in real time.                                                                                             |
| Extract reliable metadata    | `tinytag.TinyTag` reads ID3/metadata tags (artist, album, title, year, duration, etc.).                                                                            |
| Persist metadata efficiently | A **SQLite** database stores the canonical rows (`tracks` table) and an **FTS5** virtual table (`tracks_fts`) that mirrors the same columns for lightning‑fast full‑text search. |
| Keep the DB in sync          | A **single writer thread** serialises all write operations (adds, deletes, clears) via a thread‑safe `Queue[IndexEvent]`.                                             |
| Expose progress to the UI    | A tiny JSON file (`indexing_status.json`) is updated atomically during long‑running operations (rebuild, resync) so the front‑end can render progress bars.            |
| Provide a clean API for the UI | `MusicCollection` (in `reader.py`) builds the search expression, runs the query, groups results by release directory, and returns a ready‑to‑render structure (artists, albums, tracks) together with the list of terms that need highlighting. |

---

### 2. Core building blocks

| Module / Class          | Primary responsibility                                                                                                                                                                                                 |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`_extractor.py`**      | • Low‑level DB schema creation (`_init_db`). <br>• Full‑text table bootstrap (`_populate_fts_if_needed`). <br>• **`CollectionExtractor`** – orchestrates indexing, resync, rebuild, and live monitoring. <br>• **`IndexEvent` / `EventType`** – typed messages that drive the writer thread. <br>• **`_Watcher`** – translates filesystem events into `IndexEvent`s. |
| **`indexing_status.py`**| Helper functions that write/read the `indexing_status.json` file in an atomic, crash‑safe way (e.g., `set_indexing_status`, `clear_indexing_status`, `get_indexing_status`).                                                     |
| **`reader.py`**          | High‑level façade (**`MusicCollection`**) used by the UI. It parses user queries, builds the FTS/LIKE expression, runs the query, groups rows, and formats the result payload (artists, albums, tracks, and highlight terms).          |
| **`ui.py`**              | Extends `MusicCollection` with UI‑specific helpers: <br>• `_highlight_text` (term highlighting) <br>• `_safe_filename` (sanitising filenames) <br>• `_escape_for_query` (building click‑query strings) <br>• result shaping for the front‑end. |

---

### 3. Data flow – from file system to UI

1. **Startup** – `MusicCollection` creates a `CollectionExtractor`. The extractor initializes the SQLite schema and launches the writer thread.
1. **Initial population** – If the DB is empty, `MusicCollection` schedules a rebuild. The rebuild walks the entire `music_root`, enqueues an `INDEX_FILE` event for every supported file, and updates `indexing_status.json` so the UI can show progress.
1. **Live updates** – The `watchdog` observer fires on every create/modify/delete. `_Watcher` converts those into `IndexEvent`s, which the writer thread processes in order, keeping the DB and the FTS mirror perfectly aligned.
1. **Search** – When the UI calls `search_highlighting`, `MusicCollection` parses the query, builds an FTS‑compatible expression (or a fallback `LIKE` query), runs it against the DB, groups rows by release directory, and returns a dictionary of artists, albums, and tracks plus the list of parsed terms.
1. **Presentation** – `MusicCollectionUI` highlights the terms, builds click‑queries (`artist:…`, `release_dir:…`), and hands the ready‑to‑render JSON back to the front‑end. Lazy‑loading of an artist’s full discography or an album’s track list is done by re‑issuing `search_grouped` with the stored click‑query.

---

### 4. Why the design choices matter

| Design decision                                 | Benefit                                                                                                                                                              |
|-------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Single writer thread + queue**                | Guarantees deterministic ordering of DB writes, avoids SQLite lock contention, and lets the UI stay responsive while heavy indexing runs in the background.            |
| **FTS5 virtual table with triggers**            | Provides sub‑millisecond full‑text look‑ups without having to maintain a separate index manually.                                                                    |
| **Atomic JSON status file**                     | Prevents corrupted progress information even if the process crashes mid‑write; the UI never sees a half‑written file.                                                  |
| **Watchdog‑driven live sync**                   | Users see newly added songs appear instantly; deletions are reflected without a full rescan.                                                                         |
| **Separation of concerns** (`_extractor` vs. `reader` vs. `ui`) | Keeps low‑level DB handling isolated from query parsing and UI formatting, making the code easier to test and extend.                                                |
| **Typed `IndexEvent` dataclass**                | Improves readability, reduces bugs caused by mismatched queue payloads, and makes future event types straightforward to add.                                          |

---

### 5. Quick mental model

```mermaid
flowchart LR
    %% Nodes
    FS[Filesystem<br/>audio files]
    WD[Watchdog<br/>Observer]
    Q[IndexEvent Queue]
    WT[Writer Thread<br/>processes events]
    DB[SQLite DB<br/>*tracks + tracks_fts*]
    UI[MusicCollection<br>UI layer]

    %% Main data flow
    FS --> WD
    WD --> Q
    Q --> WT
    WT --> DB

    %% Queries from UI
    UI --> DB
    DB --> UI
```

*The arrow direction indicates the primary flow of data.*

The UI never talks directly to the filesystem; it always goes through MusicCollection, which in turn reads from the already‑indexed SQLite store.

---

### 6. Getting started (for developers)

1. Instantiate the high‑level class:

    ```python
    from musiclib.reader import MusicCollection
    mc = MusicCollection(music_root="/path/to/music", db_path="/path/to/db.sqlite")
    ```

2. Run a query (the UI does this internally):

    ```python
    results, terms = mc.search_grouped("artist:'Radiohead' love")
    ```

3. Monitor progress (useful for CLI tools):

    ```python
    from musiclib.indexing_status import get_indexing_status
    status = get_indexing_status("/path/to/db_folder")
    print(status)   # → {'status': 'rebuilding', 'progress': 0.42, …}
    ```

4. Shut down cleanly when the program exits:

    ```python
    mc.close()   # stops the writer thread and the watchdog observer
    ```

---

### 7. Where to look next

* `_extractor.py` – for the low‑level DB schema, triggers, and the writer‑loop logic.
* `reader.py` – for the query parser (`parse_query`) and the grouping algorithm that decides which artists/albums/tracks to return.
* `ui.py` – for the presentation helpers (highlighting, safe filenames, click‑query generation).
* `indexing_status.py` – for the atomic JSON status handling used by the UI progress bar.

That’s the complete picture of the `musiclib` module: a tightly coupled pipeline that turns a folder of audio files into a fast, searchable, and continuously synchronized music library.

---

## Searching the music collection

The `musiclib` module has the `ui.py` and `reader.py` files which provide methods for searching artists, albums, and tracks.

### 1. Query Language (handled in `MusicCollection.parse_query`)

| Element | Syntax | What it does |
|---------|--------|--------------|
| **Artist tag** | `artist:<value>` | Limits the search to a specific artist. `<value>` may be quoted (`"The Beatles"`), single‑quoted, or unquoted. |
| **Album tag** | `album:<value>` | Limits the search to a specific album (or release directory). |
| **Track/song tag** | `song:<value>` or `track:<value>` | Limits the search to a specific track title. |
| **General terms** | Anything not preceded by a tag | Treated as free‑text that is searched across *artist*, *album* and *title* fields. |
| **Quoting / escaping** | `"double‑quoted"` or `'single‑quoted'` – backslashes can escape characters inside the quotes. | Allows spaces or special characters inside a tag value. |

The parser returns a dictionary:

```python
{
    "artist": [...],
    "album":  [...],
    "track":  [...],
    "general": [...]
}
```

These lists are later used to build the actual search expression.

---

### 2. Building the Search Expression (`MusicCollection.search_grouped`)

1. **Full‑text‑search (FTS) path**

    If the SQLite database contains a virtual table `tracks_fts`, the code uses it.
    Otherwise it falls back to plain `LIKE` queries.

2. **Tag‑specific parts**

    For each tag (`artist`, `album`, `track`) the code creates a sub‑expression:
    * Multi‑word values become an **AND** of wildcard tokens (`word*`).
    * Multiple values for the same tag are combined with **OR**.

    Example: `artist:"The Beatles"` → `artist:(The* AND Beatles*)`.

3. **General terms**

    All free‑text terms are turned into a wildcard token (`term*`) and then searched in any of the three fields (`artist`, `album`, `title`). They are combined with OR.

4. **Combining tag groups**
    * If at least one explicit tag is present → the different tag groups are joined with **AND** (result must satisfy every specified tag).
    * If there are no explicit tags → everything is joined with **OR**, acting like a pure free‑text search.

5. **Final expression**

    The resulting string is passed to the FTS `MATCH` clause (or translated into a series of `LIKE` predicates).

6. **Result buffering**

    The query fetches `limit * 3` rows (the extra factor gives room for later grouping and deduplication).

---

### 3. Grouping & post‑processing (still in `search_grouped`)

After the raw rows are retrieved:

| Step | What happens |
|------|--------------|
| **Release‑directory grouping** | Rows are bucketed by the directory that contains the track (`_get_release_dir`). This groups together all tracks belonging to the same album/release. |
| **Artist aggregation** | A set of distinct artists appearing in the matched rows is collected. |
| **Compilation detection** | If a release contains tracks from more than three different artists, it is marked as a *compilation* and displayed as “Various Artists”. |
| **Sorting** | Releases are sorted alphabetically by album name; artists are sorted alphabetically as well. |
| **Conditional inclusion** | Depending on whether the original query contained explicit tags, the method decides which sections to return: <br> • `include_artists` – true if an `artist:` tag was supplied **or** the query had no tags. <br> • `include_albums` – analogous for `album:`. <br> • `include_tracks` – analogous for `track:`. |
| **Deduplication for tagged searches** | When a tag is present, the code tries to avoid showing the same information twice (e.g., an album that already appears under an artist will be omitted from the album list). |
| **Final payload** | Returns a tuple: <br> 1️⃣ A dictionary with three top‑level keys (`artists`, `albums`, `tracks`) each holding a list of dictionaries ready for UI consumption. <br> 2️⃣ The `terms` dictionary (the parsed tag values) that the UI uses for highlighting. |

---

### 4. UI layer – turning raw groups into a searchable result list (`MusicCollectionUI.search_highlighting`)

1. **Highlighting**

    `_highlight_text` receives a string and the full list of search terms (artist, album, track, and general).
    It builds a case‑insensitive regular expression that wraps each occurrence in `<mark>…</mark>`.

2. **Result construction**

    The UI builds three kinds of result objects, each matching the shape expected by the front‑end:

    a. Artist entries

    ```json
    {
        "type": "artist",
        "artist": "<highlighted name>",
        "reasons": [{ "type": "...", "text": "…" }, …],
        "albums": [],               // empty – loaded lazily
        "load_on_demand": true,
        "clickable": true,
        "click_query": "artist:'Exact Name'"
    }
    ```

    * Counts of matching albums and tracks are fetched on‑the‑fly (extra SQL queries).
    * The click_query is a ready‑to‑use query string that the UI can send back to retrieve the artist’s detailed view.

    b. Album entries

    ```json
    {
        "type": "album",
        "artist": "<highlighted artist>",
        "album": "<highlighted album>",
        "reasons": [{…}],
        "tracks": [],               // empty – loaded lazily
        "load_on_demand": true,
        "is_compilation": true/false,
        "clickable": true,
        "click_query": "release_dir:'dir/path'",
        "artist_click_query": "artist:'Exact Artist'"   // omitted for compilations
    }
    ```

    * The UI also runs a small count query to know how many tracks within that release match the original term.

    c. Track entries (fully materialised)

    ```json
    {
        "type": "track",
        "artist": "<highlighted artist>",
        "album": "<highlighted album>",
        "reasons": [{
            "type": "track",
            "text": "Track Title"
            }],
        "tracks": [ {
            "title": "Track Title",
            "duration": "3:45",
            "path": "...",
            "filename": "…"
            } ],
        "highlighted_tracks": [{
            "original": {...},
            "highlighted": "...",
            "match_type": "track"
            }],
        "artist_click_query": "artist:'Exact Artist'",
        "album_click_query": "album:'Exact Album'"
    }
    ```

3. **Lazy‑loading strategy**

    * **Artists** and **Albums** are returned without their child lists (`albums` or `tracks`). The front‑end can request the detailed view later using the generated `click_query`.
    * **Tracks** are returned fully because they are already the leaf nodes of the result hierarchy.

4. **Safe filename generation**

    `_safe_filename` strips unsafe characters from a track title before appending the original file extension – useful when the UI offers a download or “save as” feature.

5. **Query escaping**

    `_escape_for_query` makes sure that generated query strings are correctly quoted, handling embedded single‑quotes by switching to double‑quotes and escaping them.

---

### 5. Summary of the search options offered to a user

| Option                | How you trigger it                                                                                     | What it does                                                                                                                                                     |
|-----------------------|--------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Free‑text search**  | Any string **without** `artist:`, `album:` or `song:` tags                                            | Searches across all three fields (artist, album, title) using wildcards.                                                                                         |
| **Artist filter**     | `artist:<name>` (quotes allowed)                                                                      | Restricts results to that artist; still returns matching albums and tracks.                                                                                       |
| **Album filter**      | `album:<name>`                                                                                         | Restricts results to that album (or release directory).                                                                                                          |
| **Track filter**      | `song:<name>` or `track:<name>`                                                                       | Restricts results to tracks whose title matches the term.                                                                                                         |
| **Combined filters**  | Mix any of the above, e.g. `artist:"Radiohead" album:"OK Computer"`                                   | Results must satisfy **all** specified tags (AND semantics).                                                                                                      |
| **Multi‑word values** | Quoted strings (`"The Dark Side of the Moon"`)                                                       | Each word becomes a mandatory wildcard (`The* AND Dark* AND Side* …`).                                                                                            |
| **Escaping**          | Backslash before a special character (`\:`) inside a quoted value                                    | Allows literal colons, quotes, etc., inside a tag value.                                                                                                         |
| **Result highlighting** | Automatic – the UI wraps any matched term in `<mark>` tags                                           | Highlights matching terms in the displayed results.                                                                                                               |
| **Lazy loading**      | Clicking an artist or album entry sends the stored `click_query` back to the server                    | The server then calls `get_artist_details` or `get_album_details` to fetch the full track list on demand.                                                        |
| **Compilation detection** | Implicit – if a release contains tracks from **> 3** distinct artists                                 | The release is shown as “Various Artists”.                                                                                                                       |
| **Count hints**       | For each artist/album entry the UI runs extra count queries                                            | Shows how many matching albums/tracks were found for that artist or album, giving the user quick insight into the size of the result set.                           |

All of these options are driven by the same core pipeline:

1. Parse the user query → tag lists + general terms.
2. Build an FTS (or LIKE) expression that respects tag‑specific AND/OR logic.
3. Execute the query, fetch a buffered set of rows.
4. Group rows by release directory, detect compilations, and decide which sections (artist/album/track) to include.
5. Return structured data that the UI decorates with highlights and lazy‑load hooks.

---

### End‑to‑end flow of a search request

```mermaid
sequenceDiagram
    participant UI as Front‑end (MusicCollectionUI)
    participant MC as MusicCollection (backend)
    participant DB as SQLite DB (tracks / tracks_fts)

    %% 1. User issues a search
    UI->>UI: receive query string (e.g. `artist:"Radiohead" love`)
    UI->>MC: search_highlighting(query, limit)

    %% 2. Parse the query
    MC->>MC: parse_query(query)
    Note right of MC: Produces tags {artist, album, track, general}

    %% 3. Build FTS / LIKE expression
    MC->>MC: build search expression
    alt FTS table exists
        MC->>DB: SELECT … FROM tracks_fts MATCH <expr>
    else No FTS
        MC->>DB: SELECT … FROM tracks WHERE LIKE …
    end

    %% 4. Retrieve raw rows (buffered)
    DB-->>MC: rows (limit*3)

    %% 5. Group rows by release directory
    MC->>MC: _get_release_dir() → group rows
    MC->>MC: detect compilations (>3 artists)
    MC->>MC: sort releases & artists alphabetically

    %% 6. Decide which sections to include
    MC->>MC: evaluate include_artists / include_albums / include_tracks
    MC->>MC: deduplicate overlapping items

    %% 7. Return grouped data + parsed terms
    MC-->>UI: ({artists, albums, tracks}, terms)

    %% 8. Highlight terms in UI
    UI->>UI: _highlight_text() on each field
    UI->>UI: build result objects (artist, album, track)

    %% 9. Render results
    UI-->>User: JSON/HTML with <mark> highlights
    Note right of UI: Artists & albums have `click_query` for lazy loading

    %% 10. Lazy‑load on demand (optional)
    User->>UI: click on artist or album
    UI->>MC: search_grouped(click_query, limit)
    MC->>DB: (same flow as steps 3‑6)
    DB-->>MC: rows
    MC-->>UI: detailed artist/album data
    UI-->>User: expanded view with full track list
```

---

### API Searching

#### ::: src.musiclib.reader.MusicCollection

## Creating/maintaining the music collection database

### 1. High‑level picture

```
File system (music_root) ──► Watchdog events ──► IndexEvent queue ──► DB‑writer thread ──► SQLite DB (tracks + tracks_fts)
```

* **Watchdog** watches the music directory for creations, modifications, and deletions.
* Detected changes are turned into **IndexEvent** objects and placed on a thread‑safe `Queue`.
* A dedicated **writer thread** (`_db_writer_loop`) consumes those events and performs the actual SQLite writes.
* The database consists of a normal `tracks` table (metadata) and an FTS5 virtual table `tracks_fts` that mirrors the metadata for fast full‑text search.
* Helper functions in `indexing_status.py` keep a tiny JSON status file (`indexing_status.json`) that the UI can poll to show progress during a **rebuild** or **resync** operation.

### Core data structures

| Name                 | Type                                             | Purpose                                                                                                                                                     |
|----------------------|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `IndexEvent`         | `@dataclass` with fields `type: EventType` and `path: Optional[Path]` | Represents a single action for the writer thread (index a file, delete a file, clear DB, signal rebuild/resync completion).                                   |
| `EventType`          | `Literal["INDEX_FILE", "DELETE_FILE", "CLEAR_DB", "REBUILD_DONE", "RESYNC_DONE"]` | Enumerates the possible actions.                                                                                                                            |
| `_write_queue`       | `queue.Queue[IndexEvent]`                        | Thread‑safe hand‑off from the watcher / public methods to the writer thread.                                                                               |
| `_writer_stop`       | `threading.Event`                               | Signals the writer thread to shut down cleanly.                                                                                                              |
| `tracks` table       | SQLite table with columns `path, filename, artist, album, title, albumartist, genre, year, duration, mtime` | Stores the canonical metadata for each audio file.                                                                                                          |
| `tracks_fts`         | SQLite FTS5 virtual table mirroring most columns of `tracks` | Enables fast full‑text search across artist, album, title, etc.

### 3. Database initialization (`_init_db`)

1. Opens a temporary connection (`sqlite3.connect(self.db_path)`).
2. Sets WAL journal mode and normal sync for better concurrency.
3. Creates the tracks `table` if it does not exist.
4. Creates three case‑insensitive indexes on `artist`, `album`, and `title`.
5. Creates the FTS5 virtual table `tracks_fts` with a Unicode tokenizer that removes diacritics.
6. Installs three triggers (`tracks_ai`, `tracks_ad`, `tracks_au`) that keep `tracks_fts` in sync with inserts, deletes, and updates on `tracks`.

Result: the DB is ready for both ordinary queries and full‑text search without any manual maintenance.

### 4. Full‑text table boot‑strap (`_populate_fts_if_needed`)

* Opens a read‑only connection.
* Checks `SELECT count(*) FROM tracks_fts`.
* If the count is zero, executes a single `INSERT … SELECT` that copies every row from `tracks` into `tracks_fts`.
* Commits the transaction.

This routine is called once after a fresh DB creation or after a manual purge of the FTS table.

### 5. Public connection helper (`get_conn`)

* Read‑only mode (`readonly=True`) uses the URI `file:<path>?mode=ro`.
* Write mode opens a normal connection.
* Both connections set `row_factory = sqlite3.Row` so callers can treat rows like dictionaries.

All higher‑level code (search, UI, etc.) obtains connections via this method.

### 6. Writer thread (`_db_writer_loop`)

* Runs forever until _writer_stop is set.
* Pulls an IndexEvent from _write_queue with a 0.5 s timeout (so it can notice the stop flag).
* Handles each event type:

    | Event type      | Action performed                                                                                                                   |
    |-----------------|------------------------------------------------------------------------------------------------------------------------------------|
    | `CLEAR_DB`      | `DELETE FROM tracks` (removes all rows).                                                                                          |
    | `INDEX_FILE`    | Calls `_index_file(conn, path)` – extracts metadata and `INSERT OR REPLACE` into `tracks`.                                          |
    | `DELETE_FILE`   | `DELETE FROM tracks WHERE path = ?`.                                                                                               |
    | `REBUILD_DONE` / `RESYNC_DONE` | `conn.commit()` – flushes any pending changes.                                                                          |

* After every 500 processed events it forces a commit to keep the transaction size reasonable.
* Errors are caught and logged via the injected Logger.
* When the loop exits, it commits any remaining work and closes the connection.

### 7. Metadata extraction (`_index_file`)

1. Calls TinyTag.get(path, tags=True, duration=True).
2. Safely extracts the following fields (fallbacks shown in parentheses):

    | Field   | Source                              | Fallback |
    |---------|-------------------------------------|----------|
    | `artist`| `tag.artist` → `tag.albumartist`   | `"Unknown"` |
    | `album` | `tag.album`                         | `"Unknown"` |
    | `title` | `tag.title` → `path.stem`          | `"Unknown"` |
    | `year`  | `int(str(tag.year)[:4])` (if parsable) | `None` |
    | `duration`| `tag.duration`                     | `None` |
    | `mtime` | `path.stat().st_mtime`              | – |

3. Executes a single INSERT OR REPLACE INTO tracks (…) VALUES (…) with the gathered values.
4. Because of the triggers defined in _init_db, the same row is automatically mirrored into tracks_fts.

---

### 8. Full rebuild (rebuild)

* **Purpose** – create a fresh DB from the current file system state.
* Steps:
    1. Write status rebuilding with `total = -1` (unknown) and `current = 0`.
    2. Enqueue a `CLEAR_DB` event (empties the DB).
    3. Recursively walk `music_root` (`rglob("*")`) and collect every file whose suffix is in `SUPPORTED_EXTS`.
    4. Update the status file with the exact `total` count.
    5. For each discovered file, enqueue `INDEX_FILE` events. Every 100 files the status file is refreshed (`set_indexing_status`).
    6. After the loop, enqueue `REBUILD_DONE` and call `join()` on the queue (wait until the writer thread finishes processing).
    7. Remove the status file (`clear_indexing_status`).

* The UI can poll `indexing_status.json` to display a progress bar that reflects the `total`/`current`/`progress` fields.

---

### 9. Incremental resynchronisation (resync)

* **Purpose** – bring the DB up‑to‑date after files have been added, removed, or renamed since the last run.
* Steps:
    1. Set status `resyncing` with unknown totals (`total = -1`).
    1. Build a set of absolute paths for all supported files currently on disk (`fs_paths`).
    1. Query the DB for all stored paths (`db_paths`).
    1. Compute `to_add = fs_paths - db_paths` and `to_remove = db_paths - fs_paths`.
    1. `total = len(to_add) + len(to_remove)` and update the status file.
    1. Enqueue `DELETE_FILE` events for each path in `to_remove`; every 100 deletions the status file is refreshed.
    1. Enqueue `INDEX_FILE` events for each path in `to_add`; every 100 additions the status file is refreshed.
    1. Enqueue `RESYNC_DONE`, clear the status file, and log a summary.

* As with `rebuild`, the writer thread processes the queued events sequentially, guaranteeing that the DB ends up exactly matching the file system.

---

### 10. Real‑time monitoring (`start_monitoring` / `_Watcher`)

* **`start_monitoring`** creates a `watchdog.observers.Observer` (if none exists), registers a `_Watcher` instance for the `music_root`, and starts the observer thread.

* **`_Watcher`** inherits from `FileSystemEventHandler`. Its `on_any_event` method:
    1. Ignores directory events.
    1. Filters out files whose extensions are not in `SUPPORTED_EXTS`.
    1. For `created` or `modified` events → enqueues `INDEX_FILE`.
    1. For `deleted` events → enqueues `DELETE_FILE`.

* This mechanism guarantees that any change made while the application is running is eventually reflected in the DB (subject to the writer thread’s batching policy).

---

### 11. Graceful shutdown (stop)

* Sets the `_writer_stop` flag, joins the writer thread (max 5 seconds).
* Stops and joins the watchdog observer if it was started.
* After this call the extractor is fully stopped and the SQLite connection is closed.

---

### 12. Indexing‑status helper (`indexing_status.py`)

| Function                                   | Role                                                                                                                                                                                                 |
|--------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `set_indexing_status(data_root, status, total, current)` | Computes progress (`current/total`), preserves the original `started_at` timestamp (or creates a new one), builds a dictionary with `status, started_at, updated_at, total, current, progress`, and writes it atomically to `indexing_status.json`. |
| `_atomic_write_json(status_file, data)`   | Writes JSON to a temporary file in the same directory, flushes, `fsync`s, then atomically renames the temp file onto the target. Guarantees that a partially‑written file never appears.                     |
| `_calculate_progress(total, current)`      | Returns a float in `[0.0, 1.0]`; guards against division by zero or negative totals.                                                                                                                  |
| `_get_started_at(status_file)`             | Reads the existing JSON (if any) and returns the original `started_at` value, allowing a rebuild/resync to keep the same start‑time across restarts.                                                    |
| `_build_status_data(...)`                  | Packages all fields into a plain dict ready for JSON serialization.                                                                                                                                 |
| `clear_indexing_status(data_root)`         | Deletes the JSON file if it exists.                                                                                                                                                                      |
| `get_indexing_status(data_root, logger=None)` | Reads and parses the JSON file, returning the dict or `None` on missing/corrupt files. Logs JSON decode errors via the supplied logger (defaults to `NullLogger`).                                        |

These utilities are deliberately lightweight: they operate purely on the filesystem and do not depend on the SQLite connection, making them safe to call from any thread (including the writer thread).

---

### 13. End‑to‑end flow for a typical user session

```mermaid
sequenceDiagram
    participant User as End‑User (UI)
    participant LUI as Lumo UI / Front‑end
    participant MC as MusicCollection (high‑level class)
    participant EX as CollectionExtractor
    participant DB as SQLite DB (tracks + tracks_fts)
    participant FS as File System (music_root)
    participant WS as Watchdog Observer
    participant Q as IndexEvent Queue
    participant WT as Writer Thread
    participant IS as indexing_status.json

    %% 1. Application start
    User->>LUI: Open application
    LUI->>MC: Instantiate MusicCollection(root, db)
    MC->>EX: Create CollectionExtractor
    EX->>EX: _init_db()           # create tables, triggers, indexes
    EX->>WT: Start writer thread (_db_writer_loop)
    EX->>WS: start_monitoring()
    WS->>EX: Register _Watcher

    %% 2. First launch – maybe empty DB
    MC->>MC: count() → 0?
    alt DB empty
        MC->>MC: schedule background rebuild
        MC->>EX: rebuild() (queued)
    else DB has data
        MC->>MC: schedule background resync (optional)
    end

    %% 3. Background rebuild (runs in writer thread)
    Note over EX,WT: Rebuild workflow
    EX->>Q: put(CLEAR_DB)
    EX->>FS: Walk music_root for supported files
    FS-->>EX: list of file paths
    EX->>Q: put(INDEX_FILE, path) for each file
    loop every 100 files
        EX->>IS: set_indexing_status(..., total, current)
    end
    EX->>Q: put(REBUILD_DONE)
    Q->>WT: consume events sequentially
    WT->>DB: DELETE FROM tracks          # CLEAR_DB
    loop for each INDEX_FILE event
        WT->>EX: _index_file(conn, path)
        EX->>DB: INSERT OR REPLACE INTO tracks (...)
        Note right of DB: Triggers auto‑mirror into tracks_fts
    end
    WT->>DB: COMMIT                      # REBUILD_DONE
    WT->>Q: task_done() (all events processed)
    Q->>EX: join()                       # wait for queue empty
    EX->>IS: clear_indexing_status()
    Note over IS: status file removed

    %% 4. UI polls progress (while rebuilding)
    loop while rebuilding
        LUI->>IS: read indexing_status.json
        IS-->>LUI: {status, progress, …}
        LUI->>LUI: update progress bar
    end

    %% 5. Normal operation – live updates
    WS->>FS: detects file created/modified/deleted
    WS->>EX: on_any_event(event)
    alt created or modified
        EX->>Q: put(INDEX_FILE, path)
    else deleted
        EX->>Q: put(DELETE_FILE, path)
    end
    Q->>WT: writer thread processes new events
    alt INDEX_FILE
        WT->>EX: _index_file(conn, path)
        EX->>DB: INSERT OR REPLACE INTO tracks (...)
    else DELETE_FILE
        WT->>DB: DELETE FROM tracks WHERE path = ?
    end
    WT->>DB: periodic COMMIT (every 500 events)

    %% 6. User initiates a search (no DB write)
    User->>LUI: type query & press Search
    LUI->>MC: search_highlighting(query, limit)
    MC->>EX: search_grouped(query, limit)
    EX->>DB: SELECT … (FTS MATCH or LIKE)
    DB-->>EX: rows
    EX->>EX: group by release_dir, detect compilations, sort, apply include_* logic
    EX-->>MC: ({artists, albums, tracks}, terms)
    MC->>LUI: results with <mark> highlights & click_query strings

    %% 7. User clicks an artist or album (lazy load)
    User->>LUI: click on artist/album entry
    LUI->>MC: search_grouped(click_query, limit)
    MC->>EX: same path as step 6 (but query is specific)
    EX->>DB: SELECT detailed rows for that artist/album
    DB-->>EX: detailed rows
    EX-->>MC: detailed dic
```

---

## Class diagram

```mermaid
classDiagram
    %% ==== Core data types ====
    class IndexEvent {
        <<dataclass>>
        +EventType type
        +Path? path
    }

    class EventType {
        <<enumeration>>
        INDEX_FILE
        DELETE_FILE
        CLEAR_DB
        REBUILD_DONE
        RESYNC_DONE
    }

    %% ==== CollectionExtractor (main engine) ====
    class CollectionExtractor {
        -Path music_root
        -Path db_path
        -Path data_root
        -Logger _logger
        -Queue[IndexEvent] _write_queue
        -Event _writer_stop
        -Observer? _observer
        -Thread _writer_thread
        -set SUPPORTED_EXTS
        +CollectionExtractor(music_root, db_path, logger=None)
        +rebuild()
        +resync()
        +start_monitoring()
        +stop()
        +get_conn(readonly=False) Connection
        -_init_db()
        -_populate_fts_if_needed()
        -_db_writer_loop()
        -_index_file(conn, path)
        -_write_queue.put(event)
    }

    %% ==== _Watcher (filesystem event handler) ====
    class _Watcher {
        -CollectionExtractor extractor
        +_Watcher(extractor)
        +on_any_event(event)
    }

    %% ==== Indexing status helpers (module-level functions) ====
    class indexing_status {
        <<module>>
        +set_indexing_status(data_root, status, total, current)
        +clear_indexing_status(data_root)
        +get_indexing_status(data_root, logger=None)
        -_atomic_write_json(status_file, data)
        -_calculate_progress(total, current) float
        -_get_started_at(status_file) str|None
        -_build_status_data(status, started_at, total, current, progress) dict
    }

    %% ==== Relationships ====
    CollectionExtractor --> IndexEvent : produces / consumes
    CollectionExtractor --> EventType : uses literals
    CollectionExtractor --> _Watcher : creates & registers
    CollectionExtractor --> indexing_status : writes progress JSON
    _Watcher --> IndexEvent : enqueues events
    _Watcher --> CollectionExtractor : holds reference
    indexing_status ..> Path : works with filesystem paths
```

## API extractor/loader

### ::: src.musiclib._extractor.EventType

### ::: src.musiclib._extractor.IndexEvent

### ::: src.musiclib._extractor.CollectionExtractor

### ::: src.musiclib.indexing_status

### ::: src.musiclib._extractor._Watcher
