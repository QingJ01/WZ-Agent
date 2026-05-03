"""
帧管理器模块 - 优化scrcpy截图性能，支持单一长连接和帧缓存

功能说明：
- 管理scrcpy与安卓设备的连接
- 提供帧缓存机制，支持获取最新帧
- 支持共享帧管理，供多个检测器使用
- 提供性能统计功能
"""

# 导入日志模块，用于记录程序运行信息
import logging

# 导入操作系统模块，用于环境变量设置
import os

# 导入系统模块，用于标准错误流控制
import sys

# 导入线程模块，用于多线程处理
import threading

# 导入时间模块，用于延时和计时
import time

# 从数据类模块导入装饰器，用于创建简单的数据类
from dataclasses import dataclass

# 从类型提示模块导入类型定义
from typing import Callable, Dict, Optional

# 设置环境变量禁用scrcpy的H.264解码警告
# 设置AV_LOG_FORCE_NOCOLOR为1，禁用日志颜色输出
os.environ["AV_LOG_FORCE_NOCOLOR"] = "1"
# 设置LIBAV_LOG_LEVEL为error，只显示错误级别日志
os.environ["LIBAV_LOG_LEVEL"] = "error"

# 设置scrcpy库的日志级别为CRITICAL（最高级别），屏蔽其冗余日志输出
logging.getLogger("scrcpy").setLevel(logging.CRITICAL)


# 定义虚拟标准错误流类，用于过滤解码错误输出
class DummyStderr:
    """
    虚拟标准错误流类 - 过滤H.264解码错误输出

    功能说明：
    - 拦截并过滤scrcpy传输过程中产生的H.264解码错误信息
    - 只输出不包含过滤关键词的消息
    """

    # 定义需要过滤的关键词列表
    FILTER_KEYWORDS = [
        "sps_id",
        "out of range",
        "non-existing PPS",  # 参数集相关错误
        "no frame",
        "decode_slice_header",
        "referenced",  # 帧解码相关错误
        "PPS",
        "SPS",
        "NAL",
        "colocated",  # 其他技术关键词
    ]

    def write(self, msg: str) -> None:
        # 检查消息是否不包含任何过滤关键词
        if not any(kw in msg for kw in self.FILTER_KEYWORDS):
            # 如果不包含，写入原始标准错误流
            if sys.__stderr__ is not None:
                sys.__stderr__.write(msg)

    def flush(self) -> None:
        # 空实现，不需要实际刷新
        pass


# 检查环境变量中是否未设置DEBUG模式
if not os.environ.get("DEBUG"):
    # 将标准错误流替换为虚拟错误流，过滤解码错误
    sys.stderr = DummyStderr()

# 导入NumPy库，用于数组和矩阵运算
import numpy as np

# 从adbutils库导入adb对象，用于ADB设备操作
from adbutils import adb

# 从本地日志工具模块导入获取日志记录器函数
from wzry_ai.utils.logging_utils import get_logger

# 从ScrcpyTool模块导入ScrcpyTool类
# ScrcpyTool中已集成scrcpy补丁，导入时会自动应用多线程解码优化
from wzry_ai.device.ScrcpyTool import ScrcpyTool

# 导入OpenCV库，用于图像处理
import cv2

# 导入scrcpy库，用于安卓屏幕镜像
import scrcpy

# 获取当前模块的日志记录器对象
logger = get_logger(__name__)


# 使用dataclass装饰器定义帧信息数据类
@dataclass
class FrameInfo:
    """
    帧信息数据类 - 存储单帧图像的完整信息

    属性说明：
    - frame: 图像数据（NumPy数组）
    - timestamp: 接收时间戳（浮点数，单位秒）
    - frame_number: 帧序号（整数，用于追踪）
    """

    frame: np.ndarray  # 图像数据（NumPy数组格式）
    timestamp: float  # 接收时间戳（单位：秒）
    frame_number: int  # 帧序号（递增计数）


