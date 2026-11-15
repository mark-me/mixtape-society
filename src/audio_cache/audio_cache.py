"""
Audio transcoding and caching utilities for bandwidth optimization.

This module provides functionality to transcode large audio files (especially FLAC)
to smaller formats on-the-fly or via pre-caching, significantly reducing bandwidth
requirements during playback.
"""

import hashlib
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from common.logging import Logger, NullLogger


QualityLevel = Literal["high", "medium", "low", "cassette", "original"]

# The sound of a TDK D90 cassette (1995-1997): tape hiss, wow and flutter, the narrower
# frequency range of tape, and its tone. Taken from Audio Cassette Simulation by Aleksandr
# Romanov (https://github.com/AARomanov1985/Audio-Cassette-Simulation), MIT licensed; see
# cassette-simulation-LICENSE.txt.
TDK_D90_FILTER = (
    "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[music];"
    "aevalsrc=exprs='(random(0)-0.5)*0.006|(random(1)-0.5)*0.006':s=44100[static];"
    "[music][static]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed];"
    "[mixed]vibrato=f=1.8:d=0.015,vibrato=f=15.0:d=0.003,highpass=f=40,lowpass=f=14500,"
    "equalizer=f=3000:width_type=q:width=0.5:g=1.5,"
    "equalizer=f=10000:width_type=q:width=0.7:g=-2[out]"
)

# Suffix of a file ffmpeg is still writing; one left by an interrupted job is removed by
# clear_cache once it is older than PARTIAL_MAX_AGE seconds.
PARTIAL_SUFFIX = ".part"
PARTIAL_MAX_AGE = 3600

QUALITY_SETTINGS = {
    "high": {"bitrate": "256k", "format": "mp3"},
    "medium": {"bitrate": "192k", "format": "mp3"},
    "low": {"bitrate": "128k", "format": "mp3"},
    # Played in the player's cassette mode. Made for every source format, as it changes the sound.
    "cassette": {"bitrate": "192k", "format": "mp3", "filter": TDK_D90_FILTER},
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

    def should_transcode(self, file_path: Path, quality: QualityLevel = "medium") -> bool:
        """
        Determine if a file should be transcoded based on its format.

        Args:
            file_path: Path to the audio file.
            quality: Quality level asked for; the cassette sound is made for every format.

        Returns:
            True if the file should be transcoded, False otherwise.
        """
        if quality == "cassette":
            return True

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
        if quality == "original" or not self.should_transcode(original_path, quality):
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
        if quality == "original" or not self.should_transcode(original_path, quality):
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

        self.logger.debug(f"Transcoding {original_path.name} to {quality} quality ({bitrate})")

        # Written under a temporary name of its own and moved into place when complete, so a file
        # still being written is never served as cached, and two jobs making the same file at
        # once don't write into each other's.
        handle, partial_name = tempfile.mkstemp(
            dir=self.cache_dir, prefix=f"{cache_path.name}.", suffix=PARTIAL_SUFFIX
        )
        os.close(handle)
        partial_path = Path(partial_name)
        partial_path.chmod(0o644)  # mkstemp makes it private; a cached file is readable as before

        # Build ffmpeg command
        cmd = ["ffmpeg", "-y", "-i", str(original_path)]  # Overwrite output file
        if audio_filter := settings.get("filter"):
            cmd += ["-filter_complex", audio_filter, "-map", "[out]"]
        else:
            cmd += [
                "-vn",  # No video
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
            ]
        cmd += [
            "-b:a", bitrate,  # Target bitrate
            "-map_metadata", "0",  # Copy metadata
            "-id3v2_version", "3",  # ID3v2.3 for better compatibility
            "-f", settings["format"],
            str(partial_path),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            os.replace(partial_path, cache_path)
            self.logger.debug(f"Successfully cached: {cache_path}")
            return cache_path

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Transcoding failed for {original_path}: {e.stderr}")
            raise

        finally:
            # Clean up the partial file, whatever stopped the job
            partial_path.unlink(missing_ok=True)

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
        if quality == "original" or not self.should_transcode(original_path, quality):
            return original_path

        cache_path = self.get_cache_path(original_path, quality)

        return cache_path if self.is_cached(original_path, quality) else original_path

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
        total_size = sum(
            file_path.stat().st_size
            for file_path in self.cache_dir.rglob("*")
            if file_path.is_file()
        )
        return total_size

    def clear_cache(self, older_than_days: int | None = None) -> int:
        """
        Clear cached files, optionally only those older than specified days.

        Args:
            older_than_days: If specified, only delete files older than this many days.

        Returns:
            Number of files deleted.
        """
        deleted_count = 0
        current_time = time.time()

        for file_path in [*self.cache_dir.rglob("*.mp3"), *self.cache_dir.rglob(f"*{PARTIAL_SUFFIX}")]:
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_path.suffix == PARTIAL_SUFFIX:
                    # Left by an interrupted job; a younger one may still be written
                    should_delete = file_age > PARTIAL_MAX_AGE
                elif older_than_days is not None:
                    should_delete = file_age / 86400 > older_than_days
                else:
                    should_delete = True

                if should_delete:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        self.logger.debug(f"Deleted cached file: {file_path}")
                    except OSError as e:
                        self.logger.error(f"Failed to delete {file_path}: {e}")

        self.logger.info(f"Cache cleanup: deleted {deleted_count} files")
        return deleted_count
