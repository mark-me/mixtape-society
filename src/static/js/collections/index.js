// static/js/collections/index.js
/**
 * Collections Management Page JavaScript
 * Handles add, edit, delete, and resync operations for collections
 */

import { showAlert, showConfirm } from '../common/modalsStandard.js';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initCollectionsPage();
});

function initCollectionsPage() {
    // Add collection
    document.getElementById('saveAddCollectionBtn')?.addEventListener('click', handleAddCollection);

    // Edit collection
    document.querySelectorAll('.edit-collection-btn').forEach(btn => {
        btn.addEventListener('click', handleEditCollectionClick);
    });
    document.getElementById('saveEditCollectionBtn')?.addEventListener('click', handleSaveEdit);

    // Delete collection
    document.querySelectorAll('.delete-collection-btn').forEach(btn => {
        btn.addEventListener('click', handleDeleteCollectionClick);
    });
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', handleConfirmDelete);

    // Resync collection
    document.querySelectorAll('.resync-collection-btn').forEach(btn => {
        btn.addEventListener('click', handleResyncCollection);
    });

    // View stats (uses existing modal in base.html)
    document.querySelectorAll('.view-stats-btn').forEach(btn => {
        btn.addEventListener('click', handleViewStats);
    });

    // Auto-generate collection ID from name (lowercase, hyphenated)
    document.getElementById('addCollectionName')?.addEventListener('input', autoGenerateCollectionId);

    // Update the db-path preview whenever the ID or the db directory changes
    document.getElementById('addCollectionId')?.addEventListener('input', updateDbPathPreview);
    document.getElementById('addCollectionDbDir')?.addEventListener('input', updateDbPathPreview);
}

/**
 * Auto-generate collection ID from name
 */
function autoGenerateCollectionId(e) {
    const idInput = document.getElementById('addCollectionId');
    if (idInput && !idInput.value) {
        const name = e.target.value;
        const id = name.toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '');
        idInput.value = id;
    }
}

/**
 * Shows or hides the "Database file: /dir/id.db" preview below the db-dir
 * input whenever either the Collection ID or the db directory changes.
 */
function updateDbPathPreview() {
    const id  = document.getElementById('addCollectionId')?.value.trim();
    const dir = document.getElementById('addCollectionDbDir')?.value.trim();
    const preview      = document.getElementById('dbPathPreview');
    const previewValue = document.getElementById('dbPathPreviewValue');

    if (id && dir && preview && previewValue) {
        // Normalise: strip any trailing slash so we don't get double slashes
        const normalised = dir.replace(/\/+$/, '');
        previewValue.textContent = `${normalised}/${id}.db`;
        preview.style.display = 'block';
    } else if (preview) {
        preview.style.display = 'none';
    }
}

// ---------------------------------------------------------------------------
// Path Picker
// ---------------------------------------------------------------------------
// The picker modal is generic: any button with
//   data-bs-target="#pathPickerModal"
//   data-picker-target="<id of the input to fill>"
//   data-picker-dirs-only="1"       (optional – hide plain files)
// will open it.  On confirm the selected path is written into that input.
// ---------------------------------------------------------------------------

