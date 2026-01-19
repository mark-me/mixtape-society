// static/js/player/onboarding.js
export function initOnboarding() {
    // Check if it is first load
    if (localStorage.getItem('mixtapeOnboarded') === 'true') {
        console.log('Onboarding skipped: already completed');
        initHoverTooltips(); // Altijd hover-tooltips activeren (optie 3)
        return;
    }

    // First-load: Activate beacons + tooltips
    initBeaconsAndTooltips();

    // Markeer als onboarded na eerste interactie of timeout (bijv. 10s)
    setTimeout(() => markAsOnboarded(), 10000); // Auto na 10s

    // Listen to first click (click anywhere)
    document.addEventListener('click', () => markAsOnboarded(), { once: true });

    // Activate always hover tooltips
    initHoverTooltips();
}

function initBeaconsAndTooltips() {
    const elements = [
        { selector: '#big-play-btn', tooltip: 'Start playing your mixtape!' },
        { selector: '#cast-button', tooltip: 'Cast to your TV or speaker (Chromecast)' },
        { selector: '#quality-btn-bottom', tooltip: 'Choose audio-quality (for improved streaming)' },
        { selector: '#panel-mode-toggle', tooltip: 'Switch to retro-cassette mode' }
    ];

    elements.forEach(({ selector, tooltip }) => {
        const el = document.querySelector(selector);
        if (!el) return;

        // Add beacon class
        el.classList.add('beacon');

        // Activate Bootstrap tooltip (with data-bs attributes)
        el.setAttribute('data-bs-toggle', 'tooltip');
        el.setAttribute('data-bs-placement', 'top'); // Or 'right'/'bottom' dependent on position
        el.setAttribute('data-bs-title', tooltip);
        el.setAttribute('data-bs-trigger', 'manual'); // Manual for first-load show

        // Initialise and show tooltip immediately
        const bsTooltip = new bootstrap.Tooltip(el);
        bsTooltip.show();

        // Hide tooltip after 5s or at hover/click
        setTimeout(() => bsTooltip.hide(), 5000);
        el.addEventListener('mouseenter', () => bsTooltip.hide(), { once: true });
        el.addEventListener('click', () => bsTooltip.hide(), { once: true });
    });
}

function initHoverTooltips() {
    // Activate all Bootstrap tooltips on the page
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(tooltipTriggerEl => {
        new bootstrap.Tooltip(tooltipTriggerEl, {
            trigger: 'hover focus', // Hover or focus (for mobile tap)
            delay: { show: 200, hide: 100 } // Subtle delay
        });
    });
}

function markAsOnboarded() {
    localStorage.setItem('mixtapeOnboarded', 'true');

    // Remove beacons with fade-out
    document.querySelectorAll('.beacon').forEach(el => {
        el.classList.add('fade-out');
        setTimeout(() => el.classList.remove('beacon', 'fade-out'), 500);
    });

    // Hide open tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        const bsTooltip = bootstrap.Tooltip.getInstance(el);
        if (bsTooltip) bsTooltip.hide();
    });

    console.log('Onboarding completed and marked in localStorage');
}