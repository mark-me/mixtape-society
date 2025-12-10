# Development

## Project Structure

```bash
pyproject.toml      → Dependencies + build config (uv-native)
.python-version     → Python version pinning
app.py              → Main Flask entrypoint
config.py           → Env/config classes
musiclib/           → Music indexing (TinyTag + SQLite)
mixtape_manager.py  → Mixtape persistence
templates/          → Jinja2 views
docker/             → Dockerfile + docker-compose.yml
Dockerfile          → Multi-stage build for prod
```

## Local Dev Workflow (uv)

```bash
uv sync                    # Install deps
uv run pytest             # Run tests
uv run python app.py      # Dev server
uv add flask              # Add new dep (updates pyproject.toml)
```

No pip or requirements.txt needed – uv manages everything.

## Docker Development

```bash
docker build -t mixtape-society:dev .
# Or with compose: docker compose build
```

Hot-reload not included (use local uv for that). Prod images auto-built on push to main.

## Testing

```bash
# Local
APP_ENV=test uv run python -m pytest

# Docker
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

### Rebuilding Music Collection Index

```bash
uv run -c "from musiclib import MusicCollection; MusicCollection(MUSIC_ROOT).rebuild()"
```

## Contributing

PRs welcome! Ideas:

* Multi-user auth
* M3U export
* Mobile PWA support

See `pyproject.toml` for dev dependencies