// static/js/browser/sorting.js

/**
 * Initializes the sorting functionality for the mixtape browser
 * Now uses a combined dropdown for sort field and order
 */
export function initSorting() {
    const sortByWithOrder = document.getElementById('sortByWithOrder');

    if (!sortByWithOrder) {
        return; // Element not present on this page
    }

    // Handle combined sort dropdown changes
    sortByWithOrder.addEventListener('change', () => {
        const [sortBy, sortOrder] = sortByWithOrder.value.split(':');
        updateURL(sortBy, sortOrder);
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
