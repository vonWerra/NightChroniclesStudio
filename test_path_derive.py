# -*- coding: utf-8 -*-
"""Test _derive_episode_context_from_path to debug duplicate folder issue."""
from pathlib import Path
import sys
sys.path.insert(0, 'historical_processor')

from runner_cli import _derive_episode_context_from_path

# Test cases
test_paths = [
    Path("outputs/narration/Vznik Československa/CS/ep01"),
    Path("outputs/narration/Vznik Československa/CS/ep01/narration"),
    Path("D:/NightChroniclesStudio/outputs/narration/Vznik Československa/CS/ep01"),
    Path("outputs/postprocess/Vznik Československa/CS/ep01/Vznik Československa/CS/ep01"),  # Duplicita!
]

print("=" * 70)
print("TESTING _derive_episode_context_from_path()")
print("=" * 70)

for path in test_paths:
    print(f"\nInput:  {path}")
    try:
        topic, lang, ep, ep_idx = _derive_episode_context_from_path(path)
        print(f"Output: topic='{topic}', lang='{lang}', ep='{ep}', ep_idx={ep_idx}")
        
        # Simulate out_dir creation
        out_base = Path("outputs/postprocess")
        out_dir = out_base / topic / lang / ep
        print(f"Out dir would be: {out_dir}")
        
        # Check if this creates duplicate
        if str(out_dir).count(topic) > 1 or str(out_dir).count(lang) > 1:
            print("⚠️  WARNING: This would create DUPLICATE structure!")
    except Exception as e:
        print(f"ERROR: {e}")
    print("-" * 70)
