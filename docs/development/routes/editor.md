![Mixtape editor](../../images/mixtape.png){ align=right width="90" }

# Mixtape editor

The file `routes/editor.py` acts as the backend interface for the mixtape editor UI, managing the lifecycle of mixtape creation and editing, integrating with the music library, and handling file storage for mixtape data and cover images. It ensures that only authenticated users can access editor functionality. Its primary responsibility is to provide endpoints for creating, editing, searching, and saving mixtapes, including handling cover images and metadata. The file uses authentication, interacts with a music collection, and manages mixtape data as JSON files on disk.

## 🌍 High‑Level Overview

The Mixtape Editor is a full‑featured UI that lets a logged‑in user:

| Feature | Description |
| --------- | ------------- |
| **Search & add tracks** | Unchanged – powered by `MusicCollectionUI.search_highlighting`. |
| **Playlist management** | Unchanged – drag-and-drop, reorder, delete, preview. |
| **Cover handling** | Upload a custom image or generate a composite cover from track art. |
| **Save / update** | Creates or updates a mixtape JSON file on disk. |
| **Background audio-caching** | Triggered after a successful save (optional). |
| **QR-code sharing** | After a mixtape is saved, a Share button appears. Clicking it opens a modal that shows a simple QR (preview) and lets the user download an enhanced QR that includes the mixtape’s cover and title. |
| **Progress modal** | Shows background-caching progress via SSE. |

All of this lives under the Flask blueprint editor (`/editor/*`) and is protected by the `@require_auth` decorator.

## 🗺️ Flask Blueprint & Routes

| HTTP | URL Pattern | Handler | Key Behaviour |
| ----- | ---------- | ------- | ------------- |
| `GET` | `/editor/` | `new_mixtape()` | Renders a blank editor (`preload_mixtape` contains empty fields). |
| `GET` | `/editor/<slug>` | `edit_mixtape(slug)` | Loads mixtape JSON via `MixtapeManager.get(slug)` and renders the editor pre-filled. |
| `GET` | `/editor/search?q=` | `search()` | Returns up to 50 highlighted results (artist/album/track) as JSON. Minimum query length = 3. |
| `GET` | `/editor/artist_details?artist=` | `artist_details()` | Returns JSON `{artist, albums:[{album, cover, tracks,…}], …}`. 400 if missing. |
| `GET` | `/editor/album_details?release_dir=` | `album_details()` | Returns JSON `{artist, album, tracks:[…], cover, is_compilation}`. 400 if missing. |
| `POST` | `/editor/save` | `save_mixtape()` | Accepts a JSON payload (`title, cover, liner_notes, tracks, optional slug`). Handles create (new UUID) and update (existing slug). Returns `{success:true, slug, url,…}`. |
| `GET` | `/editor/progress/<slug>` | `progress_stream(slug)` | Server-Sent Events (SSE) that emit `{type:"connected"}` then `{step, status, message, current, total}` objects. Used by Progress Modal. |
| `POST` | `/editor/generate_composite` | `generate_composite()` | Takes `{covers: [url,…]}` → returns `{data_url: "data:image/png;base64,…"}` (composite cover). 400/500 on error. |
| `GET` | `/qr/<slug>.png` | `qr.generate_qr(slug)` | Simple QR code (PNG) that encodes the public mixtape URL. Optional query params: `size` (max 800) and `logo` (true/false). |
| `GET` | `/qr/<slug>/download` | `qr.download_qr(slug)` | Enhanced QR code (PNG) that can include the mixtape’s cover art, title banner, and optional logo. Optional query params: `size` (max 1200), `include_cover`, `include_title`. |

All routes are protected by `@require_auth`, so unauthenticated users are redirected to the login flow.

## 🔄 Data Flow & Server‑Side Logic

