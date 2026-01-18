// static/js/player/giftReveal.js

let currentStep = 0;
let hasInitializedPlayer = false;

const elements = {
    wrappedGift:    document.getElementById('wrapped-gift'),
    giftImage:      document.getElementById('gift-image'),
    coverReveal:    document.getElementById('cover-reveal'),
    messageScreen:  document.getElementById('message-screen'),
    coverImage:     document.getElementById('cover-image'),
    playBtn:        document.getElementById('play-btn'),
    giftContainer:  document.getElementById('gift-container'),
    playerContainer: document.getElementById('player-container'),
    backToGift:     document.getElementById('back-to-gift')
};

function initGiftReveal() {
    if (!elements.wrappedGift) return;

    const slug = getCurrentSlug();
    if (sessionStorage.getItem(`gift-revealed-${slug}`)) {
        skipToPlayer();
        return;
    }

    elements.wrappedGift.addEventListener('click', handleUnwrap);
    if (elements.coverImage) {
        elements.coverImage.addEventListener('click', handleCoverClick);
    }
    if (elements.playBtn) {
        elements.playBtn.addEventListener('click', handlePlayClick);
    }
    if (elements.backToGift) {
        elements.backToGift.addEventListener('click', showGiftView);
    }

    document.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (currentStep === 0) handleUnwrap();
            else if (currentStep === 1) handleCoverClick();
            else if (currentStep === 2) handlePlayClick();
        }
    });
}

function handleUnwrap() {
    if (currentStep !== 0) return;
    currentStep = 1;

    elements.wrappedGift.classList.add('unwrapping');
    createConfetti();

    setTimeout(() => {
        elements.wrappedGift.classList.add('hidden');
        elements.coverReveal.classList.add('active');
    }, 1400);
}

function handleCoverClick() {
    if (currentStep !== 1) return;
    currentStep = 2;

    elements.coverReveal.classList.remove('active');
    setTimeout(() => {
        elements.messageScreen.classList.add('active');
    }, 350);
}

function handlePlayClick() {
    if (currentStep !== 2) return;
    currentStep = 3;

    sessionStorage.setItem(`gift-revealed-${getCurrentSlug()}`, 'true');

    elements.messageScreen.classList.remove('active');
    setTimeout(showPlayer, 350);
}

function showPlayer() {
    elements.giftContainer.classList.add('fade-out');

    setTimeout(() => {
        elements.giftContainer.style.display = 'none';
        elements.playerContainer.classList.remove('hidden');
        elements.playerContainer.classList.add('fade-in');

        if (!hasInitializedPlayer) {
            // Add calls to your player initialization functions here
            // e.g. initPlayerControls();
            // initLinerNotes();
            // initChromecast?.();
            hasInitializedPlayer = true;

            setTimeout(() => {
                document.getElementById('big-play-btn')?.click();
            }, 500);
        }
    }, 700);
}

function skipToPlayer() {
    elements.giftContainer.style.display = 'none';
    elements.playerContainer.classList.remove('hidden');
    currentStep = 3;
}

function showGiftView() {
    document.querySelector('audio')?.pause();

    elements.playerContainer.classList.add('fade-out');

    setTimeout(() => {
        elements.playerContainer.classList.add('hidden');
        elements.playerContainer.classList.remove('fade-out');

        elements.giftContainer.style.display = 'flex';
        elements.messageScreen.classList.add('active');
        elements.coverReveal.classList.remove('active');
        currentStep = 2;
    }, 450);
}

function createConfetti() {
    const colors = ['#ffd700', '#ff6b9d', '#667eea', '#764ba2', '#ffffff', '#ffcc00'];
    for (let i = 0; i < 70; i++) {
        setTimeout(() => {
            const c = document.createElement('div');
            c.className = 'confetti';
            c.style.left = Math.random() * 100 + 'vw';
            c.style.background = colors[Math.floor(Math.random() * colors.length)];
            c.style.animationDelay = Math.random() * 0.7 + 's';
            document.body.appendChild(c);
            setTimeout(() => c.remove(), 3800);
        }, i * 22);
    }
}

function getCurrentSlug() {
    const match = location.pathname.match(/\/gift\/([^\/]+)/);
    return match ? match[1] : 'default';
}

document.addEventListener('DOMContentLoaded', initGiftReveal);