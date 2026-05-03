"""
ADB工具模块

功能说明：
    提供ADB（Android Debug Bridge）操作封装
    用于连接安卓设备、执行命令、模拟点击滑动、截图等操作
"""

# 导入子进程模块，用于执行ADB命令
import subprocess

# 导入os模块，用于读取环境变量
import os

# 导入时间模块，用于添加延迟
import time

# 从typing导入类型提示
from typing import IO, List, Optional, Tuple

# 第三方库导入
# adbutils库，用于Pythonic的ADB操作
import adbutils

# 导入AdbDevice类型
from adbutils import AdbDevice

# 本地模块导入
from wzry_ai.utils.logging_utils import get_logger

# 导入 emulator_manager 的 get_adb_path 函数（延迟导入避免循环依赖）
_ADB_PATH: Optional[str] = None


def _get_adb_path() -> str:
    """获取 ADB 路径（带缓存）"""
    global _ADB_PATH
    env_adb_path = os.environ.get("WZRY_ADB_PATH")
    if env_adb_path:
        _ADB_PATH = os.path.expanduser(os.path.expandvars(env_adb_path))
        return _ADB_PATH

    if _ADB_PATH is None:
        try:
            from wzry_ai.device.emulator_manager import get_adb_path

            _ADB_PATH = get_adb_path()
        except ImportError:
            # 如果导入失败，尝试从 config 导入
            try:
                from wzry_ai.config import ADB_PATH

                _ADB_PATH = ADB_PATH
            except ImportError:
                _ADB_PATH = "adb"
    return _ADB_PATH or "adb"


# 获取当前模块的日志记录器
logger = get_logger(__name__)

try:
    # 尝试导入模拟器管理器
    from wzry_ai.device.emulator_manager import EmulatorPortFinder, MuMuConfigManager

    # 标记模拟器管理器可用
    HAS_EMULATOR_MANAGER = True
except ImportError:
    # 导入失败，标记不可用
    HAS_EMULATOR_MANAGER = False
    EmulatorPortFinder = None
    MuMuConfigManager = None
    # 记录警告日志
    logger.warning("emulator_manager 未找到，将使用传统端口扫描")


