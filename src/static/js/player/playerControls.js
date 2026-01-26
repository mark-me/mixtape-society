// static/js/player/playerControls.js
// REFACTORED VERSION 3.0 - Modular architecture

import {
    globalCastingState,
    isCasting,
    castPlay,
    castPause,
    castTogglePlayPause,
    castNext,
    castPrevious,
    castJumpToTrack,
    isCastPlaying,
    setCastControlCallbacks
} from './chromecast.js';

import {
    detectiOS,
    detectAndroid,
    logDeviceInfo,
    silenceLocalPlayer,
    enableLocalPlayer,
    clearMediaSession,
    setupLocalMediaSession,
    updateMediaSessionPosition,
    extractMetadataFromDOM
} from './playerUtils.js';

import {
    setupAndroidAutoMediaSession,
    clearAndroidAutoMediaSession,
    logAndroidAutoStatus,
    isAndroidAutoConnected
} from './androidAuto.js';

import {
    showPlaybackErrorToast,
    showSuccessToast
} from '../common/toastSystem.js';

// Refactored managers
import { QueueManager, REPEAT_MODE_LABELS, REPEAT_MODE_ICONS, REPEAT_MODE_STYLES } from './queueManager.js';
import { StateManager } from './stateManager.js';
import { WakeLockManager } from './wakeLockManager.js';
import { QualityManager, QUALITY_LEVELS } from './qualityManager.js';
import { UISyncManager } from './uiSyncManager.js';
import { AutoAdvanceManager } from './autoAdvanceManager.js';
import { PlaybackManager } from './playbackManager.js';

/**
 * Timing constants
 */
const TIMING = {
    IOS_HELP_DISMISS: 10000,
};

// Global flag to prevent duplicate iOS help setup
let iOSHelpInitialized = false;

const iOS = detectiOS();
const androidInfo = detectAndroid();

/**
 * Show iOS-specific help message for Chromecast
 */
