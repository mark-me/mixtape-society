![PWA](../../images/app.png){ align=right width="90" }

# Progressive Web App (PWA) Optimization

Mixtape Society is designed as a Progressive Web App, providing an app-like experience without requiring installation from an app store. This is especially powerful on iOS devices, where PWA features unlock native capabilities like AirPlay streaming, background playback, and home screen installation.

## 🍎 Why PWA Matters for iOS Users

Apple devices have excellent built-in support for web audio streaming. By optimizing the PWA experience, iOS users get:

- **Native AirPlay integration** – Stream directly to Apple TV, HomePod, AirPort Express
- **Lock screen controls** – Full media controls without unlocking phone
- **Background playback** – Keep playing with screen off or while using other apps
- **Home screen installation** – Launch like a native app
- **Offline support** – Continue playing cached mixtapes without internet
- **Immersive fullscreen** – Cassette mode with landscape orientation lock

## 🎵 Native AirPlay Support

**Good news: AirPlay already works!** No additional code needed.

When iOS users play a mixtape in Safari, they automatically get native AirPlay support through the system audio player. This is actually superior to custom implementations because:

### How It Works

1. **User opens mixtape** in Safari (iOS 10+ or macOS)
2. **Starts playing a track** – System audio controls appear
3. **Taps AirPlay icon** – Built into the audio controls
4. **Selects device** – Apple TV, HomePod, or AirPlay speakers
5. **Streams seamlessly** – High-quality audio to selected device

### Advantages Over Custom Implementation

| Feature | Native AirPlay | Custom Integration |
|---------|---------------|-------------------|
| **Development effort** | ✅ Zero (already works) | ❌ Significant (server-side streaming) |
| **Device compatibility** | ✅ All AirPlay devices | ⚠️ Requires device discovery |
| **Audio quality** | ✅ Lossless (if supported) | ⚠️ Depends on implementation |
| **Battery efficiency** | ✅ System-optimized | ⚠️ Must manage manually |
| **UI/UX** | ✅ Native iOS design | ❌ Custom UI needed |
| **Maintenance** | ✅ Apple handles updates | ❌ Must maintain library |

### Where to Find AirPlay Controls

**Safari on iPhone/iPad:**
- Controls appear in the Now Playing widget
- Available in Control Center
- Lock screen media controls
- Notification shade quick access

**Safari on Mac:**
- Menu bar audio icon
- System audio controls
- Touch Bar (if available)

## 📱 PWA Installation Guide

Encourage users to install the mixtape player to their home screen for the best experience.

### Installation Instructions (iOS)

**For Mixtape Recipients:**

1. **Open the mixtape link** in Safari (must be Safari, not Chrome)
2. **Tap the Share button** (square with arrow pointing up)
3. **Scroll down and tap "Add to Home Screen"**
4. **Customize the name** if desired (defaults to "Mixtape Society")
5. **Tap "Add"** in the top-right corner

The mixtape icon now appears on the home screen like a native app!

### Why Users Should Install

**Enhanced Experience:**
- 🚀 Launches instantly (no Safari UI)
- 📺 Fullscreen immersive player
- 🎨 Custom app icon with mixtape branding
- 🔄 Faster load times (cached resources)
- ✈️ Works offline with cached tracks
- 🎵 Better audio controls and AirPlay access

**Perfect for:**
- Regular listeners of specific mixtapes
- Party playlists used frequently
- Gift mixtapes meant to be kept
- Family music collections

## 🎮 Media Session API Integration

The app uses the Media Session API to provide native OS controls. This works on both iOS and Android.

### Features Provided

**Lock Screen Controls:**
```javascript
// Already implemented in playerUtils.js
export function setupLocalMediaSession(metadata, playerControls) {
    navigator.mediaSession.metadata = new MediaMetadata({
        title: metadata.title,
        artist: metadata.artist,
        album: metadata.album,
        artwork: metadata.artwork  // Shows cover art on lock screen
    });

    // Action handlers for hardware buttons
    navigator.mediaSession.setActionHandler('play', () => playerControls.play());
    navigator.mediaSession.setActionHandler('pause', () => playerControls.pause());
    navigator.mediaSession.setActionHandler('previoustrack', () => playerControls.previous());
    navigator.mediaSession.setActionHandler('nexttrack', () => playerControls.next());
}
```

