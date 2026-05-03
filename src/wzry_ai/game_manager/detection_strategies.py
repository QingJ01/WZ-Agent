"""检测策略模块 - 分层检测策略实现

功能说明:
    本模块实现了多种游戏界面状态检测策略，包括层级检测策略和深度检测策略。
    通过分层检测机制，先检测"母模式"确定大致界面类型，再检测"子模式"确定具体状态。

主要组件:
    - DetectionStrategy: 检测策略抽象基类
    - HierarchicalDetectionStrategy: 层级检测策略（母-子模式检测）
    - DeepDetectionStrategy: 深度检测策略（全量扫描）
    - DetectionStrategyFactory: 检测策略工厂
"""

# 导入抽象基类装饰器，用于定义抽象接口
from abc import ABC, abstractmethod

# 导入枚举类，用于定义检测级别
from enum import Enum

# 导入类型提示，用于声明列表和可选类型
from typing import List, Optional, TypeAlias

# 尝试从配置模块导入模板相关配置
try:
    from wzry_ai.config import (
        TEMPLATE_CONFIDENCE_THRESHOLDS,  # 各模板的置信度阈值配置
        DEFAULT_TEMPLATE_CONFIDENCE,  # 默认置信度阈值
        POPUP_DETECTION_THRESHOLD,  # 弹窗检测阈值
    )
except ImportError:
    # 如果导入失败，使用默认空配置
    TEMPLATE_CONFIDENCE_THRESHOLDS = {}  # 空字典表示无特定配置
    DEFAULT_TEMPLATE_CONFIDENCE = 0.8  # 默认置信度0.8
    POPUP_DETECTION_THRESHOLD = 0.7  # 弹窗检测默认阈值0.7

# 尝试从上级目录导入日志工具
from wzry_ai.utils.logging_utils import get_logger, ThrottledLogger

# 获取模块级日志记录器
logger = get_logger(__name__)
# 创建节流logger用于高频检测日志（每2秒最多输出一次，避免日志过多）
throttled_logger = ThrottledLogger(logger, interval=2.0)


# ========== 母-子模式层级检测配置 ==========

# 定义哪些母模式需要进行英雄头像检测
# 这些模式表示当前处于选英雄界面，需要额外检测英雄头像
HERO_AVATAR_PARENT_MODES = {"hero_select_main", "lane_select"}

# 技能验证配置（选英雄主界面和分路选择界面需要验证的英雄）
# 优先级英雄列表，用于技能图标验证
SKILL_VERIFICATION_HEROES = ["yao", "caiwenji", "mingshiyin"]
# 技能验证置信度阈值，高于此值认为技能验证通过
SKILL_VERIFICATION_THRESHOLD = 0.7

# 母模式到状态名的映射字典
# 将检测到的母模式名称转换为对应的游戏状态名称
PARENT_MODE_TO_STATE = {
    "simulator_desktop": "launcher",  # 模拟器桌面
    "server_select": "select_zone",  # 服务器选择
    "game_hall": "hall",  # 游戏大厅
    "battle_mode_select": "battle_mode_select",  # 对战模式选择
    "wangzhe_canyon": "battle_5v5_sub",  # 王者峡谷
    "ai_mode_select": "battle_ai_mode",  # 人机模式选择（含难度）
    "team_5v5_room": "battle_room",  # 组队房间（对战/排位通用）
    "ranking_match_select": "ranking_match_select",  # 排位赛模式选择
    "ranking_hero_select": "ranking_hero_select",  # 排位赛选英雄
    "match_confirmation": "match_found",  # 匹配成功弹窗
    "hero_select_main": "hero_select",  # 人机选英雄主界面
    "lane_select": "hero_select",  # 分路选择（也属于选英雄流程）
    "loading_screen": "game_loading_vs",  # 加载画面
    "game_result": "game_end",  # 游戏结果
    "mvp_settlement": "mvp_display",  # MVP结算
    "post_match_stats": "post_match_stats",  # 赛后数据
}

