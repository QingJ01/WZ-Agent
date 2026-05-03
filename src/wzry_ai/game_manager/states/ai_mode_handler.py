# -*- coding: utf-8 -*-
"""
人机模式状态处理器 - 处理模式和难度的自动选择

功能说明：
- 比对人机模式/难度与配置是否匹配
- 自动点击切换模式或难度
- 确认配置正确后才允许进入下一步

参数说明：
- click_executor: 点击执行器实例
- template_matcher: 模板匹配器实例

返回值说明：
- check_and_adjust方法返回bool表示配置是否正确
"""

from typing import Optional, Dict, Any, Tuple  # 导入类型提示工具

from wzry_ai.utils.logging_utils import get_logger  # 导入日志工具

logger = get_logger(__name__)

try:
    from wzry_ai.config import (
        GAME_MODE,
        BATTLE_MODE,
        V5_MODE,
        AI_BATTLE_MODE,
        AI_DIFFICULTY,
        TEMPLATE_ROI,
    )  # 导入配置
except ImportError:
    # 提供默认值
    GAME_MODE = "battle"  # 默认游戏模式为对战
    BATTLE_MODE = "5v5"  # 默认地图模式为5v5
    V5_MODE = "ai"  # 默认匹配类型为人机
    AI_BATTLE_MODE = "standard"  # 默认游戏模式为标准模式
    AI_DIFFICULTY = "bronze"  # 默认难度为青铜
    TEMPLATE_ROI = {}  # 默认ROI配置为空字典


