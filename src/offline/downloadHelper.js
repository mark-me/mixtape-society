// static/js/player/downloadHelper.js

/**
 * Provides contextual download instructions based on device type
 */
export function initDownloadHelper() {
    const modal = document.getElementById('downloadModal');
    if (!modal) return;

    // Detect device type
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isAndroid = /Android/.test(navigator.userAgent);
    const isMobile = isIOS || isAndroid;

    modal.addEventListener('show.bs.modal', () => {
        updateInstructions(isIOS, isAndroid, isMobile);
        highlightRecommended(isMobile);
    });
}

function updateInstructions(isIOS, isAndroid, isMobile) {
    const infoBox = document.querySelector('#downloadModal .alert-info');
    if (!infoBox) return;

    let message = '';

    if (isIOS) {
        message = `
            <strong>iPhone detected!</strong><br>
            <strong>Stream:</strong> Instant access, plays directly from server. Apple Music may cache tracks automatically.<br>
            <strong>Offline:</strong> Downloads all tracks to your phone. Takes a few minutes but works without internet.
        `;
    } else if (isAndroid) {
        message = `
            <strong>Android detected!</strong><br>
            <strong>Stream:</strong> Quick start, plays on-demand. VLC can cache tracks for later.<br>
            <strong>Offline:</strong> Downloads all ${getTrackCount()} tracks to your device. Recommended for commuting!
        `;
    } else {
        message = `
            <strong>On a computer?</strong> Choose the desktop option for a complete package 
            with an offline player. On mobile, choose "Stream" for quick access or "Offline" 
            to download everything.
        `;
    }

    const contentDiv = infoBox.querySelector('#download-info-text');
    if (contentDiv) {
        contentDiv.innerHTML = message;
    }
}

function getTrackCount() {
    const trackCountText = document.querySelector('.opacity-75');
    if (trackCountText) {
        const match = trackCountText.textContent.match(/(\d+) tracks/);
        if (match) return match[1];
    }
    return '12'; // fallback
}

function highlightRecommended(isMobile) {
    const mobileBtn = document.querySelector('#downloadModal .btn-primary');
    const desktopBtn = document.querySelector('#downloadModal .btn-outline-primary');

    if (!mobileBtn || !desktopBtn) return;

    if (isMobile) {
        // Mobile already has btn-primary (highlighted)
        // Add a badge
        if (!mobileBtn.querySelector('.badge')) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-success ms-2';
            badge.textContent = 'Recommended';
            mobileBtn.querySelector('.fw-bold').appendChild(badge);
        }
    } else {
        // Switch highlighting for desktop
        mobileBtn.classList.remove('btn-primary');
        mobileBtn.classList.add('btn-outline-primary');
        
        desktopBtn.classList.remove('btn-outline-primary');
        desktopBtn.classList.add('btn-primary');

        // Add badge to desktop option
        if (!desktopBtn.querySelector('.badge')) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-success ms-2';
            badge.textContent = 'Recommended';
            desktopBtn.querySelector('.fw-bold').appendChild(badge);
        }
    }
}

/**
 * Shows a toast after M3U download with next steps
 */
export function showM3UInstructions() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isAndroid = /Android/.test(navigator.userAgent);

    let message = 'Playlist downloaded! ';

    if (isIOS) {
        message += 'Tap the file and choose "Open in Apple Music" or "Open in VLC".';
    } else if (isAndroid) {
        message += 'Open with VLC or your preferred music app.';
    } else {
        message += 'Open the file in your music player.';
    }

    // Create and show toast
    const toastHtml = `
        <div class="toast align-items-center text-bg-primary border-0" role="alert" id="m3u-toast">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-info-circle me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    // Find or create toast container
    let container = document.querySelector('.toast-container-download');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3 toast-container-download';
        container.style.zIndex = '1090';
        document.body.appendChild(container);
    }

    container.innerHTML = toastHtml;
    const toastElement = container.querySelector('#m3u-toast');
    const toast = new bootstrap.Toast(toastElement);
    toast.show();

    // Auto-remove after shown
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}
