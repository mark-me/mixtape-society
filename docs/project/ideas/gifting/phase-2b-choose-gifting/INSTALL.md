# 🚀 Quick Installation Guide - Phase 2

## All Files Ready!

You now have **ALL** Phase 2 files in `/mnt/user-data/outputs/`

---

## 📦 Installation Steps

### Step 1: Copy New Files (3 files)

```bash
# 1. New JavaScript module
cp giftSettings.js → YOUR_PROJECT/static/js/editor/giftSettings.js

# 2. Updated backend preferences
cp preferences.py → YOUR_PROJECT/src/preferences.py

# 3. Create mockups directory and copy mockups
mkdir -p YOUR_PROJECT/static/mockups
cp mockup-playful.html → YOUR_PROJECT/static/mockups/
cp mockup-elegant.html → YOUR_PROJECT/static/mockups/
```

---

### Step 2: Replace Modified Files (3 files)

```bash
# These files have been updated with new code

cp editor.html → YOUR_PROJECT/templates/editor.html
cp ui.js → YOUR_PROJECT/static/js/editor/ui.js
cp index.js → YOUR_PROJECT/static/js/editor/index.js
```

---

### Step 3: Update Backend Files (2 files - manual edits)

#### A. Update `mixtape_manager.py`

Find the `_verify_mixtape_metadata()` method and add:

```python
# Add this with other field normalizations (around line 320)
if "unwrap_style" not in data:
    data["unwrap_style"] = "playful"
```

Find the `save()` method and add:

```python
# Add this with other setdefault calls (around line 85)
mixtape_data.setdefault("unwrap_style", "playful")
```

#### B. Update `editor.py`

Find the `new_mixtape()` route and update empty_mixtape:

```python
empty_mixtape = {
    "title": "",
    "cover": None,
    "liner_notes": "",
    "tracks": [],
    "slug": None,
    "created_at": None,
    "updated_at": None,
    "creator_name": prefs.get("creator_name", ""),
    "gift_flow_enabled": prefs.get("default_gift_flow_enabled", False),
    "unwrap_style": prefs.get("default_unwrap_style", "playful"),  # ← ADD THIS LINE
    "show_tracklist_after_completion": prefs.get("default_show_tracklist", True),
}
```

*Note: Reference versions of these files are included in outputs for comparison.*

---

### Step 4: Restart Application

```bash
# Restart your Flask server
# For example:
./restart.sh
# or
systemctl restart your-app
```

---

## ✅ Verification

After installation, test:

1. **Visit `/editor/`**
   - Gift settings modal should auto-show
   - Enable gift flow
   - Style selector appears with Playful/Elegant options
   - Click Preview → Opens mockup in popup

2. **Create and Save**
   - Select a style
   - Save mixtape
   - Check the saved JSON file has `unwrap_style` field

3. **Edit Existing**
   - Edit the mixtape
   - Modal should show the saved style selected

---

## 📂 File Summary

**Ready to Copy (8 files):**
1. ✅ giftSettings.js
2. ✅ preferences.py
3. ✅ mockup-playful.html
4. ✅ mockup-elegant.html
5. ✅ editor.html
6. ✅ ui.js
7. ✅ index.js
8. ✅ FILE_MANIFEST.md (this guide)

**Reference Files (2 files):**
9. 📖 mixtape_manager.py (shows needed changes)
10. 📖 editor.py (shows needed changes)

**Documentation (4 files):**
11. 📚 README.md
12. 📚 PHASE_2_UPDATE.md
13. 📚 UI_VISUAL_GUIDE.md
14. 📚 MOCKUP_COMPARISON.md

---

## 🎯 That's It!

All files are in `/mnt/user-data/outputs/` and ready to copy to your project.

See **FILE_MANIFEST.md** for detailed information about each file and what changed.
