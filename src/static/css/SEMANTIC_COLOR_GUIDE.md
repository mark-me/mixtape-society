# Semantic Color System Guide

## Overview
This guide explains how to use the centralized semantic color system for artist/album/track information in your Mixtape Society application.

## Quick Reference

| Context | Bootstrap Class | Semantic Class | Current Color |
|---------|----------------|----------------|---------------|
| Artist  | `.text-warning` | `.text-artist` | Warning (Yellow) |
| Album   | `.text-success` | `.text-album` | Success (Green) |
| Track   | `.text-primary` | `.text-track` | Primary (Blue) |

## Why Use This System?

### Benefits
1. **Single source of truth** - Change colors in one place (`:root` in `base.css`)
2. **Semantic clarity** - Code reads like "artist color" instead of "warning color"
3. **Easy refactoring** - Replace Bootstrap classes with semantic classes
4. **Theme consistency** - Automatically adapts to light/dark themes
5. **Future flexibility** - Can change color schemes without touching HTML

## How to Use

### 1. Changing Color Assignments

To swap which Bootstrap color represents what, simply edit the CSS variables in `base.css`:

```css
:root {
    /* Current mapping: Artist = Warning (Yellow) */
    --color-artist: var(--bs-warning);
    
    /* Want Artist = Primary instead? Change to: */
    --color-artist: var(--bs-primary);
    --color-artist-rgb: var(--bs-primary-rgb);
    --color-artist-text: var(--bs-primary-text-emphasis);
    /* ... etc */
}
```

### 2. Available Utility Classes

#### Text Colors
```html
<span class="text-artist">Artist name</span>
<span class="text-album">Album name</span>
<span class="text-track">Track name</span>
```

#### Background Colors
```html
<div class="bg-artist p-3">Artist info</div>
<div class="bg-album p-3">Album info</div>
<div class="bg-track p-3">Track info</div>
```

#### Border Colors
```html
<div class="border border-artist">Artist card</div>
<div class="border border-album">Album card</div>
<div class="border border-track">Track card</div>
```

#### Buttons
```html
<!-- Solid buttons -->
<button class="btn btn-artist">Artist Action</button>
<button class="btn btn-album">Album Action</button>
<button class="btn btn-track">Track Action</button>

<!-- Outline buttons -->
<button class="btn btn-outline-artist">Artist Action</button>
<button class="btn btn-outline-album">Album Action</button>
<button class="btn btn-outline-track">Track Action</button>
```

#### Badges
```html
<span class="badge badge-artist">Artist</span>
<span class="badge badge-album">Album</span>
<span class="badge badge-track">Track</span>
```

#### Alerts
```html
<div class="alert alert-artist">Artist information</div>
<div class="alert alert-album">Album information</div>
<div class="alert alert-track">Track information</div>
```

### 3. Migration Strategy

#### Option A: Gradual Migration (Recommended)
Replace classes as you work on each component:

```html
<!-- Before -->
<span class="text-warning">John Doe</span>
<span class="text-success">Best Hits</span>
<span class="text-primary">Song Title</span>

<!-- After -->
<span class="text-artist">John Doe</span>
<span class="text-album">Best Hits</span>
<span class="text-track">Song Title</span>
```

#### Option B: Quick Search & Replace
1. Search for `.text-warning` → replace with `.text-artist`
2. Search for `.text-success` → replace with `.text-album`
3. Search for `.text-primary` → replace with `.text-track`
4. Repeat for `.bg-*`, `.btn-*`, `.badge-*`, etc.

**⚠️ Warning:** Only replace instances that truly represent artist/album/track semantic meaning. Some uses of these colors may be decorative and should stay as Bootstrap classes.

### 4. Using CSS Variables Directly

For custom styling beyond the utility classes:

```css
.custom-artist-card {
    background-color: var(--color-artist-bg);
    border: 2px solid var(--color-artist);
    color: var(--color-artist-text);
}

.custom-track-button {
    background: linear-gradient(135deg, var(--color-track), var(--color-track-rgb));
    box-shadow: 0 4px 8px rgba(var(--color-track-rgb), 0.3);
}
```

## Example Color Scheme Changes

### Example 1: Swap Artist and Track Colors
```css
:root {
    /* Artist now uses Primary (Blue) */
    --color-artist: var(--bs-primary);
    --color-artist-rgb: var(--bs-primary-rgb);
    --color-artist-text: var(--bs-primary-text-emphasis);
    --color-artist-bg: var(--bs-primary-bg-subtle);
    --color-artist-border: var(--bs-primary-border-subtle);
    
    /* Album stays Success (Green) */
    --color-album: var(--bs-success);
    /* ... */
    
    /* Track now uses Warning (Yellow) */
    --color-track: var(--bs-warning);
    --color-track-rgb: var(--bs-warning-rgb);
    --color-track-text: var(--bs-warning-text-emphasis);
    --color-track-bg: var(--bs-warning-bg-subtle);
    --color-track-border: var(--bs-warning-border-subtle);
}
```

### Example 2: Use Custom Colors
```css
:root {
    /* Define custom colors */
    --custom-artist-color: #e74c3c;  /* Red */
    --custom-album-color: #3498db;   /* Blue */
    --custom-track-color: #2ecc71;   /* Green */
    
    /* Use them */
    --color-artist: var(--custom-artist-color);
    /* Note: You'll need to define -rgb, -text, -bg, -border variants too */
}
```

## Best Practices

### ✅ DO
- Use semantic classes (`.text-artist`) for artist/album/track information
- Change color assignments in `base.css` only
- Keep the semantic meaning consistent across the app
- Document why you chose specific color assignments

### ❌ DON'T
- Don't use Bootstrap color classes (`.text-warning`) for semantic content
- Don't hardcode color values in component CSS files
- Don't mix semantic and Bootstrap color classes for the same purpose
- Don't change semantic class names (`.text-artist`) in multiple places

## Troubleshooting

### Colors Not Updating
1. Clear browser cache
2. Check that `base.css` is loaded before component CSS
3. Verify CSS variable syntax (dashes, not underscores)

### Conflicts with Bootstrap
If semantic classes conflict with Bootstrap:
1. Use `!important` sparingly in semantic classes
2. Ensure `base.css` loads after Bootstrap
3. Check CSS specificity

### Dark Mode Issues
Bootstrap's color variables automatically adapt to light/dark themes. Your semantic tokens will inherit this behavior as long as you use `var(--bs-*)` values.

## Future Enhancements

Consider adding:
- Hover state variants (e.g., `--color-artist-hover`)
- Opacity variants (e.g., `--color-artist-50`, `--color-artist-75`)
- Gradient variants for fancy effects
- Animation-ready CSS custom properties

## Questions?

If you need help implementing this system, check:
1. Bootstrap 5.3 color documentation
2. CSS custom properties (CSS variables) documentation
3. Your `base.css` file comments
