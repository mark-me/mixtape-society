import time
from pathlib import Path
from threading import Lock, Timer
from typing import Dict, Tuple

from watchdog.events import FileSystemEventHandler


# Configuration constants
DEBOUNCE_DELAY = 2.0  # Seconds to wait after file change before indexing


class EnhancedWatcher(FileSystemEventHandler):
    """Enhanced file system watcher with debouncing to prevent corruption.

    This watcher prevents database corruption during bulk file editing by:
    1. Waiting DEBOUNCE_DELAY seconds after the last file change before indexing
    2. Coalescing multiple modifications to the same file into a single operation
    3. Properly flushing all pending events on shutdown

    Example:
        Without debouncing:
            Edit file.mp3 5 times rapidly → 5 index operations → corruption risk

        With debouncing:
            Edit file.mp3 5 times rapidly → wait 2 seconds → 1 index operation → safe

    Attributes:
        extractor: The CollectionExtractor instance that processes index/delete events.
        debounce_delay: Number of seconds to wait after last file change (default: 2.0).
        pending_events: Dict mapping file paths to their pending event type and timestamp.
        pending_lock: Thread lock for synchronizing access to pending events.
        timers: Dict mapping file paths to their active debounce timers.
    """

    def __init__(self, extractor) -> None:
        """Initializes the enhanced watcher with debouncing.

        Args:
            extractor: The CollectionExtractor instance that will handle the events.
        """
        self.extractor = extractor
        self.debounce_delay = DEBOUNCE_DELAY

        # Track pending events: path -> (event_type, timestamp)
        self.pending_events: Dict[str, Tuple[str, float]] = {}
        self.pending_lock = Lock()

        # Track active timers: path -> Timer
        self.timers: Dict[str, Timer] = {}

    def on_any_event(self, event: object) -> None:
        """Handles file system events with debouncing.

        This method ignores directory changes and unsupported file types, then
        applies debouncing to file modification and deletion events. Multiple
        rapid changes to the same file are coalesced into a single operation.

        Args:
            event: A watchdog file system event with is_directory, src_path,
                   and event_type attributes.
        """
        # Ignore directory changes
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Only process supported audio file extensions
        if path.suffix.lower() not in self.extractor.SUPPORTED_EXTS:
            return

        path_str = str(path)
        event_type = event.event_type

        with self.pending_lock:
            # Cancel any existing timer for this file
            if path_str in self.timers:
                self.timers[path_str].cancel()

            # Update pending event (this coalesces multiple events)
            if event_type in ("created", "modified"):
                # Both created and modified should result in reindexing
                self.pending_events[path_str] = ("modified", time.time())
            elif event_type == "deleted":
                # Delete takes precedence over everything
                self.pending_events[path_str] = ("deleted", time.time())

            # Set new debounce timer
            timer = Timer(
                self.debounce_delay,
                self._process_debounced_event,
                args=(path_str,)
            )
            self.timers[path_str] = timer
            timer.start()

    def _process_debounced_event(self, path_str: str) -> None:
        """Processes a debounced event after the delay period.

        This is called by the timer after debounce_delay seconds of inactivity
        on a particular file. It sends the coalesced event to the write queue.

        Args:
            path_str: String representation of the file path.
        """
        with self.pending_lock:
            # Get and remove the pending event
            if path_str not in self.pending_events:
                return

            event_type, _ = self.pending_events.pop(path_str)

            # Clean up timer reference
            if path_str in self.timers:
                del self.timers[path_str]

        # Import IndexEvent here to avoid circular imports
        from ._extractor import IndexEvent

        # Send to processing queue
        path = Path(path_str)

        if event_type == "modified":
            self.extractor._write_queue.put(IndexEvent("INDEX_FILE", path))
        elif event_type == "deleted":
            self.extractor._write_queue.put(IndexEvent("DELETE_FILE", path))

    def shutdown(self) -> None:
        """Cancels all pending timers and processes remaining events immediately.

        This ensures no events are lost when stopping the watcher. All pending
        events are flushed to the processing queue before shutdown completes.

        This method should be called before stopping the file system observer.
        """
        # Import IndexEvent here to avoid circular imports
        from ._extractor import IndexEvent

        with self.pending_lock:
            # Cancel all pending timers
            for timer in self.timers.values():
                timer.cancel()

            # Process all remaining pending events immediately
            for path_str, (event_type, _) in self.pending_events.items():
                path = Path(path_str)
                if event_type == "modified":
                    self.extractor._write_queue.put(IndexEvent("INDEX_FILE", path))
                elif event_type == "deleted":
                    self.extractor._write_queue.put(IndexEvent("DELETE_FILE", path))

            # Clear all state
            self.pending_events.clear()
            self.timers.clear()
