![Reading](../../images/musiclib_reading.png){ align=right width="90" }

# Searching the music collection

The music collection supports a flexible, tag-based search language that can return **artists, albums, and tracks** in a single request.
Search results are **grouped, scored, highlighted**, and designed for **lazy navigation** via follow-up queries.

Searching is implemented in two layers:

* **Core search engine** – `MusicCollection.search_grouped(...)` (in `reader.py`)
* **UI-facing API** – `MusicCollectionUI.search_highlighting(...)` (in `ui.py`)

Most applications should call the UI-facing method.

---

## 🚀 Entry points

### UI-facing search (recommended)

```python
results = mc_ui.search_highlighting(query, limit=30)
```

Returns a **single list of result objects**, ready for rendering in a UI.
Each result object has a `type` field (`artist`, `album`, or `track`) and includes highlighted text and navigation metadata.

### Core grouped search (lower-level)

```python
grouped, terms = mc.search_grouped(query, limit=20)
```

Returns:

1. A dictionary with three lists: `artists`, `albums`, `tracks`
2. The parsed search terms, grouped by category

This method is primarily used internally by the UI layer.

---

## 🔎 Query language

The query parser recognizes **tagged terms** and **general free-text terms**.

### Supported tags

| Tag                | Example                  | Meaning                               |
| ------------------ | ------------------------ | ------------------------------------- |
| `artist:`          | `artist:Prince`          | Restrict results to a specific artist |
| `album:`           | `album:"Purple Rain"`    | Restrict results to a specific album  |
| `track:` / `song:` | `track:"When Doves Cry"` | Restrict results to track titles      |

### Free-text terms

Any term **not** prefixed by a tag is treated as free-text and matched against:

* artist
* album
* track title

Example:

```text
love
```

### Quoting and escaping

* Single or double quotes allow multi-word values

  ```yaml
  artist:"The Beatles"
  album:'Purple Rain'
  ```

* Backslashes can escape special characters inside quoted values

---

## ⚙️ Parsed term structure

The query is normalized into a dictionary:

```python
{
    "artist":  [...],
    "album":   [...],
    "track":   [...],
    "general": [...]
}
```

This structure is returned alongside the search results and reused for:

* scoring
* highlighting
* UI explanation ("why did this match?")

---

## ⚡ Search execution model

### Pass-one candidate collection

The search engine performs a **first pass** to collect candidates:

* Artists are scored by how well they match artist terms
* Albums are scored by album name and artist context
* Tracks are scored by title and tag matches

The engine may **reuse candidates from the previous search session** if the new query is a refinement (e.g. clicking an artist).

### Scoring (simplified)

Matches are weighted using:

* Exact matches
* Prefix matches
* Substring matches
* Tag bonuses (explicit `artist:`, `album:`, `track:`)

This produces ranked candidate sets for artists, albums, and tracks.

### Performance optimization

To minimize database overhead, the search engine batches related queries:

* Album counts for all matched artists are fetched in a single query
* Track counts for all matched albums are fetched in a single query
* Compilation status for all matched albums is checked in a single query

This reduces the number of database round trips from O(n+m) to O(1), where n is the number of artists and m is the number of albums.

---

## 🏘️ Result grouping and hierarchy

After scoring, results are assembled into a hierarchical structure:

* Artists
* Albums
* Tracks

The engine decides which groups to include based on the query:

| Query type        | Included sections               |
| ----------------- | ------------------------------- |
| Free-text only    | Artists, albums, and tracks     |
| `artist:` present | Artists + related albums/tracks |
| `album:` present  | Albums + tracks                 |
| `track:` present  | Tracks only                     |

---

## 🎯 UI result model

The UI layer converts grouped results into a **single flat list** of result objects via the function `search_highlighting`.

Each object has a `type` field and a shape appropriate for rendering.

### Artist results

```json
{
  "type": "artist",
  "artist": "<mark>Prince</mark>",
  "raw_artist": "Prince",
  "reasons": [
    { "type": "album", "text": "3 album(s)" },
    { "type": "track", "text": "12 nummer(s)" }
  ],
  "load_on_demand": true,
  "clickable": true,
  "click_query": "artist:'Prince'"
}
```

**Characteristics:**

* Summary only (no albums or tracks included)
* Always lazy-loaded
* Clicking triggers a new search using `click_query`

---

### Album results

