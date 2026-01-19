// static/js/player/giftRevealPlayful.js

/**
 * Playful gift reveal flow
 * Shows: Wrapped gift → Cover reveal → Message → Redirect to player
 */

console.log('Gift reveal playful script loaded');

// Get mixtape slug from window
const mixtapeSlug = window.MIXTAPE_SLUG;
console.log('Mixtape slug:', mixtapeSlug);

// DOM elements
const wrappedGift = document.getElementById('wrapped-gift');
const coverReveal = document.getElementById('cover-reveal');
const messageScreen = document.getElementById('message-screen');
const giftImage = document.getElementById('gift-image');
const playBtn = document.getElementById('play-btn');

console.log('Elements found:', {
    wrappedGift: !!wrappedGift,
    coverReveal: !!coverReveal,
    messageScreen: !!messageScreen,
    giftImage: !!giftImage,
    playBtn: !!playBtn
});

// Step 1: Wrapped gift → Cover reveal
if (giftImage) {
    giftImage.addEventListener('click', () => {
        console.log('Gift image clicked');
        
        // Add unwrapping animation
        if (wrappedGift) {
            wrappedGift.classList.add('unwrapping');
        }
        
        // After unwrap animation completes, show cover
        setTimeout(() => {
            if (wrappedGift) {
                wrappedGift.classList.add('fade-out');
            }
            
            setTimeout(() => {
                if (wrappedGift) wrappedGift.style.display = 'none';
                
                // Show cover
                if (coverReveal) {
                    coverReveal.classList.add('active');
                }
                
                console.log('Showing cover');
            }, 700); // Match CSS fade-out duration
        }, 1400); // Match unwrapping animation duration
    });
}

// Step 2: Cover → Message
if (coverReveal) {
    coverReveal.addEventListener('click', () => {
        console.log('Cover clicked');
        
        // Hide cover
        if (coverReveal) {
            coverReveal.classList.remove('active');
            coverReveal.classList.add('fade-out');
        }
        
        // After fade animation, show message
        setTimeout(() => {
            if (coverReveal) coverReveal.style.display = 'none';
            
            // Show message
            if (messageScreen) {
                messageScreen.classList.add('active');
            }
            
            console.log('Showing message');
        }, 700); // Match CSS fade-out duration
    });
}

// Step 3: Message → Redirect to player
if (playBtn) {
    playBtn.addEventListener('click', () => {
        console.log('Play button clicked, redirecting to:', `/play/share/${encodeURIComponent(mixtapeSlug)}`);
        
        // Redirect to regular player
        window.location.href = `/play/share/${encodeURIComponent(mixtapeSlug)}`;
    });
}
