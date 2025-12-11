# Docker Deployment

![Container](../images/container.png){ align=right width="90" }

## Why Docker?

- Zero setup: No Python/uv install needed
- Portable: Runs anywhere with Docker
- Persistent: Volumes keep your mixtapes/DB safe
- Secure: Isolated from host Python

Images: [GitHub Packages](https://github.com/mark-me/mixtape-society/pkgs/container/mixtape-society) (latest tag updated on CI).

## Quick Run

```bash
docker pull ghcr.io/mark-me/mixtape-society:latest

docker run -d -p 5000:5000 \
  -v /your/music:/music:ro \
  -v mixtapes:/app/mixtapes \
  -v data:/app/collection-data \
  -e MUSIC_ROOT=/music \
  -e APP_PASSWORD=supersecret \
  --name mixtape \
  --restart unless-stopped \
  ghcr.io/mark-me/mixtape-society:latest
```

## Docker Compose (full example)

Repo includes `docker-compose.yml`:

```yaml
version: '3.8'
services:
  mixtape-society:
    image: ghcr.io/mark-me/mixtape-society:latest
    ports:
      - "5000:5000"
    volumes:
      - music:/music:ro  # Mount your music
      - mixtapes:/app/mixtapes
      - data:/app/collection-data
    environment:
      - MUSIC_ROOT=/music
      - APP_PASSWORD=${APP_PASSWORD}  # From .env
    restart: unless-stopped

volumes:
  music: {}  # Or bind: ./Music:/music:ro
  mixtapes: {}
  data: {}
```

Run: `docker compose -f docker/docker-compose.yml up --build` (use `--env-file .env` for secrets).

## Building Your Own

```bash
# From Dockerfile in repo
docker build -f docker/Dockerfile -t my-mixtape:latest src/

# Multi-arch (ARM/x86)
docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile -t my-mixtape:latest /src
```

## Tips

- First run indexes library (monitor logs: `docker logs mixtape`).
- Expose via reverse proxy (Traefik/Nginx) for HTTPS.
- Scale? Gunicorn inside image handles multiple workers.

Questions? Check repo's `Dockerfile` for build details.
