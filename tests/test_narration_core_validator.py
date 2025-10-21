# -*- coding: utf-8 -*-
from historical_processor.narration_core.validator import TransitionQualityValidator, SegmentQualityValidator


def test_transition_validator_requires_anchor_when_present():
    prev = "V roce 1914 začala válka."
    next_ = "V roce 1915 se situace změnila."
    tv = TransitionQualityValidator(language='CS')
    valid = tv.validate(prev, next_, "Mezitím v roce 1914 došlo k zásadním změnám, což přirozeně vede k dalším událostem.")
    assert valid.ok

    invalid = tv.validate(prev, next_, "A teď se podíváme na další část.")
    assert not invalid.ok
    assert "missing_anchor" in invalid.reasons or "contains_meta_phrase" in invalid.reasons


def test_transition_validator_sentence_count():
    tv = TransitionQualityValidator(language='CS')
    prev = "Text A."
    next_ = "Text B."
    too_long = "Věta jedna. Věta dva. Věta tři."
    res = tv.validate(prev, next_, too_long)
    assert not res.ok
    assert "too_many_sentences" in res.reasons


# 🆕 NEW TESTS FOR POSSESSIVE DETECTION
def test_transition_validator_detects_possessive_czech():
    """Test that validator detects Czech possessive pronouns."""
    tv = TransitionQualityValidator(language='CS')
    prev = "Končí první část."
    next_ = "Začíná druhá část."

    # Should fail with possessive
    invalid = tv.validate(prev, next_, "V naší sérii nyní přejdeme k další tématu.")
    assert not invalid.ok
    assert "contains_possessive_pronoun" in invalid.reasons


def test_transition_validator_detects_possessive_english():
    """Test that validator detects English possessive pronouns."""
    tv = TransitionQualityValidator(language='EN')
    prev = "First part ends."
    next_ = "Second part begins."

    # Should fail with possessive
    invalid = tv.validate(prev, next_, "In our series we now move to the next topic.")
    assert not invalid.ok
    assert "contains_possessive_pronoun" in invalid.reasons


def test_transition_validator_sentence_length():
    """Test that validator checks sentence length (14-28 words)."""
    tv = TransitionQualityValidator(language='EN')
    prev = "Context A."
    next_ = "Context B."

    # Too short (< 14 words)
    short = "This is short."
    res_short = tv.validate(prev, next_, short)
    assert not res_short.ok
    assert any("too_short" in r for r in res_short.reasons)

    # Too long (> 28 words)
    long = " ".join(["word"] * 35) + "."
    res_long = tv.validate(prev, next_, long)
    assert not res_long.ok
    assert any("too_long" in r for r in res_long.reasons)


# 🆕 SEGMENT VALIDATOR TESTS
def test_segment_validator_detects_possessive():
    """Test SegmentQualityValidator detects possessives."""
    sv = SegmentQualityValidator(language='CS')

    text_with_possessive = "V našem dokumentárním seriálu zkoumáme historii."
    result = sv.validate(text_with_possessive)
    assert not result.ok
    assert "contains_possessive_pronoun" in result.reasons


def test_segment_validator_detects_long_sentences():
    """Test SegmentQualityValidator detects sentences exceeding max words."""
    sv = SegmentQualityValidator(language='EN')

    long_text = " ".join(["word"] * 40) + "."
    result = sv.validate(long_text, max_sentence_words=30)
    assert not result.ok
    assert any("exceeds" in r for r in result.reasons)


def test_segment_validator_detects_meta_phrases():
    """Test SegmentQualityValidator detects meta-narrative phrases."""
    sv = SegmentQualityValidator(language='EN')

    meta_text = "In this section we will explore the history."
    result = sv.validate(meta_text)
    assert not result.ok
    assert any("meta_phrase" in r for r in result.reasons)


def test_segment_validator_passes_clean_text():
    """Test SegmentQualityValidator passes valid text."""
    sv = SegmentQualityValidator(language='EN')

    clean_text = "The documentary explores World War II history. It covers key battles and strategic decisions."
    result = sv.validate(clean_text)
    assert result.ok
    assert len(result.reasons) == 0


def test_validator_multilingual_possessives():
    """Test that validators work for all languages."""
    test_cases = [
        ('CS', 'našem', "V našem příběhu."),
        ('EN', 'our', "In our story."),
        ('DE', 'unser', "In unserer Geschichte."),
        ('ES', 'nuestro', "En nuestro relato."),
        ('FR', 'notre', "Dans notre histoire."),
    ]

    for lang, keyword, text in test_cases:
        sv = SegmentQualityValidator(language=lang)
        result = sv.validate(text)
        assert not result.ok, f"Failed to detect '{keyword}' in {lang}"
        assert "contains_possessive_pronoun" in result.reasons
