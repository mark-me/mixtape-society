![Ideas](../../images/ideas.png){ align=right width="90" }

# Ideas & Exploration

Things I'm considering or that have been suggested. Some will happen, some won't, some need more thought before deciding.

## 🚫 What NOT to Add

To keep the soul of the project:
- No accounts on a central server
- No Spotify/Apple Music integration
- No social features (likes, comments, following)
- No ads, analytics, telemetry by default

## 🎵 Music & Playback

**Liner notes** - Background info for artist, album, or track

**Smart features** (without bloat)
- "Recently added" automatic mixtape
- Simple last.fm/scrobble support (optional)

**Transcoding optimizations**
- Cache eviction policy (manual clear, LRU strategy)
- Range-request optimizations for large files

## 📱 Mobile Experience

- Pull-to-refresh on browse page
- PWA manifest + service worker → installable
- Cache current mixtape for offline playback
- Queue-based background download of tracks
- Super-light Flutter/Tauri app (webview + native controls)

## 💬 Sharing & Discovery

- Beautiful public mixtape embed (iframe)
- ~~QR codes~~ ✅ *Shipped in v0.5.5*
- Optional short-url service integration
- Web Share API target

## 🖼️ Cover Art & Visuals

**Cover format options**
- Currently: JPEG, quality 100, max 1200px
- Consider: Configurable quality/format (WebP?)

**Image validation improvements**
- Better MIME checking
- Reject oversized payloads early
- Async I/O with aiofiles

## 👥 Multi-Library & Users

- Support multiple MUSIC_ROOT paths
- User roles: admin + read-only accounts

## 📦 Backup & Portability

- One-click export (all mixtapes + covers as .zip)
- M3U export for other players
- Import from M3U playlists

## 🛠️ Developer Experience

- Healthcheck endpoint for Docker/Kubernetes
- Podman support
- Optional Redis cache for huge libraries (>50k tracks)

## 🎨 Tiny Delights

- Keyboard shortcuts (J/K, space to play/pause)
- Click album art → enlarge lightbox
- Sleep timer in player
- Random mixtape button

## 🔧 Technical Improvements

### Browse Page
- Pagination for large libraries (currently loads all)
- Search endpoint (`/mixtapes/search?q=`)
- Bulk actions (select → delete/export)
- Thumbnail generation to reduce bandwidth
- Permissions (tie mixtapes to user ID)

### Base & UI
- Theme persistence across devices (server-side)
- Modular CSS (split by component)
- Accessibility improvements (ARIA, focus trapping)
- Internationalization (Flask-Babel)
- Progressive enhancement (JS fallbacks)

### QR Sharing
- Dynamic size selector
- Color theming
- Configurable cache headers
- Rate limiting
- SVG output option
- Hit counter analytics

---

**Got thoughts on any of these?** Open a [discussion](link) or comment on [issues](link)
