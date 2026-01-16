// static/js/browser/search.js

/**
 * Initializes the hybrid search functionality for the mixtape browser
 * - Instant title search (client-side filtering)
 * - Deep search button (server-side search in tracks/artists/albums)
 */
export function initSearch() {
    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearch');
    const deepSearchBtn = document.getElementById('deepSearchBtn');
    const mixtapeItems = document.querySelectorAll('.mixtape-item');

    if (!searchInput || !deepSearchBtn) {
        return; // Elements not present on this page
    }

    // Check if we're on a deep search results page
    const urlParams = new URLSearchParams(window.location.search);
    const isDeepSearchActive = urlParams.get('deep') === 'true';

    // Store original display states
    const originalDisplays = new Map();
    mixtapeItems.forEach(item => {
        originalDisplays.set(item, item.style.display || '');
    });

    /**
     * Client-side instant title filtering
     */
    const filterByTitle = (query) => {
        // Don't do client-side filtering if we're showing deep search results
        if (isDeepSearchActive) {
            return;
        }

        const lowerQuery = query.toLowerCase().trim();

        // If empty query, show all mixtapes
        if (!lowerQuery) {
            mixtapeItems.forEach(item => {
                item.style.display = originalDisplays.get(item);
            });
            updateEmptyState(mixtapeItems.length, false);
            return;
        }

        let visibleCount = 0;

        mixtapeItems.forEach(item => {
            const titleElement = item.querySelector('.mixtape-title');
            if (titleElement) {
                const title = titleElement.textContent.toLowerCase();
                if (title.includes(lowerQuery)) {
                    item.style.display = originalDisplays.get(item);
                    visibleCount++;
                } else {
                    item.style.display = 'none';
                }
            }
        });

        updateEmptyState(visibleCount, true, query);
    }

    /**
     * Update empty state message based on search results
     */
    const updateEmptyState = (count, isSearching, query = '') => {
        let emptyState = document.querySelector('.no-mixtapes');

        // Create empty state if it doesn't exist
        if (!emptyState) {
            const container = document.querySelector('.container.py-5');
            emptyState = document.createElement('div');
            emptyState.className = 'no-mixtapes';
            container.appendChild(emptyState);
        }

        if (count === 0 && isSearching) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = `
                <i class="bi bi-cassette display-1 mb-4 text-muted"></i>
                <h3>No mixtapes found</h3>
                <p class="text-muted">No mixtapes match "${query}" in their titles</p>
                <p class="text-muted"><small>Try the "Search Tracks" button for a deeper search</small></p>
            `;
        } else if (count === 0 && !isSearching) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = `
                <i class="bi bi-cassette display-1 mb-4 text-muted"></i>
                <h3>No mixtapes yet...</h3>
                <p class="text-muted">But that's coming soon! Create one right now.</p>
            `;
        } else {
            emptyState.style.display = 'none';
        }
    }

    /**
     * Handle input changes with instant filtering
     */
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value;

        // Show/hide clear button
        clearSearchBtn.style.display = query ? 'block' : 'none';

        // Enable/disable deep search button
        deepSearchBtn.disabled = !query;

        // Perform instant title filtering (only if not on deep search results page)
        if (!isDeepSearchActive) {
            filterByTitle(query);
        }
    });

    /**
     * Clear search and reset view
     */
    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearSearchBtn.style.display = 'none';
        deepSearchBtn.disabled = true;

        // Reset to showing all mixtapes (only if not already on deep search page)
        if (!isDeepSearchActive) {
            filterByTitle('');
        }

        // If we came from a server-side search, reload to clear it
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('search') || urlParams.has('deep')) {
            // Remove search params but keep sort params
            urlParams.delete('search');
            urlParams.delete('deep');
            const newUrl = urlParams.toString() ?
                `${window.location.pathname}?${urlParams.toString()}` :
                window.location.pathname;
            window.location.href = newUrl;
        }
    });

    /**
     * Deep search - performs server-side search through tracks/artists/albums
     */
    deepSearchBtn.addEventListener('click', () => {
        const query = searchInput.value.trim();
        if (!query) return;

        // Build URL with search query and current sort settings
        const url = new URL(window.location.href);
        url.searchParams.set('search', query);
        url.searchParams.set('deep', 'true');

        // Preserve existing sort parameters
        const sortBy = document.getElementById('sortBy')?.value;
        const sortOrder = document.getElementById('sortOrderBtn')?.dataset.order;
        if (sortBy) url.searchParams.set('sort_by', sortBy);
        if (sortOrder) url.searchParams.set('sort_order', sortOrder);

        window.location.href = url.toString();
    });

    /**
     * Allow Enter key to trigger deep search
     */
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && searchInput.value.trim()) {
            deepSearchBtn.click();
        }
    });

    // Initial setup based on page state
    if (isDeepSearchActive) {
            // We're showing deep search results - don't do any client-side filtering
            if (searchInput.value) {
                clearSearchBtn.style.display = 'block';
                deepSearchBtn.disabled = false;
            }
        }
    else if (searchInput.value) {
                filterByTitle(searchInput.value);
                clearSearchBtn.style.display = 'block';
                deepSearchBtn.disabled = false;
            }
}