**What Users Get:**

- **Lock screen** – Play, pause, skip tracks without unlocking
- **Control Center** – Quick access to playback controls (swipe down from top-right)
- **CarPlay** – Control mixtapes from car dashboard (iOS 14.5+)
- **Hardware buttons** – Headphone/earphone controls work
- **Now Playing** – See current track and album art

### iOS-Specific Optimizations

**Artwork Optimization:**
```javascript
// From playerUtils.js - iOS prefers specific sizes
if (iOS) {
    artwork = [
        { src: absoluteSrc, sizes: '512x512', type: mimeType }, // Primary for iOS
        { src: absoluteSrc, sizes: '256x256', type: mimeType },
        { src: absoluteSrc, sizes: '128x128', type: mimeType }
    ];
}
```

iOS displays artwork most reliably at 512×512 pixels. The app automatically provides this optimization.

**Version Detection:**
```javascript
// Detect iOS version and capabilities
export function detectiOS() {
    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;

    if (!isIOS) return null;

    const match = ua.match(/OS (\d+)_(\d+)/);
    const major = match ? parseInt(match[1], 10) : 0;

    return {
        isIOS: true,
        version: major,
        supportsMediaSession: major >= 15,  // iOS 15+ required
        isPWA: window.navigator.standalone === true
    };
}
```

## 📺 Fullscreen Cassette Experience

The cassette player provides an immersive retro experience, especially on mobile devices.

### Mobile Behavior

**Automatic Optimizations:**

1. **Fullscreen mode** – Removes browser chrome for immersion
2. **Landscape lock** – Forces horizontal orientation for cassette view
3. **Keep awake** – Screen stays on during playback
4. **Restore on exit** – Returns to normal orientation when stopping

**Implementation:**
```javascript
// From cassettePlayer.js
async function lockOrientationLandscape() {
    if (screen.orientation && screen.orientation.lock) {
        try {
            await screen.orientation.lock('landscape');
            console.log('🔒 Orientation locked to landscape');
        } catch (err) {
            console.warn('⚠️ Could not lock orientation:', err);
        }
    }
}

// Enters fullscreen and locks orientation when user taps play
async function enterFullscreenAndLock() {
    const container = document.getElementById('cassette-player-container');

    if (container.requestFullscreen) {
        await container.requestFullscreen();
    } else if (container.webkitRequestFullscreen) {  // iOS Safari
        await container.webkitRequestFullscreen();
    }

    await lockOrientationLandscape();
}
```

### User Experience Flow

**Starting Cassette Mode:**
1. User taps cassette mode toggle button
2. Cassette player appears with spinning reels
3. On first interaction (play/pause), device enters fullscreen
4. Screen locks to landscape orientation
5. Immersive walkman experience begins

**During Playback:**
- Phone lock/unlock maintains playback
- AirPlay controls available from lock screen
- Physical buttons control playback
- Screen stays awake (no sleep timeout)

**Stopping:**
- Stop button unlocks orientation
- User can exit fullscreen anytime
- Orientation returns to user preference

## 🔄 Service Worker & Offline Support

The PWA uses a service worker to enable offline playback and fast loading.

### Current Implementation

**Service Worker Registration:**
```javascript
// In base template
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('Service Worker registered:', registration);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    });
}
```

**What Gets Cached:**
- Core HTML, CSS, and JavaScript files
- App icons and branding
- Mixtape metadata and track listings
- Previously played audio files
- Cover art images

### Offline Indicator

```html
<!-- Shows when offline in PWA mode -->
<div id="offline-indicator"
     class="alert alert-warning"
     style="display: none;">
    <i class="bi bi-wifi-off"></i>
    <strong>Offline Mode</strong> - Playing cached tracks only
</div>
```

