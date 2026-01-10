![Container](images/container.png){ align=right width="90" }

# Docker Deployment

Deploying Mixtape Society with Docker is the easiest and most reliable way to get your private mixtape server up and running—perfect for home servers, VPS, or NAS devices.

## 🐋 Why Docker?

| Benefit | Explanation |
|---------|------------|
| Zero-setup | No manual Python, `uv`, or system-package installation. The container bundles the interpreter, dependencies, and the Flask app. |
| Portability | Works on Linux, macOS, Windows (Docker Desktop) and ARM devices (Raspberry Pi) without code changes. |
| Isolation | The app runs as an unprivileged user inside the container; the host file system is only accessed through explicit volume mounts. |
| Persistence | Docker volumes keep your SQLite DB, mixtape JSON files, cover images, and audio-cache across container upgrades or restarts. |
| Automatic Updates | Pull the latest image from GitHub Container Registry (`ghcr.io/...`) and restart – the new version starts instantly. |

## ✅ Official Image

The official, automatically‑built image lives at:

```bash
ghcr.io/mark-me/mixtape-society:latest
```

*Tags are rebuilt on every release tag for `master`. Use a specific tag (e.g. `v1.4.2`) for reproducible deployments.*

## 🚀 Quick‑Start One‑Liner

Replace the placeholders with paths that exist on your host:

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

**What this does**

| Flag | Effect |
|------|-------|
| `-p 5000:5000` | Exposes the Flask dev server on host port 5000. |
| `-v /path/to/your/music:/music:ro` | Mounts your music library read-only (required by `MUSIC_ROOT`). |
| `-v /path/for/data:/app/collection-data` | Persists the SQLite DB, mixtapes, covers, and audio cache. |
| `-e APP_PASSWORD=…` | Sets the login password (mandatory in production). |
| `-e APP_ENV=production` | Forces the `ProductionConfig` class (disables debug mode). |
| `--restart unless-stopped` | Guarantees the container restarts after crashes or host reboots. |

