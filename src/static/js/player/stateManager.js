// static/js/player/stateManager.js

/**
 * Manages playback state persistence using localStorage
 */

export class StateManager {
    constructor(storagePrefix = 'mixtape') {
        this.storagePrefix = storagePrefix;
        
        // Storage keys
        this.STORAGE_KEY_POSITION = `${storagePrefix}_playback_position`;
        this.STORAGE_KEY_TRACK = `${storagePrefix}_current_track`;
        this.STORAGE_KEY_TIME = `${storagePrefix}_current_time`;
    }
    
    // =========================================================================
    // PLAYBACK STATE
    // =========================================================================
    
    /**
     * Save current playback state
     * @param {number} trackIndex - Current track index
     * @param {number} currentTime - Current playback time
     * @param {boolean} paused - Whether playback is paused
     * @param {string} title - Track title for logging
     */
    savePlaybackState(trackIndex, currentTime, paused, title = 'Unknown') {
        if (trackIndex < 0) {
            return;
        }
        
        if (!Number.isFinite(currentTime) || currentTime < 0) {
            return;
        }
        
        try {
            localStorage.setItem(this.STORAGE_KEY_TRACK, trackIndex.toString());
            localStorage.setItem(this.STORAGE_KEY_TIME, currentTime.toString());
            localStorage.setItem(this.STORAGE_KEY_POSITION, JSON.stringify({
                track: trackIndex,
                time: currentTime,
                title: title,
                timestamp: Date.now(),
                paused: paused
            }));
            
            console.debug(`💾 Saved state: track ${trackIndex}, time ${Math.floor(currentTime)}s, paused: ${paused}`);
        } catch (e) {
            console.warn('Failed to save playback state:', e);
        }
    }
    
    /**
     * Restore playback state
     * @returns {Object|null} Saved state or null
     */
    restorePlaybackState() {
        try {
            const savedPosition = localStorage.getItem(this.STORAGE_KEY_POSITION);
            if (savedPosition) {
                const state = JSON.parse(savedPosition);
                // Only restore if saved within last 24 hours
                if (Date.now() - state.timestamp < 24 * 60 * 60 * 1000) {
                    console.log(`📍 Resuming from track ${state.track}: "${state.title}" at ${Math.floor(state.time)}s`);
                    return state;
                }
            }
        } catch (e) {
            console.warn('Failed to restore playback state:', e);
        }
        return null;
    }
    
    /**
     * Clear saved playback state
     */
    clearPlaybackState() {
        try {
            localStorage.removeItem(this.STORAGE_KEY_TRACK);
            localStorage.removeItem(this.STORAGE_KEY_TIME);
            localStorage.removeItem(this.STORAGE_KEY_POSITION);
            console.log('🗑️ Cleared playback state');
        } catch (e) {
            console.warn('Failed to clear playback state:', e);
        }
    }
}
