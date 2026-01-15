# Testing Guide - Android Auto

This page explains how to test your Android Auto integration using Google's Desktop Head Unit (DHU) tool.

---

## Overview

The **Desktop Head Unit (DHU)** is Google's official tool for testing Android Auto apps without needing a physical car or compatible head unit. It simulates the car display on your computer while your Android device (physical or emulator) provides the processing.

---

## Prerequisites

### Required Software

1. **Android Studio** - Latest stable version
2. **Android SDK Platform Tools** - Included with Android Studio
3. **Desktop Head Unit (DHU)** - Download from Android SDK Manager
4. **Android Device or Emulator** - Android 10+ with Google APIs

### System Requirements

- **OS:** Windows, macOS, or Linux
- **RAM:** 8GB minimum (16GB recommended for emulator)
- **Storage:** 10GB free space
- **Network:** Android device and computer on same network

---

## Step 1: Install Desktop Head Unit

### Option A: Android Studio SDK Manager

1. Open Android Studio
2. Go to **Tools → SDK Manager**
3. Select the **SDK Tools** tab
4. Check **Android Auto Desktop Head Unit**
5. Click **Apply** to download and install

### Option B: Command Line

```bash
# Navigate to Android SDK directory
cd ~/Android/Sdk

# Install DHU
./tools/bin/sdkmanager "extras;google;auto"

# Verify installation
ls platform-tools/desktop-head-unit*
```

---

## Step 2: Prepare Android Device

### Physical Device Setup

1. **Enable Developer Mode:**
   - Go to **Settings → About phone**
   - Tap **Build number** 7 times
   - Return to Settings, find **Developer options**

2. **Enable USB Debugging:**
   - **Settings → Developer options → USB debugging**
   - Toggle ON

3. **Install Android Auto App:**
   - Download from Google Play Store
   - Open and complete initial setup

4. **Enable Android Auto Developer Mode:**
   - Open Android Auto app
   - Tap hamburger menu (≡) → **About**
   - Tap **version number** 10 times
   - Developer mode enabled message appears

5. **Enable Unknown Sources:**
   - Return to menu → **Developer settings**
   - Toggle **Unknown sources** ON

6. **Connect to Computer:**
   - Use USB cable
   - Accept USB debugging prompt on device

### Android Emulator Setup

1. **Create AVD with Google APIs:**
   - Open **Tools → Device Manager**
   - Click **Create Device**
   - Select device (e.g., Pixel 5)
   - Choose system image: **Android 10+** with **Google APIs**
   - Click **Finish**

2. **Launch Emulator:**
   - Click play button next to AVD
   - Wait for emulator to boot

3. **Install Android Auto:**
   - Open Play Store in emulator
   - Search for "Android Auto"
   - Install and set up

4. **Enable Developer Mode:**
   - Follow same steps as physical device

---

## Step 3: Start Flask Server

Your Flask app must be accessible from the Android device:

```bash
# Start Flask with network access
flask run --host=0.0.0.0 --port=5000

# Verify Flask is running
curl http://localhost:5000/

# Note your computer's local IP
# macOS/Linux: ifconfig | grep "inet "
# Windows: ipconfig

# Example IP: 192.168.1.100
```

**Important:** Use your computer's local IP address (not localhost) when accessing from Android device.

---

## Step 4: Launch Desktop Head Unit

### Start DHU

```bash
# Navigate to platform-tools
cd ~/Android/Sdk/platform-tools

# Launch DHU (default port 5277)
./desktop-head-unit

# Or specify port
./desktop-head-unit --port 5277
```

**Windows:**
```cmd
cd %LOCALAPPDATA%\Android\Sdk\platform-tools
desktop-head-unit.exe
```

### DHU Window

When DHU launches, you'll see:
- Simulated car display (touchscreen)
- Control buttons (home, back, etc.)
- Debug console in terminal

---

## Step 5: Connect Android Device to DHU

### Automatic Connection

