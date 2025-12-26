const progressContainer = document.getElementById('progress-container');
const statsElement = document.getElementById('stats');
const etaElement = document.getElementById('eta');
const updateInfo = document.getElementById('update-info');

// Safety reload if stuck
let lastCurrent = 0;

// History for recent speed calculation
let history = []; // array of {time: timestamp_ms, processed: number}
const HISTORY_WINDOW_MS = 120000; // 2 minutes
const MIN_HISTORY_POINTS = 5;     // need at least this many points for reliable speed

// Progress bar elements
let progressWrapper = null;
let progressBarInner = null;

function createProgressBar() {
    progressWrapper = document.createElement('div');
    progressWrapper.className = 'progress';
    progressWrapper.role = 'progressbar';
    progressWrapper.style.height = '2.2rem';

    progressBarInner = document.createElement('div');
    progressBarInner.className = 'progress-bar progress-bar-striped progress-bar-animated';
    progressBarInner.style.width = '100%';
    progressBarInner.textContent = '';

    progressWrapper.appendChild(progressBarInner);
    return progressWrapper;
}

function calculateRecentSpeed(current, now) {
    // Remove old entries
    history = history.filter(h => now - h.time <= HISTORY_WINDOW_MS);

    // Add current point
    history.push({ time: now, processed: current });

    // Need enough data
    if (history.length < MIN_HISTORY_POINTS) {
        return null; // not enough data yet
    }

    // Get oldest and newest in window
    const oldest = history[0];
    const newest = history[history.length - 1];

    const elapsedMs = newest.time - oldest.time;
    const processedDelta = newest.processed - oldest.processed;

    if (elapsedMs <= 0 || processedDelta <= 0) return null;

    return processedDelta / (elapsedMs / 1000); // tracks per second
}

function updateStatus() {
    fetch('{{ url_for("indexing_status_json") }}')
        .then(response => response.json())
        .then(data => {
            if (data.done) {
                window.location.href = '{{ url_for("landing") }}';
                return;
            }

            const current = data.current || 0;
            const total = data.total || 0;
            const startedAt = data.started_at ? new Date(data.started_at) : null;
            const now = Date.now();

            if (total === 0) {
                // Still counting files
                progressContainer.innerHTML = `
                    <div class="progress" style="height: 2.2rem;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%"></div>
                    </div>
                    <p class="mt-4">Files are being counted and scanned… This may take a while for large collections.</p>
                `;
                statsElement.style.display = 'none';
                etaElement.style.display = 'none';
                return;
            }

            // Ensure progress bar exists
            if (!progressWrapper || !progressContainer.contains(progressWrapper)) {
                progressContainer.innerHTML = '';
                progressWrapper = createProgressBar();
                progressContainer.appendChild(progressWrapper);
            }

            // Update progress
            const percent = total > 0 ? (current / total * 100).toFixed(1) : 0;
            progressBarInner.style.width = `${percent}%`;
            progressBarInner.textContent = `${percent}%`;

            // Update stats
            document.getElementById('current').textContent = current.toLocaleString();
            document.getElementById('total').textContent = total.toLocaleString();

            // Overall speed (for display, optional)
            let displaySpeed = '—';
            if (startedAt && current > 100) {
                const elapsedMin = (now - startedAt) / 60000;
                const speed = Math.round(current / elapsedMin);
                displaySpeed = `${speed.toLocaleString()} /min`;
            }
            document.getElementById('speed').textContent = displaySpeed;

            // Show stats and ETA
            statsElement.style.display = 'flex';
            etaElement.style.display = 'block';

            // Improved ETA using recent speed
            const recentSpeedPerSec = calculateRecentSpeed(current, now);
            if (recentSpeedPerSec && recentSpeedPerSec > 0 && current > 50 && total > 100) {
                const remaining = total - current;
                const etaSec = remaining / recentSpeedPerSec;
                const etaMin = Math.round(etaSec / 60);

                if (etaMin < 1) {
                    etaElement.innerHTML = `Less than <strong>1 minute</strong> to go`;
                } else {
                    etaElement.innerHTML = `About <strong>${etaMin} minute${etaMin !== 1 ? 's' : ''}</strong> to go`;
                }
            } else {
                etaElement.textContent = 'Estimating time remaining…';
            }

            updateInfo.textContent = 'Updated just now';

            // Safety reload if stuck (now works because lastCurrent is defined)
            if (data.current > lastCurrent) {
                lastCurrent = data.current;
                clearTimeout(window.noProgressTimeout);
                window.noProgressTimeout = setTimeout(() => {
                    window.location.reload();
                }, 300000);  // 5 minutes no progress → reload
            }
        })
        .catch(err => {
            console.error('Failed to fetch indexing status', err);
            updateInfo.textContent = 'Update failed – retrying…';
        });
}

// Initial update and polling
updateStatus();
setInterval(updateStatus, 5000);