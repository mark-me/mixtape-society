# Getting Started

![Started](images/rocket.png){ align=right width="90" }

To get started with your own hosted Mixtape Society app you can deploy a Docker container in one of two ways:

### Option 1 – Docker (recommended for production)

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5001:5000 \
  -v /path/to/your/music:/music:ro \
  -v /data/mixtape-society:/app/mixtapes \
  -v /data/mixtape-society:/app/collection-data \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

Open [http://localhost:5001](http://localhost:5001) – Done!

### Option 2 – Docker Compose (best for long-term)

```yaml
# docker-compose.yml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5001:5000"
    volumes:
      - /path/to/your/music:/music:ro
      - /data/mixtape-society:/app/collection-data
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Amsterdam
      - PASSWORD=${APP_PASSWORD}
      - APP_ENV=production
      - LOG_LEVEL=INFO
```

with a `.env` file that contains the password which is loaded by `docker compose`:

```bash
APP_PASSWORD='YourStrongPassword123!'
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

→ opens at [http://localhost:5000](http://localhost:5000) (Default dev password: `dev-password`)

**Pro Tip**: uv sync respects .python-version for exact Python version pinning. No manual venv activation needed!

First run auto-indexes your library. Access at [http://localhost:5000](http://localhost:5000).

### Rebuild Index (if needed)

Local: `uv run -c "from musiclib import MusicCollection; MusicCollection('/path/to/music').rebuild()"`
Docker: Exec into container: `docker compose exec app python -c "..."` (same command).

Enjoy mixtape magic! 🚀
