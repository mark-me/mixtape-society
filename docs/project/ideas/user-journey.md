![User Journey](../../images/user-journey.png){ align=right width="90" }

# User Journey

## What Mixtape Society really offering 🎁

You’re not sharing *music files*.
You’re sharing:

* **Taste** (“I thought of you when I heard this”)
* **Curation** (finite, intentional, ordered)
* **A moment** (time + place + mood)
* **A physical gesture** (handing something over)

That’s why the QR card idea is already strong. Let’s build on it.

---

## 1. QR card — but make it meaningful (not just a link)

### What works well

* Familiar
* Cheap
* Easy to scan
* Bridges physical → digital smoothly

### How to elevate it

Instead of “QR → playlist”, make it:

**QR → mixtape landing page**

* Title of the mixtape
* Short personal note (“For late-night train rides”)
* Tracklist with *your annotations*
* Optional cover art
* Optional “play order matters” message

This makes it feel like a *liner note*, not a playlist.

💡 *Key insight:*
The value is not the QR — it’s the **context you wrap around it**.

---

## 2. Cassette / MiniDisc / CD-style card (nostalgia wins hard)

If your audience is even slightly nostalgic:

### Physical object ideas

* **Cassette-shaped card** (with QR on the label)
* **Mini CD sleeve** with artwork and liner notes
* **Folded insert** like old CD booklets
* **Polaroid-sized card** with handwritten vibe

You’re borrowing the *language of old mixtapes* without the technical burden.

Why this works:

* People don’t throw it away
* It invites curiosity
* It signals “this is not disposable content”

---

## 3. NFC instead of (or alongside) QR 📱

If you want a bit of magic:

* NFC sticker embedded in:

  * a card
  * a coin
  * a guitar pick
  * a postcard

**Tap → mixtape opens**

Pros:

* No camera needed
* Feels magical
* Invisible tech (very “modern artifact”)

Cons:

* Slightly more expensive
* Some people don’t know what NFC is (yet)

💡 Hybrid idea: **QR + NFC**, so it always works.

---

## 4. The “artifact” concept (beyond cards)

If you want to go more artistic / memorable:

### Objects with embedded access

* Matchbox with QR inside
* Bookmark
* Sticker set (each sticker = a track)
* Small zine (with QR at the end)
* Postcard mailed instead of handed over

Now the mixtape becomes:

> “A thing that exists in the world”

This fits beautifully with your desire to escape pure digital sharing.

---

## 5. Time-based or ritual-based access ⏳

This is where your app can do something *streaming platforms can’t*:

* Unlock 1 track per day
* Unlock only at night
* “Play in order, no shuffle”
* Expiring mixtape (30 days, then gone)
* “You can only listen once” mode

This mirrors the old limitations of tapes — and limitations create meaning.

---

## 6. Playback without accounts or ads (important constraint)

Since you explicitly want to avoid Spotify/YouTube/etc:

### Practical approaches

* Host audio files yourself (legally important!)
* Use:

  * Independent artists
  * Creative Commons music
  * Your own recordings
  * Bandcamp embeds (artist-friendly, often no ads)
* Progressive Web App:

  * Cache tracks
  * Offline listening after first open

You’re closer to a **digital liner-note player** than a “streaming app”.

---

## 7. A strong framing sentence (this matters)

You might want to articulate your app like this:

> “This is not a playlist.
> It’s a mixtape you give to someone.”

That framing will guide *every design choice*.

---

## My top 3 suggestions for you

If I had to pick:

1. **Beautiful physical card (cassette/CD-inspired)**

   * QR + optional NFC
   * Personal note
2. **Mixtape landing page, not a generic player**

   * Story, mood, annotations
3. **Intentional constraints**

   * Order matters
   * No shuffle
   * Finite

Those three together already differentiate you strongly.

---

# 1. MVP definition (one sentence)

> A creator makes a mixtape, prints a QR card, gives it to a friend.
> The friend scans it and listens — no account, no ads.

That’s it.

---

# 2. The MVP flow (creator → receiver)

## A. Creator flow (you)

**Goal:** Create something shareable in under 5 minutes.

