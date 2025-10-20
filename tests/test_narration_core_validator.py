# -*- coding: utf-8 -*-
from historical_processor.narration_core.validator import TransitionQualityValidator


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
