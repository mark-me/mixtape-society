# Mixtape Society

A beautiful, private, self-hosted web app to create, edit, share and play music mixtapes from your personal library.

![Mixtape Society screenshot](docs/images/screenshot-browse.png)

## Features

- Clean, modern UI (Bootstrap 5 + vanilla JS)
- Drag-and-drop mixtape editor
- Live search with highlighting
- Automatic or manual cover art
- Public shareable links (no login needed to play)
- Full seeking support for FLAC, MP3, M4A, etc.
- Simple single-password protection
- Background filesystem monitoring – always up-to-date
- Zero runtime external dependencies

## Quick Start

### Option 1: Local Development (uv + pyproject.toml – recommended)

This project uses `uv` for fast dependency management, with `pyproject.toml` for declarative builds and `.python-version` for tool versioning.

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society

# Install uv if needed: curl -LsSf https://astral.sh/uv/install.sh | sh

# uv handles venv, sync, and activation automatically
uv sync

# Copy and edit env
cp .env.example .env
# Edit .env → set MUSIC_ROOT and a strong password

# Run the app (first run indexes your library)
uv run python app.py
```

Your browser opens at [http://localhost:5000](http://localhost:5000)
Default dev password: `password`

### Option 2: Docker (production-ready)

Pre-built images are available on [GitHub Packages](https://github.com/mark-me/mixtape-society/pkgs/container/mixtape-society).

#### Quick Docker Run

```bash
# Pull the latest image
docker pull ghcr.io/mark-me/mixtape-society:latest

# Run with volume mounts for music and data
docker run -d \
  --name mixtape-society \
  -p 5000:5000 \
  -v /path/to/your/Music:/music:ro \
  -v ./mixtapes:/app/mixtapes \
  -v ./collection-data:/app/collection-data \
  -e MUSIC_ROOT=/music \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

#### With Docker Compose (recommended for persistence)

Copy docker-compose.yml (included in repo) and edit volumes/paths:

```bash
services:
  mixtape:
    build: .
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"                 # http://localhost:5000
    volumes:
      # Your music collection (read-only)
      - /home/mark/Music:/home/mark/Music:ro

      # Mixtapes + covers
      - mixtapes_data:/app/mixtapes

      # Collection database
      - collection_data:/app/collection-data
    environment:
      # Verander dit in een sterk wachtwoord!
      - PASSWORD=supergeheim123

      # Optioneel: logging level
      - FLASK_ENV=production
```

Then:

```bash
docker compose up -d
```

Access at [http://localhost:5000](http://localhost:5000). The image includes everything – no build needed.

## More information

[Github pages](https://mark-me.github.io/mixtape-society/)

## Environment Variables (.env)

| Variable    | Description                    | Example    |
| ----------- | --------------------------------| ---------- |
|APP_ENV      | "development, production, test" | production |
|MUSIC_ROOT   | Path to your music collection (absolute)|/mnt/music|
|DB_PATH      | SQLite database location        | /var/lib/mixtape-society/music.db |
|APP_PASSWORD | Login password (strongly recommended) | MySuperSecret123!
|MIXTAPE_DIR  | Mixtapes storage                | ./mixtapes

Load via .env file or Docker env vars.

## Supported Formats

MP3 • FLAC • M4A (AAC/ALAC) • OGG • WAV • WMA – powered by TinyTag.

## Tech Stack

* Backend: Flask + uv + pyproject.toml
* Metadata: TinyTag + SQLite + Watchdog
* Frontend: Bootstrap 5 + Sortable.js
* Deployment: Docker (multi-arch support)

## Copyright & Media Use

This project provides a Flask-based web application for managing and sharing metadata related to personal music libraries and mixtapes. The application is distributed as open-source software under the MIT License, and Docker images are provided for convenience.

No copyrighted music, cover art, or other media are included with this project or its Docker images.
Users are expected to supply their own legally obtained audio files.

By using this software, you agree that:

You are responsible for ensuring that any media files you import, host, or share comply with applicable copyright laws.

The maintainers of this project do not endorse or support the unauthorized distribution of copyrighted material.

The maintainer(s) are not liable for any misuse of this software, including illegal sharing of media files.

This project is a tool for organizing and interacting with your own music library.

## License

MIT – use it, hack it, share it.

See the [DISCLAIMER](./DISCLAIMER) for important legal information.

Made with love for real mixtapes in a digital world.
© 2025 Mark Zwart