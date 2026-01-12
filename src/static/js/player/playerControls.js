// static/js/player/playerControls.js
import { 
    isCasting, 
    castPlay, 
    castPause, 
    castTogglePlayPause,
    castNext, 
    castPrevious, 
    castJumpToTrack,
    isCastPlaying,
    setCastControlCallbacks,
    getCurrentCastMetadata,
    getCurrentCastTime
} from './chromecast.js';

/**
 * Quality settings for audio playback
 */
const QUALITY_LEVELS = {
    high: { label: 'High (256k)', bandwidth: 'high' },
    medium: { label: 'Medium (192k)', bandwidth: 'medium' },
    low: { label: 'Low (128k)', bandwidth: 'low' },
    original: { label: 'Original', bandwidth: 'highest' }
};

const DEFAULT_QUALITY = 'medium';

/**
 * Detect iOS device and version
 */
function detectiOS() {
    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    
    if (!isIOS) return null;
    
    // Extract iOS version
    const match = ua.match(/OS (\d+)_(\d+)/);
    const major = match ? parseInt(match[1], 10) : 0;
    const minor = match ? parseInt(match[2], 10) : 0;
    
    return {
        isIOS: true,
        version: major,
        versionString: `${major}.${minor}`,
        supportsMediaSession: major >= 15,
        isPWA: window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches
    };
}

const iOS = detectiOS();

/**
 * Log device and feature support
 */
function logDeviceInfo() {
    if (iOS) {
        console.log('📱 iOS Device Detected');
        console.log(`   Version: iOS ${iOS.versionString}`);
        console.log(`   PWA Mode: ${iOS.isPWA ? 'Yes' : 'No'}`);
        console.log(`   Media Session: ${iOS.supportsMediaSession ? 'Supported ✓' : 'Not Supported (need iOS 15+) ✗'}`);
    } else {
        console.log('📱 Android/Desktop Device');
    }
    
    console.log(`   Media Session API: ${'mediaSession' in navigator ? 'Available ✓' : 'Not Available ✗'}`);
    console.log(`   Cast API: ${typeof chrome !== 'undefined' && chrome.cast ? 'Available ✓' : 'Not Available ✗'}`);
}

function getMimeTypeFromUrl(url) {
    const extension = url.split('.').pop().toLowerCase();
    const mimeMap = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
    };
    return mimeMap[extension] || 'image/jpeg';
}

/**
 * Extract metadata with iOS-optimized artwork sizes
 */
function extractMetadataFromDOM(trackElement) {
    const coverImg = trackElement.querySelector('.track-cover');
    let artwork = [];

    if (coverImg && coverImg.src) {
        const mimeType = getMimeTypeFromUrl(coverImg.src);
        const absoluteSrc = new URL(coverImg.src, window.location.origin).href;
        
        // iOS prefers specific sizes, with 512x512 being most reliable
        if (iOS) {
            artwork = [
                { src: absoluteSrc, sizes: '512x512', type: mimeType }, // Primary for iOS
                { src: absoluteSrc, sizes: '256x256', type: mimeType },
                { src: absoluteSrc, sizes: '128x128', type: mimeType }
            ];
        } else {
            // Android supports more sizes
            artwork = [
                { src: absoluteSrc, sizes: '96x96',   type: mimeType },
                { src: absoluteSrc, sizes: '128x128', type: mimeType },
                { src: absoluteSrc, sizes: '192x192', type: mimeType },
                { src: absoluteSrc, sizes: '256x256', type: mimeType },
                { src: absoluteSrc, sizes: '384x384', type: mimeType },
                { src: absoluteSrc, sizes: '512x512', type: mimeType }
            ];
        }
    }

    return {
        title: trackElement.dataset.title || 'Unknown',
        artist: trackElement.dataset.artist || 'Unknown Artist',
        album: trackElement.dataset.album || '',
        artwork: artwork
    };
}

function extractMetadataFromCast() {
    const castMetadata = getCurrentCastMetadata();
    
    if (!castMetadata) {
        return null;
    }

    // Convert cast artwork format to MediaMetadata format
    const artwork = castMetadata.artwork.map(img => ({
        src: img.url,
        sizes: '512x512',
        type: 'image/png'
    }));

    return {
        title: castMetadata.title,
        artist: castMetadata.artist,
        album: castMetadata.album,
        artwork: artwork
    };
}

/**
 * Show iOS-specific help message if Chromecast isn't working
 */
