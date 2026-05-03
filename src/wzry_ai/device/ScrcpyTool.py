"""
Scrcpy视频流工具模块

功能说明：
    通过scrcpy协议获取安卓设备实时视频流，用于AI视觉检测

核心特性：
    1. 继承ADB工具 - 复用设备连接管理功能
    2. 高清视频流 - 支持1920x1080原始分辨率
    3. 帧监听回调 - 实时处理每一帧图像
    4. 双窗口调试 - 完整画面+小地图区域预览
"""

# 导入操作系统接口模块
import os

# 导入系统相关模块
import sys
from importlib import import_module
from typing import Any, Optional, cast

# 禁用scrcpy的H.264解码警告输出
# 设置环境变量，禁止libav输出彩色日志
os.environ["AV_LOG_FORCE_NOCOLOR"] = "1"

# 第三方库导入
# OpenCV库，用于图像处理和显示
import cv2

# adbutils库，用于ADB设备管理
from adbutils import AdbDevice

# av库中的CodecContext，用于视频解码
from av.codec import CodecContext

# 导入av库，用于设置libav日志级别
import av

# 本地模块导入
# 导入ADB工具基类
from wzry_ai.device.ADBTool import ADBTool

# 从配置导入scrcpy相关参数
from wzry_ai.config import SCRCPY_BITRATE, SCRCPY_MAX_FPS, SCRCPY_MAX_SIZE

# 导入日志工具
from wzry_ai.utils.logging_utils import get_logger

# 导入scrcpy库，用于视频流连接
import scrcpy

# 【优化1】抑制libav日志级别，仅保留致命错误输出
# 避免scrcpy连接初始化时出现大量libav.h264错误日志噪音
_av_logging = cast(Any, import_module("av.logging"))
_av_logging.set_level(_av_logging.FATAL)

# 获取当前模块的日志记录器
logger = get_logger(__name__)

# ----- scrcpy 多线程解码优化补丁 -----
# 保存原始的stream_loop方法，用于后续替换
_scrcpy_client_class = cast(Any, scrcpy.Client)
_original_stream_loop = getattr(_scrcpy_client_class, "_Client__stream_loop")


def _patched_stream_loop(self) -> None:
    """
    优化后的视频流处理循环（补丁函数）

    功能说明：
        重写scrcpy的视频流处理循环，启用多线程解码提升性能

    优化内容：
        1. 启用多线程解码（最多4线程），提升H.264视频解码性能
    """
    # 创建H.264解码器上下文，"r"表示读取模式（解码）
    codec = CodecContext.create("h264", "r")

    # 性能优化：启用多线程解码
    # 获取CPU核心数，如果获取失败则默认使用4
    cpu_count = os.cpu_count() or 4
    # 设置解码线程数，最多4线程，避免过度开销
    codec.thread_count = min(4, cpu_count)

    # 循环接收和解码视频帧，直到连接断开
    while self.alive:
        try:
            # 从视频socket接收原始H.264数据，0x10000是缓冲区大小（64KB）
            raw_h264 = self._Client__video_socket.recv(0x10000)
            # scrcpy-client 原版会把空包交给解码器解析；部分真机上启动阶段会
            # 短暂返回空包，不能直接把视频线程杀掉。
            if raw_h264 == b"":
                import time

                time.sleep(0.01)
                if not self.block_frame:
                    self._Client__send_to_listeners(scrcpy.EVENT_FRAME, None)
                continue
            # 解析H.264数据包
            packets = codec.parse(raw_h264)
            # 遍历每个数据包进行解码
            for packet in packets:
                # 解码数据包，获取视频帧
                frames = codec.decode(packet)
                # 遍历解码后的每一帧
                for frame in frames:
                    # 将视频帧转换为BGR格式的numpy数组（OpenCV标准格式）
                    frame = frame.to_ndarray(format="bgr24")
                    # 如果需要水平翻转图像
                    if self.flip:
                        frame = frame[:, ::-1, :]
                    # 保存最后一帧
                    self.last_frame = frame
                    # 保存分辨率信息
                    self.resolution = (frame.shape[1], frame.shape[0])
                    # 发送帧事件给所有监听器
                    self._Client__send_to_listeners(scrcpy.EVENT_FRAME, frame)
        except BlockingIOError:
            import time

            time.sleep(0.01)
            if not self.block_frame:
                self._Client__send_to_listeners(scrcpy.EVENT_FRAME, None)
        except (ConnectionError, OSError) as e:
            # 连接错误或系统错误，如果连接仍活跃则处理断开
            if self.alive:
                disconnect_event = getattr(scrcpy, "EVENT_DISCONNECT", None)
                if disconnect_event is not None:
                    self._Client__send_to_listeners(disconnect_event)
                self.stop()
                raise e
        except Exception:
            # 一般异常，短暂休眠后继续
            import time

            time.sleep(0.01)
            # 如果不是阻塞帧模式，发送空帧事件
            if not self.block_frame:
                self._Client__send_to_listeners(scrcpy.EVENT_FRAME, None)


