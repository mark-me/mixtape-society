# Development

## Project Structure

```bash
mixtape-society
├── docker-compose.yml
├── Dockerfile
├── .dockerignore       → Ignoring files for Docker builds
├── docs                → This documentation
├── .github             → Github Actions workflows
│   └── workflows
│       ├── docker-image.yml
│       └── docs.yml
├── .gitignore      → Ignored files for git
├── LICENCE         → Licence file
├── mkdocs.yml      → Docs site config
├── pyproject.toml  → Project config + dependencies
├── .python-version → Python version pinning
├── README.md       → Project README
├── src             → Source code
│   ├── app.py      → Main Flask entrypoint
│   ├── auth.py     → Auth handling
│   ├── config.py   → Env/config classes
│   ├── logtools                → Logging utilities
│   │   ├── color_formatter.py
│   │   ├── __init__.py
│   │   ├── issue_tracking.py
│   │   ├── log_config.py
│   │   ├── log_manager.py
│   │   └── tqdm_logging.py
│   ├── mixtape_manager         → Mixtape persistence
│   │   ├── __init__.py
│   │   └── mixtape_manager.py
│   ├── musiclib                → Music indexing (TinyTag + SQLite)
│   │   ├── _extractor.py
│   │   ├── __init__.py
│   │   └── reader.py
│   ├── routes                  → Flask route handlers
│   │   ├── browse_mixtapes.py
│   │   ├── editor.py
│   │   ├── __init__.py
│   │   └── play.py
│   ├── static                  → Static assets
│   │   ├── css
│   │   │   └── style.css
│   │   └── favicon.png
│   └── templates               → Jinja2 views
│       ├── base.html
│       ├── browse_mixtapes.html
│       ├── editor.html
│       ├── landing.html
│       └── play_mixtape.html
└── uv.lock             → uv-managed dependency lockfile
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