**How It Works:**
1. User loses internet connection
2. Yellow banner appears at top
3. Previously played tracks remain available
4. New tracks show as unavailable
5. Banner disappears when connection restored

## 📊 PWA Manifest Configuration

The app's `manifest.json` defines PWA behavior:

```json
{
  "name": "Mixtape Society",
  "short_name": "Mixtapes",
  "description": "Create and share beautiful music mixtapes",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#212529",
  "theme_color": "#198754",
  "orientation": "any",
  "icons": [
    {
      "src": "/static/icons/icon-72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-96.png",
      "sizes": "96x96",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-128.png",
      "sizes": "128x128",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-144.png",
      "sizes": "144x144",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-152.png",
      "sizes": "152x152",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/static/icons/icon-384.png",
      "sizes": "384x384",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### Key Properties Explained

| Property | Value | Purpose |
|----------|-------|---------|
| `display: "standalone"` | Full screen, no browser UI | App-like experience |
| `theme_color: "#198754"` | Green accent | Colors iOS status bar |
| `orientation: "any"` | User choice default | Allows portrait and landscape |
| `purpose: "maskable"` | Adaptive icon | Looks good on all Android launchers |

### iOS-Specific Meta Tags

```html
<!-- From play_mixtape.html -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Mixtape Society">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
```

These tags ensure iOS treats the PWA like a native app when added to home screen.

## 🎨 UI/UX Optimizations for Mobile

### Touch-Friendly Controls

**Large tap targets:**
- All buttons minimum 44×44 pixels (Apple HIG recommendation)
- Generous spacing between interactive elements
- Visual feedback on tap (active states)

**Responsive Design:**
- Player adapts to screen size
- Cover art scales appropriately
- Track list optimized for scrolling
- Bottom player bar always accessible

### Gesture Support

**Swipe Gestures:**
- Swipe left/right on track list to skip
- Pull-to-refresh for mixtape updates (PWA mode)
- Swipe down to dismiss modals

**Haptic Feedback (iOS 10+):**
```javascript
// Subtle vibration on button press
if (navigator.vibrate) {
    navigator.vibrate(10);  // 10ms gentle tap
}
```

## 🔐 Privacy & Security

### HTTPS Requirement

PWA features (service workers, media session, fullscreen) require HTTPS. Mixtape Society enforces this:

```python
# Flask app configuration
if not app.debug:
    @app.before_request
    def redirect_to_https():
        if request.headers.get('X-Forwarded-Proto') == 'http':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
```

### Data Privacy

**What's Stored Locally:**
- User preferences (quality settings, theme)
- Player mode (cassette vs. modern)
- Cached audio files
- Service worker cache

**What's NOT Stored:**
- User identity or login info
- Listening history or analytics
- Location data
- Personal information

**Cache Management:**
```javascript
// Users can clear cache in browser settings
// Or use the built-in cache clear option (if implemented)
localStorage.clear();
caches.keys().then(names => {
    names.forEach(name => caches.delete(name));
});
```

## 📈 Performance Optimizations

### Lazy Loading

**Images:**
```html
<img src="cover.jpg" loading="lazy" alt="Cover art">
```

**Audio:**
- Only loads when user hits play
- Preloads next track in queue (5 seconds ahead)
- Quality-based streaming (lower bitrate on slow connections)

### Resource Hints

```html
<!-- Preconnect to CDN -->
<link rel="preconnect" href="https://cdn.jsdelivr.net">

<!-- Prefetch critical assets -->
<link rel="prefetch" href="/static/css/cassette.css">
```

### Adaptive Quality

```javascript
// Automatically adjusts based on network conditions
const quality = navigator.connection?.effectiveType === '4g'
    ? 'high'
    : 'medium';
