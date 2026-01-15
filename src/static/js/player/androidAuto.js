/**
 * Android Auto Integration Module
 * 
 * Provides Android Auto-specific functionality including:
 * - Proper Android Auto detection (not just any mobile browser)
 * - Size-optimized cover art using the new API
 * - MediaSession integration
 * - Simplified UI for in-car use
 */

class AndroidAutoIntegration {
    constructor() {
        this.isAndroidAuto = false;
        this.mediaSession = null;
        this.currentMetadata = null;
        this.baseUrl = window.location.origin;
    }

    /**
     * Detects if running in Android Auto environment.
     * Uses multiple signals to avoid false positives from regular mobile Chrome.
     * 
     * @returns {boolean} True if running in Android Auto
     */
    async detectAndroidAuto() {
        const userAgent = navigator.userAgent.toLowerCase();
        
        // Check for Android Automotive OS or Android Auto indicators
        const hasAutomotiveUA = userAgent.includes('android') && 
                               (userAgent.includes('automotive') || 
                                userAgent.includes('car'));
        
        // Check for fullscreen/standalone mode (Android Auto typically uses these)
        const isFullscreen = window.matchMedia('(display-mode: fullscreen)').matches ||
                           window.matchMedia('(display-mode: standalone)').matches;
        
        // Check for car-like display dimensions (typically wide aspect ratio)
        const hasCarDimensions = window.screen.width >= 800 && 
                                window.screen.height >= 480 &&
                                window.screen.width / window.screen.height > 1.5;
        
        // Android Auto WebView exposes specific APIs
        const hasAndroidAutoAPI = typeof window.AndroidAuto !== 'undefined';
        
        // Check if running in WebView (Android Auto uses WebView)
        const isWebView = userAgent.includes('wv');
        
        // Combine signals for reliable detection
        this.isAndroidAuto = hasAndroidAutoAPI || 
                            (hasAutomotiveUA && isFullscreen) ||
                            (isWebView && isFullscreen && hasCarDimensions);
        
        console.log('Android Auto Detection:', {
            isAndroidAuto: this.isAndroidAuto,
            hasAutomotiveUA,
            isFullscreen,
            hasCarDimensions,
            hasAndroidAutoAPI,
            isWebView,
            userAgent
        });
        
        return this.isAndroidAuto;
    }

    /**
     * Initializes Android Auto integration if detected.
     */
    async initialize() {
        const detected = await this.detectAndroidAuto();
        
        if (detected) {
            console.log('Android Auto detected - initializing...');
            this.initializeMediaSession();
            this.applyAndroidAutoStyles();
            return true;
        } else {
            console.log('Not running in Android Auto');
            return false;
        }
    }

    /**
     * Initializes MediaSession API for media controls.
     */
    initializeMediaSession() {
        if (!('mediaSession' in navigator)) {
            console.warn('MediaSession API not available');
            return;
        }

        this.mediaSession = navigator.mediaSession;
        
        // Set up action handlers
        this.mediaSession.setActionHandler('play', () => {
            this.handlePlay();
        });
        
        this.mediaSession.setActionHandler('pause', () => {
            this.handlePause();
        });
        
        this.mediaSession.setActionHandler('previoustrack', () => {
            this.handlePrevious();
        });
        
        this.mediaSession.setActionHandler('nexttrack', () => {
            this.handleNext();
        });
        
        this.mediaSession.setActionHandler('seekbackward', (details) => {
            this.handleSeekBackward(details);
        });
        
        this.mediaSession.setActionHandler('seekforward', (details) => {
            this.handleSeekForward(details);
        });
        
        this.mediaSession.setActionHandler('seekto', (details) => {
            this.handleSeekTo(details);
        });

        console.log('MediaSession initialized');
    }

