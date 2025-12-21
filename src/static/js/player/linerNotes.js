
export function initLinerNotes() {
    // -----------------------------------------------------------------
    // Helper: replace #4 and #3-7 style references with track data
    // -----------------------------------------------------------------
    function renderTrackReferences(text, tracks) {
        if (!tracks || tracks.length === 0) return text;

        // Range: #3-7
        text = text.replace(/#(\d+)-(\d+)/g, (match, start, end) => {
            start = Number(start);
            end = Number(end);
            if (start > end || start < 1 || end > tracks.length) return match;

            const parts = [];
            for (let i = start; i <= end; i++) {
                const t = tracks[i - 1];
                parts.push(`${i}. ${t.title} – ${t.artist}`);
            }
            return parts.join(' → ');
        });

        // Single: #4
        text = text.replace(/#(\d+)/g, (match, num) => {
            const i = Number(num);
            if (i < 1 || i > tracks.length) return match;
            const t = tracks[i - 1];
            return `**${i}. ${t.title} – ${t.artist}**`;
        });

        return text;
    }

    // -----------------------------------------------------------------
    // Main rendering routine (called on page load and when the collapse opens)
    // -----------------------------------------------------------------
    const linerNotesEl = document.getElementById('rendered-liner-notes');
    if (!linerNotesEl) return;   // no liner notes on this mixtape

    // These variables are injected by Jinja as JSON strings
    const rawMarkdown = window.__mixtapeData?.rawMarkdown ?? '';
    const tracks = window.__mixtapeData?.tracks ?? [];

    function render() {
        const processed = renderTrackReferences(rawMarkdown, tracks);
        // `marked` and `DOMPurify` are loaded from CDNs (see template)
        const html = marked.parse(processed);
        linerNotesEl.innerHTML = DOMPurify.sanitize(html);
    }

    // Initial render
    render();

    // Re‑render whenever the collapse is shown (covers the unlikely case that tracks change)
    const collapseEl = document.getElementById('linerNotesCollapse');
    collapseEl?.addEventListener('shown.bs.collapse', render);

    // Rotate chevron arrow when the header is clicked
    const headerBtn = document.querySelector('[data-bs-target="#linerNotesCollapse"]');
    headerBtn?.addEventListener('click', function () {
        const icon = this.querySelector('.transition-chevron');
        if (icon) {
            icon.classList.toggle('rotated', this.getAttribute('aria-expanded') === 'true');
        }
    });
}