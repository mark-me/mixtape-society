![Changelog](../images/changelog.png){ align=right width="90" }

# Changelog

All notable changes to Mixtape Society are documented here. We follow [Semantic Versioning](https://semver.org/) and the spirit of [Keep a Changelog](https://keepachangelog.com/).

Each release rewinds and fast-forwards your mixtape experience—just like a real cassette! 🎧

## 📦 v0.8.2

<span class="md-tag">Release</span>

**🗓️** 2026-11-11

### 🐛 Fixed

- Shared mixtapes with track covers didn't open
- Indexing page failed for a logged-in owner
- Play button in the mixtape overview didn't work

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.8.1...v0.8.2)

---

## 📦 v0.8.1

<span class="md-tag">Release</span>

**🗓️** 2026-11-01

### 🔧 Changed

- Documentation moved from MkDocs to Zensical, with a new look; the image lightbox, zooming in diagrams and last-changed dates are gone
- Simplified diagrams that were hard to read
- Updated dependencies

### 🐛 Fixed

- Help now shows diagrams and its own fonts without internet
- Diagram on the audio playback overview didn't render
- Corrected several diagrams and outdated statements in the documentation

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.8.0...v0.8.1)

---

## 📦 v0.8.0

<span class="md-tag">Release</span>

**🗓️** 2026-11-01

!!! warning "Before you upgrade"
    The container now runs as user `1000`, so data written by an older image has to be handed over once, or the app won't start: `sudo chown -R 1000:1000 ./collection-data`. See the [installation guide](../user/creators/installation.md) for named volumes. The example Compose file now reads `PASSWORD` from `docker/.env`. Everyone is logged out once.

### ✨ Added

- Help is now part of the app: it opens the documentation of the version you run, also without internet
- Automated tests and code checks on every pull request and before every Docker image
- Vulnerability scans of the Python packages and the Docker image, and weekly dependency updates by Dependabot
- Docker health check
- `SESSION_COOKIE_SECURE` setting for installs that are only reached over HTTPS

### 🔧 Changed

- Docker image is much smaller and runs as a non-root user, read-only in the example Compose file
- Security headers on every response; requests from other sites that change something are refused
- Updated packages, including Pillow 13, CairoSVG 2.9.1 and Werkzeug 3.1.9 for security fixes
- Moved system and cover routes out of `app.py` into their own blueprints
- New logo and a more pronounced favicon
- Improved readability of the documentation

### 🐛 Fixed

- Password could be guessed offline from a session cookie: sessions are now signed with a separate random key
- App now refuses to start in production without a `PASSWORD`
- Resetting the database left the app working with the old, closed collection
- Pushing to `master` didn't build a Docker image
- Documentation build failing on pages that referred to code that wasn't there

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.5...v0.8.0)

---

## 📦 v0.7.5

<span class="md-tag">Release</span>

**🗓️** 2026-01-26

### 🔧 Changed

- Refactored playerControl.js, split across more files
- Restructuring documentation

### 🐛 Fixed

- Playback stops on mobile
- Reusing indexing for tracking playback across multiple mixtapes

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.4...v0.7.5)

---

## 📦 v0.7.4

<span class="md-tag">Release</span>

**🗓️** 2026-01-25

### 🔧 Changed

- Removed cover upload limit
- Added artist to track label for compilation albums
- Speeded up quering by improving indexes, batching count queries and batching compilcation detection

### 🐛 Fixed

- With new mixtape, every save results in a new one
- Bottom player play button doesn't resume track after page reload
- Playback stops on mobile

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.3...v0.7.4)

---

## 📦 v0.7.3

<span class="md-tag">Release</span>

**🗓️** 2026-01-24

### ✨ Added

- Sleep timer

### 🐛 Fixed

- Some Android devices stopped playback when track ended

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.2...v0.7.3)

---

## 📦 v0.7.2

<span class="md-tag">Release</span>

**🗓️** 2026-01-23

### ✨ Added

- Add confirmation modal when emptying mixtape

### 🔧 Changed

- Centralized toast system for better consistency

### 🐛 Fixed

- Chromecasting
- Android Auto

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.1...v0.7.2)

