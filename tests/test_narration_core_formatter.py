# -*- coding: utf-8 -*-
import pytest

from historical_processor.narration_core.types import FormatterConfig
from historical_processor.narration_core.formatter import TextFormatter


def test_formatter_basic_cs_number_years_and_punct():
    cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)
    src = (
        "Podle Novák, 1999 [zdroj] v roce 1914 nastaly změny... 25 vojáků šlo dál - a pak nic. "
        "Např. 12 lidí, tj. 3 jednotky."
    )
    out = f.format(src)
    # ellipsis normalized
    assert "…" in out
    # years + numbers collapsed to single words
    assert "1914" not in out
    assert "dvanáct".replace(" ","")[:4] in out  # crude check exists
    # punctuation spacing: one space after punctuation
    assert " ," not in out
    assert " ." not in out
    assert "," in out and "." in out


def test_long_sentence_split_heuristic():
    cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False, strict_sentence_split=True)
    f = TextFormatter(cfg)
    long = " ".join(["slovo"] * 65) + "."
    out = f.format(long)
    # expect at least two sentences after split
    assert out.count(".") >= 2


# 🆕 NEW TESTS FOR POSSESSIVE REMOVAL
def test_possessive_removal_czech():
    """Test removal of Czech possessive pronouns in all cases."""
    cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)

    test_cases = [
        "Vítejte v našem dokumentárním seriálu.",
        "V naší sérii se zaměřujeme na historii.",
        "První díl našeho seriálu.",
        "V našem projektu.",
    ]

    for input_text in test_cases:
        result = f.format(input_text)
        # Main assertion: no possessives remain
        assert "naš" not in result.lower(), f"Failed to remove possessive from: {input_text} -> {result}"
        # Should have some content (not empty)
        assert len(result) > 0


def test_possessive_removal_english():
    """Test removal of English possessive pronouns."""
    cfg = FormatterConfig(language='EN', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)

    test_cases = [
        ("Welcome to our documentary series.", "Welcome to the documentary series."),
        ("In our episode we explore history.", "In the episode we explore history."),
        ("This is part of our collection.", "This is part of the collection."),
    ]

    for input_text, _ in test_cases:
        result = f.format(input_text)
        assert "our" not in result.lower(), f"Failed for: {input_text}"
        assert "the" in result.lower()


def test_possessive_removal_all_languages():
    """Test possessive removal for all supported languages."""
    test_data = [
        ('CS', "V našem projektu zkoumáme.", "naš"),
        ('EN', "Our series explores history.", "our"),
        ('DE', "In unserer Serie untersuchen wir.", "unser"),
        ('ES', "Nuestra serie explora.", "nuestr"),
        ('FR', "Notre série explore.", "notre"),
    ]

    for lang, text, forbidden in test_data:
        cfg = FormatterConfig(language=lang, use_gpt_split=False, use_gpt_grammar=False)
        f = TextFormatter(cfg)
        result = f.format(text)
        assert forbidden not in result.lower(), f"Failed to remove '{forbidden}' from {lang}: {result}"


# 🆕 SOFT MODE TESTS
def test_soft_mode_warns_but_preserves():
    """Test that soft mode (strict_sentence_split=False) warns but doesn't split."""
    cfg = FormatterConfig(
        language='CS',
        use_gpt_split=False,
        use_gpt_grammar=False,
        strict_sentence_split=False,  # Soft mode
        max_sentence_words=10
    )
    f = TextFormatter(cfg)

    long_sentence = "Toto je velmi dlouhá věta která má více než deset slov a měla by být rozštěpena."
    result = f.format(long_sentence)

    # Should NOT be split (only one sentence)
    assert result.count(".") == 1
    # Should have warning
    assert len(f.warnings) > 0
    assert any("exceeds" in w for w in f.warnings)


def test_strict_mode_splits():
    """Test that strict mode (strict_sentence_split=True) actually splits."""
    cfg = FormatterConfig(
        language='CS',
        use_gpt_split=False,
        use_gpt_grammar=False,
        strict_sentence_split=True,  # Strict mode
        max_sentence_words=10
    )
    f = TextFormatter(cfg)

    long_sentence = "Toto je velmi dlouhá věta, která má více než deset slov a měla by být rozštěpena."
    result = f.format(long_sentence)

    # Should be split into multiple sentences
    assert result.count(".") >= 2


def test_intelligent_split_respects_language():
    """Test that _intelligent_split recognizes conjunctions from different languages."""
    cfg_en = FormatterConfig(language='EN', use_gpt_split=False, strict_sentence_split=True, max_sentence_words=10)
    f_en = TextFormatter(cfg_en)

    # English sentence with 'and'
    words = "This is a test sentence and it has many words that exceed the limit".split()
    result = f_en._intelligent_split(words, max_words=10)

    assert len(result) >= 2
    # First part should end before or at 'and'
    assert 'and' in result[0].lower() or 'and' in result[1].lower()


# 🆕 EDGE CASES
def test_formatter_empty_text():
    """Test formatter handles empty text gracefully."""
    cfg = FormatterConfig(language='CS', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)
    result = f.format("")
    assert result == ""


def test_formatter_already_clean_text():
    """Test formatter doesn't break already clean text."""
    cfg = FormatterConfig(language='EN', use_gpt_split=False, use_gpt_grammar=False)
    f = TextFormatter(cfg)
    clean_text = "This is a clean sentence. It has proper punctuation."
    result = f.format(clean_text)
    # Should remain largely unchanged (except possessives check)
    assert "." in result
    assert result.count(".") >= 2
