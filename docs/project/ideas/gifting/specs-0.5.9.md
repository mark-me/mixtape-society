# Present Mixtape Specs (v0.5.9)

I've created a Flask app which allows an owner of a digital music collection to create and share "mixtapes" — ordered playlists of tracks from their collection — via physical QR-code cards. The receiver scans the QR code and is taken to a minimalist web player to listen to the mixtape in order, without accounts or ads.

For the coming release I'd like to add a user experience for the receiver that enhances the ritual of receiving a physical mixtape.

## Current Flow (creator → receiver)

This is a summary of the existing flow, to ground the new feature proposals.

### Creator

| Phase | Implemented? | Files / Routes | Missing pieces |
| -- | -- | -- | -- |
| Create mixtape | ✔︎ | `routes/editor.new_mixtape()` | – |
| Add tracks | ✔︎ | `static/js/editor/search.js`, `src/musiclib/` | – |
| Add liner notes / messages | ✔︎ | – | UI for adding custom messages, liner notes |
| Publish (QR generation) | ✔︎ | `routes/qr_blueprint.py` | – |
| Print / share physically | ✔︎ | – | Printable PNG image |

### Receiver

| Phase | Implemented? | Files / Routes |
| -- | -- | -- |
| Scan QR | ✔︎ | `routes/play.public_play` |
| Landing page | ✔︎ | `templates/play_mixtape.html` |
| Listen (order-only) | ✔︎ | `playerControls.js`, `stream_audio` |

## Gift flow

When a receiver scans the QR code, they are taken to a landing page that shows a series of screens to "unwrap" the mixtape, enhancing the ritual of receiving a physical mixtape.

* Screens:
  1. **Cover art reveal**: Reveal cover art after clicking a "Tap to Unwrap" button.
  2. **Mixtape info**: Reveal mixtape title, creator name, and a short message from the creator.
  3. **Play button**: Finally, show the play button to start listening.
  4. **(Optional) Tracklist reveal**: After the mixtape is complete, show the full tracklist as a reward. (the creator can choose to enable/disable this).
     * ⏳ Time-based or ritual-based access: Unlock 1 track per day.

## Enhanced Flow (creator → receiver)

### Creator

| Phase | Implemented? | Files / Routes | Missing pieces |
| -- | -- | -- | -- |
| Create mixtape | ✔︎ | `routes/editor.new_mixtape()` | – |
| Add tracks | ✔︎ | `static/js/editor/search.js`, `src/musiclib/` | – |
| Add liner notes / messages | ✔︎ | – | UI for adding custom messages, liner notes |
| Publish (QR generation) | ✔︎ | `routes/qr_blueprint.py` | – |
| Print / share physically | ✔︎ | – | Printable PNG image |
| Optional: Configure gift flow | ✖︎ | – | UI for configuring gift flow options |
| Gift flow option track list reveal | ✖︎ | – | Option to enable/disable tracklist reveal for receiver |

### Receiver

| Phase | Implemented? | Files / Routes | Missing pieces |
| ----- | ------------ | -------------- | -------------- |
| Scan QR | ✔︎ | `routes/play.public_play` | – |
| Cover art reveal | ✖︎ | – | UI animated showing the cover art after "Tap to Unwrap" button. |
| Mixtape info | ✖︎ | – | Reveal mixtape title, creator name, and a short message from the creator. |
| Play button | ✖︎ | – | Show play button to start listening. |
| Optional: Tracklist reveal | ✖︎ | – | Show full tracklist after completion if enabled by creator. |
| Listen | ✔︎ | `playerControls.js`, `stream_audio` |

## 🗺️ Digital enablement (implementation map)

| Piece | Implemented? | Where it lives | Next step |
| -- | -- | -- | -- |
| Data model (JSON) | ✔︎ | `mixtapes/<slug>/mixtape.json` | – |
| Backend (Flask) | ✔︎ | `app.py` | – |
| Frontend UI | ✔︎ | `templates/`, `static/js/` | – |
| QR generation | ✔︎ | `routes/qr_blueprint.py` | – |
| Time-based access | ✖︎ | – | Extend JSON + client checks |
| Offline PWA | ✖︎ | – | Add `static/sw.js` |
