// static/js/base/collectionStats.js
/**
 * Initializes the collection statistics modal functionality.
 * Loads stats when modal opens and handles resync button clicks.
 *
 * Returns:
 *   None.
 */
export function initCollectionStats() {
    const statsModal = document.getElementById('collectionStatsModal');
    const resyncBtn = document.getElementById('resyncBtn');
    const confirmModal = new bootstrap.Modal(document.getElementById('resyncConfirmModal'));
    const confirmResyncBtn = document.getElementById('confirmResyncBtn');

    if (!statsModal) return;

    // Load stats when modal is shown
    statsModal.addEventListener('show.bs.modal', async () => {
        await loadStats();
    });

    // Handle resync button click - show confirmation modal
    if (resyncBtn) {
        resyncBtn.addEventListener('click', () => {
            // Hide the stats modal
            const statsModalInstance = bootstrap.Modal.getInstance(statsModal);
            statsModalInstance.hide();
            
            // Show confirmation modal
            confirmModal.show();
        });
    }

    // Handle confirm resync button
    if (confirmResyncBtn) {
        confirmResyncBtn.addEventListener('click', async () => {
            await performResync();
            confirmModal.hide();
        });
    }
}

/**
 * Loads collection statistics from the server and updates the UI.
 *
 * Returns:
 *   Promise<void>
 */
async function loadStats() {
    const loadingEl = document.getElementById('statsLoading');
    const contentEl = document.getElementById('statsContent');
    const errorEl = document.getElementById('statsError');

    // Show loading state
    loadingEl.style.display = 'block';
    contentEl.style.display = 'none';
    errorEl.style.display = 'none';

    try {
        const response = await fetch('/collection-stats');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const stats = await response.json();

        // Update the UI with stats
        document.getElementById('statsArtists').textContent = stats.num_artists.toLocaleString();
        document.getElementById('statsAlbums').textContent = stats.num_albums.toLocaleString();
        document.getElementById('statsTracks').textContent = stats.num_tracks.toLocaleString();
        document.getElementById('statsDuration').textContent = formatDuration(stats.total_duration);
        document.getElementById('statsLastAdded').textContent = formatLastAdded(stats.last_added);

        // Show content, hide loading
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';

    } catch (error) {
        console.error('Error loading collection stats:', error);
        
        // Show error state
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        document.getElementById('statsErrorMessage').textContent = 
            'Failed to load statistics. Please try again.';
    }
}

/**
 * Formats duration in seconds to a human-readable string.
 *
 * Args:
 *   seconds: Total duration in seconds
 *
 * Returns:
 *   Formatted string like "5d 3h 45m" or "2h 30m"
 */
function formatDuration(seconds) {
    if (!seconds || seconds === 0) return '0m';

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);

    return parts.join(' ') || '0m';
}

/**
 * Formats a timestamp to a human-readable relative time string.
 *
 * Args:
 *   timestamp: Unix timestamp or ISO date string
 *
 * Returns:
 *   Formatted string like "2 days ago" or "Just now"
 */
function formatLastAdded(timestamp) {
    if (!timestamp) return 'Never';

    const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    
    // For older dates, show the actual date
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

/**
 * Performs the resync operation by calling the server endpoint.
 *
 * Returns:
 *   Promise<void>
 */
async function performResync() {
    try {
        const response = await fetch('/resync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const result = await response.json();

        if (result.success) {
            // Reload the page immediately to show indexing status
            window.location.reload();
        } else {
            showAlert('Error', result.error || 'Failed to start resync', 'danger');
        }
    } catch (error) {
        console.error('Error performing resync:', error);
        showAlert('Error', 'Failed to start resync. Please try again.', 'danger');
    }
}

/**
 * Shows an alert message using Bootstrap's alert component.
 *
 * Args:
 *   title: Alert title
 *   message: Alert message
 *   type: Bootstrap alert type (success, danger, warning, info)
 *
 * Returns:
 *   None
 */
function showAlert(title, message, type = 'info') {
    // You can use the existing appModal or create a toast notification
    // This is a simple implementation using the global modal
    if (typeof window.showAlert === 'function') {
        window.showAlert(title, message, type);
    } else {
        // Fallback to native alert
        alert(`${title}: ${message}`);
    }
}
