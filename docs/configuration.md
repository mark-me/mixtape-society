# Configuration

![Configuration](images/configuration.png){ align=right width="90" }

Configuration is via environment variables (or `.env` file for local runs). Docker images support all vars via `-e` flags.

| Variable        | Description                                          | Default / Example                   |
|-----------------|------------------------------------------------------|-------------------------------------|
| `APP_ENV`       | Environment: `development`, `production`, `test`     | `development`                       |
| `MUSIC_ROOT`    | Absolute path to music folder (critical!)            | `/home/mark/Music` (local) / `/music` (Docker) |
| `DB_PATH`       | SQLite index location                                | `./collection-data/music.db`        |
| `APP_PASSWORD`  | Login password (override hard-coded default)         | `password` (dev) / Set your own!    |
| `MIXTAPE_DIR`   | Mixtapes + covers storage                            | `./mixtapes`                        |

## Docker Volumes

- `/music`:ro → Your music library
- `/app/mixtapes` → Saved mixtapes (persistent)
- `/app/collection-data` → SQLite DB (persistent)

Example `docker-compose.yml` mounts these for you.

## Python Versioning

`.python-version` pins to 3.11+ for consistency. uv enforces this during `uv sync`.
