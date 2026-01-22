# Toast Queue System - Complete Implementation

## Overview

A comprehensive toast notification system with:
- ✅ **Queue management** - Multiple toasts don't replace each other
- ✅ **Different toast types** - Success, Info, Warning, Error
- ✅ **Action buttons** - Add clickable actions to toasts
- ✅ **Auto-hide control** - Configure per toast
- ✅ **Programmatic control** - Dismiss toasts via API
- ✅ **Clean animations** - Smooth show/hide transitions

## Features

### 1. Queue Management

**Before:** New toasts replaced existing ones
```javascript
// User clicks next rapidly
showToast('Track 1 playing');  // Shown
showToast('Track 2 playing');  // Replaces Track 1 ❌
showToast('Track 3 playing');  // Replaces Track 2 ❌
// Only see Track 3!
```

**After:** Toasts queue and show sequentially
```javascript
showToast('Track 1 playing');  // Shows first
showToast('Track 2 playing');  // Queues, shows after Track 1
showToast('Track 3 playing');  // Queues, shows after Track 2
// See all 3 notifications! ✅
```

### 2. Toast Types

Four built-in types with distinct styling:

#### SUCCESS ✅
- **Icon:** Green check circle
- **Color:** Green background, white text
- **Duration:** 3 seconds (auto-hide)
- **Use for:** Successful operations

```javascript
showSuccessToast('Track added to queue');
showSuccessToast('Playlist saved successfully');
```

#### INFO ℹ️
- **Icon:** Blue info circle
- **Color:** Blue background, white text
- **Duration:** 4 seconds (auto-hide)
- **Use for:** Informational messages

```javascript
showInfoToast('Buffering track...');
showInfoToast('Shuffle enabled');
```

#### WARNING ⚠️
- **Icon:** Yellow exclamation circle
- **Color:** Yellow background, dark text
- **Duration:** 5 seconds (auto-hide)
- **Use for:** Non-critical issues

```javascript
showWarningToast('Slow network detected');
showWarningToast('Cache nearly full');
```

#### ERROR ❌
- **Icon:** Red triangle exclamation
- **Color:** Red background, white text
- **Duration:** 8 seconds (no auto-hide by default)
- **Use for:** Errors and failures

```javascript
showErrorToast('Playback failed');
showErrorToast('Unable to load track');
```

### 3. Action Buttons

Add interactive buttons to toasts:

```javascript
showErrorToast('Playback error', {
    actions: [
        {
            label: 'Retry',
            handler: () => retryPlayback(),
            primary: true  // Primary button styling
        },
        {
            label: 'Skip',
            handler: () => skipTrack()
        }
    ]
});
```

**Features:**
- Multiple buttons per toast
- Primary/secondary styling
- Auto-dismiss after action
- Custom handlers

### 4. Auto-Hide Control

Control whether toasts auto-dismiss:

```javascript
// Auto-hide after 5 seconds (default for warnings)
showWarningToast('Network slow');

// Never auto-hide (stay until manually dismissed)
showErrorToast('Critical error', { autohide: false });

// Custom duration
showInfoToast('Processing...', { duration: 10000 });
```

### 5. Programmatic Control

Dismiss toasts programmatically:

```javascript
const toast = showInfoToast('Loading...');

// Dismiss after operation completes
fetch('/api/data')
    .then(() => {
        toast.dismiss();
        showSuccessToast('Loaded!');
    })
    .catch(() => {
        toast.dismiss();
        showErrorToast('Failed');
    });
```

## API Reference

### Core Function

```javascript
showToast(message, options)
```

**Parameters:**
- `message` (string): The message to display
- `options` (object):
  - `type` (string): 'success', 'info', 'warning', 'error'
  - `duration` (number): Duration in milliseconds
  - `autohide` (boolean): Whether to auto-hide
  - `actions` (array): Array of action button objects

**Returns:** Toast control object with `dismiss()` method

### Convenience Functions

```javascript
showSuccessToast(message, options)
showInfoToast(message, options)
showWarningToast(message, options)
showErrorToast(message, options)
```

All accept same parameters as `showToast()` but with `type` pre-set.

### Compatibility Wrapper

```javascript
showPlaybackErrorToast(message, { isTerminal, onSkip })
```

Backward-compatible wrapper for existing error handler code.

**Parameters:**
- `message` (string): Error message
- `isTerminal` (boolean): If true, doesn't auto-hide
- `onSkip` (function): Handler for Skip button

## Usage Examples

### Basic Usage

```javascript
// Simple success message
showSuccessToast('Track added to playlist');

// Info with custom duration
showInfoToast('Buffering...', { duration: 2000 });

// Warning
showWarningToast('Low battery detected');

// Error that stays visible
showErrorToast('Critical failure', { autohide: false });
```

### With Action Buttons

