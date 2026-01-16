![Container](../images/container.png){ align=right width="90" }

# Local Development with Docker

While uv is recommended for local dev (faster iteration), Docker is great for testing production-like environments.

!!! INFO
    For production deployment with Docker, see the [Production Docker Guide](../user/docker-deployment.md)

## Building the Image

How to build the Docker image locally:

```bash
docker build -f docker/Dockerfile -t mixtape-society:dev .
# Or with compose: docker compose -f docker/docker-compose.yml build
```

Run: `docker compose up` (mount volumes as needed).
Note: No hot-reload—use `uv run app.py` for that. Prod images are auto-built on main pushes via GitHub Actions.
For full deployment, see Deployment.