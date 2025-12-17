# Development

![Development](../images/development.png){ align=right width="90" }

## Prerequisites

- Python 3.11+ (managed via `.python-version` and uv)
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (for containerized runs)

## Project Structure

```bash
mixtape-society
├── docker                      → Dockerfiles and compose configs
├── docs                        → This documentation
├── .github                     → GitHub Actions workflows
│   └── workflows
│       ├── docker-image.yml    → Building Docker images on ghcr
│       └── docs.yml            → Building github pages
├── .gitignore                  → Ignored files for git
├── LICENSE                     → License file
├── mkdocs.yml                  → Docs site config
├── pyproject.toml              → Project config + dependencies
├── .python-version             → Python version pinning
├── README.md                   → Project README
├── src                         → Source code
│   ├── app.py                  → Main Flask entrypoint
│   ├── auth.py                 → Auth handling
│   ├── common                  → infrastructure-free abstractions
│   ├── config                  → Env/config module
│   ├── logtools                → Logging utilities
│   ├── mixtape_manager         → Mixtape persistence
│   ├── musiclib                → Music indexing (TinyTag + SQLite)
│   ├── routes                  → Flask route handlers
│   ├── static                  → Static assets
│   │   ├──css                  → Styling of Jinja2 views
│   │   └──js                   → JavaScript for Jinja2 views
│   └── templates               → Jinja2 views
└── uv.lock             → uv-managed dependency lockfile
```

## Local Dev Workflow for uv

```bash
uv sync                   # Install deps
uv sync --extra dev       # Install dev deps
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