---

## 📦 v0.7.1

<span class="md-tag">Release</span>

**🗓️** 2026-01-22

### ✨ Added

- Shuffle option for receiver
- Repeat mode (off/all/one)

### 🗑️ Removed

- Onboarding tooltips (too little under control to be useful)

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.7.0...v0.7.1)

---

## 📦 v0.7.0

<span class="md-tag">Release</span>

**🗓️** 2026-01-21

### ✨ Added

- Gift receiver experience!
- Help pages for users
- Resuming playback on reload

### 🐛 Fixed

- Made playback more resistant against temporary network failures
- Play button on bottom didn't properly show on mobile devices with a light theme

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.6.0...v0.7.0)

---

## 📦 v0.6.0

<span class="md-tag">Release</span>

**🗓️** 2026-01-19

### ✨ Added

- Prefetching next song data for improved song switching.

### 🐛 Fixed

- Android car not showing in car.

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.9...v0.6.0)

---

## 📦 v0.5.9

<span class="md-tag">Release</span>

**🗓️** 2026-01-17

### 🐛 Fixed

- Limiter only applied to login page
- PWA manifest was not dynamic, so would not work for received shared mixtapes

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.8...v0.5.9)

---

## 📦 v0.5.8

<span class="md-tag">Release</span>

**🗓️** 2026-01-16

### ✨ Added

- Added Android Auto support
- Size-optimized cover generation
- Mechanical click sound effect for cassette mode
- Lots of extra and restructured documentation

### 🐛 Fixed

- The artist's album accordions in the search results went missing since v0.5.7

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.7...v0.5.8)

---

## 📦 v0.5.7

<span class="md-tag">Release</span>

**🗓️** 2026-01-13

### ✨ Added

- Added PWA (Progressive Web App) support for offline playback and installation
- Added ChromeCast support for playback

### 🐛 Fixed

- Allow searching for strange characters in artist/album/track names
- Type 3 characters to start searching -> 2 characters

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.6...v0.5.7)

---

## 📦 v0.5.6

<span class="md-tag">Release</span>

**🗓️** 2026-01-11

### ✨ Added

- Multi-Architecture Docker Build Setup

### 🐛 Fixed

- Slug sanitation for mixtape titles with spaces and non-URL-safe characters
- Centered QR code in modal

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.5...v0.5.6)

---

## 📦 v0.5.5

<span class="md-tag">Release</span>

**🗓️** 2026-01-09

### ✨ Added

- Sharing through QR codes on browse, editor and playback pages
- Filtering and sorting on the mixtape browsing page

### 🔧 Changed

- Changed search bar for the mixtape editor

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.4...v0.5.5)

---

## 📦 v0.5.4

<span class="md-tag">Release</span>

**🗓️** 2026-01-07

### 🐛 Fixed

- Color cassette tape strip

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.3...v0.5.4)

---

## 📦 v0.5.3

<span class="md-tag">Release</span>

**🗓️** 2026-01-07

### ✨ Added

- Immersive walkman mode on mobile

### 🐛 Fixed

- Restored mobile notification pause/play functionality

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.2...v0.5.3)

---

## 📦 v0.5.2

<span class="md-tag">Release</span>

**🗓️** 2026-01-06

### ✨ Added

- Mixtape cover resizing to reduce bandwidth needs
- Added cassette tape look option to playback

### 🔧 Changed

- Normalize cover images to RGB and handle transparency correctly before saving as JPEG, while slightly adjusting JPEG output settings.

### 🐛 Fixed

- Prevent unnecessary resizing of small cover images

