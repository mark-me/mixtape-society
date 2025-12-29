"""
Background tasks for pre-caching audio files in mixtapes.

This module provides utilities to pre-generate cached versions of audio files
when mixtapes are created or updated, ensuring smooth playback without
on-demand transcoding delays.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from audio_cache import AudioCache, QualityLevel
from common.logging import Logger, NullLogger


class CacheWorker:
    """
    Worker for pre-caching audio files in the background.
    
    Provides methods to cache individual files or entire mixtapes at specified
    quality levels using thread pools for parallel processing.
    """

    def __init__(
        self,
        audio_cache: AudioCache,
        logger: Logger | None = None,
        max_workers: int = 4,
    ):
        """
        Initialize the cache worker.

        Args:
            audio_cache: AudioCache instance for transcoding operations.
            logger: Optional logger for tracking operations.
            max_workers: Maximum number of parallel transcoding threads.
        """
        self.audio_cache = audio_cache
        self.logger = logger or NullLogger()
        self.max_workers = max_workers

    def cache_single_file(
        self,
        file_path: Path,
        qualities: list[QualityLevel] = None,
    ) -> dict[QualityLevel, bool]:
        """
        Cache a single audio file at specified quality levels.

        Args:
            file_path: Path to the audio file.
            qualities: List of quality levels to cache. Defaults to ["medium"].

        Returns:
            Dictionary mapping quality levels to success status.
        """
        if qualities is None:
            qualities = ["medium"]

        results = {}

        for quality in qualities:
            if quality == "original":
                results[quality] = True
                continue

            try:
                self.audio_cache.transcode_file(file_path, quality)
                results[quality] = True
                self.logger.info(f"Cached {file_path.name} at {quality} quality")
            except Exception as e:
                results[quality] = False
                self.logger.error(f"Failed to cache {file_path.name} at {quality}: {e}")

        return results

    def cache_mixtape(
        self,
        track_paths: list[Path],
        qualities: list[QualityLevel] = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict]:
        """
        Cache all audio files in a mixtape.

        Args:
            track_paths: List of paths to audio files in the mixtape.
            qualities: Quality levels to cache. Defaults to ["medium"].
            progress_callback: Optional callback function(current, total) for progress updates.

        Returns:
            Dictionary with results for each file.
        """
        if qualities is None:
            qualities = ["medium"]

        total_files = len(track_paths)
        results = {}

        self.logger.info(
            f"Starting cache generation for {total_files} tracks at {qualities} quality levels"
        )

        for idx, file_path in enumerate(track_paths, 1):
            if not self.audio_cache.should_transcode(file_path):
                self.logger.debug(f"Skipping {file_path.name} (no transcoding needed)")
                results[str(file_path)] = {"skipped": True}
                continue

            file_results = self.cache_single_file(file_path, qualities)
            results[str(file_path)] = file_results

            if progress_callback:
                progress_callback(idx, total_files)

        self.logger.info(f"Cache generation complete for {total_files} tracks")
        return results

    def cache_mixtape_async(
        self,
        track_paths: list[Path],
        qualities: list[QualityLevel] = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict]:
        """
        Cache all audio files in a mixtape using parallel processing.

        Args:
            track_paths: List of paths to audio files in the mixtape.
            qualities: Quality levels to cache. Defaults to ["medium"].
            progress_callback: Optional callback function(current, total) for progress updates.

        Returns:
            Dictionary with results for each file.
        """
        if qualities is None:
            qualities = ["medium"]

        # Filter files that need transcoding
        files_to_cache = [
            path for path in track_paths if self.audio_cache.should_transcode(path)
        ]

        total_files = len(files_to_cache)
        if total_files == 0:
            self.logger.info("No files need transcoding")
            return {}

        results = {}
        completed = 0

        self.logger.info(
            f"Starting parallel cache generation for {total_files} tracks "
            f"at {qualities} quality levels (max workers: {self.max_workers})"
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_path = {
                executor.submit(self.cache_single_file, path, qualities): path
                for path in files_to_cache
            }

            # Process completed jobs
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed += 1

                try:
                    file_results = future.result()
                    results[str(path)] = file_results
                    self.logger.debug(
                        f"[{completed}/{total_files}] Cached {path.name}"
                    )
                except Exception as e:
                    results[str(path)] = {"error": str(e)}
                    self.logger.error(f"Failed to cache {path.name}: {e}")

                if progress_callback:
                    progress_callback(completed, total_files)

        self.logger.info(f"Parallel cache generation complete for {total_files} tracks")
        return results

    def verify_mixtape_cache(
        self, track_paths: list[Path], quality: QualityLevel = "medium"
    ) -> dict[str, bool]:
        """
        Verify which tracks in a mixtape have valid cached versions.

        Args:
            track_paths: List of paths to audio files in the mixtape.
            quality: Quality level to check.

        Returns:
            Dictionary mapping file paths to cache availability status.
        """
        results = {}

        for path in track_paths:
            if not self.audio_cache.should_transcode(path):
                results[str(path)] = True  # Original file, no cache needed
            else:
                results[str(path)] = self.audio_cache.is_cached(path, quality)

        return results

    def regenerate_outdated_cache(
        self, track_paths: list[Path], qualities: list[QualityLevel] = None
    ) -> dict[str, dict]:
        """
        Regenerate cached versions that are older than their source files.

        Args:
            track_paths: List of paths to audio files.
            qualities: Quality levels to regenerate.

        Returns:
            Dictionary with regeneration results for each file.
        """
        if qualities is None:
            qualities = ["medium"]

        files_to_regenerate = []

        for path in track_paths:
            if not self.audio_cache.should_transcode(path):
                continue

            # Check each quality level
            for quality in qualities:
                if not self.audio_cache.is_cached(path, quality):
                    files_to_regenerate.append((path, quality))
                    self.logger.info(
                        f"Cache outdated or missing: {path.name} at {quality}"
                    )

        if not files_to_regenerate:
            self.logger.info("All caches are up-to-date")
            return {}

        results = {}

        for path, quality in files_to_regenerate:
            try:
                self.audio_cache.transcode_file(path, quality, overwrite=True)
                key = f"{path}_{quality}"
                results[key] = {"success": True}
                self.logger.info(f"Regenerated cache: {path.name} at {quality}")
            except Exception as e:
                key = f"{path}_{quality}"
                results[key] = {"success": False, "error": str(e)}
                self.logger.error(f"Failed to regenerate {path.name}: {e}")

        return results


def schedule_mixtape_caching(
    mixtape_tracks: list[dict],
    music_root: Path,
    audio_cache: AudioCache,
    logger: Logger | None = None,
    qualities: list[QualityLevel] = None,
    async_mode: bool = True,
) -> dict:
    """
    Convenience function to schedule caching for a mixtape's tracks.

    Args:
        mixtape_tracks: List of track dictionaries with 'path' keys.
        music_root: Root directory for music files.
        audio_cache: AudioCache instance.
        logger: Optional logger.
        qualities: Quality levels to cache. Defaults to ["medium"].
        async_mode: If True, use parallel processing.

    Returns:
        Dictionary with caching results.
    """
    if qualities is None:
        qualities = ["medium"]

    # Convert track dictionaries to Path objects
    track_paths = [music_root / track["path"] for track in mixtape_tracks]

    # Filter out non-existent files
    valid_paths = [path for path in track_paths if path.exists()]

    if len(valid_paths) < len(track_paths):
        missing = len(track_paths) - len(valid_paths)
        if logger:
            logger.warning(f"{missing} track files not found, skipping")

    # Create worker and cache files
    worker = CacheWorker(audio_cache, logger)

    if async_mode:
        return worker.cache_mixtape_async(valid_paths, qualities)
    else:
        return worker.cache_mixtape(valid_paths, qualities)
