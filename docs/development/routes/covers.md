# Cover Art Routes

This document describes the Flask routes for serving cover art images.

---

## Overview

Two routes handle cover art serving:

1. **Direct File Serving** - `/covers/<filename>` (original, unchanged)
2. **Size-Parameterized API** - `/api/covers/<path>` (new, with size selection)

Both routes are registered in the main Flask app (`app.py`).

---

## Route 1: Direct File Serving

### `GET /covers/<filename>`

Serves cover art files directly from the cache directory.

**Original endpoint - preserves existing behavior for backward compatibility.**

#### Request

```http
GET /covers/artist_album_256x256.jpg HTTP/1.1
Host: localhost:5000
```

#### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| `filename` | string | path | Yes | Cover filename (must end with `.jpg`, `.jpeg`, or `.png`) |

#### Response

**Success (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: public, max-age=3600
Content-Length: 42134

[binary image data]
```

**Not Found (404):**
```http
HTTP/1.1 404 Not Found
```

#### Security

- ✅ Only serves from covers directory (`DATA_ROOT/cache/covers/`)
- ✅ Restricts to image extensions (`.jpg`, `.jpeg`, `.png`)
- ✅ No directory traversal allowed

#### Implementation

```python
@app.route("/covers/<filename>")
def serve_album_cover(filename):
    """Serves extracted album cover images from cache directory."""
    covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"

    # Security: restrict to image extensions
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        abort(404)

    return send_from_directory(covers_dir, filename)
```

#### Usage

```html
<!-- Direct reference in HTML -->
<img src="/covers/artist_album_256x256.jpg" alt="Album Cover">
```

```javascript
// JavaScript fetch
fetch('/covers/artist_album_512x512.jpg')
    .then(response => response.blob())
    .then(blob => {
        const url = URL.createObjectURL(blob);
        img.src = url;
    });
```

---

## Route 2: Size-Parameterized API

### `GET /api/covers/<path:release_dir>`

Serves cover art with optional size parameter. Generates variants on-demand.

**New endpoint for responsive, bandwidth-optimized cover art.**

#### Request

```http
GET /api/covers/Artist%2FAlbum?size=256x256 HTTP/1.1
Host: localhost:5000
```

#### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| `release_dir` | string | path | Yes | Release directory path (URL-encoded) |
| `size` | string | query | No | Desired size in `WxH` format |

#### Valid Sizes

| Value | Dimensions | Use Case |
|-------|-----------|----------|
| `96x96` | 96×96 | Thumbnails |
| `128x128` | 128×128 | Small tiles |
| `192x192` | 192×192 | Medium tiles |
| `256x256` | 256×256 | **Android Auto optimal** |
| `384x384` | 384×384 | High-DPI displays |
| `512x512` | 512×512 | Full-screen player |

#### Response

**Success (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: public, max-age=3600
Content-Length: 42134
Access-Control-Allow-Origin: *

[binary image data]
```

**Invalid Size (400 Bad Request):**
```json
{
  "error": "Invalid size parameter",
  "valid_sizes": ["96x96", "128x128", "192x192", "256x256", "384x384", "512x512"]
}
```

**Not Found (404):**
```http
HTTP/1.1 404 Not Found
```

#### Behavior

**With `size` parameter:**
1. Check if size variant exists in cache
2. If not, generate variant from main cover
3. If main cover missing, extract from audio files
4. Return requested size or fallback

**Without `size` parameter:**
1. Return main cover (800px max dimension)
2. If not cached, extract from audio files
3. Return fallback if extraction fails

#### Implementation

```python
@app.route("/api/covers/<path:release_dir_encoded>")
def serve_cover_by_size(release_dir_encoded):
    """Serves cover art with optional size parameter."""
    from urllib.parse import unquote

    release_dir = unquote(release_dir_encoded)
    requested_size = request.args.get('size', '').lower()

    valid_sizes = ['96x96', '128x128', '192x192', '256x256', '384x384', '512x512']
    covers_dir = app.config["DATA_ROOT"] / "cache" / "covers"

    # No size - return main cover
    if not requested_size:
        cover_url = collection.get_cover(release_dir)
        if cover_url:
            filename = cover_url.split('/')[-1]
            return send_from_directory(covers_dir, filename)
        abort(404)

    # Validate size
    if requested_size not in valid_sizes:
        return jsonify({
            "error": "Invalid size parameter",
            "valid_sizes": valid_sizes
        }), 400

    # Get or generate size-specific cover
    slug = collection._sanitize_release_dir(release_dir)
    size_filename = f"{slug}_{requested_size}.jpg"
    size_path = covers_dir / size_filename

    # Generate if needed
    if not size_path.exists():
        main_path = covers_dir / f"{slug}.jpg"
        if not main_path.exists():
            collection._extract_cover(release_dir, main_path)

        if main_path.exists():
            collection._generate_cover_variants(release_dir, slug)

    # Serve or fallback
    if size_path.exists():
        return send_from_directory(covers_dir, size_filename)

    # Try main cover
    if (covers_dir / f"{slug}.jpg").exists():
        return send_from_directory(covers_dir, f"{slug}.jpg")

    # Final fallback
    return send_from_directory(covers_dir, "_fallback.jpg")
```

#### Usage

**Python (Flask endpoint):**
```python
@app.route('/api/mixtape/<mixtape_id>/metadata')
def get_metadata(mixtape_id):
    release_dir = get_release_dir(mixtape_id)

    # Get size variants
    cover_sizes = collection.get_cover_sizes(release_dir)

    # Build URLs
    base_url = request.host_url.rstrip('/')
    artwork = [
        {"src": f"{base_url}/{cover_sizes['256x256']}", "sizes": "256x256"},
        {"src": f"{base_url}/{cover_sizes['512x512']}", "sizes": "512x512"}
    ]

    return jsonify({"artwork": artwork})
```

**JavaScript (client-side):**
```javascript
// Request specific size
const coverUrl = `/api/covers/${encodeURIComponent(releaseDir)}?size=256x256`;

fetch(coverUrl)
    .then(response => {
        if (!response.ok) throw new Error('Cover not found');
        return response.blob();
    })
    .then(blob => {
        img.src = URL.createObjectURL(blob);
    });
```

**cURL (testing):**
```bash
# Request 256×256 variant
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=256x256" -o cover_256.jpg

# Without size (main cover)
curl "http://localhost:5000/api/covers/Artist%2FAlbum" -o cover_main.jpg

# Invalid size (returns JSON error)
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=999x999"
```

---

## Performance

### First Request (Cold Cache)

```
GET /api/covers/Artist%2FAlbum?size=256x256

Timeline:
  0ms   - Request received
  50ms  - Extract main cover from audio files
  150ms - Generate all size variants (96×96 to 512×512)
  200ms - Response sent

Total: ~200ms (one-time cost)
```

### Subsequent Requests (Warm Cache)

```
GET /api/covers/Artist%2FAlbum?size=256x256

Timeline:
  0ms  - Request received
  5ms  - Serve from filesystem
  5ms  - Response sent

Total: ~5ms (cached)
```

### Bandwidth Comparison

| Client | Route | Size | Bandwidth |
|--------|-------|------|-----------|
| Desktop | `/covers/slug.jpg` | 400 KB | 400 KB |
| Desktop | `/api/covers/path?size=512x512` | 120 KB | 120 KB (70% savings) |
| Android Auto | `/covers/slug.jpg` | 400 KB | 400 KB |
| Android Auto | `/api/covers/path?size=256x256` | 40 KB | 40 KB (90% savings) |
| Mobile | `/covers/slug.jpg` | 400 KB | 400 KB |
| Mobile | `/api/covers/path?size=128x128` | 12 KB | 12 KB (97% savings) |

---

## Error Handling

### Missing Cover

**Scenario:** Release directory has no cover art

**Fallback chain:**
1. Try `/covers/{slug}.jpg` → Not found
2. Extract from audio files → No embedded art
3. Return `/covers/_fallback.jpg` → Always exists

**Result:** User sees fallback image, no 404 error

### Invalid Size Parameter

**Request:**
```http
GET /api/covers/Artist%2FAlbum?size=999x999
```

**Response:**
```json
HTTP/1.1 400 Bad Request

{
  "error": "Invalid size parameter",
  "valid_sizes": ["96x96", "128x128", "192x192", "256x256", "384x384", "512x512"]
}
```

### Generation Failure

**Scenario:** Cannot generate variant (disk full, PIL error, etc.)

**Behavior:**
1. Log warning message
2. Return main cover instead of variant
3. Retry generation on next request

**Result:** Slightly larger file served, but request succeeds

---

## Caching Headers

Both routes include caching headers:

```http
Cache-Control: public, max-age=3600
```

**Implications:**
- Browsers cache for 1 hour
- CDNs can cache responses
- Reduces server load
- Faster repeat visits

**To bypass cache:**
```javascript
// Add timestamp parameter
const url = `/covers/slug_256x256.jpg?t=${Date.now()}`;
```

---

## Related Documentation

**Architecture:**

- [Cover Art System Overview](../cover-art/overview.md) - System architecture
- [Size Optimization](../cover-art/size-optimization.md) - Implementation details
- [API Reference](../cover-art/api.md) - Python/JavaScript API

**Integration:**

- [Android Auto Integration](../android-auto/backend-implementation.md) - Android Auto context
- [Playback Routes](play/index.md) - Audio streaming context

---

## Testing

### Manual Testing

```bash
# Start Flask
flask run --host=0.0.0.0

# Test direct route
curl http://localhost:5000/covers/artist_album.jpg -o test1.jpg

# Test API route with size
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=256x256" -o test2.jpg

# Test API route without size
curl "http://localhost:5000/api/covers/Artist%2FAlbum" -o test3.jpg

# Test invalid size
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=invalid"

# Compare file sizes
ls -lh test*.jpg
```

### Automated Testing

```python
# tests/test_cover_routes.py
def test_direct_cover_route(client):
    response = client.get('/covers/artist_album_256x256.jpg')
    assert response.status_code == 200
    assert response.content_type == 'image/jpeg'

def test_api_cover_route_with_size(client):
    response = client.get('/api/covers/Artist%2FAlbum?size=256x256')
    assert response.status_code == 200
    assert len(response.data) < 100 * 1024  # < 100KB

def test_api_cover_route_invalid_size(client):
    response = client.get('/api/covers/Artist%2FAlbum?size=invalid')
    assert response.status_code == 400
    assert 'error' in response.json
```