```json
{
  "type": "album",
  "artist": "Prince",
  "album": "<mark>Purple Rain</mark>",
  "is_compilation": false,
  "cover": "covers/prince_purplerain.jpg",
  "reasons": [
    { "type": "track", "text": "5 nummer(s)" }
  ],
  "load_on_demand": true,
  "clickable": true,
  "click_query": "release_dir:'/Prince/Purple Rain'"
}
```

**Characteristics:**

* Summary only
* Tracks are loaded on demand
* Albums with tracks by more than three artists are shown as **"Various Artists"**
* Includes `cover` field with relative URL to cached cover image

---

### Track results

```json
{
  "type": "track",
  "artist": "Prince",
  "album": "Purple Rain",
  "track": "<mark>When Doves Cry</mark>",
  "duration": "5:54",
  "path": "Prince/Purple Rain/01 - When Doves Cry.flac",
  "cover": "covers/prince_purplerain.jpg",
  "artist_click_query": "artist:'Prince'",
  "album_click_query": "album:'Purple Rain'"
}
```

**Characteristics:**

* Fully populated (no lazy loading)
* Includes navigation queries for artist and album
* Includes `cover` field with relative URL to cached cover image

---

## 🖼️ Cover art management

The music collection provides automatic cover art extraction, caching, and serving with support for **size-optimized variants** for responsive clients like Android Auto.

### Basic cover retrieval

```python
# Get cover URL for a release directory
cover_url = mc.get_cover("Artist/Album")
# Returns: "covers/artist_album.jpg" or "covers/_fallback.jpg"
```

**Behavior:**

* Searches for common cover image files (`cover.jpg`, `folder.jpg`, etc.)
* Extracts embedded artwork from audio files if no standalone image found
* Optimizes images to max 800×800px, 85% quality, ≤500KB
* Caches extracted covers in `DATA_ROOT/cache/covers/`
* Returns fallback image if no cover found

### Size-optimized cover variants

For bandwidth-conscious applications (mobile, Android Auto), request specific sizes:

```python
# Get multiple size variants
cover_sizes = mc.get_cover_sizes("Artist/Album")
# Returns:
# {
#   "96x96": "covers/artist_album_96x96.jpg",
#   "128x128": "covers/artist_album_128x128.jpg",
#   "192x192": "covers/artist_album_192x192.jpg",
#   "256x256": "covers/artist_album_256x256.jpg",
#   "384x384": "covers/artist_album_384x384.jpg",
#   "512x512": "covers/artist_album_512x512.jpg"
# }
```

**Behavior:**

* Generates size variants on-demand (lazy generation)
* Caches variants permanently for future requests
* Falls back to main cover if variant generation fails
* Returns fallback URLs for all sizes if no cover found

**Standard sizes:**

| Size | Use case | Typical file size |
| ---- | -------- | ----------------- |
| 96×96 | Thumbnails, lists | 5-8 KB |
| 128×128 | Small tiles | 8-12 KB |
| 192×192 | Medium tiles | 15-20 KB |
| 256×256 | Android Auto (optimal) | 30-50 KB |
| 384×384 | High-DPI displays | 60-90 KB |
| 512×512 | Full-screen player | 100-150 KB |

### Flask API endpoints

Two routes are available for serving cover images:

**Direct file serving (existing):**

```text
GET /covers/<filename>
```

Serves cached cover files directly. Used by existing UI code.

**Size-parameterized API (new):**

```text
GET /api/covers/<release_dir>?size=256x256
```

Serves size-specific cover variants. Generates on-demand if needed.

**Example usage:**

```python
# Android Auto - request optimal size
GET /api/covers/Artist%2FAlbum?size=256x256

# Without size parameter - returns main cover
GET /api/covers/Artist%2FAlbum

# Invalid size - returns error JSON
GET /api/covers/Artist%2FAlbum?size=999x999
# {"error": "Invalid size parameter", "valid_sizes": [...]}
```

### Cover extraction details

The extraction process follows this priority:

1. **Common image files** in release directory:
   * `cover.jpg`, `folder.jpg`, `album.jpg`, `front.jpg`
   * `cover.png`, `folder.png`

2. **Embedded artwork** from audio files:
   * Extracted from first audio file with embedded art
   * Supports all formats handled by TinyTag