# 从状态定义模块导入状态特征映射表
from .state_definitions import STATE_SIGNATURES


def _get_template_confidence(template_name: str) -> float:
    """
    获取指定模板的置信度阈值

    参数说明:
        template_name: 模板名称字符串

    返回值:
        float: 该模板的置信度阈值，如果未配置则返回默认值

    功能描述:
        根据模板名称查询对应的置信度阈值，用于判断模板匹配是否成功
    """
    # 从配置字典中获取指定模板的置信度，如果不存在则返回默认值
    configured_value = TEMPLATE_CONFIDENCE_THRESHOLDS.get(
        template_name, DEFAULT_TEMPLATE_CONFIDENCE
    )
    if isinstance(configured_value, dict):
        threshold = configured_value.get("threshold", DEFAULT_TEMPLATE_CONFIDENCE)
        return (
            threshold
            if isinstance(threshold, (int, float))
            else DEFAULT_TEMPLATE_CONFIDENCE
        )
    return float(configured_value)


DetectionResult: TypeAlias = str | tuple[str, float]


class DetectionLevel(Enum):
    """
    检测级别枚举类

    功能说明:
        定义了不同级别的检测策略，用于控制检测的深度和精度。
        不同级别适用于不同场景，如正常检测、深度扫描等。

    枚举值:
        NORMAL: 普通检测级别，使用层级检测策略
        DEEP: 深度检测级别，扫描所有状态模板
        EMERGENCY: 紧急检测级别，用于异常恢复（预留）
    """

    NORMAL = "normal"  # 普通检测级别
    DEEP = "deep"  # 深度检测级别
    EMERGENCY = "emergency"  # 紧急检测级别


class DetectionStrategy(ABC):
    """
    检测策略抽象基类

    功能说明:
        定义了所有检测策略必须实现的接口。
        具体策略类需要继承此类并实现detect方法和level属性。

    抽象方法:
        detect: 执行状态检测的核心方法
        level: 返回策略级别的属性
    """

    @abstractmethod
    def detect(
        self, img_gray, template_matcher, context: dict
    ) -> Optional[DetectionResult]:
        """
        执行状态检测

        参数说明:
            img_gray: 灰度图像，用于模板匹配
            template_matcher: 模板匹配器对象，提供模板检测功能
            context: 上下文字典，用于存储检测过程中的额外信息

        返回值:
            Optional[DetectionResult]: 检测到的状态名称，或(状态名称, 置信度)元组；如果未检测到则返回None

        功能描述:
            子类必须实现此方法，根据具体策略检测当前游戏状态
        """
        pass

    @property
    @abstractmethod
    def level(self) -> DetectionLevel:
        """
        策略级别属性

        返回值:
            DetectionLevel: 该策略的检测级别

        功能描述:
            子类必须实现此属性，返回策略对应的检测级别
        """
        pass


