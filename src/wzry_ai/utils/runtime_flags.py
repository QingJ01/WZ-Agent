"""Runtime feature flags shared by GUI, movement, and skill logic."""

from __future__ import annotations

import os


def env_flag(name: str, *, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def is_ai_control_enabled() -> bool:
    """Return whether runtime is allowed to send gameplay control inputs."""
    return env_flag("WZRY_AI_CONTROL_ENABLED", default=True)
