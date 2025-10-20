# -*- coding: utf-8 -*-
from historical_processor.narration_core.cache import NarrationCache


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('NC_OUTPUTS_ROOT', str(tmp_path))
    cache = NarrationCache()
    payload = {"type": "intro", "version": "v1", "language": "CS", "episode": 1, "title": "XXX"}
    assert cache.load(payload) is None
    cache.save(payload, {"text": "Ahoj"})
    data = cache.load(payload)
    assert data is not None
    assert data.get("text") == "Ahoj"