# 定义共享帧管理器类（单例模式）
class SharedFrameManager:
    """
    共享帧管理器类 - 管理裁剪后的帧数据（小地图、全屏等）

    功能说明：
    - 用于Master_Auto.py裁剪后的帧共享给model1/model2检测器
    - 采用单例模式，全局统一访问
    - 提供线程安全的帧存储和获取

    使用方式：
    - 通过get_instance()获取唯一实例
    - 使用set_minimap_frame/set_full_frame设置帧
    - 使用get_minimap_frame/get_full_frame获取帧
    """

    # 类变量：存储单例实例
    _instance: Optional["SharedFrameManager"] = None
    # 类变量：线程锁，用于保证单例创建的线程安全
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SharedFrameManager":
        """
        获取共享帧管理器实例（单例模式）

        返回值说明：
        - 返回SharedFrameManager的唯一实例
        - 如果实例不存在，会创建新实例
        - 线程安全，可多线程调用
        """
        # 检查实例是否已创建
        if cls._instance is None:
            # 获取线程锁，保证线程安全
            with cls._lock:
                # 双重检查，防止多个线程同时创建实例
                if cls._instance is None:
                    # 创建新实例
                    cls._instance = cls()
        # 返回实例
        return cls._instance

    def __init__(self):
        """
        初始化共享帧管理器

        注意：
        - 请使用get_instance()获取实例，不要直接实例化
        - 直接实例化会抛出RuntimeError异常
        """
        # 检查是否已通过get_instance()创建
        if SharedFrameManager._instance is not None:
            # 如果不是通过get_instance()创建，抛出异常
            raise RuntimeError("请使用 get_instance() 获取实例")

        # 初始化帧数据存储变量
        # 小地图帧（供Model1使用）
        self._minimap_frame: Optional[np.ndarray] = None
        # 全屏帧（供Model2使用）
        self._full_frame: Optional[np.ndarray] = None

        # 创建线程锁（保证线程安全）
        # 小地图帧的访问锁
        self._minimap_lock = threading.Lock()
        # 全屏帧的访问锁
        self._full_lock = threading.Lock()

        # 初始化统计信息字典
        self._stats = {
            "minimap_set_count": 0,  # 小地图帧设置次数
            "minimap_get_count": 0,  # 小地图帧获取次数
            "full_set_count": 0,  # 全屏帧设置次数
            "full_get_count": 0,  # 全屏帧获取次数
        }

    # ========== 小地图帧管理 ==========
    def set_minimap_frame(self, frame: Optional[np.ndarray]):
        """
        设置小地图帧

        参数说明：
        - frame: 小地图帧图像（NumPy数组），直接引用不拷贝

        注意：
        - 使用线程锁保证线程安全
        - 会更新统计信息中的设置次数
        """
        # 获取小地图帧锁，保证线程安全
        with self._minimap_lock:
            # 保存帧引用
            self._minimap_frame = frame
            # 增加设置次数统计
            self._stats["minimap_set_count"] += 1

    def get_minimap_frame(self, copy: bool = False) -> Optional[np.ndarray]:
        """
        获取小地图帧

        参数说明：
        - copy: 是否返回拷贝（True=安全但慢，False=快速但只读）

        返回值说明：
        - 返回小地图帧（NumPy数组）或None（如果未设置）
        - 如果copy=True，返回拷贝；如果copy=False，返回原始引用

        注意：
        - 使用线程锁保证线程安全
        - 会更新统计信息中的获取次数
        """
        # 获取小地图帧锁，保证线程安全
        with self._minimap_lock:
            # 增加获取次数统计
            self._stats["minimap_get_count"] += 1
            # 检查帧是否存在
            if self._minimap_frame is None:
                return None
            # 根据copy参数决定是否返回拷贝
            return self._minimap_frame.copy() if copy else self._minimap_frame

    def clear_minimap_frame(self):
        """
        清除小地图帧

        功能说明：
        - 将小地图帧设置为None
        - 使用线程锁保证线程安全
        """
        # 获取小地图帧锁，保证线程安全
        with self._minimap_lock:
            # 清除帧引用
            self._minimap_frame = None

    # ========== 全屏帧管理 ==========
    def set_full_frame(self, frame: Optional[np.ndarray]):
        """
        设置全屏帧

        参数说明：
        - frame: 全屏帧图像（NumPy数组），直接引用不拷贝

        注意：
        - 使用线程锁保证线程安全
        - 会更新统计信息中的设置次数
        """
        # 获取全屏帧锁，保证线程安全
        with self._full_lock:
            # 保存帧引用
            self._full_frame = frame
            # 增加设置次数统计
            self._stats["full_set_count"] += 1

    def get_full_frame(self, copy: bool = False) -> Optional[np.ndarray]:
        """
        获取全屏帧

        参数说明：
        - copy: 是否返回拷贝（True=安全但慢，False=快速但只读）

        返回值说明：
        - 返回全屏帧（NumPy数组）或None（如果未设置）
        - 如果copy=True，返回拷贝；如果copy=False，返回原始引用

        注意：
        - 使用线程锁保证线程安全
        - 会更新统计信息中的获取次数
        """
        # 获取全屏帧锁，保证线程安全
        with self._full_lock:
            # 增加获取次数统计
            self._stats["full_get_count"] += 1
            # 检查帧是否存在
            if self._full_frame is None:
                return None
            # 根据copy参数决定是否返回拷贝
            return self._full_frame.copy() if copy else self._full_frame

    def clear_full_frame(self):
        """
        清除全屏帧

        功能说明：
        - 将全屏帧设置为None
        - 使用线程锁保证线程安全
        """
        # 获取全屏帧锁，保证线程安全
        with self._full_lock:
            # 清除帧引用
            self._full_frame = None

    # ========== 批量操作 ==========
    def clear_all(self):
        """
        清除所有帧

        功能说明：
        - 同时清除小地图帧和全屏帧
        - 调用clear_minimap_frame和clear_full_frame方法
        """
        # 清除小地图帧
        self.clear_minimap_frame()
        # 清除全屏帧
        self.clear_full_frame()

    def get_stats(self) -> dict:
        """
        获取统计信息

        返回值说明：
        - 返回包含统计信息的字典
        - 包括小地图帧和全屏帧的设置/获取次数
        - 返回的是拷贝，修改不影响内部数据
        """
        # 返回统计信息的拷贝
        return self._stats.copy()


