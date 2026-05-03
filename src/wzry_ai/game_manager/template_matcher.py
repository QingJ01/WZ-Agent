# -*- coding: utf-8 -*-
"""
模板匹配模块 - 封装MTM多模板匹配功能

功能说明：
1. 支持MTM多模板匹配库进行批量模板检测
2. 支持传统OpenCV单模板匹配作为备选
3. 支持ROI区域限制以加速匹配
4. 支持RGB亮度验证判断按钮选中状态
5. 支持智能界面状态检测和模板分组
"""

# 导入标准库
import os  # 操作系统模块，用于文件路径检查
import cv2  # OpenCV库，用于图像处理和模板匹配
import numpy as np  # NumPy库，用于数值计算
import time  # 时间模块，用于性能统计
from typing import Any, Tuple, List, Optional, Dict  # 类型提示
from dataclasses import dataclass  # 数据类装饰器

# 尝试导入配置模块中的默认模板置信度阈值
try:
    from wzry_ai.config import DEFAULT_TEMPLATE_CONFIDENCE
except ImportError:
    # 如果导入失败，使用默认阈值0.8
    DEFAULT_TEMPLATE_CONFIDENCE = 0.8

# 尝试导入日志工具模块，支持相对导入和绝对导入
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.utils.resource_resolver import get_runtime_path_resolver

# 创建模块级别的日志记录器实例
logger = get_logger(__name__)

# 尝试导入MTM多模板匹配库
try:
    MTM: Any = __import__("MTM")
    MTM_AVAILABLE = True  # 标记MTM库可用
except ImportError:
    MTM = None
    MTM_AVAILABLE = False  # 标记MTM库不可用
    logger.warning("MTM 库未安装，将使用传统单模板匹配")


# 使用dataclass定义匹配结果数据类
@dataclass
class MatchResult:
    """
    模板匹配结果数据类

    属性说明：
    - found: 是否找到匹配
    - confidence: 匹配置信度，范围0.0-1.0
    - location: 匹配位置坐标 (x, y)
    - size: 匹配区域的尺寸 (width, height)
    - template_name: 模板名称
    """

    found: bool  # 是否找到匹配
    confidence: float  # 匹配置信度分数
    location: Tuple[int, int]  # 匹配位置坐标 (x, y)
    size: Tuple[int, int]  # 匹配区域尺寸 (width, height)
    template_name: str = ""  # 模板名称，默认为空字符串


