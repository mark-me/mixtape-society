// static/js/editor/progressModal.js

/**
 * Progress modal for displaying real-time caching progress
 * with Bootstrap theme support and mobile responsiveness
 */
export class ProgressModal {
    constructor() {
        this.modal = null;
        this.eventSource = null;
        this.createModal();
    }

    createModal() {
        // Create modal HTML with theme-aware styling
        const modalHTML = `
            <div class="modal fade" id="progressModal" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-fullscreen-sm-down">
                    <div class="modal-content">
                        <div class="modal-header bg-success text-white">
                            <h5 class="modal-title">
                                <i class="bi bi-hourglass-split me-2"></i>
                                Saving Mixtape
                            </h5>
                        </div>
                        <div class="modal-body">
                            <!-- Overall progress -->
                            <div class="mb-4">
                                <div class="d-flex justify-content-between mb-2">
                                    <span id="progress-main-label" class="fw-semibold">Initializing...</span>
                                    <span id="progress-percentage" class="text-muted">0%</span>
                                </div>
                                <div class="progress" style="height: 24px;">
                                    <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-success"
                                         role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                    </div>
                                </div>
                            </div>

                            <!-- Status messages -->
                            <div class="card border">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <span class="fw-semibold">Progress</span>
                                    <button id="progress-clear-log" class="btn btn-sm btn-outline-secondary" title="Clear log">
                                        <i class="bi bi-trash3"></i>
                                    </button>
                                </div>
                                <div class="card-body p-0">
                                    <div id="progress-log" class="overflow-auto font-monospace small bg-body" style="max-height: 300px;">
                                        <!-- Log entries will be added here -->
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" id="progress-close-btn" disabled>
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add to page
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Get modal instance
        this.modal = new bootstrap.Modal(document.getElementById('progressModal'));

        // Setup event listeners
        document.getElementById('progress-clear-log').addEventListener('click', () => {
            this.clearLog();
        });

        document.getElementById('progress-close-btn').addEventListener('click', () => {
            this.close();
        });
    }

    show(slug) {
        // Reset UI
        this.setMainLabel('Initializing...');
        this.setProgress(0, 0);
        this.clearLog();
        this.enableCloseButton(false);

        // Show modal
        this.modal.show();

        // Start listening for progress updates
        this.connectToProgressStream(slug);
    }

    connectToProgressStream(slug) {
        // Close existing connection if any
        if (this.eventSource) {
            this.eventSource.close();
        }

        // Create new SSE connection
        this.eventSource = new EventSource(`/editor/progress/${slug}`);

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleProgressEvent(data);
            } catch (error) {
                console.error('Failed to parse progress event:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('Progress stream error:', error);
            this.addLogEntry('Connection error - retrying...', 'text-warning');

            // Close and cleanup
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.eventSource.close();
                this.handleComplete();
            }
        };

        // Timeout after 5 minutes
        setTimeout(() => {
            if (this.eventSource && this.eventSource.readyState !== EventSource.CLOSED) {
                this.eventSource.close();
                this.addLogEntry('Timeout - caching continues in background', 'text-warning');
                this.handleComplete();
            }
        }, 300000);
    }

    handleProgressEvent(data) {
        const { step, status, message, current, total } = data;

        // Update main label based on step
        const stepLabels = {
            'initializing': 'Initializing...',
            'analyzing': 'Analyzing tracks...',
            'caching': 'Caching files...',
            'completed': 'Complete!',
            'error': 'Error'
        };

        if (stepLabels[step]) {
            this.setMainLabel(stepLabels[step]);
        }

        // Update progress bar
        if (total > 0) {
            this.setProgress(current, total);
        }

        // Add log entry with appropriate styling
        const iconClass = this.getIconForStatus(status);
        const textClass = this.getTextClassForStatus(status);

        this.addLogEntry(`${iconClass} ${message}`, textClass);

        // Handle completion
        if (status === 'completed' || status === 'failed') {
            this.handleComplete();
        }
    }

    getIconForStatus(status) {
        const icons = {
            'pending': '⏳',
            'in_progress': '⚙️',
            'completed': '✓',
            'failed': '✗',
            'skipped': '⊘'
        };
        return icons[status] || '•';
    }

    getTextClassForStatus(status) {
        const classes = {
            'completed': 'text-success',
            'failed': 'text-danger',
            'skipped': 'text-muted',
            'in_progress': 'text-primary'
        };
        return classes[status] || '';
    }

    setMainLabel(text) {
        document.getElementById('progress-main-label').textContent = text;
    }

    setProgress(current, total) {
        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        const progressBar = document.getElementById('progress-bar');
        const percentageLabel = document.getElementById('progress-percentage');

        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
        percentageLabel.textContent = `${percentage}%`;

        // Update progress bar color based on completion
        if (percentage === 100) {
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
            progressBar.classList.add('bg-success');
        }
    }

    addLogEntry(message, className = '') {
        const log = document.getElementById('progress-log');
        const timestamp = new Date().toLocaleTimeString();

        const entry = document.createElement('div');
        // Use Bootstrap's border and padding utilities + theme-aware text color
        entry.className = `p-2 border-bottom ${className}`;
        entry.style.cssText = 'word-break: break-word;'; // Ensure long filenames wrap
        entry.innerHTML = `<small class="text-muted">[${timestamp}]</small> <span>${this.escapeHtml(message)}</span>`;

        log.appendChild(entry);

        // Auto-scroll to bottom
        log.scrollTop = log.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    clearLog() {
        document.getElementById('progress-log').innerHTML = '';
    }

    handleComplete() {
        // Close SSE connection
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        // Enable close button
        this.enableCloseButton(true);

        // Stop progress bar animation
        const progressBar = document.getElementById('progress-bar');
        progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
    }

    enableCloseButton(enabled) {
        const btn = document.getElementById('progress-close-btn');
        btn.disabled = !enabled;

        if (enabled) {
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-success');
            btn.innerHTML = '<i class="bi bi-check2"></i> Close';
        } else {
            btn.classList.add('btn-secondary');
            btn.classList.remove('btn-success');
            btn.textContent = 'Please wait...';
        }
    }

    close() {
        // Close SSE connection if still open
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        // Hide modal
        this.modal.hide();
    }
}

// Create global instance
let progressModal = null;

export function showProgressModal(slug) {
    if (!progressModal) {
        progressModal = new ProgressModal();
    }
    progressModal.show(slug);
}