# ========== 便捷函数 - 小地图帧 ==========
def set_minimap_frame(frame: Optional[np.ndarray]):
    """
    设置小地图帧（便捷函数，兼容旧接口）

    参数说明：
    - frame: 小地图帧图像（NumPy数组）

    功能说明：
    - 自动获取SharedFrameManager单例实例
    - 调用实例的set_minimap_frame方法
    """
    # 获取单例实例并设置小地图帧
    SharedFrameManager.get_instance().set_minimap_frame(frame)


def get_minimap_frame(copy: bool = False) -> Optional[np.ndarray]:
    """
    获取小地图帧（便捷函数，兼容旧接口）

    参数说明：
    - copy: 是否返回拷贝（True=安全但慢，False=快速但只读）

    返回值说明：
    - 返回小地图帧或None

    功能说明：
    - 自动获取SharedFrameManager单例实例
    - 调用实例的get_minimap_frame方法
    """
    # 获取单例实例并获取小地图帧
    return SharedFrameManager.get_instance().get_minimap_frame(copy)


# ========== 便捷函数 - 全屏帧 ==========
def set_full_frame(frame: Optional[np.ndarray]):
    """
    设置全屏帧（便捷函数，兼容旧接口）

    参数说明：
    - frame: 全屏帧图像（NumPy数组）

    功能说明：
    - 自动获取SharedFrameManager单例实例
    - 调用实例的set_full_frame方法
    """
    # 获取单例实例并设置全屏帧
    SharedFrameManager.get_instance().set_full_frame(frame)


def get_full_frame(copy: bool = False) -> Optional[np.ndarray]:
    """
    获取全屏帧（便捷函数，兼容旧接口）

    参数说明：
    - copy: 是否返回拷贝（True=安全但慢，False=快速但只读）

    返回值说明：
    - 返回全屏帧或None

    功能说明：
    - 自动获取SharedFrameManager单例实例
    - 调用实例的get_full_frame方法
    """
    # 获取单例实例并获取全屏帧
    return SharedFrameManager.get_instance().get_full_frame(copy)


