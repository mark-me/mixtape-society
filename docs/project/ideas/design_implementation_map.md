![Design & Implementation Map](../../images/design.png){ align=right width="90" }

# Design & Implementation Map

## 🧭 Core principles

- **No central-server accounts**
- **No Spotify / Apple Music integration**
- **No social features** (likes, comments, following)
- **No ads, analytics, or telemetry by default**

---

## 🖼️ QR card – make it meaningful (not just a link)

| Item | Status | Where it lives | Notes / Proposal |
| -- | -- | -- | -- |
| QR → mixtape landing page (title, personal note, tracklist, optional cover, “play order matters”) | ✔︎ Implemented | `routes/play.py → public_play(slug)` renders `play_mixtape.html` | The template already displays title, cover, dedication, and a Play button. Nothing to add. |
| QR generation (one-time per mixtape) | ✔︎ Implemented | `routes/editor.py → qr.generate_qr(slug)` and `qr.download_qr(slug)` | Already usable from the editor UI. |
| QR + NFC hybrid | ✖︎ Missing | – | **Proposal:** Add `GET /nfc/<slug>.json` returning `{ "url": "<public-share-url>" }`. NFC tags store this JSON (or URL). Stateless; preserves no-account rule. |
| Contextual liner-note page (not a bare playlist) | ✔︎ Implemented | `templates/play_mixtape.html`, `static/js/player/linerNotes.js` | Markdown liner notes already render. |
| “Play order matters” banner | ✎ Partially implemented | `play_mixtape.html` | **Proposal:** Add `ordered: true` to `mixtape.json`. Template conditionally shows banner; editor exposes toggle. |

---

## 🎶 Cassette / MiniDisc / CD-style card (nostalgia wins hard)

| Item | Status | Where it lives | Notes / Proposal |
| -- | -- | -- | -- |
| Cassette-shaped card design (QR on label) | ✖︎ Missing | – | **Proposal:** Printable SVG (`assets/templates/cassette.svg`) with QR placeholder. Editor offers “Download printable card”. QR PNG merged server-side (Pillow). |
| Mini-CD sleeve with liner notes | ✖︎ Missing | – | **Proposal:** SVG CD-case layout + liner-note markdown → PDF (WeasyPrint / pdfkit). Embed QR via existing QR route. |
| Polaroid-sized card, handwritten vibe | ✖︎ Missing | – | **Proposal:** Handwritten font CSS option. Store `style` in `mixtape.json`; PDF generator applies CSS class. |

_All of these are offline artifacts; server interaction is limited to existing QR generation._

---

## 📱 NFC instead of (or alongside) QR

| Item | Status | Where it lives | Notes / Proposal |
| -- | -- | -- | -- |
| NFC-enabled card / coin / pick / postcard | ✖︎ Missing | – | **Proposal:** Add `GET /nfc/<slug>.txt` returning the plain public URL. NFC tags can be written with any consumer writer. |
| Hybrid QR + NFC fallback | ✖︎ Missing | – | **Proposal:** Printable assets embed QR + printed short URL (`/s/<slug>`). Graceful fallback for non-NFC devices. |

---

## 🎁 The “artifact” concept (beyond cards)

| Artifact | Status | Notes / Proposal |
| -- | -- | -- |
| Matchbox with QR inside | ✖︎ Missing | SVG template with QR placeholder. |
| Bookmark | ✖︎ Missing | Bookmark-shaped SVG using existing QR PNG. |
| Sticker set (each sticker = a track) | ✖︎ Missing | **Proposal:** PDF “sticker sheet” where each track has a tiny QR pointing to `/share/<slug>#track=<index>`. Client-side fragment parsing starts playback at that track. |
| Small zine (QR at end) | ✖︎ Missing | Combine liner-note markdown + QR into a single PDF (WeasyPrint). |
| Postcard (mailed) | ✖︎ Missing | Same as postcard template in §2 with larger personal note area. |

_All artifacts remain physical; backend usage is limited to existing QR endpoints._

---

## ⏳ Time-based or ritual-based access

| Item | Status | Where it lives | Notes / Proposal |
| -- | -- | -- | -- |
| Unlock 1 track per day | ✖︎ Missing | – | **Proposal:** Add `access_policy` to `mixtape.json` (`{ type: "daily_unlock", start: ... }`). Enforced client-side via `playerControls.js` + `localStorage`. |
| Unlock only at night | ✖︎ Missing | – | **Proposal:** `policy: "night_only"`. Client checks local time / UTC offset. |
| “Play in order, no shuffle” | ✔︎ Implemented | `routes/play.py`, `playerControls.js` | Shuffle disabled; order enforced. |
| Expiring mixtape (30 days) | ✖︎ Missing | – | **Proposal:** Add `expires_at`. Public page renders “Mixtape expired” if past timestamp. |
| “Listen once” mode | ✖︎ Missing | – | **Proposal:** `once: true`. Client disables playback after first full listen using `localStorage`. |

_All policies are client-side only — no server state, no accounts._

---

## 🚫 Playback without accounts or ads (important constraint)

