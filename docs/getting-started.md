# Getting Started

![Started](images/rocket.png){ align=right width="90" }

## Prerequisites

- Python 3.11+ (managed via `.python-version` and uv)
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (for containerized runs)

## Option 1: Local Development (uv + pyproject.toml)

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society

# Sync dependencies (creates .venv, installs from pyproject.toml)
uv sync

# Configure
cp .env.example .env
# Edit .env: set MUSIC_ROOT=/absolute/path/to/your/Music
# Optional: APP_PASSWORD=SomethingVeryStrong123!

# First launch (indexes library – be patient for large collections)
uv run python app.py
```

**Pro Tip**: uv sync respects .python-version for exact Python version pinning. No manual venv activation needed!

Open [http://localhost:5000](http://localhost:5000) and log in (dev default: password).

## Option 2: Docker (easiest for production/testing)

Images are hosted on [GitHub Container Registry](https://github.com/mark-me/mixtape-society/pkgs/container/mixtape-society) (latest tag always available).

### Single Container

```bash
docker pull ghcr.io/mark-me/mixtape-society:latest

docker run -d \
  --name mixtape-society \
  -p 5000:5000 \
  -v /path/to/Music:/music:ro \  # Your music lib (read-only)
  -v ./mixtapes:/app/mixtapes \  # Persistent mixtapes
  -v ./collection-data:/app/collection-data \  # DB + index
  -e MUSIC_ROOT=/music \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

### Docker Compose

The repo includes docker-compose.yml. Customize volumes and run:

```bash
docker compose up -d
```

First run auto-indexes your library. Access at [http://localhost:5000](http://localhost:5000).

### Rebuild Index (if needed)

Local: `uv run -c "from musiclib import MusicCollection; MusicCollection('/path/to/music').rebuild()"`
Docker: Exec into container: `docker compose exec app python -c "..."` (same command).

Enjoy mixtape magic! 🚀