function showiOSCastHelp() {
    if (!iOS) return;
    
    const helpHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert" style="position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; max-width: 90%; width: 400px;">
            <h6 class="alert-heading">📱 Casting from iPhone</h6>
            <small>
                <strong>To cast to Chromecast:</strong><br>
                1. Install Google Home app<br>
                2. Use Chrome browser (not Safari)<br>
                3. Connect to same WiFi network<br>
                <br>
                <strong>For best experience:</strong><br>
                Add this page to your Home Screen (PWA mode)
            </small>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Show help after 3 seconds if cast button is clicked but no devices found
    let castButtonClicked = false;
    const castBtn = document.getElementById('cast-button');
    
    if (castBtn) {
        castBtn.addEventListener('click', () => {
            castButtonClicked = true;
            
            setTimeout(() => {
                // If still no session, show help
                if (castButtonClicked && !isCasting()) {
                    const existingHelp = document.querySelector('.alert-info');
                    if (!existingHelp) {
                        document.body.insertAdjacentHTML('afterbegin', helpHtml);
                    }
                }
            }, 3000);
        });
    }
}

export function initPlayerControls() {
    const player = document.getElementById('main-player');
    const container = document.getElementById('bottom-player-container');
    const closeBtn = document.getElementById('close-bottom-player');
    const prevBtn = document.getElementById('prev-btn-bottom');
    const nextBtn = document.getElementById('next-btn-bottom');
    const trackItems = document.querySelectorAll('.track-item');
    const bottomTitle = document.getElementById('bottom-now-title');
    const bottomArtistAlbum = document.getElementById('bottom-now-artist-album');

    let currentIndex = -1;
    window.currentTrackIndex = currentIndex;
    let currentQuality = localStorage.getItem('audioQuality') || DEFAULT_QUALITY;
    let isCurrentlyCasting = false;

    // Log device info on initialization
    logDeviceInfo();
    
    // Show iOS cast help if needed
    if (iOS) {
        showiOSCastHelp();
    }

    function onlyWhenNotCasting(handler) {
        return function(...args) {
            if (!isCurrentlyCasting) {
                handler.apply(this, args);
            }
        };
    }

    /**
     * CRITICAL: Silence local player but keep Media Session for cast controls
     */
    function silenceLocalPlayer() {
        if (!player) return;
        
        console.log('🔇 Silencing local player (keeping Media Session for cast)');
        player.pause();
        player.src = '';
        player.load();
        
        // Remove controls to prevent duplicate UI
        player.removeAttribute('controls');
    }

    /**
     * Setup Media Session for Chromecast control
     * iOS-optimized with proper error handling
     */
    function setupCastMediaSession(metadata) {
        if (!('mediaSession' in navigator)) {
            console.warn('⚠️ Media Session API not available');
            return;
        }
        
        try {
            console.log('🎵 Setting up Media Session for Chromecast', metadata);
            
            // Set metadata with artwork
            navigator.mediaSession.metadata = new MediaMetadata({
                title: metadata.title,
                artist: metadata.artist,
                album: metadata.album,
                artwork: metadata.artwork
            });
            
            // Set playback state
            navigator.mediaSession.playbackState = 'playing';
            
            // Set action handlers to control Chromecast
            navigator.mediaSession.setActionHandler('play', () => {
                console.log('Media Session: play');
                castPlay();
            });

            navigator.mediaSession.setActionHandler('pause', () => {
                console.log('Media Session: pause');
                castPause();
            });

            navigator.mediaSession.setActionHandler('previoustrack', () => {
                console.log('Media Session: previous');
                castPrevious();
            });

            navigator.mediaSession.setActionHandler('nexttrack', () => {
                console.log('Media Session: next');
                castNext();
            });
            
            // iOS: Try to set seekbackward/seekforward (may not be supported)
            if (iOS && iOS.version >= 15) {
                try {
                    navigator.mediaSession.setActionHandler('seekbackward', () => {
                        console.log('Media Session: seek backward');
                        castPrevious();
                    });
                    
                    navigator.mediaSession.setActionHandler('seekforward', () => {
                        console.log('Media Session: seek forward');
                        castNext();
                    });
                } catch (e) {
                    console.debug('iOS seek actions not supported:', e);
                }
            }
            
            // Update position state
            updateCastPositionState();
            
            if (iOS) {
                console.log('✅ Media Session configured for iOS');
            }
        } catch (error) {
            console.error('❌ Failed to setup Media Session:', error);
        }
    }

    /**
     * Re-enable local player after casting ends
     */
    function enableLocalPlayer() {
        if (!player) return;
        
        console.log('🔊 Re-enabling local player');
        player.setAttribute('controls', '');
        
        // Clear Media Session when casting ends
        if ('mediaSession' in navigator) {
            try {
                navigator.mediaSession.metadata = null;
                navigator.mediaSession.playbackState = 'none';
            } catch (e) {
                console.warn('Error clearing Media Session:', e);
            }
        }
    }

    function setupAudioControlInterception() {
        player.addEventListener('play', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
                e.stopPropagation();
                player.pause();
                castPlay();
                return false;
            }
        }, true);

        player.addEventListener('pause', (e) => {
            if (isCurrentlyCasting) {
                e.stopPropagation();
                castPause();
            }
        });

        player.addEventListener('seeking', (e) => {
            if (isCurrentlyCasting) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);
    }

    function initQualitySelector() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');

        if (!qualityBtn || !qualityMenu) return;

        updateQualityButtonText();

        qualityBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            qualityMenu.classList.toggle('show');
        });

        document.addEventListener('click', (e) => {
            if (!qualityBtn.contains(e.target) && !qualityMenu.contains(e.target)) {
                qualityMenu.classList.remove('show');
            }
        });

        qualityMenu.querySelectorAll('.quality-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                const newQuality = option.dataset.quality;

                if (newQuality !== currentQuality) {
                    changeQuality(newQuality);
                }

                qualityMenu.classList.remove('show');
            });
        });
    }

    function updateQualityButtonText() {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;

        const qualityLabel = QUALITY_LEVELS[currentQuality]?.label || 'Medium';
        qualityBtn.innerHTML = `<i class="bi bi-gear-fill me-1"></i>${qualityLabel}`;
    }

    function updateQualityMenuState(quality) {
        document.querySelectorAll('.quality-option').forEach(opt => {
            const checkIcon = opt.querySelector('.bi-check2');
            if (opt.dataset.quality === quality) {
                opt.classList.add('active');
                if (checkIcon) checkIcon.style.display = 'inline';
            } else {
                opt.classList.remove('active');
                if (checkIcon) checkIcon.style.display = 'none';
            }
        });
    }

    function changeQuality(newQuality) {
        currentQuality = newQuality;
        localStorage.setItem('audioQuality', newQuality);

        updateQualityButtonText();
        updateQualityMenuState(newQuality);

        if (currentIndex >= 0 && player.src && !isCurrentlyCasting) {
            const wasPlaying = !player.paused;
            const currentTime = player.currentTime;

            playTrack(currentIndex);

            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }

        showQualityToast(newQuality);
    }

    function showQualityToast(quality) {
        const toastEl = document.getElementById('qualityToast');
        if (!toastEl) return;

        const toastBody = toastEl.querySelector('.toast-body');
        const qualityInfo = QUALITY_LEVELS[quality];

        if (toastBody && qualityInfo) {
            toastBody.textContent = `Quality changed to ${qualityInfo.label}`;
        }

        const toast = new bootstrap.Toast(toastEl, { delay: 2000 });
        toast.show();
    }

    function updateMediaSession(metadata) {
        if (!('mediaSession' in navigator)) return;
        if (isCurrentlyCasting) return; // Don't update when casting (handled separately)

        try {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: metadata.title,
                artist: metadata.artist,
                album: metadata.album,
                artwork: metadata.artwork
            });

            navigator.mediaSession.setActionHandler('play', () => {
                player.play().catch(e => console.log('Media Session play failed:', e));
            });

            navigator.mediaSession.setActionHandler('pause', () => {
                player.pause();
            });

            navigator.mediaSession.setActionHandler('previoustrack', () => {
                playTrack(currentIndex - 1);
            });

            navigator.mediaSession.setActionHandler('nexttrack', () => {
                playTrack(currentIndex + 1);
            });

            updatePositionState();
        } catch (error) {
            console.warn('Error updating Media Session:', error);
        }
    }

    function updatePositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
        if (isCurrentlyCasting) return;

        if (player.duration && !isNaN(player.duration) && isFinite(player.duration)) {
            try {
                navigator.mediaSession.setPositionState({
                    duration: player.duration,
                    playbackRate: player.playbackRate || 1.0,
                    position: Math.min(player.currentTime, player.duration)
                });
            } catch (error) {
                console.debug('Could not set position state:', error);
            }
        }
    }

    function updateCastPositionState() {
        if (!('mediaSession' in navigator) || !('setPositionState' in navigator.mediaSession)) return;
        if (!isCurrentlyCasting) return;

        const timeInfo = getCurrentCastTime();
        
        if (timeInfo.duration && !isNaN(timeInfo.duration) && isFinite(timeInfo.duration) && timeInfo.duration > 0) {
            try {
                navigator.mediaSession.setPositionState({
                    duration: timeInfo.duration,
                    playbackRate: 1.0,
                    position: Math.min(timeInfo.currentTime, timeInfo.duration)
                });
            } catch (error) {
                console.debug('Could not set cast position state:', error);
            }
        }
    }

    function buildAudioUrl(basePath, quality) {
        const urlParams = new URLSearchParams();
        urlParams.set('quality', quality);
        return `${basePath}?${urlParams.toString()}`;
    }

    /**
     * CRITICAL: playTrack must check casting state FIRST
     */
    function playTrack(index) {
        console.log(`🎵 playTrack called with index: ${index}, casting: ${isCurrentlyCasting}`);
        
        // CRITICAL: Route to Chromecast if currently casting
        if (isCurrentlyCasting) {
            console.log(`📡 Routing track ${index} to Chromecast`);
            castJumpToTrack(index);
            updateUIForTrack(index);
            
            // Update Media Session with cast metadata after a brief delay
            // iOS needs a bit more time for metadata to propagate
            const delay = iOS ? 800 : 500;
            setTimeout(() => {
                const metadata = extractMetadataFromCast();
                if (metadata) {
                    setupCastMediaSession(metadata);
                }
            }, delay);
            return;
        }

        // Local playback
        if (index === currentIndex && player.src !== '') {
            player.play().catch(e => console.log('Autoplay prevented:', e));
            return;
        }

        if (index < 0 || index >= trackItems.length) {
            stopPlayback();
            return;
        }

        const track = trackItems[index];

        player.src = buildAudioUrl(track.dataset.path, currentQuality);
        if ('mediaSession' in navigator && 'setPositionState' in navigator.mediaSession) {
            try {
                navigator.mediaSession.setPositionState();
            } catch (e) {}
        }

        updateUIForTrack(index);

        const metadata = extractMetadataFromDOM(track);
        updateMediaSession(metadata);

        player.play().catch(e => console.log('Autoplay prevented:', e));
    }

    function updateUIForTrack(index) {
        if (index < 0 || index >= trackItems.length) return;

        const track = trackItems[index];
        
        bottomTitle.textContent = track.dataset.title;
        bottomArtistAlbum.textContent = `${track.dataset.artist} • ${track.dataset.album}`;
        container.style.display = 'block';

        trackItems.forEach(t => t.classList.remove('active-track'));
        track.classList.add('active-track');

        currentIndex = index;
        window.currentTrackIndex = index;
    }

    function stopPlayback() {
        player.pause();
        player.src = '';
        player.load();
        container.style.display = 'none';
        trackItems.forEach(t => t.classList.remove('active-track'));
        currentIndex = -1;
        
        if ('mediaSession' in navigator) {
            try {
                navigator.mediaSession.metadata = null;
            } catch (e) {}
        }
    }

    function syncPlayIcons() {
        trackItems.forEach((item, idx) => {
            const icon = item.querySelector('.play-overlay-btn i');
            if (!icon) return;

            const isCurrentTrack = idx === currentIndex;
            const isPlaying = isCurrentTrack && (
                (isCurrentlyCasting && isCastPlaying()) || 
                (!isCurrentlyCasting && !player.paused)
            );

            if (isPlaying) {
                icon.classList.remove('bi-play-fill');
                icon.classList.add('bi-pause-fill');
            } else {
                icon.classList.remove('bi-pause-fill');
                icon.classList.add('bi-play-fill');
            }

            if (isPlaying) {
                item.classList.add('playing');
            } else {
                item.classList.remove('playing');
            }
        });
    }

    function togglePlayPause() {
        if (isCurrentlyCasting) {
            castTogglePlayPause();
        } else {
            if (player.paused) {
                player.play().catch(err => console.error("Resume failed:", err));
            } else {
                player.pause();
            }
        }
    }

    function updateAudioProgress() {
        if (!player.duration || isNaN(player.duration)) return;

        const progress = (player.currentTime / player.duration) * 100;
        player.style.setProperty('--audio-progress', `${progress}%`);
    }

    function initCastListeners() {
        document.addEventListener('cast:started', () => {
            isCurrentlyCasting = true;
            console.log('🎵 Casting started');
            
            silenceLocalPlayer();
            syncPlayIcons();
            
            // Setup initial Media Session for the first track
            if (currentIndex >= 0 && currentIndex < trackItems.length) {
                const track = trackItems[currentIndex];
                const metadata = extractMetadataFromDOM(track);
                setupCastMediaSession(metadata);
            }
        });

        document.addEventListener('cast:ended', () => {
            isCurrentlyCasting = false;
            console.log('🎵 Casting ended');
            
            enableLocalPlayer();
            syncPlayIcons();
        });

        setCastControlCallbacks({
            onTrackChange: (index) => {
                console.log(`📻 Cast track changed to index: ${index}`);
                updateUIForTrack(index);
                
                // Update Media Session with new track metadata
                const metadata = extractMetadataFromCast();
                if (metadata) {
                    setupCastMediaSession(metadata);
                }
            },
            onPlayStateChange: (state) => {
                console.log(`Cast play state: ${state}`);
                syncPlayIcons();
                
                // Update playback state in Media Session
                if ('mediaSession' in navigator) {
                    try {
                        navigator.mediaSession.playbackState = 
                            state === 'PLAYING' ? 'playing' : 
                            state === 'PAUSED' ? 'paused' : 'none';
                    } catch (e) {
                        console.warn('Error updating playback state:', e);
                    }
                }
            },
            onTimeUpdate: (time) => {
                updateCastPositionState();
            }
        });
    }

    function initEventListeners() {
        document.getElementById('big-play-btn')?.addEventListener('click', () => {
            if (trackItems.length === 0) return;
            if (currentIndex === -1) {
                playTrack(0);
            } else if (isCurrentlyCasting) {
                castPlay();
            } else {
                player.play();
            }
        });

        player?.addEventListener('play', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));
        
        player?.addEventListener('pause', onlyWhenNotCasting(() => {
            syncPlayIcons();
        }));
        
        player?.addEventListener('ended', () => {
            syncPlayIcons();
            if (!isCurrentlyCasting) {
                playTrack(currentIndex + 1);
            }
        });

        const handleAudioProgress = onlyWhenNotCasting(updateAudioProgress);
        player?.addEventListener('timeupdate', handleAudioProgress);
        player?.addEventListener('loadedmetadata', handleAudioProgress);
        player?.addEventListener('seeked', handleAudioProgress);

        const handlePositionUpdate = onlyWhenNotCasting(updatePositionState);
        player?.addEventListener('loadedmetadata', handlePositionUpdate);
        player?.addEventListener('play', handlePositionUpdate);
        player?.addEventListener('pause', handlePositionUpdate);
        player?.addEventListener('ratechange', handlePositionUpdate);
        player?.addEventListener('seeked', handlePositionUpdate);

        let lastPositionUpdate = 0;
        player?.addEventListener('timeupdate', onlyWhenNotCasting(() => {
            const now = Date.now();
            if (now - lastPositionUpdate >= 1000) {
                updatePositionState();
                lastPositionUpdate = now;
            }
        }));

        prevBtn?.addEventListener('click', () => {
            if (isCurrentlyCasting) {
                castPrevious();
            } else {
                playTrack(currentIndex - 1);
            }
        });

        nextBtn?.addEventListener('click', () => {
            if (isCurrentlyCasting) {
                castNext();
            } else {
                playTrack(currentIndex + 1);
            }
        });

        closeBtn?.addEventListener('click', stopPlayback);

        // Track item click handlers
        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;

            overlayBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                console.log(`🖱️ Track ${i} button clicked, casting: ${isCurrentlyCasting}`);
                
                if (i === currentIndex) {
                    togglePlayPause();
                } else {
                    playTrack(i);
                }
            });
        });
    }

    function handleAutoStart() {
        if (trackItems.length === 0) return;

        if (window.location.hash === '#play') {
            setTimeout(() => playTrack(0), 500);
        } else if (sessionStorage.getItem('startPlaybackNow')) {
            sessionStorage.removeItem('startPlaybackNow');
            playTrack(0);
        }
    }

    // Initialize
    initQualitySelector();
    setupAudioControlInterception();
    initCastListeners();
    initEventListeners();
    handleAutoStart();

    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
