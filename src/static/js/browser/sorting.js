// static/js/browser/sorting.js

/**
 * Initializes the sorting functionality for the mixtape browser
 */
export function initSorting() {
    const sortBySelect = document.getElementById('sortBy');
    const sortOrderBtn = document.getElementById('sortOrderBtn');

    if (!sortBySelect || !sortOrderBtn) {
        return; // Elements not present on this page
    }

    // Handle sort field changes
    sortBySelect.addEventListener('change', () => {
        updateURL(sortBySelect.value, sortOrderBtn.dataset.order);
    });

    // Handle sort order toggle
    sortOrderBtn.addEventListener('click', () => {
        const currentOrder = sortOrderBtn.dataset.order;
        const newOrder = currentOrder === 'desc' ? 'asc' : 'desc';
        updateURL(sortBySelect.value, newOrder);
    });
}

/**
 * Updates the URL with new sorting parameters and reloads the page
 * Preserves search parameters if they exist
 * @param {string} sortBy - The field to sort by
 * @param {string} sortOrder - The sort order (asc or desc)
 */
function updateURL(sortBy, sortOrder) {
    const url = new URL(window.location.href);
    
    // Update sort parameters
    url.searchParams.set('sort_by', sortBy);
    url.searchParams.set('sort_order', sortOrder);
    
    // Preserve search parameters if they exist
    // (they'll already be in the URL, so we don't need to add them)
    
    window.location.href = url.toString();
}
