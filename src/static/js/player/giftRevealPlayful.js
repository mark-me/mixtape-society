// static/js/player/giftRevealPlayful.js

/**
 * Playful gift reveal flow
 * Shows: Wrapped gift → Cover reveal → Message → Redirect to player
 */

// Extract slug from current URL
const urlMatch = window.location.pathname.match(/\/play\/gift-playful\/([^\/]+)/);
const mixtapeSlug = urlMatch ? decodeURIComponent(urlMatch[1]) : null;

if (!mixtapeSlug) {
    console.error('Could not extract mixtape slug from URL');
}

// DOM elements
const wrappedGift = document.getElementById('wrapped-gift');
const coverReveal = document.getElementById('cover-reveal');
const messageScreen = document.getElementById('message-screen');
const giftImage = document.getElementById('gift-image');
const playBtn = document.getElementById('play-btn');

// Step 1: Wrapped gift → Cover reveal
if (giftImage) {
    giftImage.addEventListener('click', () => {
        if (wrappedGift) {
            wrappedGift.classList.add('unwrapping');
        }
        
        setTimeout(() => {
            if (wrappedGift) {
                wrappedGift.classList.add('fade-out');
            }
            
            setTimeout(() => {
                if (wrappedGift) wrappedGift.style.display = 'none';
                if (coverReveal) {
                    coverReveal.classList.add('active');
                }
            }, 700);
        }, 1400);
    });
}

// Step 2: Cover → Message
if (coverReveal) {
    coverReveal.addEventListener('click', () => {
        if (coverReveal) {
            coverReveal.classList.remove('active');
            coverReveal.classList.add('fade-out');
        }
        
        setTimeout(() => {
            if (coverReveal) coverReveal.style.display = 'none';
            if (messageScreen) {
                messageScreen.classList.add('active');
            }
        }, 700);
    });
}

// Step 3: Message → Redirect to player
if (playBtn) {
    playBtn.addEventListener('click', () => {
        if (mixtapeSlug) {
            window.location.href = `/play/share/${encodeURIComponent(mixtapeSlug)}`;
        }
    });
}
