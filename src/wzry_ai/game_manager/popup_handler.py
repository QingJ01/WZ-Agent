# -*- coding: utf-8 -*-
"""
弹窗处理器模块 - 处理未知状态下的弹窗

功能说明：
- 检测并处理游戏中的各类弹窗（关闭按钮、确认按钮等）
- 支持多层弹窗的递归处理
- 记录处理历史用于调试分析

参数说明：
- template_matcher: 模板匹配器实例
- click_executor: 点击执行器实例
- max_depth: 最大递归深度

返回值说明：
- 各方法返回bool表示处理是否成功，或返回处理统计信息
"""

import time  # 导入时间模块，用于控制点击间隔和记录时间戳
from typing import Tuple, List, Optional, Dict, Any  # 导入类型提示工具
from dataclasses import dataclass  # 导入数据类装饰器，用于创建简洁的数据结构

try:
    from wzry_ai.config import (
        TEMPLATE_CONFIDENCE_THRESHOLDS,  # 各模板的置信度阈值配置
        DEFAULT_TEMPLATE_CONFIDENCE,  # 默认置信度阈值
        POPUP_DETECTION_THRESHOLD,  # 弹窗检测阈值
    )
except ImportError:  # 如果导入失败，使用默认值
    TEMPLATE_CONFIDENCE_THRESHOLDS = {}  # 空字典作为默认值
    DEFAULT_TEMPLATE_CONFIDENCE = 0.8  # 默认置信度0.8
    POPUP_DETECTION_THRESHOLD = 0.7  # 默认检测阈值0.7

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)  # 获取当前模块的日志记录器


@dataclass
class PopupAction:
    """
    弹窗处理动作数据类 - 定义如何处理特定弹窗

    参数说明：
    - template: 检测模板名称，用于识别弹窗
    - action_type: 动作类型，可选'click'(点击)、'click_return'(返回点击)、'wait'(等待)
    - description: 动作描述，用于日志输出
    - confidence_threshold: 置信度阈值，None则从config读取
    - max_retries: 最大重试次数
    - cooldown: 执行后冷却时间（秒）

    功能描述：
    封装处理单个弹窗所需的所有配置信息
    """

    template: str  # 检测模板名称，对应模板文件
    action_type: str  # 动作类型: 'click', 'click_return', 'wait'
    description: str  # 动作描述，用于日志显示
    confidence_threshold: Optional[float] = None  # 置信度阈值（None则从config读取）
    max_retries: int = 3  # 最大重试次数
    cooldown: float = 0.3  # 执行后冷却时间（秒）

    def __post_init__(self):
        """
        初始化后从config读取阈值

        功能描述：
        如果未指定置信度阈值，则从全局配置中查找对应模板的阈值
        """
        if self.confidence_threshold is None:  # 如果阈值未指定
            configured_value = TEMPLATE_CONFIDENCE_THRESHOLDS.get(
                self.template,
                POPUP_DETECTION_THRESHOLD,  # 从配置读取，不存在则使用默认值
            )
            if isinstance(configured_value, dict):
                threshold = configured_value.get("threshold", POPUP_DETECTION_THRESHOLD)
                self.confidence_threshold = (
                    threshold
                    if isinstance(threshold, (int, float))
                    else POPUP_DETECTION_THRESHOLD
                )
            elif isinstance(configured_value, (int, float)):
                self.confidence_threshold = float(configured_value)
            else:
                self.confidence_threshold = POPUP_DETECTION_THRESHOLD


