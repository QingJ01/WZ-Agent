"""
模拟器管理器模块 - 支持MuMu模拟器

功能说明：
1. 自动查找MuMu模拟器窗口
2. 探测ADB端口并验证连接
3. 检查窗口分辨率（必须为1920x1080）
4. 缓存配置，避免重复探测
5. 自动识别和保存未知设备型号

支持的模拟器：
- MuMu模拟器（网易）
"""

# 导入JSON模块，用于配置文件读写
import json

# 导入操作系统模块，用于文件路径操作
import os

# 导入正则表达式模块，用于字符串匹配
import re

# 导入子进程模块，用于执行ADB命令
import subprocess

# 导入系统模块
import sys

# 导入时间模块，用于延时和格式化时间
import time

# 从并发模块导入线程池
from concurrent.futures import ThreadPoolExecutor, as_completed

# 从数据类模块导入工具函数和装饰器
from dataclasses import asdict, dataclass

# 从类型提示模块导入类型定义
from typing import Any, Dict, Optional, Tuple, cast

# 尝试导入Windows GUI库（仅在Windows平台可用）
try:
    # 导入Windows GUI相关模块
    import win32gui
    import win32con

    # 标记win32库可用
    HAS_WIN32 = True
except ImportError:
    # win32库不可用（可能在非Windows平台）
    win32gui = None
    win32con = None
    HAS_WIN32 = False

# 从日志工具模块导入获取日志记录器函数
from wzry_ai.utils.logging_utils import get_logger

# 从资源解析器导入规范 data 路径
from wzry_ai.utils.resource_resolver import resolve_data_path

# 获取当前模块的日志记录器对象
logger = get_logger(__name__)

# 尝试从配置模块导入模拟器ADB路径和扫描驱动器列表
try:
    from wzry_ai.config.emulator import EMULATOR_ADB_PATHS, SCAN_DRIVES
except ImportError:
    # 导入失败，使用默认配置
    # 定义MuMu模拟器的ADB可执行文件路径列表
    EMULATOR_ADB_PATHS = {
        "mumu": [  # MuMu模拟器路径列表
            r"D:\MuMuPlayer\nx_main\adb.exe",
            r"D:\MuMu\emulator\nemu\EmulatorShell\adb.exe",
            r"C:\Program Files\MuMu\emulator\nemu\EmulatorShell\adb.exe",
            r"C:\Program Files (x86)\MuMu\emulator\nemu\EmulatorShell\adb.exe",
        ],
    }
    # 定义全盘扫描时要扫描的驱动器列表
    SCAN_DRIVES = ["C:", "D:", "E:"]


