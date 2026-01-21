![Container](../images/deployment.png){ align=right width="90" }

# Local Development with Docker

This guide covers Docker usage for **local development and testing**. For production deployment, see the [Production Docker Guide](../user/creators/installation.md).

## 🔁 Development Workflow Overview

Mixtape Society supports three development approaches:

1. **Native Python with uv** (recommended for active development)
   - Fastest iteration cycle with hot-reload
   - Direct file system access
   - Run: `uv run app.py`

2. **Local Docker build** (for testing containerization)
   - Tests the production-like environment
   - Validates Dockerfile changes
   - Useful before pushing to CI/CD

3. **Docker Compose** (for full stack testing)
   - Tests volume mounts and networking
   - Validates environment variable handling
   - Simulates production deployment locally

## ⚙️ Configuration and Environments

The application uses three configuration classes defined in `config.py`:

### Configuration Classes

```python
# APP_ENV environment variable determines which config is loaded
CONFIG_MAP = {
    "development": DevelopmentConfig,  # Default for local dev
    "test": TestConfig,                # Used by test suite
    "production": ProductionConfig,    # Used in Docker containers
}
```

### Environment-Specific Behavior

| Environment | APP_ENV value | .env file loaded? | Default PASSWORD | DEBUG mode |
| ----------- | ------------- | ----------------- | ---------------- | ---------- |
| **Development** | `development` (default) | ✅ Yes (from project root) | `dev-password` | ✅ Enabled |
| **Test** | `test` | ❌ No | `test-password` | ❌ Disabled |
| **Production** | `production` | ❌ No | Must be set via env var | ❌ Disabled |

### Key Configuration Paths

All paths are derived from two base locations:

```python
# Set via environment variables or defaults
MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/music"))
DATA_ROOT = Path(os.getenv("DATA_ROOT", "../collection-data"))

# Automatically derived (never set these directly)
DB_PATH = DATA_ROOT / "collection.db"
MIXTAPE_DIR = DATA_ROOT / "mixtapes"
COVER_DIR = MIXTAPE_DIR / "covers"
AUDIO_CACHE_DIR = DATA_ROOT / "cache" / "audio"
```

### Local Development Setup

Create a `.env` file in the project root:

```bash
# .env (used only in development mode)
MUSIC_ROOT=/home/youruser/Music
DATA_ROOT=/home/youruser/mixtape-data  # Optional, defaults to ../collection-data
PASSWORD=my-dev-password               # Optional, defaults to dev-password
LOG_LEVEL=DEBUG                        # Optional, defaults to INFO
```

**Note:** The `.env` file is **only loaded in development mode** (when `APP_ENV != "production"`). In Docker containers, all configuration must come from environment variables or docker-compose.

## 🛠️ Building the Docker Image

### Standard Build

Build the production image locally to test Dockerfile changes:

```bash
# Build from project root
docker build -f docker/Dockerfile -t mixtape-society:dev .

# Or use the compose file's build configuration
docker compose -f docker/docker-compose.yml build
```

### Build Arguments

The Dockerfile supports custom user/group IDs:

```bash
docker build \
  --build-arg USER_ID=1000 \
  --build-arg GROUP_ID=1000 \
  -f docker/Dockerfile \
  -t mixtape-society:dev .
```

### Multi-stage Build Overview

The Dockerfile uses a multi-stage build process:

1. **Base stage**: Installs system dependencies (ffmpeg, image libraries)
2. **Builder stage**: Installs uv and Python dependencies
3. **Runtime stage**: Copies app code and creates non-root user
4. **Final stage**: Sets up entrypoint and exposes port 5000

## 🚀 Running with Docker Compose

### Development Compose File

Create `docker/docker-compose.dev.yml`:

```yaml
services:
  mixtape:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: mixtape-society-dev
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      # Mount your local music library (read-only)
      - /path/to/your/music:/music:ro
      # Mount data directory for persistence
      - mixtape_dev_data:/app/collection-data
      # Optional: mount source for live editing (requires manual restart)
      # - ../src:/app/src:ro
    environment:
      - APP_ENV=production          # Use production config in container
      - PASSWORD=dev-test-password
      - MUSIC_ROOT=/music           # Container path, not host path
      - LOG_LEVEL=DEBUG
      - TZ=Europe/Amsterdam

volumes:
  mixtape_dev_data:
```

### Start the Development Container

```bash
cd docker
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop and remove
docker compose -f docker-compose.dev.yml down
```

