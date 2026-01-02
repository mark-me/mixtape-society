# Classic Vinyl Color System - Quick Reference

## Color Preview

```
🎸 ARTIST:  #ff6b35  (Warm Amber - like vinyl glow)
████████████████

💿 ALBUM:   #6c5ce7  (Deep Purple - like vinyl records)
████████████████

🎵 TRACK:   #00cec9  (Electric Cyan - like cassette windows)
████████████████
```

## Most Common Usage

### In HTML Templates

```html
<!-- Artist accordion button -->
<button class="accordion-button bg-artist">Artist Name</button>

<!-- Album accordion button -->
<button class="accordion-button bg-album">Album Title</button>

<!-- Track highlight -->
<div class="list-group-item bg-track-subtle">Track info</div>

<!-- Buttons -->
<button class="btn btn-artist">Artist Action</button>
<button class="btn btn-album">Album Action</button>
<button class="btn btn-track">Track Action</button>

<!-- Badges -->
<span class="badge badge-artist">12 tracks</span>
<span class="badge badge-album">3 albums</span>

<!-- Text colors -->
<span class="text-artist">Artist name</span>
<span class="text-album">Album title</span>
<span class="text-track">Track title</span>
```

### In CSS

```css
/* Using the variables directly */
.custom-artist-card {
    background-color: var(--color-artist);
    border: 2px solid var(--color-artist);
    color: white;
}

.custom-artist-card:hover {
    background-color: var(--color-artist-hover);
}

/* For subtle backgrounds */
.highlight-album {
    background-color: var(--color-album-bg-subtle);
    color: var(--color-album-text-emphasis);
}
```

### In JavaScript

```javascript
// Adding classes
element.classList.add('bg-artist');
element.classList.add('text-album');
element.classList.add('btn-track');

// Checking classes
const isArtist = element.classList.contains('bg-artist');
const isAlbum = element.classList.contains('bg-album');
```

## All Available Classes

### Background Colors
- `.bg-artist` - Solid amber background, white text
- `.bg-album` - Solid purple background, white text
- `.bg-track` - Solid cyan background, white text
- `.bg-artist-subtle` - Light amber background, dark text
- `.bg-album-subtle` - Light purple background, dark text
- `.bg-track-subtle` - Light cyan background, dark text

### Text Colors
- `.text-artist` - Amber text
- `.text-album` - Purple text
- `.text-track` - Cyan text
- `.text-artist-emphasis` - Darker/lighter amber (theme-aware)
- `.text-album-emphasis` - Darker/lighter purple (theme-aware)
- `.text-track-emphasis` - Darker/lighter cyan (theme-aware)

### Border Colors
- `.border-artist` - Amber border
- `.border-album` - Purple border
- `.border-track` - Cyan border

### Buttons
- `.btn-artist` - Solid amber button
- `.btn-album` - Solid purple button
- `.btn-track` - Solid cyan button
- `.btn-outline-artist` - Outlined amber button
- `.btn-outline-album` - Outlined purple button
- `.btn-outline-track` - Outlined cyan button

### Badges
- `.badge-artist` - Solid amber badge
- `.badge-album` - Solid purple badge
- `.badge-track` - Solid cyan badge
- `.badge-artist-subtle` - Light amber badge
- `.badge-album-subtle` - Light purple badge
- `.badge-track-subtle` - Light cyan badge

### Alerts
- `.alert-artist` - Artist-themed alert box
- `.alert-album` - Album-themed alert box
- `.alert-track` - Track-themed alert box

### Toasts
- `.text-bg-artist` - Artist-colored toast
- `.text-bg-album` - Album-colored toast
- `.text-bg-track` - Track-colored toast

### List Items
- `.list-group-item-artist` - Artist-colored list item
- `.list-group-item-album` - Album-colored list item
- `.list-group-item-track` - Track-colored list item

### Progress Bars
- `.progress-bar-artist` - Amber progress bar
- `.progress-bar-album` - Purple progress bar
- `.progress-bar-track` - Cyan progress bar

