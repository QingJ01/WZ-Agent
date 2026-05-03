"""Main game loop orchestration."""

from __future__ import annotations

import time
import threading
from queue import Queue
from typing import Optional

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


def run_game_loop(adb_device: Optional[str] = None) -> None:
    """
    主游戏循环 - 协调所有子系统
    
    Args:
        adb_device: ADB设备序列号
    """
    from .services import GameServices
    from .loop_handlers import LoopHandlers
    
    # 初始化服务
    services = GameServices(adb_device)
    if not services.initialize():
        logger.error("服务初始化失败")
        return
    
    # 初始化循环处理器
    handlers = LoopHandlers(services)
    
    logger.info(">>> 系统启动，初始状态: 等待进入对局")
    
    try:
        # 主循环
        while True:
            handlers.process_frame()
            
    except KeyboardInterrupt:
        logger.info("⛔ 用户终止程序")
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
    finally:
        services.cleanup()


__all__ = ["run_game_loop"]
