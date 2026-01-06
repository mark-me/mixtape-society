![modules](../images/app.png){ align=right width="90" }

# App

The file `app.py` defines the main Flask application for the "mixtape-society" project. It is responsible for initializing the web server, configuring the application based on the environment, setting up core services (such as music collection management), and registering routes and blueprints for handling various web requests. The file serves as the entry point for the application, orchestrating authentication, static file serving, and integration with modular route handlers.

## 🏛️ High‑Level Architecture

Flask App (`create_app() → Flask()`)

Core Services           | Blueprints
------------------------|----------------
MusicCollectionUI       | auth
MixtapeManager          | browser
AudioCache              | play
Logger                  | editor
Config (BaseConfig)     | og_cover

All routes are mounted under the appropriate URL prefixes (`/auth`, `/mixtapes`, `/play`, `/editor`, `/og`).

## Configuration & Environment Selection

`app.py` determines the configuration class based on the `APP_ENV` environment variable:

| `APP_ENV` value   | Config class used       | Typical purpose |
|-----------------|------------------------|----------------|
| development     | DevelopmentConfig      | Local dev with verbose logging, SQLite DB in `data/dev`. |
| test            | TestConfig             | CI / automated tests (in-memory DB). |
| production      | ProductionConfig       | Deployed instance (read-only DB, stricter limits). |
| unset           | DevelopmentConfig      | Default fallback. |

The selected class is instantiated, its `ensure_dirs()` method creates required directories (`MIXTAPE_DIR`, `CACHE_DIR`, `LOGS`, etc.), and the instance is returned from `get_configuration()`.

## Flask Application Creation (create_app) – Step‑by‑Step

1. Instantiate Flask

  ```python
  app = Flask(__name__)
  app.secret_key = config_cls.PASSWORD
  app.config.from_object(config_cls)
  CORS(app)  # adds Access‑Control‑Allow‑Origin: *
  ```

2. **Rate limiting** – flask_limiter with defaults `1000/day` and `300/hour`.
3. **Logging** – Calls `logger_setup(config)` (creates `logs/app.log`), then mirrors Gunicorn’s logger if running under Gunicorn.
4. **Core services**
    * `MusicCollectionUI` – watches the music root, builds the SQLite FTS5 DB, and exposes search/high‑level APIs.
    * `AudioCache` – instantiated with `app.config["AUDIO_CACHE_DIR"]`. Stored on `app.audio_cache` for later blueprint access.
    * `MixtapeManager` – points at `config_cls.MIXTAPE_DIR` and receives the collection instance.
5. **Error handler** – Catches `DatabaseCorruptionError` and returns either JSON (for AJAX) or a rendered `database_error.html`.
6. **`@app.before_request`** – Checks whether an indexing job (`rebuilding` / `resyncing`) is in progress; if so, renders `indexing.html` for authenticated users.
7. **Route definitions** – Landing page, indexing‑status JSON, collection‑stats JSON, resync trigger, robots.txt, cover serving, DB reset, health check.
8. **Context processors** – Inject `app_version`, `now` (UTC), `is_authenticated`, and `is_indexing` into every template.
9. **Jinja filter** – `to_datetime` parses ISO strings or custom formats for display.
10. **Blueprint registration** – Auth, Browser, Play, Editor, OG Cover are attached with their respective URL prefixes.
11. **Return** – The fully configured `app` object.

## Core Services & Dependency Wiring

| Service | Construction | Primary responsibilities |
|---------|-------------|-------------------------|
| MusicCollectionUI (`musiclib`) | `MusicCollectionUI(music_root=config_cls.MUSIC_ROOT, db_path=config_cls.DB_PATH, logger=logger)` | Scans the music folder, builds an SQLite DB with FTS5, provides `search_highlighting`, `get_artist_details`, `get_album_details`, `get_cover`, `count`, `get_collection_stats`. |
| AudioCache (`audio_cache`) | `AudioCache(cache_dir=app.config["AUDIO_CACHE_DIR"], logger=logger)` | Stores transcoded audio files, provides progress tracking via `ProgressTracker`. |
| MixtapeManager (`mixtape_manager`) | `MixtapeManager(path_mixtapes=config_cls.MIXTAPE_DIR, collection=collection)` | Persists mixtape JSON files, handles slug generation, cover processing, and deletion. |
| Logger | `get_logger(name=__name__)` (via `logtools`) | Centralised structured logging (`INFO`, `WARNING`, `ERROR`). |

All services are singletons attached to the Flask app (or passed explicitly to blueprints) so that they share the same DB connections and caches.