[Changes since last version](https://github.com/mark-me/mixtape-society/compare/v0.5.1...v0.5.2)

---

## 📦 v0.5.1

<span class="md-tag">Release</span>

All notable changes to Mixtape Society are documented here. We follow [Semantic Versioning](https://semver.org/) and the spirit of [Keep a Changelog](https://keepachangelog.com/).

Each release rewinds and fast-forwards your mixtape experience—just like a real cassette! 🎧

**🗓️** 2026-01-04

### ✨ Added

- Adaptive theming based on the mixtape cover for playback

[v0.5.1](https://github.com/mark-me/mixtape-society/compare/v0.5.0...v0.5.1)

---

## 📦 v0.5.0

<span class="md-tag">Release</span>

**🗓️** 2026-01-04

### ✨ Added

- Modal for statistics on the entire collection
- Improved details in editor for compilation albums
- Enlarged album cover in album details
- Hierarchical hints in search results
- User are alerted on broken DB and can rebuild from UI -> Shared mixtapes still usable while DB is being rebuilt

### 🔧 Changed

- Moved the resync button to the statistics modal
- Handling of compilation albums is now uniform

### 🐛 Fixed

- Database resync corrupts database
- Watcher corrupts database when changing lots of files in the music collection
- Type 2 characters to start searching -> 3 characters
- Top of search bar focus ring cut-off on top
- Title of mixtape falls off the screen
- Navbar on mobile across two rows

[v0.5.0](https://github.com/mark-me/mixtape-society/compare/v0.4.1...v0.5.0)

---

## 📦 v0.4.1

<span class="md-tag">Release</span>

**🗓️** 2026-01-02

### ✨ Added

- Fallback cover art
- Cover art for track search results
- Cover art in mobile notification

### 🔧 Changed

- CSS changed to sematic color system
- Cleaning up editor and player javascript

[v0.4.1](https://github.com/mark-me/mixtape-society/compare/v0.4.0...v0.4.1)

---

## 📦 v0.4.0

<span class="md-tag">Release</span>

**🗓️** 2026-01-01

### ✨ Added

- Floating buttons in editor for mobile to:
    - Jump to mixtape tracks
    - Save changes
- Added button for manual resyncing the music collection library

### 🐛 Fixed

- Saving existing mixtapes results in error
- Covers not available for non-admin users
- Playback notification on Mobile progress not in sync with actual playback position.

[v0.4.0](https://github.com/mark-me/mixtape-society/compare/v0.3.0...v0.4.0)

---

## 📦 v0.3.0

<span class="md-tag">Release</span>

**🗓️** 2026-01-01

### ✨ Added

- Covers included for tracks
- Composite cover generation
- Track removal toast

### 🔧 Changed

- Play buttons changed to cover-play buttons

### 🐛 Fixed

- Reordering tracks resulted in track added toast.
- White theme browsing mixtapes, mixtape title invisible
- No version information extracted from the repository

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.2.5...v0.3.0)

---

## 📦 v0.2.5

<span class="md-tag">Release</span>

**🗓️** 2025-12-30

### ✨ Added

- Creating cached versions of FLAC's converted to lower (but listenable) quality when creating a mixtape
- Option to let the user choose higher quality playback

### 🔧 Changed

- Updated documentation

### 🐛 Fixed

- When searching with multiple words, the results narrows down
- Player control text is illegible in the white theme
- Editor search result play preview button not in sync with player controls

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.2.2...v0.2.5)

---

## 📦 v0.2.2

<span class="md-tag">Release</span>

**🗓️** 2025-12-28

### ✨ Added

- Possibility to expand the tracks/liner notes for easier reordering and writing notes.
- Duration of playlist items added

### 🔧 Changed

- Mixtape player page:
    - Playback track layout so it looks better on mobile devices
    - Decreased space for controls on mobile devices
    - More track information in the audio player
- Mixtape editor page
    - Search results layout in editor looks better on mobile devices
    - Removed redundant labels from artist and album search results
    - Made player in editor consistent with player_mixtape

### 🐛 Fixed

- Track title not rendering on playlist

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.2.1...v0.2.2)

---

## 📦 v0.2.1

<span class="md-tag">Release</span>

**🗓️** 2025-12-27

### 🐛 Fixed

- Mixtapes editing made more uniform and robust against network failures, resulted in fatal crash
- Fixed album sorting for artists to case insensitive
- Made cover validation more robust

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.2.0...v0.2.1)

---

## 📦 v0.2.0

<span class="md-tag">Release</span>

**🗓️** 2025-12-27

### 🔧 Changed

- OpenGraph image and added information to better comply with standards [https://opengraph.dev/](https://opengraph.dev/)
- Changing the title of the mixtape is independent of the filename of the stored mixtape. This ensures keeping the old shared URL alive when changing the title.
- Navbar to sticky-top

### 🐛 Fixed

- Collapse of the navbar happens only on small screens
- Better player display on smaller screens
- Redundant JavaScript removed from editor.html

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.8-alpha...v0.2.0)

---

## 📦 v0.1.8-alpha

<span class="md-tag">Unreleased</span>

**🗓️** 2025-12-26

### ✨ Added

- Using tags while searching
    - Artist
    - Album
    - Song
- Track sorting for albumns by disc and track number
- Clickable search results so you can change the search to an artist or album
- Logo in social card cover image
- Cache pass-1 results between keystrokes, keep the results of Pass 1 (scored rows) around temporarily, so increasing the precision of your search  doesn't need to hit the database again.
- Added robot.txt to disallow page indexing by search engines

### 🔧 Changed

- Extracted JavaScript from Jinja templates to `static/js`
- Liner notes before tracks list
- Remove track icon
- Removed theme label from navbar
- Documentation images update
- Large cover files are scaled down to save bandwidth
- Sped up searching
- Better mixtape editing
- When indexing the music library, Ajax reloading is used to reduce page reloads

### 🐛 Fixed

- Player does not adhere to light/dark theming
- Possible mixtape collision
- Loading at first start-up in musiclib
- Progress report on loading in musiclib

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.7-alpha...v0.1.8-alpha)

---

## 📦 v0.1.7-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-18

### ✨ Added

- Editing previews - each track in the search-result can be played without adding them to the playlist
- Project link in navbar

### 🔧 Changed

- Logo and favicon
- Documentation line-up with app style

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.6-alpha...v0.1.7-alpha)

