# Jazz Lounge Color System - Quick Reference

## Color Preview

```
🎺 ARTIST:  #d4a574  (Warm Gold - brass instruments)
████████████████

📀 ALBUM:   #8b5a3c  (Rich Brown - leather sleeves)
████████████████

🎷 TRACK:   #5b8a9d  (Smoky Blue - club atmosphere)
████████████████
```

## Color Philosophy

The Jazz Lounge scheme evokes:
- 🎺 **Warm brass instruments** catching stage lights
- 📀 **Vintage vinyl collections** in leather sleeves
- 🎷 **Sophisticated jazz clubs** with dim blue lighting
- 🥃 **Timeless elegance** and mature taste
- 🎹 **Acoustic warmth** and intimate settings

Perfect for audiophiles, mature music lovers, and those who appreciate a sophisticated, low-contrast aesthetic.

## Light Mode Colors

```
Artist:  #d4a574  ▓▓▓▓▓▓▓▓ Warm, inviting gold
Album:   #8b5a3c  ▓▓▓▓▓▓▓▓ Deep, rich brown
Track:   #5b8a9d  ▓▓▓▓▓▓▓▓ Cool, smoky blue
```

## Dark Mode Colors (Enhanced)

```
Artist:  #e0b686  ▓▓▓▓▓▓▓▓ Brighter gold glow
Album:   #9f6a4a  ▓▓▓▓▓▓▓▓ Warmer brown
Track:   #7ba6ba  ▓▓▓▓▓▓▓▓ Lighter smoky blue
```

**Note:** Jazz colors automatically get richer and more visible in dark mode for optimal readability.

## Usage Examples

### HTML Templates

```html
<!-- Artist accordion -->
<button class="accordion-button bg-artist">Miles Davis</button>

<!-- Album accordion -->
<button class="accordion-button bg-album">Kind of Blue</button>

<!-- Track highlight -->
<div class="list-group-item bg-track-subtle">So What</div>

<!-- Sophisticated buttons -->
<button class="btn btn-artist">Browse Artists</button>
<button class="btn-outline-album">Albums</button>

<!-- Elegant badges -->
<span class="badge badge-artist">Jazz</span>
<span class="badge-album-subtle">12 tracks</span>
```

### CSS Variables

```css
/* All available jazz variables */

/* Artist (Warm Gold) */
--color-artist: #d4a574           /* Light mode solid */
--color-artist: #e0b686           /* Dark mode solid */
--color-artist-hover: #e0b686     /* Hover state */
--color-artist-active: #c89462    /* Active/pressed */

/* Album (Rich Brown) */
--color-album: #8b5a3c            /* Light mode solid */
--color-album: #9f6a4a            /* Dark mode solid */
--color-album-hover: #9f6a4a      /* Hover state */
--color-album-active: #774a2e     /* Active/pressed */

/* Track (Smoky Blue) */
--color-track: #5b8a9d            /* Light mode solid */
--color-track: #7ba6ba            /* Dark mode solid */
--color-track-hover: #6b9aad      /* Hover state */
--color-track-active: #4b7a8d     /* Active/pressed */
```

## All Available Classes

Same as Classic Vinyl, but with jazz colors:

### Backgrounds
- `.bg-artist` - Warm gold background
- `.bg-album` - Rich brown background
- `.bg-track` - Smoky blue background
- `.bg-artist-subtle` - Light gold tint
- `.bg-album-subtle` - Light brown tint
- `.bg-track-subtle` - Light blue tint

### Text
- `.text-artist` - Gold text
- `.text-album` - Brown text
- `.text-track` - Blue text

### Buttons
- `.btn-artist` - Solid gold button
- `.btn-album` - Solid brown button
- `.btn-track` - Solid blue button
- `.btn-outline-artist` - Gold outline
- `.btn-outline-album` - Brown outline
- `.btn-outline-track` - Blue outline

### Badges
- `.badge-artist` - Gold badge
- `.badge-album` - Brown badge
- `.badge-track` - Blue badge

## Special Jazz Features

### Warm Glow Effect
All buttons have a subtle warm glow on hover:

```css
.btn-artist:hover {
    box-shadow: 0 4px 12px rgba(212, 165, 116, 0.3);
}
```

### Vintage Texture (Optional)
Add a subtle paper texture to elements:

```html
<div class="card jazz-texture">
    <!-- Content with vintage texture -->
</div>
```