(function initPathPicker() {
    const modal       = document.getElementById('pathPickerModal');
    if (!modal) return;

    const entriesList = document.getElementById('pickerEntries');
    const breadcrumb  = document.getElementById('pickerBreadcrumb');
    const selectedEl  = document.getElementById('pickerSelectedPath');
    const confirmBtn  = document.getElementById('pickerConfirmBtn');

    // State kept for the current session of the modal
    let targetInputId = null;   // which <input> to fill on confirm
    let dirsOnly      = true;   // hide plain files?
    let currentPath   = '/';    // directory currently being listed

    // ------------------------------------------------------------------
    // Open: read config from the triggering button, load root
    // ------------------------------------------------------------------
    modal.addEventListener('show.bs.modal', (event) => {
        const btn = event.relatedTarget;                           // the <button> that opened it
        targetInputId = btn?.dataset.pickerTarget || null;
        dirsOnly      = btn?.dataset.pickerDirsOnly !== '0';       // default true

        // Reset UI
        confirmBtn.disabled = true;
        selectedEl.textContent = '—';

        // Start browsing from "/" (or the value already in the target input if non-empty)
        const existing = targetInputId && document.getElementById(targetInputId)?.value.trim();
        currentPath = existing || '/';

        loadPath(currentPath);
    });

    // ------------------------------------------------------------------
    // Confirm: write selected path back to the target input
    // ------------------------------------------------------------------
    confirmBtn.addEventListener('click', () => {
        if (targetInputId) {
            const input = document.getElementById(targetInputId);
            if (input) {
                input.value = currentPath;
                // Fire an 'input' event so any listeners (e.g. preview update) react
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        bootstrap.Modal.getInstance(modal).hide();
    });

    // ------------------------------------------------------------------
    // loadPath – fetch a directory listing and render breadcrumb + entries
    // ------------------------------------------------------------------
    const loadPath = async (dirPath) => {
        entriesList.innerHTML = '<li class="list-group-item text-center text-muted"><span class="spinner-border spinner-border-sm"></span></li>';

        try {
            const params = new URLSearchParams({ path: dirPath });
            if (!dirsOnly) params.set('show_files', '1');

            const res  = await fetch(`/collections/browse-path?${params}`);
            if (!res.ok) throw new Error((await res.json()).error || 'Browse failed');
            const data = await res.json();

            currentPath = data.current;
            renderBreadcrumb(currentPath);
            renderEntries(data.entries);

        } catch (err) {
            entriesList.innerHTML = `<li class="list-group-item text-danger"><i class="bi bi-exclamation-triangle"></i> ${err.message}</li>`;
        }
    }

    // ------------------------------------------------------------------
    // renderBreadcrumb – clickable path segments
    // ------------------------------------------------------------------
    const renderBreadcrumb = (path) => {
        // Split "/music/Jazz/Sub" → ["", "music", "Jazz", "Sub"]
        const parts = path.split('/');
        let html = '';
        let cumulative = '';

        parts.forEach((part, i) => {
            if (i === 0 && part === '') {
                // root segment "/"
                cumulative = '/';
                const isLast = parts.length === 2 && parts[1] === '';
                html += `<li class="breadcrumb-item ${isLast ? 'active' : ''}">
                            ${isLast
                                ? '/'
                                : `<a href="#" class="picker-crumb" data-path="/">/</a>`}
                         </li>`;
                return;
            }
            if (part === '') return;                              // skip trailing empty string

            cumulative += (cumulative.endsWith('/') ? '' : '/') + part;
            const isLast = (i === parts.length - 1);

            html += `<li class="breadcrumb-item ${isLast ? 'active' : ''}">
                        ${isLast
                            ? part
                            : `<a href="#" class="picker-crumb" data-path="${cumulative}">${part}</a>`}
                     </li>`;
        });

        breadcrumb.innerHTML = html;

        // Attach click handlers to crumb links (delegated – single listener)
        breadcrumb.querySelectorAll('.picker-crumb').forEach(a => {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                loadPath(a.dataset.path);
            });
        });
    }

    // ------------------------------------------------------------------
    // renderEntries – directory rows + optional "select this folder" row
    // ------------------------------------------------------------------
    const renderEntries = (entries) => {
        let html = '';

        // "Select current folder" option at the top
        html += `<li class="list-group-item list-group-item-action list-group-item-success
                          d-flex align-items-center gap-2 select-current-folder"
                     role="button">
                    <i class="bi bi-folder-check"></i>
                    <strong>Select this folder</strong>
                 </li>`;

        if (entries.length === 0) {
            html += `<li class="list-group-item text-muted text-center"><i class="bi bi-inbox"></i> Empty folder</li>`;
        }

        entries.forEach(entry => {
            if (entry.is_dir) {
                html += `<li class="list-group-item list-group-item-action d-flex align-items-center gap-2 picker-dir"
                              data-path="${entry.path}" role="button">
                            <i class="bi bi-folder"></i> ${entry.name}
                            <i class="bi bi-chevron-right ms-auto text-muted"></i>
                         </li>`;
            } else {
                // plain file – shown only when dirsOnly is false
                html += `<li class="list-group-item d-flex align-items-center gap-2 text-muted">
                            <i class="bi bi-file-earmark-music"></i> ${entry.name}
                         </li>`;
            }
        });

        entriesList.innerHTML = html;

        // "Select this folder" → enable confirm, highlight selection
        entriesList.querySelector('.select-current-folder')?.addEventListener('click', () => {
            selectedEl.textContent = currentPath;
            confirmBtn.disabled = false;
        });

        // Sub-directory rows → navigate into them
        entriesList.querySelectorAll('.picker-dir').forEach(li => {
            li.addEventListener('click', () => loadPath(li.dataset.path));
        });
    }
})();

/**
 * Handle adding a new collection
 */
async function handleAddCollection() {
    const form = document.getElementById('addCollectionForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const dbDir = document.getElementById('addCollectionDbDir').value.trim();

    const collectionData = {
        id: document.getElementById('addCollectionId').value.trim(),
        name: document.getElementById('addCollectionName').value.trim(),
        description: document.getElementById('addCollectionDescription').value.trim(),
        music_root: document.getElementById('addCollectionMusicRoot').value.trim(),
        db_path: `${dbDir.replace(/\/+$/, '')}/${document.getElementById('addCollectionId').value.trim()}.db`,
        is_default: document.getElementById('addSetAsDefault').checked
    };

    // Validate collection ID format
    if (!/^[a-z0-9-]+$/.test(collectionData.id)) {
        showAlert({
            title: 'Invalid Collection ID',
            message: 'Collection ID must contain only lowercase letters, numbers, and hyphens.'
        });
        return;
    }

    showLoading('Adding collection...');

    try {
        const response = await fetch('/collections/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(collectionData)
        });

        const data = await response.json();

        if (response.ok) {
            hideLoading();

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addCollectionModal'));
            modal.hide();

            // Show success message
            showAlert({
                title: 'Success',
                message: 'Collection added successfully! Reloading page...'
            });

            // Reload page to show new collection
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } else {
            hideLoading();
            showAlert({
                title: 'Error',
                message: data.error || 'Failed to add collection'
            });
        }

    } catch (error) {
        hideLoading();
        console.error('Error adding collection:', error);
        showAlert({
            title: 'Error',
            message: 'Failed to add collection: ' + error.message
        });
    }
}

