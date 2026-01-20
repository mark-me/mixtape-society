![Creator](../../images/mixtape.png){ align=right width="90" }

# Creator's Guide

Welcome to Mixtape Society! This guide will help you set up your server, create amazing mixtapes, and share them with the world.

---

## 📚 Complete Creator Journey

### 1. Installation & Setup

**[Installation Guide](installation.md)**

Choose your deployment method:

- **Docker (Recommended)** - Quick one-command setup
- **Docker Compose** - Production-ready with persistence
- **Local Development** - For contributors and testing

**What you'll need:**

- A music library (MP3, FLAC, etc.)
- Docker (or Python 3.11+ for local dev)
- 10 minutes for setup

---

### 2. Managing Your Collection

**[Collection Management](collection-management.md)**

Learn to:

- View your library statistics
- Resync after adding new music
- Understand what gets indexed
- Troubleshoot collection issues

**Key concepts:**

- Initial indexing vs. resyncing
- What metadata is extracted
- How album art is handled

---

### 3. Creating Mixtapes

**[Editor Guide](editor.md)**

Master the mixtape editor:

- Search and add tracks
- Reorder for perfect flow
- Customize cover art
- Write meaningful liner notes
- Save and get your share link

**Pro tips:**

- Keyboard shortcuts for efficiency
- Track reference syntax in liner notes
- Cover art best practices

---

### 4. Sharing Your Mixtapes

**[Sharing Guide](sharing.md)**

Share your creations:

- **Quick Share** - Simple links for casual sharing
- **Gift Experience** - Themed landing pages for special occasions
- **QR Codes** - For physical gifts and events

**Learn about:**

- Privacy and access control
- Permanent vs. temporary sharing
- Creative sharing ideas
- When to use each method

---

## 🎯 Common Tasks

### Creating Your First Mixtape

1. Log in to your server
2. Click "New Mixtape"
3. Search and add 5-10 favorite tracks
4. Add a title and optional liner notes
5. Click Save
6. Copy the link and share!

[Detailed walkthrough →](editor.md#how-to-create-a-mixtape)

### Adding New Music

1. Add files to your music directory
2. Log in to Mixtape Society
3. Click "Collection" in navigation
4. Click "Resync Library"
5. Wait for indexing to complete

[Full collection management →](collection-management.md)

### Sharing as a Gift

1. Create your mixtape
2. Click Save
3. Choose "Gift Experience"
4. Select Playful or Elegant theme
5. Copy the gift link
6. Share with your recipient

[Gift sharing details →](sharing.md#gift-experience-themed-landing-page)

---

## 🔧 Installation Quick Reference

### Docker One-Liner

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v /data/mixtape-society:/app/collection-data \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

### Docker Compose

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
      - mixtape_data:/app/collection-data
    environment:
      - APP_PASSWORD=${APP_PASSWORD}
      - APP_ENV=production

volumes:
  mixtape_data:
```

[Full installation guide →](installation.md)

---

## 💡 Best Practices

### Organizing Your Music Library

- Use consistent folder structure (Artist/Album/Tracks)
- Ensure proper ID3 tags (title, artist, album)
- Include album art in files when possible
- Use standard audio formats (MP3, FLAC, M4A)

### Creating Great Mixtapes

- **Flow matters** - Order tracks for emotional journey
- **Mix it up** - Vary tempo and mood
- **Liner notes** - Explain why you chose each song
- **Cover art** - Use strong visual that represents the mood
- **Length** - 10-15 tracks is the sweet spot

### Sharing Effectively

- **Context is key** - Add a personal message when sharing
- **Choose the right format**:
  - Quick link for casual shares
  - Gift theme for special occasions
  - QR code for physical presents
- **Privacy** - Only share with people you trust
- **Update when needed** - Edit mixtapes after sharing if needed

---

## 🆘 Troubleshooting

### Server Won't Start

**Check:**

- Docker is running
- Port 5000 isn't already in use
- Music directory path is correct
- You have sufficient disk space

[Detailed troubleshooting →](installation.md#common-gotchas-troubleshooting)

### Music Not Appearing

**Solutions:**

- Ensure files are in the mounted music directory
- Run a collection resync
- Check file formats are supported
- Verify file permissions

[Collection troubleshooting →](collection-management.md#troubleshooting)

### Sharing Link Not Working

**Verify:**

- Mixtape was saved successfully
- Server is accessible from outside your network
- Firewall allows inbound connections
- HTTPS setup is correct (if using)

[Sharing troubleshooting →](sharing.md#common-questions)

---

## ❓ Frequently Asked Questions

### How do I update my server?

```bash
docker compose pull
docker compose up -d --force-recreate
```

Your mixtapes and database are preserved in volumes.

### Can I edit a mixtape after sharing?

Yes! Edit anytime. The share link stays the same, and recipients see the updated version immediately.

### How much disk space do I need?

- **Database:** ~1MB per 1000 tracks
- **Cache:** Up to 2GB for transcoded audio (configurable)
- **Covers:** ~5MB per 100 mixtapes

### Can I run this on a Raspberry Pi?

Yes! Use the ARM-compatible Docker image. Works great on Pi 4 or newer.

### Is there a user limit?

No built-in limits. Performance depends on your server hardware and concurrent users.

[More FAQ →](faq.md)

---

## 📖 Next Steps

Ready to dive deeper? Check out:

- **[Installation Guide](installation.md)** - Full setup instructions
- **[Editor Guide](editor.md)** - Master the mixtape creation tools
- **[Sharing Guide](sharing.md)** - Learn all sharing options
- **[Collection Management](collection-management.md)** - Manage your music library

---

Happy mixtape making! 🎵