## Error Handling (Database Corruption)

```python
@app.errorhandler(DatabaseCorruptionError)
def handle_database_corruption(e):
    logger.error(f"Database corruption detected: {e}")

    # Detect AJAX request
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept', '').startswith('application/json') or
        request.is_json
    )

    if is_ajax:
        return jsonify({
            "error": "database_corrupted",
            "message": "The music library database needs to be rebuilt.",
            "requires_reset": True
        }), 500
    else:
        return render_template('database_error.html'), 500
```

**If the request is AJAX (or `Accept: application/json`), a JSON payload is returned; otherwise the user sees a friendly `database_error.html` page.**

## Request‑Level Hooks

### Indexing Guard (`check_indexing_before_request`)

*Runs before every request (except static assets, `/play`, `/indexing-status`, `/check-database-health`).*

* If the user is authenticated and the indexing status file (`indexing_status.json`) reports `rebuilding` or `resyncing`, the request is short‑circuited to `indexing.html`.

### Authentication (`check_auth`)

*Used by the guard and by the `@require_auth` decorator.*

* If the user is not authenticated, the guard does **nothing** (letting the view decide whether to redirect)

## Public Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page (`landing.html`). If indexing is active → `indexing.html`. If authenticated → redirect to `/mixtapes`. |
| `/indexing-status` | GET (exempt from rate limiting) | Returns JSON with current indexing progress (used by the front-end polling). |
| `/collection-stats` | GET (auth) | Returns JSON with `num_artists`, `num_albums`, `num_tracks`, `total_duration`, `last_added`. |
| `/resync` | POST (auth) | Starts a background resync of the music library (spawns a daemon thread). Returns `{ success: true }` or an error. |
| `/robots.txt` | GET | Disallows all crawlers (`User-agent: *\nDisallow: /`). |
| `/covers/<filename>` | GET | Serves cached album cover images from `DATA_ROOT/cache/covers`. Only `.jpg`/`.jpeg`/`.png` are allowed (security). |
| `/reset-database` | POST (auth) | Deletes the SQLite DB files (`*.db`, `*-wal`, `*-shm`, `*-journal`), recreates the `MusicCollectionUI` (triggers a rebuild), and returns a JSON summary. |
| `/check-database-health` | GET (auth) | Runs a quick `PRAGMA quick_check` on the DB and returns `{ healthy: true/false, error?, requires_reset? }`. Used by the front-end health monitor. |

## Template Context Processors

| Processor | Injected Variable | Use Cases |
|-----------|-----------------|-----------|
| `inject_version` | `app_version` (from `utils.get_version()`) | Displayed in the footer (`vX.Y.Z`). |
| `inject_now` | `now` (UTC datetime) | Used for timestamps in templates (`{{ now }}`). |
| `inject_auth_status` | `is_authenticated` (bool) | Conditional UI (login/logout links). |
| `inject_indexing_status` | `is_indexing` (bool) | Disables UI elements while indexing runs. |

These variables are **available in every template** without needing to pass them explicitly.

## Jinja Filter – `to_datetime`

```python
@app.template_filter("to_datetime")
def to_datetime_filter(s, fmt="%Y-%m-%d %H:%M:%S"):
    if not s:
        return None
    try:
        return datetime.strptime(s, fmt)
    except ValueError:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
```

*Converts a string timestamp (custom format or ISO‑8601) into a `datetime` object for formatting (`{{ ts|to_datetime("%b %d, %Y") }}`).*

## Blueprint Registration

```python
app.register_blueprint(
    create_authentication_blueprint(logger=logger, limiter=limiter),
    url_prefix="/auth",
)
app.register_blueprint(
    create_browser_blueprint(
        mixtape_manager=mixtape_manager,
        func_processing_status=get_indexing_status,
        logger=logger,
    ),
    url_prefix="/mixtapes",
)
app.register_blueprint(
    create_play_blueprint(
        mixtape_manager=mixtape_manager,
        path_audio_cache=app.config["AUDIO_CACHE_DIR"],
        logger=logger,
    ),
    url_prefix="/play",
)
app.register_blueprint(
    create_editor_blueprint(collection=collection, logger=logger),
    url_prefix="/editor",
)
app.register_blueprint(
    create_og_cover_blueprint(
        path_logo=Path(__file__).parent / "static" / "logo.svg", logger=logger
    ),
    url_prefix="/og",
)
```

*Each blueprint lives in `routes/` and encapsulates a coherent feature set (authentication, browsing, playback, editing, Open‑Graph cover generation).*