# 定义ADB路径查找器类
class ADBPathFinder:
    """
    ADB路径查找器类 - 自动识别各模拟器的adb.exe

    功能说明：
    - 按优先级查找ADB可执行文件
    - 支持指定模拟器类型或自动检测
    - 支持全盘扫描作为后备方案

    查找优先级：
    1. 从运行中的 MuMu 进程推导
    2. 系统PATH中的adb
    3. 预设的模拟器路径
    4. 全盘扫描
    5. 系统默认'adb'命令
    """

    # 从配置模块引用路径列表（保持向后兼容）
    EMULATOR_ADB_PATHS = EMULATOR_ADB_PATHS
    SCAN_DRIVES = SCAN_DRIVES

    @classmethod
    def _find_adb_from_mumu_process(cls) -> Optional[str]:
        """
        从运行中的 MuMu 进程路径推导 ADB 路径

        功能说明：
        - 通过查找运行中的 MuMu 进程，获取其可执行文件路径
        - 根据 MuMu 的目录结构推导出 ADB 路径
        - 支持 MuMu 12 和旧版 MuMu 的目录结构

        Returns:
            推导出的 ADB 路径，如果找不到则返回 None
        """
        # 尝试导入 psutil
        try:
            import psutil as psutil_local

            HAS_PSUTIL_LOCAL = True
        except ImportError:
            psutil_local = None
            HAS_PSUTIL_LOCAL = False

        # 使用 psutil 获取进程信息
        if HAS_PSUTIL_LOCAL:
            if psutil_local is None:
                return None
            for proc in psutil_local.process_iter(["pid", "name", "exe"]):
                try:
                    if proc.info["name"] in MUMU_PROCESS_NAMES:
                        exe_path = proc.info["exe"]
                        if not exe_path:
                            continue

                        exe_dir = os.path.dirname(exe_path)

                        # MuMu 12: 同目录下或 shell/ 子目录
                        candidates = [
                            os.path.join(exe_dir, "adb.exe"),
                            os.path.join(exe_dir, "shell", "adb.exe"),
                            os.path.join(exe_dir, "tools", "adb.exe"),
                            # 可能在父目录的 shell/
                            os.path.join(os.path.dirname(exe_dir), "shell", "adb.exe"),
                            os.path.join(os.path.dirname(exe_dir), "adb.exe"),
                        ]

                        # 旧版 MuMu: EmulatorShell/ 子目录
                        candidates.extend(
                            [
                                os.path.join(exe_dir, "EmulatorShell", "adb.exe"),
                                os.path.join(
                                    os.path.dirname(exe_dir), "EmulatorShell", "adb.exe"
                                ),
                            ]
                        )

                        for adb_path in candidates:
                            if os.path.isfile(adb_path):
                                logger.info(
                                    f"从 MuMu 进程 '{proc.info['name']}' 推导出 ADB: {adb_path}"
                                )
                                return adb_path
                except (psutil_local.NoSuchProcess, psutil_local.AccessDenied, OSError):
                    continue

        # 如果 psutil 不可用，尝试使用 ctypes/win32process 获取进程路径
        elif HAS_WIN32PROCESS:
            try:
                import ctypes
                from ctypes import wintypes

                # 枚举所有进程
                kernel32 = ctypes.windll.kernel32
                psapi = ctypes.windll.psapi

                process_ids = (wintypes.DWORD * 1024)()
                cb_needed = wintypes.DWORD()

                if kernel32.EnumProcesses(
                    process_ids, ctypes.sizeof(process_ids), ctypes.byref(cb_needed)
                ):
                    num_processes = cb_needed.value // ctypes.sizeof(wintypes.DWORD)

                    for i in range(num_processes):
                        pid = process_ids[i]
                        if pid == 0:
                            continue

                        try:
                            # 打开进程获取模块名
                            h_process = kernel32.OpenProcess(
                                0x0410, False, pid
                            )  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                            if h_process:
                                # 获取进程可执行文件名
                                h_module = wintypes.HMODULE()
                                cb_needed_module = wintypes.DWORD()

                                if psapi.EnumProcessModules(
                                    h_process,
                                    ctypes.byref(h_module),
                                    ctypes.sizeof(h_module),
                                    ctypes.byref(cb_needed_module),
                                ):
                                    module_name = ctypes.create_unicode_buffer(260)
                                    if psapi.GetModuleBaseNameW(
                                        h_process, h_module, module_name, 260
                                    ):
                                        proc_name = module_name.value
                                        if proc_name in MUMU_PROCESS_NAMES:
                                            # 获取进程完整路径
                                            full_path_buf = (
                                                ctypes.create_unicode_buffer(260)
                                            )
                                            if psapi.GetModuleFileNameExW(
                                                h_process, h_module, full_path_buf, 260
                                            ):
                                                exe_path = full_path_buf.value
                                                exe_dir = os.path.dirname(exe_path)

                                                # 构建候选路径
                                                candidates = [
                                                    os.path.join(exe_dir, "adb.exe"),
                                                    os.path.join(
                                                        exe_dir, "shell", "adb.exe"
                                                    ),
                                                    os.path.join(
                                                        exe_dir, "tools", "adb.exe"
                                                    ),
                                                    os.path.join(
                                                        os.path.dirname(exe_dir),
                                                        "shell",
                                                        "adb.exe",
                                                    ),
                                                    os.path.join(
                                                        os.path.dirname(exe_dir),
                                                        "adb.exe",
                                                    ),
                                                    os.path.join(
                                                        exe_dir,
                                                        "EmulatorShell",
                                                        "adb.exe",
                                                    ),
                                                    os.path.join(
                                                        os.path.dirname(exe_dir),
                                                        "EmulatorShell",
                                                        "adb.exe",
                                                    ),
                                                ]

                                                for adb_path in candidates:
                                                    if os.path.isfile(adb_path):
                                                        logger.info(
                                                            f"从 MuMu 进程 '{proc_name}' 推导出 ADB: {adb_path}"
                                                        )
                                                        kernel32.CloseHandle(h_process)
                                                        return adb_path

                                kernel32.CloseHandle(h_process)
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"使用 win32process 获取进程路径失败: {e}")

        return None

    @classmethod
    def find_adb_path(cls, emulator_type: Optional[str] = None) -> str:
        """
        查找ADB可执行文件路径

        参数说明：
        - emulator_type: 指定模拟器类型（'mumu'），None表示自动检测

        返回值说明：
        - 返回ADB可执行文件的完整路径
        - 如果找不到，返回系统默认'adb'

        查找顺序：
        1. 从运行中的 MuMu 进程推导
        2. 系统PATH中的adb
        3. 根据模拟器类型查找预设路径
        4. 全盘扫描
        5. 返回系统默认'adb'
        """
        # 第1步：从运行中的 MuMu 进程推导 ADB 路径
        process_adb = cls._find_adb_from_mumu_process()
        if process_adb:
            logger.info(f"使用从 MuMu 进程推导的 ADB: {process_adb}")
            return process_adb

        # 第2步：检查系统PATH中的adb
        system_adb = cls._find_system_adb()
        if system_adb:
            logger.debug(f"使用系统 ADB: {system_adb}")
            return system_adb

        # 第3步：根据模拟器类型查找预设路径
        if emulator_type and emulator_type in cls.EMULATOR_ADB_PATHS:
            # 指定了模拟器类型，只查找该类型的路径
            path = cls._check_paths(cls.EMULATOR_ADB_PATHS[emulator_type])
            if path:
                return path
        else:
            # 未指定类型，自动扫描所有模拟器路径
            for emu_type, paths in cls.EMULATOR_ADB_PATHS.items():
                path = cls._check_paths(paths)
                if path:
                    logger.debug(f"找到 {emu_type} 的 ADB: {path}")
                    return path

        # 第4步：全盘扫描（作为最后的手段）
        logger.debug("常用路径未找到，开始全盘扫描...")
        scanned_path = cls._scan_disk_for_adb(emulator_type)
        if scanned_path:
            return scanned_path

        # 第5步：回退到系统默认adb命令
        logger.warning("未找到 ADB，使用系统默认 'adb'")
        logger.warning("建议: 请确保模拟器已安装")
        return "adb"

    @classmethod
    def _check_paths(cls, paths: list[str]) -> Optional[str]:
        """
        检查路径列表，返回第一个存在的文件

        参数说明：
        - paths: 路径列表（字符串列表）

        返回值说明：
        - 返回第一个存在的文件路径
        - 如果都不存在，返回None
        """
        # 遍历路径列表
        for path in paths:
            # 检查文件是否存在
            if os.path.isfile(path):
                # 存在，返回该路径
                return path
        # 都不存在，返回None
        return None

    @classmethod
    def _find_system_adb(cls) -> Optional[str]:
        """
        查找系统PATH中的adb

        返回值说明：
        - 返回系统PATH中找到的adb路径
        - 如果找不到，返回None

        功能说明：
        - 使用where命令查找adb
        - 处理编码问题（UTF-8和GBK）
        """
        try:
            # 执行where命令查找adb
            result = subprocess.run(
                ["where", "adb"],  # Windows下的查找命令
                capture_output=True,  # 捕获输出
                timeout=5,  # 超时5秒
            )
            # 检查命令是否成功执行
            if result.returncode == 0:
                # 解码输出，先尝试UTF-8，失败则尝试GBK
                output = result.stdout.decode(
                    "utf-8", errors="ignore"
                ) or result.stdout.decode("gbk", errors="ignore")
                # 按行分割输出
                paths = output.strip().split("\n")
                # 遍历找到的每个路径
                for path in paths:
                    # 去除空白字符
                    path = path.strip()
                    # 检查路径是否有效且文件存在
                    if path and os.path.isfile(path):
                        # 返回有效的adb路径
                        return path
        except (OSError, UnicodeDecodeError):
            # 查找过程中出错，忽略错误
            pass
        # 未找到系统adb，返回None
        return None

    @classmethod
    def _scan_disk_for_adb(cls, emulator_type: Optional[str] = None) -> Optional[str]:
        """
        全盘扫描 adb.exe

        Args:
            emulator_type: 指定模拟器类型，None 表示扫描所有

        Returns:
            找到的 ADB 路径或 None
        """
        target_names = ["adb.exe"]

        # 如果指定了模拟器类型，添加特定的文件名
        if emulator_type == "mumu":
            target_names = ["adb.exe", "nemu_adb.exe"]

        for drive in cls.SCAN_DRIVES:
            if not os.path.exists(drive + "\\"):
                continue

            logger.debug(f"扫描 {drive} 盘...")

            # 优先扫描 Program Files 和常见安装目录
            priority_dirs = [
                f"{drive}\\Program Files",
                f"{drive}\\Program Files (x86)",
                f"{drive}\\",
            ]

            for base_dir in priority_dirs:
                if not os.path.exists(base_dir):
                    continue

                try:
                    for root, dirs, files in os.walk(base_dir):
                        # 跳过一些不需要扫描的目录
                        dirs[:] = [
                            d
                            for d in dirs
                            if d.lower()
                            not in ["windows", "temp", "tmp", "cache", "$recycle.bin"]
                        ]

                        for file in files:
                            if file.lower() in target_names:
                                full_path = os.path.join(root, file)
                                # 验证这个 adb 是否可用
                                if cls._verify_adb(full_path):
                                    logger.debug(f"全盘扫描找到 ADB: {full_path}")
                                    return full_path
                except PermissionError:
                    continue
                except OSError as e:
                    continue

        return None

    @classmethod
    def _verify_adb(cls, path: str) -> bool:
        """验证 adb 是否可用"""
        try:
            # 使用 CREATE_NO_WINDOW 避免弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                [path, "version"],
                capture_output=True,
                timeout=5,
                startupinfo=startupinfo,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


# 全局ADB路径变量（延迟加载，首次使用时才查找）
_ADB_PATH = None


def get_adb_path(emulator_type: Optional[str] = None, auto_save: bool = True) -> str:
    """
    获取ADB路径（带缓存功能）

    参数说明：
    - emulator_type: 指定模拟器类型（'mumu'）
    - auto_save: 是否自动保存到缓存（默认True）

    返回值说明：
    - 返回ADB可执行文件的完整路径

    功能说明：
    - 优先使用 WZRY_ADB_PATH 环境变量
    - 其次从 mumu_config.json 缓存读取 ADB 路径
    - 缓存无效时，按优先级查找 ADB 路径
    - 找到新路径后自动保存到缓存
    """
    # 声明使用全局变量
    global _ADB_PATH
    env_adb_path = os.environ.get("WZRY_ADB_PATH")
    if env_adb_path:
        _ADB_PATH = os.path.expanduser(os.path.expandvars(env_adb_path))
        return _ADB_PATH

    # 检查缓存是否为空
    if _ADB_PATH is None:
        # 第1步：尝试从 mumu_config.json 缓存读取
        cached = MuMuConfigManager.load_cached_adb_path()
        if cached and os.path.isfile(cached):
            _ADB_PATH = cached
            logger.info(f"使用缓存的 ADB 路径: {cached}")
            return _ADB_PATH

        # 第2步：正常查找流程
        _ADB_PATH = ADBPathFinder.find_adb_path(emulator_type)

        # 第3步：保存到缓存（排除系统默认 'adb'）
        if _ADB_PATH and _ADB_PATH != "adb":
            MuMuConfigManager.save_adb_path(_ADB_PATH)
    # 返回缓存的ADB路径
    return _ADB_PATH or "adb"