3. **Optimization:**
   * Converts all images to RGB JPEG
   * Resizes to max 800×800px (maintains aspect ratio)
   * Compresses to 85% quality initially
   * Reduces quality iteratively if file >500KB
   * Handles transparency by compositing on white background

4. **Caching:**
   * Sanitizes release directory to safe filename slug
   * Stores in `DATA_ROOT/cache/covers/{slug}.jpg`
   * Size variants stored as `{slug}_{size}x{size}.jpg`

### Performance characteristics

**Storage impact:**

* Main cover: 300-500 KB per album
* All 6 size variants: 50-150 KB total per album
* Lazy generation: variants only created when requested

**Bandwidth savings:**

| Client | Original (800px) | Optimized | Savings |
| ------ | ---------------- | --------- | ------- |
| Android Auto | 300-500 KB | 30-50 KB (256×256) | ~90% |
| Mobile web | 300-500 KB | 15-25 KB (128×128) | ~95% |
| List thumbnails | 300-500 KB | 5-8 KB (96×96) | ~98% |

**Generation performance:**

* First request with variants: +100-200ms (one-time cost)
* Subsequent requests: 0ms (served from cache)
* Main cover extraction: typically <100ms

---

## 💤 Lazy loading

Artist and album results include a `click_query` field.

When the user clicks such a result:

1. The UI issues a **new search**
2. Using the stored `click_query`
3. Which returns a more specific result set

This keeps the API stateless and avoids nested payloads.

---

## ✨ Highlighting

All matched terms are automatically highlighted:

* Implemented in `_highlight_text(...)`
* Case-insensitive
* Wrapped in `<mark>...</mark>`

Highlighting applies to:

* Artist names
* Album titles
* Track titles

This behavior is **UI-specific** and not part of the core search engine.

---

## 💡 Match explanations

Each result may include a `reasons` list explaining *why* it matched:

* Matching artist name
* Number of matching albums
* Number of matching tracks

These are intended for UI hints, badges, or tooltips.

---

## 👀 Real‑time monitoring

`MusicCollection.start_monitoring()` creates a `watchdog.observers.Observer` that uses the
`EnhancedWatcher` class (defined in `src/musiclib/_watcher.py`).
The enhanced watcher adds two important behaviours that differ from a naïve `FileSystemEventHandler`:

| Feature | What it does | Why it matters |
| ------- | ------------ | -------------- |
| **Debounce delay** (`DEBOUNCE_DELAY = 2.0 s`) | After the last change to a given file, the watcher waits 2 seconds before queuing an `INDEX_FILE` or `DELETE_FILE` event. | Prevents a burst of rapid edits (e.g., a tag‑editing batch) from generating many separate index operations, which could corrupt the DB. |
| **Coalescing** | Multiple `created`/`modified` events for the same path are merged into a single `INDEX_FILE` event; a later `deleted` event overrides any pending `modified` events. | Guarantees that the final state of the file is what gets indexed. |
| **Graceful shutdown** (`shutdown()` method) | Cancels all pending timers and flushes any remaining events to the write queue before the observer is stopped. | Ensures no file‑system changes are lost when the application exits. |

The rest of the monitoring flow (observer start/stop, queue → writer thread) remains exactly as described in the original diagram.

---

## 📄 Summary

In short, searching works as follows:

1. Parse the query into tagged and free-text terms
2. Collect and score artist, album, and track candidates
3. Build hierarchical grouped results
4. Flatten results into UI-friendly objects
5. Highlight matches and attach navigation queries
6. Support lazy exploration through follow-up searches

Cover art management works as follows:

1. Extract covers from release directories or embedded artwork
2. Optimize and cache at 800×800px
3. Generate size variants on-demand for bandwidth efficiency
4. Serve via direct file URLs or size-parameterized API
5. Fall back gracefully when covers unavailable

This design allows the UI to deliver a fast, expressive, and navigable search experience without embedding deep hierarchies in a single response, while efficiently serving cover art to clients with varying bandwidth and display requirements.

## 🔌 API

Only the following methods are considered stable public APIs:
`MusicCollection.search_grouped`, `MusicCollectionUI.search_highlighting`, `MusicCollection.rebuild`, `MusicCollection.resync`, `MusicCollection.close`, `MusicCollection.get_collection_stats`, `MusicCollection.get_cover`, `MusicCollection.get_cover_sizes`.

### ::: src.musiclib.reader.MusicCollection

### ::: src.musiclib.ui.MusicCollectionUI