### Softer Shadows in Dark Mode
Dark mode shadows are tinted with warm gold for a cozy feel.

## Best Practices for Jazz Theme

### Do's ✅
- Use generous whitespace for breathing room
- Combine with serif fonts for sophistication
- Use subtle animations and transitions
- Pair with dark backgrounds in dark mode
- Add texture overlays for vintage feel

### Don'ts ❌
- Avoid harsh bright colors
- Don't use pure white backgrounds
- Skip aggressive animations
- Avoid neon or electric accents
- Don't overcrowd the interface

## Accessibility Notes

**WCAG Compliance:**
- ⚠️ Light mode: Some combinations may need testing
- ✅ Dark mode: Excellent contrast across all colors
- ✅ Color blind safe: Distinct hues even with color blindness
- ✅ Focus states: Clear and visible

**Recommendations:**
1. Test in light mode with contrast checker
2. Consider using dark mode as default
3. Use text emphasis colors for better readability
4. Add visual separators for clarity

## Typography Pairing Suggestions

Jazz works beautifully with:
- **Serif fonts:** Georgia, Playfair Display, Lora
- **Script fonts:** Satisfy, Pacifico (for headings)
- **Monospace:** Courier New (for vintage tech feel)

```css
/* Example jazz typography */
.jazz-heading {
    font-family: 'Playfair Display', Georgia, serif;
    color: var(--color-artist);
    letter-spacing: 0.5px;
}

.jazz-body {
    font-family: Georgia, 'Times New Roman', serif;
    color: var(--color-album-text-emphasis);
    line-height: 1.7;
}
```

## Comparison with Classic Vinyl

| Aspect | Classic Vinyl | Jazz Lounge |
|--------|---------------|-------------|
| **Energy** | High, vibrant | Low, sophisticated |
| **Contrast** | High | Medium-Low |
| **Best for** | All ages | Audiophiles, 30+ |
| **Vibe** | Retro, fun | Elegant, timeless |
| **Reading** | Great | Better with dark mode |
| **Mood** | Energetic | Relaxed, intimate |

## When to Use Jazz Lounge

**Perfect for:**
- 🎷 Jazz, classical, or acoustic music collections
- 📚 Mature, sophisticated audiences
- 🌙 Dark mode primary users
- 🎨 Premium, high-end aesthetic
- 📖 Content-heavy reading experiences

**Not ideal for:**
- 🎮 Gaming or energetic content
- 👶 Younger audiences (too subtle)
- ☀️ High-contrast needs
- 🏃 Quick interactions (colors may blend)

## Testing Checklist

Before committing:
- [ ] Test all colors in light mode
- [ ] Test all colors in dark mode
- [ ] Check contrast ratios with tool
- [ ] View with color blindness simulator
- [ ] Get feedback from target audience
- [ ] Test on mobile devices
- [ ] Check with serif fonts enabled

## Quick Switch Between Schemes

Want to try both? Keep both CSS files and switch:

```html
<!-- Classic Vinyl -->
<link rel="stylesheet" href="css/base.css">

<!-- Jazz Lounge -->
<link rel="stylesheet" href="css/base-jazz.css">
```

Or add a theme switcher in your app settings!

## Pro Tips

1. **Use dark mode as default** with jazz colors
2. **Add subtle textures** to backgrounds
3. **Use generous spacing** between elements
4. **Combine with sepia filters** for vintage photos
5. **Add warm lighting effects** to interactive elements
6. **Use serif fonts** for headings
7. **Consider amber accent lighting** in dark mode

## Example Color Combinations

**For cards:**
```css
.jazz-card {
    background: var(--color-album);
    border: 2px solid var(--color-artist);
    color: white;
}
```

**For highlighted text:**
```css
.jazz-highlight {
    background: var(--color-artist-bg-subtle);
    color: var(--color-artist-text-emphasis);
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
```

**For navigation:**
```css
.nav-link {
    color: var(--color-track);
}
.nav-link:hover {
    color: var(--color-artist);
}
```

## Support

If jazz colors feel too muted in light mode:
1. Consider dark mode as primary
2. Increase opacity in subtle backgrounds
3. Use heavier font weights
4. Add subtle borders to elements
5. Or switch to Classic Vinyl for more punch!

---

**Remember:** Jazz Lounge is about sophistication and subtlety. It's meant to be easy on the eyes for long listening sessions, like sitting in a dim jazz club with a drink. If you want more energy and contrast, Classic Vinyl is your friend!
