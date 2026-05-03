"""Package-owned runtime orchestration entry."""

from __future__ import annotations

from importlib import import_module
from typing import Optional


def main(adb_device: Optional[str] = None) -> None:
    """Own the stable packaged runtime entry without resolving through shims."""
    # 导入bootstrap并初始化环境
    from .bootstrap import bootstrap_runtime_environment
    logger = bootstrap_runtime_environment()

    # 导入配置
    config_module = import_module("wzry_ai.config")
    resolved_device = adb_device
    if resolved_device is None:
        resolved_device = getattr(config_module, "ADB_DEVICE_SERIAL", None)

    logger.info("=== WZ-Agent v0.4 ===")
    logger.info("目前支持英雄：瑶")
    logger.info("目前支持模式：5V5人机 / 5V5匹配")

    # 导入并调用主游戏循环
    from .game_loop import run_game_loop
    run_game_loop(adb_device=resolved_device)


__all__ = ["main"]