After the container starts, open [http://localhost:5000](http://localhost:5000), log in with the password you set, and let the indexing run (check progress with `docker logs -f mixtape-society`).

## 🏗️ Full Docker‑Compose Setup (Production Ready)

Create a directory (e.g. `docker`/) and place the following two files inside it.

### `docker-compose.yml`

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

### `.env` (placed next to `docker-compose.yml`)

Create a .env file in the same directory:

```text
# Path on the host where your music files live.
# Example: /home/user/Music   (Linux/macOS)
#          C:\Users\Me\Music   (Windows, use forward slashes)
MUSIC_HOST_PATH=/absolute/path/to/your/music

# Strong password for the web UI (required in production!)
APP_PASSWORD=YourVeryStrongPasswordHere!
```

!!! TIP
    Tip: Keep the `.env` file outside version control (`gitignore`) because it contains secrets.

#### Starting the stack

```bash
cd docker
docker compose up -d   # pulls the image, creates the volume, and starts the service
```

#### Updating to a newer version

```bash
docker compose pull          # fetch latest image
docker compose up -d --no-deps --force-recreate mixtape   # restart only the app container
```

## 🔄 Configuration Mapping (Env ↔ Filesystem)

| Config variable (Python) | Docker-Compose / docker run mapping | Default (if omitted) | Where it ends up on the host |
|--------------------------|-----------------------------------|--------------------|------------------------------|
| APP_ENV | `-e APP_ENV=production` (or in `.env`) | `development` | Controls which subclass (`ProductionConfig`) is used. |
| MUSIC_ROOT | Volume mount `-v /host/music:/music:ro` | `/music` | The container sees the music library at `/music`. |
| DATA_ROOT | Volume mount `-v mixtape_data:/app/collection-data` (named volume) | `../collection-data` (relative to repo) | Holds `collection.db`, `mixtapes/`, `cache/audio/`. |
| PASSWORD (APP_PASSWORD) | `-e APP_PASSWORD=…` (or in `.env`) | `dev-password` (dev) / `test-password` (test) | Required in production; used for login. |
| LOG_LEVEL (optional) | `-e LOG_LEVEL=INFO` | `INFO` | Controls the verbosity of the Flask logger. |
| TZ (optional) | `-e TZ=UTC` | System timezone | Affects timestamps shown in the UI (`now` context variable). |

All derived paths (`DB_PATH`, `MIXTAPE_DIR`, `COVER_DIR`, `AUDIO_CACHE_DIR`) are automatically calculated from `DATA_ROOT` inside the container, so you never need to set them manually.

## 📦 Volume Layout Explained

Inside the container (`/app/collection-data`):

```bash
/app/collection-data/
├─ collection.db                # SQLite DB with indexed music metadata
├─ mixtapes/
│   ├─ <slug>.json             # One JSON file per mixtape
│   └─ covers/
│       └─ <slug>.jpg          # Optional cover image for each mixtape
└─ cache/
    └─ audio/
        └─ <artist>/<album>/<track>.mp3   # Cached/transcoded audio files
```

On the **host**, the named volume `mixtape_data` maps to a directory managed by Docker (usually under` /var/lib/docker/volumes/...`). You can inspect it with:

```bash
docker volume inspect mixtape_data
```

If you prefer a **bind‑mount** (easier to explore manually), replace the volume line with:

```bash
- /path/on/host/collection-data:/app/collection-data
```

Make sure the host directory is writable by the UID/GID the container runs as (default `1000:1000`).

## 🌐 Running Behind a Reverse Proxy (HTTPS & Domain)

For external access you’ll typically terminate TLS at a reverse proxy (Traefik, Nginx Proxy Manager, Caddy, TSDProxy, etc.). Below is a minimal Traefik example that assumes you already have Traefik running on the same Docker network.

### Traefik

#### Add Labels to docker-compose.yml

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

| Label | Meaning |
|-------|---------|
| `traefik.enable=true` | Expose this container to Traefik. |
| `rule=Host(...)` | Route requests for your domain to this service. |
| `entrypoints=websecure` | Use the TLS entrypoint (usually port 443). |
| `tls.certresolver=myresolver` | Let Traefik obtain a Let's Encrypt certificate automatically. |
| `loadbalancer.server.port=5000` | Traefik forwards to the Flask container’s internal port 5000. |

*Explanation*

#### Minimal docker-compose.yml Snippet

```yaml
services:
  traefik:
    image: traefik:v2.11
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.email=you@example.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"   # Traefik dashboard
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "letsencrypt:/letsencrypt"
    restart: unless-stopped

volumes:
  letsencrypt:
```

Now visiting `https://mixtape.yourdomain.com` will present a secure HTTPS site with a valid certificate.

### TSDProxy

If you prefer to terminate TLS and handle routing with [tailscale](https://tailscale.com/) and [TSDProxy](https://almeidapaulopt.github.io/tsdproxy/docs/) (a lightweight, Docker‑native reverse‑proxy that works similarly to Traefik/Nginx Proxy Manager), you can expose the Mixtape Society container behind it with just a few environment variables and labels.

#### Add TSDProxy Labels / Env Vars to docker-compose.yml

```yaml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"                     # internal Flask port (kept private)
    volumes:
      - ${MUSIC_HOST_PATH}:/music:ro
      - mixtape_data:/app/collection-data
    environment:
      - APP_ENV=production
      - APP_PASSWORD=${APP_PASSWORD}
      # ==== TSDProxy integration ====
      - TSDPROXY_ENABLE=true                     # tell TSDProxy to watch this container
      - TSDPROXY_HOST=mixtape.yourdomain.com    # the public hostname
      - TSDPROXY_HTTP_PORT=5000                 # internal port to forward to
      - TSDPROXY_TLS_EMAIL=you@example.com      # email for Let’s Encrypt
    # Alternatively you can use Docker **labels** instead of env vars:
    # labels:
    #   - "tsdproxy.enable=true"
    #   - "tsdproxy.host=mixtape.yourdomain.com"
    #   - "tsdproxy.port=5000"
    #   - "tsdproxy.tls.email=you@example.com"
```

What each variable does

| Variable / Label | Meaning |
|------------------|---------|
| `TSDPROXY_ENABLE=true` | Marks the container as a candidate for proxying. |
| `TSDPROXY_HOST=mixtape.yourdomain.com` | The DNS name that will resolve to your server’s public IP. |
| `TSDPROXY_HTTP_PORT=5000` | The internal port on which the Flask app listens (the port you expose above). |
| `TSDPROXY_TLS_EMAIL=you@example.com` | Email address used by Let’s Encrypt for certificate issuance and renewal notices. |

!!! NOTE
    TSDProxy reads either environment variables (as shown) or Docker labels prefixed with `tsdproxy..` Pick whichever style fits your workflow.

#### Deploy the TSDProxy Container

Create a separate `docker-compose.tsdproxy.yml` (or add it to the same file) that runs the proxy:

```yaml
services:
  tsdproxy:
    image: ghcr.io/tsdproxy/tsdproxy:latest
    container_name: tsdproxy
    restart: unless-stopped
    ports:
      - "80:80"          # HTTP → redirect to HTTPS
      - "443:443"        # HTTPS entry point
    volumes:
      - tsdproxy_data:/etc/tsdproxy   # persistent config & cert storage
    environment:
      - TZ=UTC
    networks:
      - default   # ensure it shares the same network as the mixtape service

volumes:
  mixtape_data:
  tsdproxy_data:
```

**Key points**

* TSDProxy automatically discovers containers on the same Docker network that have `TSDPROXY_ENABLE=true` (or the matching label).
* It will request a Let’s Encrypt certificate for the hostname you supplied (`mixtape.yourdomain.com`).
* Certificates are stored in the `tsdproxy_data` volume, so they survive container restarts and updates.

## ⚠️ Common Gotchas & Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| First indexing hangs forever | The music library is huge or the container lacks permission to read it. | Verify the `/music` mount is read-only and the UID inside the container (default 1000) can traverse the host directory. Check logs: `docker logs -f mixtape-society`. |
| Permission denied when writing covers | DATA_ROOT volume owned by root. | Ensure the named volume or bind-mount is owned by UID 1000 (or set `PUID`/`PGID` env vars and adjust the Dockerfile accordingly). |
| Cannot reach the app on port 5000 | Port not published or firewall blocks it. | Confirm `-p 5000:5000` (or the `ports:` entry in compose) and that your host firewall allows inbound traffic. |
| Database corruption after abrupt shutdown | Container killed with SIGKILL while SQLite was writing. | Use Docker’s graceful stop (`docker stop`) or configure `restart: unless-stopped`. SQLite is robust, but a clean shutdown is safest. |
| Audio cache not being created | `AUDIO_CACHE_ENABLED` set to False or `AUDIO_CACHE_PRECACHE_ON_UPLOAD` disabled. | Verify those env vars (defaults are True). |
| Cover images not showing | Wrong `COVER_DIR` mount or missing `covers/` sub-folder. | The container automatically creates `covers/` under `MIXTAPE_DIR`. Ensure the volume is persistent and not overwritten on each `docker compose up`. |
| SSL handshake errors behind proxy | Proxy terminates TLS but forwards HTTP to Flask on the wrong port. | Make sure the proxy forwards to port 5000 (the Flask server) and that the `X-Forwarded-Proto` header is respected (Flask handles it automatically).

## 🛠️ Building a Custom Image (Optional)

If you need to add extra Python packages, modify the UI, or pin a specific commit, you can build your own image:

```dockerfile
# Dockerfile (place in project root)
FROM python:3.11-slim

# Install system deps required by Pillow, ffmpeg, etc.
RUN apt-get update && apt-get install -y \
    libjpeg-dev zlib1g-dev libffi-dev libssl-dev \
    ffmpeg && rm -rf /var/lib/apt/lists/*

# Set a non‑root user (mirrors the official image)
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} appgroup && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} appuser

WORKDIR /app
COPY . /app

# Install uv (fast Python package manager) and dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --no-dev --frozen-lockfile

# Switch to non‑root user
USER appuser

EXPOSE 5000
CMD ["python", "app.py"]
```

Build and push:

```bash
docker build -t ghcr.io/yourname/mixtape-society:custom .
docker push ghcr.io/yourname/mixtape-society:custom
```

Then reference the custom tag in your `docker-compose.yml`.
