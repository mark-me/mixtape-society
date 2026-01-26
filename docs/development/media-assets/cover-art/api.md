# API Reference - Cover Art Optimization

Complete API documentation for the size-optimized cover art endpoints.

---

## Overview

The cover art API provides two endpoints for serving album artwork:

1. **Direct file serving** (`/covers/<filename>`) - Original endpoint, unchanged
2. **Size-parameterized API** (`/api/covers/<path>`) - New endpoint with size selection

---

## Endpoints

### GET `/covers/<filename>`

Serves cover art files directly from the cache directory.

**Original endpoint - no changes to existing behavior.**

#### Parameters

| Parameter | Type | Location | Required | Description |
| --------- | ---- | -------- | -------- | ----------- |
| `filename` | string | path | Yes | Cover filename (e.g., `artist_album.jpg`) |

#### Example Requests

```bash
# Main cover
GET /covers/artist_album.jpg

# Size variant
GET /covers/artist_album_256x256.jpg

# Fallback image
GET /covers/_fallback.jpg
```

#### Response

**Success (200 OK):**

```http
Content-Type: image/jpeg
Cache-Control: public, max-age=3600
Content-Length: 42134

[image binary data]
```

**Not Found (404):**

```text
404 Not Found
```

**Security:**

- ✅ Only serves files from covers directory
- ✅ Restricted to `.jpg`, `.jpeg`, `.png` extensions
- ✅ No directory traversal allowed

#### Usage

```html
<!-- In HTML template -->
<img src="/covers/artist_album_256x256.jpg" alt="Album Cover">
```

```javascript
// In JavaScript
const coverUrl = `/covers/${slug}_256x256.jpg`;
fetch(coverUrl).then(response => ...);
```

---

### GET `/api/covers/<path:release_dir>`

Serves cover art with optional size parameter. Generates size variants on-demand.

**New endpoint for responsive cover art.**

#### Parameters

| Parameter | Type | Location | Required | Description |
| --------- | ---- | -------- | -------- | ----------- |
| `release_dir` | string | path | Yes | Release directory path (URL-encoded) |
| `size` | string | query | No | Desired size in `WxH` format |

#### Valid Sizes

| Size | Use Case | Typical File Size |
| ---- | -------- | ----------------- |
| `96x96` | Thumbnails | 5-8 KB |
| `128x128` | Small tiles | 8-12 KB |
| `192x192` | Medium tiles | 15-20 KB |
| `256x256` | **Android Auto optimal** | 30-50 KB |
| `384x384` | High-DPI displays | 60-90 KB |
| `512x512` | Full-screen player | 100-150 KB |

#### Example Requests

```bash
# Request specific size
GET /api/covers/Artist%2FAlbum?size=256x256

# Without size (returns main cover)
GET /api/covers/Artist%2FAlbum

# Another artist
GET /api/covers/Prince%2FPurple%20Rain?size=96x96
```

#### Response

**Success (200 OK):**

```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: public, max-age=3600
Content-Length: 42134
Access-Control-Allow-Origin: *

[image binary data]
```

**Invalid Size (400 Bad Request):**

```json
{
  "error": "Invalid size parameter",
  "valid_sizes": [
    "96x96",
    "128x128",
    "192x192",
    "256x256",
    "384x384",
    "512x512"
  ]
}
```

**Not Found (404):**

```http
HTTP/1.1 404 Not Found

Release directory not found
```

#### Behavior

1. **Size Specified:**
   - Generates variant if doesn't exist
   - Returns size-specific image
   - Falls back to main cover if generation fails
   - Falls back to `_fallback.jpg` if no cover exists

2. **No Size Specified:**
   - Returns main cover (800px max dimension)
   - Falls back to `_fallback.jpg` if no cover exists

3. **First Request:**
   - ~100-200ms delay while generating variants
   - All sizes generated at once (96×96 through 512×512)

4. **Subsequent Requests:**
   - <10ms - served from cache
   - No regeneration needed

#### URL Encoding

Release directories must be URL-encoded:

```javascript
// JavaScript example
const releaseDir = "Artist/Album Name";
const encoded = encodeURIComponent(releaseDir);
const url = `/api/covers/${encoded}?size=256x256`;

// Result: /api/covers/Artist%2FAlbum%20Name?size=256x256
```

```python
# Python example
from urllib.parse import quote

release_dir = "Artist/Album Name"
encoded = quote(release_dir, safe='')
url = f"/api/covers/{encoded}?size=256x256"

# Result: /api/covers/Artist%2FAlbum%20Name?size=256x256
```

---

## Python API

### ::: src.musiclib.reader.MusicCollection.get_cover

### ::: src.musiclib.reader.MusicCollection.get_cover_sizes

---

## JavaScript API

### `extractMetadataFromDOM(trackElement)`

Extracts metadata including platform-optimized artwork URLs.