DHU automatically connects to Android devices via ADB:

```bash
# Verify device is connected
adb devices

# Should show:
# List of devices attached
# ABC123XYZ    device
```

### Manual Connection (if needed)

```bash
# Forward DHU port to device
adb forward tcp:5277 tcp:5277

# Start Android Auto on device
adb shell am start -n com.google.android.projection.gearhead/.MainActivity
```

### Verify Connection

On DHU window, you should see:
- Android Auto home screen
- Available apps listed
- "Mixtape Society" appears (if web app is accessible)

---

## Step 6: Test Your App

### Access Mixtape Society

1. **Open Browser on Android Device:**
   - Navigate to `http://192.168.1.100:5000` (your Flask IP)
   - Open a mixtape

2. **Check DHU Display:**
   - Mixtape should appear in Android Auto interface
   - Cover art should display
   - Controls should be responsive

### Test Playback

1. **Play a Track:**
   - Click play button in DHU
   - Audio should play on Android device
   - Metadata should update in DHU

2. **Test Controls:**
   - ▶️ Play - Should start playback
   - ⏸️ Pause - Should pause playback
   - ⏭️ Next - Should skip to next track
   - ⏮️ Previous - Should go to previous track

3. **Test Seeking:**
   - Drag progress bar in DHU
   - Playback position should update

---

## Step 7: Verify Cover Art Optimization

### Monitor Network Requests

**In Android Device Chrome:**

1. Enable **Remote Debugging:**
   - Chrome desktop → `chrome://inspect`
   - Find your device
   - Click **Inspect**

2. **Check Network Tab:**
   ```
   Request: /covers/artist_album_256x256.jpg
   Status: 200 OK
   Size: 42.3 KB (transferred)
   Time: 45ms
   ```

3. **Verify Sizes:**
   - Android Auto should request 256×256 (optimal)
   - Regular mobile should request 128×128 or 192×192
   - Desktop should request 512×512

### Check DHU Console

DHU terminal shows debug output:

```
[DHU] Media session updated
[DHU] Artwork: http://192.168.1.100:5000/covers/artist_album_256x256.jpg
[DHU] Title: Summer Vibes
[DHU] Artist: Various Artists
```

### Measure Bandwidth Savings

**Before optimization:**
```
Request: /covers/artist_album.jpg
Size: 387 KB
```

**After optimization:**
```
Request: /covers/artist_album_256x256.jpg
Size: 41 KB
Savings: 89.4%
```

---

## Common Testing Scenarios

### Test Case 1: First-Time Cover Load

**Goal:** Verify lazy generation works

**Steps:**
1. Clear cover cache: `rm data/cache/covers/*_*x*.jpg`
2. Play track with no cached variants
3. Observe ~200ms delay on first load
4. Subsequent loads instant (cached)

**Expected:**
- First request: 200-300ms
- Second request: <10ms
- Variant files created in cache directory

### Test Case 2: Platform Detection

**Goal:** Verify correct platform detection

**Test on:**
- ✅ Desktop browser → Should NOT trigger Android Auto mode
- ✅ Mobile Chrome → Should NOT trigger Android Auto mode
- ✅ Android Auto DHU → Should trigger Android Auto mode

**Verify:**
- Console logs show correct detection
- Appropriate artwork sizes requested
- UI changes applied (or not)

### Test Case 3: Offline Playback

**Goal:** Test PWA offline capabilities

**Steps:**
1. Load mixtape while online
2. Disconnect network
3. Attempt to play cached track

**Expected:**
- Previously cached tracks play
- Cover art shows (if cached)
- Graceful error for non-cached content

### Test Case 4: Multiple Devices

**Goal:** Test with different Android versions

**Test on:**
- Android 10 device
- Android 13 device
- Emulator with different screen sizes

**Verify:**
- All versions work correctly
- Cover art scales appropriately
- No crashes or errors

---

## Troubleshooting

### DHU Won't Start

**Symptoms:** `desktop-head-unit` command not found