class DeepDetectionStrategy(DetectionStrategy):
    """
    深度检测策略类

    功能说明:
        扫描所有状态签名中的模板，用于未知状态恢复。
        当层级检测无法确定状态时，使用此策略进行全量扫描。
        排除英雄头像等动态模板，只检测稳定的界面元素。

    使用场景:
        - 当前状态为UNKNOWN时进行恢复检测
        - 层级检测未能匹配到任何状态时作为备选方案
    """

    @property
    def level(self) -> DetectionLevel:
        """返回深度检测级别"""
        return DetectionLevel.DEEP

    def detect(
        self, img_gray, template_matcher, context: dict
    ) -> Optional[tuple[str, float]]:
        """
        扫描所有状态签名中的模板

        参数说明:
            img_gray: 灰度图像，用于模板匹配
            template_matcher: 模板匹配器对象
            context: 上下文字典（本策略未使用）

        返回值:
            Optional[tuple]: (检测到的状态名称, 置信度)，如果未检测到则返回None

        功能描述:
            收集所有状态签名中的主要模板，逐个进行检测，
            返回置信度最高的匹配结果对应的状态。
            使用较低的置信度阈值(0.3)先收集候选，
            然后验证候选状态的实际阈值和排除模板。
        """
        # 收集所有状态签名中的主要模板（不包括英雄头像等动态模板）
        state_templates = set()
        for signature in STATE_SIGNATURES.values():
            # 将每个状态的主要模板添加到集合中
            state_templates.update(signature.primary_templates)

        # 步骤1: 用较低阈值(0.3)检测所有模板，收集候选
        candidates = []  # 存储候选 (template_name, confidence)

        for template_name in state_templates:
            # 使用较低的置信度阈值(0.3)进行模板检测
            result = template_matcher.detect(
                template_name, img_gray, min_confidence=0.3
            )
            # 如果找到匹配，添加到候选列表
            if result.found:
                candidates.append((template_name, result.confidence))

        # 如果没有找到任何候选，返回None
        if not candidates:
            return None

        # 步骤2: 按置信度排序，从高到低检查
        candidates.sort(key=lambda x: x[1], reverse=True)

        # 步骤3: 对每个候选，检查其对应状态的阈值和排除模板
        for template_name, confidence in candidates:
            # 查找该模板对应的状态
            candidate_state = None
            candidate_signature = None

            for state, signature in STATE_SIGNATURES.items():
                if template_name in signature.primary_templates:
                    candidate_state = state
                    candidate_signature = signature
                    break

            if not candidate_state or not candidate_signature:
                continue

            # 获取该状态所需的置信度阈值（默认0.6）
            required_confidence = candidate_signature.required_confidence

            # 处理 required_confidence 可能为 dict 或其他非数值类型的情况
            if isinstance(required_confidence, dict):
                # 如果是字典，尝试获取 threshold 值，否则使用默认值
                required_confidence = required_confidence.get("threshold", 0.6)
            elif (
                not isinstance(required_confidence, (int, float))
                or required_confidence is None
            ):
                # 如果不是数值类型或为 None，使用默认值
                required_confidence = 0.6
            elif required_confidence == 0.0:
                required_confidence = 0.6  # 默认阈值

            # 检查置信度是否满足阈值
            if confidence < required_confidence:
                continue

            # 检查排除模板
            exclude_templates = candidate_signature.exclude_templates
            if exclude_templates:
                excluded = False
                for excl_tmpl in exclude_templates:
                    excl_result = template_matcher.detect(
                        excl_tmpl, img_gray, min_confidence=0.5
                    )
                    if excl_result.found:
                        logger.debug(
                            f"深度检测: 状态 {candidate_state.value} 被排除模板 {excl_tmpl} 排除 (conf={excl_result.confidence:.3f})"
                        )
                        excluded = True
                        break

                # 如果存在排除模板匹配，跳过此候选
                if excluded:
                    continue

            # 通过所有检查，返回该状态和实际置信度
            return (candidate_state.value, confidence)

        # 没有候选通过所有检查，返回None
        return None