### Links
- `.link-artist` - Artist-colored link
- `.link-album` - Album-colored link
- `.link-track` - Track-colored link

### Special Effects
- `.bg-gradient-artist` - Gradient amber background
- `.bg-gradient-album` - Gradient purple background
- `.bg-gradient-track` - Gradient cyan background

## CSS Variables Reference

```css
/* Artist */
--color-artist: #ff6b35
--color-artist-rgb: 255, 107, 53
--color-artist-hover: #ff8555
--color-artist-active: #e55a25
--color-artist-text-emphasis: #d44a1a (light) / #ff9b7a (dark)
--color-artist-bg-subtle: rgba(255, 107, 53, 0.1) (light) / 0.15 (dark)
--color-artist-border-subtle: rgba(255, 107, 53, 0.3) (light) / 0.4 (dark)

/* Album */
--color-album: #6c5ce7
--color-album-rgb: 108, 92, 231
--color-album-hover: #7c6ef0
--color-album-active: #5c4cd7
--color-album-text-emphasis: #4a3db8 (light) / #9d8ff5 (dark)
--color-album-bg-subtle: rgba(108, 92, 231, 0.1) (light) / 0.15 (dark)
--color-album-border-subtle: rgba(108, 92, 231, 0.3) (light) / 0.4 (dark)

/* Track */
--color-track: #00cec9
--color-track-rgb: 0, 206, 201
--color-track-hover: #20ded9
--color-track-active: #00aea9
--color-track-text-emphasis: #00968f (light) / #5ffbf1 (dark)
--color-track-bg-subtle: rgba(0, 206, 201, 0.1) (light) / 0.15 (dark)
--color-track-border-subtle: rgba(0, 206, 201, 0.3) (light) / 0.4 (dark)
```

## Migration Examples

### Before (Bootstrap colors)
```html
<button class="accordion-button bg-success">The Beatles</button>
<button class="accordion-button bg-warning">Abbey Road</button>
<div class="list-group-item bg-primary-subtle">Come Together</div>
```

### After (Semantic colors)
```html
<button class="accordion-button bg-artist">The Beatles</button>
<button class="accordion-button bg-album">Abbey Road</button>
<div class="list-group-item bg-track-subtle">Come Together</div>
```

### Before (CSS)
```css
.accordion-button.bg-success {
    background-color: #198754 !important;
}
.accordion-button.bg-warning {
    background-color: #ffc107 !important;
}
```

### After (CSS)
```css
.accordion-button.bg-artist {
    background-color: var(--color-artist) !important;
}
.accordion-button.bg-album {
    background-color: var(--color-album) !important;
}
```

### Before (JavaScript)
```javascript
const isArtist = this.classList.contains("bg-success");
const isAlbum = this.classList.contains("bg-warning");
this.classList.add('btn-primary');
```

### After (JavaScript)
```javascript
const isArtist = this.classList.contains("bg-artist");
const isAlbum = this.classList.contains("bg-album");
this.classList.add('btn-track');
```

## Testing in Browser

Open your browser console and test the colors:

```javascript
// Test artist color
document.body.style.backgroundColor = 'var(--color-artist)';

// Test album color  
document.body.style.backgroundColor = 'var(--color-album)';

// Test track color
document.body.style.backgroundColor = 'var(--color-track)';

// Reset
document.body.style.backgroundColor = '';
```

## Tips

1. **Always use semantic classes** for artist/album/track contexts
2. **Keep Bootstrap classes** for status/actions (success, danger, warning)
3. **Use `-subtle` variants** for backgrounds with text
4. **Use solid colors** for buttons and badges
5. **Test in both light and dark modes**
6. **Use the hover/active variants** for interactive elements

## When NOT to Use Semantic Colors

Keep Bootstrap colors for:
- ✅ Success messages (green)
- ✅ Error messages (red/danger)
- ✅ Warning alerts (yellow)
- ✅ Delete buttons (danger)
- ✅ Save buttons (can be success or primary)
- ✅ Cancel buttons (secondary)

These are STATUS/ACTION colors, not SEMANTIC CONTENT colors.
