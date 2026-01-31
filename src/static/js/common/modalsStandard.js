// static/js/common/modalsStandard.js
// Modal instance
const appModalEl = document.getElementById('appModal');
const appModal = new bootstrap.Modal(appModalEl);

/**
 * Displays a modal alert dialog with a customizable title, message, and button text.
 * Shows a simple notification to the user that requires acknowledgment.
 *
 * @param {Object|string} options - Either an options object or a message string
 * @param {string} options.title - The title of the alert dialog (default: "Notice")
 * @param {string} options.message - The message to display in the alert body
 * @param {string} options.buttonText - The text for the confirmation button (default: "OK")
 */
export function showAlert(options) {
    // Support both object and string parameters for backwards compatibility
    if (typeof options === 'string') {
        options = { message: options };
    }

    const {
        title = "Notice",
        message,
        buttonText = "OK"
    } = options;

    document.getElementById('appModalTitle').textContent = title;
    document.getElementById('appModalBody').innerHTML = message;
    document.getElementById('appModalFooter').innerHTML = `
        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
            ${buttonText}
        </button>
    `;
    appModal.show();
}

/**
 * Displays a modal confirmation dialog with customizable title, message, and button texts.
 * Returns a promise that resolves to true if the user confirms, or false if cancelled or dismissed.
 *
 * @param {Object} options - Configuration object
 * @param {string} options.title - The title of the confirmation dialog (default: "Confirm")
 * @param {string} options.message - The message to display in the dialog body
 * @param {string} options.confirmText - The text for the confirmation button (default: "Confirm")
 * @param {string} options.cancelText - The text for the cancellation button (default: "Cancel")
 * @returns {Promise<boolean>} A Promise that resolves to true if confirmed, false otherwise
 */
export function showConfirm({
    title = "Confirm",
    message,
    confirmText = "Confirm",
    cancelText = "Cancel"
}) {
    return new Promise(resolve => {
        document.getElementById('appModalTitle').textContent = title;
        document.getElementById('appModalBody').innerHTML = message;
        document.getElementById('appModalFooter').innerHTML = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                ${cancelText}
            </button>
            <button type="button" class="btn btn-danger" id="appModalConfirmBtn">
                ${confirmText}
            </button>
        `;

        let confirmed = false;
        const confirmBtn = document.getElementById('appModalConfirmBtn');

        confirmBtn.onclick = () => {
            confirmed = true;
            appModal.hide();
            resolve(true);
        };

        // If the modal is closed without confirming (X, backdrop, ESC)
        const hiddenHandler = () => {
            if (!confirmed) resolve(false);
        };
        appModalEl.addEventListener('hidden.bs.modal', hiddenHandler, { once: true });

        appModal.show();
    });
}