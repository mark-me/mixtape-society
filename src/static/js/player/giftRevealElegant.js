// static/js/player/giftRevealElegant.js

/**
 * Elegant gift reveal flow
 * Shows: Initial prompt → Polaroid development → Liner notes → Redirect to player
 */

// Extract slug from current URL
const urlMatch = window.location.pathname.match(/\/play\/gift-elegant\/([^\/]+)/);
const mixtapeSlug = urlMatch ? decodeURIComponent(urlMatch[1]) : null;

if (!mixtapeSlug) {
    console.error('Could not extract mixtape slug from URL');
}

// DOM elements
const initialPrompt = document.getElementById('initial-prompt');
const polaroidContainer = document.getElementById('polaroid-container');
const polaroid = document.getElementById('polaroid');
const linerNotesContainer = document.getElementById('liner-notes-container');
const revealBtn = document.getElementById('reveal-btn');
const playButton = document.getElementById('play-button');

// Step 1: Initial prompt → Polaroid
if (revealBtn) {
    revealBtn.addEventListener('click', () => {
        if (initialPrompt) {
            initialPrompt.classList.add('fade-out');
        }
        
        setTimeout(() => {
            if (initialPrompt) initialPrompt.style.display = 'none';
            if (polaroidContainer) {
                polaroidContainer.classList.add('active');
            }
        }, 800);
    });
}

// Step 2: Polaroid → Liner notes
if (polaroid) {
    polaroid.addEventListener('click', () => {
        if (polaroidContainer) {
            polaroidContainer.classList.remove('active');
            polaroidContainer.classList.add('fade-out');
        }
        
        setTimeout(() => {
            if (polaroidContainer) polaroidContainer.style.display = 'none';
            if (linerNotesContainer) {
                linerNotesContainer.classList.add('active');
            }
        }, 800);
    });
}

// Step 3: Liner notes → Redirect to player
if (playButton) {
    playButton.addEventListener('click', () => {
        if (mixtapeSlug) {
            window.location.href = `/play/share/${encodeURIComponent(mixtapeSlug)}`;
        }
    });
}
