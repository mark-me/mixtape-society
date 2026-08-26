![System](../../../images/system.png){ align=right width="90" }

# System Routes

The `routes/system.py` file defines the `system` blueprint: app‑ and library‑level housekeeping routes that don't belong to any single mixtape or feature area. It's registered in `app.py` with no URL prefix, since its routes already carry their original top‑level paths.

Kept separate from the mixtape/browsing/editing/playback blueprints because these routes operate on the collection or the app as a whole, not on a specific mixtape.

## 🔌 Construction

`create_system_blueprint(collection, data_root, limiter, logger=None)` builds and returns a Blueprint named `"system"`.

| Parameter | Purpose |
| --------- | ------- |
| `collection` | The shared `MusicCollectionUI` instance to inspect (`count`, `get_collection_stats`) and maintain (`resync`, `reload`). |
| `data_root` | Root directory the database and its `-wal`/`-shm`/`-journal` files live under. |
| `limiter` | The app's `Limiter` instance, so `/indexing-status` can opt out of rate limiting for its polling traffic. |
| `logger` | Optional `Logger`; falls back to `NullLogger`. |

## 🌐 Routes

| Route | Method | Auth | Description |
| ----- | ------ | ---- | ----------- |
| `/service-worker.js` | GET | – | Serves the PWA service worker, scoped to `/play/`, with caching disabled so updates take effect. |
| `/manifest.json` | GET | – | Serves the PWA manifest. |
| `/robots.txt` | GET | – | Disallows all crawlers (`User-agent: *\nDisallow: /`). |
| `/indexing-status` | GET (rate‑limit exempt) | – | Returns JSON with current indexing progress; used by the front‑end's polling. |
| `/collection-stats` | GET | ✅ | Returns JSON with `num_artists`, `num_albums`, `num_tracks`, `total_duration`, `last_added`. |
| `/resync` | POST | ✅ | Starts a background resync of the music library (daemon thread). Returns `409` if indexing is already in progress. |
| `/reset-database` | POST | ✅ | Deletes the SQLite DB files (`*.db`, `*-wal`, `*-shm`, `*-journal`), then reloads the collection in place and rebuilds in the background. |
| `/check-database-health` | GET | ✅ | Runs `PRAGMA quick_check` and returns `{ healthy, track_count, check_result }` or `{ healthy: false, requires_reset: true }` on corruption. |

## ♻️ Reset‑and‑Reload

`/reset-database` deletes the on‑disk database files, then calls `collection.reload()` on a background thread rather than constructing a new `MusicCollectionUI`. `reload()` closes and re‑initializes the *same* object in place, so every blueprint holding a reference to `collection` — registered once, at app startup — keeps working against the fresh state. Replacing the object instead would leave those references pointing at the old, closed collection.

## 🔌 API

### ::: src.routes.system