### Step 1 — Create a mixtape

* Title
* Short description / dedication
* Optional cover image

👉 Stored as one JSON object.

---

### Step 2 — Add tracks

For MVP:

* Upload audio files **or**
* Reference hosted files (e.g. `/audio/track01.mp3`)

Each track:

* Title
* Artist
* Audio URL
* Optional note (“Listen for the bass line at 2:10”)

⚠️ No streaming service integrations yet.

---

### Step 3 — Publish

* App generates:

  * A **public URL**:
    `/mixtape/{slug}`
  * A **QR code** pointing to that URL

---

### Step 4 — Print / share physically

* Print QR on:

  * Card
  * Sticker
  * Cassette-style insert

MVP does **not** care *how* you print it.

---

## B. Receiver flow (friend)

**Goal:** Zero friction, instant emotional payoff.

### Step 1 — Scan QR

* Opens `/mixtape/{slug}` in mobile browser
* No login
* No cookies
* No tracking popups

---

### Step 2 — Landing page

Shows:

* Mixtape title
* Cover image
* Dedication text
* “Made for you by …” (optional)

Primary CTA:
▶️ **Play**

---

### Step 3 — Listen

* Plays tracks **in order**
* No shuffle
* Simple play/pause/next
* Track notes visible while listening

That’s the full experience.

---

# 3. What the MVP explicitly includes

✅ Public mixtape page
✅ Audio playback
✅ QR code generation
✅ Mobile-first UI
✅ One creator (you)
✅ No accounts at all

---

# 4. What the MVP explicitly does NOT include (important)

❌ User accounts
❌ Search
❌ Likes / comments
❌ Sharing buttons
❌ Streaming provider APIs
❌ Analytics
❌ Recommendations

If it doesn’t help “scan → listen”, it’s out.

---

# 5. Digital enablement (how you actually build this)

This fits *perfectly* with what you already described in earlier chats.

## A. Data model (JSON-based)

Each mixtape = a folder:

```
mixtapes/
  late-night-train/
    mixtape.json
    cover.jpg
    track01.mp3
    track02.mp3
```

### mixtape.json

```json
{
  "slug": "late-night-train",
  "title": "Late Night Train",
  "description": "For long rides when the city fades out.",
  "author": "J.",
  "tracks": [
    {
      "title": "Night Window",
      "artist": "Echo Static",
      "file": "track01.mp3",
      "note": "Best part starts at 1:42"
    }
  ]
}
```

No database yet. Filesystem = truth.

---

## B. Backend (minimal)

Since you’re already comfortable here:

**Flask app**

* `GET /mixtape/<slug>` → returns HTML
* `GET /api/mixtape/<slug>` → returns JSON
* Static file serving for audio + images

That’s ~100 lines of Python.

---

## C. Frontend (simple but intentional)

* Server-rendered HTML or minimal JS
* `<audio>` element
* One playlist controller

Key UX decisions:

* Auto-advance tracks
* Lock order
* Big play button
* Works on mobile Safari

No frameworks needed yet.

---

## D. QR code generation

One-time per mixtape:

```python
import qrcode

url = "https://yourapp.com/mixtape/late-night-train"
img = qrcode.make(url)
img.save("late-night-train-qr.png")
```

Print it. Done.

---

# 6. MVP timeline (realistic)

**Week 1**

* File structure
* Flask routes
* JSON loading
* Static audio playback

**Week 2**

* Mobile layout
* QR generation
* Print test cards
* Give one to a friend

If someone listens start-to-finish, MVP succeeded.

---

# 7. One subtle but powerful MVP detail ⭐

Add this **one line** on the landing page:

> “This mixtape was made for you.
> Please listen in order.”

That framing changes behavior.

---

# 8. How you’ll know it worked

Success is **not**:

* Daily active users
* Retention
* Virality

Success is:

> Someone texts you:
> “I listened to the whole thing.”

---

If you want next, I can:

* Sketch the **exact Flask routes + templates**
* Design the **mobile-first player UI**
* Help you future-proof this for **accounts later**
* Or define **MVP v1.1 features** that *don’t* break the ritual

Just tell me what you want to build next.
