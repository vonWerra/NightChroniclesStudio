#!/usr/bin/env python3
"""
Test script for robust MSP parsing in generate_prompts.py

Verifies that extract_msp_label() handles various osnova.json formats correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add B_core to path so we can import from generate_prompts
sys.path.insert(0, str(Path(__file__).parent))

from generate_prompts import extract_msp_label


def test_msp_parsing():
    """Test all supported MSP formats."""

    tests = [
        # Format 1: String only
        {
            "name": "String MSP",
            "input": "Napoleon's rise to power",
            "expected": "Napoleon's rise to power"
        },

        # Format 2: Dict with "text" key
        {
            "name": "Dict with 'text'",
            "input": {
                "text": "The Battle of Austerlitz",
                "sources_segment": ["source1.pdf", "source2.pdf"]
            },
            "expected": "The Battle of Austerlitz"
        },

        # Format 3: Dict with "label" key
        {
            "name": "Dict with 'label'",
            "input": {
                "label": "Napoleon's exile to Elba",
                "sources_segment": ["source3.pdf"]
            },
            "expected": "Napoleon's exile to Elba"
        },

        # Format 4: Dict with "msp" key
        {
            "name": "Dict with 'msp'",
            "input": {
                "msp": "The Hundred Days",
                "sources_segment": ["source4.pdf"]
            },
            "expected": "The Hundred Days"
        },

        # Format 5: Dict with "msp_label" key
        {
            "name": "Dict with 'msp_label'",
            "input": {
                "msp_label": "The Battle of Waterloo",
                "sources_segment": ["source5.pdf"]
            },
            "expected": "The Battle of Waterloo"
        },

        # Format 6: Empty string (should return empty)
        {
            "name": "Empty string",
            "input": "",
            "expected": ""
        },

        # Format 7: Dict with no recognized keys (fallback)
        {
            "name": "Dict with unrecognized keys",
            "input": {
                "some_other_key": "value",
                "another_key": 123
            },
            "expected": ""  # No recognized keys → empty
        },

        # Format 8: String with whitespace (should trim)
        {
            "name": "String with whitespace",
            "input": "  Napoleon crowned Emperor  \n",
            "expected": "Napoleon crowned Emperor"
        },
    ]

    print("=" * 60)
    print("Testing MSP Label Extraction")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, test in enumerate(tests, 1):
        result = extract_msp_label(test["input"])
        status = "[PASS]" if result == test["expected"] else "[FAIL]"

        if result == test["expected"]:
            passed += 1
        else:
            failed += 1

        print(f"\nTest {i}: {test['name']}")
        print(f"  Input:    {repr(test['input'])}")
        print(f"  Expected: {repr(test['expected'])}")
        print(f"  Got:      {repr(result)}")
        print(f"  {status}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_msp_parsing()
    sys.exit(0 if success else 1)
