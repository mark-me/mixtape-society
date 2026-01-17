// static/js/player/giftReveal.js

/**
 * Gift Reveal Module
 * Handles the interactive cassette unwrap experience for gift mixtapes
 */

import { initPlayerControls } from './playerControls.js';
import { initLinerNotes } from './linerNotes.js';
import { initChromecast, castMixtapePlaylist, stopCasting } from './chromecast.js';

// State management
let isRevealed = false;
let revealStage = 'wrapped'; // wrapped -> unwrapping -> cassette-shown -> message-shown -> playing

/**
 * Initialize the gift reveal experience
 */
export function initGiftReveal() {
    console.log('🎁 Initializing gift reveal experience');
    
    // Get DOM elements
    const giftBox = document.getElementById('gift-box');
    const giftCassette = document.getElementById('gift-cassette');
    const giftMessage = document.getElementById('gift-message');
    const giftInstruction = document.getElementById('gift-instruction');
    const giftContainer = document.getElementById('gift-container');
    const playerContainer = document.getElementById('player-container');
    const backToGiftBtn = document.getElementById('back-to-gift');
    
    if (!giftBox || !giftContainer) {
        console.error('Gift elements not found');
        return;
    }
    
    // Check if user has already seen the reveal (session storage)
    const hasSeenReveal = sessionStorage.getItem('gift-revealed-' + getCurrentSlug());
    
    if (hasSeenReveal) {
        // Skip directly to player
        skipToPlayer();
        return;
    }
    
    // Add click handler to unwrap
    giftBox.addEventListener('click', handleUnwrap);
    giftInstruction.addEventListener('click', handleUnwrap);
    
    // Add click handler to cassette (plays mixtape)
    giftCassette.addEventListener('click', handleCassetteClick);
    
    // Back to gift button
    if (backToGiftBtn) {
        backToGiftBtn.addEventListener('click', () => {
            showGiftView();
        });
    }
    
    // Add keyboard support
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            if (revealStage === 'wrapped') {
                e.preventDefault();
                handleUnwrap();
            } else if (revealStage === 'message-shown') {
                e.preventDefault();
                handleCassetteClick();
            }
        }
    });
    
    console.log('✅ Gift reveal initialized');
}

/**
 * Handle unwrapping the gift
 */
function handleUnwrap() {
    if (revealStage !== 'wrapped') return;
    
    console.log('🎀 Unwrapping gift...');
    revealStage = 'unwrapping';
    
    const giftBox = document.getElementById('gift-box');
    const giftCassette = document.getElementById('gift-cassette');
    const giftMessage = document.getElementById('gift-message');
    const giftInstruction = document.getElementById('gift-instruction');
    
    // Play unwrap sound (if we add audio)
    // playSound('unwrap');
    
    // Animate box opening
    giftBox.classList.add('opening');
    giftInstruction.classList.add('fade-out');
    
    // After box animation completes
    setTimeout(() => {
        giftBox.classList.add('hidden');
        giftCassette.classList.remove('hidden');
        giftCassette.classList.add('revealed');
        revealStage = 'cassette-shown';
        
        // Show message after cassette is visible
        setTimeout(() => {
            giftMessage.classList.remove('hidden');
            giftMessage.classList.add('fade-in');
            revealStage = 'message-shown';
            
            // Make cassette interactive
            giftCassette.classList.add('interactive');
        }, 800);
        
    }, 1000);
}

/**
 * Handle clicking the revealed cassette
 */
function handleCassetteClick() {
    if (revealStage !== 'message-shown') return;
    
    console.log('▶ Playing mixtape...');
    revealStage = 'playing';
    
    const giftCassette = document.getElementById('gift-cassette');
    
    // Animate cassette "inserting" into player
    giftCassette.classList.add('inserting');
    
    // Mark as revealed in session
    sessionStorage.setItem('gift-revealed-' + getCurrentSlug(), 'true');
    
    // Transition to player after animation
    setTimeout(() => {
        showPlayer();
    }, 800);
}

/**
 * Show the regular player interface
 */
function showPlayer() {
    const giftContainer = document.getElementById('gift-container');
    const playerContainer = document.getElementById('player-container');
    
    // Fade out gift, fade in player
    giftContainer.classList.add('fade-out');
    
    setTimeout(() => {
        giftContainer.style.display = 'none';
        playerContainer.classList.remove('hidden');
        playerContainer.classList.add('fade-in');
        
        // Initialize player controls
        initPlayerControls();
        initLinerNotes();
        initChromecast();
        
        // Set up Chromecast
        document.addEventListener('cast:ready', () => {
            const castBtn = document.getElementById('cast-button');
            if (castBtn) {
                castBtn.hidden = false;
                castBtn.addEventListener('click', () => {
                    if (castBtn.classList.contains('connected')) {
                        stopCasting();
                    } else {
                        castMixtapePlaylist();
                    }
                });
            }
        });
        
        // Auto-play first track
        setTimeout(() => {
            const bigPlayBtn = document.getElementById('big-play-btn');
            if (bigPlayBtn) {
                bigPlayBtn.click();
            }
        }, 500);
        
    }, 600);
}

/**
 * Skip directly to player (for returning users)
 */
function skipToPlayer() {
    console.log('⏩ Skipping to player (already revealed)');
    
    const giftContainer = document.getElementById('gift-container');
    const playerContainer = document.getElementById('player-container');
    
    giftContainer.style.display = 'none';
    playerContainer.classList.remove('hidden');
    
    // Initialize player
    initPlayerControls();
    initLinerNotes();
    initChromecast();
    
    document.addEventListener('cast:ready', () => {
        const castBtn = document.getElementById('cast-button');
        if (castBtn) {
            castBtn.hidden = false;
            castBtn.addEventListener('click', () => {
                if (castBtn.classList.contains('connected')) {
                    stopCasting();
                } else {
                    castMixtapePlaylist();
                }
            });
        }
    });
    
    revealStage = 'playing';
}

/**
 * Show gift view again (back button)
 */
function showGiftView() {
    const giftContainer = document.getElementById('gift-container');
    const playerContainer = document.getElementById('player-container');
    const giftMessage = document.getElementById('gift-message');
    const giftCassette = document.getElementById('gift-cassette');
    
    // Pause any playing audio
    const player = document.getElementById('main-player');
    if (player) {
        player.pause();
    }
    
    // Reset to message-shown state
    playerContainer.classList.add('fade-out');
    
    setTimeout(() => {
        playerContainer.classList.add('hidden');
        playerContainer.classList.remove('fade-out');
        
        giftContainer.style.display = 'flex';
        giftMessage.classList.remove('hidden');
        giftCassette.classList.remove('hidden');
        giftCassette.classList.add('revealed', 'interactive');
        
        revealStage = 'message-shown';
    }, 400);
}

/**
 * Get current mixtape slug from URL
 */
function getCurrentSlug() {
    const match = window.location.pathname.match(/\/gift\/([^\/]+)/);
    return match ? match[1] : 'unknown';
}

/**
 * Play sound effect (optional enhancement)
 */
function playSound(soundName) {
    // Could implement sound effects for unwrapping, etc.
    // For now, just a placeholder
    console.log(`🔊 Playing sound: ${soundName}`);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initGiftReveal();
});