# 应用补丁：用优化后的函数替换原始函数
setattr(_scrcpy_client_class, "_Client__stream_loop", _patched_stream_loop)

# 记录补丁应用成功的日志
logger.info("[scrcpy_patch] ✓ 已应用多线程解码优化补丁 (thread_count=4)")


# 重定向stderr以过滤解码错误
class DummyStderr:
    """
    虚拟标准错误流类

    功能说明：
        用于过滤scrcpy产生的H.264解码错误信息
        这些错误不影响功能，但会污染日志输出
    """

    # 要过滤的H.264解码错误关键词列表
    FILTER_KEYWORDS = [
        "sps_id",
        "out of range",
        "non-existing PPS",
        "no frame",
        "decode_slice_header",
        "referenced",
        "PPS",
        "SPS",
        "NAL",
        "colocated",
        "Frame num change",
    ]

    def write(self, msg: str):
        """
        写入方法

        功能说明：
            重写write方法，过滤包含关键词的错误消息
        """
        # 检查消息是否包含任何过滤关键词
        if not any(kw in msg for kw in self.FILTER_KEYWORDS):
            # 不包含关键词，写入真正的stderr
            stderr = sys.__stderr__
            if stderr is not None:
                stderr.write(msg)

    def flush(self):
        """刷新方法（空实现，满足文件接口要求）"""
        pass


# 仅在非调试模式下启用错误过滤
# 如果设置了DEBUG环境变量，则不过滤错误（便于调试）
if not os.environ.get("DEBUG"):
    # 将stderr替换为自定义的过滤类
    sys.stderr = DummyStderr()

# 导入模拟器管理器（可选依赖）
try:
    from wzry_ai.device.emulator_manager import EmulatorWindowFinder, HAS_WIN32

    # 标记模拟器管理器可用
    HAS_EMULATOR_MANAGER = True
except ImportError:
    # 导入失败，标记不可用
    HAS_EMULATOR_MANAGER = False
    HAS_WIN32 = False
    EmulatorWindowFinder = None


