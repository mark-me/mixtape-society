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
                    <!-- Left Side Panel (for Walkman mode) -->
                    <div class="side-panel side-panel-left">
                        <div class="screw"></div>
                        <div class="vertical-branding">MIXTAPE</div>
                        <div class="panel-spacer"></div>
                        <div class="status-indicator">
                            <div class="status-light" id="status-play"></div>
                            <div class="status-label">PLAY</div>
                        </div>
                        <div class="status-indicator">
                            <div class="status-light" id="status-rec"></div>
                            <div class="status-label">REC</div>
                        </div>
                        <div class="panel-spacer"></div>
                        <!-- Mode toggle button -->
                        <button class="panel-mode-toggle" id="panel-mode-toggle" title="Switch to Modern Mode">
                            <i class="bi bi-list"></i>
                        </button>
                        <div class="screw"></div>
                    </div>

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
                            <div class="tape-mechanism">
                                <!-- Layer 1: Silver background rectangle -->
                                <div class="tape-background"></div>

                                <!-- Layer 2: Tape strips (connecting lines) -->
                                <div class="tape-strips">
                                    <svg viewBox="0 0 512 324.62" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                                        <!-- Tape coming INTO left cog from bottom -->
                                        <path d="M 93.509 125.6l-61.144 103.99c-2.527-1.587-4.254-4.343-4.419-7.505l58.997-100.34z" fill="#3a2a1a"/>

                                        <!-- Tape going OUT from right cog -->
                                        <polygon points="465.86,231.07 457.02,231.07 397,80.39 403.57,81.53" fill="#3a2a1a"/>
                                    </svg>
                                </div>

                                <!-- Layer 3: Reels with white gear patterns -->
                                <div class="reel-container">
                                    <!-- LEFT REEL (dark circle + white teeth) -->
                                    <div class="reel spinning" id="left-reel">
                                        <svg viewBox="249 58 202 202" xmlns="http://www.w3.org/2000/svg">
                                            <!-- Dark gray circle base (same as right reel) -->
                                            <circle cx="350.75" cy="159.48" r="120.532" fill="#504f4f"/>

                                            <!-- White gear teeth pattern - wrapped for proper rotation -->
                                            <g class="gear-rotation">
                                                <g fill="#ffffff" transform="scale(1.25)" transform-origin="350.75 159.48">
                                                <path d="m318.02 180.14s0.428 0.627 1.179 1.726c0.188 0.274 0.395 0.578 0.622 0.909 0.239 0.321 0.53 0.644 0.824 1.002 0.611 0.695 1.229 1.545 2.037 2.349 3.093 3.344 8.07 7.05 13.739 9.286 1.381 0.645 2.872 0.986 4.293 1.451 1.441 0.398 2.901 0.629 4.294 0.918 1.418 0.13 2.786 0.326 4.09 0.38 1.306-6e-3 2.543 0.034 3.68-0.014 1.134-0.111 2.174-0.212 3.096-0.301 0.924-0.079 1.704-0.311 2.359-0.419 1.303-0.263 2.048-0.412 2.048-0.412l1.572 6.191s-0.866 0.177-2.381 0.487c-0.762 0.129-1.671 0.384-2.746 0.483-1.074 0.104-2.286 0.221-3.609 0.35-1.326 0.057-2.769 0.021-4.292 0.018-1.52-0.063-3.117-0.281-4.769-0.445-1.626-0.324-3.327-0.604-5.006-1.067-1.659-0.529-3.389-0.95-5.002-1.688-6.603-2.602-12.391-6.921-15.997-10.816-0.937-0.941-1.669-1.923-2.377-2.737-0.341-0.418-0.677-0.797-0.955-1.171-0.266-0.384-0.51-0.738-0.73-1.057-0.873-1.282-1.372-2.015-1.372-2.015z"/>
                                                <path d="m345.44 189.6s0.198 0.042 0.544 0.115c0.347 0.071 0.854 0.089 1.456 0.159 0.604 0.04 1.303 0.183 2.061 0.178 0.758 3e-3 1.566 5e-3 2.373 8e-3 0.808-0.023 1.611-0.153 2.366-0.208 0.377-0.042 0.745-0.051 1.088-0.113 0.341-0.071 0.664-0.138 0.962-0.201 1.195-0.234 1.992-0.391 1.992-0.391l2.781 10.954s-1.085 0.22-2.713 0.55c-0.408 0.08-0.848 0.168-1.315 0.26-0.469 0.08-0.972 0.108-1.488 0.166-1.035 0.088-2.136 0.242-3.243 0.276-1.109-3e-3 -2.218-6e-3 -3.258-9e-3 -1.04-6e-3 -2.002-0.171-2.831-0.236-0.826-0.094-1.52-0.139-1.996-0.231-0.476-0.095-0.748-0.149-0.748-0.149z"/>
                                                <path d="m321.02 134.75s-0.478 0.591-1.314 1.625c-0.409 0.524-0.825 1.219-1.345 1.984-0.255 0.386-0.527 0.798-0.813 1.231-0.263 0.447-0.507 0.937-0.779 1.438-2.215 3.973-4.246 9.834-4.637 15.921-0.475 6.09 0.874 12.157 2.497 16.396 0.444 1.05 0.851 2.012 1.212 2.865 0.411 0.829 0.822 1.526 1.134 2.113 0.319 0.583 0.57 1.042 0.742 1.354 0.197 0.296 0.302 0.455 0.302 0.455l-5.403 3.407s-0.122-0.185-0.35-0.532c-0.201-0.364-0.496-0.897-0.871-1.576-0.366-0.683-0.839-1.5-1.316-2.467-0.421-0.993-0.896-2.115-1.415-3.338-1.895-4.932-3.452-11.985-2.904-19.095 0.45-7.102 2.821-13.93 5.399-18.554 0.316-0.583 0.605-1.151 0.911-1.671 0.331-0.506 0.646-0.985 0.942-1.436 0.603-0.893 1.096-1.696 1.57-2.307 0.971-1.206 1.526-1.895 1.526-1.895z"/>
                                                <path d="m320.45 163.73s0.5 3.216 1.563 6.291c0.658 1.479 1.211 3.006 1.865 4.033 0.288 0.533 0.528 0.977 0.697 1.289 0.166 0.312 0.3 0.467 0.3 0.467l-9.56 6.028s-0.175-0.218-0.409-0.643-0.567-1.033-0.968-1.762c-0.872-1.425-1.68-3.494-2.541-5.536-1.483-4.185-2.137-8.582-2.137-8.582z"/>
                                                <path d="m365.08 123.56s-0.175-0.073-0.505-0.209c-0.328-0.138-0.807-0.35-1.449-0.526c-0.636-0.195-1.408-0.431-2.293-0.702-0.879-0.297-1.924-0.425-3.035-0.676-4.464-0.873-10.669-1-16.579 0.511-5.914 1.491-11.308 4.562-14.815 7.458-0.857 0.751-1.713 1.362-2.345 2.042-0.649 0.661-1.215 1.237-1.68 1.712-0.482 0.461-0.801 0.875-1.024 1.153-0.224 0.277-0.344 0.424-0.344 0.424l-4.914-4.081s0.14-0.172 0.402-0.493c0.261-0.323 0.637-0.801 1.192-1.343 0.543-0.553 1.202-1.224 1.958-1.994 0.742-0.785 1.728-1.512 2.732-2.382 0.991-0.89 2.201-1.675 3.458-2.536 1.229-0.906 2.668-1.63 4.124-2.432 0.366-0.197 0.734-0.396 1.106-0.596 0.387-0.166 0.777-0.334 1.17-0.503 0.788-0.332 1.584-0.668 2.387-1.007 1.62-0.637 3.336-1.083 5.02-1.613 1.734-0.337 3.454-0.763 5.182-0.976 0.868-0.085 1.729-0.17 2.579-0.254 0.426-0.039 0.849-0.077 1.268-0.116 0.422-1e-3 0.841-2e-3 1.256-3e-3 1.662 0.011 3.271-0.04 4.785 0.17 1.515 0.157 2.954 0.269 4.249 0.58 1.297 0.286 2.51 0.454 3.537 0.791 1.032 0.316 1.931 0.591 2.672 0.818 0.747 0.211 1.306 0.452 1.689 0.612 0.383 0.157 0.588 0.242 0.588 0.242z"/>
                                                <path d="m337.33 131.98s-0.707 0.39-1.769 0.975c-0.267 0.144-0.555 0.301-0.86 0.467-0.285 0.198-0.586 0.407-0.897 0.623-0.607 0.451-1.331 0.831-1.931 1.377-0.62 0.518-1.241 1.036-1.823 1.522-0.532 0.541-1.028 1.046-1.453 1.48-0.433 0.426-0.788 0.786-0.993 1.078-0.221 0.277-0.348 0.435-0.348 0.435l-8.694-7.221s0.175-0.215 0.48-0.591c0.29-0.39 0.768-0.891 1.356-1.48 0.585-0.59 1.268-1.279 1.999-2.017 0.796-0.668 1.646-1.381 2.495-2.094 0.835-0.732 1.805-1.287 2.647-1.896 0.43-0.292 0.846-0.574 1.24-0.842 0.417-0.231 0.81-0.45 1.174-0.652 1.461-0.796 2.435-1.327 2.435-1.327z"/>
                                                <path d="m389.37 162.02s0.017-0.189 0.048-0.544c1e-3 -0.356 3e-3 -0.879 6e-3 -1.544-6e-3 -0.665 0.022-1.474-0.011-2.398-0.09-0.922-0.191-1.962-0.301-3.096-0.596-4.501-2.304-10.475-5.627-15.602-3.247-5.163-7.828-9.347-11.67-11.782-0.478-0.31-0.926-0.625-1.37-0.892-0.458-0.244-0.893-0.476-1.302-0.694-0.822-0.425-1.52-0.837-2.129-1.103-1.228-0.51-1.93-0.802-1.93-0.802l2.372-5.931s0.816 0.341 2.245 0.938c0.708 0.311 1.524 0.782 2.48 1.279 0.475 0.255 0.98 0.527 1.513 0.813 0.518 0.311 1.042 0.672 1.598 1.034 4.471 2.835 9.812 7.706 13.595 13.732 3.872 5.988 5.868 12.93 6.556 18.168 0.128 1.322 0.244 2.534 0.348 3.608 0.042 1.078 0.015 2.021 0.02 2.797-6e-3 0.775-0.011 1.385-0.014 1.8-0.035 0.414-0.054 0.634-0.054 0.634z"/>
                                                <path d="m372.76 138.25s-0.577-0.568-1.441-1.42c-0.439-0.419-1.021-0.83-1.601-1.319-0.295-0.239-0.6-0.486-0.91-0.738-0.334-0.218-0.674-0.44-1.013-0.661-1.312-0.962-2.791-1.641-3.85-2.237-1.12-0.471-1.867-0.784-1.867-0.784l4.197-10.493s1.032 0.406 2.549 1.083c1.462 0.787 3.464 1.752 5.269 3.047 0.461 0.307 0.922 0.613 1.376 0.915 0.427 0.34 0.846 0.674 1.252 0.998 0.8 0.662 1.58 1.243 2.184 1.812 1.187 1.164 1.979 1.94 1.979 1.94z"/>
                                                <path d="m360.28 197.01s0.726-0.224 1.997-0.615c0.628-0.218 1.424-0.385 2.273-0.757 0.853-0.361 1.816-0.768 2.866-1.212 1.022-0.501 2.091-1.125 3.241-1.743 1.121-0.669 2.229-1.494 3.413-2.285 1.086-0.919 2.26-1.818 3.336-2.855 1.027-1.086 2.175-2.097 3.081-3.323 3.915-4.669 6.523-10.301 7.646-14.715 0.326-1.092 0.464-2.134 0.669-3.036 0.087-0.455 0.189-0.877 0.246-1.273 0.041-0.399 0.079-0.765 0.114-1.095 0.135-1.324 0.213-2.079 0.213-2.079l6.374 0.417s-0.089 0.882-0.245 2.426c-0.042 0.385-0.088 0.812-0.138 1.277-0.066 0.462-0.18 0.955-0.281 1.486-0.233 1.053-0.408 2.265-0.783 3.539-1.312 5.143-4.339 11.701-8.901 17.137-1.065 1.418-2.386 2.612-3.591 3.869-1.255 1.207-2.616 2.265-3.891 3.326-1.374 0.933-2.673 1.886-3.98 2.666-1.336 0.729-2.588 1.45-3.781 2.032-1.223 0.518-2.344 0.993-3.338 1.414-0.992 0.426-1.912 0.635-2.644 0.885-1.479 0.45-2.325 0.707-2.325 0.707z"/>
                                                <path d="m377.73 173.84s1.616-2.841 2.425-5.99c0.281-0.763 0.402-1.565 0.555-2.307 0.138-0.745 0.337-1.429 0.357-2.038 0.125-1.206 0.208-2.009 0.208-2.009l11.277 0.738s-0.113 1.103-0.282 2.759c-0.05 0.833-0.29 1.776-0.485 2.798-0.209 1.018-0.401 2.112-0.763 3.163-0.339 1.055-0.615 2.132-0.995 3.098-0.398 0.96-0.769 1.855-1.087 2.623-0.296 0.778-0.659 1.371-0.877 1.804-0.228 0.428-0.358 0.672-0.358 0.672z"/>
                                            </g>
                                        </svg>
                                    </div>

                                    <!-- RIGHT REEL (dark circle from logo + white teeth) -->
                                    <div class="reel spinning" id="right-reel">
                                        <svg viewBox="270 79 161 161" xmlns="http://www.w3.org/2000/svg">
                                            <!-- Dark gray circle base from logo line 11 -->
                                            <circle cx="350.75" cy="159.48" r="62.426" fill="#504f4f"/>

                                            <!-- White gear teeth pattern - wrapped for proper rotation -->
                                            <g class="gear-rotation">
                                                <g fill="#ffffff">
                                                <path d="m318.02 180.14s0.428 0.627 1.179 1.726c0.188 0.274 0.395 0.578 0.622 0.909 0.239 0.321 0.53 0.644 0.824 1.002 0.611 0.695 1.229 1.545 2.037 2.349 3.093 3.344 8.07 7.05 13.739 9.286 1.381 0.645 2.872 0.986 4.293 1.451 1.441 0.398 2.901 0.629 4.294 0.918 1.418 0.13 2.786 0.326 4.09 0.38 1.306-6e-3 2.543 0.034 3.68-0.014 1.134-0.111 2.174-0.212 3.096-0.301 0.924-0.079 1.704-0.311 2.359-0.419 1.303-0.263 2.048-0.412 2.048-0.412l1.572 6.191s-0.866 0.177-2.381 0.487c-0.762 0.129-1.671 0.384-2.746 0.483-1.074 0.104-2.286 0.221-3.609 0.35-1.326 0.057-2.769 0.021-4.292 0.018-1.52-0.063-3.117-0.281-4.769-0.445-1.626-0.324-3.327-0.604-5.006-1.067-1.659-0.529-3.389-0.95-5.002-1.688-6.603-2.602-12.391-6.921-15.997-10.816-0.937-0.941-1.669-1.923-2.377-2.737-0.341-0.418-0.677-0.797-0.955-1.171-0.266-0.384-0.51-0.738-0.73-1.057-0.873-1.282-1.372-2.015-1.372-2.015z"/>
                                                <path d="m345.44 189.6s0.198 0.042 0.544 0.115c0.347 0.071 0.854 0.089 1.456 0.159 0.604 0.04 1.303 0.183 2.061 0.178 0.758 3e-3 1.566 5e-3 2.373 8e-3 0.808-0.023 1.611-0.153 2.366-0.208 0.377-0.042 0.745-0.051 1.088-0.113 0.341-0.071 0.664-0.138 0.962-0.201 1.195-0.234 1.992-0.391 1.992-0.391l2.781 10.954s-1.085 0.22-2.713 0.55c-0.408 0.08-0.848 0.168-1.315 0.26-0.469 0.08-0.972 0.108-1.488 0.166-1.035 0.088-2.136 0.242-3.243 0.276-1.109-3e-3 -2.218-6e-3 -3.258-9e-3 -1.04-6e-3 -2.002-0.171-2.831-0.236-0.826-0.094-1.52-0.139-1.996-0.231-0.476-0.095-0.748-0.149-0.748-0.149z"/>
                                                <path d="m321.02 134.75s-0.478 0.591-1.314 1.625c-0.409 0.524-0.825 1.219-1.345 1.984-0.255 0.386-0.527 0.798-0.813 1.231-0.263 0.447-0.507 0.937-0.779 1.438-2.215 3.973-4.246 9.834-4.637 15.921-0.475 6.09 0.874 12.157 2.497 16.396 0.444 1.05 0.851 2.012 1.212 2.865 0.411 0.829 0.822 1.526 1.134 2.113 0.319 0.583 0.57 1.042 0.742 1.354 0.197 0.296 0.302 0.455 0.302 0.455l-5.403 3.407s-0.122-0.185-0.35-0.532c-0.201-0.364-0.496-0.897-0.871-1.576-0.366-0.683-0.839-1.5-1.316-2.467-0.421-0.993-0.896-2.115-1.415-3.338-1.895-4.932-3.452-11.985-2.904-19.095 0.45-7.102 2.821-13.93 5.399-18.554 0.316-0.583 0.605-1.151 0.911-1.671 0.331-0.506 0.646-0.985 0.942-1.436 0.603-0.893 1.096-1.696 1.57-2.307 0.971-1.206 1.526-1.895 1.526-1.895z"/>
                                                <path d="m320.45 163.73s0.5 3.216 1.563 6.291c0.658 1.479 1.211 3.006 1.865 4.033 0.288 0.533 0.528 0.977 0.697 1.289 0.166 0.312 0.3 0.467 0.3 0.467l-9.56 6.028s-0.175-0.218-0.409-0.643-0.567-1.033-0.968-1.762c-0.872-1.425-1.68-3.494-2.541-5.536-1.483-4.185-2.137-8.582-2.137-8.582z"/>
                                                <path d="m365.08 123.56s-0.175-0.073-0.505-0.209c-0.328-0.138-0.807-0.35-1.449-0.526c-0.636-0.195-1.408-0.431-2.293-0.702-0.879-0.297-1.924-0.425-3.035-0.676-4.464-0.873-10.669-1-16.579 0.511-5.914 1.491-11.308 4.562-14.815 7.458-0.857 0.751-1.713 1.362-2.345 2.042-0.649 0.661-1.215 1.237-1.68 1.712-0.482 0.461-0.801 0.875-1.024 1.153-0.224 0.277-0.344 0.424-0.344 0.424l-4.914-4.081s0.14-0.172 0.402-0.493c0.261-0.323 0.637-0.801 1.192-1.343 0.543-0.553 1.202-1.224 1.958-1.994 0.742-0.785 1.728-1.512 2.732-2.382 0.991-0.89 2.201-1.675 3.458-2.536 1.229-0.906 2.668-1.63 4.124-2.432 0.366-0.197 0.734-0.396 1.106-0.596 0.387-0.166 0.777-0.334 1.17-0.503 0.788-0.332 1.584-0.668 2.387-1.007 1.62-0.637 3.336-1.083 5.02-1.613 1.734-0.337 3.454-0.763 5.182-0.976 0.868-0.085 1.729-0.17 2.579-0.254 0.426-0.039 0.849-0.077 1.268-0.116 0.422-1e-3 0.841-2e-3 1.256-3e-3 1.662 0.011 3.271-0.04 4.785 0.17 1.515 0.157 2.954 0.269 4.249 0.58 1.297 0.286 2.51 0.454 3.537 0.791 1.032 0.316 1.931 0.591 2.672 0.818 0.747 0.211 1.306 0.452 1.689 0.612 0.383 0.157 0.588 0.242 0.588 0.242z"/>
                                                <path d="m337.33 131.98s-0.707 0.39-1.769 0.975c-0.267 0.144-0.555 0.301-0.86 0.467-0.285 0.198-0.586 0.407-0.897 0.623-0.607 0.451-1.331 0.831-1.931 1.377-0.62 0.518-1.241 1.036-1.823 1.522-0.532 0.541-1.028 1.046-1.453 1.48-0.433 0.426-0.788 0.786-0.993 1.078-0.221 0.277-0.348 0.435-0.348 0.435l-8.694-7.221s0.175-0.215 0.48-0.591c0.29-0.39 0.768-0.891 1.356-1.48 0.585-0.59 1.268-1.279 1.999-2.017 0.796-0.668 1.646-1.381 2.495-2.094 0.835-0.732 1.805-1.287 2.647-1.896 0.43-0.292 0.846-0.574 1.24-0.842 0.417-0.231 0.81-0.45 1.174-0.652 1.461-0.796 2.435-1.327 2.435-1.327z"/>
                                                <path d="m389.37 162.02s0.017-0.189 0.048-0.544c1e-3 -0.356 3e-3 -0.879 6e-3 -1.544-6e-3 -0.665 0.022-1.474-0.011-2.398-0.09-0.922-0.191-1.962-0.301-3.096-0.596-4.501-2.304-10.475-5.627-15.602-3.247-5.163-7.828-9.347-11.67-11.782-0.478-0.31-0.926-0.625-1.37-0.892-0.458-0.244-0.893-0.476-1.302-0.694-0.822-0.425-1.52-0.837-2.129-1.103-1.228-0.51-1.93-0.802-1.93-0.802l2.372-5.931s0.816 0.341 2.245 0.938c0.708 0.311 1.524 0.782 2.48 1.279 0.475 0.255 0.98 0.527 1.513 0.813 0.518 0.311 1.042 0.672 1.598 1.034 4.471 2.835 9.812 7.706 13.595 13.732 3.872 5.988 5.868 12.93 6.556 18.168 0.128 1.322 0.244 2.534 0.348 3.608 0.042 1.078 0.015 2.021 0.02 2.797-6e-3 0.775-0.011 1.385-0.014 1.8-0.035 0.414-0.054 0.634-0.054 0.634z"/>
                                                <path d="m372.76 138.25s-0.577-0.568-1.441-1.42c-0.439-0.419-1.021-0.83-1.601-1.319-0.295-0.239-0.6-0.486-0.91-0.738-0.334-0.218-0.674-0.44-1.013-0.661-1.312-0.962-2.791-1.641-3.85-2.237-1.12-0.471-1.867-0.784-1.867-0.784l4.197-10.493s1.032 0.406 2.549 1.083c1.462 0.787 3.464 1.752 5.269 3.047 0.461 0.307 0.922 0.613 1.376 0.915 0.427 0.34 0.846 0.674 1.252 0.998 0.8 0.662 1.58 1.243 2.184 1.812 1.187 1.164 1.979 1.94 1.979 1.94z"/>
                                                <path d="m360.28 197.01s0.726-0.224 1.997-0.615c0.628-0.218 1.424-0.385 2.273-0.757 0.853-0.361 1.816-0.768 2.866-1.212 1.022-0.501 2.091-1.125 3.241-1.743 1.121-0.669 2.229-1.494 3.413-2.285 1.086-0.919 2.26-1.818 3.336-2.855 1.027-1.086 2.175-2.097 3.081-3.323 3.915-4.669 6.523-10.301 7.646-14.715 0.326-1.092 0.464-2.134 0.669-3.036 0.087-0.455 0.189-0.877 0.246-1.273 0.041-0.399 0.079-0.765 0.114-1.095 0.135-1.324 0.213-2.079 0.213-2.079l6.374 0.417s-0.089 0.882-0.245 2.426c-0.042 0.385-0.088 0.812-0.138 1.277-0.066 0.462-0.18 0.955-0.281 1.486-0.233 1.053-0.408 2.265-0.783 3.539-1.312 5.143-4.339 11.701-8.901 17.137-1.065 1.418-2.386 2.612-3.591 3.869-1.255 1.207-2.616 2.265-3.891 3.326-1.374 0.933-2.673 1.886-3.98 2.666-1.336 0.729-2.588 1.45-3.781 2.032-1.223 0.518-2.344 0.993-3.338 1.414-0.992 0.426-1.912 0.635-2.644 0.885-1.479 0.45-2.325 0.707-2.325 0.707z"/>
                                                <path d="m377.73 173.84s1.616-2.841 2.425-5.99c0.281-0.763 0.402-1.565 0.555-2.307 0.138-0.745 0.337-1.429 0.357-2.038 0.125-1.206 0.208-2.009 0.208-2.009l11.277 0.738s-0.113 1.103-0.282 2.759c-0.05 0.833-0.29 1.776-0.485 2.798-0.209 1.018-0.401 2.112-0.763 3.163-0.339 1.055-0.615 2.132-0.995 3.098-0.398 0.96-0.769 1.855-1.087 2.623-0.296 0.778-0.659 1.371-0.877 1.804-0.228 0.428-0.358 0.672-0.358 0.672z"/>
                                            </g>
                                        </g>
                                        </svg>
                                    </div>
                                </div>


                            </div>
                        </div>
                        <!-- Layer 4: Bottom cassette piece -->
                        <div class="cassette-bottom">
                        <svg viewBox="0 0 72.244476 15.794047"
                            xmlns="http://www.w3.org/2000/svg"
                            preserveAspectRatio="xMidYMid meet">

                            <g transform="translate(-82.298027,-99.354062)">
                                <!-- Bottom plate -->
                                <path
                                    d="M 153.07963,115.1481 H 83.761438
                                        c -0.80486,0 -1.46341,-0.65855 -1.46341,-1.46341
                                        l 7.248,-12.86722
                                        c 0,-0.80486 0.65855,-1.463414 1.46341,-1.463414
                                        h 54.821672
                                        c 0.80486,0 1.46341,0.658554 1.46341,1.463414
                                        l 7.24799,12.86722
                                        c 2.7e-4,0.80486 -0.65855,1.46341 -1.46341,1.46341 z"
                                    fill="#5d5e5e"/>

                                <!-- LEFT screw -->
                                <circle
                                    cx="92.5"
                                    cy="108.3"
                                    r="1.4"
                                    fill="#3e3e3e"/>
                                <circle
                                    cx="92.5"
                                    cy="108.3"
                                    r="0.6"
                                    fill="#6f6f6f"/>

                                <!-- RIGHT screw -->
                                <circle
                                    cx="144.0"
                                    cy="108.3"
                                    r="1.4"
                                    fill="#3e3e3e"/>
                                <circle
                                    cx="144.0"
                                    cy="108.3"
                                    r="0.6"
                                    fill="#6f6f6f"/>
                            </g>
                        </svg>
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

                    <!-- Right Side Panel (for Walkman mode) -->
                    <div class="side-panel side-panel-right">
                        <div class="screw"></div>
                        <div class="vertical-branding">SOCIETY</div>
                        <div class="panel-spacer"></div>
                        <div class="status-indicator">
                            <div class="status-light active" id="status-power"></div>
                            <div class="status-label">PWR</div>
                        </div>
                        <div class="status-indicator">
                            <div class="status-light" id="status-battery"></div>
                            <div class="status-label">BATT</div>
                        </div>
                        <div class="panel-spacer"></div>
                        <div class="screw"></div>
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
            btn.addEventListener('click', async () => await switchMode(btn.dataset.mode));
        });
    }

    /**
     * Lock screen orientation to landscape (mobile only)
     * Must be called from a user gesture (button click)
     */
    async function lockOrientationLandscape() {
        // Only on mobile devices
        if (!isMobile()) return;
        
        try {
            // Try Screen Orientation API
            if (screen.orientation && screen.orientation.lock) {
                await screen.orientation.lock('landscape');
                console.log('✓ Orientation locked to landscape');
            }
        } catch (error) {
            console.log('Screen Orientation API not available:', error);
            // Fallback: try deprecated method
            try {
                const lockOrientation = screen.lockOrientation || 
                                       screen.mozLockOrientation || 
                                       screen.msLockOrientation;
                if (lockOrientation) {
                    lockOrientation('landscape');
                    console.log('✓ Orientation locked (deprecated API)');
                }
            } catch (e) {
                console.log('Orientation lock not supported:', e);
            }
        }
    }

    /**
     * Unlock screen orientation (restores user's auto-rotate preference)
     */
    async function unlockOrientation() {
        try {
            if (screen.orientation && screen.orientation.unlock) {
                screen.orientation.unlock();
                console.log('✓ Orientation unlocked - user auto-rotate preference restored');
            }
        } catch (error) {
            // Try deprecated method
            try {
                const unlockOrientation = screen.unlockOrientation || 
                                         screen.mozUnlockOrientation || 
                                         screen.msUnlockOrientation;
                if (unlockOrientation) {
                    unlockOrientation();
                    console.log('✓ Orientation unlocked (deprecated API) - user preference restored');
                }
            } catch (e) {
                console.log('Orientation unlock failed:', e);
            }
        }
    }

    /**
     * Enter fullscreen mode
     */
    async function enterFullscreen() {
        if (!isMobile()) return;
        
        try {
            await requestFullscreenOn(document.documentElement);
            console.log('✓ Entered fullscreen');
        } catch (error) {
            console.log('Fullscreen request failed:', error);
        }
    }

    /**
     * Exit fullscreen mode
     */
    async function exitFullscreen() {
        try {
            if (isFullscreen()) {
                await exitFullscreenMode();
                console.log('✓ Exited fullscreen');
            }
        } catch (error) {
            console.log('Exit fullscreen failed:', error);
        }
    }

    // Track if listeners have been initialized (singleton pattern)
    let listenersInitialized = false;
    
    /**
     * Helper: Check if currently in fullscreen
     */
    function isFullscreen() {
        return !!(document.fullscreenElement || 
                 document.webkitFullscreenElement || 
                 document.mozFullScreenElement || 
                 document.msFullscreenElement);
    }

    /**
     * Helper: Request fullscreen on element
     */
    async function requestFullscreenOn(element) {
        if (element.requestFullscreen) {
            return await element.requestFullscreen();
        } else if (element.webkitRequestFullscreen) {
            return await element.webkitRequestFullscreen();
        } else if (element.mozRequestFullScreen) {
            return await element.mozRequestFullScreen();
        } else if (element.msRequestFullscreen) {
            return await element.msRequestFullscreen();
        }
    }

    /**
     * Helper: Exit fullscreen
     */
    async function exitFullscreenMode() {
        if (document.exitFullscreen) {
            return await document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            return await document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            return await document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            return await document.msExitFullscreen();
        }
    }

    /**
     * Check if device is mobile
     */
    function isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) 
            || window.innerWidth <= 932;
    }

    /**
     * Show brief notification to user about how to exit
     */
    function showExitHint() {
        // Create notification element
        const hint = document.createElement('div');
        hint.className = 'walkman-exit-hint';
        hint.innerHTML = `
            <div class="hint-content">
                <span class="hint-icon">ℹ️</span>
                <span>Tap the button on the left panel to exit Walkman mode</span>
            </div>
        `;
        document.body.appendChild(hint);
        
        // Show notification
        setTimeout(() => hint.classList.add('show'), 100);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            hint.classList.remove('show');
            setTimeout(() => hint.remove(), 300);
        }, 5000);
    }

    /**
     * Switch between modern and cassette mode
     */
    async function switchMode(mode) {
        currentMode = mode;
        localStorage.setItem('playerMode', mode);

        // Update toggle buttons
        document.querySelectorAll('.view-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Toggle visibility
        const cassetteContainer = document.getElementById('cassette-player-container');

        if (mode === 'cassette') {
            cassetteContainer?.classList.add('active');
            document.body.classList.add('cassette-mode');
            
            // On mobile: enter fullscreen and lock to landscape
            // These MUST be called from user gesture (button click)
            if (isMobile()) {
                await enterFullscreen();
                await lockOrientationLandscape();
                
                // Show hint on first time entering Walkman mode
                const hasSeenHint = localStorage.getItem('walkmanHintSeen');
                if (!hasSeenHint) {
                    showExitHint();
                    localStorage.setItem('walkmanHintSeen', 'true');
                }
            }
        } else {
            cassetteContainer?.classList.remove('active');
            document.body.classList.remove('cassette-mode');
            
            // Exit fullscreen and unlock orientation when switching to modern
            if (isMobile()) {
                await exitFullscreen();
                await unlockOrientation();
            }
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
        const playLight = document.getElementById('status-play');

        if (playing) {
            leftReel?.classList.add('spinning');
            rightReel?.classList.add('spinning');
            playLight?.classList.add('active');
        } else {
            leftReel?.classList.remove('spinning');
            rightReel?.classList.remove('spinning');
            playLight?.classList.remove('active');
        }
    }

    /**
     * Initialize audio visualization for VU meters
     */
    function initAudioVisualization() {
        const player = document.getElementById('main-player');
        if (!player || audioContext) return;

        try {
            // Create AudioContext
            audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Try to create media element source
            // This will fail if CORS headers aren't set properly
            const source = audioContext.createMediaElementSource(player);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8; // Smooth the VU meter movement

            source.connect(analyser);
            analyser.connect(audioContext.destination);

            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);

            console.log('✅ Audio visualization initialized successfully');
            updateVUMeters();
        } catch (error) {
            console.warn('⚠️ Audio visualization failed (likely CORS issue):', error.message);
            console.warn('VU meters will use fallback animation');

            // Use fallback animation when Web Audio API fails
            useFallbackVUMeters();
        }
    }

    /**
     * Fallback VU meters when Web Audio API is blocked by CORS
     */
    function useFallbackVUMeters() {
        console.log('Using fallback VU meter animation');

        function animateFallbackVUMeters() {
            if (!isPlaying) return;

            // Simulate realistic VU meter movement
            const leftMeter = document.getElementById('vu-meter-left');
            const rightMeter = document.getElementById('vu-meter-right');

            // Random but realistic values (30-80% range with occasional peaks)
            const baseLevel = 40 + Math.random() * 30;
            const leftLevel = baseLevel + Math.random() * 10;
            const rightLevel = baseLevel + Math.random() * 10 - 5;

            // Occasional peaks
            const peak = Math.random() > 0.95 ? 20 : 0;

            if (leftMeter) leftMeter.style.width = `${Math.min(95, leftLevel + peak)}%`;
            if (rightMeter) rightMeter.style.width = `${Math.min(95, rightLevel + peak)}%`;

            // Update at 60fps
            if (isPlaying) {
                requestAnimationFrame(animateFallbackVUMeters);
            }
        }

        animateFallbackVUMeters();
    }

    /**
     * Update VU meters based on audio levels
     */
    function updateVUMeters() {
        // If no analyser, we're using fallback
        if (!analyser || !dataArray) {
            useFallbackVUMeters();
            return;
        }

        try {
            analyser.getByteFrequencyData(dataArray);

            // Calculate average level
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const average = sum / dataArray.length;
            const percentage = Math.min(95, (average / 255) * 100); // Cap at 95%

            // Update both meters (simulating stereo)
            const leftMeter = document.getElementById('vu-meter-left');
            const rightMeter = document.getElementById('vu-meter-right');

            if (leftMeter) leftMeter.style.width = `${percentage}%`;
            if (rightMeter) rightMeter.style.width = `${percentage * 0.95}%`; // Slightly different for effect

            if (isPlaying) {
                requestAnimationFrame(updateVUMeters);
            }
        } catch (error) {
            console.warn('VU meter update failed, switching to fallback');
            useFallbackVUMeters();
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
        playBtn?.addEventListener('click', async () => {
            playButtonSound('click');
            
            // (Re-)enter fullscreen and orientation lock on mobile
            // This handles both initial entry and re-entry after phone lock
            if (isMobile() && currentMode === 'cassette') {
                if (!isFullscreen()) {
                    await enterFullscreen();
                }
                await lockOrientationLandscape();
            }
            
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

        // Panel mode toggle button (on MIXTAPE panel)
        const panelToggleBtn = document.getElementById('panel-mode-toggle');
        panelToggleBtn?.addEventListener('click', async () => {
            playButtonSound('click');
            await switchMode('modern'); // Switch to modern mode
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

                // Initialize audio visualization or use fallback
                if (!audioContext) {
                    initAudioVisualization();
                } else if (!analyser) {
                    // Audio context exists but analyser failed (CORS issue)
                    useFallbackVUMeters();
                } else {
                    // Real audio visualization
                    updateVUMeters();
                }
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
     * Initialize global event listeners (singleton - only runs once)
     */
    function initGlobalListeners() {
        if (listenersInitialized) {
            console.log('⚠️ Global listeners already initialized, skipping');
            return;
        }

        // Listen for fullscreen changes (phone lock/unlock will exit fullscreen)
        const handleFullscreenChange = async () => {
            // If we're in cassette mode but fullscreen was exited (e.g., phone lock/unlock)
            if (currentMode === 'cassette' && !isFullscreen() && isMobile()) {
                console.log('📱 Fullscreen exited (phone lock?)');
                
                // Only unlock orientation if tape is NOT playing
                if (!isPlaying) {
                    console.log('⏹️ Tape not playing - restoring user orientation preference');
                    await unlockOrientation();
                } else {
                    console.log('▶️ Tape still playing - keeping landscape lock, will re-enter fullscreen on next interaction');
                    // Keep orientation locked, re-enter fullscreen on next button press
                }
            }
        };
        
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        document.addEventListener('mozfullscreenchange', handleFullscreenChange);
        document.addEventListener('MSFullscreenChange', handleFullscreenChange);

        // Restore orientation when user quits/leaves the page
        const handlePageUnload = async () => {
            if (currentMode === 'cassette' && isMobile()) {
                console.log('👋 User leaving page - restoring orientation preference');
                await unlockOrientation();
            }
        };

        const handleVisibilityChange = () => {
            if (document.hidden && currentMode === 'cassette' && isMobile()) {
                console.log('👁️ Page hidden - restoring orientation preference');
                unlockOrientation();
            }
        };

        // Multiple events to catch different ways user can leave
        window.addEventListener('beforeunload', handlePageUnload);
        window.addEventListener('pagehide', handlePageUnload);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        listenersInitialized = true;
        console.log('✓ Global listeners initialized');
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

        // Initialize global listeners (singleton)
        initGlobalListeners();

        // Apply saved mode (but orientation lock won't work until user clicks)
        // Note: Just sets the UI mode, fullscreen/orientation requires user gesture
        const cassetteContainer = document.getElementById('cassette-player-container');
        if (currentMode === 'cassette') {
            cassetteContainer?.classList.add('active');
            document.body.classList.add('cassette-mode');
            
            // Show hint on mobile if starting in cassette mode
            if (isMobile() && currentMode === 'cassette') {
                console.log('💡 Tip: Click any button to enable fullscreen and landscape lock');
            }
        }

        console.log('🎵 Cassette player initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}
