#!/usr/bin/env python3
"""Scan .cache/segments/*.gz and remove entries that match suspicious patterns.
Currently removes entries whose content contains the phrase 'silk road' (case-insensitive).
Prints list of removed files.
"""
import gzip
import json
from pathlib import Path

cache_dir = Path('.cache/segments')
if not cache_dir.exists():
    print('No cache dir found:', cache_dir)
    raise SystemExit(0)

removed = []
for p in sorted(cache_dir.glob('*.gz')):
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            data = json.load(f)
        content = data.get('content', '')
        if not isinstance(content, str):
            continue
        low = content.lower()
        # suspicious patterns
        if 'silk road' in low or 'silkroad' in low:
            try:
                p.unlink()
                removed.append(str(p))
            except Exception as e:
                print('Failed to remove', p, e)
    except Exception as e:
        print('ERR reading', p, e)

print(f'Removed {len(removed)} cache files:')
for r in removed:
    print(' -', r)
if not removed:
    print('No suspicious cache files found matching patterns.')