---

## 📦 v0.1.6-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-17

### 🔧 Changed

- Extracted CSS to dedicated files in static, and added comments with clear flow

### 🐛 Fixed

- Covers not showing for users that are not logged in
- Editor headers change according to creating or editing mixtape

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.5-alpha...v0.1.6-alpha)

---

## 📦 v0.1.5-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-17

### ✨ Added

- Grouping search results:
  - Nesting for Artists: Artists show as top-level headers with summaries (e.g., "2 album(s)", "5 nummer(s)").
  - Albums are nested in an accordion below, each with their own header and collapsible tracks.
  - Folding Tracks: Tracks are hidden by default under a collapsible section (accordion for nested albums, simple collapse for standalone albums). Click the header/button to expand.

### 🔧 Changed

- Moved from JavaScript dialogs to Bootstrap dialogs

### 🐛 Fixed

- Fixed Dockerfile by starting app from factory function

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.4-alpha...v0.1.5-alpha)

---

## 📦 v0.1.4-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-16

### ✨ Added

- Page that informs user at first startup on the progress of music library scraping

### 🔧 Changed

- Music library extraction backend (Musiclib)
- Huge overhaul of back-end, making modules less interdependent

### 🐛 Fixed

- Missing standard cover art
- Theme adherence on some pages
- Favicon theme adherence
- Deleting a mixtape actually works

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.3-alpha...v0.1.4-alpha)

---

## 📦 v0.1.3-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-15

### ✨ Added

- Creating liner notes for a mixtape
- Pop-up when adding tracks to a mixtape
- Share mixtape from play page
- Social card metadata for mixtapes

### 🐛 Fixed

- Moving away from editing a mixtape then returning would lose changes

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.2-alpha...v0.1.3-alpha)

---

## 📦 v0.1.2-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-12

### 🐛 Fixed

- Made Mixtape browser responsive

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.1-alpha...v0.1.2-alpha)

---

## 📦 v0.1.1-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-12

### ✨ Added

- Included version information from git tags
- Docker logging
- Rate limiting for login

### 🔧 Changed

- Improved music path handling
- Simplified logging
- Documentation welcome page

### 🐛 Fixed

- Password handling with strange characters
- Database locks when too many Watcher related updates

[Changes since previous version](https://github.com/mark-me/mixtape-society/compare/v0.1.0...v0.1.1-alpha)
