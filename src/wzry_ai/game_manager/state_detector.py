# -*- coding: utf-8 -*-
"""
状态检测器 - 核心模块

功能说明:
    本模块是王者荣耀AI的状态检测核心，负责实时检测游戏界面状态、
    执行状态转换、处理弹窗、自动执行游戏操作等。

    主要功能:
    1. 实时状态检测（分层策略：层级检测+深度检测）
    2. 状态确认和防抖处理
    3. 状态停滞检测和弹窗处理
    4. 自动游戏操作（点击、选英雄等）
    5. 状态可视化输出和调试信息

主要组件:
    - DetectionContext: 检测上下文数据类
    - DetectionResult: 检测结果数据类
    - GameStateDetector: 状态检测器主类
"""

# 导入时间模块，用于计时和延迟
import time

# 导入OpenCV用于图像处理
import cv2

# 导入数据类装饰器和字段工厂，用于创建数据类
from dataclasses import dataclass, field

# 导入类型提示
from typing import Any, Dict, Optional, Tuple

DetectionDetails = Dict[str, object]

# 从日志工具模块导入日志记录器
from wzry_ai.utils.logging_utils import get_logger, ThrottledLogger

# 尝试从配置模块导入相关配置
try:
    from wzry_ai.config import (
        AUTO_LAUNCH,  # 是否自动启动游戏
        POPUP_DETECTION_THRESHOLD,  # 弹窗检测阈值
        STATE_STUCK_THRESHOLD,  # 状态停滞检测阈值（秒）
        STATE_STUCK_VERIFY_COUNT,  # 状态停滞验证次数
        STATE_STUCK_VERIFY_INTERVAL,  # 状态停滞验证间隔（秒）
    )
except ImportError:
    # 如果导入失败，提供默认值
    AUTO_LAUNCH = True  # 默认启用自动启动
    POPUP_DETECTION_THRESHOLD = 0.7  # 弹窗检测默认阈值0.7
    STATE_STUCK_THRESHOLD = 10  # 状态停滞默认阈值10秒
    STATE_STUCK_VERIFY_COUNT = 3  # 默认验证3次
    STATE_STUCK_VERIFY_INTERVAL = 2.0  # 默认验证间隔2秒

# 从本地模块导入检测策略
from .detection_strategies import (
    DeepDetectionStrategy,  # 深度检测策略
    DetectionLevel,  # 检测级别枚举
    HierarchicalDetectionStrategy,  # 层级检测策略
)

# 从本地模块导入英雄选择器
from .hero_selector import HeroSelector

# 从本地模块导入弹窗处理器
from .popup_handler import PopupHandler

# 从本地模块导入状态定义相关
from .state_definitions import (
    GameState,
    STATE_SIGNATURES,
    get_state_description,
    get_state_flow,
)

# 从本地模块导入状态转换相关
from .state_transitions import get_possible_next_states

# 从本地模块导入状态可视化器
from .state_visualizer import StateVisualizer

# 从本地模块导入AI模式处理器
from .states.ai_mode_handler import AIModeHandler

# 获取模块级日志记录器
logger = get_logger(__name__)


@dataclass
class DetectionContext:
    """
    检测上下文数据类

    功能说明:
        存储状态检测过程中的上下文信息，用于跟踪检测状态和计数。

    参数说明:
        frame_count: 处理的帧数计数器
        last_known_state: 最后确认的已知状态
        unknown_start_time: 进入未知状态的开始时间戳
        consecutive_unknown: 连续未知状态的帧数
        last_detection_time: 上次检测的时间戳
    """

    frame_count: int = 0  # 处理的帧数计数器
    last_known_state: str = "unknown"  # 最后确认的已知状态
    unknown_start_time: Optional[float] = None  # 进入未知状态的开始时间
    consecutive_unknown: int = 0  # 连续未知状态的帧数
    last_detection_time: float = field(default_factory=time.time)  # 上次检测时间
    detection_context: Dict[str, Any] = field(
        default_factory=dict
    )  # 最近一次分层检测上下文


@dataclass
class DetectionResult:
    """
    检测结果数据类

    功能说明:
        封装单次状态检测的结果，包含检测到的状态、置信度、策略等信息。

    参数说明:
        state: 检测到的状态名称
        confidence: 检测置信度（0.0-1.0）
        strategy: 使用的检测策略级别
        timestamp: 检测时间戳
        is_confirmed: 状态是否已确认（防抖后）
        details: 详细的检测信息字典
    """

    state: str  # 检测到的状态名称
    confidence: float  # 检测置信度
    strategy: DetectionLevel  # 使用的检测策略
    timestamp: float  # 检测时间戳
    is_confirmed: bool = False  # 是否已确认
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息