```javascript
// Single action
showWarningToast('Update available', {
    actions: [
        { label: 'Update', handler: () => startUpdate(), primary: true }
    ]
});

// Multiple actions
showErrorToast('Network error', {
    actions: [
        { label: 'Retry', handler: () => retry(), primary: true },
        { label: 'Offline Mode', handler: () => goOffline() }
    ]
});
```

### Programmatic Control

```javascript
// Show loading toast
const loadingToast = showInfoToast('Loading track...');

// Operation
loadTrack()
    .then(() => {
        loadingToast.dismiss();
        showSuccessToast('Track loaded');
    })
    .catch(err => {
        loadingToast.dismiss();
        showErrorToast(`Failed: ${err.message}`);
    });
```

### Real-World Scenarios

#### Scenario 1: Quality Change
```javascript
const changeQuality = (newQuality) => {
    currentQuality = newQuality;
    updatePlayer();
    
    // Show success toast
    showSuccessToast(`Quality changed to ${newQuality}`);
};
```

#### Scenario 2: Track Skip with Feedback
```javascript
const skipTrack = () => {
    const trackName = getCurrentTrackName();
    playNextTrack();
    
    // Show info toast
    showInfoToast(`Skipped: ${trackName}`);
};
```

#### Scenario 3: Error with Recovery
```javascript
const handlePlaybackError = (error) => {
    showErrorToast(`Playback failed: ${error.message}`, {
        autohide: false,
        actions: [
            {
                label: 'Retry',
                handler: () => retryPlayback(),
                primary: true
            },
            {
                label: 'Skip',
                handler: () => skipToNext()
            },
            {
                label: 'Report',
                handler: () => reportError(error)
            }
        ]
    });
};
```

#### Scenario 4: Queue Multiple Operations
```javascript
// Add multiple tracks
tracks.forEach(track => {
    addToQueue(track);
    showSuccessToast(`Added: ${track.name}`);
});
// All toasts show in sequence!
```

#### Scenario 5: Progressive Loading
```javascript
const loadPlaylist = async () => {
    const loading = showInfoToast('Loading playlist...');
    
    try {
        await fetchTracks();
        loading.dismiss();
        showInfoToast('Analyzing tracks...');
        
        await analyzeTracks();
        showSuccessToast('Playlist ready!');
    } catch (err) {
        loading.dismiss();
        showErrorToast('Failed to load playlist');
    }
};
```

## Integration Guide

### Step 1: Add Toast Constants

Add near the top of your file (after other constants):

```javascript
// Toast notification system
const TOAST_TYPES = {
    SUCCESS: 'success',
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'error'
};

const TOAST_CONFIG = {
    [TOAST_TYPES.SUCCESS]: {
        icon: 'bi-check-circle-fill',
        bgClass: 'bg-success',
        textClass: 'text-white',
        duration: 3000
    },
    [TOAST_TYPES.INFO]: {
        icon: 'bi-info-circle-fill',
        bgClass: 'bg-info',
        textClass: 'text-white',
        duration: 4000
    },
    [TOAST_TYPES.WARNING]: {
        icon: 'bi-exclamation-circle-fill',
        bgClass: 'bg-warning',
        textClass: 'text-dark',
        duration: 5000
    },
    [TOAST_TYPES.ERROR]: {
        icon: 'bi-exclamation-triangle-fill',
        bgClass: 'bg-danger',
        textClass: 'text-white',
        duration: 8000,
        autohide: false
    }
};

// Toast queue management
let toastQueue = [];
let currentToast = null;
let toastIdCounter = 0;
```

### Step 2: Add Toast Functions

Insert the complete toast system functions (from toast-queue-system.js).

### Step 3: Replace Existing Calls

Replace old alert/toast calls:

**Before:**
```javascript
alert('Error occurred');
showQualityToast('Quality changed');
showPlaybackErrorToast('Playback failed', { isTerminal: true });
```

**After:**
```javascript
showErrorToast('Error occurred');
showSuccessToast('Quality changed');
showErrorToast('Playback failed', { autohide: false });
```

### Step 4: Update Quality Change

```javascript
const changeQuality = (newQuality) => {
    currentQuality = newQuality;
    // ... update logic ...
    
    // Replace old showQualityToast
    showSuccessToast(`Quality changed to ${QUALITY_LEVELS[newQuality].label}`);
};
```

### Step 5: Test

```javascript
// Test all types
showSuccessToast('Success test');
showInfoToast('Info test');
showWarningToast('Warning test');
showErrorToast('Error test');

// Test queue
showInfoToast('First');
showInfoToast('Second');
showInfoToast('Third');
// Should see all 3 in sequence

// Test actions
showErrorToast('Test error', {
    actions: [
        { label: 'Action 1', handler: () => console.log('1') },
        { label: 'Action 2', handler: () => console.log('2') }
    ]
});
```