# 定义帧管理器类（单例模式，每个设备一个实例）
class FrameManager:
    """
    帧管理器类 - 管理scrcpy连接和帧接收（单例模式）

    功能说明：
    - 每个设备对应一个实例，保持单一scrcpy连接
    - 提供帧缓存机制，支持获取最新帧
    - 自动管理连接生命周期
    - 提供性能统计功能

    使用方式：
    - 通过get_instance()获取指定设备的实例
    - 使用start()启动帧接收
    - 使用get_latest_frame()获取最新帧
    - 使用stop()停止帧接收
    """

    # 类变量：存储各设备的实例字典
    _instances: Dict[str, "FrameManager"] = {}
    # 类变量：线程锁，用于保证实例创建的线程安全
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, device_serial: Optional[str] = None) -> "FrameManager":
        """
        获取指定设备的帧管理器实例（单例模式）

        参数说明：
        - device_serial: ADB设备序列号，None表示使用默认设备

        返回值说明：
        - 返回指定设备的FrameManager实例
        - 如果实例不存在，会创建新实例
        - 线程安全，可多线程调用
        """
        # 如果未指定设备序列号，获取默认设备
        serial = device_serial or cls._get_default_device()

        # 获取线程锁，保证线程安全
        with cls._lock:
            # 检查该设备的实例是否已创建
            if serial not in cls._instances:
                # 创建新实例并保存到字典
                cls._instances[serial] = cls(serial)
            # 返回实例
            return cls._instances[serial]

    @classmethod
    def _get_default_device(cls) -> str:
        """
        获取默认ADB设备

        返回值说明：
        - 返回第一个可用ADB设备的序列号

        异常说明：
        - 如果没有可用设备，抛出RuntimeError异常
        """
        # 获取ADB设备列表
        devices = adb.device_list()
        # 检查是否有可用设备
        if not devices:
            # 没有可用设备，抛出异常
            raise RuntimeError("没有可用的ADB设备")
        # 返回第一个设备的序列号
        serial = devices[0].serial
        if serial is None:
            raise RuntimeError("默认ADB设备缺少序列号")
        return serial

    def __init__(self, device_serial: str):
        """
        初始化帧管理器

        参数说明：
        - device_serial: ADB设备序列号（字符串）

        注意：
        - 请使用get_instance()获取实例，不要直接实例化
        """
        # 保存设备序列号
        self.device_serial = device_serial

        # 初始化帧缓存相关变量
        # 最新帧信息（FrameInfo对象或None）
        self._latest_frame: Optional[FrameInfo] = None
        # 帧访问锁（使用RLock支持重入）
        self._frame_lock = threading.RLock()
        # 帧更新事件（用于通知等待者）
        self._frame_event = threading.Event()

        # 初始化scrcpy客户端相关变量
        # scrcpy客户端对象
        self._client: Optional[scrcpy.Client] = None
        # ADB设备对象
        self._device = None

        # 初始化运行状态相关变量
        # 是否正在运行标志
        self._running = False
        # 接收线程对象
        self._thread: Optional[threading.Thread] = None
        # 帧计数器
        self._frame_count = 0
        # 启动时间戳
        self._start_time = 0.0

        # 初始化性能统计字典
        self._stats = {
            "total_frames": 0,  # 总帧数
            "dropped_frames": 0,  # 丢弃帧数
            "avg_fps": 0.0,  # 平均帧率
        }

    def start(self, max_fps: int = 60, bitrate: int = 8000000) -> bool:
        """
        启动帧接收

        参数说明：
        - max_fps: 最大帧率（默认60fps）
        - bitrate: 码率（默认8000000bps）

        返回值说明：
        - 返回True表示启动成功，False表示启动失败

        功能说明：
        - 连接ADB设备
        - 创建并配置scrcpy客户端
        - 启动后台接收线程
        """
        # 检查是否已在运行
        if self._running:
            # 已在运行，记录日志并返回成功
            logger.info(f"[FrameManager] {self.device_serial} 已在运行")
            return True

        try:
            # 连接ADB设备
            self._device = adb.device(self.device_serial)

            # 创建scrcpy客户端
            # max_width=0表示让设备自动协商分辨率
            self._client = scrcpy.Client(
                device=self._device,  # ADB设备对象
                max_width=0,  # 自动协商分辨率
                max_fps=max_fps,  # 最大帧率
                bitrate=bitrate,  # 码率
            )

            # 添加帧监听器，监听scrcpy的帧事件
            self._client.add_listener(scrcpy.EVENT_FRAME, self._on_frame)

            # 启动接收线程
            self._running = True  # 设置运行标志
            self._start_time = time.time()  # 记录启动时间
            # 创建后台接收线程（守护线程）
            thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread = thread
            # 启动线程
            thread.start()

            # 记录启动成功日志
            logger.info(f"[FrameManager] ✓ 已启动: {self.device_serial}")
            return True

        except (OSError, RuntimeError, ConnectionError) as e:
            # 启动失败，记录错误日志
            logger.error(f"[FrameManager] ✗ 启动失败: {e}")
            # 重置运行标志
            self._running = False
            return False

    def stop(self):
        """
        停止帧接收

        功能说明：
        - 停止scrcpy客户端
        - 停止接收线程
        - 清除帧缓存
        """
        # 检查是否正在运行
        if not self._running:
            return

        # 设置运行标志为False，通知线程停止
        self._running = False

        # 停止scrcpy客户端
        if self._client:
            try:
                self._client.stop()
            except (AttributeError, RuntimeError, OSError):
                # 忽略停止过程中的错误
                pass

        # 等待接收线程结束（最多等待2秒）
        if self._thread:
            self._thread.join(timeout=2.0)

        # 清除帧缓存
        with self._frame_lock:
            self._latest_frame = None

        # 记录停止成功日志
        logger.info(f"[FrameManager] ✓ 已停止: {self.device_serial}")

    def _receive_loop(self):
        """
        后台接收循环

        功能说明：
        - 在独立线程中运行
        - 启动scrcpy客户端的帧接收
        - 处理接收过程中的异常
        """
        try:
            # 启动scrcpy客户端（非线程模式，在当前线程运行）
            client = self._client
            if client is None:
                logger.error("[FrameManager] 接收循环启动时 scrcpy 客户端为空")
                self._running = False
                return
            client.start(threaded=False)
        except (OSError, RuntimeError, ConnectionError) as e:
            # 接收循环出错，记录错误日志
            logger.error(f"[FrameManager] 接收循环错误: {e}")
            # 设置运行标志为False，停止接收
            self._running = False

    def _on_frame(self, frame: Optional[np.ndarray]):
        """
        帧回调函数 - 由scrcpy调用当收到新帧时

        参数说明：
        - frame: 帧图像数据（NumPy数组）

        功能说明：
        - 永远只保存最新帧，丢弃旧帧
        - 使用"永远最新"策略，确保获取的帧是最新的
        - 复制帧数据避免被修改
        """
        # 检查帧是否为空
        if frame is None:
            return

        # 增加帧计数
        self._frame_count += 1

        # 创建帧信息对象（复制数据避免被修改）
        frame_info = FrameInfo(
            frame=frame.copy(),  # 复制帧数据
            timestamp=time.time(),  # 记录当前时间戳
            frame_number=self._frame_count,  # 记录帧序号
        )

        # 获取帧锁，更新最新帧
        with self._frame_lock:
            # 直接覆盖旧帧，实现"永远最新"策略
            self._latest_frame = frame_info
            # 设置事件标志，通知等待有新帧的线程
            self._frame_event.set()

        # 更新性能统计
        self._update_stats()

    def _update_stats(self):
        """
        更新性能统计

        功能说明：
        - 计算平均帧率（FPS）
        - 基于启动时间和帧计数计算
        """
        # 计算已运行时间
        elapsed = time.time() - self._start_time
        # 检查已运行时间是否大于0（避免除零错误）
        if elapsed > 0:
            # 计算平均帧率：总帧数 / 运行时间
            self._stats["avg_fps"] = self._frame_count / elapsed

    def get_latest_frame(
        self, timeout: float = 0.0, wait_new: bool = False
    ) -> Optional[np.ndarray]:
        """
        获取最新帧图像

        参数说明：
        - timeout: 等待超时时间（秒），0表示不等待
        - wait_new: 是否等待新帧（True=等待新帧，False=立即返回缓存）

        返回值说明：
        - 返回最新帧图像（NumPy数组）
        - 如果失败或未启动，返回None

        功能说明：
        - 如果未启动，会尝试自动启动
        - 支持等待新帧功能
        - 返回的是帧数据的拷贝
        """
        # 检查是否正在运行
        if not self._running:
            # 未运行，记录警告并尝试自动启动
            logger.warning("[FrameManager] 警告: 未启动，尝试自动启动")
            # 尝试启动，如果失败返回None
            if not self.start():
                return None

        # 如果需要等待新帧
        if wait_new and timeout > 0:
            # 清除事件标志
            self._frame_event.clear()
            # 等待新帧到达或超时
            if self._frame_event.wait(timeout):
                # 新帧到达，清除事件标志
                self._frame_event.clear()

        # 获取缓存帧
        with self._frame_lock:
            # 检查是否有最新帧
            if self._latest_frame is not None:
                # 返回帧数据的拷贝
                return self._latest_frame.frame.copy()
            # 没有帧数据，返回None
            return None

    def get_frame_info(self) -> Optional[FrameInfo]:
        """
        获取完整帧信息（包含时间戳和帧序号）

        返回值说明：
        - 返回FrameInfo对象（包含帧数据、时间戳、帧序号）
        - 如果没有帧数据，返回None
        - 返回的是数据的拷贝，修改不影响内部数据
        """
        # 获取帧锁
        with self._frame_lock:
            # 检查是否有最新帧
            if self._latest_frame is not None:
                # 返回FrameInfo对象的拷贝
                return FrameInfo(
                    frame=self._latest_frame.frame.copy(),  # 复制帧数据
                    timestamp=self._latest_frame.timestamp,  # 时间戳
                    frame_number=self._latest_frame.frame_number,  # 帧序号
                )
            # 没有帧数据，返回None
            return None

    def get_stats(self) -> dict:
        """
        获取性能统计信息

        返回值说明：
        - 返回包含性能统计的字典
        - 包括总帧数、丢弃帧数、平均帧率等
        - 返回的是拷贝，修改不影响内部数据
        """
        # 返回统计信息的拷贝
        return self._stats.copy()

    def is_running(self) -> bool:
        """
        检查是否正在运行

        返回值说明：
        - 返回True表示正在运行
        - 返回False表示未运行
        """
        # 返回运行状态标志
        return self._running

    @classmethod
    def stop_all(cls):
        """
        停止所有实例

        功能说明：
        - 停止所有设备的FrameManager实例
        - 清空实例字典
        - 用于程序退出时清理资源
        """
        # 获取类锁，保证线程安全
        with cls._lock:
            # 遍历所有实例并停止
            for instance in cls._instances.values():
                instance.stop()
            # 清空实例字典
            cls._instances.clear()


