# Multi-Size Cover Image Implementation Guide

This guide shows how to implement multi-size cover images optimized for Android Auto, Chromecast, iOS, and other platforms.

## 📋 Overview

**Problem:** Different platforms need different cover art sizes:
- Android Auto requires 96×96 minimum
- iOS lock screen prefers 512×512
- Chromecast works best with 256×256
- Desktop displays can use 192×192 or 512×512

**Solution:** Generate multiple sizes when extracting covers, serve appropriate size based on platform.

---

## 🎯 Size Strategy

| Size Name | Dimensions | Use Case | Quality | Max Size |
|-----------|------------|----------|---------|----------|
| `tiny` | 96×96 | Android Auto minimum | 80 | 30KB |
| `small` | 192×192 | Android Auto optimal, general mobile | 82 | 75KB |
| `medium` | 256×256 | Chromecast, standard displays | 85 | 150KB |
| `large` | 512×512 | iOS lock screen, high-quality | 90 | 300KB |
| `original` | 800×800 | Maximum quality, desktop | 85 | 500KB |

---

## 📁 File Structure

After implementation, covers directory will look like:

```
covers/
├── abc123.jpg           # Original (800×800)
├── abc123_tiny.jpg      # 96×96 for Android Auto
├── abc123_small.jpg     # 192×192 for Android Auto/mobile
├── abc123_medium.jpg    # 256×256 for Chromecast
├── abc123_large.jpg     # 512×512 for iOS
├── def456.jpg
├── def456_tiny.jpg
├── def456_small.jpg
├── def456_medium.jpg
├── def456_large.jpg
└── fallback.jpg
```

---

## 🔧 Implementation Steps

### Step 1: Update `reader.py` (MusicCollection class)

**Add constants** at the top of the class (after line 52):

```python
# Cover image size configurations for different platforms
COVER_SIZES = {
    'original': 800,    # Maximum size for original
    'large': 512,       # iOS lock screen, Android Auto high quality
    'medium': 256,      # Chromecast, standard display
    'small': 192,       # Android Auto optimal
    'tiny': 96          # Android Auto minimum required
}

JPEG_QUALITY = 85
MAX_FILE_SIZE = 500 * 1024  # 500KB for original
```

**Replace `get_cover` method** (line 1310):

```python
def get_cover(self, release_dir: str) -> str | None:
    """Returns the relative path to a cached cover image for a given release directory.
    
    Now generates multiple sizes optimized for different platforms.
    """
    cache_key = hashlib.md5(release_dir.encode()).hexdigest()
    cache_file = self.covers_dir / f"{cache_key}.jpg"
    
    if not cache_file.exists():
        if self._extract_cover_to_file(release_dir, cache_file):
            # Generate all thumbnail sizes
            self._generate_cover_thumbnails(cache_file, cache_key)
        else:
            return "fallback.jpg"
    
    return f"{cache_key}.jpg"
```

**Add new method** `_generate_cover_thumbnails`:

```python
def _generate_cover_thumbnails(self, source_path: Path, cache_key: str) -> None:
    """Generate multiple sized versions of a cover for different platforms."""
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                else:
                    img = img.convert('RGB')
            
            # Generate each thumbnail size
            for size_name, max_size in self.COVER_SIZES.items():
                if size_name == 'original':
                    continue  # Already saved at source_path
                
                thumb = img.copy()
                thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Quality and size limits per variant
                quality_map = {
                    'large': (90, 300 * 1024),
                    'medium': (85, 150 * 1024),
                    'small': (82, 75 * 1024),
                    'tiny': (80, 30 * 1024)
                }
                
                quality, max_file_size = quality_map.get(size_name, (85, 100 * 1024))
                
                # Save thumbnail
                thumb_path = self.covers_dir / f"{cache_key}_{size_name}.jpg"
                thumb.save(thumb_path, 'JPEG', quality=quality, optimize=True)
                
                # Reduce quality if too large
                current_quality = quality
                while thumb_path.stat().st_size > max_file_size and current_quality > 50:
                    current_quality -= 10
                    thumb.save(thumb_path, 'JPEG', quality=current_quality, optimize=True)
                
                self._logger.debug(
                    f"Generated {size_name} thumbnail ({max_size}px): "
                    f"{thumb_path.stat().st_size / 1024:.1f}KB"
                )
                
    except Exception as e:
        self._logger.error(f"Failed to generate thumbnails for {cache_key}: {e}")
```

