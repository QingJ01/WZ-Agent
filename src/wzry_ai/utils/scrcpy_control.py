"""Shared access to the active scrcpy client control channel."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.RLock()
_active_client: Any | None = None


def set_active_scrcpy_client(client: Any) -> None:
    """Register the scrcpy client currently owned by the runtime."""
    global _active_client
    with _lock:
        _active_client = client


def get_active_scrcpy_client() -> Any | None:
    """Return the active scrcpy client if one is available."""
    with _lock:
        return _active_client


def clear_active_scrcpy_client(client: Any | None = None) -> None:
    """Clear the active client, optionally only if it matches ``client``."""
    global _active_client
    with _lock:
        if client is None or _active_client is client:
            _active_client = None
