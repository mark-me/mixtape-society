// static/js/player/cassettePlayer.js

/**
 * Cassette Player Module
 * Retro cassette tape player experience with spinning reels, physical controls, and sound effects
 */

export function initCassettePlayer() {
    let currentMode = localStorage.getItem('playerMode') || 'modern';
    let isPlaying = false;
    let audioContext = null;
    let analyser = null;
    let dataArray = null;
    
    // Sound effect URLs (using royalty-free button click sounds)
    const SOUNDS = {
        click: 'data:audio/wav;base64,UklGRhIAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQA=', // Simple click
        eject: 'data:audio/wav;base64,UklGRhIAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQA=' // Simple beep
    };

    /**
     * Play button click sound
     */
    function playButtonSound(type = 'click') {
        const audio = new Audio(SOUNDS[type]);
        audio.volume = 0.3;
        audio.play().catch(() => {}); // Ignore autoplay errors
    }

    /**
     * Create cassette player HTML structure
     */
    function createCassetteHTML() {
        return `
            <div id="cassette-player-container">
                <div class="cassette-deck">
                    <!-- Cassette Tape Body -->
                    <div class="cassette-body">
                        <!-- White Top Label Section -->
                        <div class="cassette-top-section">
                            <!-- Gold Label Area (Left) -->
                            <div class="cassette-gold-label">
                                <div class="cassette-gold-label-text">
                                    MIXTAPE<br>SOCIETY
                                </div>
                            </div>
                            
                            <!-- Title Area (Right) -->
                            <div class="cassette-title-area">
                                <h3 class="cassette-title" id="cassette-title">Mixtape</h3>
                                <p class="cassette-side" id="cassette-side">Side A</p>
                                <p class="cassette-track-info" id="cassette-track-info">Track 1 / 12</p>
                            </div>
                        </div>
                        
                        <!-- Transparent Window with Reels -->
                        <div class="cassette-window">
                            <div class="reel-container">
                                <div class="reel" id="left-reel">
                                    <div class="reel-spokes">
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                    </div>
                                </div>
                                <div class="tape-strip"></div>
                                <div class="reel" id="right-reel">
                                    <div class="reel-spokes">
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                        <div class="reel-spoke"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Cassette Label -->
                        <div class="cassette-label">
                            <h3 class="cassette-title" id="cassette-title">Mixtape</h3>
                            <p class="cassette-side" id="cassette-side">Side A</p>
                            <p class="cassette-track-info" id="cassette-track-info">Track 1 / 12</p>
                        </div>
                    </div>
                    
                    <!-- Control Deck -->
                    <div class="control-deck">
                        <!-- Physical Buttons -->
                        <div class="cassette-buttons">
                            <button class="cassette-btn rewind" id="cassette-rewind" title="Rewind">
                                <i class="bi bi-skip-backward-fill"></i>
                            </button>
                            <button class="cassette-btn play" id="cassette-play" title="Play">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="cassette-btn pause" id="cassette-pause" title="Pause" style="display:none;">
                                <i class="bi bi-pause-fill"></i>
                            </button>
                            <button class="cassette-btn forward" id="cassette-forward" title="Fast Forward">
                                <i class="bi bi-skip-forward-fill"></i>
                            </button>
                            <button class="cassette-btn stop" id="cassette-stop" title="Stop">
                                <i class="bi bi-stop-fill"></i>
                            </button>
                            <button class="cassette-btn eject" id="cassette-eject" title="Eject">
                                <i class="bi bi-eject-fill"></i>
                            </button>
                        </div>
                        
                        <!-- Tape Counter and Auto-Reverse -->
                        <div class="tape-counter-container">
                            <div class="tape-counter" id="tape-counter">000:00</div>
                            <div class="auto-reverse">
                                <div class="auto-reverse-indicator" id="auto-reverse-indicator"></div>
                                <span>AUTO-REVERSE</span>
                            </div>
                        </div>
                        
                        <!-- VU Meters -->
                        <div class="vu-meters">
                            <div class="vu-meter">
                                <div class="vu-meter-label">L</div>
                                <div class="vu-meter-bar">
                                    <div class="vu-meter-fill" id="vu-meter-left"></div>
                                </div>
                            </div>
                            <div class="vu-meter">
                                <div class="vu-meter-label">R</div>
                                <div class="vu-meter-bar">
                                    <div class="vu-meter-fill" id="vu-meter-right"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create view mode toggle button
     */
    function createViewToggle() {
        const toggle = document.createElement('div');
        toggle.className = 'view-mode-toggle';
        toggle.innerHTML = `
            <button class="view-mode-btn ${currentMode === 'modern' ? 'active' : ''}" data-mode="modern">
                <i class="bi bi-music-note-list me-1"></i> Modern
            </button>
            <button class="view-mode-btn ${currentMode === 'cassette' ? 'active' : ''}" data-mode="cassette">
                <i class="bi bi-cassette me-1"></i> Cassette
            </button>
        `;
        document.body.appendChild(toggle);
        
        // Add click handlers
        toggle.querySelectorAll('.view-mode-btn').forEach(btn => {
            btn.addEventListener('click', () => switchMode(btn.dataset.mode));
        });
    }

    /**
     * Switch between modern and cassette mode
     */
    function switchMode(mode) {
        currentMode = mode;
        localStorage.setItem('playerMode', mode);
        
        // Update toggle buttons
        document.querySelectorAll('.view-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        
        // Toggle visibility
        const cassetteContainer = document.getElementById('cassette-player-container');
        const modernContainer = document.getElementById('bottom-player-container');
        
        if (mode === 'cassette') {
            cassetteContainer?.classList.add('active');
            document.body.classList.add('cassette-mode');
        } else {
            cassetteContainer?.classList.remove('active');
            document.body.classList.remove('cassette-mode');
        }
    }

    /**
     * Update cassette display with current track info
     */
    function updateCassetteInfo(title, artist, album, trackNum, totalTracks) {
        document.getElementById('cassette-title').textContent = title || 'Mixtape';
        document.getElementById('cassette-track-info').textContent = 
            `${artist}${album ? ' • ' + album : ''} • Track ${trackNum} / ${totalTracks}`;
        
        // Determine side (A or B)
        const side = trackNum <= Math.ceil(totalTracks / 2) ? 'A' : 'B';
        document.getElementById('cassette-side').textContent = `Side ${side}`;
        
        // Auto-reverse indicator
        const autoReverse = document.getElementById('auto-reverse-indicator');
        if (side === 'B') {
            autoReverse.classList.add('active');
        } else {
            autoReverse.classList.remove('active');
        }
    }

    /**
     * Update tape counter display
     */
    function updateTapeCounter(currentTime, duration) {
        const minutes = Math.floor(currentTime / 60);
        const seconds = Math.floor(currentTime % 60);
        const counter = document.getElementById('tape-counter');
        if (counter) {
            counter.textContent = `${String(minutes).padStart(3, '0')}:${String(seconds).padStart(2, '0')}`;
        }
    }

    /**
     * Start/stop reel animation
     */
    function toggleReels(playing) {
        const leftReel = document.getElementById('left-reel');
        const rightReel = document.getElementById('right-reel');
        
        if (playing) {
            leftReel?.classList.add('spinning');
            rightReel?.classList.add('spinning');
        } else {
            leftReel?.classList.remove('spinning');
            rightReel?.classList.remove('spinning');
        }
    }

    /**
     * Initialize audio visualization for VU meters
     */
    function initAudioVisualization() {
        const player = document.getElementById('main-player');
        if (!player || audioContext) return;
        
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaElementSource(player);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            
            source.connect(analyser);
            analyser.connect(audioContext.destination);
            
            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);
            
            updateVUMeters();
        } catch (error) {
            console.warn('Audio visualization not available:', error);
        }
    }

    /**
     * Update VU meters based on audio levels
     */
    function updateVUMeters() {
        if (!analyser || !dataArray) return;
        
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate average level
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        const percentage = (average / 255) * 100;
        
        // Update both meters (simulating stereo)
        const leftMeter = document.getElementById('vu-meter-left');
        const rightMeter = document.getElementById('vu-meter-right');
        
        if (leftMeter) leftMeter.style.width = `${percentage}%`;
        if (rightMeter) rightMeter.style.width = `${percentage * 0.95}%`; // Slightly different for effect
        
        if (isPlaying) {
            requestAnimationFrame(updateVUMeters);
        }
    }

    /**
     * Wire up cassette controls to actual player
     */
    function initCassetteControls() {
        const player = document.getElementById('main-player');
        const playBtn = document.getElementById('cassette-play');
        const pauseBtn = document.getElementById('cassette-pause');
        const stopBtn = document.getElementById('cassette-stop');
        const rewindBtn = document.getElementById('cassette-rewind');
        const forwardBtn = document.getElementById('cassette-forward');
        const ejectBtn = document.getElementById('cassette-eject');
        
        if (!player) return;
        
        // Play button
        playBtn?.addEventListener('click', () => {
            playButtonSound('click');
            player.play();
            playBtn.style.display = 'none';
            pauseBtn.style.display = 'block';
            playBtn.classList.add('active');
            isPlaying = true;
            toggleReels(true);
            if (!audioContext) initAudioVisualization();
            updateVUMeters();
        });
        
        // Pause button
        pauseBtn?.addEventListener('click', () => {
            playButtonSound('click');
            player.pause();
            pauseBtn.style.display = 'none';
            playBtn.style.display = 'block';
            playBtn.classList.remove('active');
            isPlaying = false;
            toggleReels(false);
        });
        
        // Stop button
        stopBtn?.addEventListener('click', () => {
            playButtonSound('click');
            player.pause();
            player.currentTime = 0;
            pauseBtn.style.display = 'none';
            playBtn.style.display = 'block';
            playBtn.classList.remove('active');
            isPlaying = false;
            toggleReels(false);
            updateTapeCounter(0, player.duration);
        });
        
        // Rewind (previous track)
        rewindBtn?.addEventListener('click', () => {
            playButtonSound('click');
            document.getElementById('prev-btn-bottom')?.click();
        });
        
        // Fast forward (next track)
        forwardBtn?.addEventListener('click', () => {
            playButtonSound('click');
            document.getElementById('next-btn-bottom')?.click();
        });
        
        // Eject
        ejectBtn?.addEventListener('click', () => {
            playButtonSound('eject');
            const cassetteBody = document.querySelector('.cassette-body');
            cassetteBody?.classList.add('ejecting');
            
            // Stop playback
            player.pause();
            player.currentTime = 0;
            document.getElementById('close-bottom-player')?.click();
            
            isPlaying = false;
            toggleReels(false);
            
            setTimeout(() => {
                cassetteBody?.classList.remove('ejecting');
            }, 500);
        });
        
        // Update counter during playback
        player.addEventListener('timeupdate', () => {
            updateTapeCounter(player.currentTime, player.duration);
        });
        
        // Sync with modern player state
        player.addEventListener('play', () => {
            if (currentMode === 'cassette') {
                playBtn.style.display = 'none';
                pauseBtn.style.display = 'block';
                isPlaying = true;
                toggleReels(true);
                if (!audioContext) initAudioVisualization();
                updateVUMeters();
            }
        });
        
        player.addEventListener('pause', () => {
            if (currentMode === 'cassette') {
                pauseBtn.style.display = 'none';
                playBtn.style.display = 'block';
                isPlaying = false;
                toggleReels(false);
            }
        });
    }

    /**
     * Listen for track changes from main player
     */
    function listenForTrackChanges() {
        // Observe changes to track info in bottom player
        const observer = new MutationObserver(() => {
            const title = document.getElementById('bottom-now-title')?.textContent;
            const artistAlbum = document.getElementById('bottom-now-artist-album')?.textContent;
            
            if (title && title !== '–') {
                const [artist, album] = artistAlbum?.split(' • ') || ['', ''];
                const trackItems = document.querySelectorAll('.track-item');
                const activeIndex = Array.from(trackItems).findIndex(t => t.classList.contains('active-track'));
                
                updateCassetteInfo(
                    title,
                    artist,
                    album,
                    activeIndex + 1,
                    trackItems.length
                );
            }
        });
        
        const titleElement = document.getElementById('bottom-now-title');
        if (titleElement) {
            observer.observe(titleElement, { childList: true, characterData: true, subtree: true });
        }
    }

    /**
     * Initialize everything
     */
    function init() {
        // Create cassette HTML
        const cassetteHTML = createCassetteHTML();
        document.body.insertAdjacentHTML('beforeend', cassetteHTML);
        
        // Create view toggle
        createViewToggle();
        
        // Initialize controls
        initCassetteControls();
        
        // Listen for track changes
        listenForTrackChanges();
        
        // Apply saved mode
        switchMode(currentMode);
        
        console.log('🎵 Cassette player initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}
