"""
点击执行器模块 - 封装屏幕点击、滑动等操作

功能说明：
- 将图像坐标转换为设备屏幕坐标
- 通过ADB（ADBTool）执行点击、滑动、长按、按键等操作
- 提供点击冷却机制防止操作过快
- 支持分辨率缓存，避免重复查询设备分辨率

参数说明：
- adb_device: ADB设备地址，默认是"127.0.0.1:7555"
- use_adb: 是否使用ADB方式点击，默认True

返回值说明：
- 各方法返回bool表示操作是否成功
"""

import subprocess  # 导入子进程模块，用于执行ADB命令（降级备用）
import time  # 导入时间模块，用于控制点击间隔
from typing import Optional, Tuple  # 导入类型提示工具

# 导入ADB工具类（原adb_executor已合并到ADBTool中）
try:
    from wzry_ai.device.ADBTool import ADBTool  # 导入ADB操作封装类
except ImportError:
    ADBTool = None  # 导入失败则设为None（极端情况下的容错）

# 导入日志模块（与项目其他模块保持一致的日志风格）
from wzry_ai.utils.logging_utils import get_logger

# 创建当前模块的日志记录器
logger = get_logger(__name__)


class ClickExecutor:
    """
    点击执行器类 - 封装点击、滑动、长按等屏幕操作

    参数说明：
    - adb_device: ADB设备地址字符串，如"127.0.0.1:7555"
    - use_adb: 是否使用ADB方式（目前仅支持ADB，保留参数用于兼容）

    功能描述：
    统一管理屏幕操作，通过ADBTool执行底层点击/滑动/截图命令
    自动处理图像坐标到设备坐标的转换，内置冷却机制防止操作过快
    """

    def __init__(self, adb_device: str = "127.0.0.1:7555", use_adb: bool = True):
        """
        初始化点击执行器

        参数说明：
        - adb_device: ADB设备地址，如"127.0.0.1:7555"（MuMu模拟器默认端口）
        - use_adb: 是否使用ADB方式点击（默认True，目前仅支持ADB模式）
        """
        self.adb_device = adb_device  # 保存ADB设备地址
        self.use_adb = use_adb  # 保存是否使用ADB的标志
        self._click_count = 0  # 初始化点击次数计数器
        self._last_click_time = 0  # 初始化上次点击时间戳
        self._click_cooldown = 0.1  # 设置点击冷却时间为0.1秒，防止操作过快

        # ===== 分辨率缓存 =====
        # 避免每次点击都通过ADB查询设备分辨率，首次查询后缓存结果
        self._cached_resolution = None

        # ===== 创建ADBTool实例 =====
        # ADBTool是底层ADB操作封装，提供tap/swipe/screenshot/keyevent等方法
        # 替代原来不存在的adb_executor模块
        self._adb_tool = None  # 先初始化为None
        if ADBTool is not None:
            try:
                self._adb_tool = ADBTool(device_serial=adb_device)  # 创建ADB工具实例
                # 禁用ADBTool层的点击冷却，由ClickExecutor统一管理冷却
                # 避免双重冷却（ClickExecutor 0.1s + ADBTool 0.1s = 0.2s）
                self._adb_tool.click_cooldown = 0
                logger.info(f"ADBTool初始化成功，设备: {adb_device}")
            except (AttributeError, OSError, RuntimeError) as e:
                # ADBTool初始化失败（如设备未连接），记录错误但不中断
                logger.error(f"ADBTool初始化失败: {e}，将使用subprocess降级方案")
                self._adb_tool = None
        else:
            logger.warning("ADBTool模块未找到，将使用subprocess降级方案")

    # ========================================================================
    # 核心点击方法
    # ========================================================================

    def click(self, x: int, y: int, delay: float = 0.1,
              frame_width: int = 1920, frame_height: int = 1080) -> bool:
        """
        执行点击操作，将图像坐标转换为设备坐标后点击

        参数说明：
        - x: 图像中的X坐标（像素）
        - y: 图像中的Y坐标（像素）
        - delay: 点击后的等待时间（秒），默认0.1秒
        - frame_width: 图像宽度（像素），默认1920
        - frame_height: 图像高度（像素），默认1080

        返回值：
        - bool: 点击成功返回True，失败返回False

        功能描述：
        1. 检查点击冷却时间（防止操作过快）
        2. 将图像坐标转换为设备屏幕坐标
        3. 通过ADB执行点击
        4. 点击后等待指定延迟
        """
        # 冷却检查：如果距上次点击时间太短，等待剩余冷却时间
        elapsed = time.time() - self._last_click_time  # 计算距离上次点击的时间间隔
        if elapsed < self._click_cooldown:  # 如果间隔小于冷却时间
            time.sleep(self._click_cooldown - elapsed)  # 等待剩余冷却时间

        try:
            # 坐标转换：将图像坐标映射到设备屏幕坐标
            device_x, device_y = self._convert_coordinates(x, y, frame_width, frame_height)

            # 通过ADB执行实际点击
            self._click_adb(device_x, device_y)

            # 更新统计信息
            self._click_count += 1  # 点击次数加1
            self._last_click_time = time.time()  # 记录本次点击时间

            # 点击后等待延迟（给游戏UI响应时间）
            if delay > 0:
                time.sleep(delay)

            return True  # 返回成功

        except (AttributeError, OSError, RuntimeError) as e:
            logger.error(f"点击失败 ({x}, {y}): {e}")
            return False  # 返回失败

    def click_template(self, match_result, delay: float = 0.1) -> bool:
        """
        点击模板匹配结果的中心位置

        参数说明：
        - match_result: 模板匹配结果对象，包含location(位置)和size(大小)属性
        - delay: 点击后的等待时间（秒）

        返回值：
        - bool: 点击是否成功

        功能描述：
        计算匹配结果区域的中心点坐标，然后执行点击操作
        """
        x = match_result.location[0] + match_result.size[0] // 2  # 计算中心点X坐标
        y = match_result.location[1] + match_result.size[1] // 2  # 计算中心点Y坐标
        return self.click(x, y, delay)  # 调用click方法执行点击

    def click_region(self, region: Tuple[int, int, int, int], delay: float = 0.1) -> bool:
        """
        点击指定区域的中心位置

        参数说明：
        - region: 区域元组(x, y, width, height)，表示矩形区域的位置和大小
        - delay: 点击后的等待时间（秒）

        返回值：
        - bool: 点击是否成功

        功能描述：
        计算指定区域的中心点坐标，然后执行点击操作
        """
        x = region[0] + region[2] // 2  # 计算区域中心X坐标
        y = region[1] + region[3] // 2  # 计算区域中心Y坐标
        return self.click(x, y, delay)  # 调用click方法执行点击

    def click_with_retry(self, x: int, y: int, max_retries: int = 3,
                         delay: float = 0.3,
                         frame_width: int = 1920, frame_height: int = 1080) -> bool:
        """
        带重试的点击操作 - 点击失败时自动重试

        参数说明：
        - x: 图像中的X坐标
        - y: 图像中的Y坐标
        - max_retries: 最大重试次数，默认3次
        - delay: 每次重试之间的等待时间（秒），默认0.3秒
        - frame_width: 图像宽度
        - frame_height: 图像高度

        返回值：
        - bool: 任意一次点击成功则返回True，全部失败返回False

        功能描述：
        循环尝试点击操作，适用于网络延迟或UI加载缓慢的场景
        注意：这里只做简单重试，带模板验证的重试逻辑应在业务层（如state_detector）实现
        """
        for attempt in range(max_retries):
            # 每次尝试都调用click方法（第一次用正常delay，重试时用0.1秒短延迟）
            click_delay = 0.1 if attempt < max_retries - 1 else delay
            success = self.click(x, y, delay=click_delay,
                                 frame_width=frame_width, frame_height=frame_height)
            if success:
                return True  # 点击成功，立即返回

            # 点击失败，等待后重试
            logger.warning(f"点击重试 {attempt + 1}/{max_retries} ({x}, {y})")
            if attempt < max_retries - 1:  # 不是最后一次才等待
                time.sleep(delay)

        logger.error(f"点击最终失败 ({x}, {y})，已重试{max_retries}次")
        return False  # 全部重试失败

    # ========================================================================
    # 滑动和长按
    # ========================================================================

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        执行滑动操作

        参数说明：
        - x1: 起始点X坐标
        - y1: 起始点Y坐标
        - x2: 终点X坐标
        - y2: 终点Y坐标
        - duration: 滑动持续时间（毫秒），默认300ms

        返回值：
        - bool: 滑动是否成功

        功能描述：
        从起始点滑动到终点，通过ADBTool执行
        """
        try:
            if self._adb_tool:  # 如果ADBTool可用
                return self._adb_tool.swipe(x1, y1, x2, y2, duration)  # 调用ADBTool滑动
            else:
                # 降级方案：直接用subprocess执行adb swipe命令
                cmd = f'adb -s {self.adb_device} shell input swipe {x1} {y1} {x2} {y2} {duration}'
                logger.debug(f"降级执行ADB滑动命令: {cmd}")
                result = subprocess.run(cmd, shell=True, capture_output=True)
                return result.returncode == 0
        except (AttributeError, OSError, RuntimeError) as e:
            logger.error(f"滑动失败 ({x1},{y1})->({x2},{y2}): {e}")
            return False

    def long_press(self, x: int, y: int, duration: int = 1000,
                   frame_width: int = 1920, frame_height: int = 1080) -> bool:
        """
        执行长按操作

        参数说明：
        - x: 图像中的X坐标
        - y: 图像中的Y坐标
        - duration: 长按持续时间（毫秒），默认1000ms（1秒）
        - frame_width: 图像宽度
        - frame_height: 图像高度

        返回值：
        - bool: 长按是否成功

        功能描述：
        通过"起点终点相同的滑动"来模拟长按操作
        先将图像坐标转换为设备坐标，再执行swipe(x,y,x,y,duration)
        """
        try:
            # 坐标转换：将图像坐标映射到设备屏幕坐标
            device_x, device_y = self._convert_coordinates(x, y, frame_width, frame_height)
            # 长按 = 起点终点相同的滑动，duration控制按住时长
            return self.swipe(device_x, device_y, device_x, device_y, duration)
        except (AttributeError, OSError, RuntimeError) as e:
            logger.error(f"长按失败 ({x}, {y}): {e}")
            return False

    # ========================================================================
    # 截图和按键
    # ========================================================================

    def screenshot(self) -> Optional[bytes]:
        """
        截取设备屏幕截图

        返回值：
        - Optional[bytes]: 截图数据的字节流，失败返回None

        功能描述：
        通过ADBTool获取设备屏幕截图数据
        ADBTool内部会优先使用scrcpy截图，失败后降级到adb screencap
        """
        if self._adb_tool:  # 如果ADBTool可用
            try:
                return self._adb_tool.screenshot()  # 调用ADBTool截图方法
            except (AttributeError, OSError, RuntimeError) as e:
                logger.error(f"截图失败: {e}")
                return None
        else:
            logger.warning("无法截图，ADBTool未初始化")
            return None

    def keyevent(self, keycode: int) -> bool:
        """
        发送按键事件到设备

        参数说明：
        - keycode: Android按键码，常用值：
            - 4: 返回键（KEYCODE_BACK）
            - 3: Home键（KEYCODE_HOME）
            - 26: 电源键（KEYCODE_POWER）
            - 82: 菜单键（KEYCODE_MENU）

        返回值：
        - bool: 按键发送是否成功

        功能描述：
        通过ADBTool向设备发送Android按键事件
        """
        try:
            if self._adb_tool:  # 如果ADBTool可用
                return self._adb_tool.keyevent(keycode)  # 调用ADBTool按键方法
            else:
                # 降级方案：直接用subprocess执行
                cmd = f'adb -s {self.adb_device} shell input keyevent {keycode}'
                logger.debug(f"降级执行ADB按键命令: keycode={keycode}")
                result = subprocess.run(cmd, shell=True, capture_output=True)
                return result.returncode == 0
        except (AttributeError, OSError, RuntimeError) as e:
            logger.error(f"按键事件失败 (keycode={keycode}): {e}")
            return False

    # ========================================================================
    # 坐标转换（内部方法）
    # ========================================================================

    def _convert_coordinates(self, x: int, y: int,
                             frame_width: int, frame_height: int) -> Tuple[int, int]:
        """
        将图像坐标转换为设备屏幕坐标

        参数说明：
        - x: 图像中的X坐标
        - y: 图像中的Y坐标
        - frame_width: 图像宽度（像素）
        - frame_height: 图像高度（像素）

        返回值：
        - Tuple[int, int]: 转换后的设备坐标(device_x, device_y)

        功能描述：
        根据设备分辨率和图像分辨率的比例关系，将图像坐标映射到设备屏幕坐标
        同时处理横竖屏方向不一致的情况
        内置快速路径：当图像和设备都是1920x1080时直接返回，跳过所有计算
        """
        # ===== 快速路径：MuMu模拟器 1920x1080，无需任何转换 =====
        # 覆盖95%以上的调用场景，避免不必要的分辨率查询和计算
        if frame_width == 1920 and frame_height == 1080:
            device_width, device_height = self._get_device_resolution()
            if device_width == 1920 and device_height == 1080:
                return x, y  # 分辨率完全匹配，直接返回原坐标

        # ===== 常规路径：需要坐标缩放转换 =====
        device_width, device_height = self._get_device_resolution()  # 获取设备屏幕分辨率

        # 分辨率完全相同，无需转换
        if device_width == frame_width and device_height == frame_height:
            return x, y

        # 处理横竖屏方向不一致的情况
        device_is_landscape = device_width > device_height  # 判断设备是否为横屏
        frame_is_landscape = frame_width > frame_height  # 判断图像是否为横屏

        if device_is_landscape == frame_is_landscape:  # 方向一致
            actual_device_width = device_width  # 实际宽度就是设备宽度
            actual_device_height = device_height  # 实际高度就是设备高度
        else:  # 方向不一致（设备竖屏但图像横屏，或反之）
            actual_device_width = device_height  # 交换宽高
            actual_device_height = device_width  # 交换宽高

        # 交换后再次检查是否匹配
        if actual_device_width == frame_width and actual_device_height == frame_height:
            return x, y

        # 按比例缩放坐标
        scale_x = actual_device_width / frame_width  # 计算X轴缩放比例
        scale_y = actual_device_height / frame_height  # 计算Y轴缩放比例

        device_x = int(x * scale_x)  # 按比例转换X坐标
        device_y = int(y * scale_y)  # 按比例转换Y坐标

        logger.debug(f"坐标转换: ({x}, {y}) -> ({device_x}, {device_y}) "
                     f"(图像: {frame_width}x{frame_height}, "
                     f"设备: {actual_device_width}x{actual_device_height})")

        return device_x, device_y  # 返回转换后的坐标

    def _get_device_resolution(self) -> Tuple[int, int]:
        """
        获取设备屏幕分辨率（带缓存）

        返回值：
        - Tuple[int, int]: 设备宽度和高度
            成功时返回实际分辨率，失败时返回默认值(1920, 1080)

        功能描述：
        首次调用时通过ADBTool查询设备分辨率并缓存结果
        后续调用直接返回缓存值，避免重复的ADB查询开销
        查询失败时使用MuMu模拟器的默认分辨率1920x1080
        """
        # 优先返回缓存结果
        if self._cached_resolution is not None:
            return self._cached_resolution

        # 通过ADBTool查询设备分辨率
        if self._adb_tool:
            try:
                resolution = self._adb_tool.get_resolution()
                if resolution:  # 查询成功
                    self._cached_resolution = resolution  # 缓存结果
                    logger.debug(f"设备分辨率: {resolution[0]}x{resolution[1]}")
                    return resolution
            except (AttributeError, OSError, RuntimeError) as e:
                logger.warning(f"获取设备分辨率失败: {e}，使用默认值1920x1080")

        # 查询失败，使用MuMu模拟器默认分辨率
        default_resolution = (1920, 1080)
        self._cached_resolution = default_resolution  # 缓存默认值，下次不再查询
        return default_resolution

    def _click_adb(self, x: int, y: int):
        """
        使用ADB执行点击操作（内部方法）

        参数说明：
        - x: 设备屏幕X坐标（已转换）
        - y: 设备屏幕Y坐标（已转换）

        功能描述：
        优先使用ADBTool的tap方法执行点击
        ADBTool不可用时降级到直接执行adb shell命令（应急方案）
        """
        if self._adb_tool:  # ADBTool可用（正常路径）
            # delay=0：点击后不额外等待，由上层click()方法统一管理延迟
            self._adb_tool.tap(x, y, delay=0)
        else:  # ADBTool不可用（降级路径）
            # 直接通过subprocess执行adb shell命令
            cmd = f'adb -s {self.adb_device} shell input tap {x} {y}'
            logger.debug(f"降级执行ADB点击命令: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True)
            if result.returncode != 0:
                logger.error(f"ADB点击命令失败: {cmd}")

    # ========================================================================
    # 统计和重置
    # ========================================================================

    def get_stats(self) -> dict:
        """
        获取点击统计信息

        返回值：
        - dict: 包含以下字段的字典：
            - click_count: 累计点击次数
            - adb_device: ADB设备地址
            - use_adb: 是否使用ADB模式
            - adb_tool_available: ADBTool是否可用

        功能描述：
        返回当前点击执行器的运行统计信息，用于监控和调试
        """
        return {
            'click_count': self._click_count,  # 累计点击次数
            'adb_device': self.adb_device,  # ADB设备地址
            'use_adb': self.use_adb,  # 是否使用ADB
            'adb_tool_available': self._adb_tool is not None,  # ADBTool是否可用
        }

    def reset(self):
        """
        重置点击统计信息

        功能描述：
        将点击计数器和时间戳重置为初始状态
        不影响ADBTool连接和分辨率缓存
        """
        self._click_count = 0  # 点击次数清零
        self._last_click_time = 0  # 上次点击时间清零
