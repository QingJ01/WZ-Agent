# pyright: reportMissingImports=false
"""Regression tests for temp-cwd resource consumers."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from wzry_ai.app.services import GameServices


def test_services_uses_resource_resolver_from_temp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from wzry_ai.game_manager import template_matcher as template_matcher_module

    class FakeResolver:
        def templates_dir(self, preferred_root=None):
            resolved = tmp_path / "resolved_templates"
            resolved.mkdir(exist_ok=True)
            return resolved

    monkeypatch.setattr(
        template_matcher_module,
        "get_runtime_path_resolver",
        lambda: FakeResolver(),
    )
    monkeypatch.setattr(
        template_matcher_module.TemplateMatcher,
        "_load_templates",
        lambda self: None,
    )

    with (
        patch("wzry_ai.app.services.init_emulator"),
        patch("wzry_ai.app.services.cv2"),
        patch("wzry_ai.app.services.ClickExecutor"),
        patch("wzry_ai.app.services.GameStateDetector"),
    ):
        services = GameServices(adb_device="test_device")

    services._init_state_detection()

    matcher = services.template_matcher
    assert matcher is not None
    assert matcher.path_resolver is not None
    assert Path(matcher.template_folder) == tmp_path / "resolved_templates"


def test_model1_astar_follow_uses_resource_resolver_from_temp_cwd(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    from wzry_ai.utils import resource_resolver as resource_resolver_module

    ultralytics_stub = types.ModuleType("ultralytics")

    class DummyYOLO:
        def __init__(self, *args, **kwargs):
            self.names = {}

        def to(self, *args, **kwargs):
            return self

        def predict(self, *args, **kwargs):
            return []

        def eval(self):
            return self

        def fuse(self):
            return self

        def __call__(self, *args, **kwargs):
            return []

    setattr(ultralytics_stub, "YOLO", DummyYOLO)
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics_stub)
    for module_name in ("win32con", "win32gui", "win32api"):
        monkeypatch.setitem(sys.modules, module_name, types.ModuleType(module_name))

    calls: list[tuple[str, ...]] = []

    class FakeResolver:
        def resolve_data(self, *parts):
            calls.append(tuple(str(part) for part in parts))
            resolved = tmp_path / "resolved_map_grid.txt"
            resolved.write_text("0\n", encoding="utf-8")
            return resolved

    monkeypatch.setattr(
        resource_resolver_module,
        "get_runtime_path_resolver",
        lambda: FakeResolver(),
    )

    sys.modules.pop("wzry_ai.detection.model1_astar_follow", None)

    module = importlib.import_module("wzry_ai.detection.model1_astar_follow")

    assert calls == [("map_grid.txt",)]
    assert module.map_grid_path is not None
    assert (
        Path(module.map_grid_path).resolve()
        == (tmp_path / "resolved_map_grid.txt").resolve()
    )
    assert module.obstacle_map.shape == (module.GRID_SIZE, module.GRID_SIZE)
