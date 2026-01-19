// static/js/player/giftReveal.js

let currentStep = 0;
let hasInitializedPlayer = false;

const elements = {
    initialPrompt:   document.getElementById('initial-prompt'),
    polaroidContainer: document.getElementById('polaroid-container'),
    polaroid:        document.getElementById('polaroid'),
    linerNotesContainer: document.getElementById('liner-notes-container'),
    revealBtn:       document.getElementById('reveal-btn'),
    playButton:      document.getElementById('play-button'),
    giftContainer:   document.getElementById('gift-container'),
    playerContainer: document.getElementById('player-container'),
    backToGift:      document.getElementById('back-to-gift')
};

function initGiftReveal() {
    if (!elements.initialPrompt) return;

    const slug = getCurrentSlug();
    if (sessionStorage.getItem(`gift-revealed-${slug}`)) {
        skipToPlayer();
        return;
    }

    elements.revealBtn.addEventListener('click', handleReveal);
    elements.polaroid.addEventListener('click', handlePolaroidClick);
    elements.playButton.addEventListener('click', handlePlayClick);
    if (elements.backToGift) elements.backToGift.addEventListener('click', showGiftView);

    document.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (currentStep === 0) handleReveal();
            else if (currentStep === 1) handlePolaroidClick();
            else if (currentStep === 2) handlePlayClick();
        }
    });
}

function handleReveal() {
    if (currentStep !== 0) return;
    currentStep = 1;

    elements.initialPrompt.classList.add('fade-out');
    setTimeout(() => {
        elements.initialPrompt.classList.add('hidden');
        elements.polaroidContainer.classList.add('active');
    }, 800);
}

function handlePolaroidClick() {
    if (currentStep !== 1) return;
    currentStep = 2;

    elements.polaroidContainer.classList.remove('active');
    setTimeout(() => {
        elements.linerNotesContainer.classList.add('active');
    }, 400);
}

function handlePlayClick() {
    if (currentStep !== 2) return;
    currentStep = 3;

    sessionStorage.setItem(`gift-revealed-${getCurrentSlug()}`, 'true');

    elements.linerNotesContainer.classList.remove('active');
    setTimeout(showPlayer, 400);
}

function showPlayer() {
    elements.giftContainer.classList.add('fade-out');

    setTimeout(() => {
        elements.giftContainer.style.display = 'none';
        elements.playerContainer.classList.remove('hidden');
        elements.playerContainer.classList.add('fade-in');

        if (!hasInitializedPlayer) {
            // Your player init calls
            hasInitializedPlayer = true;
            setTimeout(() => document.getElementById('big-play-btn')?.click(), 500);
        }
    }, 600);
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
        elements.linerNotesContainer.classList.add('active');
        elements.polaroidContainer.classList.remove('active');
        currentStep = 2;
    }, 400);
}

function getCurrentSlug() {
    const match = location.pathname.match(/\/gift\/([^\/]+)/);
    return match ? match[1] : 'default';
}

document.addEventListener('DOMContentLoaded', initGiftReveal);
