
/**
 * Initializes mixtape deletion functionality with confirmation modal and success toast.
 * Handles user interaction for deleting a mixtape, including feedback and error handling.
 *
 * Args:
 *   None.
 *
 * Returns:
 *   None.
 */
export function initDeleteMixtape() {
    const deleteModalEl = document.getElementById('deleteConfirmModal');
    const deleteModal = new bootstrap.Modal(deleteModalEl);
    const deleteSuccessToastEl = document.getElementById('deleteSuccessToast');
    const deleteSuccessToast = new bootstrap.Toast(deleteSuccessToastEl);

    const modalTitle = document.getElementById('deleteModalTitle');
    const confirmBtn = document.getElementById('confirmDeleteBtn');

    let pendingSlug = null;

    // Open modal
    document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', () => {
            pendingSlug = btn.dataset.slug;
            modalTitle.textContent = btn.dataset.title || 'Untitled';
            deleteModal.show();
        });
    });

    // Confirm deletion
    confirmBtn.addEventListener('click', async () => {
        if (!pendingSlug) return;

        try {
            const r = await fetch(`/mixtapes/delete/${pendingSlug}`, {
                method: 'POST',
                credentials: 'include'
            });

            const contentType = r.headers.get('content-type');
            const data = contentType && contentType.includes('application/json')
                ? await r.json()
                : { error: await r.text() };

            if (r.ok && data.success !== false) {
                deleteSuccessToast.show();
                deleteModal.hide();
                setTimeout(() => location.reload(), 1500);
            } else {
                const msg = data.error || `Server error ${r.status}`;
                alert(`Delete failed: ${msg}`);
                console.error('Delete failed:', r.status, data);
            }
        } catch (err) {
            console.error('Network/fetch error:', err);
            alert('Network error — check your connection and try again.');
        } finally {
            pendingSlug = null;
        }
    });

    // Reset state when modal closes
    deleteModalEl.addEventListener('hidden.bs.modal', () => {
        pendingSlug = null;
    });
}