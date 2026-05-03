"""Tests for runtime feature flags."""

from __future__ import annotations

from wzry_ai.utils.runtime_flags import is_ai_control_enabled


def test_ai_control_enabled_defaults_to_true_when_env_missing(monkeypatch):
    monkeypatch.delenv("WZRY_AI_CONTROL_ENABLED", raising=False)

    assert is_ai_control_enabled() is True


def test_ai_control_enabled_reads_false_values(monkeypatch):
    monkeypatch.setenv("WZRY_AI_CONTROL_ENABLED", "0")

    assert is_ai_control_enabled() is False
