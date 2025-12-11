# Mixtape Society

**A beautiful, private, self-hosted web app to create, edit, share and play music mixtapes from your personal library.**

No accounts, no telemetry, no Spotify – just your music, your server, your rules.

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

### Option 1 – Docker (recommended for production)

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v mixtape_data:/app/mixtapes \
  -v collection_data:/app/collection-data \
  -e MUSIC_ROOT=/music \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

Open [http://localhost:5000](http://localhost:5000) – Done!

### Option 2 – Docker Compose (best for long-term)

```yaml
# docker-compose.yml
services:
  mixtape:
    image: ghcr.io/mark-me/mixtape-society:latest
    container_name: mixtape-society
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /home/you/Music:/music:ro          # ← change this
      - mixtapes:/app/mixtapes
      - db:/app/collection-data
    environment:
      - MUSIC_ROOT=/music
      - APP_PASSWORD=changeme-right-now-please!
      - FLASK_ENV=production

volumes:
  mixtapes:
  db:

```

Then run:

```bash
docker compose up -d
```

### Option 3: Local Development (uv)

```bash
git clone https://github.com/mark-me/mixtape-society.git
cd mixtape-society
uv sync                    # creates venv + installs deps
cp .env.example .env
# ← Edit MUSIC_ROOT and APP_PASSWORD
uv run python app.py
```

→ opens at [http://localhost:5000](http://localhost:5000) (Default dev password: `password`)

## Project docs

- **[Changelog](https://mark-me.github.io/mixtape-society/changelog/)** – What’s new in every release
- **[Development Setup & Contributing](https://mark-me.github.io/mixtape-society/development/intro.html)**
-
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

## Legal & Copyright Notice

This software is a tool for personal, non-commercial use with legally owned music files.

No copyrighted music or artwork is included
You are solely responsible for the media you host and share
Public links should only be shared with people you trust or protected with a password

See [DISCLAIMER](./DISCLAIMER) for full text.

Made with love for real mixtapes in a digital world.
© 2025 Mark Zwart