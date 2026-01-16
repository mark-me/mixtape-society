// static/js/player/linerNotes.js

/**
 * Replaces track reference shorthand (#1, #2-4) with formatted track information
 */
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
            parts.push(`${i}. ${t.title} — ${t.artist}`);
        }
        return parts.join(' → ');
    });

    // Single: #4
    text = text.replace(/#(\d+)/g, (match, num) => {
        const i = Number(num);
        if (i < 1 || i > tracks.length) return match;
        const t = tracks[i - 1];
        return `**${i}. ${t.title} — ${t.artist}**`;
    });

    return text;
}

/**
 * Renders markdown with track references and sanitizes output
 */
function renderMarkdown(rawMarkdown, tracks) {
    const processed = renderTrackReferences(rawMarkdown, tracks);
    const html = marked.parse(processed);
    return DOMPurify.sanitize(html);
}

/**
 * Toggles chevron icon rotation based on collapse state
 */
function setupChevronToggle(headerBtn) {
    if (!headerBtn) return;

    headerBtn.addEventListener('click', function () {
        const icon = this.querySelector('.transition-chevron');
        if (!icon) return;

        const isExpanded = this.getAttribute('aria-expanded') === 'true';
        icon.classList.toggle('rotated', isExpanded);
    });
}

/**
 * Initializes liner notes rendering and collapse functionality
 */
export function initLinerNotes() {
    const linerNotesEl = document.getElementById('rendered-liner-notes');
    if (!linerNotesEl) return;

    // Get data from global variables (injected by Jinja)
    const rawMarkdown = window.__mixtapeData?.rawMarkdown ?? '';
    const tracks = window.__mixtapeData?.tracks ?? [];

    // Render function
    const render = () => {
        linerNotesEl.innerHTML = renderMarkdown(rawMarkdown, tracks);
    }

    // Initial render
    render();

    // Re-render whenever the collapse is shown
    const collapseEl = document.getElementById('linerNotesCollapse');
    collapseEl?.addEventListener('shown.bs.collapse', render);

    // Setup chevron rotation
    const headerBtn = document.querySelector('[data-bs-target="#linerNotesCollapse"]');
    setupChevronToggle(headerBtn);
}
