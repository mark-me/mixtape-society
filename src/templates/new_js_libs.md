https://marked.js.org/

[EasyMDE - Markdown Editor](https://github.com/Ionaru/easy-markdown-editor)
[DOMPurify - HTML Sanitizer](https://github.com/cure53/DOMPurify)


Here’s a clean and user-friendly **track reference syntax** upgrade for your Liner Notes editor.

### Goal
Allow users to easily reference tracks in their liner notes like:

- `#1` → automatically becomes **"1. Song Title – Artist"** in the preview (and later in the public view)
- `#3` → "3. Another Track – Artist"
- `#1-5` → "1. First – Artist → 5. Fifth Song – Artist" (nice for ranges)

This works **only in the preview** (and later public page) — users still type simple `#1` in the editor.

### Implementation (no backend changes needed)

Add this JavaScript **after** the EasyMDE initialization script (still in `{% block extra_js %}`):

```html
<script>
// Custom Markdown renderer to handle track references like #1, #2, #1-3
function renderTrackReferences(markdownText, tracks) {
    if (!tracks || tracks.length === 0) return markdownText;

    // Sort tracks by index (just in case)
    const sortedTracks = tracks.slice();

    // Replace #1-5 ranges
    markdownText = markdownText.replace(/#(\d+)-(\d+)/g, (match, start, end) => {
        start = parseInt(start);
        end = parseInt(end);
        if (start > end || start < 1 || end > sortedTracks.length) return match;

        const refs = [];
        for (let i = start; i <= end; i++) {
            const track = sortedTracks[i - 1];
            refs.push(`${i}. ${track.title} – ${track.artist}`);
        }
        return refs.join(" → ");
    });

    // Replace single #1, #12, etc.
    markdownText = markdownText.replace(/#(\d+)/g, (match, num) => {
        const index = parseInt(num);
        if (index < 1 || index > sortedTracks.length) return match;
        const track = sortedTracks[index - 1];
        return `**${index}. ${track.title} – ${track.artist}**`;
    });

    return markdownText;
}

// Override EasyMDE's preview renderer to include track references
if (typeof easyMDE !== 'undefined') {
    const originalPreviewRender = easyMDE.options.previewRender;

    easyMDE.options.previewRender = function(plainText, previewElement) {
        // Get current track list (from global playlist array)
        const currentTracks = window.playlist || [];

        // First apply track reference magic
        let processedText = renderTrackReferences(plainText, currentTracks);

        // Then render as HTML with marked
        let html = marked.parse(processedText);

        // Sanitize
        html = DOMPurify.sanitize(html);

        return html;
    };

    // Also update the custom Preview tab when needed
    const previewPane = document.getElementById('markdown-preview');
    const previewTab = document.getElementById('preview-tab');

    if (previewTab) {
        previewTab.addEventListener('shown.bs.tab', () => {
            const currentTracks = window.playlist || [];
            let text = easyMDE.value();
            text = renderTrackReferences(text, currentTracks);
            const html = marked.parse(text);
            previewPane.innerHTML = DOMPurify.sanitize(html);
        });
    }

    // Update preview when playlist changes (add/remove/reorder)
    const originalRenderPlaylist = window.renderPlaylist;
    window.renderPlaylist = function() {
        originalRenderPlaylist.apply(this, arguments);

        // If user is currently viewing the preview tab, refresh it
        if (document.querySelector('#preview-tab.active')) {
            const currentTracks = window.playlist || [];
            let text = easyMDE ? easyMDE.value() : "";
            text = renderTrackReferences(text, currentTracks);
            const html = marked.parse(text);
            document.getElementById('markdown-preview').innerHTML = DOMPurify.sanitize(html);
        }
    };
}
</script>
```

### Make the global `playlist` array accessible

In your existing code, you already have a global `let playlist = [];` — that's perfect! This script uses `window.playlist` to access it.

If you ever rename it, just make sure it's globally accessible or replace `window.playlist` with your variable name.

### Example usage for the user

Now users can write in the editor:

```markdown
This mixtape starts strong with #1, then gets dreamy around #4-6.

My personal favorite is #8 – that bassline!

Check out the transition between #12 and #13.
```

And in **preview**, it will show as:

**This mixtape starts strong with 1. Opening Track – Artist, then gets dreamy around 4. Dreamy Song – Artist → 6. Final Dream – Artist.**

**My personal favorite is 8. Favorite Track – Artist – that bassline!**

**Check out the transition between 12. Track Twelve – Artist and 13. Track Thirteen – Artist.**

Beautiful, automatic, and super intuitive!

### Bonus: Tooltip hint

Add this small hint below the editor (inside the `#notes-pane` div, before the sub-tabs):

```html
<small class="text-muted d-block mb-2">
    Tip: Use <code>#1</code>, <code>#5</code>, or <code>#2-4</code> to auto-link to tracks!
</small>
```

Let me know if you want:
- Clickable links that jump to the track in the list
- Auto-complete dropdown when typing `#`
- Or rendering the same way on the public mixtape page

This is already a huge usability win!