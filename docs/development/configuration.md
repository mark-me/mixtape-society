# Configuration

![Configuration](../images/configuration.png){ align=right width="90" }

Configuration is via environment variables (or `.env` file for local runs). Docker images support all vars via `-e` flags.

|Scenario   |MUSIC_ROOT |DATA_ROOT / DB / mixtapes / covers | How it's set |
| ---       | ---       | ---                       | ---          |
| Local dev (no .env)| /home/mark/Music | ../collection-data (next to project) | config default |
| Local dev + .env | whatever you want | whatever you want |.env overrides |
| Docker production | /music (mounted) | /app/collection-data (mounted) | env vars from docker-compose |
| Tests | /tmp/test-music|/tmp/mixtape-test-data|TestConfig override |

## Docker Volumes

- `/music` `:ro` → Your music library (read-only)
- `/app/collection-data` → SQLite DB (persistent) + Saved mixtapes (persistent)

Example `docker-compose.yml` mounts these for you.

## Python Versioning

`.python-version` pins to 3.11+ for consistency. uv enforces this during `uv sync`.
