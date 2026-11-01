# Backend Implementation

This page documents the server-side changes required for Android Auto integration, focusing on size-optimized cover art generation and serving.

---

## 🎯 Goals

1. Generate multiple size variants of cover artwork
2. Serve size-specific covers via query parameters
3. Maintain backward compatibility with existing code
4. Optimize bandwidth for mobile/in-car use

---

## 📁 Modified Files

### `src/musiclib/reader.py`

Methods to `MusicCollection` class:

- `_generate_cover_variants()` - Generates 6 size variants
- `get_cover_sizes()` - Returns URLs for all size variants

### `src/app.py`

API endpoint:

- `/api/covers/<release_dir_encoded>?size=WxH` - Serves size-specific covers

---

## 🔧 Implementation Details

### 1. Cover Variant Generation

#### ::: src.musiclib.reader.MusicCollection._extract_cover

**File naming convention:**

- Main cover: `{slug}.jpg` (e.g., `artist_album.jpg`)
- Variants: `{slug}_{size}x{size}.jpg` (e.g., `artist_album_256x256.jpg`)

**Standard sizes generated:**

- 96×96 px - Thumbnails (5-8 KB)
- 128×128 px - Small tiles (8-12 KB)
- 192×192 px - Medium tiles (15-20 KB)
- 256×256 px - Android Auto optimal (30-50 KB)
- 384×384 px - High-DPI displays (60-90 KB)
- 512×512 px - Full-screen player (100-150 KB)

---

### 2. Size URL Retrieval

#### ::: src.musiclib.reader.MusicCollection.get_cover_sizes

**Return value example:**

```python
{
    "96x96": "covers/artist_album_96x96.jpg",
    "128x128": "covers/artist_album_128x128.jpg",
    "192x192": "covers/artist_album_192x192.jpg",
    "256x256": "covers/artist_album_256x256.jpg",
    "384x384": "covers/artist_album_384x384.jpg",
    "512x512": "covers/artist_album_512x512.jpg"
}
```

---

### 3. API Endpoint

**Route:** `/api/covers/<release_dir_encoded>`

**Location:** `src/routes/covers.py` (the `covers` blueprint)

```python
@covers.route("/api/covers/<path:release_dir_encoded>")
def serve_cover_by_size(release_dir_encoded):
    """Serves cover art with optional size parameter.

    Supports ?size=WxH query parameter (e.g., ?size=256x256).
    Generates size variants on-demand and caches them.

    Args:
        release_dir_encoded: URL-encoded release directory path

    Query Parameters:
        size: Optional size in format WxH (e.g., 256x256)
              Valid: 96x96, 128x128, 192x192, 256x256, 384x384, 512x512

    Returns:
        Image file from cache directory
    """
    release_dir = unquote(release_dir_encoded)
    requested_size = request.args.get('size', '').lower()

    if not requested_size:
        # No size specified, return main cover
        cover_path = collection.get_or_create_cover(release_dir)
        if cover_path:
            return send_from_directory(covers_dir, cover_path.name)
        abort(404)

    # Validate size parameter
    if requested_size not in VALID_SIZES:
        return jsonify({
            "error": "Invalid size parameter",
            "valid_sizes": VALID_SIZES
        }), 400

    # get_or_create_cover generates the variant on demand — the
    # slugging/extraction/variant-generation internals below are
    # no longer the route's concern.
    cover_path = collection.get_or_create_cover(release_dir, size=requested_size)
    if cover_path:
        return send_from_directory(covers_dir, cover_path.name)

    # Final fallback
    return send_from_directory(covers_dir, "_fallback.jpg")
```

**Usage examples:**

```bash
# Get 256×256 variant
GET /api/covers/Artist%2FAlbum?size=256x256

# Get main cover (no size)
GET /api/covers/Artist%2FAlbum

# Invalid size returns error
GET /api/covers/Artist%2FAlbum?size=999x999
# → {"error": "Invalid size parameter", "valid_sizes": [...]}
```

---

## 🔄 Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as API endpoint
    participant Collection
    participant FS as Filesystem

    Client->>API: GET /api/covers/Artist%2FAlbum<br/>?size=256x256
    API->>API: Decode path, validate size
    API->>Collection: get_or_create_cover()
    alt Variant exists
        Collection->>FS: Look up variant
        FS-->>Collection: File found
    else Variant missing
        Collection->>Collection: Extract cover if needed
        Collection->>FS: Save main cover
        Collection->>FS: Generate 6 variants
    end
    Collection-->>API: Path to variant
    API->>FS: Read variant
    FS-->>API: File bytes
    API-->>Client: 200 + JPEG (40KB)
```

---

## 📊 Performance Characteristics

### Storage Impact

- **Main cover:** 300-500 KB per album
- **All 6 variants:** 50-150 KB total per album
- **Overhead:** ~15-25% of main cover size

### Generation Performance

- **First request:** +100-200ms (one-time)
- **Subsequent requests:** 0ms additional (served from cache)
- **Batch generation:** Can pre-generate for popular albums

### Caching Strategy

- **Lazy generation:** Only creates variants when requested
- **Permanent cache:** Variants never expire
- **No cleanup:** Variants remain until manual cleanup
- **Cache location:** `DATA_ROOT/cache/covers/`

---

## 🔙 Backward Compatibility

### Existing Routes Unchanged

✅ `/covers/<filename>` - Still works exactly as before
✅ `get_cover(release_dir)` - Returns single URL as always
✅ All existing templates - No changes required

### New Features Are Additive

- New API endpoint doesn't affect existing code
- `get_cover_sizes()` is additional, not replacement
- Variants generated only when needed
- Main cover extraction logic unchanged

### Migration Path

1. Deploy backend changes
2. No immediate action required
3. Update frontend when ready
4. Variants generate automatically

---

## 🧪 Testing

### Unit Tests

```python
def test_generate_cover_variants():
    """Test variant generation creates all sizes."""
    collection = MusicCollection(music_root, db_path)
    slug = "test_album"

    result = collection._generate_cover_variants("Artist/Album", slug)

    assert result == True
    assert (covers_dir / f"{slug}_96x96.jpg").exists()
    assert (covers_dir / f"{slug}_256x256.jpg").exists()
    assert (covers_dir / f"{slug}_512x512.jpg").exists()

def test_get_cover_sizes():
    """Test URL dictionary returns all sizes."""
    collection = MusicCollection(music_root, db_path)

    sizes = collection.get_cover_sizes("Artist/Album")

    assert "96x96" in sizes
    assert "256x256" in sizes
    assert sizes["256x256"].endswith("_256x256.jpg")
```

### Integration Tests

```bash
# Test API endpoint
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=256x256" -o test.jpg

# Verify file size
ls -lh test.jpg  # Should be ~40KB

# Test invalid size
curl "http://localhost:5000/api/covers/Artist%2FAlbum?size=999x999"
# Should return JSON error

# Test fallback
curl "http://localhost:5000/api/covers/NonExistent%2FAlbum?size=256x256"
# Should return fallback image
```

---

## 🐛 Troubleshooting

### Issue: Variants not generating

**Symptoms:** 404 on size-specific requests
**Check:** Main cover exists? PIL/Pillow installed?
**Solution:** Ensure `_extract_cover()` succeeds first

### Issue: Large file sizes

**Symptoms:** Variants larger than expected
**Adjust:** Quality setting in `_generate_cover_variants()`:

```python
quality = 90 if size >= 256 else 85  # Increase quality
```

### Issue: Slow first request

**Expected:** 100-200ms delay on first size request
**Solution:** Pre-generate for popular albums with background job