## Application Runner

```python
def serve(debug: bool = True) -> None:
    app = create_app()
    app.run(debug=debug, use_reloader=False, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    serve(debug=True)
```
*Running python `app.py` starts the development server on **port 5000** (accessible from any interface). In production you would typically use Gunicorn or another WSGI server.*

## Base Layout (`base.html`)

`base.html` is the **master template** that all pages extend. It defines the global UI skeleton, navigation, theme handling, and reusable modals/toasts.

### HTML Skeleton & Meta Tags

```html
<!doctype html>
<html lang="en" data-bs-theme="auto">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Mixtape Society{% endblock %}</title>

    <!-- Bootstrap CSS + Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">

    <!-- Custom CSS (global + theme) -->
    <link href="{{ url_for('static', filename='css/base.css') }}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body class="{% if is_authenticated %}authenticated{% endif %}">
```

*The `data-bs-theme="auto"` attribute enables Bootstrap’s built‑in dark‑mode auto‑switching (controlled by the **Theme Switcher** JS).*

### Navigation Bar

```html
<nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top">
    <div class="container-fluid">
        <a class="navbar-brand" href="{{ url_for('landing') }}">
            <i class="bi bi-music-note-beamed me-2"></i>Mixtape Society
        </a>

        <!-- Theme switcher (buttons with data-theme attributes) -->
        <div class="d-flex align-items-center">
            <button class="btn btn-sm btn-outline-light me-2" data-theme="light">
                <i class="bi bi-sun"></i>
            </button>
            <button class="btn btn-sm btn-outline-light me-2" data-theme="dark">
                <i class="bi bi-moon-stars"></i>
            </button>
            <button class="btn btn-sm btn-outline-light" data-theme="auto">
                <i class="bi bi-circle-half"></i>
            </button>
        </div>

        <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
                data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent"
                aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
        </button>

        <div class="collapse navbar-collapse justify-content-end" id="navbarSupportedContent">
            {% if is_authenticated %}
                <a class="nav-link text-light" href="{{ url_for('logout') }}">Logout</a>
            {% else %}
                <a class="nav-link text-light" href="{{ url_for('login') }}">Login</a>
            {% endif %}
        </div>
    </div>
</nav>
```

*Provides quick theme switching (light / dark / auto) and shows Login/Logout depending on `is_authenticated`.*

### Main Content Slot

```html
<main class="container my-4">
    {% block content %}{% endblock %}
</main>
```

*All page‑specific templates (`landing.html`, `browse_mixtapes.html`, `editor.html`, etc.) inject their markup here.*

### Common Modals

#### Indexing Progress Modal

```html
<div class="modal fade" id="indexingModal" tabindex="-1" aria-hidden="true" data-bs-backdrop="static">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content bg-dark text-white">
            <div class="modal-header border-0">
                <h5 class="modal-title"><i class="bi bi-hourglass-split me-2"></i>Indexing Library</h5>
            </div>
            <div class="modal-body">
                <p id="indexingStatusText">Preparing…</p>
                <div class="progress">
                    <div id="indexingProgressBar" class="progress-bar progress-bar-striped progress-bar-animated"
                         role="progressbar" style="width: 0%"></div>
                </div>
            </div>
        </div>
    </div>
</div>
```

*Shown by the `check_indexing_before_request` hook when the library is rebuilding or resyncing.*

#### Database Corruption Modal

```html
<div class="modal fade" id="corruptionModal" tabindex="-1" aria-hidden="true" data-bs-backdrop="static">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content bg-danger text-white">
            <div class="modal-header border-0">
                <h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill me-2"></i>Database Corruption Detected</h5>
            </div>
            <div class="modal-body">
                <p>The music‑library database appears to be corrupted and cannot be used.</p>
                <p class="fw-bold">You must reset the database to continue.</p>
                <div class="d-flex justify-content-end">
                    <button id="showResetConfirmBtn" class="btn btn-light me-2" data-bs-dismiss="modal">
                        Cancel
                    </button>
                    <button class="btn btn-outline-light" data-bs-toggle="modal"
                            data-bs-target="#confirmResetModal">
                        Reset Database
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

*The modal is **static** (cannot be dismissed by clicking outside) so the user must explicitly choose to reset or cancel.*

#### Reset Confirmation Modal

```html
<div class="modal fade" id="confirmResetModal" tabindex="-1" aria-hidden="true" data-bs-backdrop="static">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content bg-dark text-white">
            <div class="modal-header border-0">
                <h5 class="modal-title"><i class="bi bi-tools me-2"></i>Confirm Database Reset</h5>
            </div>
            <div class="modal-body">
                <p>This will permanently delete the current SQLite database and start a fresh rebuild.</p>
                <p class="text-warning fw-bold">All existing track metadata will be lost.</p>
                <div class="d-flex justify-content-end">
                    <button class="btn btn-secondary me-2" data-bs-dismiss="modal">Cancel</button>
                    <button id="confirmResetBtn" class="btn btn-danger">Yes, Reset Now</button>
                </div>
            </div>
        </div>
    </div>