class HierarchicalDetectionStrategy(DetectionStrategy):
    """
    母-子模式层级检测策略类

    功能说明:
        实现分层检测逻辑：先检测"母模式"确定大致界面类型，
        再检测"子模式"确定具体选项状态，最后进行英雄头像检测（如适用）。
        这是主要的检测策略，用于正常游戏流程中的状态识别。

    检测流程:
        1. 检测所有母模式，找到最佳匹配的界面类型
        2. 如果母模式有子模式，检测子模式确定具体选项
        3. 在选英雄界面进行英雄头像和技能验证
    """

    @property
    def level(self) -> DetectionLevel:
        """返回普通检测级别"""
        return DetectionLevel.NORMAL

    def __init__(self, current_state: Optional[str] = None):
        """
        初始化层级检测策略

        参数说明:
            current_state: 当前状态名称，用于上下文（当前未使用）
        """
        self.current_state = current_state

    def detect(self, img_gray, template_matcher, context: dict) -> Optional[str]:
        """
        执行层级检测

        参数说明:
            img_gray: 灰度图像，用于模板匹配
            template_matcher: 模板匹配器对象
            context: 上下文字典，用于存储检测过程中的额外信息

        返回值:
            Optional[str]: 检测到的状态名称，如果未检测到则返回None

        功能描述:
            执行三层检测流程：
            1. 检测所有母模式，找到置信度最高的匹配
            2. 如果母模式有子模式，检测子模式状态
            3. 在选英雄界面进行英雄头像和技能验证
        """
        # ========== 第一步：检测所有母模式 ==========
        best_parent = None  # 存储最佳匹配的母模式
        best_parent_confidence = 0.0  # 存储最佳匹配的置信度
        parent_result_details = {}  # 存储检测结果的详细信息

        # 组名映射表，用于日志显示中文名称
        GROUP_NAMES = {
            "simulator_desktop": "第一组-模拟器桌面",
            "server_select": "第二组-选区界面",
            "game_hall": "第三组-大厅界面",
            "battle_mode_select": "第四组-对战模式",
            "ranking_match_select": "第四组-排位赛模式选择界面（大厅点击排位按钮后进入）",
            "wangzhe_canyon": "第五组-王者峡谷界面",
            "ai_mode_select": "第六组-人机模式选择（含难度）",
            "team_5v5_room": "第七组-组队房间（对战/排位通用）",
            "match_confirmation": "第八组-匹配成功弹窗",
            "hero_select_main": "第十组-人机模式选英雄主界面",
            "lane_select": "第十一组-人机模式分路选择界面",
            "ranking_hero_select": "第十二组-排位赛选英雄界面",
            "loading_screen": "第十三组-加载界面",
            "game_result": "第十四组-胜利/失败",
            "mvp_settlement": "第十五组-MVP结算",
            "post_match_stats": "第十六组-赛后数据",
        }

        # 遍历所有配置的母模式进行检测
        group_idx = 0
        _all_debug_logs = []  # 收集所有检测日志，仅在全部失败时输出
        for parent_mode, config in TEMPLATE_CONFIDENCE_THRESHOLDS.items():
            group_idx += 1
            # 获取中文组名，如果没有则使用原始名称
            group_name = GROUP_NAMES.get(parent_mode, parent_mode)

            # 跳过非字典类型的配置项
            if not isinstance(config, dict):
                continue

            # 获取母模式的主模板
            parent_template = config.get("parent_template")
            if not parent_template:
                continue

            # 处理单个模板或模板列表的情况
            templates = (
                [parent_template]
                if isinstance(parent_template, str)
                else parent_template
            )
            # 获取该母模式的置信度阈值，默认使用全局默认值
            threshold = config.get("threshold", DEFAULT_TEMPLATE_CONFIDENCE)

            # 检测母模式的所有模板
            for template in templates:
                # 执行模板匹配
                result = template_matcher.detect(
                    template, img_gray, min_confidence=threshold
                )
                # 对关键模板输出调试日志
                if template in [
                    "wzry_icon",
                    "game_lobby",
                    "start_game",
                    "battle_mode",
                    "wangzhe_canyon",
                ]:
                    throttled_logger.debug(
                        f"[{group_name}] 检测 {template}: found={result.found}, conf={result.confidence:.3f}, threshold={threshold}"
                    )
                # 收集检测日志（延迟输出）
                if group_idx > 1:
                    _all_debug_logs.append(
                        f"[{group_name}] 检测 {template}: found={result.found}, conf={result.confidence:.3f}, threshold={threshold}"
                    )
                # 如果模板匹配成功
                if result.found and result.confidence > threshold:
                    # 检查是否有排除模板也在画面中
                    exclude_templates = config.get("exclude_templates", [])
                    if exclude_templates:
                        excluded = False
                        # 逐一检测排除模板
                        for excl_tmpl in exclude_templates:
                            excl_result = template_matcher.detect(
                                excl_tmpl, img_gray, min_confidence=0.70
                            )
                            if excl_result.found:
                                logger.info(
                                    f"  ⚠ 排除模板 {excl_tmpl} 匹配 (conf={excl_result.confidence:.3f})，跳过 {parent_mode}"
                                )
                                excluded = True
                                break
                        # 如果存在排除模板匹配，跳过此母模式
                        if excluded:
                            continue

                    # 更新最佳匹配
                    if result.confidence > best_parent_confidence:
                        best_parent_confidence = result.confidence
                        best_parent = parent_mode
                        parent_result_details = {
                            "template": template,
                            "confidence": result.confidence,
                            "location": result.location,
                        }
                    break  # 找到匹配的模板，跳出当前母模式的模板循环

        # 如果没有检测到任何母模式，输出所有失败的检测日志便于排查
        if not best_parent:
            for log_msg in _all_debug_logs:
                logger.debug(log_msg)
            return None

        # 输出检测到的母模式信息
        detected_group_name = GROUP_NAMES.get(best_parent, best_parent)
        logger.info(f"✓ {detected_group_name} (置信度: {best_parent_confidence:.3f})")

        # 获取母模式的详细配置
        parent_config = TEMPLATE_CONFIDENCE_THRESHOLDS.get(best_parent, {})
        sub_modes = parent_config.get("sub_modes")

        # ========== 第二步：如果母模式有子模式，检测子模式 ==========
        if sub_modes:
            # 存储所有检测到的子模式（亮态/已选中）
            detected_sub_modes = {}
            best_sub_mode = None
            best_sub_confidence = 0.0

            # 遍历所有子模式进行检测
            for sub_mode, sub_threshold in sub_modes.items():
                # 执行子模式模板检测
                result = template_matcher.detect(
                    sub_mode, img_gray, min_confidence=sub_threshold
                )
                # 判断子模式是否处于选中状态（高亮状态）
                is_selected = result.found and result.confidence > sub_threshold
                # 如果子模式被选中，记录到字典
                if is_selected:
                    detected_sub_modes[sub_mode] = result.confidence
                    if result.confidence > best_sub_confidence:
                        best_sub_confidence = result.confidence
                        best_sub_mode = sub_mode

            # 记录所有检测到的子模式到上下文
            if detected_sub_modes:
                # 子模式名称映射表，用于日志显示
                mode_names = {
                    "ai_standard": "标准模式",
                    "ai_quick": "快速模式",
                    "ai_recommend": "推荐",
                    "ai_bronze": "青铜",
                    "ai_gold": "黄金",
                    "ai_diamond": "钻石",
                    "ai_star": "星耀",
                    "ai_master": "王者",
                    "start_practice": "开始练习",
                }
                # 将检测到的子模式转换为中文名称
                selected_modes = [
                    mode_name
                    for k in detected_sub_modes.keys()
                    if (mode_name := mode_names.get(k, k)) is not None
                ]
                logger.info(f"已选中: {', '.join(selected_modes)}")
                # 保存到上下文供后续使用
                context["detected_sub_modes"] = detected_sub_modes
                context["sub_mode"] = best_sub_mode
                context["sub_mode_confidence"] = best_sub_confidence

        # ========== 第三步：英雄头像检测和技能验证 ==========
        # 只在选英雄主界面和分路选择界面进行英雄头像检测
        if best_parent in HERO_AVATAR_PARENT_MODES:
            # 标记启用英雄头像检测
            context["enable_hero_avatar_detection"] = True
            context["parent_mode"] = best_parent

            # 执行技能验证（检测优先级英雄的技能图标）
            verified_hero = None  # 存储验证通过的英雄
            verified_confidence = 0.0  # 存储验证的置信度

            # 遍历优先级英雄列表进行技能验证
            for hero_key in SKILL_VERIFICATION_HEROES:
                skill_template = f"skill_{hero_key}"

                # 检查技能模板是否已注册，如果没有则尝试加载
                if skill_template not in template_matcher.templates:
                    import os

                    skill_path = os.path.join("hero_skills", f"{hero_key}_skill.png")
                    if os.path.exists(skill_path):
                        # 注册技能模板到匹配器
                        template_matcher.register_template(skill_template, skill_path)
                    else:
                        # 模板文件不存在，跳过此英雄
                        continue

                # 检测技能图标
                result = template_matcher.detect(
                    skill_template,
                    img_gray,
                    min_confidence=SKILL_VERIFICATION_THRESHOLD,
                )
                if result.found:
                    # 技能验证通过，更新最佳验证结果
                    if result.confidence > verified_confidence:
                        verified_hero = hero_key
                        verified_confidence = result.confidence

            # 记录技能验证结果到上下文
            if verified_hero:
                context["verified_hero"] = verified_hero
                context["verified_hero_confidence"] = verified_confidence
                logger.info(
                    f"技能验证: {verified_hero} (置信度: {verified_confidence:.3f})"
                )
        else:
            # 不在选英雄界面，禁用英雄头像检测
            context["enable_hero_avatar_detection"] = False

        # 将母模式转换为状态名并返回
        state = PARENT_MODE_TO_STATE.get(best_parent)
        if state:
            # 保存检测信息到上下文
            context["detected_parent"] = best_parent
            context["parent_confidence"] = best_parent_confidence
            context["parent_details"] = parent_result_details
            logger.info(f"返回状态: {state}")
            return state

        # 母模式未映射到状态，输出警告
        logger.warning(f"母模式 {best_parent} 未映射到状态")
        return None


