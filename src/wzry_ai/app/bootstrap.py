"""Minimal packaged bootstrap helpers for the runtime entry."""

from __future__ import annotations

import ctypes
from importlib import import_module
import logging
import os
import sys


_BOOTSTRAPPED = False
_STDERR_FILTER_INSTALLED = False


class StderrFilter:
    """Filter noisy H.264/scrcpy decode errors from stderr."""

    ERROR_PATTERNS = [
        b"QP",
        b"out of range",
        b"decode_slice_header error",
        b"no frame!",
        b"non-existing PPS",
        b"referenced",
        b"A non-intra slice in an IDR NAL unit.",
        b"luma_log2_weight_denom",
        b"[ERROR]",
    ]

    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, data):
        if isinstance(data, bytes):
            if any(pattern in data for pattern in self.ERROR_PATTERNS):
                return
        elif isinstance(data, str):
            data_bytes = data.encode("utf-8", errors="ignore")
            if any(pattern in data_bytes for pattern in self.ERROR_PATTERNS):
                return

        self.original_stderr.write(data)

    def flush(self):
        self.original_stderr.flush()


def _set_process_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _install_stderr_filter() -> None:
    global _STDERR_FILTER_INSTALLED

    if _STDERR_FILTER_INSTALLED or isinstance(sys.stderr, StderrFilter):
        _STDERR_FILTER_INSTALLED = True
        return

    sys.stderr = StderrFilter(sys.stderr)
    _STDERR_FILTER_INSTALLED = True


def _prepend_adb_to_path(logger: logging.Logger) -> None:
    config_module = import_module("wzry_ai.config")
    adb_path = getattr(config_module, "ADB_PATH")

    adb_bin_dir = os.path.dirname(adb_path)
    current_path = os.environ.get("PATH", "")

    if os.path.exists(adb_bin_dir) and adb_bin_dir not in current_path:
        os.environ["PATH"] = adb_bin_dir + os.pathsep + current_path
        logger.info(f"已添加 ADB 路径: {adb_bin_dir}")


def _silence_third_party_loggers() -> None:
    logging.getLogger("scrcpy").setLevel(logging.CRITICAL)
    logging.getLogger("av").setLevel(logging.CRITICAL)

    try:
        import av

        av_logging = getattr(av, "logging", None)
        fatal_level = getattr(av_logging, "FATAL", None)
        if av_logging is not None and fatal_level is not None:
            av_logging.set_level(fatal_level)
    except (ImportError, AttributeError):
        pass


def bootstrap_runtime_environment() -> logging.Logger:
    """Prepare the runtime environment before importing the legacy entry."""
    global _BOOTSTRAPPED

    logging_utils = import_module("wzry_ai.utils.logging_utils")
    setup_global_logging = getattr(logging_utils, "setup_global_logging")
    get_logger = getattr(logging_utils, "get_logger")

    _set_process_dpi_awareness()
    setup_global_logging(level=logging.DEBUG)
    logger = get_logger(__name__)

    if _BOOTSTRAPPED:
        return logger

    _prepend_adb_to_path(logger)
    _silence_third_party_loggers()
    _install_stderr_filter()
    _BOOTSTRAPPED = True
    return logger


__all__ = ["StderrFilter", "bootstrap_runtime_environment"]
