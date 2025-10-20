import tempfile
import shutil
import os
import gzip
import json
import time
from pathlib import Path

import pytest

from claude_generator.claude_generator import SegmentCache


def test_cache_set_get(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = SegmentCache(cache_dir=cache_dir)

    prompt = "hello"
    params = {"model": "m1"}
    content = "generated text"

    cache.set(prompt, params, content)
    got = cache.get(prompt, params)
    assert got == content


def test_cache_expiry(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = SegmentCache(cache_dir=cache_dir)

    prompt = "old"
    params = {"model": "m1"}
    content = "old text"

    cache.set(prompt, params, content)
    # simulate old timestamp by editing file
    key = cache.get_cache_key(prompt, params)
    cache_file = cache_dir / f"{key}.gz"
    assert cache_file.exists()

    # modify timestamp inside gz to an old ISO date
    with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    data['timestamp'] = '2000-01-01T00:00:00'
    with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
        json.dump(data, f)

    # simulate process restart by clearing in-memory cache and reloading index
    key = cache.get_cache_key(prompt, params)
    cache.memory_cache.pop(key, None)
    cache.cache_index = cache._load_index()

    got = cache.get(prompt, params)
    assert got is None