| Item | Status | Where it lives | Notes / Proposal |
| -- | -- | -- | -- |
| Self-hosted audio files | ✔︎ Implemented | `routes/play.stream_audio` | Streams from `MUSIC_ROOT`. |
| Independent / CC music | ✎ Partially implemented | Editor UI | **Proposal:** License confirmation checkbox → `license: "CC0"` badge on public page. |
| Bandcamp embeds | ✖︎ Missing | – | **Proposal:** Optional `external_url` per track. Player renders `<iframe>` embed. |
| Progressive Web App (offline caching) | ✖︎ Missing | – | **Proposal:** Service Worker (`static/sw.js`) caches JSON, cover, audio files. |
| Zero-ads, zero-tracking | ✔︎ Implemented | Templates | No analytics or third-party scripts. |

---

## 🧠 Strong framing sentence (this matters)

| Item | Status | Where it lives |
| -- | -- | -- |
| “This is not a playlist. It’s a mixtape you give to someone.” | ✔︎ Implemented | `play_mixtape.html`, `editor.html` |

---

## ✅ Top 3 suggestions

| Suggestion | Already present? |
| -- | -- |
| Beautiful physical card (cassette / CD inspired) | ✖︎ Missing – see §2 |
| Mixtape landing page (not generic player) | ✔︎ Implemented |
| Intentional constraints (order matters, finite) | ✔︎ Implemented |

---

## 💡 MVP definition (one sentence)

> **“A creator makes a mixtape, prints a QR card, gives it to a friend. The friend scans it and listens — no account, no ads.”**

All parts are functional except physical artifact generation, which is purely additive.

---

## 🔁 MVP Flow (creator → receiver)

### Creator

| Phase | Implemented? | Files / Routes | Missing pieces |
| -- | -- | -- | -- |
| Create mixtape | ✔︎ | `routes/editor.new_mixtape()` | – |
| Add tracks | ✔︎ | `static/js/editor/search.js`, `src/musiclib/` | – |
| Publish (QR generation) | ✔︎ | `routes/qr_blueprint.py` | – |
| Print / share physically | ✖︎ | – | Printable SVG/PDF templates |

### Receiver

| Phase | Implemented? | Files / Routes |
| -- | -- | -- |
| Scan QR | ✔︎ | `routes/play.public_play` |
| Landing page | ✔︎ | `templates/play_mixtape.html` |
| Listen (order-only) | ✔︎ | `playerControls.js`, `stream_audio` |

---

## 📝 MVP includes / excludes (re-affirmed)

| Category | Status |
| -- | -- |
| Public mixtape page | ✔︎ |
| Audio playback | ✔︎ |
| QR-code generation | ✔︎ |
| Mobile-first UI | ✔︎ |
| No accounts | ✔︎ |
| No ads / analytics | ✔︎ |
| No social features | ✔︎ |
| No streaming-service APIs | ✔︎ |

---

## 🗺️ Digital enablement (implementation map)

| Piece | Implemented? | Where it lives | Next step |
| -- | -- | -- | -- |
| Data model (JSON) | ✔︎ | `mixtapes/<slug>/mixtape.json` | – |
| Backend (Flask) | ✔︎ | `app.py` | – |
| Frontend UI | ✔︎ | `templates/`, `static/js/` | – |
| QR generation | ✔︎ | `routes/qr_blueprint.py` | – |
| NFC endpoint | ✖︎ | – | Add `GET /nfc/<slug>.txt` |
| Printable artifacts | ✖︎ | – | Add `/print/<slug>/<template>` route |
| Time-based access | ✖︎ | – | Extend JSON + client checks |
| Offline PWA | ✖︎ | – | Add `static/sw.js` |

_All additions are stateless and preserve the four core principles._

---

## 📅 MVP timeline

| Week | Done | New tasks |
| -- | -- | -- |
| 1 | Core app, streaming, QR, editor | Design SVG templates |
| 2 | Editor save flow, QR modal | `/print` route, NFC endpoint |
| 3 | – | Access-policy enforcement |
| 4 | – | Service Worker, UI polish, physical test |

**Success metric:**
A tester scans a printed card, listens fully, sees enforced constraints — no login, no ads.

---

## 🧪 How you’ll know it worked

- **Qualitative:** “I listened to the whole thing.”
- **Technical:** No login redirects; no third-party network requests.
- **Artifact:** Printed cassette card opens the mixtape instantly on mobile.

---

## 📝 TL;DR — What’s already there vs what to add

| Feature | Implemented | Missing (quick win) |
| -- | -- | -- |
| QR → landing page | ✔︎ | – |
| QR generation | ✔︎ | – |
| Physical artifacts | – | SVG/PDF templates + `/print` |
| NFC token | – | `/nfc/<slug>.txt` |
| Time-based access | – | `access_policy` + JS |
| Offline playback | – | Service Worker |
| “Order matters” flag | ✎ | Store in JSON |
| Once-only / daily unlock | – | LocalStorage guard |
| Bandcamp embeds | – | `external_url` support |

_All missing pieces are additive and do not violate any core principles._
