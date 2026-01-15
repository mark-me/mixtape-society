# Android Auto Integration Guide

## Quick Start: Using Size-Optimized Covers in Android Auto

This guide shows how to integrate the new size-optimized cover art API with your Android Auto app.

## Flask API Changes

### New Endpoint for Mixtape Metadata

Add this endpoint to your Flask app to provide Android Auto-compatible metadata:

```python
@app.route('/api/mixtapes/<mixtape_id>/metadata')
def get_mixtape_metadata(mixtape_id):
    """
    Returns mixtape metadata with size-optimized artwork URLs for Android Auto.
    """
    mixtape = mixtape_manager.get_mixtape(mixtape_id)
    if not mixtape:
        abort(404)
    
    # Get the first track's release directory for cover art
    first_track = mixtape.tracks[0] if mixtape.tracks else None
    release_dir = None
    
    if first_track:
        # Extract release directory from track path
        track_path = first_track['path']
        release_dir = '/'.join(track_path.split('/')[:-1])  # Remove filename
    
    # Get size-optimized cover URLs
    if release_dir:
        cover_sizes = collection.get_cover_sizes(release_dir)
        base_url = request.host_url.rstrip('/')
        
        artwork = [
            {
                "src": f"{base_url}/{cover_sizes['96x96']}",
                "sizes": "96x96",
                "type": "image/jpeg"
            },
            {
                "src": f"{base_url}/{cover_sizes['192x192']}",
                "sizes": "192x192",
                "type": "image/jpeg"
            },
            {
                "src": f"{base_url}/{cover_sizes['256x256']}",
                "sizes": "256x256",
                "type": "image/jpeg"
            },
            {
                "src": f"{base_url}/{cover_sizes['512x512']}",
                "sizes": "512x512",
                "type": "image/jpeg"
            }
        ]
    else:
        # Fallback artwork
        base_url = request.host_url.rstrip('/')
        artwork = [
            {
                "src": f"{base_url}/covers/_fallback.jpg",
                "sizes": "512x512",
                "type": "image/jpeg"
            }
        ]
    
    return jsonify({
        "id": mixtape_id,
        "title": mixtape.name,
        "artist": "Various Artists",
        "album": mixtape.name,
        "artwork": artwork,
        "tracks": [
            {
                "id": track['path'],
                "title": track['track'],
                "artist": track['artist'],
                "duration": track.get('duration', 0)
            }
            for track in mixtape.tracks
        ]
    })
```

## Android App Integration

### Step 1: Update Retrofit API Interface

Add the new endpoint to your `FlaskApiService`:

```java
public interface FlaskApiService {
    
    @GET("api/mixtapes")
    Call<List<Mixtape>> getMixtapes();
    
    @GET("api/mixtapes/{id}/metadata")
    Call<MixtapeMetadata> getMixtapeMetadata(@Path("id") String id);
}
```

### Step 2: Create Data Models

```java
// MixtapeMetadata.java
public class MixtapeMetadata {
    private String id;
    private String title;
    private String artist;
    private String album;
    private List<Artwork> artwork;
    private List<Track> tracks;
    
    // Getters...
    public String getId() { return id; }
    public String getTitle() { return title; }
    public String getArtist() { return artist; }
    public String getAlbum() { return album; }
    public List<Artwork> getArtwork() { return artwork; }
    public List<Track> getTracks() { return tracks; }
}

// Artwork.java
public class Artwork {
    private String src;
    private String sizes;
    private String type;
    
    // Getters...
    public String getSrc() { return src; }
    public String getSizes() { return sizes; }
    public String getType() { return type; }
}

// Track.java
public class Track {
    private String id;
    private String title;
    private String artist;
    private int duration;
    
    // Getters...
    public String getId() { return id; }
    public String getTitle() { return title; }
    public String getArtist() { return artist; }
    public int getDuration() { return duration; }
}
```

### Step 3: Update MediaBrowserService

Modify your `MixtapePlaybackService` to use the new metadata:

