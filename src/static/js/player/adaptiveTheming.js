// static/js/player/adaptiveTheming.js

/**
 * Adaptive theming system that extracts colors from mixtape cover art
 * and applies them to the semantic color system while respecting light/dark mode
 */

/**
 * Configuration for gradient intensity
 * Adjust these values to make gradients more or less subtle
 */
const GRADIENT_CONFIG = {
    light: {
        artist: 0.15,   // 15% opacity (moderate for light mode)
        album: 0.12,    // 12% opacity
        track: 0.10     // 10% opacity
    },
    dark: {
        artist: 0.20,   // 20% opacity (moderate for dark mode)
        album: 0.16,    // 16% opacity
        track: 0.12     // 12% opacity
    }
};

/**
 * Default fallback colors (from base.css)
 */
const FALLBACK_COLORS = {
    light: {
        artist: '#8b3a3a',
        album: '#1e3a5f',
        track: '#2d5a3d'
    },
    dark: {
        artist: '#c65d5d',
        album: '#4a6fa5',
        track: '#4a8c5f'
    }
};

/**
 * Converts hex color to RGB object
 */
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

/**
 * Converts RGB to hex
 */
function rgbToHex(r, g, b) {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

/**
 * Calculates relative luminance for WCAG contrast calculations
 */
function getLuminance(r, g, b) {
    const [rs, gs, bs] = [r, g, b].map(c => {
        c = c / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculates contrast ratio between two colors
 */
function getContrastRatio(rgb1, rgb2) {
    const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b);
    const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b);
    const lighter = Math.max(lum1, lum2);
    const darker = Math.min(lum1, lum2);
    return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Adjusts color brightness for better contrast
 */
function adjustColorForMode(rgb, isDark, targetContrast = 4.5) {
    const bgColor = isDark ? { r: 33, g: 37, b: 41 } : { r: 255, g: 255, b: 255 };
    let adjusted = { ...rgb };
    let contrast = getContrastRatio(adjusted, bgColor);

    // If contrast is already good, return as-is
    if (contrast >= targetContrast) {
        return adjusted;
    }

    // Adjust brightness
    const step = isDark ? 1.15 : 0.85;
    const maxIterations = 20;
    let iterations = 0;

    while (contrast < targetContrast && iterations < maxIterations) {
        if (isDark) {
            // Make lighter for dark mode
            adjusted.r = Math.min(255, Math.round(adjusted.r * step));
            adjusted.g = Math.min(255, Math.round(adjusted.g * step));
            adjusted.b = Math.min(255, Math.round(adjusted.b * step));
        } else {
            // Make darker for light mode
            adjusted.r = Math.max(0, Math.round(adjusted.r * step));
            adjusted.g = Math.max(0, Math.round(adjusted.g * step));
            adjusted.b = Math.max(0, Math.round(adjusted.b * step));
        }
        contrast = getContrastRatio(adjusted, bgColor);
        iterations++;
    }

    return adjusted;
}

/**
 * Creates hover variant (slightly lighter or darker)
 */
function createHoverVariant(hex, isDark) {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;

    const factor = isDark ? 1.2 : 1.15;
    const r = Math.min(255, Math.round(rgb.r * factor));
    const g = Math.min(255, Math.round(rgb.g * factor));
    const b = Math.min(255, Math.round(rgb.b * factor));

    return rgbToHex(r, g, b);
}

/**
 * Creates active variant (darker)
 */
function createActiveVariant(hex) {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;

    const factor = 0.85;
    const r = Math.max(0, Math.round(rgb.r * factor));
    const g = Math.max(0, Math.round(rgb.g * factor));
    const b = Math.max(0, Math.round(rgb.b * factor));

    return rgbToHex(r, g, b);
}

/**
 * Creates subtle background variant with transparency
 */
function createSubtleVariant(hex) {
    const rgb = hexToRgb(hex);
    if (!rgb) return `rgba(0, 0, 0, 0.12)`;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.12)`;
}

/**
 * Creates border variant with transparency
 */
function createBorderVariant(hex) {
    const rgb = hexToRgb(hex);
    if (!rgb) return `rgba(0, 0, 0, 0.35)`;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.35)`;
}

/**
 * Creates text emphasis variant (slightly lighter/darker than main)
 */
function createTextEmphasisVariant(hex, isDark) {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;

    const factor = isDark ? 1.12 : 0.75;
    const r = isDark ? Math.min(255, Math.round(rgb.r * factor)) : Math.max(0, Math.round(rgb.r * factor));
    const g = isDark ? Math.min(255, Math.round(rgb.g * factor)) : Math.max(0, Math.round(rgb.g * factor));
    const b = isDark ? Math.min(255, Math.round(rgb.b * factor)) : Math.max(0, Math.round(rgb.b * factor));

    return rgbToHex(r, g, b);
}

/**
 * Creates a subtle background gradient from extracted colors
 */
function createBackgroundGradient(colors, isDark) {
    const rgb1 = hexToRgb(colors.artist);
    const rgb2 = hexToRgb(colors.album);
    const rgb3 = hexToRgb(colors.track);

    if (!rgb1 || !rgb2 || !rgb3) return null;

    // Get opacity values from config
    const opacities = isDark ? GRADIENT_CONFIG.dark : GRADIENT_CONFIG.light;

    // Create subtle radial gradients from corners
    return `
        radial-gradient(circle at 0% 0%, rgba(${rgb1.r}, ${rgb1.g}, ${rgb1.b}, ${opacities.artist}) 0%, transparent 50%),
        radial-gradient(circle at 100% 0%, rgba(${rgb2.r}, ${rgb2.g}, ${rgb2.b}, ${opacities.album}) 0%, transparent 50%),
        radial-gradient(circle at 50% 100%, rgba(${rgb3.r}, ${rgb3.g}, ${rgb3.b}, ${opacities.track}) 0%, transparent 50%)
    `.replace(/\s+/g, ' ').trim();
}

/**
 * Applies color scheme to CSS custom properties
 */
function applyColorScheme(colors, isDark) {
    const root = document.documentElement;

    // Apply each semantic color type
    Object.keys(colors).forEach(type => {
        const baseColor = colors[type];
        const rgb = hexToRgb(baseColor);

        // Set all variants
        root.style.setProperty(`--color-${type}`, baseColor);
        root.style.setProperty(`--color-${type}-rgb`, `${rgb.r}, ${rgb.g}, ${rgb.b}`);
        root.style.setProperty(`--color-${type}-hover`, createHoverVariant(baseColor, isDark));
        root.style.setProperty(`--color-${type}-active`, createActiveVariant(baseColor));
        root.style.setProperty(`--color-${type}-bg-subtle`, createSubtleVariant(baseColor));
        root.style.setProperty(`--color-${type}-border-subtle`, createBorderVariant(baseColor));
        root.style.setProperty(`--color-${type}-text-emphasis`, createTextEmphasisVariant(baseColor, isDark));
    });

    // Apply background gradient
    const gradient = createBackgroundGradient(colors, isDark);
    if (gradient) {
        root.style.setProperty('--adaptive-bg-gradient', gradient);
        document.body.style.backgroundImage = gradient;
    } else {
        if (window.__ADAPTIVE_THEME_DEBUG__) {
            console.warn('⚠️ Failed to create background gradient');
        }
    }

    // Force audio player to use track color
    const audioPlayer = document.getElementById('main-player');
    if (audioPlayer) {
        audioPlayer.style.accentColor = colors.track;
    }
}

/**
 * Extracts colors from image and applies theme
 */
async function extractAndApplyColors(imgElement) {
    try {
        // Check if Vibrant is available
        if (typeof Vibrant === 'undefined') {
            console.warn('Vibrant.js not loaded, using fallback colors');
            applyFallbackColors();
            return;
        }

        // Get current theme
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';

        // Extract palette
        const palette = await Vibrant.from(imgElement).getPalette();

        // Select best colors for each semantic type
        let colors = {};

        if (isDark) {
            // Dark mode: prefer vibrant, light-muted colors
            colors.artist = palette.LightVibrant?.hex ||
                           palette.Vibrant?.hex ||
                           palette.LightMuted?.hex ||
                           FALLBACK_COLORS.dark.artist;

            colors.album = palette.Vibrant?.hex ||
                          palette.DarkVibrant?.hex ||
                          palette.Muted?.hex ||
                          FALLBACK_COLORS.dark.album;

            colors.track = palette.LightMuted?.hex ||
                          palette.Muted?.hex ||
                          palette.DarkMuted?.hex ||
                          FALLBACK_COLORS.dark.track;
        } else {
            // Light mode: prefer darker, muted colors
            colors.artist = palette.DarkVibrant?.hex ||
                           palette.Vibrant?.hex ||
                           palette.DarkMuted?.hex ||
                           FALLBACK_COLORS.light.artist;

            colors.album = palette.DarkMuted?.hex ||
                          palette.Muted?.hex ||
                          palette.DarkVibrant?.hex ||
                          FALLBACK_COLORS.light.album;

            colors.track = palette.Muted?.hex ||
                          palette.DarkMuted?.hex ||
                          palette.DarkVibrant?.hex ||
                          FALLBACK_COLORS.light.track;
        }

        // Adjust colors for proper contrast
        Object.keys(colors).forEach(type => {
            const rgb = hexToRgb(colors[type]);
            if (rgb) {
                const adjusted = adjustColorForMode(rgb, isDark);
                colors[type] = rgbToHex(adjusted.r, adjusted.g, adjusted.b);
            }
        });

        // Apply the color scheme
        applyColorScheme(colors, isDark);

    } catch (error) {
        console.error('Failed to extract colors from cover art:', error);
        applyFallbackColors();
    }
}

/**
 * Applies fallback colors based on current theme
 */
function applyFallbackColors() {
    const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    const colors = isDark ? FALLBACK_COLORS.dark : FALLBACK_COLORS.light;
    applyColorScheme(colors, isDark);
    console.log('🎨 Using fallback colors for', isDark ? 'dark' : 'light', 'mode');
}

/**
 * Initializes adaptive theming
 */
export function initAdaptiveTheming() {
    // Find mixtape cover image
    const coverImg = document.querySelector('.img-fluid.rounded.shadow');

    if (!coverImg) {
        console.log('No mixtape cover found, using fallback colors');
        applyFallbackColors();
        return;
    }

    // Apply colors when image is loaded
    if (coverImg.complete) {
        extractAndApplyColors(coverImg);
    } else {
        coverImg.addEventListener('load', () => extractAndApplyColors(coverImg));
    }

    // Re-apply colors when theme changes
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'data-bs-theme') {
                if (coverImg.complete) {
                    extractAndApplyColors(coverImg);
                }
            }
        });
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-bs-theme']
    });

}
