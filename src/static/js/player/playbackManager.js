// static/js/player/playbackManager.js

/**
 * Manages core audio playback operations
 */

export const TIMING = {
    AUTO_SAVE_INTERVAL: 5000,
    PLAYBACK_RESUME_DELAY: 50,
};

export class PlaybackManager {
    constructor(player, qualityManager, stateManager) {
        this.player = player;
        this.qualityManager = qualityManager;
        this.stateManager = stateManager;
        
        this.currentIndex = -1;
        this.autoSaveTimer = null;
    }
    
    /**
     * Get current track index
     */
    getCurrentIndex() {
        return this.currentIndex;
    }
    
    /**
     * Set current track index
     */
    setCurrentIndex(index) {
        this.currentIndex = index;
        window.currentTrackIndex = index; // Keep global in sync
    }
    
    /**
     * Load track into player
     */
    loadTrack(index, trackPath, metadata) {
        const audioUrl = this.qualityManager.buildAudioUrl(trackPath);
        this.player.src = audioUrl;
        
        // Reset position state
        if ('mediaSession' in navigator && 'setPositionState' in navigator.mediaSession) {
            try {
                navigator.mediaSession.setPositionState();
            } catch (_e) { }
        }
        
        this.setCurrentIndex(index);
        
        return audioUrl;
    }
    
    /**
     * Play
     */
    async play() {
        if (this.player.paused) {
            return await this.player.play();
        }
    }
    
    /**
     * Pause
     */
    pause() {
        if (!this.player.paused) {
            this.player.pause();
        }
    }
    
    /**
     * Stop and clear
     */
    stop() {
        this.player.pause();
        this.player.src = '';
        this.player.load();
        this.setCurrentIndex(-1);
    }
    
    /**
     * Seek to time
     */
    seek(time) {
        if (!this.player || !Number.isFinite(time) || time < 0) {
            return;
        }
        
        if (Number.isFinite(this.player.duration) && time > this.player.duration) {
            return;
        }
        
        this.player.currentTime = time;
    }
    
    /**
     * Get current time
     */
    getCurrentTime() {
        return this.player?.currentTime || 0;
    }
    
    /**
     * Get duration
     */
    getDuration() {
        return this.player?.duration || 0;
    }
    
    /**
     * Check if playing
     */
    isPlaying() {
        return this.player && !this.player.paused;
    }
    
    /**
     * Check if player has source
     */
    hasSource() {
        return !!(this.player && this.player.src && this.player.src !== '');
    }
    
    /**
     * Start auto-save timer
     */
    startAutoSave(trackTitle) {
        if (this.autoSaveTimer) return;
        
        this.autoSaveTimer = setInterval(() => {
            this.saveCurrentState(trackTitle);
        }, TIMING.AUTO_SAVE_INTERVAL);
    }
    
    /**
     * Stop auto-save timer
     */
    stopAutoSave() {
        if (this.autoSaveTimer) {
            clearInterval(this.autoSaveTimer);
            this.autoSaveTimer = null;
        }
    }
    
    /**
     * Save current playback state
     */
    saveCurrentState(trackTitle = 'Unknown') {
        if (this.currentIndex < 0 || !this.player) {
            return;
        }
        
        this.stateManager.savePlaybackState(
            this.currentIndex,
            this.player.currentTime,
            this.player.paused,
            trackTitle
        );
    }
    
    /**
     * Seek when player is ready
     */
    seekWhenReady(targetTime) {
        if (!targetTime || targetTime <= 0) {
            return;
        }
        
        const trySeek = () => {
            if (!this.player) return;
            if (!this.player.duration || isNaN(this.player.duration)) return;
            if (targetTime > this.player.duration) return;
            if (this.player.readyState < 2) return;
            
            this.player.currentTime = targetTime;
            console.log(`⏩ Restored position: ${Math.floor(targetTime)}s`);
            
            this.player.removeEventListener('canplay', trySeek);
            this.player.removeEventListener('loadedmetadata', trySeek);
        };
        
        if (this.player.readyState >= 2) {
            trySeek();
        } else {
            this.player.addEventListener('canplay', trySeek, { once: true });
            this.player.addEventListener('loadedmetadata', trySeek, { once: true });
        }
    }
}