```java
@Override
public void onLoadChildren(@NonNull String parentId, 
                           @NonNull Result<List<MediaBrowserCompat.MediaItem>> result) {
    List<MediaBrowserCompat.MediaItem> mediaItems = new ArrayList<>();
    
    if (ROOT_ID.equals(parentId)) {
        // Root level - show "Mixtapes" category
        MediaDescriptionCompat description = new MediaDescriptionCompat.Builder()
            .setMediaId(MIXTAPES_ID)
            .setTitle("My Mixtapes")
            .build();
        
        mediaItems.add(new MediaBrowserCompat.MediaItem(
            description, 
            MediaBrowserCompat.MediaItem.FLAG_BROWSABLE
        ));
        
    } else if (MIXTAPES_ID.equals(parentId)) {
        // Fetch mixtapes with metadata from Flask API
        mediaItems = getMixtapesWithMetadata();
    }
    
    result.sendResult(mediaItems);
}

private List<MediaBrowserCompat.MediaItem> getMixtapesWithMetadata() {
    List<MediaBrowserCompat.MediaItem> items = new ArrayList<>();
    
    try {
        FlaskApiService apiService = RetrofitClient.getApiService();
        Call<List<Mixtape>> call = apiService.getMixtapes();
        retrofit2.Response<List<Mixtape>> response = call.execute();
        
        if (response.isSuccessful() && response.body() != null) {
            for (Mixtape mixtape : response.body()) {
                // Fetch detailed metadata for each mixtape
                Call<MixtapeMetadata> metadataCall = apiService.getMixtapeMetadata(mixtape.getId());
                retrofit2.Response<MixtapeMetadata> metadataResponse = metadataCall.execute();
                
                if (metadataResponse.isSuccessful() && metadataResponse.body() != null) {
                    MixtapeMetadata metadata = metadataResponse.body();
                    
                    // Find the 256x256 artwork (optimal for Android Auto)
                    String artworkUrl = null;
                    if (metadata.getArtwork() != null && !metadata.getArtwork().isEmpty()) {
                        for (Artwork art : metadata.getArtwork()) {
                            if ("256x256".equals(art.getSizes())) {
                                artworkUrl = art.getSrc();
                                break;
                            }
                        }
                        // Fallback to first available size
                        if (artworkUrl == null) {
                            artworkUrl = metadata.getArtwork().get(0).getSrc();
                        }
                    }
                    
                    MediaDescriptionCompat description = new MediaDescriptionCompat.Builder()
                        .setMediaId(metadata.getId())
                        .setTitle(metadata.getTitle())
                        .setSubtitle(metadata.getArtist())
                        .setIconUri(artworkUrl != null ? Uri.parse(artworkUrl) : null)
                        .build();
                    
                    items.add(new MediaBrowserCompat.MediaItem(
                        description,
                        MediaBrowserCompat.MediaItem.FLAG_PLAYABLE
                    ));
                }
            }
        }
    } catch (Exception e) {
        Log.e(TAG, "Failed to fetch mixtapes", e);
    }
    
    return items;
}
```

### Step 4: Update Media Session Metadata

When playing a track, set metadata with size-optimized artwork:

```java
private class MediaSessionCallback extends MediaSessionCompat.Callback {
    
    @Override
    public void onPlayFromMediaId(String mediaId, Bundle extras) {
        try {
            // Fetch metadata from Flask
            FlaskApiService apiService = RetrofitClient.getApiService();
            Call<MixtapeMetadata> call = apiService.getMixtapeMetadata(mediaId);
            retrofit2.Response<MixtapeMetadata> response = call.execute();
            
            if (response.isSuccessful() && response.body() != null) {
                MixtapeMetadata metadata = response.body();
                
                // Load artwork bitmap (Android Auto will choose appropriate size)
                Bitmap artwork = loadArtworkFromUrl(metadata.getArtwork());
                
                // Set MediaSession metadata
                MediaMetadataCompat.Builder metadataBuilder = new MediaMetadataCompat.Builder()
                    .putString(MediaMetadataCompat.METADATA_KEY_TITLE, metadata.getTitle())
                    .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, metadata.getArtist())
                    .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, metadata.getAlbum())
                    .putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, artwork);
                
                mediaSession.setMetadata(metadataBuilder.build());
                
                // Play first track
                if (!metadata.getTracks().isEmpty()) {
                    Track firstTrack = metadata.getTracks().get(0);
                    String audioUrl = "http://10.0.2.2:5000/audio/" + firstTrack.getId();
                    
                    MediaItem mediaItem = MediaItem.fromUri(audioUrl);
                    player.setMediaItem(mediaItem);
                    player.prepare();
                    player.play();
                    mediaSession.setActive(true);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error playing from media ID", e);
        }
    }
    
    private Bitmap loadArtworkFromUrl(List<Artwork> artworkList) {
        if (artworkList == null || artworkList.isEmpty()) {
            return null;
        }
        
        // Choose appropriate size based on context
        // For Android Auto, 256x256 or 512x512 are good choices
        String targetUrl = null;
        for (Artwork art : artworkList) {
            if ("256x256".equals(art.getSizes())) {
                targetUrl = art.getSrc();
                break;
            }
        }
        
        if (targetUrl == null) {
            targetUrl = artworkList.get(artworkList.size() - 1).getSrc(); // Use largest
        }
        
        try {
            URL url = new URL(targetUrl);
            return BitmapFactory.decodeStream(url.openConnection().getInputStream());
        } catch (Exception e) {
            Log.e(TAG, "Failed to load artwork", e);
            return null;
        }
    }
}
```

