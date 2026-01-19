// static/js/player/giftRevealElegant.js

/**
 * Elegant gift reveal flow
 * Shows: Initial prompt → Polaroid development → Liner notes → Redirect to player
 */

console.log('Gift reveal elegant script loaded');

// Get mixtape slug from window
const mixtapeSlug = window.MIXTAPE_SLUG;
console.log('Mixtape slug:', mixtapeSlug);

// DOM elements
const initialPrompt = document.getElementById('initial-prompt');
const polaroidContainer = document.getElementById('polaroid-container');
const polaroid = document.getElementById('polaroid');
const linerNotesContainer = document.getElementById('liner-notes-container');
const revealBtn = document.getElementById('reveal-btn');
const playButton = document.getElementById('play-button');

console.log('Elements found:', {
    initialPrompt: !!initialPrompt,
    polaroidContainer: !!polaroidContainer,
    polaroid: !!polaroid,
    linerNotesContainer: !!linerNotesContainer,
    revealBtn: !!revealBtn,
    playButton: !!playButton
});

// Step 1: Initial prompt → Polaroid
if (revealBtn) {
    revealBtn.addEventListener('click', () => {
        console.log('Reveal button clicked');
        
        // Hide initial prompt with fade-out
        if (initialPrompt) {
            initialPrompt.classList.add('fade-out');
        }
        
        // After fade animation, hide and show next step
        setTimeout(() => {
            if (initialPrompt) initialPrompt.style.display = 'none';
            
            // Show polaroid container
            if (polaroidContainer) {
                polaroidContainer.classList.add('active');
            }
            
            console.log('Showing polaroid container');
        }, 800); // Match CSS transition duration
    });
}

// Step 2: Polaroid → Liner notes
if (polaroid) {
    polaroid.addEventListener('click', () => {
        console.log('Polaroid clicked');
        
        // Remove active class from polaroid
        if (polaroidContainer) {
            polaroidContainer.classList.remove('active');
            polaroidContainer.classList.add('fade-out');
        }
        
        // After fade animation, show liner notes
        setTimeout(() => {
            if (polaroidContainer) polaroidContainer.style.display = 'none';
            
            // Show liner notes
            if (linerNotesContainer) {
                linerNotesContainer.classList.add('active');
            }
            
            console.log('Showing liner notes');
        }, 800); // Match CSS transition duration
    });
}

// Step 3: Liner notes → Redirect to player
if (playButton) {
    playButton.addEventListener('click', () => {
        console.log('Play button clicked, redirecting to:', `/play/share/${encodeURIComponent(mixtapeSlug)}`);
        
        // Redirect to regular player
        window.location.href = `/play/share/${encodeURIComponent(mixtapeSlug)}`;
    });
}
