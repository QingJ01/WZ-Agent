"""Tests for logging stream compatibility."""

from __future__ import annotations

import io
import logging
import sys

from wzry_ai.utils import logging_utils


def test_global_logging_replaces_unencodable_console_characters(monkeypatch, capsys):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    logging_utils._global_logging_configured = False
    logging.root.handlers = []

    try:
        logging_utils.setup_global_logging(level=logging.INFO, enable_color=False)
        logging.getLogger("test").info("scrcpy patch ✓ ready")
        for handler in logging.root.handlers:
            handler.flush()
    finally:
        logging.root.handlers = []
        logging_utils._global_logging_configured = False
        stream.detach()

    captured = capsys.readouterr()
    assert "Logging error" not in captured.err


def test_colored_formatter_does_not_mutate_record_message():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="plain message",
        args=(),
        exc_info=None,
    )
    formatter = logging_utils.ColoredFormatter("%(message)s")

    formatted = formatter.format(record)

    assert "plain message" in formatted
    assert record.msg == "plain message"


def test_setup_colored_logger_handles_stderr_without_isatty(monkeypatch):
    class StderrLike:
        def write(self, value):
            pass

        def flush(self):
            pass

    logger_name = "test.stderr_without_isatty"
    logger = logging.getLogger(logger_name)
    logger.handlers = []
    monkeypatch.setattr(sys, "stderr", StderrLike())

    try:
        configured = logging_utils.setup_colored_logger(logger_name)
        configured.info("ready")
    finally:
        logger.handlers = []
        logger.propagate = True

    assert configured.name == logger_name