    /**
     * Fetches mixtape metadata with size-optimized artwork from Flask API.
     * 
     * @param {string} mixtapeId - The mixtape identifier
     * @returns {Promise<Object>} Metadata object with size-optimized artwork
     */
    async fetchMixtapeMetadata(mixtapeId) {
        try {
            const response = await fetch(`${this.baseUrl}/api/mixtapes/${mixtapeId}/metadata`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const metadata = await response.json();
            
            // Validate artwork array exists and has proper structure
            if (!metadata.artwork || !Array.isArray(metadata.artwork)) {
                console.warn('No artwork in metadata, using fallback');
                metadata.artwork = this.getFallbackArtwork();
            }
            
            console.log('Fetched metadata:', metadata);
            return metadata;
            
        } catch (error) {
            console.error('Failed to fetch mixtape metadata:', error);
            return this.getFallbackMetadata(mixtapeId);
        }
    }

    /**
     * Prepares artwork array, preserving size-specific URLs from the backend.
     * No longer duplicates a single URL - uses the optimized variants provided.
     * 
     * @param {Array} artworkArray - Array of artwork objects from API
     * @returns {Array} Properly formatted artwork array for MediaMetadata
     */
    prepareArtwork(artworkArray) {
        if (!artworkArray || artworkArray.length === 0) {
            return this.getFallbackArtwork();
        }
        
        // Preserve the size-specific URLs from the backend
        // Each artwork object should have: src, sizes, type
        return artworkArray.map(art => ({
            src: art.src,           // Keep the size-optimized URL with ?size= parameter
            sizes: art.sizes,       // Keep the declared size (e.g., "256x256")
            type: art.type || 'image/jpeg'
        }));
    }

    /**
     * Returns fallback artwork when none is available.
     * 
     * @returns {Array} Fallback artwork array
     */
    getFallbackArtwork() {
        return [
            {
                src: `${this.baseUrl}/covers/_fallback.jpg`,
                sizes: '512x512',
                type: 'image/jpeg'
            }
        ];
    }

    /**
     * Returns fallback metadata when fetch fails.
     * 
     * @param {string} mixtapeId - The mixtape identifier
     * @returns {Object} Fallback metadata object
     */
    getFallbackMetadata(mixtapeId) {
        return {
            id: mixtapeId,
            title: 'Unknown Mixtape',
            artist: 'Unknown Artist',
            album: 'Unknown Album',
            artwork: this.getFallbackArtwork(),
            tracks: []
        };
    }

    /**
     * Updates MediaSession metadata for the currently playing mixtape/track.
     * 
     * @param {Object} metadata - Metadata object with title, artist, album, artwork
     */
    updateMediaMetadata(metadata) {
        if (!this.mediaSession) {
            console.warn('MediaSession not initialized');
            return;
        }

        try {
            // Prepare size-optimized artwork array
            const artwork = this.prepareArtwork(metadata.artwork);
            
            // Create MediaMetadata object
            this.currentMetadata = new MediaMetadata({
                title: metadata.title || 'Unknown Title',
                artist: metadata.artist || 'Unknown Artist',
                album: metadata.album || 'Unknown Album',
                artwork: artwork
            });
            
            this.mediaSession.metadata = this.currentMetadata;
            
            console.log('Updated MediaSession metadata:', {
                title: metadata.title,
                artist: metadata.artist,
                album: metadata.album,
                artworkCount: artwork.length,
                artworkSizes: artwork.map(a => a.sizes)
            });
            
        } catch (error) {
            console.error('Failed to update MediaSession metadata:', error);
        }
    }

    /**
     * Updates playback state in MediaSession.
     * 
     * @param {string} state - Playback state: 'none', 'paused', 'playing'
     * @param {Object} options - Optional position and duration
     */
    updatePlaybackState(state, options = {}) {
        if (!this.mediaSession) {
            return;
        }

        try {
            this.mediaSession.playbackState = state;
            
            if (options.position !== undefined || options.duration !== undefined) {
                this.mediaSession.setPositionState({
                    duration: options.duration || 0,
                    playbackRate: options.playbackRate || 1.0,
                    position: options.position || 0
                });
            }
            
            console.log('Updated playback state:', state, options);
            
        } catch (error) {
            console.error('Failed to update playback state:', error);
        }
    }

    /**
     * Extracts metadata from DOM elements (for non-API scenarios).
     * Preserves size-specific artwork URLs if available in data attributes.
     * 
     * @returns {Object} Metadata extracted from DOM
     */
    extractMetadataFromDOM() {
        const title = document.querySelector('[data-title]')?.textContent || 
                     document.querySelector('h1')?.textContent || 
                     'Unknown';
        
        const artist = document.querySelector('[data-artist]')?.textContent || 
                      'Unknown Artist';
        
        const album = document.querySelector('[data-album]')?.textContent || '';
        
        // Extract size-specific artwork URLs from DOM
        const artworkElements = document.querySelectorAll('[data-artwork]');
        const artwork = Array.from(artworkElements).map(el => ({
            src: el.dataset.artwork || el.src,
            sizes: el.dataset.artworkSize || '512x512',
            type: el.dataset.artworkType || 'image/jpeg'
        }));
        
        return {
            title,
            artist,
            album,
            artwork: artwork.length > 0 ? artwork : this.getFallbackArtwork()
        };
    }

    /**
     * Applies Android Auto-specific CSS styles for better in-car UX.
     */
    applyAndroidAutoStyles() {
        // Add Android Auto class to body for CSS targeting
        document.body.classList.add('android-auto-mode');
        
        // Create and inject stylesheet
        const style = document.createElement('style');
        style.textContent = `
            .android-auto-mode {
                /* Larger touch targets for in-car use */
                --touch-target-size: 60px;
                
                /* High contrast for visibility */
                --text-contrast: 1.2;
                
                /* Reduced animations for safety */
                --animation-duration: 0.2s;
            }
            
            .android-auto-mode button,
            .android-auto-mode .track-item {
                min-height: var(--touch-target-size);
                min-width: var(--touch-target-size);
                font-size: 1.2em;
            }
            
            .android-auto-mode .player-controls button {
                width: 80px;
                height: 80px;
                margin: 0 20px;
            }
            
            /* Hide complex UI elements */
            .android-auto-mode .settings-panel,
            .android-auto-mode .detailed-stats,
            .android-auto-mode .edit-controls {
                display: none !important;
            }
            
            /* Simplified layout */
            .android-auto-mode .container {
                max-width: 100%;
                padding: 20px;
            }
            
            /* Enhanced now-playing display */
            .android-auto-mode .now-playing {
                font-size: 1.5em;
                padding: 30px;
            }
            
            .android-auto-mode .album-art {
                width: 300px;
                height: 300px;
                border-radius: 8px;
            }
        `;
        
        document.head.appendChild(style);
        console.log('Applied Android Auto styles');
    }

    // Media control handlers - these should be connected to your actual player

    handlePlay() {
        console.log('Play action');
        const event = new CustomEvent('androidauto:play');
        document.dispatchEvent(event);
    }

    handlePause() {
        console.log('Pause action');
        const event = new CustomEvent('androidauto:pause');
        document.dispatchEvent(event);
    }

    handlePrevious() {
        console.log('Previous track action');
        const event = new CustomEvent('androidauto:previous');
        document.dispatchEvent(event);
    }

    handleNext() {
        console.log('Next track action');
        const event = new CustomEvent('androidauto:next');
        document.dispatchEvent(event);
    }

    handleSeekBackward(details) {
        const seekOffset = details.seekOffset || 10;
        console.log('Seek backward:', seekOffset);
        const event = new CustomEvent('androidauto:seekbackward', { 
            detail: { offset: seekOffset } 
        });
        document.dispatchEvent(event);
    }

    handleSeekForward(details) {
        const seekOffset = details.seekOffset || 10;
        console.log('Seek forward:', seekOffset);
        const event = new CustomEvent('androidauto:seekforward', { 
            detail: { offset: seekOffset } 
        });
        document.dispatchEvent(event);
    }

    handleSeekTo(details) {
        const seekTime = details.seekTime || 0;
        console.log('Seek to:', seekTime);
        const event = new CustomEvent('androidauto:seekto', { 
            detail: { time: seekTime } 
        });
        document.dispatchEvent(event);
    }
}

// Initialize when DOM is ready
let androidAuto = null;

document.addEventListener('DOMContentLoaded', async () => {
    androidAuto = new AndroidAutoIntegration();
    await androidAuto.initialize();
    
    // Make available globally for other scripts
    window.androidAuto = androidAuto;
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AndroidAutoIntegration;
}
