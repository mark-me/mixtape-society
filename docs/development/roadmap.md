# Roadmap

## What NOT to add (to keep the soul of the project)

- No accounts on a central server
- No Spotify/Apple Music integration
- No social features (likes, comments, following)
- No ads, analytics, telemetry by default

## 1. Progressive Web App (PWA) + Offline Playback

- Add manifest.json + service worker → installable on phone/home screen
- Cache current mixtape for offline playback (big for mobile users on the go)
- Queue-based background download of mixtape tracks (zip or sequential)

## 2. Mobile Experience

- Fully responsive player controls (bottom-fixed on mobile)
- Swipe gestures in editor (remove track, reorder)
- Pull-to-refresh on browse page
- Dark mode (already half-there with Bootstrap, just add prefers-color-scheme)

## 3. Transcoding / Streaming Optimisation

- Optional on-the-fly transcoding to Opus 96-128kbps for mobile/low-bandwidth (using ffmpeg in Docker)
- HLS streaming fallback for very large FLAC files (>100 MB) to enable instant seeking
- Configurable bitrate ceiling per client (detect mobile → lower bitrate)

## 4. Smart Features (without becoming bloated)

- “Smart Mix” button → auto-generate mixtape by genre/mood/decade/BPM with simple filters
- “Recently added” automatic mixtape
- Play count + last played tracking (opt-in)
- Simple last.fm/scrobble support (optional)

## 5. Sharing & Discovery

- Beautiful public mixtape page with embed support (iframe)
- QR code for quick mobile sharing
- Optional short-url service (built-in or caddy/shlink integration)
- Web Share API target (native share button on mobile)

## 7. Cover Art & Visual Polish

- Fallback to folder.jpg / Cover.jpg / embedded art (already does this) → add auto-generated mosaic or gradient if missing
- Support for .webp covers (smaller files)

## 8. Multi-Library & Multi-User Support

- Support multiple MUSIC_ROOT paths (e.g., “Main” + “Vinyl Rips” + “Live Bootlegs”)
- User roles: admin + read-only “family” accounts

## 9. Backup & Portability

- One-click export of all mixtapes + cover art as .zip
- M3U export of mixtapes for use in other players
- Import from M3U playlists to create mixtapes

## 10. Developer/Deployment Experience

- Add Traefik/Caddy reverse-proxy example with HTTPS (Let’s Encrypt)
- Add healthcheck endpoint for Docker/Kubernetes
- Support for Podman as well as Docker
- Optional Redis cache for very large libraries (>50k tracks)

## 11. Tiny but Delightful Details

- Keyboard shortcuts (J/K for next/prev, space to play/pause, etc.)
- Click on album art in player → enlarge lightbox
- Show bitrate + file format in track list (hover or optional column)
- “Sleep timer” in player
- Random mixtape button on home page

## 12. Optional Companion Mobile App (future)

A super-light Flutter or Tauri app that just points to your self-hosted instance (basically a webview + native controls + background playback). Many users would love this.
