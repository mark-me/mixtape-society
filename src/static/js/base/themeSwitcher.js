/**
 * Initializes the theme switcher UI and applies the selected or system theme.
 * Handles user interaction for theme selection and responds to OS-level theme changes.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initThemeSwitcher() {
    const html = document.documentElement;
    const themeButtons = document.querySelectorAll('[data-theme]');
    const themeIcon = document.getElementById('themeNavbarIcon');

    function applyTheme(theme) {
        if (theme === 'auto') {
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            html.setAttribute('data-bs-theme', isDark ? 'dark' : 'light');
            themeIcon.className = 'bi bi-circle-half';
        } else {
            html.setAttribute('data-bs-theme', theme);
            themeIcon.className = theme === 'dark' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
        }

        localStorage.setItem('theme', theme);
        themeButtons.forEach(btn =>
            btn.classList.toggle('active', btn.dataset.theme === theme)
        );
    }

    // ----- initialise -------------------------------------------------
    const savedTheme = localStorage.getItem('theme') || 'auto';
    applyTheme(savedTheme);

    // ----- UI interaction ---------------------------------------------
    themeButtons.forEach(btn => {
        btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
    });

    // ----- react to OS‑level theme changes ----------------------------
    window.matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', () => {
            if ((localStorage.getItem('theme') || 'auto') === 'auto') {
                applyTheme('auto');
            }
        });
}