**Update `_extract_cover_to_file`** (line 1339) - just change the constants:

```python
def _extract_cover_to_file(self, release_dir: str, target_path: Path) -> bool:
    """Extract cover to file using class constants."""
    # ... existing code ...
    
    # Use class constants instead of local variables
    MAX_SIZE = self.COVER_SIZES['original']  # 800
    JPEG_QUALITY = self.JPEG_QUALITY          # 85
    MAX_FILE_SIZE = self.MAX_FILE_SIZE        # 500KB
    
    # ... rest of method unchanged ...
```

---

### Step 2: Update Flask Routes (play.py)

**Option A: Query Parameter Approach** (Recommended)

Update the existing `serve_cover` route:

```python
@play.route("/covers/<filename>")
def serve_cover(filename: str) -> Response:
    """Serves cover images with optional size parameter.
    
    Query Parameters:
        size: 'tiny', 'small', 'medium', 'large', 'original' (default)
    
    Examples:
        /covers/abc123.jpg               -> Returns 800×800
        /covers/abc123.jpg?size=tiny     -> Returns 96×96
        /covers/abc123.jpg?size=large    -> Returns 512×512
    """
    size = request.args.get('size', 'original')
    
    # Validate size
    valid_sizes = ['tiny', 'small', 'medium', 'large', 'original']
    if size not in valid_sizes:
        size = 'original'
    
    # Build filename with size suffix
    if size != 'original' and not filename.startswith('fallback'):
        base_name = filename.rsplit('.', 1)[0]
        ext = filename.rsplit('.', 1)[1] if '.' in filename else 'jpg'
        sized_filename = f"{base_name}_{size}.{ext}"
        
        # Fall back to original if sized version doesn't exist
        sized_path = Path(current_app.config["COVER_DIR"]) / sized_filename
        if not sized_path.exists():
            sized_filename = filename
    else:
        sized_filename = filename
    
    return send_from_directory(current_app.config["COVER_DIR"], sized_filename)
```

**Option B: Path-Based Approach** (Alternative)

Add a new route:

```python
@play.route("/covers/<size>/<filename>")
def serve_cover_sized(size: str, filename: str) -> Response:
    """Serves cover with size in URL path.
    
    Examples:
        /covers/tiny/abc123.jpg
        /covers/large/abc123.jpg
    """
    valid_sizes = ['tiny', 'small', 'medium', 'large', 'original']
    if size not in valid_sizes:
        abort(400)
    
    if size != 'original' and not filename.startswith('fallback'):
        base_name = filename.rsplit('.', 1)[0]
        ext = filename.rsplit('.', 1)[1] if '.' in filename else 'jpg'
        sized_filename = f"{base_name}_{size}.{ext}"
        
        sized_path = Path(current_app.config["COVER_DIR"]) / sized_filename
        if not sized_path.exists():
            sized_filename = filename
    else:
        sized_filename = filename
    
    return send_from_directory(current_app.config["COVER_DIR"], sized_filename)
```

---

### Step 3: Update JavaScript (playerUtils.js)

Replace `extractMetadataFromDOM` function:

```javascript
export function extractMetadataFromDOM(trackElement) {
    const iOS = detectiOS();
    const android = detectAndroid();
    const coverImg = trackElement.querySelector('.track-cover');
    let artwork = [];

    if (coverImg && coverImg.src) {
        const mimeType = getMimeTypeFromUrl(coverImg.src);
        const coverUrl = new URL(coverImg.src, window.location.origin);
        const basePath = coverUrl.pathname; // e.g., /covers/abc123.jpg
        
        if (iOS) {
            // iOS: Fewer, larger sizes
            artwork = [
                { src: `${basePath}?size=large`, sizes: '512x512', type: mimeType },
                { src: `${basePath}?size=medium`, sizes: '256x256', type: mimeType },
                { src: `${basePath}?size=small`, sizes: '128x128', type: mimeType }
            ];
        } else if (android) {
            // Android: Full range including required minimum
            artwork = [
                { src: `${basePath}?size=tiny`, sizes: '96x96', type: mimeType },
                { src: `${basePath}?size=small`, sizes: '128x128', type: mimeType },
                { src: `${basePath}?size=small`, sizes: '192x192', type: mimeType },
                { src: `${basePath}?size=medium`, sizes: '256x256', type: mimeType },
                { src: `${basePath}?size=large`, sizes: '512x512', type: mimeType }
            ];
        } else {
            // Desktop: Simple set
            artwork = [
                { src: `${basePath}?size=small`, sizes: '192x192', type: mimeType },
                { src: `${basePath}?size=large`, sizes: '512x512', type: mimeType }
            ];
        }
    }

    return {
        title: trackElement.dataset.title || 'Unknown',
        artist: trackElement.dataset.artist || 'Unknown Artist',
        album: trackElement.dataset.album || '',
        artwork: artwork
    };
}
```

