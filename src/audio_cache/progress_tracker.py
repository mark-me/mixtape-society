"""
Progress tracking for audio caching operations using Server-Sent Events (SSE).

This module provides real-time progress updates to the frontend during
long-running caching operations.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional
from queue import Queue, Empty
import threading

from common.logging import Logger, NullLogger


class ProgressStatus(Enum):
    """Represents the lifecycle state of a tracked caching operation or step.

    Encodes whether work is pending, actively running, completed, failed, or intentionally skipped.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProgressEvent:
    """Represents a single progress update for a tracked task.

    Captures the step name, status, human-readable message, and numeric progress so it can be streamed to clients.
    """
    task_id: str
    step: str
    status: ProgressStatus
    message: str
    current: int = 0
    total: int = 0
    timestamp: str = None

    def __post_init__(self):
        """Ensures each progress event has a timestamp.

        Automatically populates the timestamp with the current time when one is not provided.
        """
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        """Convert the progress event into a serializable dictionary.

        Produces a JSON-ready mapping with the status enum rendered as its string value.
        """
        data = asdict(self)
        data['status'] = self.status.value
        return data

    def to_sse(self):
        """Format the progress event as a Server-Sent Event payload.

        Produces a correctly structured SSE data line ready to be streamed to connected clients.
        """
        return f"data: {json.dumps(self.to_dict())}\n\n"


class ProgressTracker:
    """
    Tracks progress of long-running operations and broadcasts updates via SSE.

    Thread-safe implementation that allows multiple operations to report progress
    while clients listen for updates.
    """

    def __init__(self, logger: Logger | None = None):
        """Initializes a new progress tracker with optional logging.

        Sets up internal, thread-safe queues for tracking task-specific progress events that can be streamed to clients.

        Args:
            logger: Optional logger instance used to record progress tracker activity.
        """
        self.logger = logger or NullLogger()
        self._queues: dict[str, Queue] = {}
        self._lock = threading.Lock()

    def create_task(self, task_id: str) -> None:
        """
        Create a new task for tracking.

        Args:
            task_id: Unique identifier for this task (e.g., mixtape slug)
        """
        with self._lock:
            if task_id not in self._queues:
                self._queues[task_id] = Queue()
                self.logger.debug(f"Created progress task: {task_id}")

    def emit(
        self,
        task_id: str,
        step: str,
        status: ProgressStatus,
        message: str,
        current: int = 0,
        total: int = 0
    ) -> None:
        """
        Emit a progress event.

        Args:
            task_id: Task identifier
            step: Name of the current step (e.g., "saving", "caching_track")
            status: Current status
            message: Human-readable message
            current: Current progress count
            total: Total items to process
        """
        event = ProgressEvent(
            task_id=task_id,
            step=step,
            status=status,
            message=message,
            current=current,
            total=total
        )

        with self._lock:
            if task_id in self._queues:
                self._queues[task_id].put(event)
                self.logger.debug(f"[{task_id}] {step}: {message} ({current}/{total})")

    def listen(self, task_id: str, timeout: int = 300):
        """
        Generator that yields SSE-formatted progress events.

        Args:
            task_id: Task identifier to listen to
            timeout: Maximum time to wait for events (seconds)

        Yields:
            str: SSE-formatted event strings
        """
        self.create_task(task_id)

        start_time = time.time()

        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"

        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                self.logger.warning(f"Progress stream timeout for task: {task_id}")
                break

            try:
                with self._lock:
                    queue = self._queues.get(task_id)

                if queue is None:
                    break

                # Get event with short timeout to allow checking for completion
                event = queue.get(timeout=1)

                yield event.to_sse()

                # If task is completed or failed, clean up and stop
                if event.status in (ProgressStatus.COMPLETED, ProgressStatus.FAILED):
                    self.logger.debug(f"Task completed: {task_id}")
                    break

            except Empty:
                # Send keepalive
                yield ": keepalive\n\n"
                continue

        # Cleanup
        self.cleanup_task(task_id)

    def cleanup_task(self, task_id: str) -> None:
        """
        Remove a task and its queue.

        Args:
            task_id: Task identifier to clean up
        """
        with self._lock:
            if task_id in self._queues:
                del self._queues[task_id]
                self.logger.debug(f"Cleaned up progress task: {task_id}")


# Global progress tracker instance
_progress_tracker: Optional[ProgressTracker] = None


def get_progress_tracker(logger: Logger | None = None) -> ProgressTracker:
    """Get or create the global progress tracker instance."""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker(logger)
    return _progress_tracker


class ProgressCallback:
    """
    Callback wrapper for audio caching progress.

    Translates cache worker progress updates into SSE events.
    """

    def __init__(self, task_id: str, tracker: ProgressTracker, total_tracks: int):
        """
        Initialize the progress callback.

        Args:
            task_id: Task identifier
            tracker: ProgressTracker instance
            total_tracks: Total number of tracks to cache
        """
        self.task_id = task_id
        self.tracker = tracker
        self.total_tracks = total_tracks
        self.cached_count = 0
        self.skipped_count = 0
        self.failed_count = 0

    def __call__(self, current: int, total: int) -> None:
        """
        Called by cache worker with progress updates.

        Args:
            current: Current file number
            total: Total files to process
        """
        self.tracker.emit(
            task_id=self.task_id,
            step="caching",
            status=ProgressStatus.IN_PROGRESS,
            message=f"Caching track {current} of {total}",
            current=current,
            total=total
        )

    def track_cached(self, track_name: str) -> None:
        """Records that a track has been successfully cached.

        Increments the count of cached tracks and emits a progress event reflecting the updated completion state.

        Args:
            track_name: The display name or identifier of the cached track.
        """
        self.cached_count += 1
        self.tracker.emit(
            task_id=self.task_id,
            step="track_cached",
            status=ProgressStatus.IN_PROGRESS,
            message=f"✓ Cached: {track_name}",
            current=self.cached_count,
            total=self.total_tracks
        )

    def track_skipped(self, track_name: str, reason: str = "already cached") -> None:
        """Records that a track was intentionally skipped during caching.

        Increments the skipped count and emits a progress event explaining why the track was not processed.

        Args:
            track_name: The display name or identifier of the skipped track.
            reason: Human-readable explanation for why the track was skipped.
        """
        self.skipped_count += 1
        self.tracker.emit(
            task_id=self.task_id,
            step="track_skipped",
            status=ProgressStatus.SKIPPED,
            message=f"⊘ Skipped: {track_name} ({reason})",
            current=self.cached_count + self.skipped_count,
            total=self.total_tracks
        )

    def track_failed(self, track_name: str, error: str) -> None:
        """Records that caching a track has failed.

        Increments the failed count and emits a progress event describing the error that occurred.

        Args:
            track_name: The display name or identifier of the track that failed to cache.
            error: Human-readable error description explaining the failure.
        """
        self.failed_count += 1
        self.tracker.emit(
            task_id=self.task_id,
            step="track_failed",
            status=ProgressStatus.FAILED,
            message=f"✗ Failed: {track_name} - {error}",
            current=self.cached_count + self.skipped_count + self.failed_count,
            total=self.total_tracks
        )
