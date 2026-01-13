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

### Smart features (without bloat)

- "Recently added" automatic mixtape
- Simple last.fm/scrobble support (optional)

### Transcoding optimizations

- Cache eviction policy (manual clear, LRU strategy)
- Range-request optimizations for large files

## 📱 Mobile Experience

- Pull-to-refresh on browse page
- PWA manifest + service worker → installable
- Cache current mixtape for offline playback
- Queue-based background download of tracks
- Super-light Flutter/Tauri app (webview + native controls)
- Background sync for offline actions
- Push notifications for new mixtapes
- Predictive caching based on listening patterns
- Differential updates (only changed tracks)
- Peer-to-peer sharing (WebRTC)
- Offline playlist editing (IndexedDB)
- Advanced compression (Opus codec)
- Smart preloading next track

## 💬 Sharing & Discovery

- Beautiful public mixtape embed (iframe)
- Optional short-url service integration
- Web Share API target

## 🖼️ Cover Art & Visuals

Image validation improvements:

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

### Base & UI

- Modular CSS (split by component)
- Accessibility improvements (ARIA, focus trapping)
- Internationalization (Flask-Babel)
- Progressive enhancement (JS fallbacks)

---

**Got thoughts on any of these?** Open a [discussion](https://github.com/mark-me/mixtape-society/discussions) or comment on [issues](https://github.com/mark-me/mixtape-society/issues).