---

### Step 4: Update Chromecast Integration (chromecast.js)

Find the `loadQueue` function and update the metadata creation:

```javascript
function loadQueue(session) {
    const tracks = window.__mixtapeData?.tracks || [];
    const quality = localStorage.getItem('audioQuality') || 'medium';

    const queueItems = tracks.map((track, index) => {
        // ... existing track URL code ...
        
        const metadata = new chrome.cast.media.MusicTrackMediaMetadata();
        metadata.title = track.track || 'Unknown Title';
        metadata.artist = track.artist || 'Unknown Artist';
        metadata.albumName = track.album || '';
        metadata.trackNumber = index + 1;

        if (track.cover) {
            // Request medium size for Chromecast (optimal: 256×256)
            const coverUrl = new URL(track.cover, window.location.origin);
            const basePath = coverUrl.pathname;
            const chromecastCoverUrl = new URL(
                `${basePath}?size=medium`, 
                window.location.origin
            ).href;
            
            metadata.images = [new chrome.cast.Image(chromecastCoverUrl)];
        }

        mediaInfo.metadata = metadata;
        // ... rest of code ...
    });
}
```

---

## 🔄 Migration Strategy

### For Existing Covers

If you already have covers in your cache, you need to regenerate thumbnails:

**Option 1: Regenerate All (Recommended)**

```python
# Add a management command or admin route
def regenerate_all_thumbnails():
    """Regenerate thumbnails for all existing covers."""
    covers_dir = Path(current_app.config["COVER_DIR"])
    
    for cover_file in covers_dir.glob("*.jpg"):
        # Skip thumbnails and fallback
        if '_' in cover_file.stem or cover_file.name == 'fallback.jpg':
            continue
        
        cache_key = cover_file.stem
        music_collection._generate_cover_thumbnails(cover_file, cache_key)
        print(f"Regenerated thumbnails for {cover_file.name}")
```

**Option 2: Lazy Generation**

Thumbnails will be generated automatically when covers are next accessed (via `get_cover`).

**Option 3: Rebuild Cache**

```bash
# Delete existing cache (except fallback)
rm -rf cache/covers/*.jpg  # Keep fallback.jpg
# Restart app - covers will regenerate on access
```

---

## 🧪 Testing

### 1. Test Cover Generation

```python
# In Python shell or test
from music_collection import MusicCollection
from pathlib import Path

mc = MusicCollection('/path/to/music', 'data/collection.db')
cover_path = mc.get_cover('Artist/Album')

# Check that all sizes were created
covers_dir = Path('cache/covers')
cache_key = cover_path.replace('.jpg', '')

assert (covers_dir / f"{cache_key}_tiny.jpg").exists()
assert (covers_dir / f"{cache_key}_small.jpg").exists()
assert (covers_dir / f"{cache_key}_medium.jpg").exists()
assert (covers_dir / f"{cache_key}_large.jpg").exists()
assert (covers_dir / f"{cache_key}.jpg").exists()  # original
```

### 2. Test Flask Routes

```bash
# Test different sizes
curl -I http://localhost:5000/covers/abc123.jpg
curl -I http://localhost:5000/covers/abc123.jpg?size=tiny
curl -I http://localhost:5000/covers/abc123.jpg?size=large

# Check file sizes are appropriate
curl -s http://localhost:5000/covers/abc123.jpg?size=tiny -o /tmp/tiny.jpg
ls -lh /tmp/tiny.jpg  # Should be ~30KB or less

curl -s http://localhost:5000/covers/abc123.jpg?size=large -o /tmp/large.jpg
ls -lh /tmp/large.jpg  # Should be ~300KB or less
```

### 3. Test in Browser

