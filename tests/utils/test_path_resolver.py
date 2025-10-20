"""Tests for PathResolver."""
import pytest
import os
from pathlib import Path
from studio_gui.src.utils.path_resolver import PathResolver


def test_module_env_takes_priority(monkeypatch, tmp_path):
    """Module-specific env var should take priority over NC_OUTPUTS_ROOT."""
    custom_prompts = tmp_path / "custom_prompts"
    custom_prompts.mkdir()
    nc_root = tmp_path / "nc"

    monkeypatch.setenv("PROMPTS_OUTPUT_ROOT", str(custom_prompts))
    monkeypatch.setenv("NC_OUTPUTS_ROOT", str(nc_root))

    result = PathResolver.prompts_root()
    assert result == custom_prompts


def test_nc_outputs_root_fallback(monkeypatch, tmp_path):
    """NC_OUTPUTS_ROOT + subdir should be used when module-specific env not set."""
    nc_root = tmp_path / "nc"
    nc_root.mkdir()

    monkeypatch.delenv("PROMPTS_OUTPUT_ROOT", raising=False)
    monkeypatch.setenv("NC_OUTPUTS_ROOT", str(nc_root))

    result = PathResolver.prompts_root()
    assert result == nc_root / "prompts"


def test_cwd_fallback_when_no_env(monkeypatch):
    """Should fall back to cwd()/outputs/<module> when no env set."""
    monkeypatch.delenv("PROMPTS_OUTPUT_ROOT", raising=False)
    monkeypatch.delenv("NC_OUTPUTS_ROOT", raising=False)

    result = PathResolver.prompts_root()
    assert result == Path.cwd() / "outputs" / "prompts"


def test_all_module_roots_available():
    """All module roots should be accessible."""
    roots = [
        PathResolver.osnova_root(),
        PathResolver.prompts_root(),
        PathResolver.narration_root(),
        PathResolver.postproc_root(),
        PathResolver.tts_root(),
        PathResolver.export_root(),
    ]

    # All should return Path objects
    for root in roots:
        assert isinstance(root, Path)


def test_invalid_module_raises():
    """Invalid module name should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown module"):
        PathResolver.get_root("invalid_module")
