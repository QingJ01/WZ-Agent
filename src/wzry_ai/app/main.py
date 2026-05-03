"""Stable packaged runtime entrypoint."""

from __future__ import annotations

from typing import Optional


def main(adb_device: Optional[str] = None) -> None:
    """Run the current application runtime via the packaged composition root."""
    from .runtime import run_app_runtime

    run_app_runtime(adb_device=adb_device)


__all__ = ["main"]
