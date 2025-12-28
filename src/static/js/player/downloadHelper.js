// static/js/player/downloadHelper.js

/**
 * Provides contextual download instructions based on device type and progress feedback
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
        resetDownloadState();
    });

    // Handle desktop download with progress indicator
    const desktopBtn = document.getElementById('desktop-download-btn');
    if (desktopBtn) {
        desktopBtn.addEventListener('click', (e) => {
            showDownloadProgress();
        });
    }
}

function showDownloadProgress() {
    const progressDiv = document.getElementById('download-progress');
    const desktopBtn = document.getElementById('desktop-download-btn');
    
    if (progressDiv && desktopBtn) {
        // Show progress indicator
        progressDiv.classList.remove('d-none');
        
        // Disable button temporarily
        desktopBtn.classList.add('disabled');
        desktopBtn.style.opacity = '0.5';
        
        // Re-enable after 3 seconds (download should have started by then)
        setTimeout(() => {
            resetDownloadState();
        }, 3000);
    }
}

function resetDownloadState() {
    const progressDiv = document.getElementById('download-progress');
    const desktopBtn = document.getElementById('desktop-download-btn');
    
    if (progressDiv) {
        progressDiv.classList.add('d-none');
    }
    
    if (desktopBtn) {
        desktopBtn.classList.remove('disabled');
        desktopBtn.style.opacity = '1';
    }
}

function updateInstructions(isIOS, isAndroid, isMobile) {
    const infoBox = document.querySelector('#downloadModal .alert-info');
    if (!infoBox) return;

    let message = '';

    if (isIOS) {
        message = `
            <strong>iPhone detected!</strong><br>
            <strong>Stream:</strong> Plays immediately, may auto-cache in Apple Music.<br>
            <strong>Offline:</strong> Downloads each track separately when opened in your music app.
        `;
    } else if (isAndroid) {
        message = `
            <strong>Android detected!</strong><br>
            <strong>Stream:</strong> Opens in VLC/music app, plays on-demand.<br>
            <strong>Offline:</strong> Downloads all ${getTrackCount()} tracks via your music app.
        `;
    } else {
        message = `
            <strong>On a computer?</strong> Choose the desktop package for everything in one file.
            The ZIP includes an offline web player - just open index.html after extracting.
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
        const match = trackCountText.textContent.match(/(\d+) (tracks|files)/);
        if (match) return match[1];
    }
    return '12'; // fallback
}

function highlightRecommended(isMobile) {
    const mobileBtn = document.querySelector('#downloadModal .btn-primary');
    const desktopBtn = document.querySelector('#desktop-download-btn');

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
        
        desktopBtn.classList.remove('btn-outline-secondary');
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