</div>
```

*Triggered from the **Database Corruption modal**. The JavaScript in `static/js/base/databaseCorruption.js` (or its production‑optimized variant) handles the POST to `/reset-database`, shows a loading overlay, and finally redirects to the landing page where the indexing progress is displayed.*

#### Loading Overlay (used during reset)

```html
<div id="resetLoadingOverlay" class="d-none">
    <div class="loading-spinner"></div>
    <p class="mt-3">Resetting database… please wait.</p>
</div>
```

*The overlay is hidden (`d-none`) by default. The JS toggles `style.display = 'flex'` while the reset request is in flight, preventing any further interaction.*

#### Toasts (User Feedback)

```html
<!-- Copy‑to‑clipboard toast -->
<div class="position-fixed bottom-0 end-0 p-3" style="z-index: 1080;">
    <div id="copyToast" class="toast align-items-center text-bg-success border-0 shadow" role="alert">
        <div class="d-flex">
            <div class="toast-body"><i class="bi bi-check2-circle me-2"></i>Public link copied!</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
</div>

<!-- Delete success toast -->
<div class="position-fixed bottom-0 end-0 p-3" style="z-index: 1080;">
    <div id="deleteSuccessToast" class="toast align-items-center text-bg-danger border-0 shadow" role="alert">
        <div class="d-flex">
            <div class="toast-body"><i class="bi bi-trash-fill me-2"></i>Mixtape deleted successfully</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
</div>

<!-- Add track toast (used by the editor) -->
<div class="position-fixed bottom-0 end-0 p-3" style="z-index: 1080;">
    <div id="addTrackToast" class="toast align-items-center text-bg-success border-0 shadow" role="alert">
        <div class="d-flex">
            <div class="toast-body"><i class="bi bi-plus-circle me-2"></i>Track added to mixtape!</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
</div>

<!-- Remove track toast (used by the editor) -->
<div class="position-fixed bottom-0 end-0 p-3" style="z-index: 1080;">
    <div id="removeTrackToast" class="toast align-items-center text-bg-danger border-0 shadow" role="alert">
        <div class="d-flex">
            <div class="toast-body"><i class="bi bi-trash-fill me-2"></i>Track removed from mixtape</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
</div>
```

*All toasts are **Bootstrap 5** components. They are instantiated in the corresponding JavaScript modules (`copyToast.js`, `deleteMixtape.js`, `editor/ui.js`). The `position-fixed` placement ensures they appear in the bottom‑right corner on every page.*

#### Footer

```html
<footer class="mt-5 py-4 border-top text-center bg-body-tertiary">
    <div class="container">
        <p class="mb-1">
            © {{ now.year }} Mixtape Society – v{{ app_version }}
            <a href="https://github.com/yourorg/mixtape-society" target="_blank" class="text-decoration-none ms-2">
                <i class="bi bi-github"></i>GitHub
            </a>
        </p>
        <p class="text-muted small mb-0">
            Theme by <a href="https://bootswatch.com/" target="_blank" class="text-muted">Bootswatch</a>.
            Icons from <a href="https://icons.getbootstrap.com/" target="_blank" class="text-muted">Bootstrap Icons</a>.
        </p>
    </div>
</footer>
```

*`{{ now.year }}` comes from the inject_now context processor. `{{ app_version }}` is injected by inject_version. The footer is deliberately minimal to keep the focus on the main content.*

#### Extra CSS / JS Includes

At the very end of `base.html` (just before `</body>`):

```html
<!-- Bootstrap Bundle (includes Popper) -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

<!-- Base JavaScript (theme switcher, collection stats, database‑corruption handling) -->
<script type="module" src="{{ url_for('static', filename='js/base/index.js') }}"></script>

{% block extra_js %}{% endblock %}
</body>
</html>
```

*`extra_js` is a block that child templates can extend (e.g., the editor page loads its own modules). The base `index.js` pulls in the theme switcher, collection‑stats loader, and database‑corruption detection.*

## 🔌 API

### ::: src.app
