# -*- coding: utf-8 -*-
"""Debug script for testing possessive removal."""
from historical_processor.narration_core.formatter import TextFormatter
from historical_processor.narration_core.types import FormatterConfig

def test_possessive_removal():
    cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)

    test_cases = [
        ("Vítejte v našem dokumentárním seriálu.", "v tomto"),
        ("V naší sérii se zaměřujeme na historii.", "v této"),
        ("První díl našeho seriálu.", "našeho removed"),
    ]

    print("=" * 60)
    print("TESTING POSSESSIVE REMOVAL")
    print("=" * 60)

    for input_text, check in test_cases:
        result = f.format(input_text)
        has_našem = "naš" in result.lower()

        print(f"\nInput:  {input_text}")
        print(f"Output: {result}")
        print(f"Contains 'naš': {has_našem}")
        print(f"Check: {check}")
        print(f"Status: {'FAIL' if has_našem else 'PASS'}")
        print("-" * 60)

if __name__ == "__main__":
    test_possessive_removal()