class PopupHandler:
    """
    弹窗处理器类 - 处理未知状态下的各类弹窗

    参数说明：
    - template_matcher: 模板匹配器实例，用于检测弹窗
    - click_executor: 点击执行器实例，用于点击处理弹窗
    - max_depth: 最大递归深度，用于处理多层弹窗嵌套

    功能描述：
    1. 按优先级顺序检测并处理各类弹窗
    2. 支持多层弹窗的递归处理
    3. 记录处理历史便于调试
    4. 防止重复点击造成问题
    """

    # 弹窗处理优先级队列（按优先级排序）
    # 置信度阈值从 config.py 的 TEMPLATE_CONFIDENCE_THRESHOLDS 读取
    POPUP_ACTIONS = [
        # ========== 最高优先级：防沉迷弹窗 ==========
        PopupAction("rest_confirm", "click", "防沉迷确认按钮"),
        # ========== 最高优先级：关闭按钮 ==========
        PopupAction("close1", "click", "关闭按钮-蓝色背景版本"),
        PopupAction("close2", "click", "关闭按钮-细线条版本"),
        PopupAction("close3", "click", "关闭按钮-粗线条圆角版本"),
        PopupAction("close4", "click", "关闭按钮-标准白色X"),
        # ========== 中优先级：返回按钮 ==========
        PopupAction("return_room", "click", "返回房间按钮"),
        PopupAction("return_btn", "click", "返回按钮"),
        PopupAction("Match_Statistics", "click", "比赛统计按钮"),
        # ========== 中优先级：确认按钮 ==========
        PopupAction("confirm", "click", "确认按钮"),
        PopupAction("confirm1", "click", "确认按钮样式1"),
        PopupAction("confirm2", "click", "确认按钮样式2"),
        # ========== 低优先级：继续按钮 ==========
        PopupAction("continue", "click", "继续按钮"),
    ]

    def __init__(self, template_matcher, click_executor, max_depth: int = 6):
        """
        初始化弹窗处理器

        参数说明：
        - template_matcher: 模板匹配器，用于检测弹窗模板
        - click_executor: 点击执行器，用于执行点击操作
        - max_depth: 最大递归深度，处理多层弹窗时的最大层数

        功能描述：
        初始化处理器，保存依赖组件，设置处理记录和防重复点击机制
        """
        self.template_matcher = template_matcher  # 保存模板匹配器引用
        self.click_executor = click_executor  # 保存点击执行器引用
        self.max_depth = max_depth  # 保存最大递归深度

        # 处理记录
        self.processed_popups: List[Dict] = []  # 初始化已处理弹窗列表
        self.unknown_state_counter = 0  # 初始化未知状态计数器

        # 防重复点击
        self.last_click_time = 0  # 初始化上次点击时间
        self.click_cooldown = 1.0  # 设置点击冷却时间为1秒

        logger.info(f"初始化完成，最大处理深度: {max_depth}")  # 记录初始化完成日志

    def handle_unknown_state(
        self, img_gray, current_depth: int = 0
    ) -> Tuple[bool, int]:
        """
        处理未知状态 - 递归检测并处理弹窗

        参数说明：
        - img_gray: 灰度图像数据，用于模板匹配
        - current_depth: 当前递归深度，从0开始

        返回值：
        - Tuple[bool, int]: (是否成功处理, 处理的弹窗数量/当前深度)

        功能描述：
        递归检测并处理弹窗，支持多层弹窗嵌套，每层处理后等待界面响应
        """
        if current_depth >= self.max_depth:  # 如果达到最大递归深度
            logger.warning(
                f"达到最大递归深度 {self.max_depth}，停止处理"
            )  # 记录警告日志
            return False, current_depth  # 返回失败和当前深度

        # 检查点击冷却
        now = time.time()  # 获取当前时间
        if (
            now - self.last_click_time < self.click_cooldown
        ):  # 如果距离上次点击时间小于冷却时间
            time.sleep(
                self.click_cooldown - (now - self.last_click_time)
            )  # 等待剩余冷却时间

        logger.info(
            f"未知状态处理 - 第 {current_depth + 1}/{self.max_depth} 层"
        )  # 记录当前处理层数

        # 1. 尝试检测并处理弹窗
        popup_found, action_taken = self._try_handle_popup(
            img_gray
        )  # 调用弹窗检测处理方法

        if not popup_found:  # 如果没有找到弹窗
            logger.info("未检测到可处理弹窗，尝试点击屏幕中心...")  # 记录日志
            # 尝试点击屏幕中心（处理无按钮的遮挡界面）
            success = self._click_screen_center(img_gray)  # 点击屏幕中心
            if success:  # 如果点击成功
                logger.info("已点击屏幕中心")  # 记录成功日志
                return True, current_depth + 1  # 返回成功和下一层深度
            return False, current_depth  # 返回失败和当前深度

        # 2. 记录处理
        self.processed_popups.append(
            {  # 将处理记录添加到列表
                "depth": current_depth,  # 记录当前深度
                "action": action_taken,  # 记录执行的动作
                "timestamp": time.time(),  # 记录处理时间戳
            }
        )

        # 3. 等待弹窗动画/界面响应
        logger.info(f"等待界面响应...")  # 记录等待日志
        if action_taken is None:
            return False, current_depth
        time.sleep(action_taken.cooldown)  # 等待配置的冷却时间

        # 4. 返回成功，由调用者决定是否需要继续检测（需要重新获取帧）
        logger.info(f"第 {current_depth + 1} 层处理完成")  # 记录完成日志
        return True, current_depth + 1  # 返回成功和下一层深度

    def _try_handle_popup(self, img_gray) -> Tuple[bool, Optional[PopupAction]]:
        """
        尝试处理单个弹窗

        参数说明：
        - img_gray: 灰度图像数据

        返回值：
        - Tuple[bool, Optional[PopupAction]]: (是否找到弹窗, 执行的动作对象)

        功能描述：
        按优先级顺序遍历弹窗动作列表，检测并处理第一个匹配的弹窗
        """
        for action in self.POPUP_ACTIONS:  # 遍历所有弹窗动作配置
            result = self.template_matcher.detect(  # 使用模板匹配器检测
                action.template,  # 模板名称
                img_gray,  # 灰度图像
                min_confidence=action.confidence_threshold,  # 使用配置的置信度阈值
            )

            if result.found:  # 如果检测到弹窗
                logger.info(
                    f"检测到弹窗: {action.description} "
                    f"(置信度: {result.confidence:.2f})"
                )  # 记录检测信息

                # 执行点击
                success = self._execute_action(action, result)  # 调用动作执行方法

                if success:  # 如果执行成功
                    self.last_click_time = time.time()  # 更新上次点击时间
                    logger.info(f"已处理: {action.description}")  # 记录成功日志
                    return True, action  # 返回成功和动作对象
                else:  # 如果执行失败
                    logger.error(f"处理失败: {action.description}")  # 记录错误日志

        return False, None  # 没有找到弹窗，返回失败

    def _execute_action(self, action: PopupAction, match_result) -> bool:
        """
        执行弹窗动作

        参数说明：
        - action: 弹窗动作配置对象
        - match_result: 模板匹配结果对象，包含位置和大小信息

        返回值：
        - bool: 动作是否执行成功

        功能描述：
        根据动作类型执行相应的操作（点击、等待等）
        """
        try:  # 尝试执行动作
            x, y = match_result.location  # 获取匹配位置的左上角坐标
            w, h = match_result.size  # 获取匹配区域的宽高

            # 计算点击位置（中心点）
            click_x = x + w // 2  # 中心点X坐标
            click_y = y + h // 2  # 中心点Y坐标

            if action.action_type == "click":  # 如果是普通点击类型
                # 普通点击（关闭/确认按钮）
                logger.info(f"点击位置: ({click_x}, {click_y})")  # 记录点击位置
                return self.click_executor.click(click_x, click_y)  # 执行点击并返回结果

            elif action.action_type == "click_return":  # 如果是返回点击类型
                # 返回按钮点击
                logger.info(f"点击返回: ({click_x}, {click_y})")  # 记录返回点击
                return self.click_executor.click(click_x, click_y)  # 执行点击并返回结果

            elif action.action_type == "wait":  # 如果是等待类型
                # 等待
                logger.info(f"等待 {action.cooldown} 秒")  # 记录等待时间
                time.sleep(action.cooldown)  # 执行等待
                return True  # 等待成功返回True

        except (AttributeError, OSError, RuntimeError) as e:  # 捕获所有异常
            logger.error(f"执行动作失败: {e}", exc_info=True)  # 记录错误日志
            return False  # 返回失败

        return False  # 默认返回失败

    def _click_screen_center(self, img_gray) -> bool:
        """
        点击屏幕中心位置（处理无按钮的遮挡界面）

        参数说明：
        - img_gray: 灰度图像数据

        返回值：
        - bool: 点击是否成功

        功能描述：
        计算图像中心点坐标并执行点击，用于处理没有明确按钮的遮挡界面
        """
        try:  # 尝试点击
            h, w = img_gray.shape[:2]  # 获取图像高度和宽度
            center_x = w // 2  # 计算中心点X坐标
            center_y = h // 2  # 计算中心点Y坐标

            logger.info(f"点击屏幕中心: ({center_x}, {center_y})")  # 记录点击位置
            success = self.click_executor.click(center_x, center_y)  # 执行点击

            if success:  # 如果点击成功
                self.last_click_time = time.time()  # 更新上次点击时间

            return success  # 返回点击结果

        except (AttributeError, OSError, RuntimeError) as e:  # 捕获异常
            logger.error(f"点击屏幕中心失败: {e}", exc_info=True)  # 记录错误日志
            return False  # 返回失败

    def quick_check_popup(self, img_gray) -> Tuple[bool, str]:
        """
        快速检查是否有弹窗（不处理）

        参数说明：
        - img_gray: 灰度图像数据

        返回值：
        - Tuple[bool, str]: (是否有弹窗, 弹窗类型描述)

        功能描述：
        快速检测是否存在弹窗，只检查前5个高优先级动作（通常是关闭按钮），不执行任何操作
        """
        for action in self.POPUP_ACTIONS[:5]:  # 只检查前5个高优先级动作（关闭按钮）
            result = self.template_matcher.detect(  # 检测模板
                action.template,  # 模板名称
                img_gray,  # 灰度图像
                min_confidence=action.confidence_threshold,  # 使用配置的阈值
            )
            if result.found:  # 如果检测到弹窗
                return True, action.description  # 返回True和弹窗描述

        return False, ""  # 没有检测到弹窗，返回False和空字符串

    def get_processed_summary(self) -> str:
        """
        获取处理摘要

        返回值：
        - str: 处理摘要文本，包含处理的弹窗数量和详细信息

        功能描述：
        生成已处理弹窗的汇总信息，用于日志输出和调试
        """
        if not self.processed_popups:  # 如果没有处理过弹窗
            return "未处理任何弹窗"  # 返回提示信息

        summary = f"共处理 {len(self.processed_popups)} 个弹窗:\n"  # 构建摘要开头
        for i, popup in enumerate(self.processed_popups, 1):  # 遍历所有处理的弹窗
            action = popup["action"]  # 获取动作对象
            summary += f"  {i}. 第{popup['depth'] + 1}层: {action.description}\n"  # 添加每条记录

        return summary  # 返回完整摘要

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        返回值：
        - Dict: 包含处理总数、最大深度、未知状态计数等统计信息的字典

        功能描述：
        返回弹窗处理的统计数据，用于性能分析和调试
        """
        return {
            "total_processed": len(self.processed_popups),  # 处理弹窗总数
            "max_depth_reached": max([p["depth"] for p in self.processed_popups])
            if self.processed_popups
            else 0,  # 达到的最大深度
            "unknown_state_counter": self.unknown_state_counter,  # 未知状态计数
        }

    def reset(self):
        """
        重置处理器状态

        功能描述：
        清空处理记录，重置计数器和时间戳，恢复到初始状态
        """
        self.processed_popups.clear()  # 清空已处理弹窗列表
        self.unknown_state_counter = 0  # 重置未知状态计数器
        self.last_click_time = 0  # 重置上次点击时间
        logger.info("状态已重置")  # 记录重置日志
