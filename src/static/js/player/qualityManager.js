// static/js/player/qualityManager.js

/**
 * Manages audio quality selection and switching
 */

export const QUALITY_LEVELS = {
    high: { label: 'High (256k)', bandwidth: 'high' },
    medium: { label: 'Medium (192k)', bandwidth: 'medium' },
    low: { label: 'Low (128k)', bandwidth: 'low' },
    original: { label: 'Original', bandwidth: 'highest' }
};

export const DEFAULT_QUALITY = 'medium';

export class QualityManager {
    constructor(storageKey = 'audioQuality') {
        this.storageKey = storageKey;
        this.currentQuality = DEFAULT_QUALITY;
        this.restoreQuality();
    }
    
    /**
     * Get current quality setting
     */
    getQuality() {
        return this.currentQuality;
    }
    
    /**
     * Set quality
     */
    setQuality(quality) {
        if (!QUALITY_LEVELS[quality]) {
            console.warn('Invalid quality level:', quality);
            return false;
        }
        
        this.currentQuality = quality;
        this.saveQuality();
        return true;
    }
    
    /**
     * Get quality levels
     */
    getQualityLevels() {
        return QUALITY_LEVELS;
    }
    
    /**
     * Get quality label
     */
    getQualityLabel(quality = null) {
        const q = quality || this.currentQuality;
        return QUALITY_LEVELS[q]?.label || 'Medium';
    }
    
    /**
     * Build audio URL with quality parameter
     */
    buildAudioUrl(basePath, quality = null) {
        const q = quality || this.currentQuality;
        const urlParams = new URLSearchParams();
        urlParams.set('quality', q);
        return `${basePath}?${urlParams.toString()}`;
    }
    
    /**
     * Save quality preference
     */
    saveQuality() {
        try {
            localStorage.setItem(this.storageKey, this.currentQuality);
        } catch (e) {
            console.warn('Failed to save audio quality preference:', e.message);
        }
    }
    
    /**
     * Restore quality preference
     */
    restoreQuality() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored && QUALITY_LEVELS[stored]) {
                this.currentQuality = stored;
            }
        } catch (e) {
            console.warn('Failed to load audio quality from storage, using default:', e.message);
        }
    }
}