```

## 🚀 Future PWA Enhancements

### Planned Features

**Background Sync:**
- Queue mixtapes for offline download
- Sync listening progress across devices
- Pre-cache entire mixtapes automatically

**Web Share API:**
```javascript
// Share mixtapes directly from PWA
if (navigator.share) {
    navigator.share({
        title: mixtape.title,
        text: 'Check out this mixtape!',
        url: mixtape.url
    });
}
```

**Notification API:**
```javascript
// Notify when new tracks added to followed mixtapes
if (Notification.permission === 'granted') {
    new Notification('New track added to Summer Vibes!');
}
```

**Install Prompt:**
```javascript
// Smart prompt to install PWA at optimal moment
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Show custom install button
});
```

## 📱 Testing Checklist

### iOS Testing

- [ ] Install to home screen from Safari
- [ ] Launch from home screen (standalone mode)
- [ ] Verify splash screen appears
- [ ] Check status bar color matches theme
- [ ] Test lock screen controls
- [ ] Verify AirPlay button appears
- [ ] Stream to AirPlay device successfully
- [ ] Test background playback (screen off)
- [ ] Verify cassette fullscreen mode
- [ ] Check orientation lock in cassette mode
- [ ] Test offline playback (airplane mode)
- [ ] Confirm service worker caching
- [ ] Verify proper icon display
- [ ] Test CarPlay integration (iOS 14.5+)

### Android Testing

- [ ] Install prompt appears correctly
- [ ] Install to home screen
- [ ] Verify maskable icon adaptation
- [ ] Test lock screen controls
- [ ] Check notification controls
- [ ] Verify Chromecast button appears
- [ ] Cast to Chromecast device
- [ ] Test background playback
- [ ] Check offline indicator
- [ ] Verify service worker updates

## 🐛 Troubleshooting

### AirPlay Not Appearing (iOS)

**Possible causes:**
- Using Chrome instead of Safari (must use Safari)
- Device and AirPlay receiver on different WiFi networks
- AirPlay device turned off or unavailable
- Audio hasn't started playing yet

**Solution:**
1. Confirm using Safari browser
2. Check WiFi connection
3. Start playing a track first
4. Look for AirPlay icon in audio controls

### PWA Won't Install

**iOS:**
- Must use Safari (not Chrome or Firefox)
- Requires iOS 11.3 or later
- Some enterprise MDM policies block PWA installation

**Android:**
- Requires Chrome 72+ or Edge 79+
- Service worker must be registered
- Site must be served over HTTPS
- Manifest must be valid

### Lock Screen Controls Not Working

**Check these:**
```javascript
// Verify Media Session API support
console.log('Media Session:', 'mediaSession' in navigator);

// Check if metadata is set
console.log('Metadata:', navigator.mediaSession.metadata);

// Verify action handlers
console.log('Actions:', navigator.mediaSession);
```

**Common issues:**
- Audio element must have started playback
- Metadata must include title, artist, artwork
- Action handlers must be set before playback
- iOS 15+ required for full support

### Offline Mode Not Working

**Verify service worker:**
```javascript
// Check registration
navigator.serviceWorker.getRegistration()
    .then(reg => console.log('SW registered:', reg))
    .catch(err => console.error('SW error:', err));

// Check cache
caches.keys()
    .then(names => console.log('Cached:', names));
```

**Common issues:**
- Service worker not registered
- HTTPS required (doesn't work on http://)
- Cache storage full or disabled
- Private browsing mode (cache disabled)

## 📚 Resources

**Apple Developer Documentation:**
- [Configuring Web Applications](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html)
- [Media Session API](https://developer.apple.com/documentation/webkitjs/mediasession)
- [AirPlay Overview](https://developer.apple.com/airplay/)

**Web Standards:**
- [PWA Builder](https://www.pwabuilder.com/)
- [Media Session API Spec](https://w3c.github.io/mediasession/)
- [Service Worker Spec](https://w3c.github.io/ServiceWorker/)

**Testing Tools:**
- [Lighthouse PWA Audit](https://developers.google.com/web/tools/lighthouse)
- [Web.dev PWA Checklist](https://web.dev/pwa-checklist/)
- [Safari Web Inspector](https://developer.apple.com/safari/tools/)

---

By focusing on PWA optimization rather than custom AirPlay integration, Mixtape Society provides a superior user experience with less complexity and better long-term maintainability. The native capabilities of iOS combined with web standards deliver everything users need.
