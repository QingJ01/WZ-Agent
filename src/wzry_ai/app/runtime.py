"""Runtime delegation helpers for the packaged app entry."""

from __future__ import annotations

from typing import Optional, Protocol, cast

from .bootstrap import bootstrap_runtime_environment


class RuntimeEntry(Protocol):
    def __call__(self, *, adb_device: Optional[str] = None) -> None: ...


def _import_orchestration_module():
    module_name = ".".join(("wzry_ai", "app", "orchestration"))
    return __import__(module_name, fromlist=["main"])


def load_runtime_main() -> RuntimeEntry:
    """Import and return the package-owned runtime entrypoint."""
    bootstrap_runtime_environment()
    runtime_module = _import_orchestration_module()
    return cast(RuntimeEntry, runtime_module.main)


def load_legacy_main() -> RuntimeEntry:
    """Backward-compatible alias for the packaged runtime entrypoint loader."""
    return load_runtime_main()


def run_app_runtime(adb_device: Optional[str] = None) -> None:
    """Execute the package-owned runtime through the packaged entry."""
    runtime_main = load_runtime_main()
    runtime_main(adb_device=adb_device)


def run_legacy_runtime(adb_device: Optional[str] = None) -> None:
    """Backward-compatible alias for package-owned runtime execution."""
    run_app_runtime(adb_device=adb_device)


__all__ = [
    "load_legacy_main",
    "load_runtime_main",
    "run_app_runtime",
    "run_legacy_runtime",
]
