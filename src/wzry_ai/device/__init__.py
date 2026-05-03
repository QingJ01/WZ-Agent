"""设备通信模块 - ADB、Scrcpy、模拟器管理"""

from wzry_ai.device.ADBTool import ADBTool, tap, swipe
from wzry_ai.device.emulator_manager import (
    EmulatorManager,
    EmulatorPortFinder,
    EmulatorWindowFinder,
    MuMuConfigManager,
    MuMuConfig,
    ADBPathFinder,
    get_adb_path,
    init_emulator,
    init_mumu,
    HAS_WIN32,
)


def __getattr__(name):
    """按需加载可选的 scrcpy 依赖。"""
    if name == "ScrcpyTool":
        from wzry_ai.device.ScrcpyTool import ScrcpyTool

        return ScrcpyTool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # ADB工具
    'ADBTool',
    'tap',
    'swipe',
    # Scrcpy工具
    'ScrcpyTool',
    # 模拟器管理
    'EmulatorManager',
    'EmulatorPortFinder',
    'EmulatorWindowFinder',
    'MuMuConfigManager',
    'MuMuConfig',
    'ADBPathFinder',
    'get_adb_path',
    'init_emulator',
    'init_mumu',
    'HAS_WIN32',
]