# ========== 便捷函数 ==========
def get_frame(
    device_serial: Optional[str] = None, timeout: float = 0.1
) -> Optional[np.ndarray]:
    """
    快速获取一帧图像（便捷函数）

    参数说明：
    - device_serial: 设备序列号，None表示使用默认设备
    - timeout: 等待超时时间（秒）

    返回值说明：
    - 返回图像帧（NumPy数组）或None

    功能说明：
    - 自动获取FrameManager实例
    - 自动启动FrameManager（如果未启动）
    - 简化获取单帧的操作
    """
    # 获取FrameManager实例
    manager = FrameManager.get_instance(device_serial)

    # 检查是否正在运行
    if not manager.is_running():
        # 未运行，尝试启动
        if not manager.start():
            # 启动失败，返回None
            return None

    # 获取最新帧并返回
    return manager.get_latest_frame(timeout=timeout)


# ========== 测试代码 ==========
if __name__ == "__main__":
    # 打印测试开始信息
    logger.info("FrameManager 测试")
    logger.info("=" * 60)

    # 获取帧管理器实例
    manager = FrameManager.get_instance()

    # 启动帧管理器
    if manager.start(max_fps=60):
        # 启动成功，打印提示信息
        logger.info("测试获取帧（按Ctrl+C停止）：")
        try:
            # 循环获取100帧
            for i in range(100):
                # 获取最新帧
                frame = manager.get_latest_frame()
                # 检查是否获取到帧
                if frame is not None:
                    # 获取到帧，打印帧信息和FPS
                    logger.debug(
                        f"帧 #{i}: {frame.shape}, FPS: {manager.get_stats()['avg_fps']:.1f}"
                    )
                else:
                    # 未获取到帧，打印无数据
                    logger.debug(f"帧 #{i}: 无数据")
                # 等待100毫秒
                time.sleep(0.1)
        except KeyboardInterrupt:
            # 捕获键盘中断（用户按Ctrl+C）
            logger.info("停止测试")

    # 停止帧管理器
    manager.stop()
    # 打印测试完成信息
    logger.info("测试完成")