class AIModeHandler:
    """
    人机模式处理器类 - 处理人机对战模式和难度的自动选择

    参数说明：
    - click_executor: 点击执行器实例，用于执行点击操作
    - template_matcher: 模板匹配器实例，用于检测界面元素

    功能描述：
    1. 比对当前选中模式/难度与配置是否匹配
    2. 执行点击切换操作
    3. 确认配置正确后才允许进入下一步
    """

    # 游戏模式映射：配置键 -> 显示名称
    GAME_MODE_MAP = {
        "battle": "对战",
        "ranking": "排位",
    }

    # 地图模式映射：配置键 -> 显示名称
    BATTLE_MODE_MAP = {
        "5v5": "5V5王者峡谷",
        "3v3": "3V3长平攻防战",
        None: "普通对战",
    }

    # 匹配类型映射：配置键 -> 显示名称
    V5_MODE_MAP = {
        "match": "匹配",
        "ai": "人机",
    }

    # 游戏模式映射：配置键 -> 显示名称
    MODE_MAP = {
        "standard": "标准模式",
        "quick": "快速模式",
    }

    # 难度映射：配置键 -> 显示名称
    DIFFICULTY_MAP = {
        "recommend": "推荐",
        "bronze": "青铜",
        "gold": "黄金",
        "diamond": "钻石",
        "star": "星耀",
        "master": "王者",
    }

    # 模板映射：模式名称 -> 模板名称（用于点击未选中的选项）
    MODE_TEMPLATES = {
        "标准模式": "ai_standard",
        "快速模式": "ai_quick",
    }

    # 难度模板映射：难度名称 -> 模板名称（用于点击未选中的选项）
    DIFFICULTY_TEMPLATES = {
        "推荐": "ai_recommend",
        "青铜": "ai_bronze",
        "黄金": "ai_gold",
        "钻石": "ai_diamond",
        "星耀": "ai_star",
        "王者": "ai_master",
    }

    def __init__(self, click_executor, template_matcher):
        """
        初始化人机模式处理器

        参数说明：
        - click_executor: 点击执行器，用于执行点击操作
        - template_matcher: 模板匹配器，用于检测界面上的模式和难度选项

        功能描述：
        从配置中读取目标模式和难度，初始化状态变量，并打印目标配置信息
        """
        self.click_executor = click_executor  # 保存点击执行器引用
        self.template_matcher = template_matcher  # 保存模板匹配器引用

        # 目标配置 - 从配置文件中读取并转换为显示名称
        self.target_game_mode = self.GAME_MODE_MAP.get(
            GAME_MODE, "对战"
        )  # 目标游戏模式
        self.target_battle_mode = self.BATTLE_MODE_MAP.get(
            BATTLE_MODE, "未知"
        )  # 目标地图模式
        self.target_v5_mode = self.V5_MODE_MAP.get(V5_MODE, "未知")  # 目标匹配类型
        self.target_mode = self.MODE_MAP.get(
            AI_BATTLE_MODE
        )  # 目标游戏模式（标准/快速）
        self.target_difficulty = self.DIFFICULTY_MAP.get(AI_DIFFICULTY)  # 目标难度

        # 状态标志
        self.mode_correct = False  # 模式是否正确
        self.difficulty_correct = False  # 难度是否正确
        self.last_check_time = 0  # 上次检查时间戳
        self.check_interval = 0.5  # 检查间隔（秒），防止检查过于频繁

        # 显示完整目标配置
        logger.info(
            f"目标配置: 模式={self.target_game_mode}, 地图={self.target_battle_mode}, "
            f"匹配={self.target_v5_mode}, 游戏模式={self.target_mode}, 难度={self.target_difficulty}"
        )

    def check_and_adjust(self, context: Dict[str, Any], img_gray) -> bool:
        """
        检查并调整模式/难度

        参数说明：
        - context: 检测上下文字典，包含ai_selected_mode（当前选中模式）、ai_selected_difficulty（当前选中难度）等
        - img_gray: 灰度图像数据，用于模板匹配

        返回值：
        - bool: True表示配置正确可以进行下一步，False表示需要调整

        功能描述：
        检查当前选中的模式和难度是否与目标配置匹配，如果不匹配则自动点击切换
        """
        import time  # 导入时间模块

        # 限制检查频率
        current_time = time.time()  # 获取当前时间
        if (
            current_time - self.last_check_time < self.check_interval
        ):  # 如果距离上次检查时间小于间隔
            return (
                self.mode_correct and self.difficulty_correct
            )  # 直接返回当前状态，不重复检查
        self.last_check_time = current_time  # 更新上次检查时间

        # 获取当前选中的模式和难度
        current_mode = context.get("ai_selected_mode")  # 从上下文中获取当前模式
        current_difficulty = context.get(
            "ai_selected_difficulty"
        )  # 从上下文中获取当前难度
        actual_difficulty = context.get("ai_actual_difficulty")  # 获取实际难度（备用）

        logger.debug(
            f"检查配置: 当前模式={current_mode}, 目标模式={self.target_mode}, "
            f"当前难度={current_difficulty}, 目标难度={self.target_difficulty}"
        )

        if not current_mode:  # 如果没有检测到当前模式
            logger.warning("未检测到当前模式")
            return False  # 返回失败

        # 检查模式
        if current_mode == self.target_mode:  # 如果当前模式与目标匹配
            logger.info(f"模式匹配: {current_mode}")
            self.mode_correct = True  # 设置模式正确标志
        else:  # 如果模式不匹配
            logger.info(
                f"模式不匹配: 当前={current_mode}, 目标={self.target_mode}, 准备点击切换"
            )
            self.mode_correct = False  # 设置模式不正确标志
            if self.target_mode is None:
                logger.warning("目标模式配置未知，无法切换")
                return False
            self._click_mode(self.target_mode, img_gray)  # 调用方法点击切换模式
            return False  # 返回失败，需要再次检查

        # 检查难度
        # 获取所有检测到的难度（用于推荐难度的双重高亮处理）
        all_difficulties = context.get("all_detected_difficulties", [])

        # 如果目标是推荐，检查推荐是否被选中
        if AI_DIFFICULTY == "recommend":  # 如果配置为推荐难度
            if current_difficulty == "推荐":  # 如果当前选中的是推荐
                logger.info("难度匹配: 推荐")
                self.difficulty_correct = True  # 设置难度正确标志
            else:  # 如果当前不是推荐
                logger.info(
                    f"难度不匹配: 当前={current_difficulty}, 目标=推荐, 准备点击切换"
                )
                self.difficulty_correct = False  # 设置难度不正确标志
                self._click_difficulty("推荐", img_gray)  # 点击切换到推荐
                return False  # 返回失败
        else:  # 如果目标是具体难度
            if current_difficulty == self.target_difficulty:  # 如果当前难度与目标匹配
                logger.info(f"难度匹配: {current_difficulty}")
                self.difficulty_correct = True  # 设置难度正确标志
            elif (
                current_difficulty == "推荐"
                and self.target_difficulty in all_difficulties
            ):
                # 推荐难度的双重高亮处理：当前显示"推荐"，但实际难度与目标匹配
                logger.info(f"推荐难度实际为{self.target_difficulty}，配置匹配")
                self.difficulty_correct = True  # 设置难度正确标志
            else:  # 如果难度不匹配
                logger.info(
                    f"难度不匹配: 当前={current_difficulty}, 目标={self.target_difficulty}, 准备点击切换"
                )
                self.difficulty_correct = False  # 设置难度不正确标志
                if self.target_difficulty is None:
                    logger.warning("目标难度配置未知，无法切换")
                    return False
                self._click_difficulty(
                    self.target_difficulty, img_gray
                )  # 点击切换到目标难度
                return False  # 返回失败

        # 配置正确
        logger.info(f"配置正确: {current_mode} | {current_difficulty}")
        return True  # 返回成功

    def _click_mode(self, mode_name: str, img_gray):
        """
        点击切换模式（使用模板匹配或ROI位置）

        参数说明：
        - mode_name: 模式名称（如"标准模式"、"快速模式"）
        - img_gray: 灰度图像数据，用于模板匹配

        功能描述：
        先尝试通过模板匹配找到模式按钮位置，如果失败则使用ROI配置中的固定位置进行点击
        """
        if mode_name not in self.MODE_TEMPLATES:  # 如果模式名称不在映射中
            logger.warning(f"未知模式: {mode_name}")
            return  # 直接返回

        template_name = self.MODE_TEMPLATES[mode_name]  # 获取对应的模板名称
        result = self.template_matcher.detect(template_name, img_gray)  # 检测模板

        if result.found:  # 如果模板匹配成功
            x, y = result.location  # 获取匹配位置
            w, h = result.size  # 获取匹配区域大小
            click_x = x + w // 2  # 计算中心点X坐标
            click_y = y + h // 2  # 计算中心点Y坐标
            logger.info(
                f"点击切换模式: {mode_name} (模板匹配位置: {click_x}, {click_y})"
            )
            self.click_executor.click(click_x, click_y)  # 执行点击
        else:  # 如果模板匹配失败
            # 模板匹配失败，使用ROI配置中的位置
            if template_name in TEMPLATE_ROI:  # 如果ROI配置中存在该模板
                roi = TEMPLATE_ROI[template_name]  # 获取ROI配置
                click_x = roi["x"] + roi["w"] // 2  # 计算中心点X坐标
                click_y = roi["y"] + roi["h"] // 2  # 计算中心点Y坐标
                logger.info(
                    f"点击切换模式: {mode_name} (ROI位置: {click_x}, {click_y})"
                )
                self.click_executor.click(click_x, click_y)  # 执行点击
            else:  # 如果ROI配置中也不存在
                logger.warning(f"未找到模式按钮模板: {template_name}，且无ROI配置")

    def _click_difficulty(self, difficulty_name: str, img_gray):
        """
        点击切换难度（使用模板匹配或ROI位置）

        参数说明：
        - difficulty_name: 难度名称（如"青铜"、"王者"等）
        - img_gray: 灰度图像数据，用于模板匹配

        功能描述：
        先尝试通过模板匹配找到难度按钮位置，如果失败则使用ROI配置中的固定位置进行点击
        """
        if difficulty_name not in self.DIFFICULTY_TEMPLATES:  # 如果难度名称不在映射中
            logger.warning(f"未知难度: {difficulty_name}")
            return  # 直接返回

        template_name = self.DIFFICULTY_TEMPLATES[difficulty_name]  # 获取对应的模板名称
        result = self.template_matcher.detect(template_name, img_gray)  # 检测模板

        if result.found:  # 如果模板匹配成功
            x, y = result.location  # 获取匹配位置
            w, h = result.size  # 获取匹配区域大小
            click_x = x + w // 2  # 计算中心点X坐标
            click_y = y + h // 2  # 计算中心点Y坐标
            logger.info(
                f"点击切换难度: {difficulty_name} (模板匹配位置: {click_x}, {click_y})"
            )
            self.click_executor.click(click_x, click_y)  # 执行点击
        else:  # 如果模板匹配失败
            # 模板匹配失败，使用ROI配置中的位置
            if template_name in TEMPLATE_ROI:  # 如果ROI配置中存在该模板
                roi = TEMPLATE_ROI[template_name]  # 获取ROI配置
                click_x = roi["x"] + roi["w"] // 2  # 计算中心点X坐标
                click_y = roi["y"] + roi["h"] // 2  # 计算中心点Y坐标
                logger.info(
                    f"点击切换难度: {difficulty_name} (ROI位置: {click_x}, {click_y})"
                )
                self.click_executor.click(click_x, click_y)  # 执行点击
            else:  # 如果ROI配置中也不存在
                logger.warning(f"未找到难度按钮模板: {template_name}，且无ROI配置")
