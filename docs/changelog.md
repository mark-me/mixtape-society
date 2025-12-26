# Changelog

![Changelog](images/changelog.png){ align=right width="90" }

All notable changes to Mixtape Society are documented here. We follow [Semantic Versioning](https://semver.org/) and the spirit of [Keep a Changelog](https://keepachangelog.com/).

Each release rewinds and fast-forwards your mixtape experience—just like a real cassette! 🎧

## 📦 v0.1.9-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-27

### 🔧 Changed

-

### 🐛 Fixed

- Collapse of the navbar happens only on small screens
- Better player display on smaller screens
- Redundant JavaScript removed from editor.html

[v0.1.9-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.8-alpha...v0.1.9-alpha)

---

## 📦 v0.1.8-alpha

<span class="md-tag">Unreleased</span>

**🗓️** 2025-12-26

### 🚀 Added

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

[v0.1.8-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.7-alpha...v0.1.8-alpha)

---

## 📦 v0.1.7-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-18

### 🚀 Added

- Editing previews - each track in the search-result can be played without adding them to the playlist
- Project link in navbar

### 🔧 Changed

- Logo and favicon
- Documentation line-up with app style

[v0.1.7-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.6-alpha...v0.1.7-alpha)

---

## 📦 v0.1.6-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-17

### 🔧 Changed

- Extracted CSS to dedicated files in static, and added comments with clear flow

### 🐛 Fixed

- Covers not showing for users that are not logged in
- Editor headers change according to creating or editing mixtape

[v0.1.6-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.5-alpha...v0.1.6-alpha)

---

## 📦 v0.1.5-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-17

### 🚀 Added

- Grouping search results:
  - Nesting for Artists: Artists show as top-level headers with summaries (e.g., "2 album(s)", "5 nummer(s)").
  - Albums are nested in an accordion below, each with their own header and collapsible tracks.
  - Folding Tracks: Tracks are hidden by default under a collapsible section (accordion for nested albums, simple collapse for standalone albums). Click the header/button to expand.

### 🔧 Changed

- Moved from JavaScript dialogs to Bootstrap dialogs

### 🐛 Fixed

- Fixed Dockerfile by starting app from factory function

[v0.1.5-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.4-alpha...v0.1.5-alpha)

---

## 📦 v0.1.4-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-16

### 🚀 Added

- Page that informs user at first startup on the progress of music library scraping

### 🔧 Changed

- Music library extraction backend (Musiclib)
- Huge overhaul of back-end, making modules less interdependent

### 🐛 Fixed

- Missing standard cover art
- Theme adherence on some pages
- Favicon theme adherence
- Deleting a mixtape actually works

[v0.1.4-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.3-alpha...v0.1.4-alpha)

---

## 📦 v0.1.3-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-15

### 🚀 Added

- Creating liner notes for a mixtape
- Pop-up when adding tracks to a mixtape
- Share mixtape from play page
- Social card metadata for mixtapes

### 🐛 Fixed

- Moving away from editing a mixtape then returning would lose changes

[v0.1.3-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.2-alpha...v0.1.3-alpha)

---

## 📦 v0.1.2-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-12

### 🐛 Fixed

- Made Mixtape browser responsive

[v0.1.2-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.1-alpha...v0.1.2-alpha)

---

## 📦 v0.1.1-alpha

<span class="md-tag">Pre-release</span>

**🗓️** 2025-12-12

### 🚀 Added

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

[v0.1.1-alpha](https://github.com/mark-me/mixtape-society/compare/v0.1.0...v0.1.1-alpha)