# 检查win32库是否可用
if not HAS_WIN32:
    # win32库不可用，记录警告日志
    logger.warning("win32gui 未安装，窗口功能不可用")


# 使用dataclass装饰器定义MuMu配置数据类
@dataclass
class MuMuConfig:
    """
    MuMu配置数据类 - 存储模拟器配置信息

    属性说明：
    - port: ADB端口号（整数）
    - serial: ADB设备序列号（字符串，格式如"127.0.0.1:7555"）
    - window_title: 模拟器窗口标题（字符串）
    - window_rect: 窗口矩形区域（元组，格式为(left, top, right, bottom)）
    - client_size: 客户区大小（元组，格式为(width, height)）
    - saved_at: 配置保存时间（字符串，格式为'YYYY-MM-DD HH:MM:SS'）
    """

    port: int  # ADB端口号
    serial: str  # ADB设备序列号
    window_title: str  # 窗口标题
    window_rect: Tuple[int, int, int, int]  # 窗口矩形(left, top, right, bottom)
    client_size: Tuple[int, int]  # 客户区大小(width, height)
    saved_at: str  # 保存时间


# 尝试从配置模块导入端口和型号配置
try:
    from wzry_ai.config.emulator import EMULATOR_PORTS, EMULATOR_MODELS
except ImportError:
    # Fallback: 使用默认配置
    EMULATOR_PORTS = {
        "mumu": [5554, 5555, 7555, 16384],
    }
    EMULATOR_MODELS = {
        "mumu": ["mumu", "netease", "vivo", "v2241a"],
    }