class GameStateDetector:
    """
    游戏状态检测器主类

    功能说明:
        负责实时检测游戏界面状态，执行状态转换，处理弹窗，
        并根据状态自动执行相应的游戏操作。

    核心职责:
        1. 实时检测游戏界面状态（使用分层检测策略）
        2. 提供分层检测策略（层级检测/深度检测）
        3. 维护状态历史，支持防抖处理
        4. 与模板匹配系统集成
        5. 自动执行游戏操作（点击、选英雄等）

    参数说明（初始化参数）:
        template_matcher: 模板匹配器对象
        click_executor: 点击执行器对象
        history_size: 状态历史大小
        max_popup_depth: 弹窗处理最大深度
        confirm_threshold: 状态确认阈值（连续帧数）
        unknown_threshold: 未知状态处理阈值（连续帧数）
    """

    def __init__(
        self,
        template_matcher,
        click_executor,
        history_size: int = 5,
        max_popup_depth: int = 6,
        confirm_threshold: int = 3,
        unknown_threshold: int = 5,
    ):
        """
        初始化状态检测器

        参数说明:
            template_matcher: 模板匹配器对象，用于检测界面元素
            click_executor: 点击执行器对象，用于执行点击操作
            history_size: 状态历史大小（当前未使用）
            max_popup_depth: 弹窗处理最大深度，限制递归处理层数
            confirm_threshold: 状态确认阈值，连续检测到多少次才确认状态切换
            unknown_threshold: 未知状态处理阈值，连续多少次未知后触发弹窗处理
        """
        # 保存模板匹配器和点击执行器引用
        self.template_matcher = template_matcher
        self.click_executor = click_executor

        # 初始化子模块
        # 状态可视化器，用于跟踪和显示状态转换历史
        self.visualizer = StateVisualizer(history_size=20)
        # 弹窗处理器，用于处理未知状态下的弹窗
        self.popup_handler = PopupHandler(
            template_matcher, click_executor, max_popup_depth
        )
        # AI模式处理器，用于处理人机模式的配置
        self.ai_mode_handler = AIModeHandler(click_executor, template_matcher)

        # 初始化英雄选择器，用于自动选择英雄
        self.hero_selector = HeroSelector(template_matcher, click_executor)

        # 初始化当前状态和置信度
        self.current_state = GameState.UNKNOWN.value  # 初始状态为未知
        self.last_confidence = 0.0  # 上次检测置信度

        # 保存配置参数
        self.confirm_threshold = confirm_threshold  # 状态确认阈值
        self.unknown_threshold = unknown_threshold  # 未知状态阈值

        # 初始化检测上下文
        self.context = DetectionContext()
        # 状态确认计数器，记录各状态连续检测次数
        self.state_confirm_counter: Dict[str, int] = {}

        # 状态停滞验证相关变量
        self.stuck_verify_counter = 0  # 连续未检测到界面的次数
        self.last_stuck_check_time = 0  # 上次验证时间戳
        self._last_frame = None  # 保存当前帧用于停滞验证

        # 深度检测性能控制
        self.last_deep_detection = 0  # 上次深度检测时间戳
        self.deep_detection_interval = 2.0  # 深度检测最小间隔（秒）

        # 状态停滞检测相关
        self.last_state_change_time = time.time()  # 上次状态变化时间
        self.last_state_value = GameState.UNKNOWN.value  # 上次状态值

        # 状态动作冷却：防止每帧重复点击同一按钮
        self._action_cooldown = {}  # {state: last_click_time}
        self._action_cooldown_sec = 2.0  # 冷却时间（秒）

        # 初始化统计数据字典
        self.stats = {
            "total_detections": 0,  # 总检测次数
            "normal_hits": 0,  # 层级检测命中次数
            "deep_hits": 0,  # 深度检测命中次数
            "emergency_hits": 0,  # 紧急检测命中次数
            "unknown_hits": 0,  # 未知状态次数
            "popup_handles": 0,  # 弹窗处理次数
        }

        # 创建节流日志器，用于高频输出（每3秒最多输出一次）
        self._throttled = ThrottledLogger(logger, interval=3.0)

        # 输出初始化信息日志
        logger.info("=" * 70)
        logger.info("状态检测器初始化完成")
        logger.info(f"支持状态: {len(STATE_SIGNATURES)} 个")
        logger.info(f"弹窗处理深度: {max_popup_depth} 层")
        logger.info(f"状态确认阈值: {confirm_threshold} 帧")
        logger.info(f"未知状态阈值: {unknown_threshold} 帧")
        logger.info(f"状态停滞阈值: {STATE_STUCK_THRESHOLD} 秒")
        logger.info(f"状态停滞验证: {STATE_STUCK_VERIFY_COUNT} 次")
        logger.info("=" * 70)

    def _click_match_confirm_with_verification(
        self, click_x: int, click_y: int, img_gray
    ) -> bool:
        """
        点击匹配确认按钮并验证点击是否生效

        参数说明:
            click_x: 点击X坐标
            click_y: 点击Y坐标
            img_gray: 当前帧灰度图像（用于获取新截图前的参考）

        返回值:
            bool: 点击验证是否成功

        功能描述:
            执行匹配确认按钮的点击，并验证点击是否生效。
            验证逻辑：
            1. 点击按钮（金色"确认" -> 预期变为灰色"确定"）
            2. 等待短暂时间
            3. 检测 confirmed 模板（灰色"确定"按钮）
            4. 如果 confirmed 匹配成功，说明点击生效
            5. 如果仍然是 match_confirm（金色"确认"），重试点击
            6. 最多重试 3 次
        """
        max_retries = 3  # 最大重试次数
        verification_threshold = 0.5  # confirmed模板验证阈值

        # 循环尝试点击和验证
        for attempt in range(max_retries):
            # 执行点击操作
            logger.info(
                f"匹配成功，点击确认按钮: ({click_x}, {click_y}) [尝试 {attempt + 1}/{max_retries}]"
            )
            success = self.click_executor.click(click_x, click_y)

            # 如果点击执行失败，等待后重试
            if not success:
                logger.warning(f"⚠ 点击执行失败 [尝试 {attempt + 1}/{max_retries}]")
                time.sleep(0.3)
                continue

            # 点击后记录日志
            logger.info("匹配确认按钮已点击，验证中...")

            # 等待界面响应（给游戏时间处理点击）
            time.sleep(0.5)

            # 获取当前帧进行验证
            verification_frame = None
            # 尝试从template_matcher获取最新缓存帧（注意：_last_frame是BGR格式）
            if (
                hasattr(self.template_matcher, "_last_frame")
                and self.template_matcher._last_frame is not None
            ):
                bgr_frame = self.template_matcher._last_frame
                if len(bgr_frame.shape) == 3:
                    verification_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
                else:
                    verification_frame = bgr_frame
            else:
                # 如果没有缓存帧，使用传入的img_gray
                verification_frame = img_gray

            # 检测confirmed模板（灰色"确定"按钮）
            confirmed_result = self.template_matcher.detect(
                "confirmed", verification_frame, min_confidence=verification_threshold
            )

            # 如果检测到confirmed模板，说明点击生效（按钮变灰）
            if (
                confirmed_result.found
                and confirmed_result.confidence > verification_threshold
            ):
                logger.info(
                    f"✓ 匹配确认点击验证成功（按钮已变灰）置信度: {confirmed_result.confidence:.2f}"
                )
                return True

            # 检测是否仍然是match_confirm（金色"确认"按钮）
            match_confirm_result = self.template_matcher.detect(
                "match_confirm", verification_frame, min_confidence=0.5
            )

            # 如果仍然是match_confirm，说明点击未生效
            if match_confirm_result.found:
                if attempt < max_retries - 1:
                    # 还有重试次数，等待后重试
                    logger.warning(
                        f"⚠ 匹配确认点击未生效，重试点击... [尝试 {attempt + 1}/{max_retries}]"
                    )
                    time.sleep(0.3)
                else:
                    # 已用完所有重试次数
                    logger.error(f"✗ 匹配确认点击验证失败，已重试{max_retries}次")
            else:
                # 既不是confirmed也不是match_confirm，可能是状态已变化
                logger.info(f"✓ 按钮状态已变化（可能已确认或进入下一状态）")
                return True

        # 所有重试都失败，返回False
        return False

    def _check_state_stuck(self, current_state: str) -> bool:
        """
        检测状态是否停滞（支持多次验证）

        参数说明:
            current_state: 当前检测到的状态

        返回值:
            bool: 是否停滞超过阈值且多次验证通过

        功能描述:
            检测游戏是否卡在某个状态超过阈值时间。
            检测逻辑：
            1. 状态变化时重置计时器和验证计数器
            2. 停滞时间超过阈值后，进行多次验证
            3. 连续多次未检测到界面才返回True
        """
        current_time = time.time()

        # 状态变化时重置计时器和验证计数器
        if current_state != self.last_state_value:
            self.last_state_value = current_state
            self.last_state_change_time = current_time
            self.stuck_verify_counter = 0
            self.last_stuck_check_time = 0
            return False

        # 检查是否停滞超过阈值
        elapsed = current_time - self.last_state_change_time
        if elapsed < STATE_STUCK_THRESHOLD:
            return False

        # 停滞时间超过阈值，检查是否到了验证间隔
        if current_time - self.last_stuck_check_time < STATE_STUCK_VERIFY_INTERVAL:
            return False  # 还没到验证时间

        # 更新上次验证时间
        self.last_stuck_check_time = current_time

        # 验证：检测是否有任何母模板匹配
        from wzry_ai.config import TEMPLATE_CONFIDENCE_THRESHOLDS

        any_detected = False

        # 遍历所有母模式配置进行检测
        for parent_mode, config in TEMPLATE_CONFIDENCE_THRESHOLDS.items():
            parent_template = config.get("parent_template")
            if not parent_template:
                continue

            # 处理单个模板或模板列表
            templates = (
                [parent_template]
                if isinstance(parent_template, str)
                else parent_template
            )
            threshold = config.get("threshold", 0.8)

            # 检测该母模式的所有模板
            for template in templates:
                result = self.template_matcher.detect(
                    template, self._last_frame, min_confidence=threshold
                )
                if result.found and result.confidence > threshold:
                    any_detected = True
                    break
            if any_detected:
                break

        if any_detected:
            # 检测到界面，重置验证计数器
            self.stuck_verify_counter = 0
            return False
        else:
            # 未检测到界面，增加验证计数器
            self.stuck_verify_counter += 1
            self._throttled.warning(
                f"状态停滞验证 {self.stuck_verify_counter}/{STATE_STUCK_VERIFY_COUNT} - 未检测到任何界面",
                key="stuck_check",
            )

            # 检查是否达到验证次数阈值
            if self.stuck_verify_counter >= STATE_STUCK_VERIFY_COUNT:
                # 连续多次未检测到界面，确认停滞
                logger.warning(
                    f"⚠️ 状态停滞验证完成，连续{STATE_STUCK_VERIFY_COUNT}次未检测到界面"
                )
                self.stuck_verify_counter = 0  # 重置计数器
                return True
            return False

    def _scan_for_popups(
        self, img_gray, current_state: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        扫描弹窗元素

        参数说明:
            img_gray: 灰度图像，用于模板匹配
            current_state: 当前状态（用于判断哪些按钮是弹窗）

        返回值:
            Tuple[bool, str]: (是否发现弹窗, 弹窗模板名)

        功能描述:
            扫描画面中是否存在弹窗元素（如关闭按钮、返回按钮等），
            用于处理状态停滞时可能出现的弹窗。
        """
        # 基础弹窗扫描列表（关闭按钮，这些在任何状态都是弹窗）
        popup_templates = [
            "close1",
            "close2",
            "close3",
            "close4",  # 各种关闭按钮
            "rest_confirm",  # 防沉迷确认按钮
        ]

        # return_btn在状态停滞时作为弹窗处理（帮助退出卡住的界面）
        # 在未知状态下也作为导航按钮
        if current_state == GameState.UNKNOWN.value or current_state is not None:
            popup_templates.extend(["return_btn", "return_btn1"])

        # 遍历所有弹窗模板进行检测
        for template in popup_templates:
            result = self.template_matcher.detect(
                template, img_gray, min_confidence=POPUP_DETECTION_THRESHOLD
            )
            if result.found:
                # 发现弹窗，输出日志并返回
                self._throttled.info(
                    f"状态停滞 - 发现弹窗: {template} (置信度: {result.confidence:.2f})",
                    key="stuck_popup",
                )
                return True, template

        # 未发现弹窗
        return False, ""

    def _handle_stuck_state(
        self, img_gray, current_state: Optional[str] = None
    ) -> bool:
        """
        处理状态停滞 - 扫描并点击弹窗

        参数说明:
            img_gray: 灰度图像，用于模板匹配和点击
            current_state: 当前状态

        返回值:
            bool: 是否成功处理了弹窗

        功能描述:
            当检测到状态停滞时，扫描并点击弹窗以尝试恢复游戏流程。
            点击成功后重置状态计时器。
        """
        # 扫描弹窗
        found, template = self._scan_for_popups(img_gray, current_state)

        if found:
            # 重新检测获取弹窗位置
            result = self.template_matcher.detect(template, img_gray)
            if result.found:
                # 计算点击位置（模板中心点）
                x, y = result.location
                w, h = result.size
                click_x = x + w // 2
                click_y = y + h // 2

                try:
                    # 执行点击
                    logger.info(f"点击弹窗: {template}")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        # 更新弹窗处理统计
                        self.stats["popup_handles"] += 1
                        # 重置状态计时器，给界面响应时间
                        self.last_state_change_time = time.time()
                        return True
                except (AttributeError, OSError, RuntimeError) as e:
                    # 点击失败，记录错误
                    logger.error(f"点击弹窗失败: {e}", exc_info=True)

        # 未处理弹窗或处理失败
        return False

    def detect(
        self, img_gray, img_bgr=None, allow_popup_handle: bool = True
    ) -> DetectionResult:
        """
        主检测入口

        参数说明:
            img_gray: 灰度图像，用于模板匹配
            img_bgr: BGR原始图像（可选，用于RGB亮度验证）
            allow_popup_handle: 是否允许处理弹窗，默认为是

        返回值:
            DetectionResult: 检测结果对象，包含状态、置信度等信息

        功能描述:
            状态检测的主入口方法，执行完整的检测流程：
            1. 分层检测确定当前状态
            2. 状态确认（防抖处理）
            3. 未知状态处理
            4. 状态停滞检测和处理
            5. 根据状态执行相应的自动操作
        """
        # 更新帧计数和检测统计
        self.context.frame_count += 1
        self.stats["total_detections"] += 1

        # 保存当前帧用于停滞验证
        self._last_frame = img_gray

        # 设置上一帧用于RGB验证
        if img_bgr is not None:
            self.template_matcher.set_last_frame(img_bgr)

        # 初始化详细信息字典
        details: DetectionDetails = {
            "frame_count": self.context.frame_count,
            "consecutive_unknown": self.context.consecutive_unknown,
        }

        # ========== 1. 分层检测 ==========
        detected_state, confidence, strategy = self._detect_with_strategy(img_gray)

        # ========== 2. 状态确认（防抖） ==========
        confirmed_state, is_confirmed = self._confirm_state(
            detected_state, confidence, strategy
        )

        # ========== 3. 未知状态处理 ==========
        if confirmed_state == GameState.UNKNOWN.value and allow_popup_handle:
            # 尝试通过弹窗处理恢复已知状态
            confirmed_state = self._handle_unknown_state(img_gray)
            if confirmed_state != GameState.UNKNOWN.value:
                # 弹窗处理成功，重置置信度和策略
                confidence = 0.5
                strategy = DetectionLevel.NORMAL

        # ========== 4. 状态停滞检测 ==========
        # 定义正常的过渡状态（这些状态本身就需要等待，不进行检测）
        TRANSITION_STATES = [
            GameState.GAME_LOADING_VS.value,  # VS加载画面
            GameState.MATCHING.value,  # 匹配中
            GameState.MATCH_FOUND.value,  # 匹配成功弹窗（需要手动确认）
        ]

        # 非未知状态且非过渡状态下检查是否卡在某个状态
        if (
            confirmed_state != GameState.UNKNOWN.value
            and confirmed_state not in TRANSITION_STATES
            and allow_popup_handle
        ):
            if self._check_state_stuck(confirmed_state):
                # 扫描并尝试处理弹窗
                self._throttled.info(
                    f"状态 '{confirmed_state}' 停滞 {STATE_STUCK_THRESHOLD} 秒，扫描弹窗...",
                    key="stuck_scan",
                )
                handled = self._handle_stuck_state(img_gray, confirmed_state)
                if handled:
                    # 弹窗已处理，记录到详细信息
                    details["stuck_popup_handled"] = True
                    # 重置停滞计时器，给界面响应时间
                    self.last_state_change_time = time.time()

        # ========== 5. 更新可视化 ==========
        if confirmed_state != self.current_state or strategy == DetectionLevel.DEEP:
            flow = get_state_flow(confirmed_state)
            self.visualizer.update(
                confirmed_state, flow, confidence, trigger=strategy.value
            )

        # ========== 6. 根据状态执行自动操作 ==========
        # AI模式处理（配置比对和自动调整）
        if confirmed_state == GameState.BATTLE_AI_MODE.value:
            # 独立检测当前选中的模式和难度（不依赖层级检测上下文）
            # 通过模板匹配+RGB亮度检查，只有高亮（选中）的按钮才返回found=True
            ai_context = {}

            # 检测当前选中的模式（标准/快速）- 使用置信度最高匹配
            mode_templates = {"ai_standard": "标准模式", "ai_quick": "快速模式"}
            best_mode_name = None
            best_mode_conf = 0.0
            for tmpl_name, mode_name in mode_templates.items():
                result = self.template_matcher.detect(
                    tmpl_name, img_gray, min_confidence=0.50
                )
                logger.info(
                    f"模式检测: {tmpl_name} found={result.found}, conf={result.confidence:.3f}"
                )
                if result.confidence > best_mode_conf:
                    best_mode_conf = result.confidence
                    best_mode_name = mode_name
            # 置信度最高且超过阈值的作为当前选中模式
            if best_mode_name and best_mode_conf >= 0.70:
                ai_context["ai_selected_mode"] = best_mode_name
                logger.info(f"选中模式: {best_mode_name} (conf={best_mode_conf:.3f})")

            # 检测当前选中的难度 - 使用置信度最高匹配
            difficulty_templates = {
                "ai_recommend": "推荐",
                "ai_bronze": "青铜",
                "ai_gold": "黄金",
                "ai_diamond": "钻石",
                "ai_star": "星耀",
                "ai_master": "王者",
            }
            best_diff_name = None
            best_diff_conf = 0.0
            best_found_name = None  # found=True 中置信度最高的
            best_found_conf = 0.0
            all_detected_difficulties = []
            for tmpl_name, diff_name in difficulty_templates.items():
                result = self.template_matcher.detect(
                    tmpl_name, img_gray, min_confidence=0.30
                )
                logger.info(
                    f"难度检测: {tmpl_name} found={result.found}, conf={result.confidence:.3f}"
                )
                if result.confidence > best_diff_conf:
                    best_diff_conf = result.confidence
                    best_diff_name = diff_name
                # 优先记录 found=True 的最高置信度结果
                if result.found and result.confidence > best_found_conf:
                    best_found_conf = result.confidence
                    best_found_name = diff_name
                # 收集所有高置信度匹配（包括 found=True 的）
                if result.found or result.confidence >= 0.90:
                    all_detected_difficulties.append(diff_name)
            # 优先使用 found=True 的结果，回退到置信度最高的
            selected_diff = best_found_name if best_found_name else best_diff_name
            selected_conf = best_found_conf if best_found_name else best_diff_conf
            if selected_diff and selected_conf >= 0.40:
                ai_context["ai_selected_difficulty"] = selected_diff
                logger.info(
                    f"选中难度: {selected_diff} (conf={selected_conf:.3f}, found_match={'是' if best_found_name else '否'})"
                )
            # 传递所有检测到的难度（用于推荐难度的双重高亮处理）
            if all_detected_difficulties:
                ai_context["all_detected_difficulties"] = all_detected_difficulties
                logger.info(f"所有检测到的难度: {all_detected_difficulties}")

            # 检查并调整模式/难度
            current_mode = ai_context.get("ai_selected_mode", "未检测")
            current_difficulty = ai_context.get("ai_selected_difficulty", "未检测")
            all_difficulties = ai_context.get("all_detected_difficulties", [])
            logger.info(
                f"当前选中: 模式={current_mode}, 难度={current_difficulty}, 所有检测到的难度={all_difficulties}"
            )
            # 调用AI模式处理器检查配置并自动调整
            can_proceed = self.ai_mode_handler.check_and_adjust(ai_context, img_gray)
            details["ai_config_matched"] = can_proceed

            # 配置正确后，点击开始练习按钮（仅在自动启动模式下，使用ROI坐标直接点击）
            if can_proceed and AUTO_LAUNCH:
                from wzry_ai.config import TEMPLATE_ROI

                roi = TEMPLATE_ROI.get("start_practice")
                if roi:
                    click_x = roi["x"] + roi["w"] // 2
                    click_y = roi["y"] + roi["h"] // 2

                    try:
                        logger.info(
                            f"配置正确，直接点击开始练习: ({click_x}, {click_y})"
                        )
                        success = self.click_executor.click(click_x, click_y)
                    except (AttributeError, OSError, RuntimeError) as e:
                        logger.error(f"点击失败: {e}", exc_info=True)

        # Launcher界面 - 点击游戏图标启动游戏（仅在自动启动模式下）
        if confirmed_state == GameState.LAUNCHER.value and AUTO_LAUNCH:
            # 检测游戏图标位置并点击
            result = self.template_matcher.detect(
                "wzry_icon", img_gray, min_confidence=0.70
            )
            if result.found:
                # 计算图标中心点坐标
                x, y = result.location
                w, h = result.size
                click_x = x + w // 2
                click_y = y + h // 2

                try:
                    logger.info(f"检测到游戏图标，点击位置: ({click_x}, {click_y})")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_wzry_icon"
                        logger.info(f"✓ 游戏图标点击成功")
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击游戏图标异常: {e}", exc_info=True)

        # 选区界面 - 点击进入游戏（直接点击ROI）（仅在自动启动模式下）
        if confirmed_state == GameState.SELECT_ZONE.value and AUTO_LAUNCH:
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("start_game")
            if roi:
                # 计算ROI中心点坐标
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2
                try:
                    logger.info(f"选区界面，直接点击开始游戏: ({click_x}, {click_y})")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_start_game"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击进入游戏异常: {e}", exc_info=True)

        # 选英雄界面 - 自动选择英雄
        if confirmed_state == GameState.HERO_SELECT.value:
            # 自动按优先级选择英雄（传入彩色图像用于RGB验证）
            select_result = self.hero_selector.select_hero_by_priority(
                img_gray, img_bgr
            )
            details["hero_select_result"] = {
                "success": select_result.success,
                "selected_hero": select_result.selected_hero,
                "message": select_result.message,
                "needs_refresh": select_result.needs_refresh,
            }

            # 如果需要刷新图像（如刚点击进入分路选择），跳过本次后续处理
            if select_result.needs_refresh:
                details["action"] = "wait_for_lane_refresh"
                # 返回DetectionResult对象
                return DetectionResult(
                    state=confirmed_state,
                    confidence=confidence,
                    strategy=strategy,
                    timestamp=time.time(),
                    is_confirmed=is_confirmed,
                    details=details,
                )

            # 如果英雄选择已成功，记录选中的英雄
            if select_result.success and select_result.selected_hero:
                details["selected_hero"] = select_result.selected_hero

        # 游戏大厅 - 根据配置选择对战模式或排位模式
        if confirmed_state == GameState.HALL.value and self._try_action("hall"):
            from wzry_ai.config import TEMPLATE_ROI, GAME_MODE

            # 根据游戏模式选择点击目标
            if GAME_MODE == "ranking":
                # 排位模式：点击排位赛按钮
                roi = TEMPLATE_ROI.get("ranking")
                action_desc = "排位赛"
                action_key = "clicked_ranking"
            else:
                # 对战模式：点击对战模式按钮
                roi = TEMPLATE_ROI.get("battle")
                action_desc = "对战模式"
                action_key = "clicked_battle"

            if roi:
                # 计算ROI中心点坐标
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2
                try:
                    logger.info(
                        f"游戏大厅，直接点击{action_desc}: ({click_x}, {click_y})"
                    )
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = action_key
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击{action_desc}异常: {e}", exc_info=True)

        # 对战模式选择 - 点击5V5（直接点击ROI）
        if confirmed_state == GameState.BATTLE_MODE_SELECT.value and self._try_action(
            "battle_mode_select"
        ):
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("5v5_canyon")
            if roi:
                # 计算ROI中心点坐标
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2
                try:
                    logger.info(f"对战模式选择，直接点击5V5: ({click_x}, {click_y})")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_5v5"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击5V5异常: {e}", exc_info=True)

        # 排位赛模式选择界面 - 点击进入排位房间
        if confirmed_state == GameState.RANKING_MATCH_SELECT.value:
            result = self.template_matcher.detect("ranking_match", img_gray)
            if result.found:
                # 计算按钮中心点坐标
                x, y = result.location
                w, h = result.size
                click_x = x + w // 2
                click_y = y + h // 2
                try:
                    logger.info(f"排位赛模式选择界面，点击进入排位房间")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_enter_ranking_room"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击进入排位房间异常: {e}", exc_info=True)

        # 排位赛选英雄界面 - 选择英雄并锁定
        if confirmed_state == GameState.RANKING_HERO_SELECT.value:
            # 使用hero_selector选择英雄
            select_result = self.hero_selector.select_hero_in_ranking(img_gray, img_bgr)
            if select_result.success:
                details["hero_select_result"] = {
                    "success": True,
                    "selected_hero": select_result.selected_hero,
                    "message": select_result.message,
                }
                details["action"] = (
                    f"ranking_hero_selected_{select_result.selected_hero}"
                )
            else:
                details["hero_select_result"] = {
                    "success": False,
                    "message": select_result.message,
                }

        # 5V5子菜单 - 根据配置选择人机或匹配（使用ROI坐标直接点击）
        if confirmed_state == GameState.BATTLE_5V5_SUB.value and self._try_action(
            "battle_5v5_sub"
        ):
            from wzry_ai.config import V5_MODE, TEMPLATE_ROI

            # 根据配置选择ROI：ai=人机, match=匹配
            if V5_MODE == "ai":
                roi_name = "ai_mode"
                action_desc = "人机"
            else:
                roi_name = "canyon_match"
                action_desc = "匹配"

            roi = TEMPLATE_ROI.get(roi_name)
            if roi:
                # 使用ROI中心点坐标（状态已确认，直接点击已知位置）
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2

                try:
                    logger.info(
                        f"王者峡谷界面，直接点击{action_desc}: ({click_x}, {click_y})"
                    )
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = f"clicked_{roi_name}"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击{action_desc}异常: {e}", exc_info=True)

        # 对战类型选择 - 点击人机（使用ROI坐标直接点击）
        if confirmed_state == GameState.BATTLE_5V5_TYPE.value and self._try_action(
            "battle_5v5_type"
        ):
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("ai_mode")
            if roi:
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2

                try:
                    logger.info(
                        f"对战类型选择，直接点击人机模式: ({click_x}, {click_y})"
                    )
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_ai_mode"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击人机模式异常: {e}", exc_info=True)

        # 人机难度选择 / 已选难度等待开始 — 与BATTLE_AI_MODE是同一界面
        # 使用相同的配置检查逻辑：独立检测当前模式/难度，比对配置后再操作
        if confirmed_state in (
            GameState.BATTLE_AI_DIFFICULTY.value,
            GameState.BATTLE_START_PRACTICE.value,
        ):
            ai_context = {}

            # 检测当前选中的模式 - 使用置信度最高匹配
            mode_templates = {"ai_standard": "标准模式", "ai_quick": "快速模式"}
            best_mode_name = None
            best_mode_conf = 0.0
            for tmpl_name, mode_name in mode_templates.items():
                result = self.template_matcher.detect(
                    tmpl_name, img_gray, min_confidence=0.50
                )
                logger.info(
                    f"模式检测: {tmpl_name} found={result.found}, conf={result.confidence:.3f}"
                )
                if result.confidence > best_mode_conf:
                    best_mode_conf = result.confidence
                    best_mode_name = mode_name
            # 置信度最高且超过阈值的作为当前选中模式
            if best_mode_name and best_mode_conf >= 0.70:
                ai_context["ai_selected_mode"] = best_mode_name
                logger.info(f"选中模式: {best_mode_name} (conf={best_mode_conf:.3f})")

            # 检测当前选中的难度 - 使用置信度最高匹配
            difficulty_templates = {
                "ai_recommend": "推荐",
                "ai_bronze": "青铜",
                "ai_gold": "黄金",
                "ai_diamond": "钻石",
                "ai_star": "星耀",
                "ai_master": "王者",
            }
            best_diff_name = None
            best_diff_conf = 0.0
            best_found_name = None  # found=True 中置信度最高的
            best_found_conf = 0.0
            all_detected_difficulties = []
            for tmpl_name, diff_name in difficulty_templates.items():
                result = self.template_matcher.detect(
                    tmpl_name, img_gray, min_confidence=0.30
                )
                logger.info(
                    f"难度检测: {tmpl_name} found={result.found}, conf={result.confidence:.3f}"
                )
                if result.confidence > best_diff_conf:
                    best_diff_conf = result.confidence
                    best_diff_name = diff_name
                # 优先记录 found=True 的最高置信度结果
                if result.found and result.confidence > best_found_conf:
                    best_found_conf = result.confidence
                    best_found_name = diff_name
                # 收集所有高置信度匹配（包括 found=True 的）
                if result.found or result.confidence >= 0.90:
                    all_detected_difficulties.append(diff_name)
            # 优先使用 found=True 的结果，回退到置信度最高的
            selected_diff = best_found_name if best_found_name else best_diff_name
            selected_conf = best_found_conf if best_found_name else best_diff_conf
            if selected_diff and selected_conf >= 0.40:
                ai_context["ai_selected_difficulty"] = selected_diff
                logger.info(
                    f"选中难度: {selected_diff} (conf={selected_conf:.3f}, found_match={'是' if best_found_name else '否'})"
                )
            # 传递所有检测到的难度（用于推荐难度的双重高亮处理）
            if all_detected_difficulties:
                ai_context["all_detected_difficulties"] = all_detected_difficulties
                logger.info(f"所有检测到的难度: {all_detected_difficulties}")

            can_proceed = self.ai_mode_handler.check_and_adjust(ai_context, img_gray)
            details["ai_config_matched"] = can_proceed

            if can_proceed and AUTO_LAUNCH:
                from wzry_ai.config import TEMPLATE_ROI

                roi = TEMPLATE_ROI.get("start_practice")
                if roi:
                    click_x = roi["x"] + roi["w"] // 2
                    click_y = roi["y"] + roi["h"] // 2
                    try:
                        logger.info(
                            f"配置正确，直接点击开始练习: ({click_x}, {click_y})"
                        )
                        success = self.click_executor.click(click_x, click_y)
                        if success:
                            details["action"] = "clicked_start_practice"
                    except (AttributeError, OSError, RuntimeError) as e:
                        logger.error(f"点击开始练习异常: {e}", exc_info=True)

        # 对战房间 - 点击开始匹配（使用ROI坐标直接点击）
        if confirmed_state == GameState.BATTLE_ROOM.value and self._try_action(
            "battle_room"
        ):
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("start_match")
            if roi:
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2

                try:
                    logger.info(f"对战房间，直接点击开始匹配: ({click_x}, {click_y})")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_start_match"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击开始匹配异常: {e}", exc_info=True)

        # 更新日志弹窗 - 点击关闭
        if confirmed_state == GameState.UPDATE_LOG.value:
            # 尝试多个关闭按钮
            for close_btn in ["close1", "close2", "close3", "close4"]:
                result = self.template_matcher.detect(close_btn, img_gray)
                if result.found:
                    # 计算按钮中心点坐标
                    x, y = result.location
                    w, h = result.size
                    click_x = x + w // 2
                    click_y = y + h // 2

                    try:
                        logger.info(f"点击关闭按钮")
                        success = self.click_executor.click(click_x, click_y)
                        if success:
                            details["action"] = f"clicked_{close_btn}"
                            break
                    except (AttributeError, OSError, RuntimeError) as e:
                        logger.error(f"点击关闭按钮异常: {e}", exc_info=True)

        # 防沉迷弹窗 - 点击确认
        if confirmed_state == GameState.REST_POPUP.value:
            result = self.template_matcher.detect("rest_confirm", img_gray)
            if result.found:
                # 计算按钮中心点坐标
                x, y = result.location
                w, h = result.size
                click_x = x + w // 2
                click_y = y + h // 2

                try:
                    logger.info(f"点击防沉迷确认")
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_rest_confirm"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击防沉迷确认异常: {e}", exc_info=True)

        # 匹配成功 - 点击确认按钮
        logger.debug(
            f"状态检查: confirmed_state={confirmed_state}, MATCH_FOUND={GameState.MATCH_FOUND.value}"
        )
        if confirmed_state in (
            GameState.MATCH_FOUND.value,
            GameState.MATCH_CONFIRMED.value,
        ):
            # 匹配确认按钮位置固定（基于confirm/hero_confirm模板实测: x=800,y=848,w=320,h=104）
            click_x, click_y = 960, 900
            logger.debug(
                f"匹配成功状态，模板检测结果: found=True, conf=1.000 (使用固定ROI坐标)"
            )
            try:
                # 使用带验证的点击方法
                success = self._click_match_confirm_with_verification(
                    click_x, click_y, img_gray
                )
                if success:
                    details["action"] = "clicked_match_confirm"
            except (AttributeError, OSError, RuntimeError) as e:
                logger.error(f"点击匹配确认异常: {e}", exc_info=True)

        # 结算界面 - 点击胜利/失败按钮（直接点击ROI）
        if confirmed_state == GameState.GAME_END.value:
            from wzry_ai.config import TEMPLATE_ROI

            # 依次尝试点击胜利/失败按钮的ROI位置
            # 优先尝试检测到的模板，然后依次尝试其他按钮
            detection_ctx = getattr(self.context, "detection_context", {})
            parent_details = detection_ctx.get("parent_details", {})
            detected_template = parent_details.get("template")  # 检测到的具体模板

            # 构建点击顺序：优先检测到的模板，然后是victory、victory1、defeat
            buttons_to_try = []
            if detected_template and detected_template in [
                "victory",
                "victory1",
                "defeat",
            ]:
                buttons_to_try.append(detected_template)
            # 添加其他按钮（避免重复）
            for btn in ["victory", "victory1", "defeat"]:
                if btn not in buttons_to_try:
                    buttons_to_try.append(btn)

            # 依次尝试点击
            for btn_template in buttons_to_try:
                roi = TEMPLATE_ROI.get(btn_template)
                if roi:
                    # 计算ROI中心点坐标
                    click_x = roi["x"] + roi["w"] // 2
                    click_y = roi["y"] + roi["h"] // 2
                    try:
                        logger.info(
                            f"结算界面，直接点击{btn_template}: ({click_x}, {click_y})"
                        )
                        success = self.click_executor.click(click_x, click_y)
                        if success:
                            details["action"] = f"clicked_{btn_template}"
                            break  # 点击成功，跳出循环
                    except (AttributeError, OSError, RuntimeError) as e:
                        logger.error(f"点击胜利/失败按钮异常: {e}", exc_info=True)

        # MVP展示 - 直接点击继续按钮（无需检测，直接点击ROI位置）
        if confirmed_state == GameState.MVP_DISPLAY.value:
            # 使用ROI配置直接计算点击位置
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("continue")
            if roi:
                # 计算ROI中心点坐标
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2
                try:
                    logger.info(
                        f"MVP展示状态，直接点击继续按钮: ({click_x}, {click_y})"
                    )
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_continue"
                        logger.info(f"✓ MVP继续按钮点击成功")
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击MVP继续异常: {e}", exc_info=True)

        # 赛后数据 - 点击返回房间（直接点击ROI）
        if confirmed_state == GameState.POST_MATCH_STATS.value:
            from wzry_ai.config import TEMPLATE_ROI

            roi = TEMPLATE_ROI.get("return_to_the_room")
            if roi:
                # 计算ROI中心点坐标
                click_x = roi["x"] + roi["w"] // 2
                click_y = roi["y"] + roi["h"] // 2
                try:
                    logger.info(
                        f"赛后数据界面，直接点击返回房间: ({click_x}, {click_y})"
                    )
                    success = self.click_executor.click(click_x, click_y)
                    if success:
                        details["action"] = "clicked_return_room"
                except (AttributeError, OSError, RuntimeError) as e:
                    logger.error(f"点击返回房间异常: {e}", exc_info=True)

        # ========== 7. 更新当前状态 ==========
        if confirmed_state != self.current_state and is_confirmed:
            # 状态已确认切换，清除冷却记录使新状态处理器能立即执行
            self._action_cooldown.clear()
            # 执行状态转换
            self._transition_state(confirmed_state, confidence, strategy)

        # 更新当前状态和置信度
        self.current_state = confirmed_state
        self.last_confidence = confidence

        # 返回检测结果
        return DetectionResult(
            state=confirmed_state,
            confidence=confidence,
            strategy=strategy,
            timestamp=time.time(),
            is_confirmed=is_confirmed,
            details=details,
        )

    def force_set_state(self, state: str):
        """
        强制设置当前状态

        参数说明:
            state: 要设置的状态名称

        功能描述:
            强制将当前状态设置为指定值，用于模态检测确认进入战斗等场景。
            会触发状态切换日志和可视化更新。
        """
        if state != self.current_state:
            logger.info(f"强制切换状态: {self.current_state} -> {state}")
            self._transition_state(state, 0.9, DetectionLevel.NORMAL)
            self.current_state = state

    def _detect_with_strategy(self, img_gray) -> Tuple[str, float, DetectionLevel]:
        """
        分层策略检测

        参数说明:
            img_gray: 灰度图像，用于模板匹配

        返回值:
            Tuple[str, float, DetectionLevel]: (状态名, 置信度, 检测策略)

        功能描述:
            按优先级执行检测策略：
            1. 首先尝试层级检测策略（母-子模式检测）
            2. 如果层级检测失败，尝试深度检测策略（限制频率）
            3. 如果都失败，返回未知状态
        """
        # 策略1: 母-子模式层级检测
        detection_context = {}
        strategy = HierarchicalDetectionStrategy(self.current_state)
        state = strategy.detect(img_gray, self.template_matcher, detection_context)
        if state:
            # 层级检测成功，更新统计
            self.stats["normal_hits"] += 1
            # 保存检测上下文供后续使用
            self.context.detection_context = detection_context
            return (
                state,
                detection_context.get("parent_confidence", 0.75),
                DetectionLevel.NORMAL,
            )

        # 策略2: 深度检测（限制频率，避免性能问题）
        now = time.time()
        if now - self.last_deep_detection > self.deep_detection_interval:
            self.last_deep_detection = now
            deep = DeepDetectionStrategy()
            result = deep.detect(img_gray, self.template_matcher, {})
            if result:
                # 深度检测成功，更新统计
                self.stats["deep_hits"] += 1
                state, confidence = result
                return state, confidence, DetectionLevel.DEEP

        # 未检测到任何状态
        self.stats["unknown_hits"] += 1
        return GameState.UNKNOWN.value, 0.0, DetectionLevel.NORMAL

    def _try_action(self, state: str) -> bool:
        """检查状态动作是否在冷却中，未冷却则标记并返回True"""
        now = time.time()
        last = self._action_cooldown.get(state, 0)
        if now - last < self._action_cooldown_sec:
            return False
        self._action_cooldown[state] = now
        return True

    def _confirm_state(
        self,
        detected_state: str,
        confidence: float,
        strategy: DetectionLevel = DetectionLevel.NORMAL,
    ) -> Tuple[str, bool]:
        """
        状态确认（连续帧防抖）

        参数说明:
            detected_state: 检测到的状态
            confidence: 检测置信度
            strategy: 检测策略级别，deep检测不允许立即确认关键状态

        返回值:
            Tuple[str, bool]: (确认后的状态, 是否已确认)

        功能描述:
            对检测到的状态进行防抖处理，防止状态频繁跳动。
            相同状态快速确认，关键状态立即确认（仅限层级检测），
            新状态需要连续检测达到阈值才确认。

            对于模板匹配不稳定的状态（如 battle_ai_mode），使用更低的确认阈值，
            以加快状态确认速度，避免由于交替帧检测导致的确认延迟。
        """
        # 定义需要快速确认的状态及其阈值（相对于默认阈值的降低比例）
        # 这些状态的模板匹配可能不稳定，需要更快的确认速度
        FAST_CONFIRM_STATES = {
            GameState.BATTLE_AI_MODE.value: 2,  # 人机模式设置界面，模板匹配不稳定
            GameState.BATTLE_AI_DIFFICULTY.value: 2,  # 人机难度选择（同界面）
            GameState.BATTLE_START_PRACTICE.value: 2,  # 等待开始练习（同界面）
        }

        # 根据状态确定确认阈值
        confirm_threshold = FAST_CONFIRM_STATES.get(
            detected_state, self.confirm_threshold
        )

        # 如果是相同状态，快速确认（保留其他状态的累积计数）
        if detected_state == self.current_state:
            self.state_confirm_counter[detected_state] = confirm_threshold
            return detected_state, True

        # 关键状态立即确认（匹配成功弹窗需要快速响应，但仅限层级检测）
        # deep检测置信度低容易误报，不允许立即确认
        IMMEDIATE_CONFIRM_STATES = [
            GameState.MATCH_FOUND.value,  # 匹配成功弹窗持续时间有限
            GameState.MATCH_CONFIRMED.value,  # 匹配已确认状态
        ]
        if (
            detected_state in IMMEDIATE_CONFIRM_STATES
            and strategy != DetectionLevel.DEEP
        ):
            self.state_confirm_counter.clear()
            return detected_state, True

        # 增加新状态计数
        count = self.state_confirm_counter.get(detected_state, 0) + 1
        self.state_confirm_counter[detected_state] = count

        # 达到阈值才切换
        if count >= confirm_threshold:
            if detected_state == GameState.UNKNOWN.value:
                # UNKNOWN达到阈值时，只清除UNKNOWN自己的计数，保留其他状态的累积计数
                # 避免深度检测慢慢积累的有效状态计数被UNKNOWN清零
                self.state_confirm_counter.pop(detected_state, None)
            else:
                self.state_confirm_counter.clear()
            return detected_state, True

        # 保持当前状态，等待确认
        return self.current_state, False

    def _handle_unknown_state(self, img_gray) -> str:
        """
        处理未知状态 - 弹窗处理

        参数说明:
            img_gray: 灰度图像，用于弹窗检测

        返回值:
            str: 处理后的状态名

        功能描述:
            当状态为UNKNOWN时，尝试通过弹窗处理恢复已知状态。
            达到未知状态阈值后才触发弹窗处理，避免频繁处理。
        """
        # 增加连续未知状态计数
        self.context.consecutive_unknown += 1

        # 达到阈值才处理弹窗
        if self.context.consecutive_unknown < self.unknown_threshold:
            return self.current_state

        logger.info(
            f"\n⚠️ 未知状态持续 {self.context.consecutive_unknown} 帧，触发弹窗处理"
        )

        # 执行弹窗处理
        success, depth = self.popup_handler.handle_unknown_state(img_gray)

        if success:
            # 弹窗处理成功
            self.stats["popup_handles"] += 1
            logger.info(f"✅ 弹窗处理完成，共处理 {depth} 层")
            self.context.consecutive_unknown = 0
            # 返回unknown让下次检测重新识别
            return GameState.UNKNOWN.value
        else:
            # 弹窗处理失败，也重置计数器，让新界面重新累积
            logger.info(f"❌ 弹窗处理未能恢复已知状态")
            self.context.consecutive_unknown = 0
            return GameState.UNKNOWN.value

    def _transition_state(
        self, new_state: str, confidence: float, strategy: DetectionLevel
    ):
        """
        执行状态切换

        参数说明:
            new_state: 新状态名称
            confidence: 检测置信度
            strategy: 使用的检测策略

        功能描述:
            执行状态切换的日志记录和可视化更新。
            输出状态切换信息和流程进度。
        """
        old_state = self.current_state

        # 重置未知状态计数
        if new_state != GameState.UNKNOWN.value:
            self.context.consecutive_unknown = 0

        # 获取状态描述
        old_desc = get_state_description(old_state)
        new_desc = get_state_description(new_state)

        # 输出状态切换日志
        logger.info(f"\n✅ 状态确认切换")
        logger.info(f"  {old_state} ({old_desc})")
        logger.info(f"  → {new_state} ({new_desc})")
        logger.info(f"  置信度: {confidence:.2f}, 策略: {strategy.value}")

        # 打印流程进度
        progress = self.visualizer.get_flow_progress()
        if progress.percentage > 0:
            logger.info(
                f"  流程进度: {progress.percentage:.1f}% ({progress.current_index}/{progress.total_states})"
            )

    def force_detect_state(self, img_gray) -> DetectionResult:
        """
        强制检测当前状态（无视当前状态，用于未知状态恢复）

        参数说明:
            img_gray: 灰度图像，用于模板匹配

        返回值:
            DetectionResult: 检测结果对象

        功能描述:
            强制执行深度检测来确定当前状态，不经过防抖确认。
            用于未知状态恢复等特殊场景。
        """
        logger.info("\n🔄 强制深度检测...")

        # 使用深度检测策略
        deep = DeepDetectionStrategy()
        result = deep.detect(img_gray, self.template_matcher, {})

        if result:
            # 深度检测成功
            state, confidence = result
            strategy = DetectionLevel.DEEP
        else:
            # 深度检测失败，返回未知状态
            confidence = 0.0
            strategy = DetectionLevel.NORMAL
            state = GameState.UNKNOWN.value

        # 直接切换状态（不经过确认）
        if state != self.current_state:
            self._transition_state(state, confidence, strategy)
            self.current_state = state

        # 返回检测结果
        return DetectionResult(
            state=state,
            confidence=confidence,
            strategy=strategy,
            timestamp=time.time(),
            is_confirmed=True,
        )

    def get_state_confidence(self, state: str, img_gray) -> float:
        """
        获取指定状态的置信度

        参数说明:
            state: 状态名称
            img_gray: 灰度图像，用于模板匹配

        返回值:
            float: 该状态的检测置信度（0.0-1.0）

        功能描述:
            检测指定状态的所有主要模板，返回最高置信度。
            用于判断当前是否可能处于该状态。
        """
        try:
            # 将字符串转换为GameState枚举
            state_enum = GameState(state)
            # 获取该状态的特征签名
            signature = STATE_SIGNATURES.get(state_enum)

            if not signature:
                return 0.0

            # 检测所有主要模板，获取最高置信度
            max_confidence = 0.0
            for template in signature.primary_templates:
                result = self.template_matcher.detect(template, img_gray)
                if result.found and result.confidence > max_confidence:
                    max_confidence = result.confidence

            return max_confidence

        except ValueError:
            # 状态名称无效，返回0
            return 0.0

    def is_in_state(self, state: str, img_gray, min_confidence: float = 0.7) -> bool:
        """
        检查是否处于指定状态

        参数说明:
            state: 状态名称
            img_gray: 灰度图像，用于模板匹配
            min_confidence: 最小置信度阈值，默认0.7

        返回值:
            bool: 如果处于该状态返回True，否则返回False

        功能描述:
            检查当前画面是否匹配指定状态，通过比较置信度和阈值判断。
        """
        # 获取状态的置信度
        confidence = self.get_state_confidence(state, img_gray)
        # 判断置信度是否达到阈值
        return confidence >= min_confidence

    def get_status_report(self) -> str:
        """
        获取状态报告

        返回值:
            str: 格式化的状态报告字符串

        功能描述:
            生成状态检测器的运行报告，包含当前状态、检测统计、
            策略命中率、弹窗处理次数和最近状态转换历史。
        """
        # 获取总检测次数，避免除零
        total = self.stats["total_detections"]
        if total == 0:
            total = 1

        # 构建报告字符串
        report = f"""
{"=" * 70}
状态检测器运行报告
{"=" * 70}
当前状态: {self.current_state} ({get_state_description(self.current_state)})
当前流程: {self.visualizer.current_flow}
总检测次数: {self.context.frame_count}

检测策略命中率:
  层级检测: {self.stats["normal_hits"]} ({self.stats["normal_hits"] / total * 100:.1f}%)
  深度检测: {self.stats["deep_hits"]} ({self.stats["deep_hits"] / total * 100:.1f}%)
  紧急检测: {self.stats["emergency_hits"]} ({self.stats["emergency_hits"] / total * 100:.1f}%)
  未知状态: {self.stats["unknown_hits"]} ({self.stats["unknown_hits"] / total * 100:.1f}%)

弹窗处理:
  处理次数: {self.stats["popup_handles"]}
  {self.popup_handler.get_processed_summary()}

最近状态转换历史:
"""
        # 添加最近5条状态转换历史记录
        for i, trans in enumerate(list(self.visualizer.history)[-5:], 1):
            time_str = time.strftime("%H:%M:%S", time.localtime(trans.timestamp))
            report += f"  {i}. [{time_str}] {trans.from_state} → {trans.to_state}\n"

        report += f"{'=' * 70}"
        return report

    def print_status(self):
        """
        打印当前状态

        功能描述:
            输出当前状态的简要信息到日志，包括状态名、描述、
            流程、置信度和进度。
        """
        logger.info(f"\n当前状态: {self.current_state}")
        logger.info(f"  描述: {get_state_description(self.current_state)}")
        logger.info(f"  流程: {self.visualizer.current_flow}")
        logger.info(f"  置信度: {self.last_confidence:.2f}")

        # 输出流程进度
        progress = self.visualizer.get_flow_progress()
        if progress.percentage > 0:
            logger.info(f"  进度: {progress.percentage:.1f}%")

    def force_state(self, state: str):
        """
        强制设置状态（用于调试）

        参数说明:
            state: 目标状态名称

        功能描述:
            强制将当前状态设置为指定值，用于调试和测试。
            会更新状态确认计数器和可视化。
        """
        logger.info(f"⚡ 强制设置状态: {self.current_state} → {state}")
        old_state = self.current_state
        self.current_state = state
        # 设置状态确认计数器，使状态立即确认
        self.state_confirm_counter = {state: self.confirm_threshold}
        # 重置未知状态计数
        self.context.consecutive_unknown = 0

        # 更新可视化
        flow = get_state_flow(state)
        self.visualizer.update(state, flow, 1.0, trigger="force")

    def reset(self):
        """
        重置检测器

        功能描述:
            重置检测器到初始状态，包括当前状态、上下文、
            计数器、弹窗处理器、可视化器和统计数据。
        """
        # 重置核心状态
        self.current_state = GameState.UNKNOWN.value
        self.context = DetectionContext()
        self.state_confirm_counter.clear()

        # 重置子模块
        self.popup_handler.reset()
        self.visualizer.reset()

        # 重置统计数据
        self.stats = {
            "total_detections": 0,
            "normal_hits": 0,
            "deep_hits": 0,
            "emergency_hits": 0,
            "unknown_hits": 0,
            "popup_handles": 0,
        }

        logger.info("🔄 检测器已重置")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        返回值:
            Dict[str, Any]: 包含各种统计信息的字典

        功能描述:
            返回检测器的统计信息，包括检测次数、当前状态、
            流程、帧数和连续未知状态数。
        """
        return {
            **self.stats,
            "current_state": self.current_state,
            "current_flow": self.visualizer.current_flow,
            "frame_count": self.context.frame_count,
            "consecutive_unknown": self.context.consecutive_unknown,
        }
