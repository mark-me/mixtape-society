// static/js/player/onboarding.js
export function initOnboarding() {
    // Check if it is first load
    if (localStorage.getItem('mixtapeOnboarded') === 'true') {
        console.log('Onboarding skipped: already completed');
        initHoverTooltips(); // Always activate hover tooltips
        return;
    }

    // First-load: Activate beacons + tooltips
    initBeaconsAndTooltips();

    // Listen for cast button to become available
    document.addEventListener('cast:ready', () => {
        addCastButtonTooltip();
    });

    // Mark as onboarded after first interaction or timeout (e.g., 10s)
    setTimeout(() => markAsOnboarded(), 10000); // Auto after 10s

    // Listen to first click (click anywhere)
    document.addEventListener('click', () => markAsOnboarded(), { once: true });

    // Activate always hover tooltips
    initHoverTooltips();
}

function initBeaconsAndTooltips() {
    const elements = [
        { selector: '#big-play-btn', tooltip: 'Start playing your mixtape!', placement: 'top' },
        { selector: '.quality-selector', tooltip: 'Choose audio quality for improved streaming', placement: 'top' },
        { selector: '.side-panel-left', tooltip: 'Switch to retro cassette mode', placement: 'right' }
    ];

    elements.forEach(({ selector, tooltip, placement }) => {
        const el = document.querySelector(selector);
        if (!el) {
            console.log(`⚠️ Onboarding element not found: ${selector}`);
            return;
        }

        addTooltipToElement(el, tooltip, placement);
    });
}

function addCastButtonTooltip() {
    const el = document.querySelector('#cast-button');
    if (!el || el.hidden) {
        console.log('⚠️ Cast button not available for onboarding');
        return;
    }

    // Only add tooltip if onboarding hasn't been completed
    if (localStorage.getItem('mixtapeOnboarded') !== 'true') {
        addTooltipToElement(el, 'Cast to your TV or speaker (Chromecast)', 'top');
    }
}

function addTooltipToElement(el, tooltip, placement) {
    // Add beacon class
    el.classList.add('beacon');

    // Activate Bootstrap tooltip (with data-bs attributes)
    el.setAttribute('data-bs-toggle', 'tooltip');
    el.setAttribute('data-bs-placement', placement);
    el.setAttribute('data-bs-title', tooltip);
    el.setAttribute('data-bs-trigger', 'manual'); // Manual for first-load show

    // Initialize and show tooltip immediately
    const bsTooltip = new bootstrap.Tooltip(el);
    bsTooltip.show();

    // Hide tooltip after 5s or at hover/click
    setTimeout(() => bsTooltip.hide(), 5000);
    el.addEventListener('mouseenter', () => bsTooltip.hide(), { once: true });
    el.addEventListener('click', () => bsTooltip.hide(), { once: true });
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
