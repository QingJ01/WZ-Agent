"""Regression tests for the public skills package surface."""

from __future__ import annotations

import importlib

import pytest


def test_skills_package_no_longer_exports_hero_skill_manager():
    module = importlib.import_module("wzry_ai.skills")

    assert not hasattr(module, "HeroSkillManager")
    assert "HeroSkillManager" not in getattr(module, "__all__", [])

    with pytest.raises(ImportError):
        exec("from wzry_ai.skills import HeroSkillManager", {})
