"""
模拟器配置模块

功能说明：
    本模块配置MuMu安卓模拟器的连接参数，
    包括ADB路径、端口号、设备标识、窗口模式等，用于自动识别和连接模拟器。

参数说明：
    无直接参数，通过导入变量使用

返回值说明：
    无直接返回值，提供各类模拟器配置常量
"""

# ========== 模拟器 ADB 路径配置 ==========
# EMULATOR_ADB_PATHS字典定义了MuMu模拟器的ADB工具安装路径
# 程序会按顺序尝试这些路径，找到可用的ADB工具
EMULATOR_ADB_PATHS = {
    "mumu": [  # MuMu模拟器的ADB可能路径列表
        r"D:\MuMuPlayer\nx_main\adb.exe",  # MuMu主程序目录
        r"D:\MuMu\emulator\nemu\EmulatorShell\adb.exe",  # MuMu模拟器目录
        r"C:\Program Files\MuMu\emulator\nemu\EmulatorShell\adb.exe",  # 64位系统默认安装路径
        r"C:\Program Files (x86)\MuMu\emulator\nemu\EmulatorShell\adb.exe",  # 32位系统默认安装路径
    ],
}

# ========== 模拟器端口配置 ==========
# EMULATOR_PORTS字典定义了MuMu模拟器默认的ADB连接端口
# 多开模拟器时，端口号会依次递增
EMULATOR_PORTS = {
    "mumu": [
        7555,
        16384,
        5554,
        5555,
    ],  # MuMu模拟器默认端口：主实例7555，多开实例16384，标准端口5554/5555
}

# ========== 设备型号标识 ==========
# EMULATOR_MODELS字典定义了MuMu模拟器的设备型号标识字符串
# 用于通过ADB命令识别当前连接的是哪种模拟器
EMULATOR_MODELS = {
    "mumu": ["mumu", "netease", "vivo", "v2241a"],  # MuMu模拟器的设备标识
}

# ========== 窗口标题模式 ==========
# WINDOW_PATTERNS字典定义了MuMu模拟器窗口的标题关键词
# 用于通过窗口标题识别和定位模拟器窗口
WINDOW_PATTERNS = {
    "mumu": [  # MuMu模拟器可能的窗口标题（按优先级排序）
        "MuMu安卓设备",  # 最精确的匹配，MuMu 12+ 版本
        "MuMu模拟器",  # 较精确的匹配
        "MuMuPlayer",  # 旧版本或国际版
    ],
}

# ========== 标题排除关键词 ==========
# EXCLUDE_TITLE_KEYWORDS列表定义了需要排除的窗口标题关键词
# 用于避免误匹配 IDE 等其他应用程序窗口
EXCLUDE_TITLE_KEYWORDS = [
    "Qoder",  # Qoder IDE
    "PyCharm",  # PyCharm IDE
    "VSCode",  # VS Code
    "Visual Studio",  # Visual Studio
    "IntelliJ",  # IntelliJ IDEA
    "Cursor",  # Cursor IDE
    "Code",  # VS Code 等
    "Notepad++",  # Notepad++
    "Sublime",  # Sublime Text
]

# ========== 模拟器进程名配置 ==========
# MUMU_PROCESS_NAMES列表定义了MuMu模拟器的主进程名称
# 用于通过进程名查找模拟器窗口（不依赖窗口标题）
MUMU_PROCESS_NAMES = [
    "MuMuNxDevice.exe",  # MuMu 12+ 主窗口进程（最常用）
    "MuMuPlayer.exe",  # 旧版本主进程
    "MuMuVMMHeadless.exe",  # VMM 虚拟机进程
    "MuMuVMMSVC.exe",  # VMM 服务进程
    "NemuPlayer.exe",  # 旧版 Nemu 进程
]

# ========== 模拟器窗口类名配置 ==========
# MUMU_CLASS_NAMES列表定义了MuMu模拟器窗口的类名
# 用于通过窗口类名查找模拟器窗口（不依赖窗口标题）
# 注意：类名匹配会结合进程名验证，避免误匹配其他 Qt5 应用
MUMU_CLASS_NAMES = [
    "MuMuPlayer",  # MuMu 专用类名（最可靠）
    "Qt5156QWindowIcon",  # MuMu 12+ Qt 版本
    "Qt5154QWindowIcon",  # MuMu 特定 Qt 版本
    "Qt6QWindowIcon",  # MuMu Qt6 版本
    "Qt5QWindowIcon",  # 通用 Qt5 类名（需配合进程名验证使用）
]

# ========== 窗口分辨率配置 ==========
# 定义期望的模拟器窗口分辨率和边框尺寸
EXPECTED_WIDTH = 1920  # 期望窗口宽度（像素）
EXPECTED_HEIGHT = 1080  # 期望窗口高度（像素）
BORDER_WIDTH = 16  # 窗口边框宽度（像素）
TITLE_HEIGHT = 48  # 窗口标题栏高度（像素）

# ========== 扫描配置 ==========
# SCAN_DRIVES列表定义了自动扫描ADB工具时要搜索的磁盘分区
SCAN_DRIVES = ["C:", "D:", "E:"]  # 按优先级排序的磁盘分区列表

# ========== 配置文件路径 ==========
# 定义存储模拟器配置信息的JSON文件名
import os
from importlib import import_module

get_runtime_path_resolver = import_module(
    "wzry_ai.utils.resource_resolver"
).get_runtime_path_resolver

_PATH_RESOLVER = get_runtime_path_resolver()
PROJECT_ROOT = os.fspath(_PATH_RESOLVER.repo_root)
DATA_DIR = os.fspath(_PATH_RESOLVER.data_dir())  # 数据文件目录
CONFIG_FILE = os.fspath(
    _PATH_RESOLVER.resolve_data("mumu_config.json")
)  # MuMu模拟器配置文件
EMULATOR_MODELS_FILE = os.fspath(
    _PATH_RESOLVER.resolve_data("emulator_models.json")
)  # 模拟器型号信息文件
