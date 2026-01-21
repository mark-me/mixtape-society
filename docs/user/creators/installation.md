![Container](../../images/rocket.png){ align=right width="90" }

# Installation

Deploying Mixtape Society with Docker is the recommended way to run your private mixtape server—perfect for home servers, VPS, or NAS devices.

## 🐋 Why Docker?

| Benefit | Explanation |
| ------- | ---------- |
| Zero-setup | No manual Python or dependency installation. Everything runs in an isolated container. |
| Portability | Works on Linux, macOS, Windows, and ARM devices (Raspberry Pi) without code changes. |
| Isolation | The app runs securely with limited system access through volume mounts. |
| Persistence | Your data (database, mixtapes, covers, cache) survives container updates and restarts. |
| Easy Updates | Pull the latest image and restart—new version runs in seconds. |

## ✅ Official Image

The official, automatically-built image is available at:

```bash
ghcr.io/mark-me/mixtape-society:latest
```

*Images are rebuilt automatically on every release. Use specific version tags (e.g., `v1.4.2`) for reproducible deployments.*

## 🚀 Quick-Start One-Liner

Replace the placeholders with your actual paths:

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v mixtape_data:/app/collection-data \
  -e PASSWORD=YourStrongPassword123! \
  -e APP_ENV=production \
  ghcr.io/mark-me/mixtape-society:latest
```

**What this does:**

| Flag | Effect |
| ---- | ----- |
| `-p 5000:5000` | Exposes the web interface on host port 5000. |
| `-v /path/to/your/music:/music:ro` | Mounts your music library read-only. |
| `-v mixtape_data:/app/collection-data` | Persists database, mixtapes, covers, and cache. |
| `-e PASSWORD=...` | Sets your login password (required). |
| `-e APP_ENV=production` | Enables production configuration (required). |
| `--restart unless-stopped` | Automatically restarts after crashes or reboots. |

After the container starts:

1. Open [http://localhost:5000](http://localhost:5000)
2. Log in with your password
3. Wait for initial music indexing to complete (check progress with `docker logs -f mixtape-society`)

## 🗂️ Full Docker-Compose Setup (Recommended)

### Directory Structure

Create a deployment directory:

```bash
mkdir ~/mixtape-society
cd ~/mixtape-society
```

### docker-compose.yml

Create this file in your deployment directory:

```yaml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ${MUSIC_HOST_PATH}:/music:ro
      - mixtape_data:/app/collection-data
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Amsterdam
      - PASSWORD=${PASSWORD}
      - APP_ENV=production
      - LOG_LEVEL=INFO

volumes:
  mixtape_data:
```

### .env

Create this file next to `docker-compose.yml`:

```bash
# Path to your music collection on the host
MUSIC_HOST_PATH=/home/user/Music

# Strong password for web interface (required!)
PASSWORD=YourVeryStrongPasswordHere!
```

!!! warning "Security Note"
    Never commit `.env` files to version control. Add it to `.gitignore` if you're tracking your deployment configuration.

### Starting the Service

```bash
docker compose up -d
```

**First-time setup:**

- The container will start indexing your music library automatically
- Monitor progress: `docker compose logs -f`
- Indexing time depends on library size (e.g., ~5 minutes for 10,000 tracks)

### Updating to a Newer Version

```bash
docker compose pull
docker compose up -d
```

Your data (database, mixtapes, covers) is preserved in the `mixtape_data` volume.

## 📁 Data Storage

### Volume Layout

Inside the container, data is stored at `/app/collection-data`:

```bash
/app/collection-data/
├── collection.db              # Music library database
├── mixtapes/
│   ├── <slug>.json           # Mixtape definitions
│   └── covers/
│       └── <slug>.jpg        # Custom cover images
└── cache/
    └── audio/
        └── <artist>/<album>/<track>.mp3   # Transcoded audio cache
```

### Using Named Volumes (Default)

Named volumes are managed by Docker and are the recommended approach:

```yaml
volumes:
  - mixtape_data:/app/collection-data
```

**Advantages:**

- Automatic management by Docker
- Good performance
- Easy to backup with `docker volume` commands

**Inspect volume location:**

```bash
docker volume inspect mixtape_data
# Usually at: /var/lib/docker/volumes/mixtape_data/_data
```

### Using Bind Mounts (Alternative)

If you prefer direct access to data files:

```yaml
volumes:
  - /path/on/host/mixtape-data:/app/collection-data
```

**Advantages:**

- Easy to browse/backup with regular tools
- Direct file system access

**Requirements:**

- Directory must be writable by UID 1000 (default container user)
- Run: `sudo chown -R 1000:1000 /path/on/host/mixtape-data`

## 🔧 Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `PASSWORD` | **Yes** | *(none)* | Login password for the web interface |
| `APP_ENV` | **Yes** | `development` | Must be set to `production` for deployment |
| `MUSIC_ROOT` | No | `/music` | Container path to music (matches volume mount) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TZ` | No | `UTC` | Timezone for timestamps (e.g., `America/New_York`) |
| `PUID` | No | `1000` | User ID for file permissions |
| `PGID` | No | `1000` | Group ID for file permissions |

### Port Configuration

Default port mapping:

```yaml
ports:
  - "5000:5000"    # host:container
```

To use a different host port (e.g., 8080):

```yaml
ports:
  - "8080:5000"    # Access at http://localhost:8080
```

