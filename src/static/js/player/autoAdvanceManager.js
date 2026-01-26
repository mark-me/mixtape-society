// static/js/player/autoAdvanceManager.js

/**
 * Manages automatic track advancement with mobile-optimized retry logic
 */

export const AUTO_ADVANCE_TIMING = {
    RETRY_DELAY_1: 50,
    RETRY_DELAY_2: 100,
    RETRY_DELAY_3: 200,
    MAX_RETRIES: 3
};

export class AutoAdvanceManager {
    constructor(player, wakeLockManager) {
        this.player = player;
        this.wakeLockManager = wakeLockManager;
        this.isTransitioning = false;
    }
    
    /**
     * Check if currently transitioning between tracks
     */
    isTransitioningTracks() {
        return this.isTransitioning;
    }
    
    /**
     * Set transitioning flag
     */
    setTransitioning(value) {
        this.isTransitioning = value;
        if (value) {
            console.log('🔄 Track transition started');
        } else {
            console.log('✅ Track transition completed');
        }
    }
    
    /**
     * Attempt to play track with mobile auto-advance handling
     * 
     * @param {Function} onSuccess - Callback when playback starts successfully
     * @param {Function} onFailure - Callback if all attempts fail
     */
    attemptAutoAdvancePlay(onSuccess, onFailure) {
        console.log('📱 Auto-advance mode: using enhanced playback strategy');
        
        // Mark as transitioning
        this.setTransitioning(true);
        
        // Strategy 1: Immediate play attempt
        const playPromise = this.player.play();
        
        if (playPromise !== undefined) {
            playPromise
                .then(() => {
                    console.log('✅ Auto-advance play successful (immediate)');
                    this.setTransitioning(false);
                    if (onSuccess) onSuccess();
                })
                .catch(e => {
                    console.warn('⚠️ Immediate play blocked:', e.message);
                    
                    // Strategy 2: Update Media Session and retry
                    if ('mediaSession' in navigator) {
                        navigator.mediaSession.playbackState = 'playing';
                        console.log('📱 Updated Media Session state to playing');
                    }
                    
                    // Strategy 3: Multiple retry attempts with increasing delays
                    this._retryPlay(1, AUTO_ADVANCE_TIMING.RETRY_DELAY_1, onSuccess, onFailure);
                });
        } else {
            // Older browsers without promise support
            this.setTransitioning(false);
            if (onSuccess) onSuccess();
        }
    }
    
    /**
     * Retry play with exponential backoff
     * @private
     */
    _retryPlay(attemptNum, delay, onSuccess, onFailure) {
        setTimeout(() => {
            console.log(`🔄 Retry attempt ${attemptNum}`);
            
            this.player.play()
                .then(() => {
                    console.log(`✅ Auto-advance successful on attempt ${attemptNum}`);
                    this.setTransitioning(false);
                    if (onSuccess) onSuccess();
                })
                .catch(err => {
                    console.warn(`⚠️ Attempt ${attemptNum} failed:`, err.message);
                    
                    // Try up to MAX_RETRIES times with increasing delays
                    if (attemptNum < AUTO_ADVANCE_TIMING.MAX_RETRIES) {
                        this._retryPlay(attemptNum + 1, delay * 2, onSuccess, onFailure);
                    } else {
                        // Final fallback: at least ensure UI is ready
                        console.error('❌ All auto-advance attempts failed');
                        console.log('💡 User can resume via notification controls');
                        this.setTransitioning(false);
                        
                        // Keep Media Session active for user to resume
                        if ('mediaSession' in navigator) {
                            navigator.mediaSession.playbackState = 'paused';
                        }
                        
                        if (onFailure) onFailure();
                    }
                });
        }, delay);
    }
    
    /**
     * Attempt standard play (user-initiated)
     * @param {Function} onSuccess - Callback when playback starts
     * @param {Function} onFailure - Callback if play fails
     */
    attemptStandardPlay(onSuccess, onFailure) {
        this.setTransitioning(true);
        
        this.player.play()
            .then(() => {
                this.setTransitioning(false);
                if (onSuccess) onSuccess();
            })
            .catch(e => {
                console.log('Autoplay prevented:', e);
                this.setTransitioning(false);
                if (onFailure) onFailure(e);
            });
    }
}