1. Creating a New Mixtape
    * `new_mixtape()` builds an empty dict (`title`, `cover`, `liner_notes`, `tracks`, `slug`, `timestamps`) and renders `editor.html` with preload_mixtape set to that dict.
    * The client receives a `client‑id` (generated lazily via `crypto.randomUUID()` and stored in `localStorage["current_mixtape_client_id"])` to guarantee idempotent creates.
2. Editing an Existing Mixtape
    * `edit_mixtape(slug)` instantiates a `MixtapeManager` (pointing at `app.config["MIXTAPE_DIR"]`) and calls `get(slug)`.
    * The resulting dict (including cover, liner_notes, tracks, timestamps) is passed to the template as preload_mixtape.
    * The hidden <input id="editing-slug"> carries the slug so the client knows it is an **update**.
3. Saving (`save_mixtape`)
    * Payload is parsed from JSON.
    * **Track enrichment** – each track’s cover is refreshed via `collection.get_cover(release_dir)`.
    * If a `slug` is present → **update** (`MixtapeManager.update`). Otherwise → **create** (`MixtapeManager.save`).
    * After a successful write, a **background audio‑caching job** is launched (if `AUDIO_CACHE_PRECACHE_ON_UPLOAD` is true) via a daemon thread that calls `_trigger_audio_caching_async`.
    * The response includes the final slug and a URL (`/editor/<slug>`).
4. Progress Streaming (`progress_stream`)
    * Uses `audio_cache.get_progress_tracker` to obtain a `ProgressTracker`.
    * The generator yields SSE lines (`data: {...}\n\n`).
    * The client consumes these events in `progressModal.js`.
5. Composite Cover Generation (`generate_composite`)
    * Receives an array of cover URLs, builds a grid composite (via `CoverCompositor.generate_grid_composite`) and returns a data‑URL (`image/png;base64,…`).

## 🏛️ Client‑Side Architecture

All editor‑related scripts live under `static/js/editor/`.
They are **module‑scoped** (ES6 `import`/`export`) and loaded by `index.js` after the DOM is ready.

| Module | Exported Symbol(s) | Core Responsibility |
| ------ | ------------------ | ------------------- |
| `index.js` | – | Bootstraps the whole page: preload mixtape data, initialise EasyMDE, search, playlist, UI, and set the initial “Liner-Notes” sub-tab. |
| `search.js` | `initSearch` | Debounced search input → `/editor/search` → render grouped results (artists, albums, tracks). Handles lazy loading of album/artist details, “Add” buttons, and preview play/pause. |
| `playlist.js` | `playlist, initPlaylist, addToPlaylist, setPlaylist, register*Callback` | Manages the playlist array, renders the sortable list, handles track-play preview, removal, and “Add whole album” actions. Emits callbacks for unsaved-changes and toast notifications. |
| `editorNotes.js` | `initEditorNotes` | Instantiates EasyMDE, wires up the preview pane, and registers a custom `previewRender` that expands #1, #2-4 references using the current playlist. |
| `ui.js` | `initUI, activateInitialNotesTab` | Handles cover upload/composite modal, Save button (including client-id handling), floating-button behaviour, unsaved-changes detection, navigation guard, and the bottom audio player. |
| `progressModal.js` | `showProgressModal` | Constructs a Bootstrap modal that displays a progress bar, log of caching events, and a “Close” button that appears only after completion. Connects to the SSE endpoint. |
| `utils.js` | `escapeHtml, escapeRegExp, highlightText, showAlert, showConfirm, renderTrackReferences, htmlSafeJson` | Miscellaneous helpers used across the UI (HTML escaping, markdown rendering, modal dialogs). |
| `index.js` | – | Bootstraps the whole page: preload mixtape data, initialise EasyMDE, search, playlist, UI, QR sharing (via common module), and set the initial "Liner-Notes" sub-tab. |
| `coverCompositor.js` (via `utils.CoverCompositor`) | – | Generates a composite cover image from a set of track covers (used by `/editor/generate_composite`). |
| `qrShare.js` | `static/js/common/qrShare.js` | **Shared QR functionality** – Used by browser, editor, and player pages. Handles QR modal display, QR code loading, link copying, and QR download. Eliminates code duplication across pages. |

All modules share a single source of truth (`playlist` array) and communicate via **callback registration** (unsaved‑changes, toast notifications). No circular imports occur.

## 🖥️ UI Layout (Jinja Template – `editor.html`)

| Section | Description |
| ------- | ----------- |
| Header (`<h1>`) | Dynamically shows “Create Mixtape”, “Edit Mixtape”, or “Edit: `title`”. |
| Search Bar | Large pill-shaped input with a search icon, info-popover (advanced search tips), and a loading spinner. |
| Results Column (`col-lg-7`) | Card titled Library – initially shows a placeholder; populated by `search.js` with artists, albums, and tracks. |
| Mixtape Column (`col-lg-5`) | Card titled My Mixtape – contains cover image + upload button, title textarea, tabs (Tracks / Liner Notes), playlist `<ol>` (rendered by `playlist.js`), and a Clear button. |
| Floating Buttons (mobile only) | “Save” (hidden until unsaved) and “Tracks” (always visible) – positioned bottom-right. |
| Bottom Audio Player (`#audio-player-container`) | Fixed-bottom panel that shows the currently playing preview track (cover, title, artist) and a native `<audio>` element. |
| Modals | Generic `appModal` (alerts/confirmations), Cover Options modal (Upload vs Composite). |
| Toasts | “Track added”, “Track removed”, and “Public link copied” toasts (Bootstrap). |
| Progress Modal (injected by `progressModal.js`) | Not in the template; created dynamically when saving. |

All elements use **Bootstrap 5** utilities and custom CSS variables (`--color‑track`, `--bs-body-bg`, etc.) for light/dark and semantic Theming.

## 🧱 Static JavaScript Modules

### Page Load (`index.js`)

```js
document.addEventListener("DOMContentLoaded", () => {
    // 1️⃣ Pre‑populate playlist, cover, title (if editing)
    // 2️⃣ Initialise EasyMDE (with pre‑loaded liner notes)
    // 3️⃣ Initialise search, playlist UI, and UI glue code
    // 4️⃣ Initialise QR share (from common module)
    //    - autoShow: true for existing mixtapes (has slug)
    //    - autoShow: false for new mixtapes (hidden until save)
    // 5️⃣ Activate the correct Liner‑Notes sub‑tab (Write vs Preview)
});
```

* **Pre‑load data** – `window.PRELOADED_MIXTAPE` (populated by Flask) is read.
* **Playlist** – `setPlaylist(preloadMixtape.tracks)` populates the UI list.
* **Cover & Title** – If a cover URL exists, it is set on `#playlist-cover`; title is placed in the textarea (`#playlist-title`).
* **Unsaved‑Changes Reset** – When editing an existing mixtape (`slug` present) the stored `client_id` is kept; for a brand‑new mixtape the local‑storage `current_mixtape_client_id` is cleared.
* **Editor (EasyMDE)** – `initEditorNotes(preloadMixtape.liner_notes)` creates the markdown editor with the appropriate initial value.
* **UI Init** – `initSearch()`, `initPlaylist()`, `initUI()` wire up all interactive pieces (search bar, playlist drag‑&‑drop, floating buttons, unsaved‑change detection, etc.).
* **Liner‑Notes Tab** – `activateInitialNotesTab(hasNotes)` selects Preview if there are saved notes, otherwise Write.

### Library Search (`search.js`)

* **Debounced input** – 300 ms after the user stops typing, a request to `/editor/search?q=` is sent.
* **Results Rendering** – Returned JSON is grouped by `type` (`artist`, `album`, `track`).
* **Artists** → collapsible accordion (`bg-artist`). Clicking expands to lazily load the artist’s albums via `/editor/artist_details`.
* **Albums** → collapsible accordion (`bg-album`). Expanding loads tracks via `/editor/album_details`.
* **Tracks** → list items with a **preview** button (plays a short preview via the global audio player) and an **add** button (pushes the track into the playlist).
* **Add‑Album** – Inside an album accordion a “Add whole album” button adds *all* tracks at once.
* **Highlighting** – Search terms are wrapped in `<mark>` by the back‑end (`MusicCollection.search_highlighting`). The UI adds extra colour classes for visual distinction.

### QR Share Integration (`common/qrShare.js`)

* **Module location** – `static/js/common/qrShare.js` (shared across browser, editor, and player)
* **Modal definition** – `#qrShareModal` in `base.html` (global, no duplication)
* **Button visibility logic** –
  - **New mixtape**: Share button starts hidden (`autoShow: false`)
  - **Existing mixtape**: Share button shown immediately (`autoShow: true`)
  - **After save**: `mixtape-saved` event triggers button visibility update
* **Slug detection** – Checks `#editing-slug` input value, falls back to `window.PRELOADED_MIXTAPE.slug`
* **QR display** – Loads `/qr/<slug>.png` (simple QR for preview)
* **Download** – Calls `/qr/<slug>/download` (enhanced QR with cover art and title)
* **Copy link** – Copies `/play/share/<slug>` to clipboard with toast notification

**Integration in `index.js`:**

```javascript
// Determine if existing mixtape (has slug)
const isExistingMixtape = Boolean(
    (preloadMixtape && preloadMixtape.slug) ||
    document.getElementById('editing-slug')?.value
);

initQRShare({
    shareButtonSelector: '#share-playlist',
    modalId: 'qrShareModal',
    getSlug: () => {
        const editingInput = document.getElementById('editing-slug');
        if (editingInput && editingInput.value) return editingInput.value;
        if (window.PRELOADED_MIXTAPE?.slug) return window.PRELOADED_MIXTAPE.slug;
        return null;
    },
    autoShow: isExistingMixtape  // Show immediately for existing, hide for new
});
```

**Save integration in `ui.js`:**
After successful save, trigger the share button visibility:

```javascript
// In the save function after success
document.getElementById('editing-slug').value = data.slug;
document.dispatchEvent(new CustomEvent('mixtape-saved', {
    detail: { slug: data.slug }
}));
```

### Playlist (`playlist.js`)

* **Data model** – `window.playlist` is a plain array of objects `{artist, album, track, duration, path, filename, cover}`.
* **Rendering** – `renderPlaylist()` builds an ordered list (`<ol id="playlist">`) with:
  * Drag handle (`.drag-handle`) for reordering.
  * Cover thumbnail (or placeholder).
  * Play‑preview overlay button (`.play-overlay-btn`).
  * Track title, artist · album, duration, and a delete button.
* **Drag‑&‑Drop** – Powered by **Sortable.js**; after a reorder the array is rebuilt from the DOM order.
* **Play‑preview** – Clicking a track’s overlay button:
  1. Loads the file into the **global audio player** (`#global-audio-player`).
  2. Shows the bottom player container (`#audio-player-container`).
  3. Updates “Now playing” title/artist and cover image.
  4. Toggles the button icon between **play** (`bi-play-fill`) and **pause** (`bi-pause-fill`).
* **Add / Remove callbacks** – `registerTrackAddedCallback` and `registerTrackRemovedCallback` fire toast notifications (`#addTrackToast`, `#removeTrackToast`).

### Liner‑Notes (`editorNotes.js`)

* **EasyMDE** – Configured with a custom toolbar, spell‑checker disabled, and a **preview renderer** that expands `#1`, `#2‑4`, etc. using the current playlist (`renderTrackReferences`).
* **Live preview** – When the **Preview** tab becomes visible, the markdown is rendered with **marked** → **DOMPurify** → inserted into `#markdown-preview`.
* **Two‑way sync** – Switching back to **Write** retains the editor’s current value; changes in the editor automatically update the preview when the tab is active.

### Save Workflow (`ui.js`)

1. **Mark unsaved** – Any mutation (cover upload, title edit, playlist change, liner‑notes edit) calls `markUnsaved()`.
2. **Badge & floating button** – An “Unsaved” badge appears on the top‑right **Save** button; a floating **Save** button (`#floating-save`) appears on mobile.
3. **Client‑ID handling** –
   * For a new mixtape a UUID (`crypto.randomUUID()`) is stored in `localStorage.current_mixtape_client_id`.
   * The same ID is reused for subsequent saves, guaranteeing **idempotent** creation.
4. **POST `/editor/save`** – Payload includes:
   * `title`, `cover` (data‑URL or `null`), `liner_notes`, `tracks` (plain objects), optional `slug`, and `client_id`.
5. **Server response** – Returns `{success:true, slug, url,…}`.
6. **Open progress modal** – `showProgressModal(slug)` displays the **Progress Modal**.

### Cover Generation / Upload (`ui.js` + `/editor/generate_composite`)

* **Cover Options Modal** – Clicking the camera button opens `#coverOptionsModal` with two choices:
  1. **Upload Image** – Triggers the hidden file input (`#cover-upload`). Validation checks file type (`jpg/png/gif/webp`) and size (≤ 5 MiB). On success the image is read as a data‑URL and displayed.
  2. **Generate Composite** – Sends the list of track cover URLs (`playlist.map(t=>t.cover)`) to `/editor/generate_composite`. The server returns a **data‑URL** PNG which replaces the current cover.
* **Both actions** set `coverDataUrl` and call `markUnsaved()`.

### Navigation Guard & Browser Warning

* **Link interception** – Any internal `<a>` click while `hasUnsavedChanges` is `true` shows a **confirmation modal** (`showConfirm`). If the user confirms, navigation proceeds; otherwise it is cancelled.
* **`beforeunload`** – Browsers display a native “You have unsaved changes…” dialog when the user tries to close, refresh, or navigate away.

### Reorder Mode

* **Toggle button** – `#toggle-reorder-mode` adds/removes the class `reorder-mode` on `<body>`.
* **Effects** –
  * Hides the library column (`.col-lg-7`).
  * Expands the mixtape column to full width.
  * Enlarges the playlist area for easier drag‑&‑drop.
  * Hides the cover/title section to maximize vertical space.

### Floating Buttons (Mobile)

* **Save** – `#floating-save` mirrors the top‑right **Save** button; it becomes visible when there are unsaved changes.
* **Tracks** – `#floating-tracks` jumps to the **Tracks** tab and scrolls the mixtape card into view.

---

**Summary** – The editor page is a tightly‑coupled SPA‑style UI built on vanilla JavaScript, Bootstrap, and a handful of third‑party libraries (Sortable.js, EasyMDE, marked, DOMPurify). All user actions funnel through the central `playlist` model, which synchronises the visual list, the global audio player, and the back‑end save endpoint. Unsaved‑change detection, background audio‑caching progress, and cover‑generation utilities provide a polished, production‑ready experience.

## 🛤️ Interaction Flow (Typical User Journey)

1. **Open** the editor (`/editor/` or `/editor/<slug>`).
2. **Page loads** → `index.js` pre‑populates playlist, cover, title, and liner notes (if editing).
3. **Search** → type ≥ 2 characters → `search.js` fetches results → user clicks Add → track appears in the playlist (toast shown).
4. **Reorder** (optional) → click the expand button → drag handles appear → rearrange tracks.
5. **Edit title / liner notes** → any change marks the mixtape as unsaved (badge appears, floating save button fades in).
6. **Cover** → click camera button → choose Upload or Generate Composite → cover preview updates → unsaved flag set.
7. **Preview a track** → click the play overlay → bottom player appears, showing cover, title, artist; button toggles play/pause.
8. **Save** → click Save (or floating save).
    * Client‑id generated (if new).
    * POST `/editor/save`.
    * Server writes JSON, possibly triggers background audio‑caching.
    * UI shows Progress Modal (`showProgressModal(slug)`).
9. **Progress Modal** receives SSE events → updates progress bar & log.
    * When `completed` → “Close” button enabled → user

## 📤 QR‑Code Sharing

### Share Button & Visibility

* The **Share** button (`#share-playlist`) is hidden (`display:none`) until the editor has a valid `slug`.
* The client‑side module `static/js/editor/qrShare.js` listens for the custom **`mixtape-saved`** event (dispatched by `ui.js` after a successful `POST` `/editor/save`). When the event fires, the module calls `updateShareButtonVisibility()` which sets `shareBtn.style.display = ''`.
* If the user opens an existing mixtape (`/editor/<slug>`), the hidden input `#editing-slug` already contains the `slug`, so the button is shown immediately on page load.

### QR Share Modal

The modal contains three UI states:

| State | Element | Behaviour |
| ----- | ------- | --------- |
| Loading | `#qr-loading` (spinner) | Shown while the QR image is being fetched. |
| Success | `#qr-code-img` | Displayed once the PNG loads (`onload` event). |
| Error | `#qr-error` | Shown if the image request fails (e.g., 404 or server error). |

The **Copy** Link button copies the public mixtape URL (`/share/<slug>`) to the clipboard and shows a toast (`#shareToast`). The **Download** button triggers the **enhanced QR** endpoint (`/qr/<slug>/download?...`) and forces a file download with a friendly filename (`<Mixtape‑Title>-qr-code.png`).

### Backend QR Blueprint (`/qr/...`)

Implemented in `routes/qr_blueprint.py` and exposed via the `qr` Flask blueprint:

| Route | Method | Description |
| ----- | ------ | ----------- |
| `/qr/<slug>.png` | `GET` | Returns a simple QR PNG (`size` = size px, optional logo). |
| `/qr/<slug>/download` | `GET` | Returns an enhanced QR PNG that can include the mixtape’s cover art, title banner, and optional logo. |

Both routes:

* Validate that the mixtape exists (`MixtapeManager.get(slug)`).
* Resolve the optional logo (`static/logo.svg` → fallback `static/logo.png`).
* For the **download** endpoint, also resolve the mixtape cover (`app.config["COVER_DIR"]`).
* Use the **`qr_generator`** package (`generate_mixtape_qr` / `generate_mixtape_qr_with_cover`).
* Return **`Cache‑Control: public, max-age=3600`** and an appropriate **`Content‑Disposition`** header (`inline` for the preview, `attachment` for the download).

!!! Important
  The QR blueprint is registered separately from the editor blueprint:

  ```python
  # app.py (excerpt)
  from routes.qr_blueprint import create_qr_blueprint
  app.register_blueprint(
      create_qr_blueprint(mixtape_manager, logger=get_logger(__name__)),
      url_prefix="/qr",
  )
```

### Front‑End Integration (`static/js/editor/qrShare.js`)

Key functions (full source in `editorQrShare.js`):

| Function | What it does |
| -------- | ------------ |
| `initEditorQRShare()` | Finds the Share button and modal, registers the mixtape-saved listener, toggles button visibility, and wires up the modal’s Copy and Download actions. |
| `showQRModal(modal, slug)` | Builds the preview URL (`/qr/<slug>.png?...`), shows the loading spinner, loads the image, and handles success/error UI transitions. |
| `downloadQRCode(slug)` | Calls `/qr/<slug>/download?...` with `size=800&include_cover=true&include_title=true`, parses the `Content-Disposition` header for a friendly filename, and triggers a browser download. |
| `copyShareLink()` | Copies the public share URL (`window.location.origin + "/share/" + slug`) to the clipboard and shows a toast. |
| `triggerShare()` | Public helper that can be called from other scripts (e.g., a keyboard shortcut) to open the QR modal programmatically. |

The module is imported at the bottom of `editor.html`:

```html
<script type="module" src="{{ url_for('static', filename='js/editor/qrShare.js') }}"></script>
```

### Example Request Flow

```mermaid
sequenceDiagram
    participant UI as Editor UI
    participant QRBlueprint as /qr Blueprint
    participant MM as MixtapeManager
    participant QRGen as qr_generator
    participant FS as FileSystem (static folder)

    Note over UI,FS: Simple QR Request Flow
    UI->>QRBlueprint: GET /qr/awesome-mixtape.png?size=400&logo=true
    QRBlueprint->>MM: get('awesome-mixtape')
    MM-->>QRBlueprint: mixtape dict

    Note over QRBlueprint,FS: Resolve logo (SVG preferred, fallback PNG, else None)
    QRBlueprint->>FS: Check static/logo.svg or static/logo.png
    alt logo found
        FS-->>QRBlueprint: logo_path
    else none
        FS-->>QRBlueprint: logo_path = None
    end

    Note over QRBlueprint,QRGen: Build share URL & generate QR
    QRBlueprint->>QRBlueprint: share_url = url_for('play.public_play', slug, _external=True)
    QRBlueprint->>QRGen: generate_mixtape_qr(url, title, logo_path, size=400)
    QRGen-->>QRBlueprint: PNG bytes

    Note over QRBlueprint,UI: Return simple QR
    QRBlueprint->>UI: 200 OK, image/png, inline filename
    UI->>UI: Hide spinner, display img element

    Note over UI,FS: Enhanced QR Request Flow (download)
    UI->>QRBlueprint: GET /qr/awesome-mixtape/download?size=800&include_cover=true
    QRBlueprint->>MM: get('awesome-mixtape')
    MM-->>QRBlueprint: mixtape dict

    Note over QRBlueprint,FS: Resolve logo & cover
    QRBlueprint->>FS: Check static/logo.svg/logo.png and COVER_DIR
    alt logo or cover exists
        FS-->>QRBlueprint: logo_path, cover_path
    else missing
        FS-->>QRBlueprint: logo_path/cover_path = None
    end

    Note over QRBlueprint,QRGen: Generate enhanced QR
    QRBlueprint->>QRBlueprint: share_url = url_for('play.public_play', slug, _external=True)
    QRBlueprint->>QRGen: generate_mixtape_qr_with_cover(params)
    QRGen-->>QRBlueprint: PNG bytes

    Note over QRBlueprint,UI: Return downloadable QR
    QRBlueprint->>UI: 200 OK, image/png, attachment filename
    UI->>UI: Prompt file download dialog
```

Explanation of the diagram

1. **Simple QR preview** – The editor UI requests `/qr/<slug>.png`.
    * The QR blueprint validates the mixtape, resolves an optional logo, builds the public share URL, and calls `qr_generator.generate_mixtape_qr`.
    * The generated PNG is returned with caching headers; the UI hides the spinner and shows the image inside the modal.

2. **Enhanced QR (download)** – When the user clicks **Download**, the editor requests `/qr/<slug>/download` with extra query parameters.
    * The blueprint additionally resolves the mixtape’s cover image (if it exists) and passes it to `generate_mixtape_qr_with_cover`.
    * The response includes a **Content‑Disposition: attachment** header so the browser prompts a file‑save dialog with a friendly filename.

3. **Error handling** (not shown in the happy‑path diagram) –
    * If `MixtapeManager.get(slug)` returns `None`, the blueprint aborts with `404`.
    * If the `qrcode` library is missing, an `ImportError` is caught and a `500` response with a helpful message is sent.
    * Any unexpected exception is logged (`logger.exception`) and results in a `500` error.

4. **QR Share Architecture** –
    * The QR modal (`#qrShareModal`) is defined once in `base.html` (available globally on all pages)
    * The common module (`static/js/common/qrShare.js`) handles all QR functionality
    * Each page (browser, editor, player) calls `initQRShare()` with page-specific config
    * For the editor: Share button is hidden initially (`autoShow: false`), shown after save
    * After saving, the UI dispatches `mixtape-saved` event, which triggers share button visibility

This sequence diagram captures the complete round‑trip for both the preview and download QR flows, illustrating how the front‑end (now using a common module), Flask blueprint, and QR‑generation library collaborate.

## 🔧 Core Helper Functions (Back‑End)

| Function | File | Purpose |
| -------- | ---- | ------- |
| `new_mixtape()` | `editor.py` | Returns a fresh empty mixtape JSON for the template. |
| `edit_mixtape(slug)` | `editor.py` | Retrieves a mixtape via `MixtapeManager.get(slug)` and renders the editor with pre-loaded data. |
| `search()` | `editor.py` | Calls `collection.search_highlighting(query, limit=50)` (the same high-level search used elsewhere). |
| `artist_details()` | `editor.py` | Wrapper around `MusicCollection.get_artist_details(artist)`. |
| `album_details()` | `editor.py` | Wrapper around `MusicCollection.get_album_details(release_dir)`. |
| `save_mixtape()` | `editor.py` | Normalises incoming JSON, enriches each track with its cover (`collection.get_cover(release_dir)`), then either `MixtapeManager.update(slug, …)` or `MixtapeManager.save(...)`. |
| `_trigger_audio_caching_async()` | `editor.py` | Fires a background thread that calls `schedule_mixtape_caching` (from `audio_cache`) and emits progress events via `ProgressTracker`. |
| `generate_composite()` | `editor.py` | Calls `CoverCompositor.generate_grid_composite(covers)` and returns a data-URL. |
| `progress_stream(slug)` | `editor.py` | Returns an SSE Response that streams events from the shared `ProgressTracker`. |

### Important behaviours

* **Cover handling** – If the client sends a `data:image/...` URL, the server decodes, resizes (max 1200 px width) and stores it as `covers/<slug>.jpg`.
* **Timestamp handling** – `MixtapeManager` adds `created_at` and `updated_at` ISO‑8601 timestamps on creation; `updated_at` is refreshed on each edit.
* **Client‑ID reuse** – `save_mixtape` preserves the original `client_id` when updating, ensuring idempotent uploads.

## 📄 API Contract (JSON Schemas)

### Save Payload (`POST` `/editor/save`)

```json
{
  "title": "string (optional, defaults to \"Unnamed Mixtape\")",
  "cover": "string | null – data:image/*;base64 or null",
  "liner_notes": "string (markdown)",
  "tracks": [
    {
      "artist": "string",
      "album": "string",
      "track": "string",
      "duration": "string (MM:SS or seconds)",
      "path": "string – relative to MUSIC_ROOT",
      "filename": "string",
      "cover": "string | null – relative URL to cover image"
    }
  ],
  "slug": "string | null – present only when editing",
  "client_id": "string – UUID, generated client‑side"
}
```

#### Response (success)

```json
{
  "success": true,
  "title": "...",
  "slug": "...",
  "client_id": "...",
  "url": "/editor/<slug>"
}
```

**Error responses** – `400` for validation errors, `404` if an edit targets a missing mixtape, `500` for server failures.

### Search Result (excerpt)

```json
[
  {
    "type": "artist",
    "artist": "The Beatles",
    "raw_artist": "The Beatles",
    "reasons": [{ "type": "album", "text": "3 album(s)" }],
    "num_albums": 3,
    "albums": [],               // lazy‑loaded later
    "load_on_demand": true,
    "clickable": true,
    "click_query": "artist:'The Beatles'"
  },
  {
    "type": "album",
    "artist": "Radiohead",
    "album": "OK Computer",
    "raw_album": "OK Computer",
    "cover": "covers/ok_computer.jpg",
    "is_compilation": false,
    "reasons": [{ "type": "track", "text": "12 track(s)" }],
    "num_tracks": 12,
    "tracks": [],               // lazy‑loaded later
    "load_on_demand": true,
    "click_query": "release_dir:/Radiohead/OK%20Computer/"
  },
  {
    "type": "track",
    "artist": "Pink Floyd",
    "album": "The Wall",
    "track": "Another Brick in the Wall",
    "duration": "5:12",
    "path": "Pink Floyd/The Wall/05 Another Brick in the Wall.flac",
    "filename": "05 Another Brick in the Wall.flac",
    "cover": "covers/the_wall.jpg",
    "highlighted_track": "<mark>Another</mark> Brick in the Wall"
  }
]
```

### SSE Progress Event (from `/editor/progress/<slug>`)

```json
{
  "type": "progress",
  "step": "caching",               // initializing | analyzing | caching | completed | error
  "status": "in_progress",        // pending | in_progress | completed | failed | skipped
  "message": "Caching 3/12 files…",
  "current": 3,
  "total": 12
}
```

## 🔌 API

### ::: src.routes.editor
