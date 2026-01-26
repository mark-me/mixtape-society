// static/js/player/queueManager.js

/**
 * Manages track queue with shuffle and repeat functionality
 */

export const REPEAT_MODES = {
    OFF: 'off',
    ALL: 'all',
    ONE: 'one'
};

export const REPEAT_MODE_LABELS = {
    [REPEAT_MODES.OFF]: 'Off',
    [REPEAT_MODES.ALL]: 'All',
    [REPEAT_MODES.ONE]: 'One'
};

export const REPEAT_MODE_ICONS = {
    [REPEAT_MODES.OFF]: 'bi-repeat',
    [REPEAT_MODES.ALL]: 'bi-repeat',
    [REPEAT_MODES.ONE]: 'bi-repeat-1'
};

export const REPEAT_MODE_STYLES = {
    [REPEAT_MODES.OFF]: 'btn-outline-light',
    [REPEAT_MODES.ALL]: 'btn-light',
    [REPEAT_MODES.ONE]: 'btn-info'
};

export class QueueManager {
    constructor(trackCount, storageKey = 'mixtape') {
        this.trackCount = trackCount;
        this.storageKey = storageKey;
        
        // Shuffle state
        this.isShuffled = false;
        this.shuffleOrder = [];
        
        // Repeat state
        this.repeatMode = REPEAT_MODES.OFF;
        
        // Storage keys
        this.STORAGE_KEY_SHUFFLE = `${storageKey}_shuffle_state`;
        this.STORAGE_KEY_REPEAT = `${storageKey}_repeat_mode`;
    }
    
    // =========================================================================
    // SHUFFLE MANAGEMENT
    // =========================================================================
    
    enableShuffle() {
        this.isShuffled = true;
        this.shuffleOrder = this._generateShuffleOrder();
        this.saveShuffleState();
        console.log('🔀 Shuffle enabled:', this.shuffleOrder);
        return this.shuffleOrder;
    }
    
    disableShuffle() {
        this.isShuffled = false;
        this.shuffleOrder = [];
        this.saveShuffleState();
        console.log('▶️ Sequential playback enabled');
    }
    
    toggleShuffle() {
        if (this.isShuffled) {
            this.disableShuffle();
        } else {
            this.enableShuffle();
        }
        return this.isShuffled;
    }
    
    _generateShuffleOrder() {
        const order = Array.from({ length: this.trackCount }, (_, i) => i);
        
        // Fisher-Yates shuffle
        for (let i = order.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [order[i], order[j]] = [order[j], order[i]];
        }
        
        return order;
    }
    
    isShuffleEnabled() {
        return this.isShuffled;
    }
    
    getShuffleOrder() {
        return [...this.shuffleOrder];
    }
    
    saveShuffleState() {
        try {
            localStorage.setItem(this.STORAGE_KEY_SHUFFLE, JSON.stringify({
                enabled: this.isShuffled,
                order: this.shuffleOrder
            }));
        } catch (error) {
            console.warn('Could not save shuffle state:', error);
        }
    }
    