### Environment Variables Reference

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `APP_ENV` | No | `development` | Config class to use (`development`, `test`, `production`) |
| `MUSIC_ROOT` | Yes | `/music` | Path to music library inside container |
| `DATA_ROOT` | No | `/app/collection-data` | Path to persistent data inside container |
| `PASSWORD` | **Yes** (in production) | `dev-password` (dev only) | Login password for web UI |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TZ` | No | `UTC` | Timezone for timestamps |
| `PUID` / `PGID` | No | `1000` | User/group ID for file permissions |

## 🧪 Testing Configuration Changes

### Verify Configuration Loading

Run the container and check which config is active:

```bash
docker compose -f docker-compose.dev.yml exec mixtape python -c "
from config import get_configuration
config = get_configuration()
print(f'Config class: {config.__class__.__name__}')
print(f'MUSIC_ROOT: {config.MUSIC_ROOT}')
print(f'DATA_ROOT: {config.DATA_ROOT}')
print(f'DEBUG: {config.DEBUG}')
"
```

### Test Environment Switching

```bash
# Test development config
APP_ENV=development uv run python -c "from config import DevelopmentConfig; print(DevelopmentConfig.DEBUG)"

# Test production config
APP_ENV=production uv run python -c "from config import ProductionConfig; print(ProductionConfig.DEBUG)"
```

## 📋 Common Development Tasks

### Rebuild After Code Changes

Docker doesn't support hot-reload by default:

```bash
# Rebuild and restart
docker compose -f docker-compose.dev.yml up -d --build

# Or manually
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
```

**Tip:** For active development, use `uv run app.py` instead for instant hot-reload.

### Access Container Shell

```bash
docker compose -f docker-compose.dev.yml exec mixtape bash

# Or with docker directly
docker exec -it mixtape-society-dev bash
```

### Inspect Volume Contents

```bash
# Find the volume location
docker volume inspect mixtape_dev_data

# Access files (requires root on host)
sudo ls -la /var/lib/docker/volumes/mixtape_dev_data/_data/
```

### Reset Development Data

```bash
# Remove the volume (deletes DB, mixtapes, cache)
docker compose -f docker-compose.dev.yml down -v

# Start fresh
docker compose -f docker-compose.dev.yml up -d
```

## 🔄 CI/CD Integration

### GitHub Actions Build

The production images are automatically built on:

- Push to `main` branch → `latest` tag
- New release tags → version-specific tags (e.g., `v1.4.2`)

Images are published to GitHub Container Registry:

```bash
ghcr.io/mark-me/mixtape-society:latest
ghcr.io/mark-me/mixtape-society:v1.4.2
```

### Local Testing Before Push

Test the exact production build locally:

```bash
# Build with production settings
docker build -f docker/Dockerfile -t mixtape-society:test-prod .

# Run with production config
docker run --rm \
  -e APP_ENV=production \
  -e PASSWORD=test123 \
  -v /path/to/music:/music:ro \
  -v test_data:/app/collection-data \
  -p 5000:5000 \
  mixtape-society:test-prod
```

## 🩺 Troubleshooting

### Config Not Loading as Expected

```bash
# Check which .env files exist
ls -la .env

# Verify APP_ENV is set correctly
docker compose -f docker-compose.dev.yml exec mixtape env | grep APP_ENV

# Check if .env is being loaded (should be "no" in containers)
docker compose -f docker-compose.dev.yml exec mixtape python -c "
import os
print('APP_ENV:', os.getenv('APP_ENV', 'not set'))
print('.env loaded:', os.getenv('APP_ENV', 'development') != 'production')
"
```

### Permission Issues

```bash
# Check container user
docker compose -f docker-compose.dev.yml exec mixtape id

# Fix volume permissions (if using bind mount)
sudo chown -R 1000:1000 /path/to/data
```

### Database Not Persisting

```bash
# Verify volume is mounted
docker compose -f docker-compose.dev.yml exec mixtape ls -la /app/collection-data/

# Check if volume exists
docker volume ls | grep mixtape
```

## 📈 Performance Considerations

### When to Use Docker vs. Native

| Scenario | Recommended Approach | Reason |
| -------- | ------------------- | ------ |
| Active code iteration | Native (`uv run app.py`) | Hot-reload, faster startup |
| Testing Dockerfile changes | Local Docker build | Validates containerization |
| Testing volume mounts | Docker Compose | Simulates production setup |
| Integration testing | Docker Compose | Tests full stack |
| Final validation before release | Docker Compose | Production-like environment |

### Optimizing Build Times

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t mixtape-society:dev .

# Use compose BuildKit
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker compose build

# Cache the builder stage
docker build --target builder -t mixtape-society:builder -f docker/Dockerfile .
```

## 📚 Related Documentation

- **[Production Deployment](../user/creators/installation.md)**: Full Docker production setup with reverse proxy configuration
- **[Configuration Module](configuration.md)**: Detailed explanation of `config.py` and environment handling
- **[Project Architecture](intro.md)**: Overview of the application structure
