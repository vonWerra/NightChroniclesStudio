# -*- coding: utf-8 -*-
import pytest

from historical_processor.narration_core.types import FormatterConfig
from historical_processor.narration_core.formatter import TextFormatter


def test_formatter_basic_cs_number_years_and_punct():
    cfg = FormatterConfig(language='CS')
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
    cfg = FormatterConfig(language='CS')
    f = TextFormatter(cfg)
    long = " ".join(["slovo"] * 65) + "."
    out = f.format(long)
    # expect at least two sentences after split
    assert out.count(".") >= 2
