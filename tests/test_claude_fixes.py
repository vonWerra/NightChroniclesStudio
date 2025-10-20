from claude_generator.claude_generator import _strip_code_fences


def test_strip_code_fences_simple():
    s = "```yaml\nopening_hook_present: yes\nclosing_handoff_present: yes\n```"
    out = _strip_code_fences(s)
    assert 'opening_hook_present' in out
    assert 'closing_handoff_present' in out


def test_strip_code_fences_inline():
    s = "Some text\n```yaml\nkey: value\n```\nmore"
    out = _strip_code_fences(s)
    assert 'key: value' in out


def test_strip_code_fences_none():
    assert _strip_code_fences(None) is None
