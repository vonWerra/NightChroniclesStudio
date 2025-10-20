#!/usr/bin/env python3
"""Inspect .cache/segments gz cache entries and print prompt_hash and snippet.
Run from repo root: python scripts/inspect_cache.py
"""
import gzip
import json
from pathlib import Path

cache_dir = Path('.cache/segments')
if not cache_dir.exists():
    print('No cache dir found:', cache_dir)
    raise SystemExit(1)

for p in sorted(cache_dir.glob('*.gz')):
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            data = json.load(f)
        ts = data.get('timestamp')
        ph = data.get('prompt_hash') or data.get('prompt_hash', '')
        content = data.get('content', '')
        chars = len(content)
        words = len(content.split())
        print(p.name, f'ts={ts}', f'prompt_hash={ph}', f'chars={chars}', f'words={words}')
        print('--- snippet ---')
        print(content[:800].replace('\n','\n'))
        print('\n' + '='*60 + '\n')
    except Exception as e:
        print('ERR reading', p, e)
