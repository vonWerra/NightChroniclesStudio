#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clear narration_core cache to force regeneration with new prompts.

Usage:
    python scripts/clear_narration_cache.py [--dry-run]
"""
import argparse
import shutil
from pathlib import Path
import os


def main():
    parser = argparse.ArgumentParser(description="Clear narration_core cache")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be deleted without actually deleting"
    )
    args = parser.parse_args()

    # Locate cache directory
    root = Path(os.environ.get("NC_OUTPUTS_ROOT", Path.cwd() / "outputs"))
    cache_dir = root / ".cache" / "narration_core"

    if not cache_dir.exists():
        print(f"✅ Cache directory does not exist: {cache_dir}")
        return

    # Count files
    cache_files = list(cache_dir.glob("*.json"))
    
    if not cache_files:
        print(f"✅ Cache directory is empty: {cache_dir}")
        return

    print(f"📂 Cache directory: {cache_dir}")
    print(f"📊 Found {len(cache_files)} cache files")

    if args.dry_run:
        print("\n🔍 DRY RUN - Would delete:")
        for f in cache_files[:5]:  # Show first 5
            print(f"   - {f.name}")
        if len(cache_files) > 5:
            print(f"   ... and {len(cache_files) - 5} more")
        print("\nRe-run without --dry-run to actually delete.")
    else:
        confirm = input(f"\n⚠️  Delete {len(cache_files)} cache files? [y/N]: ")
        if confirm.lower() == 'y':
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Cache cleared: {cache_dir}")
        else:
            print("❌ Cancelled")


if __name__ == "__main__":
    main()