## Testing the Integration

### 1. Start Flask Server
```bash
flask run --host=0.0.0.0 --port=5000
```

### 2. Test API Endpoint
```bash
# Test metadata endpoint
curl http://localhost:5000/api/mixtapes/test_mixtape/metadata | jq

# Expected output:
{
  "id": "test_mixtape",
  "title": "Summer Vibes",
  "artist": "Various Artists",
  "album": "Summer Vibes",
  "artwork": [
    {
      "src": "http://localhost:5000/covers/artist_album_96x96.jpg",
      "sizes": "96x96",
      "type": "image/jpeg"
    },
    {
      "src": "http://localhost:5000/covers/artist_album_256x256.jpg",
      "sizes": "256x256",
      "type": "image/jpeg"
    },
    {
      "src": "http://localhost:5000/covers/artist_album_512x512.jpg",
      "sizes": "512x512",
      "type": "image/jpeg"
    }
  ],
  "tracks": [...]
}
```

### 3. Run Android App in Emulator
```bash
# In Android Studio, run your app on the emulator
# Check Logcat for network requests and errors
adb logcat | grep -i "mixtape\|retrofit\|cover"
```

### 4. Launch Desktop Head Unit
```bash
# Navigate to platform-tools directory
cd ~/Android/Sdk/platform-tools

# Launch DHU
./desktop-head-unit
```

### 5. Verify in Android Auto
- Open Android Auto in DHU
- Navigate to your app
- Verify mixtapes appear with cover art
- Play a mixtape and check that artwork displays correctly
- Monitor bandwidth usage (should be significantly reduced)

## Bandwidth Comparison

### Before Optimization
```
Request: http://10.0.2.2:5000/covers/artist_album.jpg
Response: 450KB (800x800 JPEG)
Total per mixtape: 450KB
```

### After Optimization
```
Request: http://10.0.2.2:5000/api/covers/Artist%2FAlbum?size=256x256
Response: 35KB (256x256 JPEG)
Total per mixtape: 35KB
Savings: ~92%
```

## Troubleshooting

### Issue: Artwork not displaying
**Check:**
1. Network connectivity between emulator and Flask server
2. URL encoding of release directory paths
3. CORS headers in Flask app
4. Image loading in Logcat

### Issue: Wrong artwork size
**Adjust size selection logic:**
```java
// For thumbnails, use 96x96 or 128x128
// For player UI, use 256x256 or 384x384
// For high-res displays, use 512x512
```

### Issue: Slow initial load
**This is expected:**
- First request generates all size variants (~100-200ms)
- Subsequent requests are instant (served from cache)
- Consider pre-generating variants for popular mixtapes

## Performance Tips

1. **Use 256x256 for Android Auto** - Optimal balance of quality and bandwidth
2. **Cache Bitmap objects** - Avoid reloading the same artwork multiple times
3. **Use Glide or Picasso** - Handle image loading, caching, and memory management
4. **Implement placeholder images** - Show while artwork loads
5. **Batch metadata requests** - Fetch multiple mixtapes at once if possible

## Next Steps

1. Implement the Flask endpoint for mixtape metadata
2. Update your Android data models
3. Modify MediaBrowserService to use new API
4. Test with Desktop Head Unit
5. Monitor bandwidth usage and adjust sizes as needed
6. Deploy to production

## Additional Resources

- Android Auto Media App documentation: https://developer.android.com/training/cars/media
- MediaBrowserService guide: https://developer.android.com/guide/topics/media-apps/audio-app/building-a-mediabrowserservice
- ExoPlayer documentation: https://exoplayer.dev/