## 🌐 Running Behind a Reverse Proxy

For external access with HTTPS and a custom domain, use a reverse proxy.

### Traefik

Add these labels to your `docker-compose.yml`:

```yaml
services:
  mixtape:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mixtape.rule=Host(`mixtape.yourdomain.com`)"
      - "traefik.http.routers.mixtape.entrypoints=websecure"
      - "traefik.http.routers.mixtape.tls.certresolver=letsencrypt"
      - "traefik.http.services.mixtape.loadbalancer.server.port=5000"
```

**What this does:**

- Routes `mixtape.yourdomain.com` to your service
- Automatically obtains Let's Encrypt certificates
- Terminates TLS at the proxy level

### Nginx Proxy Manager

1. In NPM web interface, add a new Proxy Host
2. Set:
   - **Domain:** `mixtape.yourdomain.com`
   - **Forward Hostname:** `mixtape-society` (container name)
   - **Forward Port:** `5000`
   - **Enable SSL:** Yes (request Let's Encrypt certificate)

### Caddy

Create a `Caddyfile`:

```json
mixtape.yourdomain.com {
    reverse_proxy mixtape-society:5000
}
```

Caddy automatically handles HTTPS certificates.

### Tailscale with TSDProxy

If using Tailscale for private access:

```yaml
services:
  mixtape:
    # ... existing configuration ...
    environment:
      - TSDPROXY_ENABLE=true
      - TSDPROXY_HOST=mixtape.yourtailnet.ts.net
      - TSDPROXY_HTTP_PORT=5000
      - TSDPROXY_TLS_EMAIL=you@example.com
```

**What this does:**

- Exposes your service on your Tailscale network
- Automatically provisions TLS certificates
- Private access without exposing to public internet

## ⚠️ Troubleshooting

### Container Won't Start

**Check logs:**

```bash
docker compose logs
```

**Common causes:**

- Missing required environment variables (`PASSWORD`, `APP_ENV`)
- Port 5000 already in use
- Volume mount paths don't exist

### Music Library Not Indexing

**Verify music mount:**

```bash
docker compose exec mixtape ls -la /music
```

**Check permissions:**

- Container user (UID 1000) must be able to read music files
- For bind mounts: `chmod -R 755 /path/to/music`

**Monitor indexing progress:**

```bash
docker compose logs -f | grep -i index
```

### Cannot Access Web Interface

**Check container is running:**

```bash
docker compose ps
```

**Verify port mapping:**

```bash
docker compose port mixtape 5000
```

**Test from inside container:**

```bash
docker compose exec mixtape curl -I http://localhost:5000
```

### Permission Errors When Writing Data

**Verify volume ownership:**

```bash
# For bind mounts
ls -la /path/to/mixtape-data

# Should be owned by UID 1000
sudo chown -R 1000:1000 /path/to/mixtape-data
```

**Adjust container user (if needed):**

```yaml
environment:
  - PUID=1001
  - PGID=1001
```

### Database Corruption

If you encounter database errors:

1. **Stop the container:**

   ```bash
   docker compose down
   ```

2. **Backup current data:**

   ```bash
   docker run --rm -v mixtape_data:/data -v $(pwd):/backup \
     alpine tar czf /backup/mixtape-backup.tar.gz /data
   ```

3. **Reset database** (this will re-index your library):
   - Through web UI: Settings → Reset Database
   - Manual: Delete `collection.db` and restart

4. **Restore only mixtapes** (if needed):

   ```bash
   tar xzf mixtape-backup.tar.gz data/mixtapes/ --strip-components=1
   ```

### Audio Not Playing

**Check audio cache:**

```bash
docker compose exec mixtape ls -la /app/collection-data/cache/audio/
```

**Verify browser console for errors:**

- Open browser DevTools (F12)
- Check Console and Network tabs for failed requests

**Test direct audio access:**

```bash
curl -I http://localhost:5000/play/<mixtape-slug>/stream/<track-id>
```

## 📊 Monitoring and Maintenance

### View Logs

```bash
# Real-time logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Logs for specific time
docker compose logs --since="2024-01-20T10:00:00"
```

### Container Resource Usage

```bash
docker stats mixtape-society
```

### Backup Data

**Using named volume:**

```bash
docker run --rm \
  -v mixtape_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mixtape-backup-$(date +%Y%m%d).tar.gz /data
```

**Using bind mount:**

```bash
tar czf mixtape-backup-$(date +%Y%m%d).tar.gz /path/to/mixtape-data
```

### Restore Backup

```bash
docker compose down
docker run --rm \
  -v mixtape_data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/mixtape-backup.tar.gz --strip-components=1"
docker compose up -d
```

## 🔄 Upgrade Checklist

Before upgrading to a new version:

1. ✅ **Backup your data** (see above)
2. ✅ **Read release notes** for breaking changes
3. ✅ **Pull new image**: `docker compose pull`
4. ✅ **Restart**: `docker compose up -d`
5. ✅ **Verify functionality**: Check web interface and play a mixtape
6. ✅ **Monitor logs**: `docker compose logs -f` for any errors

## 📚 Related Documentation

- **[Local Development with Docker](../../development/docker-dev.md)**: For developers building and testing images
- **[Configuration Reference](../../development/configuration.md)**: Detailed explanation of all configuration options
- **[Installation Overview](installation.md)**: Alternative installation methods (non-Docker)
