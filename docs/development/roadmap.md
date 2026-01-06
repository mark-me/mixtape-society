![Roadmap](../images/roadmap.png){ align=right width="90" }

# Roadmap

## What NOT to add (to keep the soul of the project)

- No accounts on a central server
- No Spotify/Apple Music integration
- No social features (likes, comments, following)
- No ads, analytics, telemetry by default

## 0. Liner notes

- Background info for artist, album or track

## 1. Progressive Web App (PWA) + Offline Playback

- Add manifest.json + service worker → installable on phone/home screen
- Cache current mixtape for offline playback (big for mobile users on the go)
- Queue-based background download of mixtape tracks (zip or sequential)

## 2. Mobile Experience

- Pull-to-refresh on browse page

## 3. Transcoding / Streaming Optimisation

- HLS streaming fallback for very large FLAC files (>100 MB) to enable instant seeking
- Cache eviction policy
  - Manual clear via admin endpoint.
  - Implement an LRU or size‑based eviction strategy inside AudioCache.
- Range‑request optimisations
  - Reads the requested slice into memory (f.read(length)).
  - Stream directly from the file using werkzeug.wsgi.wrap_file for very large files.

## 4. Smart Features (without becoming bloated)

- “Smart Mix” button → auto-generate mixtape by genre/mood/decade/BPM with simple filters
- “Recently added” automatic mixtape
- Simple last.fm/scrobble support (optional)

## 5. Sharing & Discovery

- Beautiful public mixtape page with embed support (iframe)
- QR code for quick mobile sharing
- Optional short-url service (built-in or caddy/shlink integration)
- Web Share API target (native share button on mobile)

## 7. Cover Art & Visual Polish

- Cover format
    - Now Always JPEG, quality 100, max width 1200 px.
    - Add a configuration option (max_width, jpeg_quality, or even support PNG/WebP).
- Image validation
    - Now: Only checks that the string starts with `data:image`.
    - Verify MIME type (image/jpeg, image/png) before decoding, reject oversized payloads early.
- Async I/O
    - Now: All file operations are blocking.
    - Switch to aiofiles + async methods if you need non-blocking behavior in a high-throughput API server.                                                                                      |

## 8. Multi-Library & Multi-User Support

- Support multiple MUSIC_ROOT paths (e.g., “Main” + “Vinyl Rips” + “Live Bootlegs”)
- User roles: admin + read-only “family” accounts

## 9. Backup & Portability

- One-click export of all mixtapes + cover art as .zip
- M3U export of mixtapes for use in other players
- Import from M3U playlists to create mixtapes

## 10. Developer/Deployment Experience

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

## 13. Browser page

| Area | Current implementation | Suggested enhancements |
|------|----------------------|------------------------|
| Pagination | All mixtapes are loaded at once (`list_all`). | Add `limit`/`offset` parameters to `MixtapeManager.list_all` and UI pagination controls for large libraries. |
| Search | No search endpoint for mixtapes. | Introduce `/mixtapes/search?q=` that filters by title/artist, returning JSON for a live-search UI. |
| Bulk actions | Only single-item delete. | Add “Select → Delete” or “Export” bulk actions, with a new API endpoint (`POST /mixtapes/bulk_delete`). |
| Cover thumbnail generation | Covers are served directly from the file system. | Serve scaled thumbnails via a dedicated route (`/mixtapes/thumb/<slug>`) to reduce bandwidth on the browse page. |
| Permissions | All authenticated users can edit/delete any mixtape. | Tie mixtapes to a user ID (`owner_id`) and restrict edit/delete to the owner (or admins). |
| Progressive enhancement | JavaScript is required for copy/delete. | Provide graceful degradation (e.g., plain links for copy, a server-side delete confirmation page) for users with JS disabled. |

## 14. Base page and app

| Area | Current State | Suggested Improvements |
|------|---------------|------------------------|
| Theme persistence | Stored in `localStorage['theme']`. | Add a server-side preference (user profile) so the choice survives across devices. |
| Modular CSS | One monolithic `base.css`. | Split into component-level files (navbar, modals, toasts) and use a build step (e.g., PostCSS) for easier maintenance. |
| Accessibility | Basic ARIA attributes on modals/buttons. | Add `aria-live="polite"` to toasts, ensure focus trapping inside modals, and provide high-contrast color variants. |
| Internationalisation | Hard-coded English strings. | Integrate Flask-Babel and expose a `gettext` filter in Jinja to support multiple locales. |
| Progressive Enhancement | Many features rely on JavaScript (copy, delete, theme). | Provide graceful fallbacks: a plain link for copying (mailto fallback), a server-side confirmation page for delete, and a CSS-only dark-mode toggle. |
| Testing | No unit tests for `base.html` or the global JS. | Add Selenium / Playwright integration tests that verify the theme switcher, indexing modal, and database-corruption flow. |
| Security | CSRF protection is handled globally by Flask-WTF (not shown). | Ensure all POST endpoints (`/reset-database`, `/delete/<slug>`, `/resync`) validate a CSRF token. |
| Performance | All static assets are CDN-served individually. | Bundle CSS/JS with a tool like Webpack or Rollup, enable HTTP/2 server push, and add integrity attributes for Subresource Integrity (SRI). |

