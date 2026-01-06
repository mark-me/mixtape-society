![Configuration](../images/configuration.png){ align=right width="90" }

# Configuration

This document explains every configuration option used by the Mixtape Society application, how the values are sourced (environment variables, .env file, or defaults), the directory layout that results, and the Docker‑specific considerations. The description directly to the implementation in `src/config/config.py`.

## 📥 How Configuration Is Loaded

```python
# src/config/config.py
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env only when we are *not* in production.
if os.getenv("APP_ENV", "development") != "production":
    project_root = Path(__file__).parent.parent.parent   # src/config → project root
    load_dotenv(project_root / ".env")
```

* In **development** (or when `APP_ENV` is anything other than `production`) the file tries to read a `.env` file located at the project root.
* In production the `.env` file is ignored – all configuration must be supplied via real environment variables.

After the optional `.env` load, the module defines a **`BASE_DIR`** (`src/`) and a hierarchy of configuration classes.

## 🛤️ Core Paths & Their Defaults

| Setting | Default (when no env var) | Meaning |
|---------|---------------------------|---------|
| `MUSIC_ROOT` | `/music` | Absolute path to the read-only music library that the collection scanner watches. |
| `DATA_ROOT` | `../collection-data` (relative to the project root) | Root folder writable by the app. All generated data lives underneath this directory. |
| `DB_PATH` | `<DATA_ROOT>/collection.db` | SQLite database file that stores the indexed music metadata. |
| `MIXTAPE_DIR` | `<DATA_ROOT>/mixtapes` | Folder that holds each mixtape’s JSON file (`<slug>.json`). |
| `COVER_DIR` | `<MIXTAPE_DIR>/covers` | Sub-folder for mixtape cover images (`<slug>.jpg`). |
| `AUDIO_CACHE_DIR` | `<DATA_ROOT>/cache/audio` | Directory where transcoded audio files are cached for streaming. |

!!! IMPORTANT
    `DB_PATH`, `MIXTAPE_DIR`, `COVER_DIR`, and `AUDIO_CACHE_DIR` are derived from `DATA_ROOT`. You must not set them directly – change `DATA_ROOT` instead.

## 🌱 Environment Variables (full list)

| Variable | Where it is read | Default (if not set) | Description |
|----------|-----------------|---------------------|-------------|
| `APP_ENV` | `config.py` (top) | `development` | Determines which configuration class (`DevelopmentConfig`, `TestConfig`, `ProductionConfig`) is used. Accepted values: `development`, `test`, `production`. |
| `MUSIC_ROOT` | `BaseConfig.MUSIC_ROOT` | `/music` | Absolute path to the music collection. Must be readable by the process. |
| `DATA_ROOT` | `BaseConfig.DATA_ROOT` | `../collection-data` (project-root relative) | Writable directory for all app-generated files. |
| `PASSWORD` | `BaseConfig.PASSWORD` (and overridden in subclasses) | `dev-password` (dev) / `test-password` (test) / must be set (prod) | Login password for the web UI. |
| `AUDIO_CACHE_ENABLED` | `BaseConfig.AUDIO_CACHE_ENABLED` | `True` | Toggle the whole audio-caching subsystem on/off. |
| `AUDIO_CACHE_DEFAULT_QUALITY` | `BaseConfig.AUDIO_CACHE_DEFAULT_QUALITY` | `medium` | Default quality for cached audio files (`low`, `medium`, `high`). |
| `AUDIO_CACHE_MAX_WORKERS` | `BaseConfig.AUDIO_CACHE_MAX_WORKERS` | `4` | Number of worker threads used for background transcoding. |
| `AUDIO_CACHE_PRECACHE_ON_UPLOAD` | `BaseConfig.AUDIO_CACHE_PRECACHE_ON_UPLOAD` | `True` | When a mixtape is saved, automatically start caching its tracks. |
| `AUDIO_CACHE_PRECACHE_QUALITIES` | `BaseConfig.AUDIO_CACHE_PRECACHE_QUALITIES` | `["medium"]` | List of qualities to precache (e.g., `["low","medium","high"]`). |
| `DEBUG` | Set by subclass (`DevelopmentConfig.DEBUG = True`) | `False` (prod) | Enables Flask’s debugger and auto-reload. |
| `PYTHONPATH` / `PYTHON_VERSION` | Not read by the app, but documented for developers. | – | Pinning to Python 3.11+ via `.python-version` (used by `uv`). |