class ADBTool:
    """
    ADB工具类

    功能说明：
        封装ADB操作，提供设备连接、命令执行、点击滑动、截图等功能
        支持自动检测模拟器端口和设备连接
    """

    # 默认ADB服务器地址
    DEFAULT_ADB_HOST = "127.0.0.1"

    def __init__(
        self,
        device_serial=None,
        auto_detect: bool = True,
        adb_path: Optional[str] = None,
    ):
        """
        初始化ADB工具

        功能说明：
            建立ADB连接，自动检测模拟器或连接指定设备

        参数说明：
            device_serial: 指定设备序列号，如果为None则自动检测
            auto_detect: 是否自动检测模拟器，默认为True
            adb_path: ADB可执行文件路径，None则使用配置中的路径
        """
        # 初始化adbutils的adb对象
        self.adb = adbutils.adb
        # 初始化模拟器类型为None
        self.emulator_type: Optional[str] = None
        # 设置ADB路径，优先使用传入的参数，其次使用缓存的 ADB 路径
        self.adb_path = adb_path or _get_adb_path()
        # 初始化点击计数器
        self.click_count = 0
        # 初始化上次点击时间
        self.last_click_time = 0
        # 设置点击冷却时间（秒），防止点击过快
        self.click_cooldown = 0.1
        # 连接状态标记，避免每次操作都重新连接
        self._connected = False
        # 持久 shell 子进程
        self._persistent_shell: Optional[subprocess.Popen[bytes]] = None

        # 如果指定了设备序列号，先连接再使用
        if device_serial:
            try:
                # 尝试连接设备
                logger.info(f"连接到设备: {device_serial}")
                self.adb.connect(device_serial)
            except (OSError, RuntimeError) as e:
                # 连接失败，记录警告但不中断
                logger.warning(f"连接警告: {e}")
            # 获取设备对象
            self.device_serial = self.adb.device(device_serial)
            self._connected = True
            return

        # 获取当前已连接的设备列表
        devices = self.get_devices()

        # 如果没有设备且允许自动检测，尝试自动检测模拟器
        if not devices and auto_detect:
            # 调用自动检测方法
            port = self._auto_detect_emulator()
            if port:
                try:
                    # 记录连接日志
                    logger.info(f"连接到模拟器端口: {port}")
                    # 连接到检测到的端口
                    self.adb.connect(f"{self.DEFAULT_ADB_HOST}:{port}")
                    # 重新获取设备列表
                    devices = self.get_devices()
                except (OSError, RuntimeError) as e:
                    # 连接失败，记录错误
                    logger.error(f"连接失败: {e}", exc_info=True)

        # 如果还是没有设备，尝试传统端口扫描方式
        if not devices:
            devices = self._legacy_connect()

        # 如果仍然没有设备，抛出运行时错误
        if not devices:
            raise RuntimeError(
                "没有检测到ADB设备，请确保：\n"
                "1. 手机/模拟器已连接\n"
                "2. USB调试已开启\n"
                "3. 模拟器已启动并分辨率为 1920x1080"
            )

        # 使用第一个可用设备
        self.device_serial = devices[0]
        self._connected = True

        # 初始化持久 shell 连接
        self._init_persistent_shell()

    def _init_persistent_shell(self):
        """初始化持久 ADB shell 连接"""
        if self._persistent_shell and self._persistent_shell.poll() is None:
            return  # 已经存在且活着
        serial = self.get_device_name(self.device_serial)
        self._persistent_shell = subprocess.Popen(
            [self.adb_path, "-s", serial, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _get_shell_stdin(self) -> IO[bytes]:
        """获取持久 shell 的标准输入流。"""
        shell = self._persistent_shell
        if shell is None or shell.stdin is None:
            raise RuntimeError("持久 Shell 未初始化")
        return shell.stdin

    def _ensure_shell_alive(self):
        """确保持久 shell 存活，断开时自动重连"""
        if self._persistent_shell is None or self._persistent_shell.poll() is not None:
            logger.warning("持久 Shell 已断开，正在重连...")
            self._init_persistent_shell()

    def _shell_cmd(self, cmd: str):
        """通过持久 shell 发送命令"""
        self._ensure_shell_alive()
        try:
            shell_stdin = self._get_shell_stdin()
            shell_stdin.write(f"{cmd}\n".encode())
            shell_stdin.flush()
        except (BrokenPipeError, OSError) as e:
            logger.error(f"持久 Shell 写入失败: {e}，尝试重连")
            self._init_persistent_shell()
            shell_stdin = self._get_shell_stdin()
            shell_stdin.write(f"{cmd}\n".encode())
            shell_stdin.flush()

    def __del__(self):
        """清理持久 shell 进程"""
        if self._persistent_shell and self._persistent_shell.poll() is None:
            try:
                shell_stdin = self._persistent_shell.stdin
                if shell_stdin is not None:
                    shell_stdin.close()
                self._persistent_shell.terminate()
                self._persistent_shell.wait(timeout=1)
            except Exception:
                pass

    def _auto_detect_emulator(self) -> Optional[int]:
        """
        自动检测模拟器端口（内部方法）

        功能说明：
            使用emulator_manager自动检测模拟器端口

        返回值：
            int: 检测到的端口号，如果检测失败则返回None
        """
        # 检查模拟器管理器是否可用
        if not HAS_EMULATOR_MANAGER or EmulatorPortFinder is None:
            return None

        try:
            # 记录检测开始日志
            logger.info("正在自动检测模拟器...")
            # 创建端口查找器
            port_finder = EmulatorPortFinder()
            # 查找端口，优先使用缓存
            port, emu_type = port_finder.find_port(prefer_cached=True)
            if port:
                # 保存模拟器类型
                self.emulator_type = emu_type
                # 获取类型名称
                type_name = emu_type or "未知"
                # 记录检测结果
                logger.info(f"✓ 检测到 {type_name} 模拟器，端口: {port}")
                return port
        except (OSError, RuntimeError) as e:
            # 检测失败，记录错误
            logger.error(f"自动检测失败: {e}", exc_info=True)

        return None

    def _legacy_connect(self) -> List[AdbDevice]:
        """
        传统连接方式（内部方法）

        功能说明：
            通过扫描常见端口来连接模拟器（兼容旧代码）

        返回值：
            List[AdbDevice]: 连接成功的设备列表
        """
        # MuMu模拟器端口列表
        common_ports = [7555, 16384]

        # 遍历每个端口尝试连接
        for port in common_ports:
            try:
                # 记录尝试日志
                logger.debug(f"尝试端口 {port}...")
                # 连接到该端口
                self.adb.connect(f"{self.DEFAULT_ADB_HOST}:{port}")
                # 获取设备列表
                devices = self.get_devices()
                if devices:
                    # 连接成功，记录日志并返回
                    logger.info(f"成功连接到端口 {port}")
                    return devices
            except (OSError, ConnectionError, RuntimeError):
                # 连接失败，继续尝试下一个端口
                continue

        # 所有端口都尝试失败，返回空列表
        return []

    def get_devices(self) -> List[AdbDevice]:
        """
        获取设备列表

        功能说明：
            获取当前所有已连接的ADB设备

        返回值：
            List[AdbDevice]: 设备对象列表
        """
        return self.adb.device_list()

    def get_device_resolution(self):
        """
        获取设备屏幕分辨率

        功能说明：
            通过ADB命令获取设备屏幕分辨率

        返回值：
            Tuple[int, int]: (宽度, 高度)的元组
        """
        # 执行wm size命令获取分辨率
        output = self.device_serial.shell("wm size")
        # 解析输出，格式为"Physical size: 1920x1080"
        resolution = output.split()[-1].split("x")
        return int(resolution[0]), int(resolution[1])

    def set_serial(self, name: str) -> bool:
        """
        设置目标设备

        功能说明：
            根据设备序列号设置当前操作的设备

        参数说明：
            name: 设备序列号

        返回值：
            bool: 设置成功返回True，失败返回False
        """
        # 遍历所有设备查找匹配的设备
        for e in self.get_devices():
            if e.serial == name:
                # 找到匹配设备，设置为当前设备
                self.device_serial = e
                return True
        return False

    def get_devices_name(self) -> list[str]:
        """
        获取设备名称列表

        功能说明：
            获取所有已连接设备的序列号列表

        返回值：
            list[str]: 设备序列号列表
        """
        # 获取设备列表
        devices = self.get_devices()
        # 初始化空列表存储设备名
        devices_name = []
        # 遍历设备，提取序列号
        for e in devices:
            devices_name.append(e.serial)
        return devices_name

    def execute_command(self, command: str) -> str:
        """
        执行ADB命令并返回结果

        功能说明：
            在设备上执行shell命令并返回输出

        参数说明：
            command: 要执行的命令

        返回值：
            str: 命令输出结果
        """
        return self.device_serial.shell(command)

    def execute_command_non_result(self, command: str):
        """
        执行ADB命令（不返回结果）

        功能说明：
            在设备上执行shell命令，不等待返回结果

        参数说明：
            command: 要执行的命令
        """
        self.device_serial.shell(command)

    @staticmethod
    def get_device_name(name: AdbDevice) -> str:
        """
        获取设备名称（静态方法）

        功能说明：
            从AdbDevice对象中提取序列号

        参数说明：
            name: AdbDevice设备对象

        返回值：
            str: 设备序列号
        """
        serial = name.serial
        if serial is None:
            raise RuntimeError("ADB设备缺少序列号")
        return serial

    # ===== 从 adb_executor.py 合并的方法 =====

    def _reconnect(self) -> bool:
        """
        重新连接设备（内部方法）

        功能说明：
            通过adbutils重新建立设备连接，仅在连接断开时调用

        返回值：
            bool: 重连成功返回True，失败返回False
        """
        try:
            serial = self.get_device_name(self.device_serial)
            self.adb.connect(serial)
            self.device_serial = self.adb.device(serial)
            self._connected = True
            logger.info(f"设备重连成功: {serial}")
            return True
        except (OSError, RuntimeError, adbutils.AdbError) as e:
            self._connected = False
            logger.error(f"设备重连失败: {e}")
            return False

    def _shell(self, cmd: str) -> Tuple[bool, str]:
        """
        通过adbutils长连接执行shell命令（快速通道）

        功能说明：
            使用adbutils的AdbDevice.shell()执行命令，避免subprocess开销
            连接断开时自动重连一次

        参数说明：
            cmd: 要执行的shell命令（不含'shell'前缀）

        返回值：
            Tuple[bool, str]: (是否成功, 输出内容)
        """
        try:
            output = self.device_serial.shell(cmd)
            return True, output if output else ""
        except (
            ConnectionError,
            ConnectionResetError,
            BrokenPipeError,
            RuntimeError,
            OSError,
            adbutils.AdbError,
        ) as e:
            logger.warning(f"shell 执行失败，尝试重连: {e}")
            if self._reconnect():
                try:
                    output = self.device_serial.shell(cmd)
                    return True, output if output else ""
                except (
                    ConnectionError,
                    RuntimeError,
                    OSError,
                    adbutils.AdbError,
                ) as e2:
                    logger.error(f"重连后执行仍失败: {e2}")
                    return False, f"重连后仍失败: {e2}"
            return False, f"连接已断开: {e}"

    def _ensure_connected(self) -> bool:
        """
        确保设备已连接（内部方法）

        功能说明：
            用于subprocess方式前确保设备连接状态
            已连接时直接返回，避免重复subprocess开销

        返回值：
            bool: 连接成功返回True，失败返回False
        """
        # 检查设备序列号是否已设置
        if not self.device_serial:
            logger.error("错误: 未设置设备 Serial")
            return False

        # 已连接时跳过重连
        if self._connected:
            return True

        try:
            # 使用CREATE_NO_WINDOW标志避免弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # 获取设备序列号
            serial = self.get_device_name(self.device_serial)
            # 构建连接命令
            cmd = f"{self.adb_path} connect {serial}"
            # 执行连接命令
            subprocess.run(
                cmd, shell=True, capture_output=True, timeout=5, startupinfo=startupinfo
            )
            self._connected = True
            return True
        except (OSError, subprocess.SubprocessError) as e:
            # 连接失败，记录错误
            logger.error(f"连接设备失败: {e}", exc_info=True)
            return False

    def _run_adb(self, command: str, timeout: int = 10, binary: bool = False):
        """
        运行ADB命令（subprocess方式）

        功能说明：
            使用subprocess执行ADB命令，支持超时和二进制输出

        参数说明：
            command: ADB命令（不含adb前缀）
            timeout: 超时时间（秒），默认10秒
            binary: 是否返回二进制数据，用于截图

        返回值：
            Tuple[bool, Union[str, bytes]]: (是否成功, 输出内容)
        """
        # 先确保设备已连接
        if not self._ensure_connected():
            error_msg = "Device not connected"
            return False, error_msg.encode() if binary else error_msg

        try:
            # 获取设备序列号
            serial = self.get_device_name(self.device_serial)
            # 构建完整命令
            full_cmd = f"{self.adb_path} -s {serial} {command}"

            # 使用CREATE_NO_WINDOW避免弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # 执行命令
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                timeout=timeout,
                startupinfo=startupinfo,
            )

            # 根据binary参数决定返回类型
            if binary:
                stdout = result.stdout if result.stdout else b""
                stderr = result.stderr if result.stderr else b""
            else:
                stdout = (
                    result.stdout.decode("utf-8", errors="ignore")
                    if result.stdout
                    else ""
                )
                stderr = (
                    result.stderr.decode("utf-8", errors="ignore")
                    if result.stderr
                    else ""
                )

            # 检查命令执行结果
            if result.returncode == 0:
                return True, stdout
            else:
                error_msg = stderr or stdout or "未知错误"
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"执行异常: {e}"

    def tap(self, x: int, y: int, delay: float = 0.1) -> bool:
        """
        点击屏幕

        功能说明：
            在指定坐标模拟点击操作，通过持久 shell 执行

        参数说明：
            x: X坐标（像素）
            y: Y坐标（像素）
            delay: 点击后延迟（秒）

        返回值：
            bool: 点击成功返回True，失败返回False
        """
        # 检查冷却时间
        now = time.time()
        if now - self.last_click_time < self.click_cooldown:
            # 如果点击太快，添加延迟
            time.sleep(self.click_cooldown - (now - self.last_click_time))

        # 通过持久 shell 点击屏幕
        self._shell_cmd(f"input tap {int(x)} {int(y)}")

        # 更新点击计数和时间
        self.click_count += 1
        self.last_click_time = time.time()

        # 如果指定了延迟，执行延迟
        if delay > 0:
            time.sleep(delay)
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        滑动屏幕

        功能说明：
            模拟从起始坐标滑动到结束坐标，通过持久 shell 执行

        参数说明：
            x1: 起始X坐标
            y1: 起始Y坐标
            x2: 结束X坐标
            y2: 结束Y坐标
            duration: 滑动持续时间（毫秒），默认300ms

        返回值：
            bool: 滑动成功返回True，失败返回False
        """
        # 记录滑动日志
        logger.debug(f"滑动 ({x1}, {y1}) -> ({x2}, {y2})")
        # 通过持久 shell 滑动
        self._shell_cmd(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration)}"
        )
        return True

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        长按屏幕

        功能说明：
            在指定坐标长按屏幕，通过 swipe 起终点相同实现

        参数说明：
            x: X坐标（像素）
            y: Y坐标（像素）
            duration: 长按持续时间（毫秒），默认1000ms

        返回值：
            bool: 长按成功返回True，失败返回False
        """
        return self.swipe(x, y, x, y, duration)

    def keyevent(self, keycode: int) -> bool:
        """
        发送按键事件

        功能说明：
            发送安卓按键事件（如返回键、Home键等），通过持久 shell 执行

        参数说明：
            keycode: 按键码（如4是返回键，3是Home键）

        返回值：
            bool: 发送成功返回True，失败返回False
        """
        logger.debug(f"按键 {keycode}")
        # 通过持久 shell 发送按键
        self._shell_cmd(f"input keyevent {keycode}")
        return True

    def text(self, text: str) -> bool:
        """
        输入文本

        功能说明：
            在设备上输入文本内容

        参数说明：
            text: 要输入的文本

        返回值：
            bool: 输入成功返回True，失败返回False
        """
        logger.debug(f"输入文本: {text}")
        # 替换空格为%s（ADB文本输入的特殊转义）
        text = text.replace(" ", "%s")
        # 执行文本输入命令（通过adbutils长连接）
        success, output = self._shell(f'input text "{text}"')

        if success:
            logger.debug(f"✓ 输入成功")
            return True
        else:
            logger.error(f"输入失败: {output}")
            return False

    def screenshot(
        self, save_path: Optional[str] = None, use_scrcpy: bool = True
    ) -> Optional[bytes]:
        """
        截图

        功能说明：
            获取设备屏幕截图
            优先使用FrameManager（scrcpy长连接）获取高性能截图
            失败时回退到ADB screencap命令

        参数说明：
            save_path: 保存路径，None则返回图片数据
            use_scrcpy: 是否优先使用scrcpy（FrameManager）

        返回值：
            bytes: 图片数据（如果save_path为None），否则返回None
        """
        # 优先使用FrameManager（高性能方式）
        if use_scrcpy:
            try:
                # 导入frame_manager和cv2
                from wzry_ai.utils.frame_manager import get_frame
                import cv2

                # 获取设备序列号
                serial = self.get_device_name(self.device_serial)
                # 从frame_manager获取帧
                frame = get_frame(device_serial=serial, timeout=0.05)
                if frame is not None:
                    # 编码为PNG格式
                    _, img_encoded = cv2.imencode(".png", frame)
                    img_bytes = img_encoded.tobytes()

                    # 如果指定了保存路径，保存到文件
                    if save_path:
                        with open(save_path, "wb") as f:
                            f.write(img_bytes)
                        return None
                    return img_bytes
            except (AttributeError, RuntimeError, OSError) as e:
                # FrameManager失败，回退到ADB方式
                pass

        # 回退到ADB screencap命令
        if save_path:
            logger.debug(f"截图保存到: {save_path}")
            success, output = self._run_adb(f"shell screencap -p > {save_path}")
            return None if success else None
        else:
            logger.debug(f"截图")
            # 使用exec-out直接获取二进制数据，避免字符串转换
            success, output = self._run_adb("exec-out screencap -p", binary=True)
            return output if success and isinstance(output, bytes) else None

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """
        获取屏幕分辨率（兼容旧方法名）

        功能说明：
            获取设备屏幕分辨率，兼容旧代码的方法名

        返回值：
            Tuple[int, int]: (宽度, 高度)，获取失败返回None
        """
        # 优先使用adbutils方式
        try:
            return self.get_device_resolution()
        except (AttributeError, RuntimeError, OSError):
            # 回退到_shell方式（仍使用adbutils长连接）
            success, output = self._shell("wm size")
            if success:
                try:
                    # 解析输出: Physical size: 1920x1080
                    parts = output.strip().split()
                    if len(parts) >= 3:
                        size_str = parts[-1]
                        width, height = map(int, size_str.split("x"))
                        return width, height
                except (ValueError, IndexError, AttributeError):
                    pass
            return None

    def get_click_count(self) -> int:
        """
        获取点击次数统计

        功能说明：
            获取自初始化以来的总点击次数

        返回值：
            int: 点击次数
        """
        return self.click_count

    def set_device(self, device_serial: str):
        """
        设置设备

        功能说明：
            切换当前操作的设备

        参数说明：
            device_serial: 设备序列号
        """
        self.device_serial = self.adb.device(device_serial)
        logger.info(f"设置设备: {device_serial}")


# ===== 便捷函数（保持向后兼容） =====


def tap(
    x: int, y: int, device_serial: Optional[str] = None, delay: float = 0.1
) -> bool:
    """
    快速点击（便捷函数）

    功能说明：
        无需创建ADBTool实例，直接执行点击操作

    参数说明：
        x: X坐标
        y: Y坐标
        device_serial: 设备序列号，None则自动检测
        delay: 点击后延迟

    返回值：
        bool: 点击成功返回True
    """
    # 创建ADBTool实例并执行点击
    executor = ADBTool(device_serial)
    return executor.tap(x, y, delay)


def swipe(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    device_serial: Optional[str] = None,
    duration: int = 300,
) -> bool:
    """
    快速滑动（便捷函数）

    功能说明：
        无需创建ADBTool实例，直接执行滑动操作

    参数说明：
        x1: 起始X坐标
        y1: 起始Y坐标
        x2: 结束X坐标
        y2: 结束Y坐标
        device_serial: 设备序列号，None则自动检测
        duration: 滑动持续时间（毫秒）

    返回值：
        bool: 滑动成功返回True
    """
    # 创建ADBTool实例并执行滑动
    executor = ADBTool(device_serial)
    return executor.swipe(x1, y1, x2, y2, duration)


# 测试代码块
if __name__ == "__main__":
    # 创建ADBTool实例
    tool = ADBTool()
    # 记录设备列表
    logger.info(f"设备列表: {tool.get_devices()}")
    # 记录设备分辨率
    logger.info(f"设备分辨率: {tool.get_device_resolution()}")
    # 记录CPU架构
    logger.info(f"CPU架构: {tool.execute_command('getprop ro.product.cpu.abi')}")
