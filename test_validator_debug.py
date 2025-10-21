# -*- coding: utf-8 -*-
"""Debug script for testing validator possessive detection."""
import re
from historical_processor.narration_core.validator import SegmentQualityValidator, POSSESSIVE_PATTERNS

def test_regex_patterns():
    patterns_cs = POSSESSIVE_PATTERNS['CS']
    
    test_strings = [
        "V našem dokumentárním seriálu",
        "V naší sérii",
        "našeho seriálu",
        "našich projektů",
    ]
    
    print("=" * 60)
    print("TESTING REGEX PATTERNS FOR CZECH POSSESSIVES")
    print("=" * 60)
    
    for pattern in patterns_cs:
        print(f"\nPattern: {pattern}")
        for test_str in test_strings:
            match = re.search(pattern, test_str, flags=re.IGNORECASE)
            print(f"  '{test_str}': {'MATCH' if match else 'NO MATCH'}")
            if match:
                print(f"    Matched: '{match.group()}'")

def test_validator():
    sv = SegmentQualityValidator(language='CS')
    
    test_texts = [
        "V našem dokumentárním seriálu zkoumáme historii.",
        "V naší sérii se zaměřujeme na historii.",
        "První díl našeho seriálu.",
    ]
    
    print("\n" + "=" * 60)
    print("TESTING SEGMENT VALIDATOR")
    print("=" * 60)
    
    for text in test_texts:
        result = sv.validate(text)
        print(f"\nText: {text}")
        print(f"Valid: {result.ok}")
        print(f"Reasons: {result.reasons}")

if __name__ == "__main__":
    test_regex_patterns()
    test_validator()
