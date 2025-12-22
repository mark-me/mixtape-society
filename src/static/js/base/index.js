// static/js/base/index.js
import { initThemeSwitcher } from './themeSwitcher.js';
import { initTooltips } from './tooltipInit.js';
import { initNavigationGuard } from "./navigationGuard.js";
import { hasUnsavedChanges } from "../editor/ui.js";

document.addEventListener('DOMContentLoaded', () => {
    initThemeSwitcher();
    initTooltips();
    // Initialise the guard, passing a function that returns the latest flag.
    initNavigationGuard(() => getUnsavedFlag());
});

export function getUnsavedFlag() {
    return hasUnsavedChanges; // or whatever variable you use internally
}