**Solution:**
```bash
# Add to PATH
export PATH=$PATH:~/Android/Sdk/platform-tools

# Or use full path
~/Android/Sdk/platform-tools/desktop-head-unit
```

### Device Not Connected

**Symptoms:** DHU shows "Waiting for device..."

**Solution:**
```bash
# Check ADB connection
adb devices

# If no devices shown:
adb kill-server
adb start-server
adb devices

# Re-enable USB debugging on device
```

### App Not Appearing in DHU

**Symptoms:** DHU home screen doesn't show Mixtape Society

**Causes & Solutions:**

1. **Web app not accessible from device:**
   ```bash
   # On Android device browser, test:
   http://YOUR_COMPUTER_IP:5000
   
   # Should load mixtape player
   ```

2. **Wrong URL in Android Auto:**
   - Check device browser URL
   - Must use computer's local IP, not localhost

3. **Android Auto not in developer mode:**
   - Re-enable developer settings
   - Toggle "Unknown sources" ON

### Cover Art Not Showing

**Symptoms:** Tracks play but no cover art in DHU

**Debug:**

1. **Check Network Tab:**
   ```
   Request: /covers/artist_album_256x256.jpg
   Status: 404 (file not generated)
   ```

2. **Verify Backend:**
   ```bash
   # Check covers directory
   ls -la data/cache/covers/
   
   # Should have variants
   ```

3. **Check Console Logs:**
   ```javascript
   // Should show:
   "Generated 256x256 variant for artist_album"
   ```

### Audio Doesn't Play

**Symptoms:** Controls work but no sound

**Causes:**

1. **CORS headers missing:**
   - Check Flask response headers
   - Should include `Access-Control-Allow-Origin: *`

2. **Audio format unsupported:**
   - Check browser console for codec errors
   - Try different audio file

3. **Network issue:**
   - Check Flask logs
   - Verify HTTP 200 response for audio files

---

## Performance Benchmarks

Target performance metrics for Android Auto:

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Cover load time (cached) | <50ms | <100ms | >200ms |
| Cover load time (first) | <300ms | <500ms | >1s |
| Cover file size (256×256) | 30-50 KB | 50-80 KB | >100 KB |
| Playback start delay | <500ms | <1s | >2s |
| Control response time | <100ms | <300ms | >500ms |

### Measure Performance

```javascript
// Add to playerUtils.js
console.time('cover-load');
fetch(coverUrl).then(() => {
    console.timeEnd('cover-load');
});
```

---

## Automated Testing

### Playwright Test Example

```javascript
// tests/android-auto.spec.js
const { test, expect } = require('@playwright/test');

test('Android Auto cover art optimization', async ({ page }) => {
    // Navigate to mixtape
    await page.goto('http://localhost:5000/share/test-mixtape');
    
    // Play track
    await page.click('#big-play-btn');
    
    // Wait for cover art request
    const coverRequest = await page.waitForRequest(
        request => request.url().includes('_256x256.jpg')
    );
    
    // Verify correct size requested
    expect(coverRequest.url()).toContain('_256x256.jpg');
    
    // Verify response
    const response = await coverRequest.response();
    expect(response.status()).toBe(200);
    
    // Check file size
    const contentLength = parseInt(response.headers()['content-length']);
    expect(contentLength).toBeLessThan(100 * 1024); // <100KB
});
```

---

## Next Steps

After successful DHU testing:

1. ✅ Verify all features work in DHU
2. ✅ Test on physical device in actual car (if available)
3. ✅ Monitor bandwidth usage in production
4. ✅ Gather user feedback
5. → Deploy to production

---

## Related Documentation

- [Backend Implementation](backend-implementation.md) - Server-side setup
- [Frontend Integration](frontend-integration.md) - Client-side code
- [API Reference](api-reference.md) - Complete API docs
- [Android Auto Developer Docs](https://developer.android.com/training/cars/testing) - Official Google docs
