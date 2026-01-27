#!/usr/bin/env python3
"""
Migrate existing mixtapes to multi-collection format.

This script adds the collection_id field to all existing mixtapes that don't
already have one, making them compatible with the multi-collection system.

Usage:
    python migrate_mixtapes.py [mixtapes_dir] [default_collection_id]
    
    # Use defaults (from environment or config)
    python migrate_mixtapes.py
    
    # Specify custom paths
    python migrate_mixtapes.py /data/mixtapes main
    
    # Dry run mode (show what would be changed without modifying files)
    python migrate_mixtapes.py --dry-run

Example output:
    Found 15 mixtapes to check
    ✓ Migrated: summer-vibes.json
    ✓ Migrated: road-trip-2024.json
    ⊘ Skipped: jazz-classics.json (already has collection_id)
    
    Migration complete: 12/15 mixtapes updated
"""

import json
from pathlib import Path
import sys
import argparse
from typing import List, Tuple


def migrate_mixtapes(
    mixtapes_dir: Path,
    default_collection_id: str = "main",
    dry_run: bool = False
) -> Tuple[int, int, List[str]]:
    """Add collection_id to existing mixtapes.
    
    Args:
        mixtapes_dir: Directory containing mixtape JSON files
        default_collection_id: Collection ID to assign to mixtapes without one
        dry_run: If True, show what would change without modifying files
    
    Returns:
        Tuple of (total_count, migrated_count, error_files)
    """
    
    mixtape_files = list(mixtapes_dir.glob("*.json"))
    
    if not mixtape_files:
        print("No mixtapes found to migrate")
        return 0, 0, []
    
    print(f"Found {len(mixtape_files)} mixtapes to check")
    if dry_run:
        print("DRY RUN MODE - No files will be modified\n")
    else:
        print()
    
    migrated = 0
    skipped = 0
    errors = []
    
    for mixtape_file in mixtape_files:
        try:
            with open(mixtape_file) as f:
                data = json.load(f)
            
            # Skip if already has collection_id
            if 'collection_id' in data:
                print(f"⊘ Skipped: {mixtape_file.name} (already has collection_id)")
                skipped += 1
                continue
            
            # Add default collection_id
            data['collection_id'] = default_collection_id
            
            if dry_run:
                print(f"✓ Would migrate: {mixtape_file.name}")
            else:
                # Write back with proper formatting
                with open(mixtape_file, 'w') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"✓ Migrated: {mixtape_file.name}")
            
            migrated += 1
            
        except json.JSONDecodeError as e:
            print(f"✗ JSON error in {mixtape_file.name}: {e}", file=sys.stderr)
            errors.append(str(mixtape_file))
        except Exception as e:
            print(f"✗ Failed to migrate {mixtape_file.name}: {e}", file=sys.stderr)
            errors.append(str(mixtape_file))
    
    print(f"\n{'Would migrate' if dry_run else 'Migration complete'}: "
          f"{migrated}/{len(mixtape_files)} mixtapes updated")
    if skipped > 0:
        print(f"Skipped: {skipped} (already had collection_id)")
    if errors:
        print(f"Errors: {len(errors)} files failed", file=sys.stderr)
    
    return len(mixtape_files), migrated, errors


def load_config_defaults() -> Tuple[Path, str]:
    """Load default paths from config if available.
    
    Returns:
        Tuple of (mixtapes_dir, default_collection_id)
    """
    try:
        # Try to import config
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from config.config import BaseConfig
        
        mixtapes_dir = BaseConfig.MIXTAPE_DIR
        default_collection_id = "main"
        
        return mixtapes_dir, default_collection_id
    except Exception:
        # Fallback to common defaults
        return Path("/data/mixtapes"), "main"


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate existing mixtapes to multi-collection format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use defaults from config
  python migrate_mixtapes.py
  
  # Specify custom paths
  python migrate_mixtapes.py /data/mixtapes main
  
  # Dry run (preview changes)
  python migrate_mixtapes.py --dry-run
  
  # Specify everything
  python migrate_mixtapes.py /custom/path jazz-collection --dry-run
        """
    )
    
    parser.add_argument(
        'mixtapes_dir',
        nargs='?',
        type=Path,
        help='Directory containing mixtape JSON files (default: from config)'
    )
    
    parser.add_argument(
        'collection_id',
        nargs='?',
        default='main',
        help='Default collection ID to assign (default: main)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without modifying files'
    )
    
    args = parser.parse_args()
    
    # Determine paths
    if args.mixtapes_dir:
        mixtapes_dir = args.mixtapes_dir
        collection_id = args.collection_id
    else:
        # Load from config
        mixtapes_dir, collection_id = load_config_defaults()
        if args.collection_id != 'main':
            collection_id = args.collection_id
    
    # Validate directory exists
    if not mixtapes_dir.exists():
        print(f"Error: Directory not found: {mixtapes_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Migrating mixtapes in: {mixtapes_dir}")
    print(f"Default collection: {collection_id}")
    print()
    
    # Run migration
    total, migrated, errors = migrate_mixtapes(
        mixtapes_dir,
        collection_id,
        args.dry_run
    )
    
    # Exit with error code if there were failures
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
