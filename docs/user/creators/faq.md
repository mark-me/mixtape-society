![FAQ](../images/faq.png){ align=right width="90" }

# Creator FAQ

Frequently asked questions for Mixtape Society creators and server administrators.

---

## 🚀 Installation & Setup

### How do I install Mixtape Society?

The easiest way is using Docker:

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

[Full installation guide →](installation.md)

### How do I update my server?

Using Docker Compose:

```bash
docker compose pull
docker compose up -d --force-recreate
```

Using Docker run:

```bash
docker pull ghcr.io/mark-me/mixtape-society:latest
docker stop mixtape-society
docker rm mixtape-society
# Run your original docker run command again
```

Your mixtapes and database are preserved in volumes.

### Can I run this on a Raspberry Pi?

**Yes!** Mixtape Society works great on Raspberry Pi 4 or newer.

**Requirements:**

- Raspberry Pi 4 (2GB+ RAM recommended)
- Docker installed
- External storage recommended for music library
- Stable power supply

**Performance notes:**

- Initial indexing may take longer
- Transcoding is slower than on desktop
- Works perfectly once library is indexed

### What are the minimum system requirements?

**Minimum:**

- 1GB RAM
- 2GB disk space (plus music library)
- Single-core CPU
- Docker or Python 3.11+

**Recommended:**

- 2GB+ RAM
- 10GB disk space (for cache and database)
- Multi-core CPU
- SSD storage

### How much disk space do I need?

**Base requirements:**

- Database: ~1MB per 1,000 tracks
- Audio cache: Up to 2GB (configurable)
- Cover images: ~5MB per 100 mixtapes
- Application: ~500MB

**Example:** 10,000-track library = ~50MB database + 2GB cache = ~2.5GB total

### Where is my data stored?

In Docker, data is stored in volumes:

**Collection data volume** (`/app/collection-data`):

- `collection.db` - SQLite database
- `mixtapes/` - JSON files for each mixtape
- `mixtapes/covers/` - Custom cover images
- `cache/audio/` - Transcoded audio files

**Music volume** (`/music`):

- Your original music files (read-only)
- Not modified by Mixtape Society