    restoreShuffleState() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY_SHUFFLE);
            if (!stored) return false;
            
            const shuffleState = JSON.parse(stored);
            
            if (shuffleState.enabled &&
                shuffleState.order &&
                shuffleState.order.length === this.trackCount) {
                
                this.isShuffled = true;
                this.shuffleOrder = shuffleState.order;
                console.log('🔀 Restored shuffle mode:', this.shuffleOrder);
                return true;
            } else if (shuffleState.order && shuffleState.order.length !== this.trackCount) {
                console.log('⚠️ Shuffle order length mismatch - clearing');
                localStorage.removeItem(this.STORAGE_KEY_SHUFFLE);
            }
        } catch (error) {
            console.warn('Could not restore shuffle state:', error);
        }
        
        return false;
    }
    
    // =========================================================================
    // REPEAT MODE MANAGEMENT
    // =========================================================================
    
    cycleRepeatMode() {
        const modes = Object.values(REPEAT_MODES);
        const currentIdx = modes.indexOf(this.repeatMode);
        const nextIdx = (currentIdx + 1) % modes.length;
        this.repeatMode = modes[nextIdx];
        
        this.saveRepeatMode();
        console.log(`🔁 Repeat: ${REPEAT_MODE_LABELS[this.repeatMode]}`);
        return this.repeatMode;
    }
    
    setRepeatMode(mode) {
        if (!Object.values(REPEAT_MODES).includes(mode)) {
            console.warn('Invalid repeat mode:', mode);
            return;
        }
        this.repeatMode = this._normalizeRepeatMode(mode);
        this.saveRepeatMode();
    }
    
    getRepeatMode() {
        return this.repeatMode;
    }
    
    _normalizeRepeatMode(mode) {
        // Force OFF when 0-1 tracks
        if (this.trackCount <= 1) {
            return REPEAT_MODES.OFF;
        }
        return mode;
    }
    
    isValidRepeatMode(mode) {
        return Object.values(REPEAT_MODES).includes(mode);
    }
    
    saveRepeatMode() {
        try {
            localStorage.setItem(this.STORAGE_KEY_REPEAT, this.repeatMode);
        } catch (e) {
            console.warn('Failed to save repeat mode:', e.message);
        }
    }
    
    restoreRepeatMode() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY_REPEAT);
            if (!stored) return;
            
            if (this.isValidRepeatMode(stored)) {
                this.repeatMode = this._normalizeRepeatMode(stored);
                console.log(`🔁 Restored repeat mode: ${REPEAT_MODE_LABELS[this.repeatMode]}`);
            } else {
                console.warn('⚠️ Invalid repeat mode in storage, using default');
            }
        } catch (error) {
            console.warn('Could not restore repeat mode:', error);
        }
    }
    
    // =========================================================================
    // NAVIGATION
    // =========================================================================
    
    getNextTrack(currentIndex, options = {}) {
        const { skipRepeatOne = false } = options;
        
        // Validate
        if (this.trackCount === 0) {
            console.warn('⚠️ No tracks available');
            return -1;
        }
        
        if (currentIndex < 0 || currentIndex >= this.trackCount) {
            console.warn(`⚠️ Invalid currentIndex: ${currentIndex}, defaulting to first track`);
            currentIndex = 0;
        }
        
        // Repeat One
        if (this.repeatMode === REPEAT_MODES.ONE && !skipRepeatOne) {
            return currentIndex;
        }
        
        // Get next
        let nextIndex = this._getNextIndex(currentIndex);
        
        // Repeat All - loop
        if (nextIndex === -1 && this.repeatMode === REPEAT_MODES.ALL) {
            return this.isShuffled && this.shuffleOrder.length > 0
                ? this.shuffleOrder[0]
                : 0;
        }
        
        return nextIndex;
    }
    
    getPreviousTrack(currentIndex) {
        // Validate
        if (this.trackCount === 0) {
            console.warn('⚠️ No tracks available');
            return -1;
        }
        
        if (currentIndex < 0 || currentIndex >= this.trackCount) {
            console.warn(`⚠️ Invalid currentIndex: ${currentIndex}, defaulting to last track`);
            currentIndex = this.trackCount - 1;
        }
        
        // Repeat One
        if (this.repeatMode === REPEAT_MODES.ONE) {
            return currentIndex;
        }
        
        // Get previous
        let prevIndex = this._getPreviousIndex(currentIndex);
        
        // Repeat All - loop
        if (prevIndex === -1 && this.repeatMode === REPEAT_MODES.ALL) {
            return this.isShuffled && this.shuffleOrder.length > 0
                ? this.shuffleOrder[this.shuffleOrder.length - 1]
                : this.trackCount - 1;
        }
        
        return prevIndex;
    }
    
    _getNextIndex(currentIndex) {
        if (this.isShuffled && this.shuffleOrder.length > 0) {
            const currentPosition = this.shuffleOrder.indexOf(currentIndex);
            
            if (currentPosition === -1) {
                console.warn('⚠️ Track not in shuffle order, starting from beginning');
                return this.shuffleOrder[0];
            }
            
            const nextPosition = currentPosition + 1;
            
            if (nextPosition < this.shuffleOrder.length) {
                return this.shuffleOrder[nextPosition];
            } else {
                return -1;
            }
        } else {
            // Sequential
            const nextIndex = currentIndex + 1;
            return nextIndex < this.trackCount ? nextIndex : -1;
        }
    }
    
    _getPreviousIndex(currentIndex) {
        if (this.isShuffled && this.shuffleOrder.length > 0) {
            const currentPosition = this.shuffleOrder.indexOf(currentIndex);
            
            if (currentPosition === -1) {
                return this.shuffleOrder[this.shuffleOrder.length - 1];
            }
            
            const prevPosition = currentPosition - 1;
            
            if (prevPosition >= 0) {
                return this.shuffleOrder[prevPosition];
            } else {
                return -1;
            }
        } else {
            // Sequential
            return currentIndex - 1;
        }
    }
}
