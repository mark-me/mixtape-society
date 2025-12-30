# 📼 Mixtape Society

**A private, self-hosted web app to create, edit, share and play music mixtapes from your personal library.**

No accounts, no telemetry, no Spotify – just your music, your server, your rules.

![Mixtape Society screenshot](docs/images/screenshot-browse.png)

## ✨ Features

- Clean, modern UI (Bootstrap 5 + vanilla JS)
- Drag-and-drop mixtape editor
- Live search with highlighting
- Automatic or manual cover art
- Public shareable links (no login needed to play)
- Full seeking support for FLAC, MP3, M4A, etc.
- Simple single-password protection
- Background filesystem monitoring – always up-to-date
- Zero runtime external dependencies

## 🚀 Quick Start

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

Open [http://localhost:5001](http://localhost:5001) – Done!

## 📖 Project docs

- [🚀 Getting Started](https://mark-me.github.io/mixtape-society/getting-started.html)
- [📖 Full Documentation](https://mark-me.github.io/mixtape-society/index.html)
- [🐳 Docker Deployment](https://mark-me.github.io/mixtape-society/docker.html)
- [🙌 Acknowledgements](https://mark-me.github.io/mixtape-society/about.html#acknowledgements)

## Legal & Copyright Notice

This software is a tool for personal, non-commercial use with legally owned music files.

No copyrighted music or artwork is included
You are solely responsible for the media you host and share
Public links should only be shared with people you trust or protected with a password

See [DISCLAIMER](./DISCLAIMER) for full text.

Made with love for real mixtapes in a digital world.


