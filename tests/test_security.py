import os
from pathlib import Path
import tempfile
import pytest

from claude_generator.claude_generator import SecureCredentialManager


def test_sanitize_path_allows_cwd(tmp_path):
    p = tmp_path / "subdir"
    p.mkdir()
    # use explicit allowed_roots (tmp_path) so sanitize_path accepts it
    result = SecureCredentialManager.sanitize_path(str(p), allowed_roots=[str(tmp_path)])
    assert isinstance(result, Path)
    assert str(result).startswith(str(tmp_path))


def test_sanitize_path_disallows_outside(tmp_path, monkeypatch):
    # set allowed_roots to only tmp_path to simulate restriction
    outside = Path("/tmp")
    with pytest.raises(ValueError):
        SecureCredentialManager.sanitize_path(str(outside), allowed_roots=[str(tmp_path)])
