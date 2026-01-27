// static/js/browser/collections.js
/**
 * Collection Management for Browse View
 * 
 * Handles:
 * - Collection filtering
 * - Collection badge styling
 * - Collection statistics
 */

/**
 * Initialize collection filter buttons
 */
export function initCollectionFilter() {
    const filterButtons = document.querySelectorAll('[name="collectionFilter"]');
    
    if (filterButtons.length === 0) {
        // Single collection or no filtering UI
        return;
    }
    
    console.log('Initializing collection filter with', filterButtons.length, 'options');
    
    // Handle filter changes
    filterButtons.forEach(button => {
        button.addEventListener('change', (e) => {
            const collectionId = e.target.value;
            applyCollectionFilter(collectionId);
        });
    });
    
    // Set initial state based on URL
    const urlParams = new URLSearchParams(window.location.search);
    const currentFilter = urlParams.get('collection');
    
    if (currentFilter) {
        const button = document.getElementById(`filter-${currentFilter}`);
        if (button) {
            button.checked = true;
        }
    } else {
        const allButton = document.getElementById('filter-all');
        if (allButton) {
            allButton.checked = true;
        }
    }
}

/**
 * Apply collection filter
 */
function applyCollectionFilter(collectionId) {
    const url = new URL(window.location);
    
    if (collectionId) {
        url.searchParams.set('collection', collectionId);
    } else {
        url.searchParams.delete('collection');
    }
    
    // Preserve other query params (search, sort, etc.)
    window.location.href = url.toString();
}

/**
 * Colorize collection badges with consistent colors
 */
export function colorizeCollectionBadges() {
    const badges = document.querySelectorAll('[data-collection-id]');
    
    if (badges.length === 0) {
        return;
    }
    
    // Color palette for collections
    const colors = {
        'main': '#0d6efd',      // Bootstrap primary blue
        'jazz': '#6f42c1',      // Purple
        'classical': '#d63384', // Pink
        'rock': '#dc3545',      // Red
        'electronic': '#20c997', // Teal
        'default': '#6c757d'    // Gray
    };
    
    badges.forEach(badge => {
        const collectionId = badge.dataset.collectionId;
        const color = colors[collectionId] || colors.default;
        
        // Apply background color
        badge.style.backgroundColor = color;
        badge.style.color = 'white';
        badge.style.borderColor = color;
    });
    
    console.log('Colorized', badges.length, 'collection badges');
}

/**
 * Update collection counts in filter buttons
 */
export function updateCollectionCounts() {
    const filterButtons = document.querySelectorAll('[name="collectionFilter"]');
    
    if (filterButtons.length === 0) {
        return;
    }
    
    // Count mixtapes per collection
    const counts = {};
    const mixtapeCards = document.querySelectorAll('.mixtape-item[data-collection-id]');
    
    mixtapeCards.forEach(card => {
        const collectionId = card.dataset.collectionId;
        counts[collectionId] = (counts[collectionId] || 0) + 1;
    });
    
    // Update button labels
    filterButtons.forEach(button => {
        const collectionId = button.value;
        const label = button.nextElementSibling; // Label element
        
        if (!label) return;
        
        if (collectionId === '') {
            // "All" button
            const totalCount = mixtapeCards.length;
            label.innerHTML = `All (${totalCount})`;
        } else {
            // Specific collection
            const count = counts[collectionId] || 0;
            const name = label.textContent.split('(')[0].trim();
            label.innerHTML = `${name} (${count})`;
        }
    });
}

/**
 * Client-side collection filtering (for instant feedback)
 * Use this if you want to filter without page reload
 */
export function filterMixtapesClientSide(collectionId) {
    const mixtapeCards = document.querySelectorAll('.mixtape-item');
    
    mixtapeCards.forEach(card => {
        const cardCollectionId = card.dataset.collectionId;
        
        if (!collectionId || cardCollectionId === collectionId) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
    
    // Update counts after filtering
    updateCollectionCounts();
}

/**
 * Add collection info to mixtape cards dynamically
 * Use if server doesn't include collection badges
 */
export function addCollectionBadges(collections) {
    const mixtapeCards = document.querySelectorAll('.mixtape-item');
    
    mixtapeCards.forEach(card => {
        const collectionId = card.dataset.collectionId;
        
        if (!collectionId) return;
        
        // Find collection info
        const collection = collections.find(c => c.id === collectionId);
        if (!collection) return;
        
        // Check if badge already exists
        if (card.querySelector('.collection-badge')) return;
        
        // Create badge
        const badge = document.createElement('span');
        badge.className = 'badge collection-badge';
        badge.dataset.collectionId = collectionId;
        badge.innerHTML = `<i class="bi bi-collection"></i> ${collection.name}`;
        
        // Add to card header
        const badgesContainer = card.querySelector('.badges');
        if (badgesContainer) {
            badgesContainer.insertBefore(badge, badgesContainer.firstChild);
        }
    });
    
    // Colorize newly added badges
    colorizeCollectionBadges();
}

/**
 * Show collection statistics
 */
export function showCollectionStats(collections) {
    const statsContainer = document.getElementById('collectionStats');
    
    if (!statsContainer || collections.length <= 1) {
        return;
    }
    
    // Calculate stats
    const stats = collections.map(collection => ({
        name: collection.name,
        id: collection.id,
        trackCount: collection.stats?.track_count || 0,
        artistCount: collection.stats?.artist_count || 0,
        albumCount: collection.stats?.album_count || 0
    }));
    
    // Render stats
    statsContainer.innerHTML = `
        <div class="row g-3">
            ${stats.map(stat => `
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">
                                <span class="badge" data-collection-id="${stat.id}">
                                    ${stat.name}
                                </span>
                            </h6>
                            <ul class="list-unstyled mb-0">
                                <li><small>${stat.trackCount} tracks</small></li>
                                <li><small>${stat.artistCount} artists</small></li>
                                <li><small>${stat.albumCount} albums</small></li>
                            </ul>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    
    // Colorize badges in stats
    colorizeCollectionBadges();
}

/**
 * Initialize tooltips for collection badges
 */
export function initCollectionTooltips() {
    const badges = document.querySelectorAll('[data-collection-id][data-bs-toggle="tooltip"]');
    
    badges.forEach(badge => {
        const collectionId = badge.dataset.collectionId;
        const collectionName = badge.textContent.trim();
        
        // Set tooltip text
        badge.setAttribute('title', `From ${collectionName} collection`);
        badge.setAttribute('data-bs-placement', 'top');
    });
    
    // Initialize Bootstrap tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(el => new bootstrap.Tooltip(el));
    }
}