## Styling

Toasts use Bootstrap classes and are positioned at bottom-right by default.

**Container:**
```css
#toast-container {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1060;
    max-width: 400px;
}
```

**Customization:**
Modify toast positioning in the `displayToast()` function:

```javascript
// Top-right
container.style.top = '20px';
container.style.right = '20px';

// Top-center
container.style.top = '20px';
container.style.left = '50%';
container.style.transform = 'translateX(-50%)';

// Bottom-center
container.style.bottom = '20px';
container.style.left = '50%';
container.style.transform = 'translateX(-50%)';
```

## Queue Behavior

### Sequential Display

Toasts show one at a time in order:
```
Queue: [Toast1, Toast2, Toast3]
       ↓
Show Toast1 → Auto-hide after 3s
       ↓
Show Toast2 → Auto-hide after 4s
       ↓
Show Toast3 → Auto-hide after 5s
```

### Manual Dismiss

User can dismiss current toast early:
```
Showing Toast1 (4s remaining)
User clicks X
       ↓
Toast1 dismissed
       ↓
Toast2 shows immediately (doesn't wait)
```

### Programmatic Dismiss

```javascript
const toast1 = showInfoToast('Processing...');
const toast2 = showInfoToast('Analyzing...');

// Dismiss specific toast
toast1.dismiss();  // Toast2 shows next

// If toast not current, removed from queue
toast2.dismiss();  // Removed from queue, never shows
```

## Error Handling

### Graceful Degradation

If Bootstrap isn't available, toasts still work:
- Falls back to native DOM styling
- Same functionality
- Slightly different appearance

### Container Cleanup

Toast container auto-created on first use:
```javascript
if (!container) {
    container = document.createElement('div');
    // ... setup ...
    document.body.appendChild(container);
}
```

### Memory Management

Toasts are properly cleaned up:
- Elements removed from DOM after animation
- Timeouts cleared on manual dismiss
- Queue processed sequentially

## Performance

**Lightweight:**
- ~10KB unminified
- No external dependencies (uses Bootstrap classes)
- Minimal DOM manipulation
- Efficient queue processing

**Optimizations:**
- Single container for all toasts
- Reuses toast element pattern
- Cleanup after each toast
- No memory leaks

## Accessibility

**ARIA Support:**
```html
<div role="alert" aria-live="assertive" aria-atomic="true">
    <!-- Toast content -->
</div>
```

**Keyboard Accessible:**
- Close button is focusable
- Action buttons are keyboard accessible
- Tab navigation works

**Screen Reader Friendly:**
- `role="alert"` announces toasts
- `aria-live="assertive"` for important messages
- Descriptive labels on buttons

## Migration Guide

### From `alert()`

**Before:**
```javascript
if (error) {
    alert('An error occurred');
}
```

**After:**
```javascript
if (error) {
    showErrorToast('An error occurred');
}
```

### From Custom Toast

**Before:**
```javascript
showQualityToast(quality);  // Custom function
```

**After:**
```javascript
showSuccessToast(`Quality: ${quality}`);
```

### From showPlaybackErrorToast

**Before:**
```javascript
showPlaybackErrorToast('Error', {
    isTerminal: true,
    onSkip: () => skip()
});
```

**After (Option 1 - Direct):**
```javascript
showErrorToast('Error', {
    autohide: false,
    actions: [
        { label: 'Skip', handler: () => skip(), primary: true }
    ]
});
```

**After (Option 2 - Wrapper):**
```javascript
// Keep existing calls - wrapper handles conversion
showPlaybackErrorToast('Error', {
    isTerminal: true,
    onSkip: () => skip()
});
```

## Summary

### Benefits

✅ **Better UX:** Queue prevents message loss  
✅ **Consistent:** Unified notification system  
✅ **Flexible:** Multiple types and options  
✅ **Interactive:** Action buttons for common tasks  
✅ **Controllable:** Programmatic dismiss  
✅ **Professional:** Polished animations  
✅ **Accessible:** ARIA support  
✅ **Maintainable:** Single implementation  

### Use Cases

- **Success:** Operations completed successfully
- **Info:** Status updates, progress
- **Warning:** Non-critical issues
- **Error:** Failures with recovery options

### Best Practices

1. **Choose appropriate type** - Match severity to message
2. **Keep messages brief** - One sentence max
3. **Provide actions** - Make errors actionable
4. **Use auto-hide wisely** - Errors shouldn't auto-hide
5. **Don't spam** - Queue naturally, but consider debouncing rapid events
6. **Test the queue** - Ensure messages don't pile up excessively

---

**Status**: ✅ Complete Implementation  
**Files**: toast-queue-system.js  
**Dependencies**: Bootstrap 5 (for styling)  
**Browser Support**: All modern browsers  
**Production Ready**: Yes