function showiOSCastHelp() {
    if (!iOS || iOSHelpInitialized) return;
    
    iOSHelpInitialized = true;
    
    const helpHtml = `
        <div class="alert alert-info alert-dismissible fade show" role="alert" style="position: fixed; top: 70px; left: 50%; transform: translateX(-50%); z-index: 9999; max-width: 90%; width: 400px;">
            <h6 class="alert-heading">📱 Casting from iPhone</h6>
            <small>
                <strong>To cast to Chromecast:</strong><br>
                1. Install Google Home app<br>
                2. Use Chrome browser (not Safari)<br>
                3. Connect to same WiFi network<br>
                <br>
                <strong>For AirPlay (recommended):</strong><br>
                Use Safari and tap the AirPlay icon in audio controls
            </small>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const castBtn = document.getElementById('cast-button');
    
    if (castBtn) {
        castBtn.addEventListener('click', () => {
            setTimeout(() => {
                if (!isCasting()) {
                    const existingHelp = document.querySelector('.alert-info');
                    if (!existingHelp) {
                        document.body.insertAdjacentHTML('afterbegin', helpHtml);
                    }
                }
            }, 3000);
        }, { once: true });
    }
}

/**
 * Main initialization function
 */
export function initPlayerControls() {
    // Get DOM elements
    const player = document.getElementById('main-player');
    const container = document.getElementById('bottom-player-container');
    const closeBtn = document.getElementById('close-bottom-player');
    const prevBtn = document.getElementById('prev-btn-bottom');
    const nextBtn = document.getElementById('next-btn-bottom');
    const trackItems = document.querySelectorAll('.track-item');
    const bottomTitle = document.getElementById('bottom-now-title');
    const bottomArtistAlbum = document.getElementById('bottom-now-artist-album');
    const bottomCover = document.getElementById('bottom-now-cover');
    
    // Initialize managers
    const queueManager = new QueueManager(trackItems.length);
    const stateManager = new StateManager('mixtape');
    const wakeLockManager = new WakeLockManager();
    const qualityManager = new QualityManager('audioQuality');
    const uiManager = new UISyncManager(container, trackItems, bottomTitle, bottomArtistAlbum, bottomCover);
    const playbackManager = new PlaybackManager(player, qualityManager, stateManager);
    const autoAdvanceManager = new AutoAdvanceManager(player, wakeLockManager);
    
    // Casting state
    let isCurrentlyCasting = false;
    
    // Guard flag for document click listener
    let documentClickHandlerInstalled = false;
    
    // Log device capabilities
    logDeviceInfo();
    if (androidInfo) {
        logAndroidAutoStatus();
    }
    if (iOS) {
        showiOSCastHelp();
    }
    
    console.log('🎮 PlayerControls initialized (v3.0 - Refactored)');
    
    // =========================================================================
    // HELPER FUNCTIONS
    // =========================================================================
    
    const checkCastingState = () => {
        return globalCastingState || isCurrentlyCasting;
    };
    
    const onlyWhenNotCasting = (handler) => {
        return function (...args) {
            if (!checkCastingState()) {
                handler.apply(this, args);
            }
        };
    };
    
    const createCastAwareHandler = (castHandler, localHandler) => {
        return () => {
            if (checkCastingState()) {
                castHandler();
            } else {
                localHandler();
            }
        };
    };
    
    const getSafeTrackIndex = () => {
        const currentIndex = playbackManager.getCurrentIndex();
        if (trackItems.length === 0) {
            return -1;
        }
        if (currentIndex >= 0 && currentIndex < trackItems.length) {
            return currentIndex;
        }
        return 0;
    };
    
    const ensureTrackLoadedAndPlay = () => {
        const index = getSafeTrackIndex();
        if (index === -1) {
            console.warn('⚠️ No tracks available to play');
            return;
        }
        
        if (!playbackManager.hasSource()) {
            console.log('🎵 Loading track before play:', index);
            playTrack(index);
            setTimeout(() => syncPlayIcons(), 100);
        } else {
            player.play().catch(err => console.error("Resume failed:", err));
        }
    };
    
    // =========================================================================
    // MEDIA SESSION MANAGEMENT
    // =========================================================================
    
    const updateLocalMediaSession = (metadata) => {
        if (checkCastingState()) {
            console.log('⭕️ Skipping Media Session - Chromecast handles it');
            return;
        }
        
        const androidInfo = detectAndroid();
        
        if (androidInfo) {
            console.log('Using Android-optimized Media Session');
            setupAndroidAutoMediaSession(metadata, playerControlsAPI, player);
        } else if (detectiOS()) {
            console.log('Using iOS Media Session');
            setupLocalMediaSession(metadata, playerControlsAPI);
        } else {
            console.log('Using desktop Media Session');
            setupLocalMediaSession(metadata, playerControlsAPI);
        }
    };
    
    const updatePositionState = () => {
        if (checkCastingState()) return;
        updateMediaSessionPosition(
            playbackManager.getCurrentTime(),
            playbackManager.getDuration(),
            player.playbackRate
        );
    };
    
    // =========================================================================
    // PREFETCH
    // =========================================================================
    
    const prefetchNextTrack = async (currentIdx) => {
        const nextIdx = queueManager.getNextTrack(currentIdx, { skipRepeatOne: true });
        
        if (nextIdx < 0 || nextIdx >= trackItems.length || nextIdx === currentIdx) {
            console.log('🚫 No next track to prefetch');
            return;
        }
        
        const nextTrack = trackItems[nextIdx];
        if (!nextTrack) return;
        
        const audioUrl = qualityManager.buildAudioUrl(nextTrack.dataset.path);
        
        const repeatInfo = queueManager.getRepeatMode() !== 'off' ? ` (repeat: ${queueManager.getRepeatMode()})` : '';
        console.log(`🔥 Prefetching next track${repeatInfo}:`, nextTrack.dataset.title);
        
        const doPrefetch = async () => {
            try {
                if ('caches' in window) {
                    const cached = await caches.match(audioUrl);
                    if (cached) {
                        console.log('✅ Next track already cached');
                        return;
                    }
                }
                
                await fetch(audioUrl, {
                    method: 'GET',
                    credentials: 'include'
                });
                
                console.log('✅ Next track prefetch initiated');
            } catch (error) {
                console.warn('⚠️ Prefetch failed (not critical):', error.message);
            }
        };
        
        if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
            window.requestIdleCallback(() => doPrefetch());
        } else {
            setTimeout(() => doPrefetch(), 0);
        }
    };
    
    // =========================================================================
    // CORE PLAYBACK FUNCTIONS
    // =========================================================================
    
    /**
     * Play a track
     * @param {number} index - Track index
     * @param {boolean} isAutoAdvance - True if auto-advance (not user-initiated)
     */
    const playTrack = (index, isAutoAdvance = false) => {
        console.log(`🎵 playTrack(${index}), auto-advance: ${isAutoAdvance}, casting: ${checkCastingState()}`);
        
        if (checkCastingState()) {
            console.log(`📡 Routing to Chromecast`);
            castJumpToTrack(index);
            uiManager.updateUIForTrack(index);
            playbackManager.setCurrentIndex(index);
            return;
        }
        
        console.log(`📊 Playing locally`);
        
        if (index === playbackManager.getCurrentIndex() && player.src !== '') {
            player.play().catch(e => console.log('Autoplay prevented:', e));
            return;
        }
        
        if (index < 0 || index >= trackItems.length) {
            stopPlayback();
            return;
        }
        
        const track = trackItems[index];
        
        // Load track
        playbackManager.loadTrack(index, track.dataset.path, null);
        
        // Update UI
        uiManager.updateUIForTrack(index);
        
        // Update Media Session
        const metadata = extractMetadataFromDOM(track);
        updateLocalMediaSession(metadata);
        
        // Play with appropriate strategy
        if (isAutoAdvance) {
            autoAdvanceManager.attemptAutoAdvancePlay();
        } else {
            autoAdvanceManager.attemptStandardPlay();
        }
        
        // Prefetch next track
        prefetchNextTrack(index);
    };
    
    const togglePlayPause = () => {
        if (checkCastingState()) {
            castTogglePlayPause();
            return;
        }
        
        if (!playbackManager.hasSource()) {
            console.log('🎵 No source, loading track...');
            ensureTrackLoadedAndPlay();
            return;
        }
        
        if (player.paused) {
            player.play().catch(err => console.error("Play failed:", err));
        } else {
            player.pause();
        }
    };
    
    const stopPlayback = () => {
        playbackManager.stop();
        uiManager.hidePlayer();
        uiManager.setActiveTrack(null);
        
        if (isAndroidAutoConnected()) {
            clearAndroidAutoMediaSession();
        } else {
            clearMediaSession();
        }
    };
    
    const syncPlayIcons = () => {
        const isPlaying = (
            (checkCastingState() && isCastPlaying()) ||
            (!checkCastingState() && !player.paused)
        );
        uiManager.syncPlayIcons(playbackManager.getCurrentIndex(), isPlaying);
    };
    
    const updateCastVolume = (volume, muted) => {
        // Update volume slider if it exists
        const volumeSlider = document.getElementById('cast-volume-slider');
        const volumeIcon = document.getElementById('cast-volume-icon');
        const volumeValue = document.getElementById('cast-volume-value');
        
        if (volumeSlider) {
            volumeSlider.value = volume * 100;
        }
        
        if (volumeValue) {
            volumeValue.textContent = `${Math.round(volume * 100)}%`;
        }
        
        if (volumeIcon) {
            // Update volume icon based on level
            volumeIcon.className = 'bi ';
            if (muted || volume === 0) {
                volumeIcon.className += 'bi-volume-mute-fill';
            } else if (volume < 0.3) {
                volumeIcon.className += 'bi-volume-down-fill';
            } else if (volume < 0.7) {
                volumeIcon.className += 'bi-volume-up-fill';
            } else {
                volumeIcon.className += 'bi-volume-up-fill';
            }
        }
    };
    
    // =========================================================================
    // QUALITY MANAGEMENT
    // =========================================================================
    
    const initQualitySelector = () => {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        const qualityMenu = document.getElementById('quality-menu');
        
        if (!qualityBtn || !qualityMenu) return;
        
        updateQualityButtonText();
        
        qualityBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            qualityMenu.classList.toggle('show');
        });
        
        if (!documentClickHandlerInstalled) {
            document.addEventListener('click', (e) => {
                const qualityBtn = document.getElementById('quality-btn-bottom');
                const qualityMenu = document.getElementById('quality-menu');
                
                if (qualityBtn && qualityMenu &&
                    !qualityBtn.contains(e.target) &&
                    !qualityMenu.contains(e.target)) {
                    qualityMenu.classList.remove('show');
                }
            });
            documentClickHandlerInstalled = true;
        }
        
        qualityMenu.querySelectorAll('.quality-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                const newQuality = option.dataset.quality;
                
                if (newQuality !== qualityManager.getQuality()) {
                    changeQuality(newQuality);
                }
                
                qualityMenu.classList.remove('show');
            });
        });
    };
    
    const updateQualityButtonText = () => {
        const qualityBtn = document.getElementById('quality-btn-bottom');
        if (!qualityBtn) return;
        
        const qualityLabel = qualityManager.getQualityLabel();
        
        qualityBtn.textContent = '';
        const icon = document.createElement('i');
        icon.className = 'bi bi-gear-fill me-1';
        qualityBtn.appendChild(icon);
        qualityBtn.appendChild(document.createTextNode(qualityLabel));
    };
    
    const updateQualityMenuState = (quality) => {
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
    };
    
    const changeQuality = (newQuality) => {
        qualityManager.setQuality(newQuality);
        
        updateQualityButtonText();
        updateQualityMenuState(newQuality);
        
        const currentIndex = playbackManager.getCurrentIndex();
        if (currentIndex >= 0 && player.src && !checkCastingState()) {
            const wasPlaying = !player.paused;
            const {currentTime} = player;
            
            playTrack(currentIndex);
            
            if (wasPlaying) {
                player.currentTime = currentTime;
            }
        }
        
        showSuccessToast(`Quality changed to ${qualityManager.getQualityLabel(newQuality)}`);
    };
    
    // =========================================================================
    // SHUFFLE & REPEAT UI
    // =========================================================================
    
    const updateShuffleButton = () => {
        const shuffleBtn = document.getElementById('shuffle-btn-bottom');
        if (!shuffleBtn) return;
        
        if (queueManager.isShuffleEnabled()) {
            shuffleBtn.classList.remove('btn-outline-light');
            shuffleBtn.classList.add('btn-light');
            shuffleBtn.title = 'Shuffle: ON';
        } else {
            shuffleBtn.classList.remove('btn-light');
            shuffleBtn.classList.add('btn-outline-light');
            shuffleBtn.title = 'Shuffle: OFF';
        }
    };
    
    const toggleShuffle = () => {
        queueManager.toggleShuffle();
        updateShuffleButton();
    };
    
    const updateRepeatButton = () => {
        const repeatBtn = document.getElementById('repeat-btn-bottom');
        if (!repeatBtn) return;
        
        const mode = queueManager.getRepeatMode();
        
        Object.values(REPEAT_MODE_STYLES).forEach(cls => {
            repeatBtn.classList.remove(cls);
        });
        
        const styleClass = REPEAT_MODE_STYLES[mode];
        repeatBtn.classList.add(styleClass);
        
        const iconClass = REPEAT_MODE_ICONS[mode];
        repeatBtn.textContent = '';
        
        const icon = document.createElement('i');
        icon.className = iconClass;
        repeatBtn.appendChild(icon);
        
        const label = REPEAT_MODE_LABELS[mode];
        repeatBtn.title = `Repeat: ${label}`;
    };
    
    const cycleRepeatMode = () => {
        queueManager.cycleRepeatMode();
        updateRepeatButton();
    };
    
    // =========================================================================
    // PLAYER CONTROLS API
    // =========================================================================
    
    const playerControlsAPI = {
        play: () => {
            if (player.paused) {
                player.play().catch(err => console.error("Play failed:", err));
            }
        },
        pause: () => {
            if (!player.paused) {
                player.pause();
            }
        },
        next: () => {
            const nextIdx = queueManager.getNextTrack(playbackManager.getCurrentIndex());
            if (nextIdx >= 0 && nextIdx < trackItems.length) {
                playTrack(nextIdx);
            } else {
                console.log('🚗 No next track available');
            }
        },
        previous: () => {
            const prevIdx = queueManager.getPreviousTrack(playbackManager.getCurrentIndex());
            if (prevIdx >= 0 && prevIdx < trackItems.length) {
                playTrack(prevIdx);
            } else {
                console.log('🚗 No previous track available');
            }
        },
        jumpTo: (index) => {
            if (index >= 0 && index < trackItems.length) {
                playTrack(index);
            }
        },
        seek: (time) => {
            if (checkCastingState()) {
                // Would need castSeek function
                console.warn('Cast seek not implemented');
            } else {
                playbackManager.seek(time);
            }
        }
    };
    
    // =========================================================================
    // AUDIO CONTROL INTERCEPTION
    // =========================================================================
    
    const setupAudioControlInterception = () => {
        player.addEventListener('play', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                player.pause();
                castPlay();
                return false;
            }
            
            if (!playbackManager.hasSource()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                console.log('🎵 Native play button clicked - loading track first');
                ensureTrackLoadedAndPlay();
                return false;
            }
        }, true);
        
        player.addEventListener('pause', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                castPause();
            }
        });
        
        player.addEventListener('seeking', (e) => {
            if (checkCastingState()) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);
        
        player.addEventListener('loadeddata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
                player.pause();
            }
        }, true);
        
        player.addEventListener('loadedmetadata', (e) => {
            if (checkCastingState()) {
                e.stopPropagation();
            }
        }, true);
    };
    
    // =========================================================================
    // EVENT LISTENERS
    // =========================================================================
    
    const initEventListeners = () => {
        // Error handling
        let errorRetryCount = 0;
        const MAX_RETRY_ATTEMPTS = 3;
        let hasShownTerminalErrorToast = false;
        
        player?.addEventListener('error', (e) => {
            const error = player.error;
            console.error('Player error:', error);
            
            if (!error) return;
            
            // Don't show errors if we're casting - these are expected during cast transitions
            if (checkCastingState()) {
                console.log('Ignoring player error during casting');
                return;
            }
            
            if (errorRetryCount >= MAX_RETRY_ATTEMPTS) {
                if (!hasShownTerminalErrorToast) {
                    showPlaybackErrorToast(
                        'Playback failed after multiple attempts. Please check your connection or try a different quality setting.',
                        10000
                    );
                    hasShownTerminalErrorToast = true;
                }
                return;
            }
            
            const errorCode = error.code;
            let shouldRetry = false;
            let retryDelay = 1000;
            
            switch (errorCode) {
                case MediaError.MEDIA_ERR_NETWORK:
                    console.warn('Network error - will retry');
                    shouldRetry = true;
                    retryDelay = Math.min(1000 * Math.pow(2, errorRetryCount), 5000);
                    break;
                case MediaError.MEDIA_ERR_DECODE:
                    console.error('Decode error - media may be corrupted');
                    showPlaybackErrorToast('Media file appears to be corrupted. Try switching quality.');
                    break;
                case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
                    console.error('Source not supported');
                    showPlaybackErrorToast('This audio format is not supported by your browser.');
                    break;
                case MediaError.MEDIA_ERR_ABORTED:
                    console.warn('Playback aborted by user');
                    break;
                default:
                    console.error('Unknown media error:', errorCode);
                    shouldRetry = true;
                    retryDelay = 2000;
            }
            
            if (shouldRetry && playbackManager.getCurrentIndex() >= 0) {
                errorRetryCount++;
                console.log(`🔄 Retry attempt ${errorRetryCount}/${MAX_RETRY_ATTEMPTS} in ${retryDelay}ms`);
                
                setTimeout(() => {
                    const currentTime = player.currentTime || 0;
                    playTrack(playbackManager.getCurrentIndex());
                    
                    if (currentTime > 0) {
                        setTimeout(() => {
                            player.currentTime = currentTime;
                        }, 500);
                    }
                }, retryDelay);
            }
        });
        
        player?.addEventListener('stalled', () => {
            console.warn('⚠️ Playback stalled, attempting to recover...');
            const currentIndex = playbackManager.getCurrentIndex();
            const track = trackItems[currentIndex];
            playbackManager.saveCurrentState(track?.dataset.title);
        });
        
        player?.addEventListener('waiting', () => {
            console.log('⏳ Buffering...');
        });
        
        player?.addEventListener('playing', () => {
            console.log('▶️ Playback resumed');
            errorRetryCount = 0;
            hasShownTerminalErrorToast = false;
        });
        
        player?.addEventListener('canplaythrough', () => {
            console.log('✅ Track ready for uninterrupted playback');
        });
        
        // Track ended - auto-advance
        player?.addEventListener('ended', () => {
            syncPlayIcons();
            const currentIndex = playbackManager.getCurrentIndex();
            const trackElement = trackItems[currentIndex];
            const trackTitle = trackElement?.dataset.title || 'Unknown';
            console.log('✅ Track ended:', trackTitle);
            console.log('🔍 State check:', {
                currentIndex,
                totalTracks: trackItems.length,
                repeatMode: queueManager.getRepeatMode(),
                isShuffled: queueManager.isShuffleEnabled(),
                wakeLockActive: wakeLockManager.isActive(),
                isCasting: checkCastingState(),
                playerPaused: player.paused,
                playerEnded: player.ended
            });
            
            if (!checkCastingState()) {
                playbackManager.saveCurrentState(trackTitle);
                
                const nextIndex = queueManager.getNextTrack(currentIndex);
                console.log('📋 Next track calculation:', {
                    currentIndex,
                    nextIndex,
                    willAdvance: nextIndex >= 0 && nextIndex < trackItems.length
                });
                
                if (nextIndex >= 0 && nextIndex < trackItems.length) {
                    const shuffleMode = queueManager.isShuffleEnabled() ? '🔀 shuffle' : '▶️ sequential';
                    const repeatInfo = queueManager.getRepeatMode() !== 'off' ? ` (repeat: ${queueManager.getRepeatMode()})` : '';
                    const nextTrack = trackItems[nextIndex];
                    const nextTitle = nextTrack?.dataset.title || 'Unknown';
                    
                    console.log(`🎵 Auto-advancing to next track (${shuffleMode}${repeatInfo})`);
                    console.log(`   From: "${trackTitle}" (${currentIndex})`);
                    console.log(`   To: "${nextTitle}" (${nextIndex})`);
                    console.log(`   Wake lock: ${wakeLockManager.isActive() ? 'ACTIVE ✅' : 'INACTIVE ❌'}`);
                    
                    playTrack(nextIndex, true);
                } else {
                    console.log('🏁 Reached end of playlist');
                    stateManager.clearPlaybackState();
                    wakeLockManager.release();
                }
            }
        });
        
        const handleAudioProgress = onlyWhenNotCasting(() => {
            uiManager.updateProgress(playbackManager.getCurrentTime(), playbackManager.getDuration());
        });
        player?.addEventListener('timeupdate', handleAudioProgress);
        player?.addEventListener('loadedmetadata', handleAudioProgress);
        player?.addEventListener('seeked', handleAudioProgress);
        
        // Play event - start autosave and wake lock
        player?.addEventListener('play', () => {
            autoAdvanceManager.setTransitioning(false);
            
            const currentIndex = playbackManager.getCurrentIndex();
            const track = trackItems[currentIndex];
            playbackManager.startAutoSave(track?.dataset.title);
            
            wakeLockManager.acquire();
            
            // Update play/pause icons
            syncPlayIcons();
        });
        
        // Pause event - save and consider wake lock release
        player?.addEventListener('pause', () => {
            const currentIndex = playbackManager.getCurrentIndex();
            const track = trackItems[currentIndex];
            playbackManager.saveCurrentState(track?.dataset.title);
            playbackManager.stopAutoSave();
            
            if (!autoAdvanceManager.isTransitioningTracks()) {
                wakeLockManager.release();
            } else {
                console.log('⏭️ Pause during transition - keeping wake lock');
            }
            
            // Update play/pause icons
            syncPlayIcons();
        });
        
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
        
        // Button event listeners
        prevBtn?.addEventListener('click', createCastAwareHandler(
            castPrevious,
            () => {
                const prevIndex = queueManager.getPreviousTrack(playbackManager.getCurrentIndex());
                if (prevIndex >= 0) {
                    playTrack(prevIndex);
                } else {
                    console.log('⏮️ At start of playlist');
                }
            }
        ));
        
        nextBtn?.addEventListener('click', createCastAwareHandler(
            castNext,
            () => {
                const nextIndex = queueManager.getNextTrack(playbackManager.getCurrentIndex());
                if (nextIndex >= 0 && nextIndex < trackItems.length) {
                    playTrack(nextIndex);
                } else {
                    console.log('⏭️ At end of playlist');
                }
            }
        ));
        
        const shuffleBtn = document.getElementById('shuffle-btn-bottom');
        shuffleBtn?.addEventListener('click', toggleShuffle);
        
        const repeatBtn = document.getElementById('repeat-btn-bottom');
        repeatBtn?.addEventListener('click', cycleRepeatMode);
        
        closeBtn?.addEventListener('click', stopPlayback);
        
        trackItems.forEach((item, i) => {
            const overlayBtn = item.querySelector('.play-overlay-btn');
            if (!overlayBtn) return;
            
            overlayBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                if (i === playbackManager.getCurrentIndex()) {
                    togglePlayPause();
                } else {
                    playTrack(i);
                }
            });
        });
    };
    
    // =========================================================================
    // CAST LISTENERS
    // =========================================================================
    
    const initCastListeners = () => {
        setCastControlCallbacks({
            onCastStart: () => {
                console.log('🚀 Cast session started');
                isCurrentlyCasting = true;
                silenceLocalPlayer();
                clearMediaSession();
                syncPlayIcons();
            },
            onCastEnd: () => {
                console.log('🛑 Cast session ended');
                isCurrentlyCasting = false;
                enableLocalPlayer();
                
                const currentIndex = playbackManager.getCurrentIndex();
                if (currentIndex >= 0 && currentIndex < trackItems.length) {
                    const track = trackItems[currentIndex];
                    
                    // Reload track into local player
                    console.log('📱 Reloading track into local player after casting');
                    playbackManager.loadTrack(currentIndex, track.dataset.path, null);
                    
                    // Update Media Session
                    const metadata = extractMetadataFromDOM(track);
                    updateLocalMediaSession(metadata);
                    
                    // Resume playback (user was listening via cast, so continue locally)
                    player.play().catch(err => {
                        console.warn('Could not auto-resume after casting:', err);
                        // Not critical - user can manually play
                    });
                }
                
                syncPlayIcons();
            },
            onTrackChange: (newIndex) => {
                console.log(`🎵 Chromecast track changed to: ${newIndex}`);
                uiManager.updateUIForTrack(newIndex);
                playbackManager.setCurrentIndex(newIndex);
            },
            onPlayStateChange: (isPlaying) => {
                console.log(`▶️ Chromecast play state: ${isPlaying ? 'playing' : 'paused'}`);
                syncPlayIcons();
            },
            onTimeUpdate: (currentTime, duration) => {
                // Update progress bar while casting
                uiManager.updateProgress(currentTime, duration);
            },
            onVolumeChange: (volume, muted) => {
                console.log(`🔊 Cast volume: ${Math.round(volume * 100)}%${muted ? ' (muted)' : ''}`);
                updateCastVolume(volume, muted);
            }
        });
    };
    
    // =========================================================================
    // AUTO-START HANDLING
    // =========================================================================
    
    const handleAutoStart = () => {
        if (trackItems.length === 0) return;
        
        if (window.location.hash === '#play') {
            setTimeout(() => playTrack(0), 500);
        } else if (sessionStorage.getItem('startPlaybackNow')) {
            sessionStorage.removeItem('startPlaybackNow');
            playTrack(0);
        }
    };
    
    // =========================================================================
    // VISIBILITY CHANGE HANDLER
    // =========================================================================
    
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            console.log('👁️ Page hidden (app backgrounded or screen locked)');
            
            if (player && !player.paused && !checkCastingState()) {
                wakeLockManager.acquire();
                
                if ('mediaSession' in navigator) {
                    navigator.mediaSession.playbackState = 'playing';
                    console.log('📱 Reinforced Media Session state: playing');
                }
            }
        } else {
            console.log('👁️ Page visible (app foregrounded)');
        }
    });
    
    // =========================================================================
    // INITIALIZATION SEQUENCE
    // =========================================================================
    
    // 1. Initialize UI components
    initQualitySelector();
    setupAudioControlInterception();
    initCastListeners();
    initEventListeners();
    
    // 2. Restore state
    queueManager.restoreShuffleState();
    updateShuffleButton();
    
    queueManager.restoreRepeatMode();
    updateRepeatButton();
    
    // 3. Restore playback position if available
    const savedState = stateManager.restorePlaybackState();
    if (savedState && savedState.track < trackItems.length) {
        playbackManager.setCurrentIndex(savedState.track);
        
        const track = trackItems[savedState.track];
        if (!track) {
            console.warn('⚠️ Cannot restore track: index out of range');
            playbackManager.setCurrentIndex(0);
            handleAutoStart();
            return {
                playTrack,
                syncPlayIcons,
                changeQuality,
            };
        }
        
        // Apply restored UI state
        uiManager.applyRestoredUIState(savedState.track);
        
        // Load track without playing
        player.src = qualityManager.buildAudioUrl(track.dataset.path);
        player.load();
        console.log('🎵 Loaded track for restoration:', savedState.track);
        
        // Update Media Session
        const metadata = extractMetadataFromDOM(track);
        updateLocalMediaSession(metadata);
        
        // Seek on first play
        let restoredSeekTime = savedState.time;
        const handleRestoredPlay = () => {
            if (player && playbackManager.getCurrentIndex() === savedState.track && restoredSeekTime > 0) {
                playbackManager.seekWhenReady(restoredSeekTime);
                restoredSeekTime = 0;
            }
            player.removeEventListener('play', handleRestoredPlay);
        };
        player.addEventListener('play', handleRestoredPlay);
    } else {
        // No saved state - run auto-start logic
        handleAutoStart();
    }
    
    // =========================================================================
    // RETURN API
    // =========================================================================
    
    return {
        playTrack,
        syncPlayIcons,
        changeQuality,
    };
}