[Volume layout details →](installation.md#-data-storage)

---

## 🎵 Music Library Management

### What audio formats are supported?

**Supported formats:**

- ✅ MP3
- ✅ FLAC
- ✅ M4A / AAC
- ✅ OGG Vorbis
- ✅ WAV
- ✅ ALAC (Apple Lossless)
- ✅ WMA (Windows Media Audio)

**Not supported:**

- ❌ DRM-protected files
- ❌ Proprietary formats

### Why aren't my new files showing up?

New files won't appear until you resync your library.

**To resync:**

1. Log in to your server
2. Click **Collection** in navigation
3. Click **Resync Library**
4. Wait for indexing to complete

[Collection management guide →](collection-management.md)

### How often should I resync?

**Resync whenever you:**

- Add new music files
- Delete or move files
- Rename files or folders
- Update ID3 tags or metadata
- Notice missing tracks or incorrect data

**Note:** Resyncing is safe and can be done as often as needed. It doesn't affect existing mixtapes.

### Can I organize my music library while using Mixtape Society?

**Yes!** Your music library is mounted read-only, so Mixtape Society never modifies your files.

**You can safely:**

- Add new files
- Move files between folders
- Rename files or folders
- Update ID3 tags
- Delete files

**Just remember to resync after making changes.**

### What metadata does Mixtape Society use?

**Extracted from ID3 tags:**

- Track title
- Artist name
- Album name
- Track number
- Genre
- Year
- Album artist
- Duration
- Bitrate

**Extracted from files:**

- File path
- File size
- File modification date
- Embedded album art

### How do I add album art?

#### Method 1: Embed in files (recommended)

- Use a music tagger (Mp3tag, MusicBrainz Picard)
- Embed cover art directly in audio files
- Resync library

#### Method 2: Folder.jpg

- Place `folder.jpg` or `cover.jpg` in album folder
- Some taggers do this automatically
- Resync library

#### Method 3: Custom mixtape covers

- Upload when creating mixtape
- Overrides album art
- Specific to that mixtape

### Can I have multiple music libraries?

**Currently:** Only one music library path is supported per server instance.

**Workaround:**

- Mount multiple folders to subdirectories of `/music`
- Example: `/music/library1/`, `/music/library2/`
- All will be indexed together

**Alternative:**

- Run multiple Mixtape Society instances
- Each on different port
- Each with different music library

---

## 🎨 Creating Mixtapes

### How many tracks can a mixtape have?

**Technical limit:** 1,000 tracks (unlikely to reach)

**Practical recommendations:**

- **Short mixtape:** 5-10 tracks (~30-45 min)
- **Standard:** 10-15 tracks (~45-60 min)
- **Long:** 15-25 tracks (~1-2 hours)
- **Very long:** 25+ tracks (use sparingly)

**Note:** Longer mixtapes take more effort to listen through completely.

### Can I edit a mixtape after sharing?

**Yes!** You can edit anytime:

- ✅ Add or remove tracks
- ✅ Reorder tracks
- ✅ Change cover art
- ✅ Update liner notes
- ✅ Change title

**The share link stays the same** and recipients see updates immediately.

### What happens if I delete a mixtape?

**Immediate effects:**

- All share links stop working immediately
- Recipients can no longer access it
- Mixtape is permanently deleted
- Cover image is deleted
- Cannot be recovered

**Not affected:**

- Your music library remains unchanged
- Other mixtapes are unaffected
- Database statistics update

!!! warning "Permanent Deletion"
    There is no "undo" for deleting a mixtape. Make sure you're ready before confirming deletion.

### Can I duplicate a mixtape?

**Currently:** No built-in duplication feature.

**Workaround:**

1. Open the mixtape in editor
2. Manually recreate with same tracks
3. Copy liner notes
4. Upload same cover image

**Future feature:** One-click duplication is planned.

### How do I reference tracks in liner notes?

Use the track reference syntax:

**Single track:**

- `#1` → Becomes "Track Title by Artist"
- `#5` → Fifth track in the mixtape

**Range of tracks:**

- `#1-3` → First three tracks
- `#5-8` → Tracks 5 through 8

**Example liner notes:**

```text
This mixtape starts with #1, which reminds me of our road trip.
Tracks #3-5 are for when you need motivation.
And #12 is your favorite - had to include it!
```

[Editor guide →](editor.md)

---

## 🔗 Sharing & Access

### How long do share links last?

**Links are permanent** and never expire unless you:

- Delete the mixtape
- Shut down the server

**Links contain:**

- Mixtape slug (title)
- Creation date
- Unique random ID

### Can I see who's listening to my mixtapes?

**No.** Mixtape Society does not track listeners:

- No analytics
- No view counts
- No listener identification
- Complete privacy for recipients

**This is by design** to protect recipient privacy.

### Can I password-protect a mixtape?

**Currently:** No password protection feature.

**Access control is through:**

- Link privacy (unguessable URLs)
- Sharing only with trusted people
- Deleting mixtapes when needed

**Workaround for privacy:**

- Only share links privately
- Delete and recreate if link is compromised
- Use a reverse proxy with authentication

### What if someone shares my link publicly?

**If a link is shared publicly:**

1. Delete the mixtape immediately
2. This breaks all links (including the public one)
3. Create a new mixtape
4. Share new link only with trusted people

**Prevention:**

- Only share with people you trust
- Use private communication channels
- Remind recipients not to share further

### Can I create temporary/expiring links?

**Currently:** No built-in link expiration.

**All links are permanent** until the mixtape is deleted.

**Future consideration:** Temporary links may be added in future versions.

### How do gift links work?

Gift links are the same URL as direct links, but displayed differently in your sharing modal.

**When you choose "Gift Experience":**

1. You select a theme (Playful or Elegant)
2. The link includes a parameter for the theme
3. Recipients see themed landing page
4. Same link, different presentation

**The recipient experience includes:**

- Themed landing page
- Cover art showcase
- Liner notes display
- "Unwrap" or "Open" button

[Full sharing guide →](sharing.md)

---

## ⚙️ Configuration & Customization

### How do I change my admin password?

**Docker Compose:**

1. Edit `.env` file
2. Change `APP_PASSWORD` value
3. Restart container: `docker compose up -d`

**Docker run:**

1. Stop container: `docker stop mixtape-society`
2. Remove container: `docker rm mixtape-society`
3. Run again with new `-e APP_PASSWORD=NewPassword`

**Local development:**

1. Edit `.env` file
2. Change `APP_PASSWORD` value
3. Restart application

### Can I customize the appearance?

**Currently:** Limited customization options.

**What you can customize:**

- Server name (in config)
- Password
- Logo (by modifying static files)

**Future plans:**

- Theme customization
- Color schemes
- Custom branding

### How do I enable HTTPS?

**Recommended:** Use a reverse proxy (Traefik, Nginx, Caddy)

**Example with Traefik:**
[See installation guide →](installation.md#-running-behind-a-reverse-proxy)

**Not recommended:**

- Built-in Flask HTTPS (development only)
- Self-signed certificates

### Can I run multiple servers?

**Yes!** You can run multiple instances:

**Use cases:**

- Different music libraries
- Separate family vs. friends servers
- Test vs. production
- Different geographic locations

**Requirements:**

- Different ports for each instance
- Separate data volumes
- Unique passwords

**Example:**

```bash
# Server 1 - Personal
docker run -d --name mixtape-personal -p 5000:5000 ...

# Server 2 - Family
docker run -d --name mixtape-family -p 5001:5000 ...
```

---

## 🔧 Technical Issues

### Initial indexing is taking forever

**This is normal for large libraries.**

**Expected times:**

- 1,000 tracks: 2-5 minutes
- 10,000 tracks: 15-30 minutes
- 50,000 tracks: 1-2 hours
- 100,000+ tracks: Several hours

**What affects speed:**

- CPU speed
- Disk speed (SSD vs HDD)
- File formats (FLAC takes longer)
- Embedded artwork size

**Check progress:**

```bash
docker logs -f mixtape-society
```

### Database corruption after crash

**Symptoms:**

- Server won't start
- Database errors in logs
- Mixtapes won't load

**Recovery:**

1. Stop the server
2. Backup data volume
3. Delete `collection.db`
4. Restart server (triggers re-index)
5. Mixtapes are preserved (stored in JSON)

**Prevention:**

- Use `restart: unless-stopped` in Docker
- Proper shutdown procedures
- Don't kill Docker containers

### Audio cache keeps filling up

**Cache behavior:**

- Caches transcoded audio
- Grows over time with usage
- Automatically managed (LRU)

**If cache is too large:**

**Option 1:** Clear cache manually

```bash
docker exec mixtape-society rm -rf /app/collection-data/cache/audio/*
```

**Option 2:** Disable cache

```yaml
environment:
  - AUDIO_CACHE_ENABLED=false
```

**Option 3:** Reduce cache size (future feature)

### Cannot access from other devices

**Common causes:**

**Firewall blocking:**

- Check host firewall settings
- Allow port 5000 inbound
- Check Docker firewall rules

**Port not published:**

- Verify `-p 5000:5000` in docker run
- Check `ports:` in docker-compose.yml

**Wrong IP address:**

- Use server's local IP, not localhost
- Find IP: `ip addr` or `ifconfig`
- Example: `http://192.168.1.100:5000`

**Docker network mode:**

- Use bridge mode (default)
- Avoid host-only network

### Mixtapes won't play

**Check:**

1. Original music files still exist
2. File permissions are correct
3. Music directory is mounted
4. No file corruption

**Debug:**

```bash
# Check if music is accessible
docker exec mixtape-society ls /music

# Check logs
docker logs mixtape-society
```

---

## 📊 Performance & Scaling

### How many users can my server handle?

**Depends on:**

- Server hardware
- Number of concurrent streams
- Quality settings
- Network bandwidth

**Rough estimates:**

- Raspberry Pi 4: 2-5 concurrent users
- Basic VPS: 5-10 concurrent users
- Dedicated server: 20+ concurrent users

**Bottlenecks:**

- CPU (for transcoding)
- Network bandwidth
- Disk I/O
- RAM (minimal impact)

### Can I upgrade without losing data?

**Yes!** Data is preserved in Docker volumes.

**Safe to upgrade:**

- ✅ Mixtapes (stored in JSON)
- ✅ Database (SQLite file)
- ✅ Cover images
- ✅ Audio cache (can be cleared)
- ✅ Configuration

**Process:**

```bash
docker compose pull
docker compose up -d
```

### Should I use SSD or HDD for storage?

**For music library:**

- HDD is fine
- Read-mostly workload
- Size matters more than speed

**For database/cache:**

- SSD recommended
- Faster indexing
- Better concurrent access
- Quicker cache reads

**Ideal setup:**

- Music on HDD (larger capacity)
- Database/cache on SSD (better performance)

---

## 💡 Best Practices

### How should I organize my music library?

**Recommended structure:**

```bash
/music/
  ├── Artist Name/
  │   ├── Album Name/
  │   │   ├── 01 - Track Name.mp3
  │   │   ├── 02 - Track Name.mp3
  │   │   └── cover.jpg
  │   └── Another Album/
  └── Another Artist/
```

**Key principles:**

- Consistent folder naming
- Complete ID3 tags
- Embed album art when possible
- Use standard formats

### How often should I backup?

**Critical data to backup:**

- Database (`collection.db`)
- Mixtape JSON files (`mixtapes/*.json`)
- Custom cover images (`mixtapes/covers/`)

**Recommended schedule:**

- Weekly backups for active servers
- Before major updates
- After creating important mixtapes

**Docker backup:**

```bash
# Backup entire data volume
docker run --rm \
  -v mixtape_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mixtape-backup.tar.gz /data
```

### Should I use Docker or local installation?

**Use Docker if:**

- ✅ You want easy setup
- ✅ You're deploying to production
- ✅ You want easy updates
- ✅ You need isolation

**Use local if:**

- You're developing/contributing
- You need custom modifications
- You're testing new features
- You prefer direct access

**Recommendation:** Docker for 95% of users.

---

## 📚 Additional Resources

- **[Installation Guide](installation.md)** - Full setup instructions
- **[Editor Guide](editor.md)** - Creating mixtapes
- **[Collection Management](collection-management.md)** - Managing your library
- **[Sharing Guide](sharing.md)** - Sharing options
- **[GitHub Issues](https://github.com/mark-me/mixtape-society/issues)** - Report bugs or request features

---

Still have questions? Ask in [GitHub Discussions](https://github.com/mark-me/mixtape-society/discussions)!
