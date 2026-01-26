// static/js/player/uiSyncManager.js

/**
 * Manages UI updates and synchronization
 */

export const TIMING = {
    UI_RESTORE_DELAY: 500,
    HIGHLIGHT_DURATION: 3000,
};

export class UISyncManager {
    constructor(container, trackItems, bottomTitle, bottomArtistAlbum, bottomCover) {
        this.container = container;
        this.trackItems = trackItems;
        this.bottomTitle = bottomTitle;
        this.bottomArtistAlbum = bottomArtistAlbum;
        this.bottomCover = bottomCover;
    }
    
    /**
     * Update bottom player info with track details
     */
    updateBottomPlayerInfo(track) {
        if (this.bottomTitle) {
            this.bottomTitle.textContent = track.dataset.title || 'Unknown Track';
        }
        
        if (this.bottomArtistAlbum) {
            const artist = track.dataset.artist || 'Unknown Artist';
            const album = track.dataset.album || '';
            this.bottomArtistAlbum.textContent = album ? `${artist} – ${album}` : artist;
        }
        
        const coverImg = track.querySelector('.track-cover');
        if (coverImg && this.bottomCover) {
            this.bottomCover.src = coverImg.src;
            this.bottomCover.alt = track.dataset.title || 'Album Cover';
        }
    }
    
    /**
     * Set active track
     */
    setActiveTrack(track) {
        this.trackItems.forEach(t => t.classList.remove('active'));
        if (track) {
            track.classList.add('active');
        }
    }
    
    /**
     * Scroll to current track
     */
    scrollToCurrentTrack(trackElement) {
        if (!trackElement) return;
        
        trackElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest'
        });
    }
    
    /**
     * Sync play/pause icons across all tracks
     */
    syncPlayIcons(currentIndex, isPlaying) {
        this.trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;
            
            const isCurrentTrack = idx === currentIndex;
            const shouldShowPause = isCurrentTrack && isPlaying;
            
            if (shouldShowPause) {
                icon.classList.remove('bi-play-fill');
                icon.classList.add('bi-pause-fill');
                item.classList.add('playing');
            } else {
                icon.classList.remove('bi-pause-fill');
                icon.classList.add('bi-play-fill');
                item.classList.remove('playing');
            }
        });
    }
    
    /**
     * Update UI for track change
     */
    updateUIForTrack(index) {
        if (index < 0 || index >= this.trackItems.length) return;
        
        const track = this.trackItems[index];
        
        this.updateBottomPlayerInfo(track);
        this.container.style.display = 'block';
        this.setActiveTrack(track);
        this.scrollToCurrentTrack(track);
        
        return track;
    }
    
    /**
     * Apply restored UI state with highlight
     */
    applyRestoredUIState(trackIndex) {
        if (trackIndex < 0 || trackIndex >= this.trackItems.length) {
            console.warn('⚠️ Cannot restore UI: track index out of range');
            return null;
        }
        
        const track = this.trackItems[trackIndex];
        
        this.updateBottomPlayerInfo(track);
        this.container.style.display = 'block';
        this.setActiveTrack(track);
        
        // Scroll with visual indicator
        setTimeout(() => {
            track.scrollIntoView({ behavior: 'smooth', block: 'center' });
            track.style.backgroundColor = '#fff3cd';
            setTimeout(() => {
                track.style.backgroundColor = '';
            }, TIMING.HIGHLIGHT_DURATION);
        }, TIMING.UI_RESTORE_DELAY);
        
        return track;
    }
    
    /**
     * Update progress bar and time display
     */
    updateProgress(currentTime, duration) {
        const progressBar = document.getElementById('bottom-progress-bar');
        const currentTimeEl = document.getElementById('bottom-current-time');
        const durationEl = document.getElementById('bottom-duration');
        
        if (!progressBar) return;
        
        if (duration && !isNaN(duration) && isFinite(duration)) {
            const progress = (currentTime / duration) * 100;
            progressBar.style.width = `${progress}%`;
            
            if (currentTimeEl) {
                currentTimeEl.textContent = this.formatTime(currentTime);
            }
            
            if (durationEl) {
                durationEl.textContent = this.formatTime(duration);
            }
        }
    }
    
    /**
     * Format time in mm:ss
     */
    formatTime(seconds) {
        if (!seconds || isNaN(seconds) || !isFinite(seconds)) {
            return '0:00';
        }
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    /**
     * Show/hide bottom player container
     */
    showPlayer() {
        this.container.style.display = 'block';
    }
    
    hidePlayer() {
        this.container.style.display = 'none';
    }
}
