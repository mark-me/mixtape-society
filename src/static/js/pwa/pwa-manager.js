// static/js/pwa/pwa-manager.js
// PWA initialization and offline features management

/**
 * PWA Manager - Handles service worker registration, installation prompts,
 * and offline functionality controls
 */
class PWAManager {
    constructor() {
        this.swRegistration = null;
        this.deferredPrompt = null;
        this.isOnline = navigator.onLine;
        
        this.init();
    }

    /**
     * Initialize PWA features
     */
    async init() {
        // Check for service worker support
        if (!('serviceWorker' in navigator)) {
            console.warn('Service Workers not supported in this browser');
            return;
        }

        // Register service worker
        await this.registerServiceWorker();

        // Setup install prompt handler
        this.setupInstallPrompt();

        // Setup online/offline detection
        this.setupNetworkDetection();

        // Initialize offline controls
        this.initializeOfflineControls();

        // Check for updates periodically
        this.setupUpdateChecks();

        console.log('✅ PWA Manager initialized');
    }

    /**
     * Register the service worker
     */
    async registerServiceWorker() {
        try {
            const registration = await navigator.serviceWorker.register('/service-worker.js', {
                scope: '/play/'  // Scope to /play/ only for public mixtapes
            });

            this.swRegistration = registration;

            console.log('✅ Service Worker registered:', registration.scope);

            // Check for updates on page load
            registration.update();

            // Listen for updates
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // New version available
                        this.showUpdateNotification();
                    }
                });
            });

            // Listen for controller change (new SW took over)
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                console.log('🔄 New service worker activated, reloading page...');
                window.location.reload();
            });

        } catch (error) {
            console.error('❌ Service Worker registration failed:', error);
        }
    }

    /**
     * Setup install prompt handling
     */
    setupInstallPrompt() {
        window.addEventListener('beforeinstallprompt', (e) => {
            // Prevent the mini-infobar from appearing on mobile
            e.preventDefault();
            
            // Store the event for later use
            this.deferredPrompt = e;
            
            // Show install button
            this.showInstallButton();
            
            console.log('📱 Install prompt available');
        });

        // Track installation
        window.addEventListener('appinstalled', () => {
            console.log('✅ PWA installed successfully');
            this.deferredPrompt = null;
            this.hideInstallButton();
            this.showToast('App installed successfully!', 'success');
        });
    }

    /**
     * Setup network status detection
     */
    setupNetworkDetection() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.updateOfflineIndicator(false);
            this.showToast('Back online', 'success');
            console.log('🌐 Back online');
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.updateOfflineIndicator(true);
            this.showToast('You are offline', 'warning');
            console.log('📵 Offline');
        });

        // Initial check
        this.updateOfflineIndicator(!this.isOnline);
    }

    /**
     * Show install button in UI
     */
    showInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'block';
            installBtn.addEventListener('click', () => this.promptInstall());
        }
    }

    /**
     * Hide install button
     */
    hideInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'none';
        }
    }

    /**
     * Prompt user to install PWA
     */
    async promptInstall() {
        if (!this.deferredPrompt) {
            console.log('No install prompt available');
            return;
        }

        // Show the install prompt
        this.deferredPrompt.prompt();

        // Wait for user choice
        const { outcome } = await this.deferredPrompt.userChoice;
        
        console.log(`User ${outcome} the install prompt`);
        
        // Clear the deferred prompt
        this.deferredPrompt = null;
        this.hideInstallButton();
    }

    /**
     * Update offline indicator in UI
     */
    updateOfflineIndicator(isOffline) {
        const indicator = document.getElementById('offline-indicator');
        if (indicator) {
            indicator.style.display = isOffline ? 'block' : 'none';
        }

        // Add class to body for styling
        document.body.classList.toggle('offline-mode', isOffline);
    }

    /**
     * Show update notification
     */
    showUpdateNotification() {
        const updateBtn = document.createElement('div');
        updateBtn.className = 'update-notification';
        
        // Create structure using DOM methods (XSS-safe)
        const updateContent = document.createElement('div');
        updateContent.className = 'update-content';
        
        const icon = document.createElement('i');
        icon.className = 'bi bi-arrow-clockwise me-2';
        
        const span = document.createElement('span');
        span.textContent = 'Update available';
        
        updateContent.appendChild(icon);
        updateContent.appendChild(span);
        
        const button = document.createElement('button');
        button.className = 'btn btn-sm btn-light';
        button.id = 'update-now-btn';
        button.textContent = 'Update';
        
        updateBtn.appendChild(updateContent);
        updateBtn.appendChild(button);
        
        document.body.appendChild(updateBtn);

        // Handle update button click
        document.getElementById('update-now-btn').addEventListener('click', () => {
            if (this.swRegistration && this.swRegistration.waiting) {
                // Tell the waiting SW to activate
                this.swRegistration.waiting.postMessage({ action: 'SKIP_WAITING' });
            }
        });
    }

    /**
     * Setup periodic update checks
     */
    setupUpdateChecks() {
        // Check for updates every hour
        setInterval(() => {
            if (this.swRegistration) {
                this.swRegistration.update();
            }
        }, 60 * 60 * 1000); // 1 hour
    }

    /**
     * Initialize offline controls (download, cache management)
     */
    initializeOfflineControls() {
        // Download mixtape button
        const downloadMixtapeBtn = document.getElementById('download-mixtape-btn');
        if (downloadMixtapeBtn) {
            downloadMixtapeBtn.addEventListener('click', () => this.downloadMixtapeForOffline());
        }

        // Cache management button
        const manageCacheBtn = document.getElementById('manage-cache-btn');
        if (manageCacheBtn) {
            manageCacheBtn.addEventListener('click', () => this.showCacheManagement());
        }

        // Clear cache button
        const clearCacheBtn = document.getElementById('clear-cache-btn');
        if (clearCacheBtn) {
            clearCacheBtn.addEventListener('click', () => this.clearCache());
        }
    }

    /**
     * Download entire mixtape for offline playback
     */
    async downloadMixtapeForOffline() {
        const mixtapeData = window.__mixtapeData;
        if (!mixtapeData || !mixtapeData.tracks) {
            this.showToast('No mixtape data found', 'danger');
            return;
        }

        const tracks = mixtapeData.tracks;
        const quality = localStorage.getItem('audioQuality') || 'medium';
        
        this.showToast(`Downloading ${tracks.length} tracks...`, 'info');

        const downloadBtn = document.getElementById('download-mixtape-btn');
        if (downloadBtn) {
            downloadBtn.disabled = true;
            // Use textContent (XSS-safe) and set icon separately
            downloadBtn.innerHTML = ''; // Clear existing content
            const icon = document.createElement('i');
            icon.className = 'bi bi-hourglass-split me-2';
            const text = document.createTextNode('Downloading...');
            downloadBtn.appendChild(icon);
            downloadBtn.appendChild(text);
        }

        let successCount = 0;
        let failCount = 0;

        // Download tracks in parallel (limit to 3 at a time)
        const limit = 3;
        for (let i = 0; i < tracks.length; i += limit) {
            const batch = tracks.slice(i, i + limit);
            
            const results = await Promise.allSettled(
                batch.map(track => this.cacheAudioFile(track.path, quality))
            );

            results.forEach(result => {
                if (result.status === 'fulfilled') {
                    successCount++;
                } else {
                    failCount++;
                    console.error('Failed to cache track:', result.reason);
                }
            });

            // Update progress (XSS-safe)
            const progress = Math.round(((i + batch.length) / tracks.length) * 100);
            if (downloadBtn) {
                downloadBtn.innerHTML = ''; // Clear
                const icon = document.createElement('i');
                icon.className = 'bi bi-hourglass-split me-2';
                const text = document.createTextNode(`${progress}%`);
                downloadBtn.appendChild(icon);
                downloadBtn.appendChild(text);
            }
        }

        // Restore button (XSS-safe)
        if (downloadBtn) {
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = ''; // Clear
            const icon = document.createElement('i');
            icon.className = 'bi bi-download me-2';
            const text = document.createTextNode('Downloaded');
            downloadBtn.appendChild(icon);
            downloadBtn.appendChild(text);
            
            // Reset after 3 seconds
            setTimeout(() => {
                downloadBtn.innerHTML = ''; // Clear
                const resetIcon = document.createElement('i');
                resetIcon.className = 'bi bi-download me-2';
                const resetText = document.createTextNode('Download for Offline');
                downloadBtn.appendChild(resetIcon);
                downloadBtn.appendChild(resetText);
            }, 3000);
        }

        if (failCount === 0) {
            this.showToast(`All ${successCount} tracks downloaded!`, 'success');
        } else {
            this.showToast(`Downloaded ${successCount} tracks, ${failCount} failed`, 'warning');
        }
    }

    /**
     * Cache a single audio file via service worker
     */
    async cacheAudioFile(path, quality) {
        if (!this.swRegistration || !this.swRegistration.active) {
            throw new Error('Service worker not active');
        }

        return new Promise((resolve, reject) => {
            const messageChannel = new MessageChannel();
            
            messageChannel.port1.onmessage = (event) => {
                if (event.data.success) {
                    resolve();
                } else {
                    reject(new Error(event.data.error));
                }
            };

            this.swRegistration.active.postMessage(
                {
                    action: 'CACHE_AUDIO',
                    data: { url: path, quality }
                },
                [messageChannel.port2]
            );
        });
    }

    /**
     * Show cache management modal
     */
    async showCacheManagement() {
        const cacheSize = await this.getCacheSize();
        
        const modal = new bootstrap.Modal(document.getElementById('cacheManagementModal'));
        
        // Update UI with cache info
        if (cacheSize) {
            document.getElementById('cache-usage').textContent = 
                this.formatBytes(cacheSize.usage);
            document.getElementById('cache-quota').textContent = 
                this.formatBytes(cacheSize.quota);
            document.getElementById('cache-percentage').textContent = 
                `${cacheSize.percentage}%`;
            
            // Update progress bar
            const progressBar = document.querySelector('#cache-progress .progress-bar');
            if (progressBar) {
                progressBar.style.width = `${cacheSize.percentage}%`;
                progressBar.textContent = `${cacheSize.percentage}%`;
            }
        }
        
        modal.show();
    }

    /**
     * Get cache size via service worker
     */
    async getCacheSize() {
        if (!this.swRegistration || !this.swRegistration.active) {
            return null;
        }

        return new Promise((resolve, reject) => {
            const messageChannel = new MessageChannel();
            
            messageChannel.port1.onmessage = (event) => {
                if (event.data.success) {
                    resolve(event.data.size);
                } else {
                    reject(new Error(event.data.error));
                }
            };

            this.swRegistration.active.postMessage(
                { action: 'GET_CACHE_SIZE' },
                [messageChannel.port2]
            );
        });
    }

    /**
     * Clear cache
     */
    async clearCache(type = 'audio') {
        if (!this.swRegistration || !this.swRegistration.active) {
            this.showToast('Service worker not available', 'danger');
            return;
        }

        const confirmed = confirm(`Clear ${type} cache? This will free up space but you'll need to download tracks again.`);
        if (!confirmed) return;

        return new Promise((resolve, reject) => {
            const messageChannel = new MessageChannel();
            
            messageChannel.port1.onmessage = (event) => {
                if (event.data.success) {
                    this.showToast('Cache cleared successfully', 'success');
                    resolve();
                } else {
                    this.showToast('Failed to clear cache', 'danger');
                    reject(new Error(event.data.error));
                }
            };

            this.swRegistration.active.postMessage(
                {
                    action: 'CLEAR_CACHE',
                    data: { type }
                },
                [messageChannel.port2]
            );
        });
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Create toast element using DOM methods (XSS-safe)
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0`;
        toastEl.setAttribute('role', 'alert');
        
        const toastFlex = document.createElement('div');
        toastFlex.className = 'd-flex';
        
        const toastBody = document.createElement('div');
        toastBody.className = 'toast-body';
        toastBody.textContent = message; // Use textContent (XSS-safe)
        
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close btn-close-white me-2 m-auto';
        closeButton.setAttribute('data-bs-dismiss', 'toast');
        
        toastFlex.appendChild(toastBody);
        toastFlex.appendChild(closeButton);
        toastEl.appendChild(toastFlex);

        // Add to toast container
        let container = document.getElementById('pwa-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'pwa-toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }

        container.appendChild(toastEl);

        // Show toast
        const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
        toast.show();

        // Remove from DOM after hidden
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    }

    /**
     * Format bytes to human readable string
     */
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
}

// Initialize PWA Manager when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.pwaManager = new PWAManager();
    });
} else {
    window.pwaManager = new PWAManager();
}

// Export for module use
export default PWAManager;
