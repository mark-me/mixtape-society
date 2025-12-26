# Searching the music collection

The music collection supports a flexible, tag-based search language that can return **artists, albums, and tracks** in a single request.
Search results are **grouped, scored, highlighted**, and designed for **lazy navigation** via follow-up queries.

Searching is implemented in two layers:

* **Core search engine** – `MusicCollection.search_grouped(...)` (in `reader.py`)
* **UI-facing API** – `MusicCollectionUI.search_highlighting(...)` (in `ui.py`)

Most applications should call the UI-facing method.

---

## 1. Entry points

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

## 2. Query language

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

```
love
```

### Quoting and escaping

* Single or double quotes allow multi-word values

  ```
  artist:"The Beatles"
  ```
* Backslashes can escape special characters inside quoted values

---

## 3. Parsed term structure

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
* UI explanation (“why did this match?”)

---

## 4. Search execution model

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

---

## 5. Result grouping and hierarchy

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

## 6. UI result model

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

**Characteristics**

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
  "reasons": [
    { "type": "track", "text": "5 nummer(s)" }
  ],
  "load_on_demand": true,
  "clickable": true,
  "click_query": "release_dir:'/Prince/Purple Rain'"
}
```

**Characteristics**

* Summary only
* Tracks are loaded on demand
* Albums with tracks by more than three artists are shown as **“Various Artists”**

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
  "artist_click_query": "artist:'Prince'",
  "album_click_query": "album:'Purple Rain'"
}
```

**Characteristics**

* Fully populated (no lazy loading)
* Includes navigation queries for artist and album

---

## 7. Lazy loading

Artist and album results include a `click_query` field.

When the user clicks such a result:

1. The UI issues a **new search**
2. Using the stored `click_query`
3. Which returns a more specific result set

This keeps the API stateless and avoids nested payloads.

---

## 8. Highlighting

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

## 9. Match explanations

Each result may include a `reasons` list explaining *why* it matched:

* Matching artist name
* Number of matching albums
* Number of matching tracks

These are intended for UI hints, badges, or tooltips.

---

## 10. Summary

In short, searching works as follows:

1. Parse the query into tagged and free-text terms
2. Collect and score artist, album, and track candidates
3. Build hierarchical grouped results
4. Flatten results into UI-friendly objects
5. Highlight matches and attach navigation queries
6. Support lazy exploration through follow-up searches

This design allows the UI to deliver a fast, expressive, and navigable search experience without embedding deep hierarchies in a single response.

## API Searching

Only the following methods are considered stable public APIs:
`MusicCollection.search_grouped`, `MusicCollectionUI.search_highlighting`, `MusicCollection.rebuild`, `MusicCollection.resync`, `MusicCollection.close`.

### ::: src.musiclib.reader.MusicCollection

### ::: src.musiclib.ui.MusicCollectionUI
