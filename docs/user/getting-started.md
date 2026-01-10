![Started](../images/rocket.png){ align=right width="90" }

# Getting Started

Launch your own Mixtape Society server and start crafting mixtapes from your music library.

We recommend **Docker** for most users: it is the quickest and most reliable way.

## 🚀 Quickest Way: One-Command Docker Run

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

→ Open [http://localhost:5000](http://localhost:5000), log in with your password, and let it index your library (check logs if needed: docker logs -f mixtape-society).

## 🏗️ Prefer Docker Compose or More Options?

See the full [Docker Deployment](docker.md) guide for:

- Docker Compose examples (with .env secrets)
- Persistent volumes setup
- HTTPS via reverse proxy
- Troubleshooting & tips

## 🛠️ Local Development (for contributors)

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society
uv sync
cp .env.example .env  # Edit MUSIC_ROOT and APP_PASSWORD
uv run python app.py
```

Opens at [http://localhost:5000](http://localhost:5000) (dev password: `dev-password`).

First run auto-indexes your library.

Enjoy the mixtape magic! 🚀