/**
 * Handle edit collection button click
 */
function handleEditCollectionClick(e) {
    const {collectionId} = e.currentTarget.dataset;

    // Find collection data in the page
    const card = document.querySelector(`[data-collection-id="${collectionId}"]`);
    if (!card) return;

    const name = card.querySelector('.collection-header h5').textContent.trim();
    const description = card.querySelector('.collection-header p')?.textContent.trim() || '';

    // Populate edit form
    document.getElementById('editCollectionId').value = collectionId;
    document.getElementById('editCollectionName').value = name;
    document.getElementById('editCollectionDescription').value = description;

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('editCollectionModal'));
    modal.show();
}

/**
 * Handle saving collection edits
 */
async function handleSaveEdit() {
    const form = document.getElementById('editCollectionForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const collectionId = document.getElementById('editCollectionId').value;
    const updateData = {
        name: document.getElementById('editCollectionName').value.trim(),
        description: document.getElementById('editCollectionDescription').value.trim()
    };

    showLoading('Updating collection...');

    try {
        const response = await fetch(`/collections/edit/${collectionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });

        const data = await response.json();

        if (response.ok) {
            hideLoading();

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('editCollectionModal'));
            modal.hide();

            // Show success message
            showAlert({
                title: 'Success',
                message: 'Collection updated successfully! Reloading page...'
            });

            // Reload page
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } else {
            hideLoading();
            showAlert({
                title: 'Error',
                message: data.error || 'Failed to update collection'
            });
        }

    } catch (error) {
        hideLoading();
        console.error('Error updating collection:', error);
        showAlert({
            title: 'Error',
            message: 'Failed to update collection: ' + error.message
        });
    }
}

/**
 * Handle delete collection button click
 */
function handleDeleteCollectionClick(e) {
    const {collectionId, collectionName} = e.currentTarget.dataset;

    // Populate delete modal
    document.getElementById('deleteCollectionId').value = collectionId;
    document.getElementById('deleteCollectionName').textContent = collectionName;

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('deleteCollectionModal'));
    modal.show();
}

/**
 * Handle confirm delete
 */
async function handleConfirmDelete() {
    const collectionId = document.getElementById('deleteCollectionId').value;

    showLoading('Deleting collection...');

    try {
        const response = await fetch(`/collections/delete/${collectionId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            hideLoading();

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteCollectionModal'));
            modal.hide();

            // Show success message
            showAlert({
                title: 'Success',
                message: 'Collection deleted successfully! Reloading page...'
            });

            // Reload page
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } else {
            hideLoading();
            showAlert({
                title: 'Error',
                message: data.error || 'Failed to delete collection'
            });
        }

    } catch (error) {
        hideLoading();
        console.error('Error deleting collection:', error);
        showAlert({
            title: 'Error',
            message: 'Failed to delete collection: ' + error.message
        });
    }
}

/**
 * Handle resync collection
 */
async function handleResyncCollection(e) {
    const {collectionId, collectionName} = e.currentTarget.dataset;

    const confirmed = await showConfirm({
        title: 'Resync Collection',
        message: `This will rescan "${collectionName}" and update the database with any changes. This may take several minutes depending on library size.`,
        confirmText: 'Resync',
        cancelText: 'Cancel'
    });

    if (!confirmed) return;

    showLoading('Starting resync...');

    try {
        const response = await fetch(`/api/collections/${collectionId}/resync`, {
            method: 'POST'
        });

        const data = await response.json();

        hideLoading();

        if (response.ok) {
            showAlert({
                title: 'Resync Started',
                message: `Collection "${collectionName}" is now being resynced. This may take a few minutes.`
            });
        } else {
            showAlert({
                title: 'Error',
                message: data.error || 'Failed to start resync'
            });
        }

    } catch (error) {
        hideLoading();
        console.error('Error starting resync:', error);
        showAlert({
            title: 'Error',
            message: 'Failed to start resync: ' + error.message
        });
    }
}

/**
 * Handle view stats button click
 */
function handleViewStats(e) {
    const {collectionId, collectionName} = e.currentTarget.dataset;

    // Set data attributes on modal for JavaScript in base.html to use
    const modal = document.getElementById('collectionStatsModal');
    if (modal) {
        modal.dataset.collectionId = collectionId;
        modal.dataset.collectionName = collectionName;
    }
}

/**
 * Show loading overlay
 */
function showLoading(message = 'Processing...') {
    const overlay = document.getElementById('loadingOverlay');
    const messageEl = document.getElementById('loadingMessage');

    if (messageEl) messageEl.textContent = message;
    if (overlay) overlay.style.display = 'flex';
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'none';
}
