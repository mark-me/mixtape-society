# Docker Deployment

![Container](images/container.png){ align=right width="90" }

Deploying Mixtape Society with Docker is the easiest and most reliable way to get your private mixtape server up and running—perfect for home servers, VPS, or NAS devices.

## Why Docker?

- **Zero setup** — No need to install Python, uv, or dependencies manually.
- **Portable —** Runs identically on Linux, Windows (with Docker Desktop), macOS, or ARM devices (e.g., Raspberry Pi).
- **Persistent data** — Volumes keep your mixtapes, database, and index safe across restarts or updates.
- **Secure isolation** — The app runs in a container, separated from your host system.

Official images are hosted on GitHub Container Registry: [ghcr.io/mark-me/mixtape-society:latest](ghcr.io/mark-me/mixtape-society:latest). They're automatically built and pushed on every commit to main.

## Quick Start (Single Command)

For testing or simple setups:

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v /path/for/data:/app/collection-data \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

- Open with [http://localhost:5000](http://localhost:5000).
- Login with your password
- The first run will index your library (this can take time—check logs with `docker logs -f mixtape-society`).

## Recommended: Docker Compose

For production or long-term use, Docker Compose makes management easier (updates, secrets, named volumes).

Create a docker-compose.yml:

```yaml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /your/music:/music:ro
      - /data/mixtape-society:/app/collection-data
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Amsterdam
      - PASSWORD=${APP_PASSWORD}
      - APP_ENV=production
      - LOG_LEVEL=INFO
```

Create a .env file in the same directory:

```text
APP_PASSWORD=YourVeryStrongPasswordHere!
```

Run it:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Update later with `docker compose pull && docker compose up -d`.

## Volumes explained

- /music:ro → Your music files (mounted read-only for safety).
- /app/collection-data → Persistent SQLite database, indexing data and a subdirectory for your created mixtapes (JSON files + covers).

## Exposing Securely (HTTPS + Domain)

For access outside your local network, use a reverse proxy like Traefik or Nginx Proxy Manager.
Example setup with Traefik (labels in compose):

```yaml
services:
  mixtape-society:
    # ... existing config
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mixtape.rule=Host(`mixtape.yourdomain.com`)"
      - "traefik.http.routers.mixtape.entrypoints=websecure"
      - "traefik.http.routers.mixtape.tls.certresolver=myresolver"
```

## Tips & Troubleshooting

- **First indexing slow?** Normal for large libraries—monitor with `docker logs -f mixtape-society`.
- **Rebuild index?** Exec into container: `docker compose exec mixtape-society python -c "from musiclib import MusicCollection; - MusicCollection('/music').rebuild()"`
- **Permissions issues?** Ensure the host music directory is readable by the container user (UID 1000).
- **Building your own image?** See the [Development](development/docker.md) section.

Enjoy your private mixtape haven! If you run into issues, check the logs or open a GitHub issue. 🎧