All variables can be supplied via:
* A `.env` file in the project root (development only).
* Docker environment variables (`-e VAR=value` or `environment:` block in `docker-compose.yml`).
* Direct export in the shell (`export VAR=value`).

## 🔗 Derived Paths (never set directly)

```python
class BaseConfig:
    DB_PATH = DATA_ROOT / "collection.db"
    MIXTAPE_DIR = DATA_ROOT / "mixtapes"
    COVER_DIR = MIXTAPE_DIR / "covers"
    AUDIO_CACHE_DIR = DATA_ROOT / "cache" / "audio"
```

Because these are computed **once** when the class is defined, they automatically follow any change to `DATA_ROOT`. Changing `DB_PATH` or `MIXTAPE_DIR` manually would have no effect and could cause path mismatches.

## 📁 Directory Creation (`ensure_dirs`)

```python
@classmethod
def ensure_dirs(cls):
    cls.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    cls.MIXTAPE_DIR.mkdir(parents=True, exist_ok=True)
    cls.COVER_DIR.mkdir(parents=True, exist_ok=True)
    cls.AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
```

*Called early in `app.py` (`config.ensure_dirs()`).*

It guarantees that all writable directories exist before any component tries to write files. If a directory already exists, `exist_ok=True` prevents an error.

## 🏷️ Configuration Classes

| Class | Inherits from | Overrides / Special behaviour |
|-------|---------------|-------------------------------|
| `BaseConfig` | – | Defines all defaults and `ensure_dirs`. |
| `DevelopmentConfig` | `BaseConfig` | `DEBUG = True`; `PASSWORD` defaults to `"dev-password"` (or env var). |
| `TestConfig` | `BaseConfig` | Uses a temporary `DATA_ROOT` (`/tmp/mixtape-test-data`) and a dummy `MUSIC_ROOT` (`/tmp/test-music`). Ideal for CI pipelines. |
| `ProductionConfig` | `BaseConfig` | `DEBUG = False`; requires `PASSWORD` to be set via env var (no fallback). All other values are taken from the environment or defaults. |

`app.py` selects the class with:

```python
env = os.getenv("APP_ENV", "development")
if env == "production":
    config_cls = ProductionConfig
elif env == "test":
    config_cls = TestConfig
else:
    config_cls = DevelopmentConfig
```

## 🐳 Docker Integration

For more information look at the [Docker Deployment](../docker.md) documentation.

## 🖼️ Typical Scenarios (what you’ll see on disk)

| Scenario | APP_ENV | MUSIC_ROOT | DATA_ROOT | Resulting layout (host side) |
|----------|---------|------------|-----------|-------------------------------|
| Local dev, no `.env` | development | /home/mark/Music (hard-coded default) | ../collection-data (next to the repo) | `collection-data/collection.db`, `collection-data/mixtapes/…`, `collection-data/cache/audio/…` |
| Local dev + `.env` | development | Whatever you set in `.env` | Whatever you set in `.env` | Same as above, but paths reflect the values you placed in `.env`. |
| Docker prod | production | /music (mounted read-only) | /app/collection-data (mounted read-write) | Inside the container the same layout as above; on the host you’ll see the folder you bound to `/app/collection-data`. |
| Automated tests | test | /tmp/test-music (created by the test harness) | /tmp/mixtape-test-data | Temporary directories that are cleaned up after the test suite finishes. |

## 💡 Best‑Practice Recommendations

1. **Never commit a `.env`** containing secrets. Keep passwords out of source control.
2. **In production**, set `APP_PASSWORD` (or any other secret) via the orchestration platform (Docker‑Compose `env_file`, Kubernetes secret, etc.). The app will refuse to start without it.
3. **Mount `DATA_ROOT` on persistent storage** (a volume, bind‑mount, or cloud‑disk) so that the SQLite DB and cached audio survive container restarts.
4. **Keep `MUSIC_ROOT` read‑only** – the scanner only needs to read files; mounting it as ro prevents accidental modifications from the container.
5. **Adjust audio‑caching workers** (`AUDIO_CACHE_MAX_WORKERS`) according to the host CPU count; the default of 4 works well on most 4‑core machines.
6. **If you change `DATA_ROOT` after the app has started**, you must delete the old DB and mixtape folder (or run a migration script) because the paths are baked into the SQLite DB.
7. Run the test suite with `APP_ENV=test` (or simply `pytest` which forces `TestConfig`). This isolates filesystem side‑effects to `/tmp`.

## 🔌 API

### ::: src.config.config