```javascript
// In browser console
const track = document.querySelector('.track-item');
const metadata = extractMetadataFromDOM(track);
console.log(metadata.artwork);

// Should show different URLs with ?size= parameter
// Example output:
// [
//   { src: "/covers/abc123.jpg?size=tiny", sizes: "96x96", ... },
//   { src: "/covers/abc123.jpg?size=small", sizes: "192x192", ... },
//   ...
// ]
```

### 4. Test Android Auto

1. Connect Android phone to car
2. Open mixtape in Chrome
3. Check browser console for:
   ```
   🚗 Android Auto detected!
   🚗 Setting up Android Auto Media Session
   ```
4. Verify album art shows on car display
5. Check network tab shows correct size being loaded (should be `?size=small` or `?size=medium`)

### 5. Test Chromecast

1. Cast to Chromecast device
2. Check network tab for cover requests
3. Should see `?size=medium` being requested
4. Verify cover appears on TV

---

## 📊 Performance Impact

### Storage

**Before:** 1 file per album (~500KB)  
**After:** 5 files per album (~1.1MB total)

For 1000 albums:
- Before: ~500MB
- After: ~1.1GB (+600MB)

### Network

**Bandwidth savings:**

| Platform | Before | After | Savings |
|----------|--------|-------|---------|
| Android Auto | 500KB | 75KB | 85% |
| Mobile | 500KB | 150KB | 70% |
| Chromecast | 500KB | 150KB | 70% |
| Desktop | 500KB | 300-500KB | 0-40% |

**For 20-track mixtape:**
- Android Auto: 10MB → 1.5MB (saves 8.5MB)
- Mobile: 10MB → 3MB (saves 7MB)

### Generation Time

**Per album:**
- Original only: ~200ms
- With 4 thumbnails: ~400ms (+200ms)

**For 1000 albums:**
- Additional ~3 minutes one-time cost

---

## 🐛 Troubleshooting

### Thumbnails Not Generated

**Check:**
```python
# Verify PIL is working
from PIL import Image
img = Image.open('covers/abc123.jpg')
print(img.size)

# Check permissions
import os
covers_dir = Path('cache/covers')
print(os.access(covers_dir, os.W_OK))  # Should be True
```

### Wrong Size Served

**Check:**
```python
# In Flask route, add debug logging
@play.route("/covers/<filename>")
def serve_cover(filename: str) -> Response:
    size = request.args.get('size', 'original')
    current_app.logger.debug(f"Serving {filename} at size {size}")
    # ... rest of code
```

### Android Auto Not Using Right Size

**Verify artwork array:**
```javascript
// In androidAuto.js, log artwork
function prepareArtwork(originalArtwork) {
    console.log('🚗 Artwork URLs:', originalArtwork.map(a => a.src));
    // Should show ?size=tiny, ?size=small, etc.
    // ...
}
```

---

## 💡 Best Practices

1. **Generate on extraction:** Always create thumbnails when cover is first extracted
2. **Lazy generation fallback:** Have on-demand generation as backup
3. **Use query parameters:** Easier to implement than path-based routing
4. **Log thumbnail creation:** Track what's being generated for debugging
5. **Monitor file sizes:** Ensure thumbnails stay within target sizes
6. **Test on real devices:** Android Auto behavior differs from desktop

---

## 🚀 Optional Enhancements

### 1. WebP Support

```python
# In _generate_cover_thumbnails, add WebP generation
if 'webp' in supported_formats:
    thumb_webp = img.copy()
    webp_path = self.covers_dir / f"{cache_key}_{size_name}.webp"
    thumb_webp.save(webp_path, 'WEBP', quality=quality)
```

### 2. Responsive Images in HTML

```html
<picture>
    <source srcset="/covers/abc123.jpg?size=tiny" media="(max-width: 200px)">
    <source srcset="/covers/abc123.jpg?size=small" media="(max-width: 400px)">
    <source srcset="/covers/abc123.jpg?size=medium" media="(max-width: 800px)">
    <img src="/covers/abc123.jpg?size=large" alt="Album cover">
</picture>
```

### 3. CDN Integration

```python
# Serve from CDN
def get_cover_url(filename, size='original'):
    if USE_CDN:
        return f"https://cdn.example.com/covers/{filename}?size={size}"
    return url_for('play.serve_cover', filename=filename, size=size)
```

---

This implementation provides optimal cover delivery for all platforms while maintaining backward compatibility!
