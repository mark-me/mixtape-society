// static/js/base/collectionStats.js
/**
 * Initializes the collection statistics modal functionality.
 * Supports both single collection and multi-collection modes.
 * Loads stats when modal opens and handles resync button clicks.
 *
 * Returns:
 *   None.
 */
export function initCollectionStats() {
    const statsModal = document.getElementById('collectionStatsModal');
    const resyncBtn = document.getElementById('resyncBtn');
    const confirmModal = document.getElementById('resyncConfirmModal') 
        ? new bootstrap.Modal(document.getElementById('resyncConfirmModal'))
        : null;
    const confirmResyncBtn = document.getElementById('confirmResyncBtn');

    if (!statsModal) return;

    let currentCollectionId = null;

    // Load stats when modal is shown
    statsModal.addEventListener('show.bs.modal', async (event) => {
        // Get collection ID from the button that triggered the modal
        const button = event.relatedTarget;
        currentCollectionId = button?.dataset.collectionId || 
                             statsModal.dataset.collectionId || 
                             null;
        
        const collectionName = button?.dataset.collectionName || null;
        
        // Update modal title if collection name is provided
        if (collectionName) {
            const modalTitle = statsModal.querySelector('.modal-title');
            if (modalTitle) {
                modalTitle.innerHTML = `<i class="bi bi-bar-chart-fill"></i> ${collectionName} Statistics`;
            }
        }
        
        await loadStats(currentCollectionId);
    });

    // Handle resync button click - show confirmation modal
    if (resyncBtn) {
        resyncBtn.addEventListener('click', () => {
            if (confirmModal) {
                // Hide the stats modal
                const statsModalInstance = bootstrap.Modal.getInstance(statsModal);
                if (statsModalInstance) {
                    statsModalInstance.hide();
                }
                
                // Show confirmation modal
                confirmModal.show();
            } else {
                // No confirmation modal, perform resync directly
                performResync(currentCollectionId);
            }
        });
    }

    // Handle confirm resync button
    if (confirmResyncBtn) {
        confirmResyncBtn.addEventListener('click', async () => {
            await performResync(currentCollectionId);
            if (confirmModal) {
                confirmModal.hide();
            }
        });
    }
}

/**
 * Loads collection statistics from the server and updates the UI.
 *
 * Args:
 *   collectionId: ID of the collection to load stats for (null for default)
 *
 * Returns:
 *   Promise<void>
 */
async function loadStats(collectionId = null) {
    const loadingEl = document.getElementById('statsLoading');
    const contentEl = document.getElementById('statsContent');
    const errorEl = document.getElementById('statsError');

    // Show loading state
    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';

    try {
        let url;
        if (collectionId) {
            // Multi-collection mode: use collections API
            url = `/api/collections/${collectionId}/stats`;
        } else {
            // Single collection mode: use legacy endpoint
            url = '/collection-stats';
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const stats = await response.json();

        // Update the UI with stats
        // Handle both old format (num_artists) and new format (artist_count)
        const artistCount = stats.artist_count || stats.num_artists || 0;
        const albumCount = stats.album_count || stats.num_albums || 0;
        const trackCount = stats.track_count || stats.num_tracks || 0;
        const totalDuration = stats.total_duration || 0;
        const totalSize = stats.total_size || 0;
        const lastAdded = stats.last_added || null;

        if (document.getElementById('statsArtists')) {
            document.getElementById('statsArtists').textContent = artistCount.toLocaleString();
        }
        if (document.getElementById('statsAlbums')) {
            document.getElementById('statsAlbums').textContent = albumCount.toLocaleString();
        }
        if (document.getElementById('statsTracks')) {
            document.getElementById('statsTracks').textContent = trackCount.toLocaleString();
        }
        if (document.getElementById('statsDuration')) {
            document.getElementById('statsDuration').textContent = formatDuration(totalDuration);
        }
        
        // Optional fields
        if (document.getElementById('statsTotalSize')) {
            const sizeGB = (totalSize / (1024 ** 3)).toFixed(2);
            document.getElementById('statsTotalSize').textContent = `${sizeGB} GB`;
        }
        if (document.getElementById('statsLastAdded')) {
            document.getElementById('statsLastAdded').textContent = formatLastAdded(lastAdded);
        }

        // Show content, hide loading
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';

    } catch (error) {
        console.error('Error loading collection stats:', error);
        
        // Show error state
        if (loadingEl) loadingEl.style.display = 'none';
        if (errorEl) {
            errorEl.style.display = 'block';
            const errorMsg = document.getElementById('statsErrorMessage');
            if (errorMsg) {
                errorMsg.textContent = 'Failed to load statistics. Please try again.';
            }
        }
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
 * Args:
 *   collectionId: ID of the collection to resync (null for default)
 *
 * Returns:
 *   Promise<void>
 */
async function performResync(collectionId = null) {
    try {
        let url;
        if (collectionId) {
            // Multi-collection mode: use collections API
            url = `/api/collections/${collectionId}/resync`;
        } else {
            // Single collection mode: use legacy endpoint
            url = '/resync';
        }
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const result = await response.json();

        if (result.success || response.ok) {
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
    // Use the existing appModal if available
    if (typeof window.showAlert === 'function') {
        window.showAlert(title, message, type);
    } else {
        // Fallback to native alert
        alert(`${title}: ${message}`);
    }
}
