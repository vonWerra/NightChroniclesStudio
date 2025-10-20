#!/usr/bin/env python3
"""Invalidate cache entries for all prompts belonging to a series.
Usage: python scripts/invalidate_cache_series.py <series_name> [lang]

This computes the cache key for each prompt file under outputs/prompts/<series>/<lang>/ep*/prompts/*.txt
and removes the corresponding .cache/segments/<key>.gz and its index entry if present.
"""
import sys
import json
import hashlib
from pathlib import Path

series = None
lang = None
if len(sys.argv) >= 2:
    series = sys.argv[1]
if len(sys.argv) >= 3:
    lang = sys.argv[2]
if not series:
    print("Usage: python scripts/invalidate_cache_series.py <series_name> [lang]")
    raise SystemExit(1)

# import Config to get model/temperature/max_tokens
try:
    from claude_generator.claude_generator import Config
except Exception:
    # fallback: try to import via file
    import importlib.util
    p = Path('claude_generator/claude_generator.py')
    spec = importlib.util.spec_from_file_location('claude_generator_impl', str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    Config = mod.Config

cfg = Config()
params = {
    'model': cfg.model,
    'temperature': cfg.temperature,
    'max_tokens': cfg.max_tokens
}
params_json = json.dumps(params, sort_keys=True)

prompts_root = Path(cfg.base_output_path)
if not prompts_root.exists():
    print('Prompts root does not exist:', prompts_root)
    raise SystemExit(1)

pattern_base = prompts_root / series
if lang:
    pattern_base = pattern_base / lang

prompt_files = list(pattern_base.rglob('prompts/*.txt'))
if not prompt_files:
    print('No prompt files found for', series, lang if lang else '')
    raise SystemExit(1)

cache_dir = Path('.cache/segments')
index_file = cache_dir / 'index.json'
index = {}
if index_file.exists():
    try:
        index = json.loads(index_file.read_text(encoding='utf-8'))
    except Exception:
        index = {}

removed = []
for pf in prompt_files:
    try:
        text = pf.read_text(encoding='utf-8')
    except Exception:
        text = pf.read_text(encoding='utf-8', errors='replace')
    key = hashlib.sha256((text + params_json).encode('utf-8')).hexdigest()
    gz = cache_dir / f"{key}.gz"
    if gz.exists():
        try:
            gz.unlink()
            removed.append(str(gz))
            if key in index:
                del index[key]
        except Exception as e:
            print('Failed to remove', gz, e)

# Save updated index
try:
    if index_file.exists():
        index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as e:
    print('Failed to update index.json:', e)

print(f'Removed {len(removed)} cache files:')
for r in removed:
    print(' -', r)

if not removed:
    print('No cache files removed (they may not exist or were not cached with current params).')