# 定义模拟器端口查找器类
class EmulatorPortFinder:
    """
    模拟器端口查找器类 - 支持MuMu模拟器

    功能说明：
    - 自动查找MuMu模拟器的ADB端口
    - 支持缓存端口，避免重复扫描
    - 支持自动识别模拟器类型
    - 支持自动学习未知设备型号

    使用方式：
    - 创建实例后调用find_port()方法查找端口
    - 支持通过emulator_type参数指定模拟器类型
    """

    # 从配置模块引用（保持向后兼容）
    EMULATOR_PORTS = EMULATOR_PORTS
    EMULATOR_MODELS = EMULATOR_MODELS

    def __init__(self, adb_path: Optional[str] = None):
        """
        初始化端口查找器

        参数说明：
        - adb_path: ADB可执行文件路径，None表示自动查找
        """
        # 如果没有指定ADB路径，自动查找
        if adb_path is None:
            adb_path = get_adb_path()
        # 保存ADB路径
        self.adb_path = adb_path

        # 加载已保存的设备型号配置
        self._load_device_models()

    def find_port(
        self, prefer_cached: bool = True, emulator_type: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        查找模拟器端口

        Args:
            prefer_cached: 优先使用缓存的端口
            emulator_type: 指定模拟器类型 ('mumu')，None 表示自动检测

        Returns:
            (端口号, 模拟器类型) 或 (None, None)
        """
        # 1. 尝试缓存的端口
        if prefer_cached:
            cached_port = MuMuConfigManager.load_cached_port()
            cached_type = MuMuConfigManager.load_cached_emulator_type()
            if cached_port and self._test_port(cached_port):
                logger.info(
                    f"使用缓存端口: {cached_port} ({cached_type or '未知类型'})"
                )
                return cached_port, cached_type

        # 2. 如果指定了类型，只扫描该类型的端口
        if emulator_type and emulator_type in self.EMULATOR_PORTS:
            ports = self.EMULATOR_PORTS[emulator_type]
            logger.info(f"扫描 {emulator_type} 端口: {ports}")
            port = self._scan_ports(ports, emulator_type)
            if port:
                return port, emulator_type
        else:
            # 3. 自动扫描所有类型
            logger.info("自动扫描所有模拟器端口...")
            for emu_type, ports in self.EMULATOR_PORTS.items():
                logger.info(f"扫描 {emu_type} 端口: {ports}")
                port = self._scan_ports(ports, emu_type)
                if port:
                    return port, emu_type

        logger.error("未找到模拟器端口")
        return None, None

    def _scan_ports(self, ports: list, expected_type: str) -> Optional[int]:
        """并行扫描指定端口列表"""

        def _try_port(port):
            if self._test_port(port):
                detected_type = self._detect_emulator_type(port)
                if detected_type:
                    return port, detected_type
            return None

        with ThreadPoolExecutor(max_workers=min(len(ports), 4)) as executor:
            futures = {executor.submit(_try_port, p): p for p in ports}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    port, detected_type = result
                    logger.info(f"找到 {detected_type} 端口: {port}")
                    MuMuConfigManager.save_port(port, detected_type)
                    return port
        return None

    def _test_port(self, port: int) -> bool:
        """测试端口是否可连接"""
        try:
            serial = f"127.0.0.1:{port}"

            # 使用 CREATE_NO_WINDOW 避免弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # 1. 尝试连接
            adb_path = self.adb_path
            cmd = f"{adb_path} connect {serial}"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=2, startupinfo=startupinfo
            )
            # 使用 errors='ignore' 避免编码问题
            stdout = (
                result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
            )
            stderr = (
                result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""
            )
            output = (stdout + stderr).lower()

            # 检查是否连接成功
            if not ("connected" in output or "already connected" in output):
                return False

            # 2. 验证设备是否真正可用（执行一个简单的 adb 命令）
            test_cmd = f"{adb_path} -s {serial} shell echo ok"
            test_result = subprocess.run(
                test_cmd,
                shell=True,
                capture_output=True,
                timeout=2,
                startupinfo=startupinfo,
            )
            test_output = (
                test_result.stdout.decode("utf-8", errors="ignore")
                if test_result.stdout
                else ""
            )

            if "ok" in test_output.lower():
                logger.info(f"端口 {port} 设备可用")
                return True
            else:
                logger.warning(f"端口 {port} 连接成功但设备不可用")
                return False

        except subprocess.TimeoutExpired:
            logger.warning(f"端口 {port} 连接超时")
            return False
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"测试端口 {port} 失败: {e}", exc_info=True)
            return False

    def _detect_emulator_type(self, port: int) -> Optional[str]:
        """检测模拟器类型"""
        try:
            # 使用 CREATE_NO_WINDOW 避免弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # 获取设备型号
            adb_path = self.adb_path
            cmd = f"{adb_path} -s 127.0.0.1:{port} shell getprop ro.product.model"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=5, startupinfo=startupinfo
            )
            model = result.stdout.decode("utf-8", errors="ignore").strip().lower()
            logger.info(f"设备型号: {model}")

            # 检查匹配哪个模拟器
            for emu_type, keywords in self.EMULATOR_MODELS.items():
                for keyword in keywords:
                    if keyword.lower() in model:
                        return emu_type

            # 如果型号不匹配，尝试通过制造商判断
            cmd = (
                f"{adb_path} -s 127.0.0.1:{port} shell getprop ro.product.manufacturer"
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=5, startupinfo=startupinfo
            )
            manufacturer = (
                result.stdout.decode("utf-8", errors="ignore").strip().lower()
            )
            logger.info(f"制造商: {manufacturer}")

            for emu_type, keywords in self.EMULATOR_MODELS.items():
                for keyword in keywords:
                    if keyword.lower() in manufacturer:
                        return emu_type

            # 如果都没匹配到，但端口是已知MuMu端口，则自动添加到 mumu 类型
            # 并保存到配置文件
            if model:
                logger.info(f"未知设备型号 '{model}'，尝试自动识别...")
                detected = self._auto_learn_device_model(port, model, manufacturer)
                if detected:
                    return detected

            return None
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as e:
            logger.error(f"检测设备类型失败: {e}", exc_info=True)
            return None

    def _auto_learn_device_model(
        self, port: int, model: str, manufacturer: str
    ) -> Optional[str]:
        """
        自动学习并保存未知设备型号

        根据端口号推断模拟器类型，并将新型号添加到配置
        """
        # 根据端口推断模拟器类型
        inferred_type = None
        if port in self.EMULATOR_PORTS["mumu"]:
            inferred_type = "mumu"

        if not inferred_type:
            return None

        # 添加到 EMULATOR_MODELS
        if model not in self.EMULATOR_MODELS[inferred_type]:
            self.EMULATOR_MODELS[inferred_type].append(model)
            logger.info(f"自动添加新型号 '{model}' 到 {inferred_type}")

        if manufacturer and manufacturer not in self.EMULATOR_MODELS[inferred_type]:
            self.EMULATOR_MODELS[inferred_type].append(manufacturer)
            logger.info(f"自动添加新制造商 '{manufacturer}' 到 {inferred_type}")

        # 保存到配置文件
        self._save_device_models()

        return inferred_type

    def _save_device_models(self):
        """保存设备型号配置到文件"""
        try:
            config_file = os.fspath(resolve_data_path("emulator_models.json"))
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.EMULATOR_MODELS, f, indent=2, ensure_ascii=False)
            logger.debug(f"设备型号配置已保存到 {config_file}")
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"保存设备型号配置失败: {e}", exc_info=True)

    def _load_device_models(self):
        """从文件加载设备型号配置"""
        try:
            config_file = os.fspath(resolve_data_path("emulator_models.json"))
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # 合并到现有配置
                    for emu_type, models in loaded.items():
                        if emu_type in self.EMULATOR_MODELS:
                            for model in models:
                                if model not in self.EMULATOR_MODELS[emu_type]:
                                    self.EMULATOR_MODELS[emu_type].append(model)
                    logger.debug(f"已加载设备型号配置")
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"加载设备型号配置失败: {e}", exc_info=True)


# 尝试从配置模块导入窗口模式和分辨率配置
try:
    from wzry_ai.config.emulator import (
        WINDOW_PATTERNS,
        EXPECTED_WIDTH,
        EXPECTED_HEIGHT,
        BORDER_WIDTH,
        TITLE_HEIGHT,
        MUMU_PROCESS_NAMES,
        MUMU_CLASS_NAMES,
        EXCLUDE_TITLE_KEYWORDS,
    )
except ImportError:
    # Fallback: 使用默认配置
    WINDOW_PATTERNS = {
        "mumu": [
            "MuMu安卓设备",
            "MuMu模拟器",
            "MuMuPlayer",
            "MuMu",
        ],
    }
    EXPECTED_WIDTH = 1920
    EXPECTED_HEIGHT = 1080
    BORDER_WIDTH = 16
    TITLE_HEIGHT = 48
    MUMU_PROCESS_NAMES = [
        "MuMuNxDevice.exe",
        "MuMuPlayer.exe",
        "MuMuVMMHeadless.exe",
        "MuMuVMMSVC.exe",
        "NemuPlayer.exe",
    ]
    MUMU_CLASS_NAMES = [
        "MuMuPlayer",
        "Qt5156QWindowIcon",
        "Qt5154QWindowIcon",
        "Qt6QWindowIcon",
        "Qt5QWindowIcon",
        "QWindowIcon",
    ]
    EXCLUDE_TITLE_KEYWORDS = [
        "Qoder",
        "PyCharm",
        "VSCode",
        "Visual Studio",
        "IntelliJ",
        "Cursor",
        "Code",
        "Notepad++",
        "Sublime",
    ]

# 尝试导入 psutil 用于进程查找
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False
    logger.debug("psutil 未安装，将使用 win32process 进行进程查找")

# 尝试导入 win32process 用于获取进程信息
try:
    import win32process

    HAS_WIN32PROCESS = True
except ImportError:
    win32process = None
    HAS_WIN32PROCESS = False


# 定义模拟器窗口查找器类
class EmulatorWindowFinder:
    """
    模拟器窗口查找器类 - 支持MuMu模拟器

    功能说明：
    - 自动查找MuMu模拟器窗口
    - 检查窗口分辨率是否符合要求
    - 支持多窗口情况下的智能选择
    - 支持指定模拟器类型或自动检测

    使用方式：
    - 创建实例后调用find_window()方法查找窗口
    - 支持通过emulator_type参数指定模拟器类型
    """

    # 从配置模块引用（保持向后兼容）
    WINDOW_PATTERNS = WINDOW_PATTERNS
    EXPECTED_WIDTH = EXPECTED_WIDTH
    EXPECTED_HEIGHT = EXPECTED_HEIGHT
    BORDER_WIDTH = BORDER_WIDTH
    TITLE_HEIGHT = TITLE_HEIGHT

    def __init__(self):
        """
        初始化窗口查找器

        异常说明：
        - 如果win32gui未安装，抛出RuntimeError异常
        """
        # 检查win32库是否可用
        if not HAS_WIN32:
            # win32库不可用，抛出异常
            raise RuntimeError("win32gui 未安装，无法查找窗口")

    def _find_by_process(self) -> list:
        """
        通过进程名查找 MuMu 窗口

        返回：
            列表，每个元素为 (hwnd, title, rect, 'mumu')
        """
        if win32gui is None or win32process is None:
            logger.debug("win32process 不可用，跳过进程名匹配")
            return []

        win32gui_module = cast(Any, win32gui)
        win32process_module = cast(Any, win32process)
        psutil_module = cast(Any, psutil) if psutil is not None else None

        logger.debug(f"进程名匹配: 开始扫描进程，目标进程名: {MUMU_PROCESS_NAMES}")

        # 获取所有 MuMu 进程的 PID
        mumu_pids = set()
        found_processes = []  # 记录找到的进程详情用于调试

        if psutil_module is not None:
            # 使用 psutil 获取进程信息
            try:
                for proc in psutil_module.process_iter(["pid", "name"]):
                    try:
                        proc_name = proc.info["name"]
                        if proc_name in MUMU_PROCESS_NAMES:
                            mumu_pids.add(proc.info["pid"])
                            found_processes.append(
                                f"{proc_name}(PID={proc.info['pid']})"
                            )
                    except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                        continue
            except Exception as e:
                logger.debug(f"psutil 获取进程信息失败: {e}")
        else:
            # 使用 win32process 获取进程信息
            try:
                import ctypes
                from ctypes import wintypes

                # 枚举所有进程
                kernel32 = ctypes.windll.kernel32
                EnumProcesses = kernel32.EnumProcesses
                EnumProcesses.argtypes = [
                    wintypes.LPDWORD,
                    wintypes.DWORD,
                    wintypes.LPDWORD,
                ]
                EnumProcesses.restype = wintypes.BOOL

                # 获取进程列表
                process_ids = (wintypes.DWORD * 1024)()
                cb_needed = wintypes.DWORD()

                if EnumProcesses(
                    process_ids, ctypes.sizeof(process_ids), ctypes.byref(cb_needed)
                ):
                    num_processes = cb_needed.value // ctypes.sizeof(wintypes.DWORD)

                    for i in range(num_processes):
                        pid = process_ids[i]
                        if pid == 0:
                            continue
                        try:
                            # 打开进程获取模块名
                            h_process = kernel32.OpenProcess(
                                0x0410, False, pid
                            )  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                            if h_process:
                                # 获取进程可执行文件名
                                h_module = wintypes.HMODULE()
                                cb_needed_module = wintypes.DWORD()

                                if ctypes.windll.psapi.EnumProcessModules(
                                    h_process,
                                    ctypes.byref(h_module),
                                    ctypes.sizeof(h_module),
                                    ctypes.byref(cb_needed_module),
                                ):
                                    module_name = ctypes.create_unicode_buffer(260)
                                    if ctypes.windll.psapi.GetModuleBaseNameW(
                                        h_process, h_module, module_name, 260
                                    ):
                                        proc_name = module_name.value
                                        if proc_name in MUMU_PROCESS_NAMES:
                                            mumu_pids.add(pid)
                                            found_processes.append(
                                                f"{proc_name}(PID={pid})"
                                            )
                                kernel32.CloseHandle(h_process)
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"win32process 获取进程信息失败: {e}")

        if not mumu_pids:
            logger.debug("进程名匹配: 未找到 MuMu 进程")
            return []

        logger.debug(
            f"进程名匹配: 找到 {len(mumu_pids)} 个 MuMu 进程: {found_processes}"
        )

        # 枚举所有窗口，找到属于 MuMu 进程的可见窗口
        results = []
        skipped_tool = 0

        # 需要排除的工具窗口类名（这些不是渲染窗口）
        EXCLUDED_CLASS_NAMES = [
            "Qt5156QWindowToolSaveBits",
            "Qt5154QWindowToolSaveBits",
            "Qt6QWindowToolSaveBits",
            "Qt5QWindowToolSaveBits",
            "Qt5156QWindowTool",
            "Qt5154QWindowTool",
        ]

        def callback(hwnd, _):
            nonlocal skipped_tool
            try:
                if win32gui_module.IsWindowVisible(hwnd):
                    _, pid = win32process_module.GetWindowThreadProcessId(hwnd)
                    if pid in mumu_pids:
                        # 排除工具窗口
                        cls_name = win32gui_module.GetClassName(hwnd)
                        if any(
                            excluded in cls_name for excluded in EXCLUDED_CLASS_NAMES
                        ):
                            skipped_tool += 1
                            logger.debug(f"进程匹配: 跳过工具窗口 (class='{cls_name}')")
                            return

                        title = win32gui_module.GetWindowText(hwnd)
                        rect = win32gui_module.GetWindowRect(hwnd)
                        # 过滤掉太小的窗口（可能是工具窗口）
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 800 and h > 600 and title:
                            results.append((hwnd, title, rect, "mumu"))
                            logger.debug(f"进程匹配窗口: '{title}' ({w}x{h}) PID={pid}")
            except Exception as e:
                pass

        win32gui_module.EnumWindows(callback, None)

        if skipped_tool > 0:
            logger.debug(f"进程名匹配: 跳过 {skipped_tool} 个工具窗口")

        return results

    def _find_by_class(self) -> list:
        """
        通过窗口类名 + 进程名联合查找 MuMu 窗口

        类名匹配需要结合进程名验证，避免误匹配其他 Qt5 应用（如 Qoder IDE）

        返回：
            列表，每个元素为 (hwnd, title, rect, 'mumu')
        """
        results = []
        skipped_non_mumu = 0  # 记录因进程名不匹配而跳过的窗口数
        skipped_tool_window = 0  # 记录因工具窗口而跳过的窗口数

        if win32gui is None:
            return results

        win32gui_module = cast(Any, win32gui)
        win32process_module = (
            cast(Any, win32process) if win32process is not None else None
        )
        psutil_module = cast(Any, psutil) if psutil is not None else None

        logger.debug(f"类名匹配: 开始扫描窗口，目标类名: {MUMU_CLASS_NAMES}")

        # 需要排除的工具窗口类名（这些不是渲染窗口）
        EXCLUDED_CLASS_NAMES = [
            "Qt5156QWindowToolSaveBits",
            "Qt5154QWindowToolSaveBits",
            "Qt6QWindowToolSaveBits",
            "Qt5QWindowToolSaveBits",
            "Qt5156QWindowTool",
            "Qt5154QWindowTool",
        ]

        def callback(hwnd, _):
            nonlocal skipped_non_mumu, skipped_tool_window
            try:
                if win32gui_module.IsWindowVisible(hwnd):
                    cls_name = win32gui_module.GetClassName(hwnd)

                    # 排除工具窗口（这些不是渲染窗口）
                    if any(excluded in cls_name for excluded in EXCLUDED_CLASS_NAMES):
                        skipped_tool_window += 1
                        title = win32gui_module.GetWindowText(hwnd)
                        logger.debug(
                            f"类名匹配: 跳过工具窗口 '{title}' (class='{cls_name}')"
                        )
                        return

                    if any(pattern in cls_name for pattern in MUMU_CLASS_NAMES):
                        # 额外验证：检查窗口所属进程是否为 MuMu
                        if (
                            win32process_module is not None
                            and psutil_module is not None
                        ):
                            try:
                                _, pid = win32process_module.GetWindowThreadProcessId(
                                    hwnd
                                )
                                proc = psutil_module.Process(pid)
                                if proc.name() not in MUMU_PROCESS_NAMES:
                                    skipped_non_mumu += 1
                                    logger.debug(
                                        f"类名匹配: 跳过非 MuMu 进程窗口 '{win32gui_module.GetWindowText(hwnd)}' (PID={pid}, 进程={proc.name()})"
                                    )
                                    return  # 不是 MuMu 进程，跳过
                            except (
                                psutil_module.NoSuchProcess,
                                psutil_module.AccessDenied,
                            ):
                                pass  # 无法获取进程名时，继续检查其他条件
                            except Exception:
                                pass  # 其他错误，继续检查

                        title = win32gui_module.GetWindowText(hwnd)
                        rect = win32gui_module.GetWindowRect(hwnd)
                        # 过滤掉太小的窗口（可能是工具窗口）
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 800 and h > 600 and title:
                            results.append((hwnd, title, rect, "mumu"))
                            logger.debug(
                                f"类名匹配窗口: '{title}' 类名='{cls_name}' ({w}x{h})"
                            )
            except Exception as e:
                pass

        win32gui_module.EnumWindows(callback, None)

        if skipped_non_mumu > 0:
            logger.debug(f"类名匹配: 跳过 {skipped_non_mumu} 个非 MuMu 进程窗口")
        if skipped_tool_window > 0:
            logger.debug(f"类名匹配: 跳过 {skipped_tool_window} 个工具窗口")
        logger.debug(f"类名匹配: 找到 {len(results)} 个有效窗口")

        return results

    def _scan_windows_by_title(self) -> list:
        """
        通过窗口标题匹配查找 MuMu 窗口（兜底策略）

        标题匹配会排除 IDE 等容易误匹配的窗口

        返回：
            列表，每个元素为 (hwnd, title, rect, 'mumu')
        """
        windows = self._enum_visible_windows()
        results = []
        skipped_ide = 0  # 记录因 IDE 关键词而跳过的窗口数

        if win32gui is None:
            return results

        win32gui_module = cast(Any, win32gui)

        logger.debug(f"标题匹配: 开始扫描窗口，目标模式: {self.WINDOW_PATTERNS}")
        logger.debug(f"标题匹配: 排除关键词: {EXCLUDE_TITLE_KEYWORDS}")

        for emu_type, patterns in self.WINDOW_PATTERNS.items():
            for pattern in patterns:
                for hwnd, title in windows:
                    if not title:
                        continue

                    # 排除 IDE 等误匹配窗口
                    if any(kw in title for kw in EXCLUDE_TITLE_KEYWORDS):
                        skipped_ide += 1
                        logger.debug(f"标题匹配: 跳过 IDE 窗口 '{title}'")
                        continue

                    if pattern in title:
                        try:
                            rect = win32gui_module.GetWindowRect(hwnd)
                            w = rect[2] - rect[0]
                            h = rect[3] - rect[1]
                            # 过滤掉太小的窗口（可能是工具窗口）
                            if w > 800 and h > 600:
                                results.append((hwnd, title, rect, emu_type))
                                logger.debug(f"标题匹配窗口: '{title}' ({w}x{h})")
                        except Exception:
                            continue

        if skipped_ide > 0:
            logger.debug(f"标题匹配: 跳过 {skipped_ide} 个 IDE 窗口")
        logger.debug(f"标题匹配: 找到 {len(results)} 个有效窗口")

        return results

    def find_window(
        self, check_resolution: bool = True, emulator_type: Optional[str] = None
    ) -> Tuple[int, str, Tuple[int, int, int, int], str]:
        """
        查找模拟器窗口（三重 fallback 机制）

        查找策略：
        1. 优先：进程名匹配 — 通过 MuMuPlayer.exe 等进程找到对应窗口
        2. 其次：窗口类名匹配 — 通过 MuMu 特有的窗口 class name 匹配
        3. 兜底：标题匹配 — 保留现有的标题模式匹配作为最后手段

        多窗口策略：
        - 有多个窗口时，只选择分辨率符合要求的窗口（屏蔽不符合的）
        - 只有一个窗口但分辨率不符合时，报错并退出

        Args:
            check_resolution: 是否检查分辨率
            emulator_type: 指定模拟器类型 ('mumu')，None 表示自动检测

        Returns:
            (hwnd, title, rect, detected_type)

        Raises:
            RuntimeError: 未找到窗口或分辨率不符合要求
        """
        logger.info(f"正在查找MuMu模拟器窗口...")

        candidates = []
        match_method = None

        # Step 1: 进程名匹配（优先）
        candidates = self._find_by_process()
        if candidates:
            match_method = "进程名"
            logger.info(f"通过进程名匹配找到 {len(candidates)} 个 MuMu 窗口")

        # Step 2: 类名匹配（其次）
        if not candidates:
            candidates = self._find_by_class()
            if candidates:
                match_method = "窗口类名"
                logger.info(f"通过窗口类名匹配找到 {len(candidates)} 个 MuMu 窗口")

        # Step 3: 标题匹配（兜底）
        if not candidates:
            candidates = self._scan_windows_by_title()
            if candidates:
                match_method = "窗口标题"
                logger.info(f"通过窗口标题匹配找到 {len(candidates)} 个 MuMu 窗口")

        if not candidates:
            raise RuntimeError(
                "未找到MuMu模拟器窗口！\n"
                "请确保:\n"
                "1. MuMu模拟器已启动\n"
                "2. 模拟器窗口可见\n"
                "3. 窗口标题包含MuMu字样\n\n"
                "支持的窗口标题:\n"
                "- MuMu安卓设备\n"
                "- MuMu模拟器\n"
                "- MuMuPlayer\n"
                "- MuMu"
            )

        # 处理找到的窗口（分辨率检查等）
        result = self._process_candidates(
            candidates, check_resolution, match_method or "未知"
        )
        if result:
            return result

        raise RuntimeError("处理窗口候选时出错")

    def _process_candidates(
        self, candidates: list, check_resolution: bool, match_method: str
    ) -> Optional[Tuple[int, str, Tuple[int, int, int, int], str]]:
        """
        处理候选窗口列表，进行分辨率检查并选择最佳窗口

        Args:
            candidates: 候选窗口列表，每个元素为 (hwnd, title, rect, emu_type)
            check_resolution: 是否检查分辨率
            match_method: 匹配方式（用于日志）

        Returns:
            (hwnd, title, rect, emu_type) 或 None
        """
        if not candidates:
            return None

        # 去重（按 hwnd）
        seen_hwnds = set()
        unique_candidates = []
        for candidate in candidates:
            hwnd = candidate[0]
            if hwnd not in seen_hwnds:
                seen_hwnds.add(hwnd)
                unique_candidates.append(candidate)
        candidates = unique_candidates

        logger.info(f"找到 {len(candidates)} 个候选窗口（匹配方式: {match_method}）")
        for hwnd, title, rect, emu_type in candidates:
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            logger.info(f"  候选窗口: '{title}' ({w}x{h})")

        if not check_resolution:
            # 不检查分辨率，返回第一个
            hwnd, title, rect, emu_type = candidates[0]
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            logger.info(
                f"选择窗口（不检查分辨率）: '{title}' ({w}x{h}) [匹配方式: {match_method}]"
            )
            return hwnd, title, rect, emu_type

        # 按分辨率过滤
        valid_windows = []
        invalid_windows = []

        for hwnd, title, rect, emu_type in candidates:
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if self._is_resolution_valid(w, h):
                valid_windows.append((hwnd, title, rect, emu_type, w, h))
            else:
                invalid_windows.append((hwnd, title, rect, emu_type, w, h))

        # 多窗口情况：屏蔽不符合分辨率的
        if len(candidates) > 1:
            if invalid_windows:
                for hwnd, title, rect, emu_type, w, h in invalid_windows:
                    logger.warning(f"屏蔽窗口（分辨率不符合）: '{title}' ({w}x{h})")

            if valid_windows:
                hwnd, title, rect, emu_type, w, h = valid_windows[0]
                logger.info(f"选择窗口: '{title}' ({w}x{h}) [匹配方式: {match_method}]")
                return hwnd, title, rect, emu_type
            else:
                # 多个窗口但都不符合分辨率，报错退出
                raise RuntimeError(
                    f"找到 {len(candidates)} 个模拟器窗口，但均不符合分辨率要求！\n"
                    + self._format_resolution_error(
                        invalid_windows[0][4], invalid_windows[0][5]
                    )
                )

        # 单窗口情况
        hwnd, title, rect, emu_type = candidates[0]
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]

        if valid_windows:
            logger.info(f"选择窗口: '{title}' ({w}x{h}) [匹配方式: {match_method}]")
            logger.info(f"分辨率检查通过")
            return hwnd, title, rect, emu_type
        else:
            # 单个窗口且分辨率不符合，报错退出
            raise RuntimeError(self._format_resolution_error(w, h))

    def _scan_windows_multi(
        self, windows: list, patterns: list, check_resolution: bool, emu_type: str
    ) -> Optional[Tuple[int, str, Tuple[int, int, int, int]]]:
        """
        扫描多窗口，支持分辨率过滤（兼容旧代码）

        多窗口策略：
        - 先收集所有匹配的模拟器窗口
        - 如果有多个窗口，只保留分辨率符合要求的
        - 如果只有一个窗口且分辨率不符合，报错退出
        """
        if win32gui is None:
            return None

        win32gui_module = cast(Any, win32gui)

        # 第一步：收集所有匹配的模拟器窗口
        all_matched = []
        for pattern in patterns:
            for hwnd, title in windows:
                if pattern in title:
                    try:
                        rect = win32gui_module.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        # 过滤掉太小的窗口（可能是工具窗口）
                        if w > 800 and h > 600:
                            all_matched.append((hwnd, title, rect, w, h))
                            logger.info(f"候选窗口: '{title}' ({w}x{h})")
                    except Exception:  # win32gui 可能抛出 pywintypes.error
                        continue

        if not all_matched:
            return None

        logger.info(f"找到 {len(all_matched)} 个{emu_type}模拟器窗口")

        if not check_resolution:
            # 不检查分辨率，返回第一个
            hwnd, title, rect, w, h = all_matched[0]
            logger.info(f"选择窗口: '{title}' ({w}x{h})")
            return hwnd, title, rect

        # 第二步：按分辨率过滤
        valid_windows = []
        invalid_windows = []

        for hwnd, title, rect, w, h in all_matched:
            if self._is_resolution_valid(w, h):
                valid_windows.append((hwnd, title, rect, w, h))
            else:
                invalid_windows.append((hwnd, title, rect, w, h))

        # 多窗口情况：屏蔽不符合分辨率的
        if len(all_matched) > 1:
            if invalid_windows:
                for hwnd, title, rect, w, h in invalid_windows:
                    logger.warning(f"屏蔽窗口（分辨率不符合）: '{title}' ({w}x{h})")

            if valid_windows:
                hwnd, title, rect, w, h = valid_windows[0]
                logger.info(f"选择窗口: '{title}' ({w}x{h})")
                return hwnd, title, rect
            else:
                # 多个窗口但都不符合分辨率，报错退出
                raise RuntimeError(
                    f"找到 {len(all_matched)} 个模拟器窗口，但均不符合分辨率要求！\n"
                    + self._format_resolution_error(
                        all_matched[0][3], all_matched[0][4]
                    )
                )

        # 单窗口情况
        hwnd, title, rect, w, h = all_matched[0]
        logger.info(f"找到窗口: '{title}' ({w}x{h})")

        if valid_windows:
            logger.info(f"分辨率检查通过")
            return hwnd, title, rect
        else:
            # 单个窗口且分辨率不符合，报错退出
            raise RuntimeError(self._format_resolution_error(w, h))

    def _is_resolution_valid(self, window_width: int, window_height: int) -> bool:
        """检查窗口分辨率是否符合要求"""
        expected_window_width = self.EXPECTED_WIDTH + self.BORDER_WIDTH
        expected_window_height = self.EXPECTED_HEIGHT + self.TITLE_HEIGHT
        tolerance = 100

        width_diff = abs(window_width - expected_window_width)
        height_diff = abs(window_height - expected_window_height)

        return width_diff <= tolerance and height_diff <= tolerance

    def _format_resolution_error(self, window_width: int, window_height: int) -> str:
        """格式化分辨率错误信息"""
        expected_window_width = self.EXPECTED_WIDTH + self.BORDER_WIDTH
        expected_window_height = self.EXPECTED_HEIGHT + self.TITLE_HEIGHT
        return (
            f"模拟器窗口分辨率不符合要求！\n"
            f"当前窗口大小: {window_width}x{window_height}\n"
            f"期望窗口大小: {expected_window_width}x{expected_window_height}\n"
            f"对应客户区: {self.EXPECTED_WIDTH}x{self.EXPECTED_HEIGHT}\n\n"
            f"请按以下步骤调整:\n"
            f"1. 打开模拟器设置\n"
            f"2. 进入 '显示' 或 '分辨率' 设置\n"
            f"3. 设置为 1920x1080\n"
            f"4. 重启模拟器"
        )

    def _enum_visible_windows(self) -> list:
        """枚举所有可见窗口"""
        windows = []

        if win32gui is None:
            return windows

        win32gui_module = cast(Any, win32gui)

        def callback(hwnd, extra):
            try:
                if win32gui_module.IsWindowVisible(hwnd):
                    title = win32gui_module.GetWindowText(hwnd)
                    if title:
                        windows.append((hwnd, title))
            except Exception as e:  # win32gui 可能抛出 pywintypes.error
                # 忽略枚举过程中的错误
                pass

        try:
            win32gui_module.EnumWindows(callback, None)
        except Exception as e:  # win32gui 可能抛出 pywintypes.error
            logger.error(f"枚举窗口时出错: {e}", exc_info=True)

        return windows

    def _is_valid_window(self, hwnd: int) -> bool:
        """验证窗口是否有效"""
        is_valid, _ = self._is_valid_window_with_reason(hwnd)
        return is_valid

    def _is_valid_window_with_reason(self, hwnd: int) -> tuple:
        """验证窗口是否有效，返回原因"""
        if win32gui is None:
            return False, "win32gui 不可用"

        win32gui_module = cast(Any, win32gui)

        if not win32gui_module.IsWindow(hwnd):
            return False, "不是有效窗口"
        if not win32gui_module.IsWindowVisible(hwnd):
            return False, "不可见"

        try:
            rect = win32gui_module.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # 窗口必须足够大
            if width <= 200 or height <= 200:
                return False, f"太小 ({width}x{height})"
        except Exception as e:  # win32gui 可能抛出 pywintypes.error
            return False, f"获取窗口大小失败: {e}"

        return True, "有效"

    def _check_resolution(self, window_width: int, window_height: int):
        """检查窗口分辨率"""
        # 计算期望的窗口大小（包含边框）
        expected_window_width = self.EXPECTED_WIDTH + self.BORDER_WIDTH
        expected_window_height = self.EXPECTED_HEIGHT + self.TITLE_HEIGHT

        # 允许一定的误差
        tolerance = 100

        width_diff = abs(window_width - expected_window_width)
        height_diff = abs(window_height - expected_window_height)

        if width_diff > tolerance or height_diff > tolerance:
            raise RuntimeError(
                f"模拟器窗口分辨率不符合要求！\n"
                f"当前窗口大小: {window_width}x{window_height}\n"
                f"期望窗口大小: {expected_window_width}x{expected_window_height}\n"
                f"对应客户区: {self.EXPECTED_WIDTH}x{self.EXPECTED_HEIGHT}\n\n"
                f"请按以下步骤调整:\n"
                f"1. 打开模拟器设置\n"
                f"2. 进入 '显示' 或 '分辨率' 设置\n"
                f"3. 设置为 1920x1080\n"
                f"4. 重启模拟器"
            )

        logger.info(f"分辨率检查通过")


# 定义MuMu配置管理器类
class MuMuConfigManager:
    """
    MuMu配置管理器类 - 管理模拟器配置的缓存读写

    功能说明：
    - 保存和读取模拟器端口配置
    - 保存和读取完整配置信息
    - 支持清除缓存

    配置文件：
    - 默认配置文件名为'mumu_config.json'
    - 存储在程序运行目录
    """

    # 配置文件名（使用类方法获取绝对路径，保存到 data/ 目录）
    @classmethod
    def _get_config_file(cls) -> str:
        """获取配置文件路径"""
        from wzry_ai.utils.resource_resolver import resolve_data_path

        return os.fspath(resolve_data_path("mumu_config.json"))

    @classmethod
    def load_cached_port(cls) -> Optional[int]:
        """
        读取缓存的端口

        返回值说明：
        - 返回缓存的端口号（整数）
        - 如果没有缓存或读取失败，返回None
        """
        try:
            config_file = cls._get_config_file()
            # 检查配置文件是否存在
            if os.path.exists(config_file):
                # 打开并读取配置文件
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # 获取端口配置
                    port = config.get("port")
                    if port:
                        # 记录读取到的端口
                        logger.debug(f"读取缓存端口: {port}")
                        return port
        except (OSError, json.JSONDecodeError, KeyError) as e:
            # 读取失败，记录错误日志
            logger.error(f"读取缓存失败: {e}", exc_info=True)
        # 读取失败或没有缓存，返回None
        return None

    @classmethod
    def load_cached_emulator_type(cls) -> Optional[str]:
        """读取缓存的模拟器类型"""
        try:
            config_file = cls._get_config_file()
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("emulator_type")
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取缓存失败: {e}", exc_info=True)
        return None

    @classmethod
    def save_port(cls, port: int, emulator_type: Optional[str] = None):
        """保存端口到缓存"""
        try:
            config_file = cls._get_config_file()
            config = {
                "port": port,
                "emulator_type": emulator_type,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            type_str = f" ({emulator_type})" if emulator_type else ""
            logger.debug(f"端口已保存: {port}{type_str}")
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)

    @classmethod
    def load_full_config(cls) -> Optional["MuMuConfig"]:
        """读取完整配置"""
        try:
            config_file = cls._get_config_file()
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return MuMuConfig(**data)
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"读取配置失败: {e}", exc_info=True)
        return None

    @classmethod
    def save_full_config(cls, config: "MuMuConfig"):
        """保存完整配置"""
        try:
            config_file = cls._get_config_file()
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(config), f, indent=2, ensure_ascii=False)
            logger.debug(f"配置已保存")
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)

    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        try:
            config_file = cls._get_config_file()
            if os.path.exists(config_file):
                os.remove(config_file)
                logger.debug(f"缓存已清除")
        except OSError as e:
            logger.error(f"清除缓存失败: {e}", exc_info=True)

    @classmethod
    def save_adb_path(cls, adb_path: str):
        """
        保存 ADB 路径到缓存

        Args:
            adb_path: ADB 可执行文件路径
        """
        try:
            config_file = cls._get_config_file()
            # 读取现有配置
            config = {}
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            # 添加/更新 adb_path 字段
            config["adb_path"] = adb_path
            config["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # 写回文件
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"ADB 路径已缓存: {adb_path}")
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"保存 ADB 路径到缓存失败: {e}", exc_info=True)

    @classmethod
    def load_cached_adb_path(cls) -> Optional[str]:
        """
        读取缓存的 ADB 路径

        Returns:
            缓存的 ADB 路径，如果缓存不存在或无效则返回 None
        """
        try:
            config_file = cls._get_config_file()
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    adb_path = config.get("adb_path")
                    if adb_path:
                        # 验证文件是否存在
                        if os.path.isfile(adb_path):
                            logger.info(f"从缓存读取到 ADB 路径: {adb_path}")
                            return adb_path
                        else:
                            logger.warning(
                                f"缓存的 ADB 路径无效（文件不存在）: {adb_path}"
                            )
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取缓存的 ADB 路径失败: {e}", exc_info=True)
        return None


# 兼容旧代码：立即获取ADB路径（必须在MuMuConfigManager定义之后）
ADB_PATH = get_adb_path()


# 定义模拟器管理器类（主类）
class EmulatorManager:
    """
    模拟器管理器类（主类）- 支持MuMu模拟器

    功能说明：
    - 统一管理MuMu模拟器的窗口查找和端口探测
    - 自动识别模拟器类型
    - 检查窗口分辨率
    - 缓存配置避免重复探测

    使用示例：
        manager = EmulatorManager()
        config = manager.initialize()  # 自动查找窗口和端口
        print(f"端口: {config.port}")
        print(f"窗口: {config.window_title}")
        print(f"类型: {config.emulator_type}")
    """

    def __init__(self, adb_path: Optional[str] = None):
        """
        初始化模拟器管理器

        参数说明：
        - adb_path: ADB可执行文件路径，None表示自动查找
        """
        # 如果没有指定ADB路径，自动查找
        if adb_path is None:
            adb_path = get_adb_path()
        # 保存ADB路径
        self.adb_path = adb_path
        # 创建端口查找器实例
        self.port_finder = EmulatorPortFinder(adb_path)
        # 创建窗口查找器实例（如果win32可用）
        self.window_finder = EmulatorWindowFinder() if HAS_WIN32 else None
        # 初始化配置为None
        self.config: Optional[MuMuConfig] = None
        # 初始化模拟器类型为None
        self.emulator_type: Optional[str] = None

    def initialize(
        self, force_redetect: bool = False, emulator_type: Optional[str] = None
    ) -> "MuMuConfig":
        """
        初始化模拟器（查找窗口和端口）

        Args:
            force_redetect: 强制重新探测（忽略缓存）
            emulator_type: 指定模拟器类型 ('mumu')，None 表示自动检测

        Returns:
            MuMuConfig 配置对象

        Raises:
            RuntimeError: 初始化失败
        """
        logger.info("=" * 50)
        logger.info("初始化模拟器")
        logger.info("=" * 50)

        # 1. 查找窗口
        if self.window_finder is None:
            raise RuntimeError("win32gui 未安装，无法查找窗口")

        hwnd, title, rect, detected_type = self.window_finder.find_window(
            check_resolution=True, emulator_type=emulator_type
        )
        self.emulator_type = detected_type

        # 2. 查找端口
        port, port_type = self.port_finder.find_port(
            prefer_cached=not force_redetect, emulator_type=emulator_type
        )
        if port is None:
            raise RuntimeError("未找到模拟器 ADB 端口")

        # 如果窗口和端口检测的类型不一致，以窗口为准
        if detected_type and port_type and detected_type != port_type:
            logger.warning(
                f"窗口类型 ({detected_type}) 与端口类型 ({port_type}) 不一致"
            )
            logger.warning(f"使用窗口检测的类型: {detected_type}")

        # 3. 计算客户区大小
        client_width = rect[2] - rect[0] - EmulatorWindowFinder.BORDER_WIDTH
        client_height = rect[3] - rect[1] - EmulatorWindowFinder.TITLE_HEIGHT

        # 4. 创建配置
        serial = f"127.0.0.1:{port}"
        self.config = MuMuConfig(
            port=port,
            serial=serial,
            window_title=title,
            window_rect=rect,
            client_size=(client_width, client_height),
            saved_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        # 5. 保存完整配置
        MuMuConfigManager.save_full_config(self.config)

        # 6. 打印信息
        type_name_map = {
            "mumu": "MuMu 模拟器",
        }
        type_display = type_name_map.get(
            self.emulator_type, self.emulator_type or "未知"
        )

        logger.info("=" * 50)
        logger.info("初始化成功")
        logger.info(f"  模拟器类型: {type_display}")
        logger.info(f"  窗口标题: {title}")
        logger.info(f"  窗口句柄: {hwnd}")
        logger.info(f"  窗口位置: ({rect[0]}, {rect[1]})")
        logger.info(f"  窗口大小: {rect[2] - rect[0]}x{rect[3] - rect[1]}")
        logger.info(f"  客户区大小: {client_width}x{client_height}")
        logger.info(f"  ADB 端口: {port}")
        logger.info(f"  ADB Serial: {serial}")
        logger.info("=" * 50)

        return self.config

    def get_config(self) -> Optional["MuMuConfig"]:
        """获取当前配置"""
        return self.config

    def get_emulator_type(self) -> Optional[str]:
        """获取模拟器类型"""
        return self.emulator_type

    def reload(self) -> "MuMuConfig":
        """重新加载（清除缓存重新探测）"""
        MuMuConfigManager.clear_cache()
        return self.initialize(force_redetect=True)


# 保持向后兼容的别名（兼容旧代码）
MuMuManager = EmulatorManager
MuMuPortFinder = EmulatorPortFinder
MuMuWindowFinder = EmulatorWindowFinder


# ========== 便捷函数 ==========
def init_emulator(
    adb_path: Optional[str] = None, emulator_type: Optional[str] = None
) -> "MuMuConfig":
    """
    快速初始化模拟器（便捷函数）

    参数说明：
    - adb_path: ADB可执行文件路径，None表示自动查找
    - emulator_type: 指定模拟器类型（'mumu'），None表示自动检测

    返回值说明：
    - 返回MuMuConfig配置对象

    使用示例：
        # 自动检测模拟器类型
        config = init_emulator()

        # 指定MuMu模拟器
        config = init_emulator(emulator_type='mumu')
    """
    # 如果没有指定ADB路径但指定了模拟器类型，根据类型查找ADB
    if adb_path is None and emulator_type:
        adb_path = get_adb_path(emulator_type)

    # 创建模拟器管理器实例
    manager = EmulatorManager(adb_path)
    # 初始化并返回配置
    return manager.initialize(emulator_type=emulator_type)


# 保持向后兼容的别名
init_mumu = init_emulator


# ========== 测试代码 ==========
if __name__ == "__main__":
    # 配置日志输出到控制台，确保测试时能看到日志
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 测试模拟器自动检测
    try:
        # 打印测试开始信息
        logger.info("测试自动检测模拟器...")
        # 调用初始化函数
        config = init_emulator()
        # 测试通过，打印成功信息
        logger.info("测试通过！")
        # 打印检测到的端口
        logger.info(f"端口: {config.port}")
        # 打印检测到的窗口标题
        logger.info(f"窗口: {config.window_title}")
    except Exception as e:
        # 测试失败，打印错误信息
        logger.error(f"测试失败: {e}", exc_info=True)
