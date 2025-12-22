// static/js/base/navigationGuard.js
import { showAlert } from "../editor/utils.js"; // optional – you can reuse existing helpers

// Grab the modal elements once the DOM is ready
let navigateModal, leaveBtn, stayBtn;
let pendingNavigation = null; // will hold the URL we want to go to

export function initNavigationGuard(hasUnsavedChangesGetter) {
    // `hasUnsavedChangesGetter` is a function that returns the current flag
    // (we pass a closure from ui.js so the guard always sees the latest value).

    // Initialise modal (Bootstrap 5)
    const modalEl = document.getElementById('navigateAwayModal');
    navigateModal = new bootstrap.Modal(modalEl, {
        backdrop: 'static',   // prevent click‑outside dismissal
        keyboard: false       // prevent ESC dismissal
    });

    // Buttons inside the modal
    leaveBtn = document.getElementById('leaveBtn');
    stayBtn  = document.getElementById('stayBtn');

    // -----------------------------------------------------------------
    // 1️⃣ Intercept Back/Forward navigation via popstate
    // -----------------------------------------------------------------
    window.addEventListener('popstate', ev => {
        // `ev.state` is whatever you pushed onto history; we only care that
        // a navigation is happening.
        if (!hasUnsavedChangesGetter()) {
            // No unsaved changes → allow navigation normally
            return;
        }

        // There are unsaved changes → prevent the automatic navigation.
        // Push the current URL back onto the history stack so the address bar
        // stays where it was (otherwise the Back button would already have
        // changed it).
        history.pushState(null, '', location.href);

        // Store the *intended* destination (the URL the browser wanted to go to)
        pendingNavigation = location.href; // will be overwritten by the next pushState

        // Show our custom modal
        navigateModal.show();

        // Prevent the default popstate handling (the URL is already restored)
        ev.preventDefault();
    });

    // -----------------------------------------------------------------
    // 2️⃣ “Leave” button – user accepts loss of changes
    // -----------------------------------------------------------------
    leaveBtn.addEventListener('click', () => {
        navigateModal.hide();

        // Reset the flag so we don’t loop forever
        // (you could also call a function that clears the flag in UI)
        // Example: window.dispatchEvent(new Event('force-leave'));
        // For simplicity we just set the flag to false here:
        window.hasUnsavedChanges = false; // if you expose it globally

        // Perform the navigation we blocked earlier.
        // Using `history.back()` works because we just pushed the same URL
        // onto the stack a moment ago; going back will now land on the
        // *previous* entry (the one the user originally wanted).
        history.back();
    });

    // -----------------------------------------------------------------
    // 3️⃣ “Stay” button – user decides to remain on the page
    // -----------------------------------------------------------------
    stayBtn.addEventListener('click', () => {
        navigateModal.hide();
        // Nothing else to do – the URL is already where it was.
        pendingNavigation = null;
    });
}