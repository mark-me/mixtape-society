# PWA Quick Start Checklist

## ⚡ 30-Minute Implementation Path

### Phase 1: Core PWA Files (10 minutes)

- [ ] **Copy service-worker.js to app root**
  ```bash
  cp service-worker.js /path/to/mixtape-society/service-worker.js
  ```

- [ ] **Copy manifest.json to app root**
  ```bash
  cp manifest.json /path/to/mixtape-society/manifest.json
  ```

- [ ] **Copy pwa-manager.js to static directory**
  ```bash
  mkdir -p /path/to/mixtape-society/static/js/pwa
  cp pwa-manager.js /path/to/mixtape-society/static/js/pwa/pwa-manager.js
  ```

- [ ] **Copy pwa_routes.py to app directory**
  ```bash
  cp pwa_routes.py /path/to/mixtape-society/pwa_routes.py
  ```

### Phase 2: Backend Integration (5 minutes)

- [ ] **Update app.py - Add imports**
  ```python
  from pwa_routes import create_pwa_blueprint
  ```

- [ ] **Register PWA blueprint**
  ```python
  # After other blueprints
  app.register_blueprint(create_pwa_blueprint())
  ```

- [ ] **Update play.py - Add cache headers**
  ```python
  # In stream_audio function, before return:
  response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
  response.headers["Access-Control-Allow-Origin"] = "*"
  ```

### Phase 3: Frontend Integration (10 minutes)

- [ ] **Update base.html - Add to `<head>`**
  ```html
  <!-- PWA Manifest -->
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#198754">
  
  <!-- Apple PWA -->
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="Mixtape Society">
  ```

- [ ] **Update base.html - Add before `</body>`**
  ```html
  <!-- PWA Manager -->
  <script type="module" src="{{ url_for('static', filename='js/pwa/pwa-manager.js') }}"></script>
  ```

- [ ] **Update play_mixtape.html - Add after navbar**
  ```html
  <!-- Offline Indicator -->
  <div id="offline-indicator" class="alert alert-warning mb-0 text-center" style="display: none;">
      <i class="bi bi-wifi-off me-2"></i>
      <strong>Offline Mode</strong> - Playing cached tracks only
  </div>
  ```

- [ ] **Add download button near big play button**
  ```html
  <button id="download-mixtape-btn" class="btn btn-success">
      <i class="bi bi-download me-2"></i>
      Download for Offline
  </button>
  ```

- [ ] **Add cache management modal** (copy from pwa-ui-components.html)

### Phase 4: Icons (5 minutes)

- [ ] **Create icons directory**
  ```bash
  mkdir -p static/icons
  ```

- [ ] **Generate PWA icons** (choose one method):
  
  **Option A: Use online tool** (fastest)
  - Visit https://www.pwabuilder.com/imageGenerator
  - Upload your logo
  - Download generated icons
  - Extract to `static/icons/`
  
  **Option B: Use Python script**
  ```python
  from PIL import Image
  from pathlib import Path
  
  source = Path("static/logo.png")  # Your logo
  output = Path("static/icons/")
  output.mkdir(exist_ok=True)
  
  for size in [72, 96, 128, 144, 152, 192, 384, 512]:
      with Image.open(source) as img:
          img = img.convert('RGBA')
          img = img.resize((size, size), Image.LANCZOS)
          img.save(output / f"icon-{size}.png", 'PNG')
  ```

### Phase 5: Testing (5 minutes)

- [ ] **Start your Flask app**
  ```bash
  python app.py
  ```

- [ ] **Open Chrome DevTools (F12)**
  - Go to **Application** tab
  - Check **Manifest** section
  - Verify icons and metadata appear

- [ ] **Check Service Worker**
  - In Application tab → Service Workers
  - Should see "activated and is running"

- [ ] **Test Offline Mode**
  - Visit a mixtape: `/play/share/your-slug`
  - Check "Offline" in Service Workers section
  - Refresh page
  - Should still load!

- [ ] **Run Lighthouse Audit**
  - DevTools → Lighthouse tab
  - Check "Progressive Web App"
  - Generate report
  - Aim for 90+ score

---

## 🎯 Minimal Viable PWA (15 minutes)

If you're REALLY pressed for time, here's the absolute minimum:

### Must-Have Files:
1. `service-worker.js` (in root)
2. `manifest.json` (in root)
3. PWA meta tags in `base.html`

### Must-Have Code:
```html
<!-- base.html <head> -->
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#198754">
```

```python
# app.py
@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')
```

This gives you:
✅ Offline page caching
✅ Basic installability
✅ Service worker benefits

---

## ✅ Verification Checklist

### Service Worker Active?
```javascript
// In browser console:
navigator.serviceWorker.getRegistration().then(reg => 
    console.log('SW Status:', reg ? 'Active' : 'Not registered')
);
```

### Manifest Valid?
- Open DevTools → Application → Manifest
- Should show app name, icons, colors

### Cache Working?
- Open DevTools → Application → Cache Storage
- Should see cache entries after visiting pages

### Offline Works?
- Enable offline mode in DevTools
- Refresh page
- Should load from cache

---

## 🐛 Quick Troubleshooting

### "Service Worker not found"
**Fix:** Ensure service-worker.js is in app root, not /static/

### "Manifest errors"
**Fix:** Check manifest.json syntax with JSONLint

### "Icons not showing"
**Fix:** Verify icon paths in manifest match actual file locations

### "Not installable"
**Fix:** Must have:
- Valid manifest
- Service worker
- HTTPS (or localhost)
- At least 192x192 and 512x512 icons

---

## 📱 Test on Real Devices

### Android + Chrome:
1. Open mixtape on phone
2. Menu → "Add to Home screen"
3. Open installed app
4. Test offline by enabling airplane mode

### iOS + Safari:
1. Open mixtape on iPhone
2. Share button → "Add to Home Screen"
3. Open app from home screen
4. Test offline by enabling airplane mode

---

## 🎉 Success Criteria

After implementation, you should have:

✅ **Service worker registered and active**
✅ **Manifest.json accessible at /manifest.json**
✅ **PWA icons in multiple sizes**
✅ **Offline indicator shows when offline**
✅ **Mixtape pages load offline**
✅ **Download button works**
✅ **Lighthouse PWA score > 90**
✅ **Installable on mobile devices**

---

## 📞 Need Help?

### Debug Commands:
```javascript
// Check service worker status
navigator.serviceWorker.ready.then(reg => console.log('SW Ready:', reg));

// Check caches
caches.keys().then(keys => console.log('Cache keys:', keys));

// Get cache size estimate
navigator.storage.estimate().then(est => 
    console.log('Storage:', (est.usage/1024/1024).toFixed(2), 'MB used')
);
```

### Common Issues:

**Issue:** Service worker not updating
**Solution:** 
- Unregister: `navigator.serviceWorker.getRegistration().then(reg => reg.unregister())`
- Hard refresh (Ctrl+Shift+R)
- Clear cache in DevTools

**Issue:** Install prompt not showing
**Solution:**
- Check all PWA criteria are met
- Try in Chrome Incognito
- Check browser console for errors

**Issue:** Audio not playing offline
**Solution:**
- Verify tracks were downloaded (check Cache Storage)
- Check cache key format matches in service worker
- Try clearing and re-downloading

---

## 🚀 You're Ready!

Follow this checklist step-by-step, and you'll have a fully functional PWA in about 30 minutes!

**Pro tip:** Do Phase 1-3 first, test basic functionality, then add icons and advanced features later.

Good luck! 🎵
