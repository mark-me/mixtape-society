# The Mixtape Society

**Bringing mixtapes back — digitally.**
A beautiful, modern web app to create, manage, and share your own digital mixtapes — just like the old days, but better.

![Mixtape Revival](https://i.imgur.com/2rF9kP8.png)
*(Homepage in dark mode)*

## Features

- Clean, responsive UI with **Bootstrap 5**
- Light / **dark mode** (auto + manual toggle)
- Full **admin panel** (login required)
- Create, clone, edit, and delete mixtapes
- **Drag-and-drop** track reordering
- Add tracks from your own music library (MP3, FLAC, Ogg Vorbis)
- Automatic **metadata** reading (artist, title, album) via Mutagen
- Per-mixtape **cover art** upload
- Gorgeous **APlayer** with progress bar, artwork, and playlist view
- Unique shareable link for every mixtape
- Live **search** in the admin area
- Zero database – everything stored as tidy JSON files
- Fully containerized with **Docker & Docker Compose**

## Screenshots

| Home (light)        | APlayer             | Admin Editor         |
|---------------------|---------------------|----------------------|
| ![Home](https://i.imgur.com/Wx8vN1m.png) | ![Player](https://i.imgur.com/8YvR9pL.png) | ![Editor](https://i.imgur.com/kP3mXvZ.png) |

## Quick Start with Docker (recommended)

```bash
# 1. Clone the repo
git clone https://github.com/your-username/mixtape-revival.git
cd mixtape-revival

# 2. Create folders and add your music
mkdir music covers mixtapes
# Copy your MP3/FLAC/Ogg files into the music folder

# 3. Launch
docker-compose up -d --build

# 4. Open your browser
http://localhost:5000

Default admin login:
Username: admin
Password: password
Change these immediately in production!

## Run without Docker

```bash
git clone https://github.com/your-username/mixtape-revival.git
cd mixtape-revival

uv run app.py
```

## Directory structure

```bash
mixtapes/
├── music/          ← Put all your music files here
├── covers/         ← Auto-filled when you upload covers
├── mixtapes/       ← One JSON file per mixtape
├── src/
|    ├──templates/      ← HTML templates (Bootstrap)
|    └── app.py         ← Main Flask application
├── .python-version
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── uv.lock
```

## Security & Production tips

This project is designed as a **personal / hobby** application.
For real-world use:

* Change the hardcoded admin credentials (ADMIN_USERNAME / ADMIN_PASSWORD in app.py)
* Replace the simple login with a proper user database + password hashing
* Put behind a reverse proxy (Nginx, Caddy, Traefik) with HTTPS
* Restrict direct access to the /music folder

## Tech stack
* Python + Flask
* Bootstrap 5 + Bootstrap Icons
* APlayer (beautiful audio player)
* Sortable.js (drag & drop)
* Mutagen (metadata extraction)
* Docker & Docker Compose


License
MIT License – fork it, modify it, use it anywhere.

Mixtapes are back. And they sound better than ever.
Made with love and nostalgia
© 2025 – Mixtape Revival