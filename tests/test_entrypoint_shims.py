"""Regression tests for thin entrypoint shims."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch


def _assert_thin_entrypoint(module_name: str, adb_device: str) -> None:
    sys.modules.pop(module_name, None)

    with patch("wzry_ai.app.main.main", return_value="delegated") as mock_main:
        module = importlib.import_module(module_name)
        result = module.main(adb_device=adb_device)

    mock_main.assert_called_once_with(adb_device=adb_device)
    assert result == "delegated"
    assert module.__file__ is not None
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from wzry_ai.app.main import main as _packaged_main" in source
    assert "for candidate in (SRC_ROOT, REPO_ROOT)" not in source


def test_master_auto_delegates_to_packaged_main():
    _assert_thin_entrypoint("Master_Auto", "adb-123")


def test_scripts_master_auto_delegates_to_packaged_main():
    _assert_thin_entrypoint("scripts.master_auto", "adb-456")
