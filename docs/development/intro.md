# Development

![Development](../images/development.png){ align=right width="90" }

Welcome to the development guide for Mixtape Society. This section covers everything you need to contribute, from setup to architecture and future plans.

## Why This Structure?

The project is modularized to separate concerns: core modules (e.g., musiclib, mixtape_manager) handle domain logic without depending on Flask, while routes focus on web interactions. This makes testing easier, improves maintainability, and allows potential extensions (e.g., CLI tools).

## Prerequisites

- Python 3.13+ (managed via `.python-version` and uv)
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
└── uv.lock                     → uv-managed dependency lockfile
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

PRs welcome! To contribute:

- Fork the repo and create a feature branch.
- Install dev deps with `uv sync --extra dev`.
- Run tests: `uv run pytest`.
- Submit a PR against main with a clear description.

 Ideas:

* Multi-user auth
* M3U export
* Mobile PWA support

See `pyproject.toml` for dev dependencies and the [Roadmap](roadmap.md) for more inspiration.