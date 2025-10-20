"""Tests for fs_helpers utilities."""
from pathlib import Path
import pytest

from studio_gui.src.utils.fs_helpers import (
    normalize_name,
    resolve_topic_dir,
    find_topic_in_index,
)


def test_normalize_name_diacritics():
    assert normalize_name("Příšerně žluťoučký") == "priserne_zlutoucky"
    assert normalize_name("Café") == "cafe"


def test_normalize_name_case_insensitive():
    assert normalize_name("Ancient Rome") == normalize_name("ANCIENT ROME")
    assert normalize_name("TeSt") == "test"


def test_normalize_name_special_chars():
    assert normalize_name("Hello-World!") == "hello_world"
    assert normalize_name("test___multiple") == "test_multiple"


def test_resolve_topic_dir_exact_match(tmp_path):
    topic_dir = tmp_path / "Ancient_Rome"
    topic_dir.mkdir()

    result = resolve_topic_dir(tmp_path, "Ancient_Rome")
    assert result == topic_dir
    assert result.exists()


def test_resolve_topic_dir_normalized_match(tmp_path):
    # Create dir with diacritics
    topic_dir = tmp_path / "Starověký_Řím"
    topic_dir.mkdir()

    # Search with ASCII version
    result = resolve_topic_dir(tmp_path, "Staroveky Rim")
    assert result == topic_dir


def test_resolve_topic_dir_no_match_returns_exact_path(tmp_path):
    result = resolve_topic_dir(tmp_path, "NonExistent")
    assert result == tmp_path / "NonExistent"
    assert not result.exists()


def test_resolve_topic_dir_root_not_exists():
    # Should not crash if root doesn't exist
    root = Path('/this_path_should_not_exist_12345')
    result = resolve_topic_dir(root, "topic")
    assert result == root / "topic"


def test_find_topic_in_index_exact_match():
    index = {"topics": {"Ancient Rome": {}, "Medieval Europe": {}}}
    assert find_topic_in_index("Ancient Rome", index) == "Ancient Rome"


def test_find_topic_in_index_normalized_match():
    index = {"topics": {"Starověký_Řím": {}, "Test": {}}}
    result = find_topic_in_index("Staroveky Rim", index)
    assert result == "Starověký_Řím"


def test_find_topic_in_index_no_match():
    index = {"topics": {"Topic1": {}}}
    assert find_topic_in_index("NonExistent", index) is None


def test_find_topic_in_index_invalid_input():
    assert find_topic_in_index("test", None) is None
    assert find_topic_in_index("test", {}) is None
    assert find_topic_in_index("test", {"topics": {}}) is None
