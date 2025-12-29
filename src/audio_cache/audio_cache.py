"""
Audio transcoding and caching utilities for bandwidth optimization.

This module provides functionality to transcode large audio files (especially FLAC)
to smaller formats on-the-fly or via pre-caching, significantly reducing bandwidth
requirements during playback.
"""

import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Literal

from common.logging import Logger, NullLogger


QualityLevel = Literal["high", "medium", "low", "original"]

QUALITY_SETTINGS = {
    "high": {"bitrate": "256k", "format": "mp3"},
    "medium": {"bitrate": "192k", "format": "mp3"},
    "low": {"bitrate": "128k", "format": "mp3"},
}


class AudioCache:
    """
    Manages audio file transcoding and caching for bandwidth optimization.
    
    Provides methods to check for cached versions, generate transcoded files,
    and manage the cache directory.
    """

    def __init__(self, cache_dir: Path, logger: Logger | None = None):
        """
        Initialize the AudioCache manager.

        Args:
            cache_dir: Directory where cached transcoded files will be stored.
            logger: Optional logger for tracking operations.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or NullLogger()

    def _normalize_path(self, path: Path) -> str:
        """
        Normalize a path for consistent hashing.
        
        This ensures that the same file always produces the same hash,
        regardless of how the path was constructed.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized path string for hashing
        """
        try:
            # Try to resolve to absolute path
            normalized = path.resolve()
            return str(normalized)
        except Exception as e:
            # If resolve fails (e.g., file doesn't exist yet), use absolute
            self.logger.debug(f"Path resolve failed for {path}, using absolute: {e}")
            return str(path.absolute())

    def get_cache_path(
        self, original_path: Path, quality: QualityLevel = "medium"
    ) -> Path:
        """
        Generate a cache filename based on the original path and quality level.

        Args:
            original_path: Path to the original audio file.
            quality: Quality level for transcoding (high, medium, low).

        Returns:
            Path to the cached file location.
        """
        if quality == "original":
            return original_path

        # Create unique hash from the normalized file path
        path_str = self._normalize_path(original_path)
        path_hash = hashlib.md5(path_str.encode()).hexdigest()

        # Get quality settings
        settings = QUALITY_SETTINGS[quality]
        bitrate = settings["bitrate"]
        ext = settings["format"]

        cache_filename = f"{path_hash}_{quality}_{bitrate}.{ext}"
        
        # Log for debugging
        self.logger.debug(
            f"Cache path generation: {original_path.name} -> {cache_filename} "
            f"(hash of: {path_str})"
        )
        
        return self.cache_dir / cache_filename

    def should_transcode(self, file_path: Path) -> bool:
        """
        Determine if a file should be transcoded based on its format.

        Args:
            file_path: Path to the audio file.

        Returns:
            True if the file should be transcoded, False otherwise.
        """
        # Transcode lossless formats that are bandwidth-heavy
        transcode_formats = {".flac", ".wav", ".aiff", ".ape", ".alac"}
        return file_path.suffix.lower() in transcode_formats

    def is_cached(self, original_path: Path, quality: QualityLevel = "medium") -> bool:
        """
        Check if a cached version exists and is up-to-date.

        Args:
            original_path: Path to the original audio file.
            quality: Quality level to check.

        Returns:
            True if a valid cached version exists, False otherwise.
        """
        if quality == "original" or not self.should_transcode(original_path):
            return True

        cache_path = self.get_cache_path(original_path, quality)

        if not cache_path.exists():
            self.logger.debug(f"Cache miss: {cache_path.name} does not exist")
            return False

        # Check if cache is newer than original
        try:
            cache_mtime = cache_path.stat().st_mtime
            
            # Only check mtime if original file exists
            if original_path.exists():
                original_mtime = original_path.stat().st_mtime
                if cache_mtime < original_mtime:
                    self.logger.debug(
                        f"Cache outdated: {cache_path.name} is older than source"
                    )
                    return False
            
            self.logger.debug(f"Cache hit: {cache_path.name}")
            return True
            
        except OSError as e:
            self.logger.warning(f"Error checking cache status for {cache_path}: {e}")
            return False

    def transcode_file(
        self, 
        original_path: Path, 
        quality: QualityLevel = "medium",
        overwrite: bool = False
    ) -> Path:
        """
        Transcode an audio file to a cached version.

        Args:
            original_path: Path to the original audio file.
            quality: Quality level for transcoding.
            overwrite: If True, regenerate cache even if it exists.

        Returns:
            Path to the transcoded file (or original if no transcoding needed).

        Raises:
            subprocess.CalledProcessError: If ffmpeg transcoding fails.
            FileNotFoundError: If the original file doesn't exist.
        """
        if quality == "original" or not self.should_transcode(original_path):
            return original_path

        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_path}")

        cache_path = self.get_cache_path(original_path, quality)

        # Check if we need to transcode
        if not overwrite and self.is_cached(original_path, quality):
            self.logger.debug(f"Using existing cache: {cache_path}")
            return cache_path

        # Get transcoding settings
        settings = QUALITY_SETTINGS[quality]
        bitrate = settings["bitrate"]

        self.logger.info(f"Transcoding {original_path.name} to {quality} quality ({bitrate})")

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-i", str(original_path),
            "-vn",  # No video
            "-ar", "44100",  # Sample rate
            "-ac", "2",  # Stereo
            "-b:a", bitrate,  # Target bitrate
            "-map_metadata", "0",  # Copy metadata
            "-id3v2_version", "3",  # ID3v2.3 for better compatibility
            str(cache_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            self.logger.info(f"Successfully cached: {cache_path}")
            return cache_path

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Transcoding failed for {original_path}: {e.stderr}")
            # Clean up partial file if it exists
            if cache_path.exists():
                cache_path.unlink()
            raise

    def get_cached_or_original(
        self, original_path: Path, quality: QualityLevel = "medium"
    ) -> Path:
        """
        Get the cached version if available, otherwise return original path.

        This method does NOT generate a cache if it doesn't exist.
        Use transcode_file() for that purpose.

        Args:
            original_path: Path to the original audio file.
            quality: Quality level to retrieve.

        Returns:
            Path to cached version if available, otherwise original path.
        """
        if quality == "original" or not self.should_transcode(original_path):
            return original_path

        cache_path = self.get_cache_path(original_path, quality)

        if self.is_cached(original_path, quality):
            return cache_path

        return original_path

    def precache_file(
        self, 
        original_path: Path, 
        qualities: list[QualityLevel] = None
    ) -> dict[QualityLevel, Path]:
        """
        Pre-generate cached versions at multiple quality levels.

        Args:
            original_path: Path to the original audio file.
            qualities: List of quality levels to generate. Defaults to ["medium"].

        Returns:
            Dictionary mapping quality levels to their cached paths.
        """
        if qualities is None:
            qualities = ["medium"]

        results = {}

        for quality in qualities:
            if quality == "original":
                results[quality] = original_path
                continue

            try:
                cached_path = self.transcode_file(original_path, quality)
                results[quality] = cached_path
            except Exception as e:
                self.logger.error(f"Failed to precache {quality} version: {e}")
                results[quality] = original_path

        return results

    def get_cache_size(self) -> int:
        """
        Calculate total size of the cache directory in bytes.

        Returns:
            Total size in bytes.
        """
        total_size = 0
        for file_path in self.cache_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size

    def clear_cache(self, older_than_days: int | None = None) -> int:
        """
        Clear cached files, optionally only those older than specified days.

        Args:
            older_than_days: If specified, only delete files older than this many days.

        Returns:
            Number of files deleted.
        """
        import time

        deleted_count = 0
        current_time = time.time()

        for file_path in self.cache_dir.rglob("*.mp3"):
            if file_path.is_file():
                should_delete = True

                if older_than_days is not None:
                    file_age_days = (current_time - file_path.stat().st_mtime) / 86400
                    should_delete = file_age_days > older_than_days

                if should_delete:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        self.logger.debug(f"Deleted cached file: {file_path}")
                    except OSError as e:
                        self.logger.error(f"Failed to delete {file_path}: {e}")

        self.logger.info(f"Cache cleanup: deleted {deleted_count} files")
        return deleted_count
