# Getting Started

![Started](images/rocket.png){ align=right width="90" }

## Prerequisites

- Python 3.11+ (managed via `.python-version` and uv)
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (for containerized runs)

### Option 1 – Docker (recommended for production)

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v mixtape_data:/app/mixtapes \
  -v collection_data:/app/collection-data \
  -e MUSIC_ROOT=/music \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

Open [http://localhost:5000](http://localhost:5000) – Done!

### Option 2 – Docker Compose (best for long-term)

```yaml
# docker-compose.yml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /home/you/Music:/music:ro          # ← change this
      - mixtapes:/app/mixtapes
      - db:/app/collection-data
    environment:
      - MUSIC_ROOT=/music
      - APP_PASSWORD=changeme-right-now-please!
      - FLASK_ENV=production

volumes:
  mixtapes:
  db:

```

Then run:

```bash
docker compose up -d
```

### Option 3: Local Development (uv)

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society
uv sync                    # creates venv + installs deps
cp .env.example .env
# ← Edit MUSIC_ROOT and APP_PASSWORD
uv run python app.py
```

→ opens at [http://localhost:5000](http://localhost:5000) (Default dev password: `password`)

**Pro Tip**: uv sync respects .python-version for exact Python version pinning. No manual venv activation needed!

First run auto-indexes your library. Access at [http://localhost:5000](http://localhost:5000).

### Rebuild Index (if needed)

Local: `uv run -c "from musiclib import MusicCollection; MusicCollection('/path/to/music').rebuild()"`
Docker: Exec into container: `docker compose exec app python -c "..."` (same command).

Enjoy mixtape magic! 🚀