```javascript
import { extractMetadataFromDOM } from './playerUtils.js';

const trackElement = document.querySelector('.track-item');
const metadata = extractMetadataFromDOM(trackElement);

// Returns:
{
    title: "Track Name",
    artist: "Artist Name",
    album: "Album Name",
    artwork: [
        { src: "/covers/slug_96x96.jpg", sizes: "96x96", type: "image/jpeg" },
        { src: "/covers/slug_256x256.jpg", sizes: "256x256", type: "image/jpeg" },
        { src: "/covers/slug_512x512.jpg", sizes: "512x512", type: "image/jpeg" }
    ]
}
```

**Platform-Specific Sizes:**

**iOS:**

```javascript
artwork: [
    { src: "/covers/slug_512x512.jpg", sizes: "512x512", type: "image/jpeg" },
    { src: "/covers/slug_256x256.jpg", sizes: "256x256", type: "image/jpeg" },
    { src: "/covers/slug_192x192.jpg", sizes: "192x192", type: "image/jpeg" }
]
```

**Android Auto:**

```javascript
artwork: [
    { src: "/covers/slug_96x96.jpg", sizes: "96x96", type: "image/jpeg" },
    { src: "/covers/slug_128x128.jpg", sizes: "128x128", type: "image/jpeg" },
    { src: "/covers/slug_192x192.jpg", sizes: "192x192", type: "image/jpeg" },
    { src: "/covers/slug_256x256.jpg", sizes: "256x256", type: "image/jpeg" },
    { src: "/covers/slug_512x512.jpg", sizes: "512x512", type: "image/jpeg" }
]
```

**Desktop:**

```javascript
artwork: [
    { src: "/covers/slug_192x192.jpg", sizes: "192x192", type: "image/jpeg" },
    { src: "/covers/slug_512x512.jpg", sizes: "512x512", type: "image/jpeg" }
]
```

---

### `AndroidAutoIntegration.updateMediaMetadata(metadata)`

Updates MediaSession with size-optimized artwork.

```javascript
const androidAuto = new AndroidAutoIntegration();
await androidAuto.initialize();

// Update metadata
androidAuto.updateMediaMetadata({
    title: "Track Name",
    artist: "Artist Name",
    album: "Album Name",
    artwork: [
        { src: "/covers/slug_256x256.jpg", sizes: "256x256", type: "image/jpeg" },
        { src: "/covers/slug_512x512.jpg", sizes: "512x512", type: "image/jpeg" }
    ]
});
```

**Result:**

- MediaSession metadata updated
- Android Auto displays appropriate size
- Bandwidth optimized automatically

---

## Rate Limiting

Currently no rate limiting on cover art endpoints.

**Recommendations for production:**

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=get_remote_address)

@app.route("/api/covers/<path:release_dir>")
@limiter.limit("100 per minute")  # Adjust as needed
def serve_cover_by_size(release_dir):
    # ...
```

---

## Caching Headers

All cover art responses include caching headers:

```http
Cache-Control: public, max-age=3600
```

**Implications:**

- Browsers cache for 1 hour
- CDN can cache responses
- Reduces server load
- Faster subsequent loads

**To force refresh:**

```javascript
// Bypass cache with timestamp
const url = `/covers/${slug}_256x256.jpg?t=${Date.now()}`;
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When |
| ---- | ------- | ---- |
| 200 | OK | Cover found and served |
| 400 | Bad Request | Invalid size parameter |
| 404 | Not Found | Release directory doesn't exist |
| 500 | Internal Server Error | Server error during generation |

### Fallback Behavior

The API implements multiple fallback levels:

1. **Requested size variant** (`artist_album_256x256.jpg`)
   ↓ if doesn't exist, try to generate
   ↓ if generation fails ↓

2. **Main cover** (`artist_album.jpg`)
   ↓ if doesn't exist ↓

3. **Fallback image** (`_fallback.jpg`)
   ↓ always exists

**Result:** Users never see broken images

---

## Performance Considerations

### First Request

```text
GET /api/covers/Artist%2FAlbum?size=256x256

[No cached variants exist]
→ Extract main cover from audio files (~50-100ms)
→ Generate all 6 size variants (~100-200ms)
→ Return requested variant
→ Cache all variants for future requests

Total: ~150-300ms
```

### Subsequent Requests

```text
GET /api/covers/Artist%2FAlbum?size=256x256

[Variants already cached]
→ Serve from filesystem (~5-10ms)

Total: ~5-10ms
```

### Bandwidth Comparison

| Scenario | Original | Optimized | Savings |
| -------- | -------- | --------- | ------- |
| Android Auto | 400 KB | 40 KB | 90% |
| Mobile Web | 400 KB | 15 KB | 96% |
| 10 tracks × Android Auto | 4 MB | 400 KB | 90% |
| 50 tracks × Mobile | 20 MB | 750 KB | 96% |
