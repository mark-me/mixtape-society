#!/usr/bin/env python3
"""
Debug script to help diagnose cache path mismatches.

This script helps you verify that:
1. Cache paths are being generated correctly
2. File paths match between caching and lookup
3. Cache files are in the expected location
"""

import hashlib
from pathlib import Path
import sys


def generate_cache_path(original_path: str, quality: str = "medium") -> str:
    """
    Generate the cache path using the same logic as AudioCache.
    
    Args:
        original_path: The original file path (can be absolute or relative)
        quality: Quality level (high, medium, low)
    
    Returns:
        The expected cache filename
    """
    # This should match the logic in audio_cache.py
    path_hash = hashlib.md5(str(Path(original_path).resolve()).encode()).hexdigest()
    
    bitrate = {
        "high": "256k",
        "medium": "192k", 
        "low": "128k"
    }.get(quality, "192k")
    
    return f"{path_hash}_{quality}_{bitrate}.mp3"


def debug_cache_lookup(music_root: str, relative_path: str, cache_dir: str):
    """
    Debug a cache lookup to see why it might be failing.
    
    Args:
        music_root: Root directory for music files (e.g., "/music")
        relative_path: Relative path to the audio file (e.g., "Artist/Album/Song.flac")
        cache_dir: Directory where cache files are stored
    """
    print("=" * 70)
    print("CACHE LOOKUP DEBUG")
    print("=" * 70)
    
    # Build full path
    full_path = Path(music_root) / relative_path
    print(f"\n1. Original path components:")
    print(f"   Music root: {music_root}")
    print(f"   Relative:   {relative_path}")
    print(f"   Full path:  {full_path}")
    print(f"   Resolved:   {full_path.resolve()}")
    
    # Generate cache path for each quality
    print(f"\n2. Expected cache filenames:")
    for quality in ["high", "medium", "low"]:
        cache_filename = generate_cache_path(full_path, quality)
        cache_path = Path(cache_dir) / cache_filename
        exists = cache_path.exists()
        
        print(f"   {quality:8s}: {cache_filename}")
        print(f"            Exists: {'✓ YES' if exists else '✗ NO'}")
        if exists:
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            print(f"            Size:   {size_mb:.2f} MB")
    
    # List actual cache files that might match
    print(f"\n3. Scanning cache directory: {cache_dir}")
    cache_dir_path = Path(cache_dir)
    
    if not cache_dir_path.exists():
        print(f"   ✗ Cache directory does not exist!")
        return
    
    # Get the filename from the relative path
    filename = Path(relative_path).name
    print(f"   Looking for caches of: {filename}")
    
    all_caches = list(cache_dir_path.glob("*.mp3"))
    print(f"   Total cache files: {len(all_caches)}")
    
    # Try to find potential matches by checking if any hash matches
    print(f"\n4. Checking for potential matches:")
    
    # Generate hashes with different path formats
    test_paths = [
        full_path,
        full_path.resolve(),
        Path(relative_path),
        str(full_path),
        str(full_path.resolve()),
    ]
    
    for test_path in test_paths:
        path_hash = hashlib.md5(str(test_path).encode()).hexdigest()
        matches = [f for f in all_caches if f.name.startswith(path_hash)]
        
        if matches:
            print(f"   ✓ MATCH with path: {test_path}")
            for match in matches:
                print(f"     → {match.name}")
        else:
            print(f"   ✗ No match for:    {test_path}")
            print(f"     Hash: {path_hash}")
    
    # Show first few cache files for reference
    if all_caches:
        print(f"\n5. Sample cache files (first 5):")
        for cache_file in all_caches[:5]:
            size_mb = cache_file.stat().st_size / (1024 * 1024)
            print(f"   {cache_file.name} ({size_mb:.2f} MB)")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 4:
        print("Usage: python debug_cache.py <music_root> <relative_path> <cache_dir>")
        print()
        print("Example:")
        print('  python debug_cache.py "/music" "Jessica Pratt/Here in the Pitch/02 Better Hate.flac" "collection-data/cache/audio"')
        print()
        sys.exit(1)
    
    music_root = sys.argv[1]
    relative_path = sys.argv[2]
    cache_dir = sys.argv[3]
    
    debug_cache_lookup(music_root, relative_path, cache_dir)
