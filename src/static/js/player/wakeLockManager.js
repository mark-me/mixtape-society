// static/js/player/wakeLockManager.js

/**
 * Manages Screen Wake Lock to prevent app suspension during playback
 */

export class WakeLockManager {
    constructor() {
        this.wakeLock = null;
        this.isSupported = 'wakeLock' in navigator;
    }
    
    /**
     * Check if Wake Lock API is supported
     */
    isWakeLockSupported() {
        return this.isSupported;
    }
    
    /**
     * Check if wake lock is currently active
     */
    isActive() {
        return this.wakeLock !== null;
    }
    
    /**
     * Request wake lock
     */
    async acquire() {
        if (!this.isSupported) {
            console.log('⚠️ Wake Lock API not available (requires HTTPS and modern browser)');
            return false;
        }
        
        // Don't request if already have one
        if (this.wakeLock) {
            return true;
        }
        
        try {
            this.wakeLock = await navigator.wakeLock.request('screen');
            console.log('🔒 Wake lock acquired - preventing app suspension during playback');
            
            // Re-acquire if released
            this.wakeLock.addEventListener('release', () => {
                console.log('🔓 Wake lock auto-released by system');
                this.wakeLock = null;
            });
            
            return true;
        } catch (err) {
            console.warn('⚠️ Wake lock request failed:', err.name, err.message);
            return false;
        }
    }
    
    /**
     * Release wake lock
     */
    async release() {
        if (!this.wakeLock) {
            return;
        }
        
        try {
            await this.wakeLock.release();
            this.wakeLock = null;
            console.log('🔓 Wake lock released - allowing normal power management');
        } catch (err) {
            console.warn('⚠️ Wake lock release failed:', err.message);
            this.wakeLock = null; // Clear it anyway
        }
    }
}