class TemplateMatcher:
    """
    模板匹配器类

    功能说明：
    1. 封装MTM多模板匹配和传统单模板匹配
    2. 支持模板缓存和ROI优化
    3. 支持RGB亮度验证判断UI元素状态
    4. 支持智能界面状态检测

    参数说明：
    - template_folder: 模板图像文件夹路径
    - match_scale: 匹配缩放比例，用于加速匹配
    - use_mtm: 是否使用MTM库
    """

    def __init__(
        self,
        template_folder: Optional[str] = None,
        match_scale: float = 0.25,
        use_mtm: bool = True,
    ):
        """
        初始化模板匹配器

        参数说明：
        - template_folder: 模板图像文件夹路径，默认为'image/'
        - match_scale: 图像缩放比例，默认为0.25（缩小到1/4加速匹配）
        - use_mtm: 是否使用MTM多模板匹配，默认为True
        """
        self.path_resolver = get_runtime_path_resolver()
        template_folder = os.fspath(
            self.path_resolver.templates_dir(preferred_root=template_folder)
        )
        self.template_folder = template_folder  # 保存模板文件夹路径（绝对路径）
        self.match_scale = match_scale  # 保存匹配缩放比例
        self.use_mtm = use_mtm and MTM_AVAILABLE  # 根据可用性决定是否使用MTM

        # 模板缓存字典，键为模板名称，值为模板图像
        self.templates: Dict[str, np.ndarray] = {}
        # 预缩放模板缓存，避免每次detect都重新缩放
        self._scaled_templates: Dict[str, np.ndarray] = {}
        # 帧级缩放图像缓存 (img_id, scaled_img)，同一帧多次detect复用
        self._img_scale_cache: Tuple = (None, None)
        # 帧级检测结果缓存 {(img_id, template_name): MatchResult}，避免同帧重复匹配
        self._detect_cache: Dict[Tuple, "MatchResult"] = {}
        self._detect_cache_img_id: int = -1
        # 模板配置字典，用于存储每个模板的自定义配置
        self.template_configs: Dict[str, dict] = {}

        # 性能统计字典，记录各类调用的次数
        self.stats = {
            "total_calls": 0,  # 总调用次数
            "cache_hits": 0,  # 缓存命中次数
            "mtm_calls": 0,  # MTM调用次数
            "traditional_calls": 0,  # 传统匹配调用次数
        }

        # 保存上一帧BGR图像，用于RGB亮度验证
        self._last_frame: Optional[np.ndarray] = None

        # 需要RGB验证的模板集合（用于判断UI元素选中状态）
        # 这些模板匹配后，会通过亮度检测判断是高亮(选中)还是灰度(未选中)
        self.rgb_check_templates = {
            # 人机模式选择按钮
            "ai_standard",
            "ai_quick",
            # 人机难度选择按钮
            "ai_recommend",
            "ai_bronze",
            "ai_gold",
            "ai_diamond",
            "ai_star",
            "ai_master",
            # 分路选择按钮
            "lane_top",
            "lane_jungle",
            "lane_mid",
            "lane_adc",
            "lane_support",
            # 全部分路选项
            "all_lane",
        }

        # ========== 层级检测策略：模板分组 ==========
        # 界面状态到模板组的映射，用于智能检测当前界面状态
        # 每个状态包含指示器模板和该状态下可能出现的所有模板
        self.screen_template_groups = {
            # 人机模式设置界面
            "AI_MODE": {
                "indicators": ["Ai_Mode1"],  # 状态指示器模板
                "templates": [  # 该状态下可能同时出现的模板
                    "AI_Bronze",
                    "AI_Diamond",
                    "AI_Gold",
                    "AI_Master",
                    "AI_Quick",
                    "AI_Recommend",
                    "AI_Standard",
                    "AI_Star",
                    "Start_practicing",
                ],
            },
            # 游戏大厅界面
            "LOBBY": {
                "indicators": ["game_lobby", "battle", "ranking"],
                "templates": [
                    "game_lobby",
                    "battle",
                    "ranking",
                ],
            },
            # 开始游戏界面
            "START_GAME": {"indicators": ["start_game"], "templates": ["start_game"]},
            # 对战/排位模式选择界面
            "BATTLE_MODE_SELECT": {
                "indicators": ["Battle_Mode"],
                "templates": ["Battle_Mode", "5v5"],
            },
            # 5V5王者峡谷选择界面
            "5V5_SELECT": {
                "indicators": ["Canyon_Match", "ai_mode"],
                "templates": ["Canyon_Match", "ai_mode"],
            },
            # 5V5房间界面
            "5V5_ROOM": {
                "indicators": ["5v5_Team", "Start-Match"],
                "templates": ["5v5_Team", "Start-Match"],
            },
            # 匹配成功确认界面
            "MATCH_CONFIRM": {
                "indicators": ["Match_successful", "Match_Confirm"],
                "templates": ["Match_successful", "Match_Confirm"],
            },
            # 选英雄主界面
            "HERO_SELECT_MAIN": {
                "indicators": [
                    "Select-Hero",
                    "arrow_right",
                    "yao_skill",
                    "caiwenji_skill",
                    "mingshiyin_skill",
                ],
                "templates": [
                    "Select-Hero",
                    "arrow_right",
                    "yao_skill",
                    "caiwenji_skill",
                    "mingshiyin_skill",
                ],
            },
            # 分路选择界面
            "LANE_SELECT": {
                "indicators": [
                    "lane_top",
                    "lane_jungle",
                    "lane_mid",
                    "lane_adc",
                    "lane_support",
                    "all_lane",
                ],
                "templates": [
                    "lane_top",
                    "lane_jungle",
                    "lane_mid",
                    "lane_adc",
                    "lane_support",
                    "all_lane",
                ],
            },
        }

        # 当前界面状态缓存变量
        self._current_screen: Optional[str] = None  # 当前检测到的界面状态
        self._screen_state_frames: int = 0  # 当前状态持续帧数
        self._screen_state_timeout: int = 30  # 状态超时帧数（约1秒@30fps）

        # 加载所有模板图像
        self._load_templates()

    def _load_templates(self):
        """
        加载所有模板图像到内存缓存

        功能说明：
        1. 定义所有需要加载的模板文件映射
        2. 从模板文件夹读取每个模板图像
        3. 以灰度模式读取并缓存到self.templates字典
        4. 记录加载成功和失败的数量
        """
        import os  # 在方法内导入os模块，用于文件路径操作

        # 定义模板文件名映射字典，键为模板名称，值为文件名
        template_files = {
            # ========== 启动流程 ==========
            "wzry_icon": "wzry_icon.png",  # 游戏图标
            "start_game": "start_game.png",  # 开始游戏按钮
            # ========== 大厅 ==========
            "game_lobby": "game_lobby.png",  # 游戏大厅
            "battle": "battle.png",  # 对战按钮
            "ranking": "ranking.png",  # 排位按钮
            "ranking_match": "ranking_match.png",  # 排位赛匹配
            "ranking_hero_select": "ranking_support.png",  # 排位选英雄
            "ranking_support": "ranking_support.png",  # 游走分路标识
            "ranking_confirm": "ranking_confirm.png",  # 排位确认按钮
            # ========== 对战流程 ==========
            "canyon_match": "canyon_match.png",  # 峡谷匹配
            "wangzhe_canyon": "wangzhe_canyon.png",  # 王者峡谷
            "battle_mode": "battle_mode.png",  # 对战模式
            "5v5_canyon": "5v5_canyon.png",  # 5v5峡谷
            "ai_mode": "ai_mode.png",  # 人机模式
            "ai_mode_choose": "ai_mode_choose.png",  # 人机模式选择
            "ai_standard": "ai_standard.png",  # 标准人机
            "ai_quick": "ai_quick.png",  # 快速人机
            "ai_recommend": "ai_recommend.png",  # 推荐难度
            "ai_bronze": "ai_bronze.png",  # 青铜难度
            "ai_gold": "ai_gold.png",  # 黄金难度
            "ai_diamond": "ai_diamond.png",  # 钻石难度
            "ai_star": "ai_star.png",  # 星耀难度
            "ai_master": "ai_master.png",  # 王者难度
            "start_practice": "start_practicing.png",  # 开始练习
            "start_match": "start_match.png",  # 开始匹配
            # ========== 匹配流程 ==========
            "match_confirm": "match_confirm.png",  # 匹配确认
            "confirmed": "confirmed.png",  # 已确认
            "hero_confirm": "hero_confirm.png",  # 英雄确认
            # ========== 选英雄 ==========
            "select_hero": "select_hero.png",  # 选择英雄
            "hero_selection": "all_lane.png",  # 英雄选择界面
            # ========== 分路选择 ==========
            "lane_top": "lane_top.png",  # 对抗路
            "lane_jungle": "lane_jungle.png",  # 打野
            "lane_mid": "lane_mid.png",  # 中路
            "lane_adc": "lane_adc.png",  # 发育路
            "lane_support": "lane_support.png",  # 游走
            "all_lane": "all_lane.png",  # 全部分路
            # ========== 结算 ==========
            "victory": "victory.png",  # 胜利
            "victory1": "victory1.png",  # 胜利（另一种）
            "defeat": "defeat.png",  # 失败
            "match_statistics": "match_statistics.png",  # 比赛统计
            "stats": "stats.png",  # 统计
            "return_room": "return_to_the_room.png",  # 返回房间
            # ========== 关闭按钮 ==========
            "close1": "close1.png",  # 关闭按钮1
            "close2": "close2.png",  # 关闭按钮2
            "close3": "close3.png",  # 关闭按钮3
            "close4": "close4.png",  # 关闭按钮4
            # ========== 返回按钮 ==========
            "return_btn": "return_btn.png",  # 返回按钮
            "return_btn1": "return_btn1.png",  # 返回按钮1
            # ========== VS加载画面 ==========
            "VS": "VS.png",  # VS对战画面
            # ========== 分路选择入口 ==========
            "arrow_right": "arrow_right.png",  # 右箭头（进入分路选择）
            # ========== 继续按钮 ==========
            "continue": "continue.png",  # 继续按钮
            # ========== 确认按钮 ==========
            "confirm": "confirm.png",  # 确认按钮
            "confirm1": "confirm1.png",  # 确认按钮1
            "confirm2": "confirm2.png",  # 确认按钮2
            # ========== 防沉迷弹窗 ==========
            "rest": "rest.png",  # 休息提示
            "rest_confirm": "rest_confirm.png",  # 休息确认
        }

        # 记录开始加载模板
        logger.info(f"开始加载模板...")
        loaded_count = 0  # 初始化成功加载计数器

        # 遍历模板文件映射，逐个加载
        for name, filename in template_files.items():
            # 构建完整的文件路径
            filepath = os.fspath(
                self.path_resolver.resolve_template(
                    filename,
                    preferred_root=self.template_folder,
                )
            )
            # 检查文件是否存在
            if os.path.exists(filepath):
                try:
                    # 以灰度模式读取模板图像
                    template = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                    # 检查图像是否成功读取
                    if template is not None:
                        # 将模板添加到缓存字典
                        self.templates[name] = template
                        loaded_count += 1  # 增加成功计数
                except (OSError, cv2.error, ValueError) as e:
                    # 记录加载失败的错误信息
                    logger.error(f"加载模板失败 {name}: {e}", exc_info=True)
            else:
                # 记录文件不存在的警告
                logger.warning(f"模板文件不存在: {filepath}")

        # 记录加载完成信息
        logger.info(f"成功加载 {loaded_count} 个模板")

    def register_template(self, name: str, filepath: str) -> bool:
        """
        动态注册模板到模板缓存

        参数说明：
        - name: 模板名称，用于后续检测时引用
        - filepath: 模板图像文件的完整路径

        返回值说明：
        - 返回True表示注册成功，False表示失败

        功能说明：
        在运行时动态添加新的模板到缓存中，支持从文件路径加载模板图像
        """
        try:
            if not os.path.isabs(filepath):
                filepath = os.path.join(
                    os.fspath(self.path_resolver.repo_root), filepath
                )
            # 检查文件是否存在
            if os.path.exists(filepath):
                # 以灰度模式读取模板图像
                template = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                # 检查图像是否成功读取
                if template is not None:
                    # 将模板添加到缓存字典
                    self.templates[name] = template
                    return True
            else:
                # 文件不存在，记录错误
                logger.error(f"注册模板失败，文件不存在: {filepath}")
        except (OSError, cv2.error, ValueError) as e:
            # 发生异常，记录错误信息
            logger.error(f"注册模板失败 {name}: {e}", exc_info=True)
        # 注册失败返回False
        return False

    def _cache_scaled_template(self, name: str, template: np.ndarray):
        """预缩放模板并缓存，加载时调用一次"""
        self._scaled_templates[name] = cv2.resize(
            template,
            (
                int(template.shape[1] * self.match_scale),
                int(template.shape[0] * self.match_scale),
            ),
        )

    def _get_scaled_img(self, img_gray: np.ndarray) -> np.ndarray:
        """帧级缩放缓存：同一img对象只缩放一次"""
        img_id = id(img_gray)
        cached_id, cached_img = self._img_scale_cache
        if cached_id == img_id:
            return cached_img
        h, w = img_gray.shape[:2]
        scaled = cv2.resize(
            img_gray, (int(w * self.match_scale), int(h * self.match_scale))
        )
        self._img_scale_cache = (img_id, scaled)
        return scaled

    def set_last_frame(self, frame: np.ndarray):
        """
        设置上一帧BGR图像（用于RGB亮度验证）

        参数说明：
        - frame: BGR格式的原始彩色图像

        功能说明：
        保存原始彩色图像，用于后续的RGB亮度验证
        在模板匹配后，通过比较ROI区域亮度判断按钮的选中状态
        """
        # 如果帧不为空则复制保存，否则设为None
        self._last_frame = frame.copy() if frame is not None else None

    def detect(
        self,
        template_name: str,
        img_gray: np.ndarray,
        min_confidence: Optional[float] = None,
        use_roi: bool = True,
    ) -> MatchResult:
        """
        检测单个模板（支持ROI优化）

        参数说明：
        - template_name: 要检测的模板名称
        - img_gray: 灰度图像，用于模板匹配
        - min_confidence: 最小置信度阈值，None则使用模板配置或默认值
        - use_roi: 是否使用ROI配置加速匹配，默认为True

        返回值说明：
        - 返回MatchResult对象，包含匹配结果信息

        功能说明：
        1. 从缓存获取模板图像
        2. 如有ROI配置，裁剪ROI区域进行匹配以加速
        3. 使用MTM或传统方法进行模板匹配
        4. 对需要RGB验证的模板进行亮度检查
        """
        # 增加总调用次数统计
        self.stats["total_calls"] += 1

        # 帧级检测缓存：同一帧同一模板直接返回缓存结果
        img_id = id(img_gray)
        if img_id != self._detect_cache_img_id:
            self._detect_cache.clear()
            self._detect_cache_img_id = img_id
        cache_key = (template_name, min_confidence, use_roi)
        cached = self._detect_cache.get(cache_key)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached

        # 从模板缓存获取模板图像
        template = self.templates.get(template_name)
        # 如果模板不存在，返回未找到结果
        if template is None:
            return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

        # 检查是否有ROI配置
        roi = None
        if use_roi:
            try:
                # 尝试从配置导入TEMPLATE_ROI
                from wzry_ai.config import TEMPLATE_ROI

                # 获取当前模板的ROI配置
                roi = TEMPLATE_ROI.get(template_name)
            except ImportError:
                # 配置导入失败，忽略ROI
                pass

        # 如果有ROI配置，裁剪ROI区域进行匹配
        if roi:
            # 提取ROI坐标和尺寸
            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            # 确保ROI在图像范围内，防止越界
            img_h, img_w = img_gray.shape[:2]
            x = max(0, min(x, img_w - 1))  # 限制x在有效范围
            y = max(0, min(y, img_h - 1))  # 限制y在有效范围
            w = min(w, img_w - x)  # 限制宽度不超出图像
            h = min(h, img_h - y)  # 限制高度不超出图像

            # 裁剪ROI区域图像
            roi_img = img_gray[y : y + h, x : x + w]

            # 在ROI区域内进行模板匹配
            if self.use_mtm:
                # 使用MTM方法匹配
                result = self._detect_mtm_single(
                    template_name, template, roi_img, min_confidence
                )
            else:
                # 使用传统方法匹配
                result = self._detect_traditional(
                    template_name, template, roi_img, min_confidence
                )

            # 将匹配坐标转换回全图坐标系
            if result.found:
                result.location = (result.location[0] + x, result.location[1] + y)
        else:
            # 没有ROI配置，进行全图匹配
            if self.use_mtm:
                # 使用MTM方法全图匹配
                result = self._detect_mtm_single(
                    template_name, template, img_gray, min_confidence
                )
            else:
                # 使用传统方法全图匹配
                result = self._detect_traditional(
                    template_name, template, img_gray, min_confidence
                )

        # 对需要RGB验证的模板进行亮度辅助验证
        if result.found and template_name in self.rgb_check_templates:
            result = self._apply_rgb_check(result, template_name)

        # 返回最终的匹配结果（并存入帧级缓存）
        self._detect_cache[cache_key] = result
        return result

    def detect_group(
        self,
        template_names: List[str],
        img_gray: np.ndarray,
        min_confidence: float = 0.7,
    ) -> List[MatchResult]:
        """
        检测多个模板（使用MTM批量匹配）

        参数说明：
        - template_names: 模板名称列表
        - img_gray: 灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回匹配结果列表，每个元素是MatchResult对象

        功能说明：
        1. 如果MTM不可用或只有一个模板，回退到逐个检测
        2. 使用MTM批量匹配提高效率
        3. 对需要RGB验证的模板进行亮度验证
        """
        # 如果MTM不可用或只有一个模板，回退到逐个检测
        if not self.use_mtm or len(template_names) <= 1:
            results = []
            for name in template_names:
                # 逐个检测每个模板
                result = self.detect(name, img_gray, min_confidence)
                if result.found:
                    results.append(result)
            return results

        # 使用MTM批量检测
        results = self._detect_mtm_group(template_names, img_gray, min_confidence)

        # 对需要RGB验证的模板进行验证
        validated_results = []
        for result in results:
            if result.found and result.template_name in self.rgb_check_templates:
                # 进行RGB亮度验证
                result = self._apply_rgb_check(result, result.template_name)
                # RGB验证通过后仍认为是找到
                if result.found:
                    validated_results.append(result)
            elif result.found:
                # 不需要RGB验证，直接添加
                validated_results.append(result)

        return validated_results

    def detect_smart(
        self, img_gray: np.ndarray, min_confidence: float = 0.7
    ) -> List[MatchResult]:
        """
        智能检测 - 根据当前界面状态选择检测的模板组

        参数说明：
        - img_gray: 灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回检测结果列表

        功能说明：
        策略：
        1. 先检测当前状态指示器模板，确认界面状态
        2. 如果状态未变，只检测该状态相关的模板（提高效率）
        3. 如果状态变化或超时，重新检测所有指示器
        """
        # 步骤1：检测当前状态的指示器（如果已有状态且未超时）
        if (
            self._current_screen
            and self._screen_state_frames < self._screen_state_timeout
        ):
            # 获取当前状态的指示器列表
            indicators = self.screen_template_groups[self._current_screen]["indicators"]
            indicator_found = False

            # 检测任意一个指示器是否存在
            for indicator in indicators:
                result = self.detect(indicator, img_gray, min_confidence)
                if result.found:
                    indicator_found = True
                    break

            if indicator_found:
                # 状态保持，只检测该状态的模板
                self._screen_state_frames += 1
                templates = self.screen_template_groups[self._current_screen][
                    "templates"
                ]
                results = []
                for template in templates:
                    result = self.detect(template, img_gray, min_confidence)
                    if result.found:
                        results.append(result)
                return results
            else:
                # 指示器未找到，状态可能已变化，重置状态
                self._current_screen = None
                self._screen_state_frames = 0

        # 步骤2：没有状态或状态已失效，检测所有指示器
        all_results = []
        for screen_name, group in self.screen_template_groups.items():
            for indicator in group["indicators"]:
                result = self.detect(indicator, img_gray, min_confidence)
                if result.found:
                    # 找到指示器，确定当前状态
                    self._current_screen = screen_name
                    self._screen_state_frames = 1
                    all_results.append(result)

                    # 检测该状态的所有模板
                    for template in group["templates"]:
                        if template != indicator:  # 避免重复检测指示器
                            t_result = self.detect(template, img_gray, min_confidence)
                            if t_result.found:
                                all_results.append(t_result)
                    return all_results

        # 步骤3：没有找到任何指示器，返回空列表
        return []

    def reset_screen_state(self):
        """
        重置界面状态（用于场景切换后）

        功能说明：
        当检测到场景切换时调用此方法，清除当前状态缓存
        强制下次检测时重新识别界面状态
        """
        self._current_screen = None  # 清除当前界面状态
        self._screen_state_frames = 0  # 重置状态持续帧数

    def detect_all_mtm(
        self, img_gray: np.ndarray, min_confidence: float = 0.3
    ) -> Tuple[bool, Optional[MatchResult], List[MatchResult]]:
        """
        使用MTM扫描所有模板

        参数说明：
        - img_gray: 灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回元组 (是否找到, 最佳匹配, 所有匹配列表)

        功能说明：
        使用MTM库一次性匹配所有已加载的模板，返回所有匹配结果
        """
        # 检查MTM是否可用且模板不为空
        if not self.use_mtm or MTM is None or not self.templates:
            return False, None, []

        # 增加MTM调用次数统计
        self.stats["mtm_calls"] += 1

        try:
            # 构建模板列表（名称和图像的元组列表）
            template_list = list(self.templates.items())

            # 使用MTM进行批量模板匹配
            hits = MTM.matchTemplates(
                template_list,  # 模板列表
                img_gray,  # 目标图像
                method=cv2.TM_CCOEFF_NORMED,  # 匹配方法：归一化相关系数
                N_object=float("inf"),  # 不限制匹配数量
                score_threshold=min_confidence,  # 置信度阈值
                maxOverlap=0.25,  # 最大重叠率
            )

            # 如果没有匹配结果，返回空
            if not hits:
                return False, None, []

            # 解析匹配结果
            all_matches = []
            for label, bbox, score in hits:
                x, y, w, h = bbox
                # 坐标转换（从缩放图像坐标转换回原图坐标）
                orig_x = int(x / self.match_scale)
                orig_y = int(y / self.match_scale)
                orig_w = int(w / self.match_scale)
                orig_h = int(h / self.match_scale)

                # 创建MatchResult对象
                all_matches.append(
                    MatchResult(
                        found=True,
                        confidence=score,
                        location=(orig_x, orig_y),
                        size=(orig_w, orig_h),
                        template_name=label,
                    )
                )

            # 按置信度降序排序
            all_matches.sort(key=lambda x: x.confidence, reverse=True)

            # 返回结果：找到标志、最佳匹配、所有匹配
            return True, all_matches[0], all_matches

        except (OSError, cv2.error, ValueError) as e:
            # 发生异常，记录错误并返回空结果
            logger.error(f"MTM全模板扫描失败: {e}", exc_info=True)
            return False, None, []

    def _detect_mtm_single(
        self,
        template_name: str,
        template: np.ndarray,
        img_gray: np.ndarray,
        min_confidence: Optional[float],
    ) -> MatchResult:
        """
        使用MTM检测单个模板

        参数说明：
        - template_name: 模板名称
        - template: 模板图像（灰度图）
        - img_gray: 目标灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回MatchResult对象，包含匹配结果

        功能说明：
        1. 缩放图像和模板以提高匹配速度
        2. 使用MTM进行单模板匹配
        3. 将匹配坐标转换回原始尺寸
        """
        if MTM is None:
            return self._detect_traditional(
                template_name, template, img_gray, min_confidence
            )

        try:
            # 缩放图像和模板以提高匹配速度
            # 注意：不使用缓存，因为img_gray可能是ROI裁剪后的临时对象，
            # 其内存地址可能被重用，导致缓存命中错误的图像
            h, w = img_gray.shape[:2]
            scaled_img = cv2.resize(
                img_gray, (int(w * self.match_scale), int(h * self.match_scale))
            )
            scaled_template = self._scaled_templates.get(template_name)
            if scaled_template is None:
                scaled_template = cv2.resize(
                    template,
                    (
                        int(template.shape[1] * self.match_scale),
                        int(template.shape[0] * self.match_scale),
                    ),
                )

            # 确定实际使用的置信度阈值
            actual_threshold = (
                min_confidence
                if min_confidence is not None
                else DEFAULT_TEMPLATE_CONFIDENCE
            )

            # 尺寸检查：模板比目标图像大时无法匹配，直接返回
            if (
                scaled_template.shape[0] > scaled_img.shape[0]
                or scaled_template.shape[1] > scaled_img.shape[1]
            ):
                return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

            # 使用MTM进行单模板匹配
            hits = MTM.matchTemplates(
                [(template_name, scaled_template)],  # 单模板列表
                scaled_img,  # 缩放后的目标图像
                method=cv2.TM_CCOEFF_NORMED,  # 归一化相关系数匹配方法
                N_object=1,  # 只返回最佳匹配
                score_threshold=actual_threshold,  # 置信度阈值
                maxOverlap=0.25,  # 最大重叠率
            )

            # 检查是否有匹配结果
            if hits and len(hits) > 0:
                label, bbox, score = hits[0]

                # 再次检查置信度是否满足阈值（双重保险）
                if score < actual_threshold:
                    return MatchResult(False, score, (0, 0), (0, 0), template_name)

                # 提取匹配框坐标
                x, y, w, h = bbox
                # 将缩放后的坐标转换回原始图像坐标
                orig_x = int(x / self.match_scale)
                orig_y = int(y / self.match_scale)
                orig_w = int(w / self.match_scale)
                orig_h = int(h / self.match_scale)

                # 返回成功的匹配结果
                return MatchResult(
                    True, score, (orig_x, orig_y), (orig_w, orig_h), template_name
                )

            # 没有匹配结果，返回失败
            return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

        except (OSError, cv2.error, ValueError) as e:
            # 发生异常，记录错误并返回失败结果
            logger.error(f"MTM单模板检测失败 {template_name}: {e}", exc_info=True)
            return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

    def _detect_mtm_group(
        self, template_names: List[str], img_gray: np.ndarray, min_confidence: float
    ) -> List[MatchResult]:
        """
        使用MTM批量检测多个模板

        参数说明：
        - template_names: 模板名称列表
        - img_gray: 目标灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回MatchResult对象列表

        功能说明：
        1. 构建缩放后的模板列表
        2. 使用MTM一次性匹配所有模板
        3. 将结果坐标转换回原始尺寸
        """
        if MTM is None:
            results = []
            for name in template_names:
                template = self.templates.get(name)
                if template is None:
                    continue
                result = self._detect_traditional(
                    name, template, img_gray, min_confidence
                )
                if result.found:
                    results.append(result)
            return results

        try:
            # 构建模板列表，使用预缩放缓存
            template_list = []
            for name in template_names:
                if name in self.templates:
                    scaled_template = self._scaled_templates.get(name)
                    if scaled_template is None:
                        template = self.templates[name]
                        scaled_template = cv2.resize(
                            template,
                            (
                                int(template.shape[1] * self.match_scale),
                                int(template.shape[0] * self.match_scale),
                            ),
                        )
                    template_list.append((name, scaled_template))

            # 如果模板列表为空，返回空结果
            if not template_list:
                return []

            # 缩放图像以提高匹配速度
            # 注意：不使用缓存，因为img_gray可能是ROI裁剪后的临时对象，
            # 其内存地址可能被重用，导致缓存命中错误的图像
            ih, iw = img_gray.shape[:2]
            scaled_img = cv2.resize(
                img_gray, (int(iw * self.match_scale), int(ih * self.match_scale))
            )

            # 过滤掉比目标图像大的模板
            img_h, img_w = scaled_img.shape[:2]
            template_list = [
                (n, t)
                for n, t in template_list
                if t.shape[0] <= img_h and t.shape[1] <= img_w
            ]
            if not template_list:
                return []

            # 使用MTM进行批量模板匹配
            hits = MTM.matchTemplates(
                template_list,  # 模板列表
                scaled_img,  # 缩放后的目标图像
                method=cv2.TM_CCOEFF_NORMED,  # 归一化相关系数方法
                N_object=float("inf"),  # 不限制匹配数量
                score_threshold=min_confidence,  # 置信度阈值
                maxOverlap=0.25,  # 最大重叠率
            )

            # 解析匹配结果
            results = []
            if hits:
                for label, bbox, score in hits:
                    x, y, w, h = bbox
                    # 将缩放后的坐标转换回原始图像坐标
                    orig_x = int(x / self.match_scale)
                    orig_y = int(y / self.match_scale)
                    orig_w = int(w / self.match_scale)
                    orig_h = int(h / self.match_scale)

                    # 创建MatchResult对象并添加到结果列表
                    results.append(
                        MatchResult(
                            found=True,
                            confidence=score,
                            location=(orig_x, orig_y),
                            size=(orig_w, orig_h),
                            template_name=label,
                        )
                    )

            # 记录调试日志
            if results:
                logger.debug(
                    f"MTM批量匹配结果: {[(r.template_name, f'{r.confidence:.2f}') for r in results]}"
                )

            return results

        except (OSError, cv2.error, ValueError) as e:
            # 发生异常，记录错误并返回空结果
            logger.error(f"MTM批量检测失败: {e}", exc_info=True)
            return []

    def _detect_traditional(
        self,
        template_name: str,
        template: np.ndarray,
        img_gray: np.ndarray,
        min_confidence: Optional[float],
    ) -> MatchResult:
        """
        使用传统OpenCV模板匹配方法

        参数说明：
        - template_name: 模板名称
        - template: 模板图像
        - img_gray: 目标灰度图像
        - min_confidence: 最小置信度阈值

        返回值说明：
        - 返回MatchResult对象

        功能说明：
        使用OpenCV的matchTemplate函数进行模板匹配，支持缩放加速
        """
        # 增加传统匹配调用次数统计
        self.stats["traditional_calls"] += 1

        try:
            # 缩放图像和模板以提高匹配速度
            # 注意：不使用缓存，因为img_gray可能是ROI裁剪后的临时对象，
            # 其内存地址可能被重用，导致缓存命中错误的图像
            h, w = img_gray.shape[:2]
            scaled_img = cv2.resize(
                img_gray, (int(w * self.match_scale), int(h * self.match_scale))
            )
            scaled_template = self._scaled_templates.get(template_name)
            if scaled_template is None:
                scaled_template = cv2.resize(
                    template,
                    (
                        int(template.shape[1] * self.match_scale),
                        int(template.shape[0] * self.match_scale),
                    ),
                )

            # 尺寸检查：模板比目标图像大时无法匹配
            if (
                scaled_template.shape[0] > scaled_img.shape[0]
                or scaled_template.shape[1] > scaled_img.shape[1]
            ):
                return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

            # 使用OpenCV进行模板匹配
            result = cv2.matchTemplate(
                scaled_img, scaled_template, cv2.TM_CCOEFF_NORMED
            )
            # 获取匹配结果的最小值、最大值及其位置
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # 确定实际使用的阈值
            threshold = min_confidence or 0.7

            # 检查最大置信度是否超过阈值
            if max_val >= threshold:
                # 将缩放后的坐标转换回原始图像坐标
                orig_x = int(max_loc[0] / self.match_scale)
                orig_y = int(max_loc[1] / self.match_scale)
                # 模板尺寸保持原始大小
                orig_w = int(template.shape[1])
                orig_h = int(template.shape[0])

                # 返回成功的匹配结果
                return MatchResult(
                    True, max_val, (orig_x, orig_y), (orig_w, orig_h), template_name
                )

            # 未超过阈值，返回失败结果
            return MatchResult(False, max_val, (0, 0), (0, 0), template_name)

        except (OSError, cv2.error, ValueError) as e:
            # 发生异常，记录错误并返回失败结果
            logger.error(f"传统模板匹配失败 {template_name}: {e}", exc_info=True)
            return MatchResult(False, 0.0, (0, 0), (0, 0), template_name)

    def get_stats(self) -> dict:
        """
        获取性能统计信息

        返回值说明：
        - 返回包含统计数据的字典副本

        功能说明：
        返回模板匹配器的性能统计数据，包括总调用次数、缓存命中次数等
        """
        return self.stats.copy()

    def _apply_rgb_check(self, result: MatchResult, template_name: str) -> MatchResult:
        """
        应用RGB亮度验证来判断UI元素状态

        参数说明：
        - result: 模板匹配的原始结果
        - template_name: 模板名称

        返回值说明：
        - 返回调整后的MatchResult对象，包含状态信息

        功能说明：
        通过比较ROI区域亮度与模板亮度的差异来判断选中状态
        当ROI亮度比模板亮度下降15以上时，认为是暗态（未选中）
        """
        # 如果没有保存的彩色帧，无法验证，直接返回原结果
        if self._last_frame is None:
            return result

        # 提取匹配位置信息
        x, y = result.location
        w, h = result.size

        # 计算ROI区域的平均亮度
        roi_brightness = self._get_brightness(self._last_frame, (x, y, w, h))

        # 获取模板图像的基准亮度
        template_brightness = self._get_template_brightness(template_name)

        # 计算亮度差异（模板亮度减去ROI亮度）
        brightness_diff = template_brightness - roi_brightness

        # 判断状态：亮度下降15以上认为是暗态（未选中）
        BRIGHTNESS_THRESHOLD = 15
        is_highlight = brightness_diff < BRIGHTNESS_THRESHOLD

        # 根据亮度差异调整置信度得分
        if is_highlight:
            # 高亮状态：亮度差异越小越好
            brightness_score = min(
                1.0, 0.8 + (BRIGHTNESS_THRESHOLD - brightness_diff) / 50
            )
        else:
            # 灰度状态：亮度差异越大越好
            brightness_score = min(
                1.0, 0.8 + (brightness_diff - BRIGHTNESS_THRESHOLD) / 50
            )

        # 综合原始置信度和亮度得分（加权平均）
        new_confidence = result.confidence * 0.6 + brightness_score * 0.4

        # 构建新的模板名称，包含状态信息后缀
        status_suffix = "_highlight" if is_highlight else "_gray"
        new_template_name = f"{template_name}{status_suffix}"

        # 只有当是高亮状态时才返回成功
        if is_highlight:
            return MatchResult(
                found=True,
                confidence=new_confidence,
                location=result.location,
                size=result.size,
                template_name=new_template_name,
            )
        else:
            # 灰度状态，返回未找到
            return MatchResult(
                False, new_confidence, result.location, result.size, new_template_name
            )

    def _get_brightness(
        self, frame: np.ndarray, roi_box: Tuple[int, int, int, int]
    ) -> float:
        """
        计算指定区域的平均亮度

        参数说明：
        - frame: BGR格式的彩色图像
        - roi_box: 区域坐标元组 (x, y, w, h)

        返回值说明：
        - 返回平均亮度值（0-255）

        功能说明：
        将指定区域转换为灰度图后计算平均像素值
        """
        # 解包区域坐标
        x, y, w, h = roi_box
        # 确保坐标在图像范围内，防止越界
        fh, fw = frame.shape[:2]
        x = max(0, min(x, fw - 1))  # 限制x在有效范围
        y = max(0, min(y, fh - 1))  # 限制y在有效范围
        w = min(w, fw - x)  # 限制宽度不超出图像
        h = min(h, fh - y)  # 限制高度不超出图像

        # 如果区域太小，返回默认中等亮度
        if w < 10 or h < 10:
            return 100

        # 提取ROI区域
        roi = frame[y : y + h, x : x + w]
        # 转换为灰度图
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # 返回平均亮度值
        return float(np.mean(gray))

    def _get_template_brightness(self, template_name: str) -> float:
        """
        获取模板的基准亮度

        参数说明：
        - template_name: 模板名称

        返回值说明：
        - 返回模板图像的平均亮度值

        功能说明：
        计算模板图像的平均亮度，作为判断ROI区域亮度的基准
        """
        # 检查模板是否存在
        if template_name not in self.templates:
            return 100  # 默认亮度值

        # 获取模板图像
        template = self.templates[template_name]
        # 模板是灰度图像，直接计算平均亮度
        return float(np.mean(template))

    def _check_highlight_by_brightness(
        self,
        frame: np.ndarray,
        roi_box: Tuple[int, int, int, int],
        is_highlight_template: bool = True,
    ) -> float:
        """
        通过亮度检测按钮是高亮（选中）还是灰度（未选中）

        参数说明：
        - frame: BGR格式的原始彩色图像
        - roi_box: 按钮区域坐标 (x, y, w, h)
        - is_highlight_template: True表示期望匹配高亮模板，False表示期望匹配灰度模板

        返回值说明：
        - 返回亮度匹配得分，范围0.0-1.0，越高越符合模板类型

        功能说明：
        基于亮度阈值100区分高亮和灰度状态
        - 人机难度按钮: 高亮 114-123, 灰度 90-106
        - 人机模式按钮: 高亮 106-107, 灰度 72-74
        """
        # 解包区域坐标
        x, y, w, h = roi_box
        # 确保坐标在图像范围内
        fh, fw = frame.shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = min(w, fw - x)
        h = min(h, fh - y)

        # 如果区域太小，返回默认中等得分
        if w < 10 or h < 10:
            return 0.5

        # 提取ROI区域
        roi = frame[y : y + h, x : x + w]

        # 转换为灰度图并计算平均亮度
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)

        # 使用阈值100区分高亮/灰度
        threshold = 100

        # 根据模板类型计算匹配得分
        if is_highlight_template:
            # 高亮模板：期望匹配高亮度区域
            if brightness >= threshold:
                # 亮度 >= 阈值，高分匹配
                score = min(1.0, 0.5 + (brightness - threshold) / 30)
            else:
                # 亮度 < 阈值，不匹配（实际是灰度）
                score = brightness / threshold * 0.5  # 最大 0.5
        else:
            # 灰度模板：期望匹配低亮度区域
            if brightness < threshold:
                # 亮度 < 阈值，高分匹配
                score = min(1.0, 0.5 + (threshold - brightness) / 30)
            else:
                # 亮度 >= 阈值，不匹配（实际是高亮）
                score = max(0.0, (threshold - brightness) / 50)

        return float(score)