class DetectionStrategyFactory:
    """
    检测策略工厂类

    功能说明:
        负责创建不同类型的检测策略实例。
        提供静态方法用于创建单个策略或策略链。

    使用场景:
        - 根据需要创建不同级别的检测策略
        - 获取默认的策略链用于顺序检测
    """

    @staticmethod
    def create_strategy(
        level: DetectionLevel, current_state: Optional[str] = None
    ) -> DetectionStrategy:
        """
        创建指定级别的检测策略

        参数说明:
            level: 检测级别枚举值（NORMAL/DEEP/EMERGENCY）
            current_state: 当前状态名称，用于策略初始化（可选）

        返回值:
            DetectionStrategy: 对应级别的检测策略实例

        功能描述:
            根据检测级别创建相应的策略实例：
            - NORMAL: 创建层级检测策略
            - DEEP: 创建深度检测策略
            - 其他: 默认创建层级检测策略
        """
        if level == DetectionLevel.NORMAL:
            # 创建层级检测策略实例
            return HierarchicalDetectionStrategy(current_state or "unknown")
        elif level == DetectionLevel.DEEP:
            # 创建深度检测策略实例
            return DeepDetectionStrategy()
        else:
            # 默认创建层级检测策略
            return HierarchicalDetectionStrategy(current_state or "unknown")

    @staticmethod
    def get_strategy_chain(current_state: str) -> List[DetectionStrategy]:
        """
        获取默认策略链

        参数说明:
            current_state: 当前状态名称，用于策略初始化

        返回值:
            List[DetectionStrategy]: 策略实例列表，按执行顺序排列

        功能描述:
            返回默认的策略链，包含层级检测策略和深度检测策略。
            检测时按顺序执行，直到某个策略成功检测到状态。
        """
        return [
            HierarchicalDetectionStrategy(current_state),  # 首先尝试层级检测
            DeepDetectionStrategy(),  # 然后尝试深度检测
        ]