class ScrcpyTool(ADBTool):
    """
    Scrcpy视频流工具类

    功能说明：
        继承自ADBTool，提供视频流获取和帧处理功能
        用于实时获取安卓设备的屏幕画面
    """

    # 【优化2】帧预热配置：连接后丢弃前N帧，确保后续帧稳定
    # 预热帧数，丢弃前5帧以避免初始化阶段的错误帧
    FRAME_WARMUP_COUNT = 5

    def __init__(self, device_serial: Optional[str] = None, auto_detect: bool = True):
        """
        初始化 Scrcpy 工具

        功能说明：
            建立ADB连接并初始化scrcpy客户端

        参数说明：
            device_serial: ADB设备序列号（如"127.0.0.1:7555"），None则自动检测
            auto_detect: 是否自动检测模拟器窗口和端口，默认为True
        """
        # 先调用父类初始化（建立ADB连接）
        super().__init__(device_serial=device_serial, auto_detect=auto_detect)

        # 如果需要且没有指定设备，检测模拟器窗口
        if auto_detect and device_serial is None and HAS_EMULATOR_MANAGER and HAS_WIN32:
            self._check_emulator_window()

        # 创建scrcpy客户端
        self.client = self.Update_Client()
        # 初始化帧预热计数器
        self._frame_warmup_counter = 0
        # 初始化预热完成标志
        self._is_warmed_up = False

    def _check_emulator_window(self):
        """
        检查模拟器窗口（内部方法）

        功能说明：
            验证模拟器窗口的分辨率和可见性
        """
        try:
            # 记录检查开始日志
            logger.info("[ScrcpyTool] 检查模拟器窗口...")
            # 创建窗口查找器
            if EmulatorWindowFinder is None:
                return
            window_finder = EmulatorWindowFinder()
            # 查找窗口并检查分辨率
            hwnd, title, rect, emu_type = window_finder.find_window(
                check_resolution=True
            )
            # 记录检查通过日志
            logger.info(f"[ScrcpyTool] ✓ 窗口检查通过: {title}")
        except Exception as e:  # EmulatorWindowFinder 可能抛出多种异常
            # 检查失败，记录警告日志（不中断程序）
            logger.warning(f"[ScrcpyTool] ⚠️ 窗口检查警告: {e}")

    def Update_Client(self) -> scrcpy.Client:
        """
        创建并配置scrcpy客户端

        功能说明：
            创建scrcpy客户端实例，配置视频流参数

        返回值：
            scrcpy.Client: 配置好的scrcpy客户端
        """
        # 创建scrcpy客户端，配置解码参数
        # 注意：max_width必须在__init__时传入，创建后修改无效
        client = scrcpy.Client(
            device=self.device_serial,  # ADB设备
            max_width=0,  # 使用设备原始分辨率
            max_fps=SCRCPY_MAX_FPS,  # 最大帧率
            bitrate=SCRCPY_BITRATE,  # 视频比特率
            flip=False,  # 不水平翻转
        )
        return client

    def Set_Client(self, device: AdbDevice):
        """
        设置scrcpy客户端

        参数说明：
            device: ADB设备对象
        """
        # 使用指定设备创建新的scrcpy客户端
        self.client = scrcpy.Client(device)

    def get_Client(self) -> scrcpy.Client:
        """
        获取当前scrcpy客户端

        返回值：
            scrcpy.Client: 当前的scrcpy客户端实例
        """
        return self.client

    def preview(self, fps: Optional[int] = None):
        """
        启动视频流预览

        功能说明：
            启动视频流并添加帧监听器，开始接收视频帧

        参数说明：
            fps: 目标帧率，None则使用配置中的默认值
        """
        # 重置帧预热状态
        self._frame_warmup_counter = 0
        self._is_warmed_up = False
        # 记录启动日志
        logger.info(f"[ScrcpyTool] 启动视频流，帧预热设置: {self.FRAME_WARMUP_COUNT}帧")

        # 添加帧监听器，使用带预热处理的回调函数
        self.client.add_listener(scrcpy.EVENT_FRAME, self._on_frame_with_warmup)
        # 设置帧率
        target_fps = fps if fps is not None else SCRCPY_MAX_FPS
        self.client.max_fps = target_fps
        # 启动客户端，使用独立线程
        self.client.start(threaded=True)

    def _on_frame_with_warmup(self, frame):
        """
        带帧预热的帧回调处理（内部方法）

        功能说明：
            处理接收到的视频帧，丢弃前几帧以确保后续帧稳定

        参数说明：
            frame: 视频帧数据（numpy数组）
        """
        # 帧预热阶段：丢弃前N帧
        if not self._is_warmed_up:
            # 如果帧为None，静默跳过
            if frame is None:
                return

            # 增加预热计数器
            self._frame_warmup_counter += 1
            # 检查是否仍在预热阶段
            if self._frame_warmup_counter < self.FRAME_WARMUP_COUNT:
                # 仍在预热阶段，丢弃该帧
                return
            else:
                # 预热完成，设置标志
                self._is_warmed_up = True
                # 记录预热完成日志
                logger.info(
                    f"[ScrcpyTool] ✓ 帧预热完成，已丢弃{self.FRAME_WARMUP_COUNT}帧，开始正常处理"
                )

        # 正常处理帧
        self.on_frame(frame)

    @staticmethod
    def on_frame(frame):
        """
        处理视频帧（静态方法）

        功能说明：
            显示视频帧，创建两个窗口：完整画面和小地图区域

        参数说明：
            frame: 视频帧数据（numpy数组）
        """
        # 检查帧是否有效
        if frame is not None:
            # 显示完整画面
            cv2.imshow("EVE", frame)
            # 裁剪小地图区域（左上角400x400像素）
            img = frame[0:400, 0:400]
            # 显示小地图窗口
            cv2.imshow("EVE Check", img)

        # 等待5毫秒，允许OpenCV处理窗口事件
        cv2.waitKey(5)


# 测试代码块
if __name__ == "__main__":
    # 导入time模块
    import time

    # 创建ScrcpyTool实例
    tool = ScrcpyTool()
    # 启动预览，设置帧率为30fps
    tool.preview(fps=30)
    # 记录设备列表
    logger.info(f"设备列表: {tool.get_devices()}")

    # 保持程序运行，直到用户按Ctrl+C
    logger.info("按 Ctrl+C 停止...")
    try:
        # 无限循环，保持程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 捕获Ctrl+C中断信号
        logger.info("停止中...")
