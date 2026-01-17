# Phase 2 Update: Unwrap Style Selection & Preview

## Overview
Extended Phase 2 to allow creators to choose between two unwrap styles (Playful and Elegant) and preview them before saving.

---

## Changes Made

### 1. Frontend (Editor UI)

#### `editor.html`
**Added:**
- Unwrap style selector (radio buttons) in Gift Settings Modal
- Preview button to view selected style
- Updated `PRELOADED_MIXTAPE` to include `unwrap_style`

```html
<!-- Unwrap Style Selection (visible when gift flow enabled) -->
<div id="gift-style-container">
  <input type="radio" name="gift-style" id="style-playful" value="playful" checked>
  <input type="radio" name="gift-style" id="style-elegant" value="elegant">
  <button id="preview-gift-flow">Preview Unwrapping Experience</button>
</div>
```

#### `static/js/editor/giftSettings.js` (NEW FILE)
**Features:**
- `unwrap_style` field added to `currentGiftSettings` (default: 'playful')
- Event listeners for style radio button changes
- `openPreview()` function - opens mockup in new window
- Saves `default_unwrap_style` to preferences when "Save as default" is checked
- Loads initial style from preloaded mixtape or preferences

**Preview Function:**
```javascript
function openPreview() {
    const style = currentGiftSettings.unwrap_style; // 'playful' or 'elegant'
    const previewUrl = `/static/mockups/mockup-${style}.html`;
    window.open(previewUrl, 'GiftFlowPreview', '...');
}
```

#### `static/js/editor/ui.js`
**Updated:**
- Save payload now includes `unwrap_style` field:
```javascript
const playlistData = {
    // ... other fields
    unwrap_style: giftSettings.unwrap_style,  // NEW
    // ...
};
```

---

### 2. Backend (Data Model)

#### `src/preferences.py`
**Added:**
- `default_unwrap_style` to `DEFAULT_PREFERENCES` (default: 'playful')
- Automatically merged with existing preferences on load

```python
DEFAULT_PREFERENCES = {
    "creator_name": "",
    "default_gift_flow_enabled": False,
    "default_unwrap_style": "playful",  # NEW
    "default_show_tracklist": True,
}
```

#### `mixtape_manager.py` (needs update)
**Required changes:**
```python
# In _verify_mixtape_metadata():
if "unwrap_style" not in data:
    data["unwrap_style"] = "playful"

# In save():
mixtape_data.setdefault("unwrap_style", "playful")
```

#### `editor.py` (needs update)
**Required changes:**
```python
# In new_mixtape():
empty_mixtape["unwrap_style"] = prefs.get("default_unwrap_style", "playful")

# In save_mixtape():
# Accept unwrap_style from request and save it
```

---

### 3. Static Assets

#### `/static/mockups/` (NEW DIRECTORY)
**Files to add:**
- `mockup-playful.html` - Interactive playful unwrap mockup
- `mockup-elegant.html` - Interactive elegant unwrap mockup

These are self-contained HTML files that demonstrate each unwrap style.

---

## Updated Mixtape JSON Schema

```json
{
  "title": "Summer Vibes '24",
  "tracks": [...],
  "liner_notes": "...",
  "creator_name": "DJ Claude",
  "gift_flow_enabled": true,
  "unwrap_style": "playful",  // NEW: 'playful' or 'elegant'
  "show_tracklist_after_completion": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T15:45:00"
}
```

---

## User Experience Flow

### Creating a New Mixtape:
1. Visit `/editor/`
2. Gift settings modal auto-shows
3. Enable gift flow → Style selector appears
4. Choose between Playful or Elegant
5. Click "Preview" to see selected style in action
6. Optionally check "Save as default" to remember preference
7. Save mixtape → `unwrap_style` included in payload

### Editing Existing Mixtape:
1. Visit `/editor/<slug>`
2. Settings load silently (including saved `unwrap_style`)
3. Click "Gift" button to modify
4. Change style and preview as needed
5. Save → Changes persist

---

## Preview Window

When creator clicks "Preview Unwrapping Experience":

```javascript
// Opens in centered popup window (600x700)
window.open('/static/mockups/mockup-playful.html', ...)
// or
window.open('/static/mockups/mockup-elegant.html', ...)
```

**Window features:**
- Centered on screen
- Resizable & scrollable
- Can be closed independently
- Shows interactive demo with controls

---

## Files Modified

### Frontend:
- ✅ `templates/editor.html` - Added style selector & preview button
- ✅ `static/js/editor/ui.js` - Added unwrap_style to save payload
- ✅ `static/js/editor/giftSettings.js` (NEW) - Full implementation

### Backend:
- ✅ `src/preferences.py` - Added default_unwrap_style field
- ⏳ `src/mixtape_manager.py` - Need to add unwrap_style normalization
- ⏳ `src/editor.py` - Need to handle unwrap_style in save/load

### Static Assets:
- ⏳ Create `/static/mockups/` directory
- ⏳ Copy `mockup-playful.html` to `/static/mockups/`
- ⏳ Copy `mockup-elegant.html` to `/static/mockups/`

---

## Next Steps

### To Complete Phase 2:
1. ✅ Update `mixtape_manager.py` to normalize `unwrap_style`
2. ✅ Update `editor.py` to handle `unwrap_style` in new_mixtape() and save_mixtape()
3. ✅ Create `/static/mockups/` directory in project
4. ✅ Copy mockup HTML files to static folder
5. ✅ Test full flow: create → select style → preview → save → edit → change style

### For Phase 3 (Receiver Experience):
Once Phase 2 is complete, implement the actual unwrapping flow:
1. Detect `gift_flow_enabled` flag on `/play/share/<slug>`
2. Check `unwrap_style` value
3. Load appropriate flow (playful or elegant)
4. Implement hash-based states: #unwrap → #reveal → #listen
5. Hide tracklist until completion (if enabled)

---

## Testing Checklist

- [ ] Gift settings modal shows style selector when gift flow enabled
- [ ] Style selector hides when gift flow disabled
- [ ] Preview button opens correct mockup based on selection
- [ ] Default style preference saves and persists
- [ ] New mixtapes load default style from preferences
- [ ] Existing mixtapes load saved style correctly
- [ ] Save payload includes unwrap_style field
- [ ] Backend accepts and saves unwrap_style
- [ ] Switching styles works without save/reload

---

## File Deliverables

All updated files are in `/mnt/user-data/outputs/`:
1. `giftSettings.js` - Complete implementation
2. `preferences.py` - Updated with unwrap_style
3. `static-mockups/` - Contains mockup HTML files
4. This implementation guide

Copy these to your project and apply the backend changes noted above.
