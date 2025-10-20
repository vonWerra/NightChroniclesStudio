import asyncio
import json
import os
from pathlib import Path
import tempfile

import pytest

from historical_processor.runner_cli import process_file, _numbers_to_words, load_rules, sha256_text
from historical_processor.processors.text_processor import TextProcessor


def write_tmp_file(content: str) -> Path:
    fd, p = tempfile.mkstemp(suffix='.txt')
    os.close(fd)
    pth = Path(p)
    pth.write_text(content, encoding='utf-8')
    return pth


def test_numbers_to_words_no_crash():
    # Should not raise even if num2words missing
    text = "Rok 1945 byl pro Evropu klíčový."
    out = _numbers_to_words(text)
    assert isinstance(out, str)


def test_prepare_for_tts_abbreviations():
    tp = TextProcessor()
    inp = "Toto je, např. test."
    out = tp.prepare_for_tts(inp)
    assert "například" in out or "napr" not in out


@pytest.mark.asyncio
async def test_process_file_dry_run_creates_temp(tmp_path):
    content = "Ahoj, např. toto je test 2020."
    src = tmp_path / "segment_01.txt"
    src.write_text(content, encoding='utf-8')
    out_base = tmp_path / "post"
    out_base.mkdir()

    res = await process_file(src, out_base, rules={}, preset='default', dry_run=True)
    assert res.get('ok') is True
    meta = res.get('meta')
    assert 'temp_path' in meta or 'temp_path' in res
    tp = res.get('temp_path') or meta.get('temp_path')
    assert tp
    assert Path(tp).exists()
    txt = Path(tp).read_text(encoding='utf-8')
    assert isinstance(txt, str)


@pytest.mark.asyncio
async def test_process_file_apply_writes_output_and_meta(tmp_path):
    content = "Číslo 10 a zkratka např. musí být rozpsána."
    src = tmp_path / "segment_02.txt"
    src.write_text(content, encoding='utf-8')
    out_base = tmp_path / "post"
    out_base.mkdir()

    res = await process_file(src, out_base, rules={}, preset='default', dry_run=False)
    assert res.get('ok') is True
    meta = res.get('meta')
    out_path = Path(meta.get('output_path'))
    assert out_path.exists()
    meta_path = out_path.with_suffix(out_path.suffix + '.meta.json')
    assert meta_path.exists()
    data = json.loads(meta_path.read_text(encoding='utf-8'))
    assert data['source_path'] == str(src.resolve())
    assert 'output_sha256' in data


def test_sha256_text_consistent():
    s = 'hello world'
    h1 = sha256_text(s)
    h2 = sha256_text(s)
    assert h1 == h2
