# Docker Deployment

![Container](images/container.png){ align=right width="90" }

Deploy Mixtape Society effortlessly with Docker. Images are available on [GitHub Packages](https://github.com/mark-me/mixtape-society/pkgs/container/mixtape-society) (latest tag updated on CI).

## Why Docker?

- Zero setup: No Python/uv install needed
- Portable: Runs anywhere with Docker
- Persistent: Volumes keep your mixtapes/DB safe
- Secure: Isolated from host Python

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

Access at [http://localhost:5000](http://localhost:5000). First run indexes your library—check logs with docker logs mixtape.

## Docker Compose (Recommended for Production)

Use this for persistent setup with secrets in `.env`.

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

Run: `docker compose -f docker/docker-compose.yml up --build` (use `--env-file .env` for secrets).

## Building Your Own Image

For custom builds (e.g., during development):

```bash
# From Dockerfile in repo
docker build -f docker/Dockerfile -t mixtape-society .

# Multi-arch (ARM/x86)
docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile -t my-mixtape:latest /src
```

## Tips

- Reverse Proxy: Use Nginx/Traefik for HTTPS.
- Scaling: Gunicorn inside the image handles multiple workers.
- Troubleshooting: Monitor indexing with `docker logs`. Rebuild index if needed via container exec.
- Questions? See repo's `Dockerfile` or open an issue.

For dev-specific Docker workflows, see [Local Development](development/docker.md).
