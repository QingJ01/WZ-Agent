"""Tests for ADBTool screenshot frame-source selection."""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock

from wzry_ai.device.ADBTool import ADBTool


def _make_tool() -> ADBTool:
    tool = object.__new__(ADBTool)
    tool.device_serial = Mock(serial="serial")
    tool._persistent_shell = None
    return tool


def test_adb_tool_screenshot_does_not_fallback_in_forced_scrcpy_mode(monkeypatch):
    frame_manager = types.ModuleType("wzry_ai.utils.frame_manager")
    frame_manager.get_frame = lambda device_serial, timeout=0.05: None
    monkeypatch.setitem(sys.modules, "wzry_ai.utils.frame_manager", frame_manager)
    monkeypatch.setenv("WZRY_FRAME_SOURCE", "scrcpy")

    tool = _make_tool()
    adb_calls = []
    tool._run_adb = (  # type: ignore[method-assign]
        lambda *args, **kwargs: (adb_calls.append((args, kwargs)) or (False, b""))
    )

    assert tool.screenshot(use_scrcpy=True) is None
    assert adb_calls == []


def test_adb_tool_screenshot_falls_back_in_auto_mode(monkeypatch):
    frame_manager = types.ModuleType("wzry_ai.utils.frame_manager")
    frame_manager.get_frame = lambda device_serial, timeout=0.05: None
    monkeypatch.setitem(sys.modules, "wzry_ai.utils.frame_manager", frame_manager)
    monkeypatch.setenv("WZRY_FRAME_SOURCE", "auto")

    tool = _make_tool()
    tool._run_adb = lambda *args, **kwargs: (True, b"png")  # type: ignore[method-assign]

    assert tool.screenshot(use_scrcpy=True) == b"png"
