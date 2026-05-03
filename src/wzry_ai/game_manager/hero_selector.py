"""英雄选择器 - 按优先级自动选择英雄"""

# 导入标准库
import os  # 操作系统接口模块，用于文件路径操作
import time  # 时间模块，用于点击冷却计时
from dataclasses import dataclass  # 数据类装饰器
from typing import Optional, List, Tuple  # 类型提示

# 导入第三方库
import cv2  # OpenCV库，用于图像处理
import numpy as np  # NumPy库，用于数值计算

# 尝试从配置导入英雄选择相关配置
try:
    from ..config import (
        HERO_SELECT_PRIORITY,
        HERO_LANE_MAP,
        DEFAULT_SUPPORT_HERO,
        HERO_SELECT_MAX_RETRY,
    )
except ImportError:
    from wzry_ai.config import (
        HERO_SELECT_PRIORITY,
        HERO_LANE_MAP,
        DEFAULT_SUPPORT_HERO,
        HERO_SELECT_MAX_RETRY,
    )

# 尝试导入日志工具模块
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.utils.resource_resolver import get_runtime_path_resolver

# 创建模块级别的日志记录器实例
logger = get_logger(__name__)


# 使用dataclass定义英雄选择结果数据类
@dataclass
class HeroSelectResult:
    """
    英雄选择结果数据类

    属性说明：
    - success: 是否选择成功
    - selected_hero: 选中的英雄中文名，失败时为None
    - message: 结果描述信息
    - needs_refresh: 是否需要重新获取图像（用于分路选择流程）
    """

    success: bool  # 选择是否成功
    selected_hero: Optional[str] = None  # 选中的英雄名称
    message: str = ""  # 结果描述信息
    needs_refresh: bool = False  # 是否需要刷新图像


class HeroSelector:
    """
    英雄选择器类

    功能说明：
    1. 按 HERO_SELECT_PRIORITY 配置的优先级选择英雄
    2. 处理分路选择流程（进入分路界面、选择分路、选择英雄）
    3. 通过技能图标验证确认英雄选择
    4. 支持防重复点击和重试机制

    参数说明：
    - template_matcher: 模板匹配器实例，用于检测英雄头像和技能图标
    - click_executor: 点击执行器实例，用于执行屏幕点击操作
    - avatar_folder: 英雄头像文件夹路径，默认为"hero"
    - skill_folder: 英雄技能图标文件夹路径，默认为"hero_skills"
    """

    # 英雄分路映射（中文名 -> 分路key）
    HERO_LANE_MAP = {
        "瑶": "lane_support",
        "蔡文姬": "lane_support",
        "明世隐": "lane_support",
    }

    # 英雄名称映射（拼音key -> 中文名）
    HERO_NAME_MAP = {
        "caiwenji": "蔡文姬",
        "mingshiyin": "明世隐",
        "yao": "瑶",
    }

    # 英雄头像文件夹路径（默认由共享解析器决定）
    AVATAR_FOLDER = None
    # 英雄技能图标文件夹路径（默认由共享解析器决定）
    SKILL_FOLDER = None

    def __init__(
        self,
        template_matcher,
        click_executor,
        avatar_folder: Optional[str] = None,
        skill_folder: Optional[str] = None,
    ):
        """
        初始化英雄选择器

        参数说明：
        - template_matcher: 模板匹配器实例
        - click_executor: 点击执行器实例
        - avatar_folder: 英雄头像文件夹路径，可选
        - skill_folder: 技能图标文件夹路径，可选
        """
        self.template_matcher = template_matcher  # 保存模板匹配器引用
        self.click_executor = click_executor  # 保存点击执行器引用
        self.path_resolver = get_runtime_path_resolver()
        self.avatar_folder_hint = avatar_folder
        self.skill_folder_hint = skill_folder
        self.avatar_folder = os.fspath(
            self.path_resolver.heroes_dir(preferred_root=avatar_folder)
        )
        self.skill_folder = os.fspath(
            self.path_resolver.hero_skills_dir(preferred_root=skill_folder)
        )

        # 防重复点击机制
        self._last_click_time = 0  # 上次点击时间戳
        self._last_click_hero = None  # 上次点击的英雄
        self._click_cooldown = 2.0  # 点击冷却时间（秒）

        # 标记是否刚从分路选择界面返回
        self._just_returned_from_lane = False

        # 分路按钮坐标缓存（优化性能）
        self._lane_button_positions = {}  # 分路按钮位置缓存 {lane_key: (x, y, w, h)}
        self._lane_click_count = {}  # 分路按钮点击计数 {lane_key: 次数}
        self._lane_position_verify_interval = 5  # 每5次点击重新验证坐标

        # 英雄选择重试机制
        self._current_hero_key = None  # 当前尝试的英雄key
        self._retry_count = 0  # 当前英雄的重试次数
        self._pending_hero = None  # 待验证的英雄（刚从分路返回）

        # 选择完成标记
        self._selection_completed = False  # 是否已完成英雄选择
        self._selected_hero_key = None  # 最终选中的英雄key

        # 英雄锁定检测配置
        self._confirm_btn_roi = {"x": 800, "y": 900, "w": 320, "h": 100}  # 确认按钮区域
        self._skill_area_roi = {"x": 1400, "y": 800, "w": 300, "h": 200}  # 技能图标区域
        self._lock_thresholds = {
            "brightness_diff": 8,  # 亮度差异阈值
            "skill_edge_threshold": 50,  # 技能区域边缘阈值
        }

        # 注册英雄头像模板到模板匹配器
        self._register_hero_avatars()

        # 记录初始化完成信息
        logger.info(f"初始化完成，优先级列表: {self._get_priority_names()}")

    def _register_hero_avatars(self):
        """
        注册英雄头像模板到模板匹配器

        功能说明：
        1. 遍历HERO_SELECT_PRIORITY中的英雄
        2. 读取每个英雄的头像图像
        3. 缩放到标准尺寸（138×138）
        4. 注册到模板匹配器的模板缓存中
        """
        # 排位赛选英雄界面头像标准尺寸
        AVATAR_SIZE = (138, 138)

        registered_count = 0  # 初始化注册计数器

        # 遍历优先级列表中的每个英雄
        for hero_key in HERO_SELECT_PRIORITY:
            # 构建英雄头像文件的完整路径
            avatar_path = os.fspath(
                self.path_resolver.resolve_hero_portrait(
                    f"{hero_key}.jpg",
                    preferred_root=self.avatar_folder_hint,
                )
            )
            if not os.path.exists(avatar_path):
                avatar_path = os.fspath(
                    self.path_resolver.resolve_hero_portrait(
                        f"{hero_key}.png",
                        preferred_root=self.avatar_folder_hint,
                    )
                )

            # 检查头像文件是否存在
            if os.path.exists(avatar_path):
                # 以灰度模式读取头像图像
                avatar_img = cv2.imread(avatar_path, cv2.IMREAD_GRAYSCALE)
                if avatar_img is not None:
                    # 使用INTER_AREA插值方法缩放到标准尺寸
                    avatar_resized = cv2.resize(
                        avatar_img, AVATAR_SIZE, interpolation=cv2.INTER_AREA
                    )
                    # 直接注册到模板匹配器的模板字典
                    self.template_matcher.templates[hero_key] = avatar_resized
                    registered_count += 1
            else:
                # 记录头像不存在的警告
                logger.warning(f"英雄头像不存在: {avatar_path}")

        # 记录注册完成信息
        if registered_count > 0:
            logger.info(
                f"已注册 {registered_count} 个英雄头像模板 (尺寸: {AVATAR_SIZE[0]}×{AVATAR_SIZE[1]})"
            )

    def _get_priority_names(self) -> List[str]:
        """
        获取优先级英雄中文名列表

        返回值说明：
        - 返回英雄中文名列表

        功能说明：
        将HERO_SELECT_PRIORITY中的拼音key转换为中文名
        """
        names = []
        for hero_key in HERO_SELECT_PRIORITY:
            # 使用映射获取中文名，如果没有映射则使用原key
            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)
            names.append(hero_name)
        return names

    def _get_first_available_lane(self) -> str:
        """
        获取第一个优先级英雄的分路

        返回值说明：
        - 返回分路类型字符串，如 'lane_support'

        功能说明：
        根据HERO_SELECT_PRIORITY中第一个英雄确定目标分路
        """
        # 检查优先级列表是否非空
        if HERO_SELECT_PRIORITY:
            first_hero_key = HERO_SELECT_PRIORITY[0]
            # 从配置获取分路，默认游走
            return HERO_LANE_MAP.get(first_hero_key, "lane_support")
        # 列表为空，默认返回游走分路
        return "lane_support"

    def _get_current_hero_index(self) -> int:
        """
        获取当前英雄在优先级列表中的索引

        返回值说明：
        - 返回当前英雄在HERO_SELECT_PRIORITY中的索引位置
        """
        # 如果当前英雄未设置，返回0
        if self._current_hero_key is None:
            return 0
        try:
            # 查找当前英雄在列表中的索引
            return HERO_SELECT_PRIORITY.index(self._current_hero_key)
        except ValueError:
            # 当前英雄不在列表中，重置为第一个
            return 0

    def _get_next_hero_key(self) -> Optional[str]:
        """
        获取下一个优先级英雄key

        返回值说明：
        - 返回下一个英雄的拼音key，如果没有则返回None
        """
        # 获取当前索引
        current_idx = self._get_current_hero_index()
        next_idx = current_idx + 1
        # 检查是否超出列表范围
        if next_idx < len(HERO_SELECT_PRIORITY):
            return HERO_SELECT_PRIORITY[next_idx]
        # 已到列表末尾，返回None
        return None

    def _set_current_hero(self, hero_key: str):
        """
        设置当前尝试的英雄

        参数说明：
        - hero_key: 英雄的拼音key

        功能说明：
        设置当前英雄并重置重试计数和待验证状态
        """
        self._current_hero_key = hero_key  # 设置当前英雄
        self._retry_count = 0  # 重置重试计数
        self._pending_hero = None  # 清除待验证英雄

    def select_hero_by_priority(self, img_gray, img_color=None) -> HeroSelectResult:
        """
        按优先级选择英雄（支持主界面和分路选择界面）

        参数说明：
        - img_gray: 灰度图像，用于模板匹配
        - img_color: 彩色图像（BGR格式），用于RGB亮度验证，可选

        返回值说明：
        - 返回HeroSelectResult对象，包含选择结果信息

        功能说明：
        1. 检查是否已完成选择（避免重复检测）
        2. 检测当前界面状态（主界面或分路选择界面）
        3. 根据界面状态调用对应的处理方法
        """
        # 如果已完成选择，直接返回成功结果（避免重复检测）
        if self._selection_completed and self._selected_hero_key:
            hero_name = self.HERO_NAME_MAP.get(
                self._selected_hero_key, self._selected_hero_key
            )
            return HeroSelectResult(
                success=True,
                selected_hero=hero_name,
                message=f"已完成选择: {hero_name}",
            )

        logger.info("开始按优先级选择英雄")

        # 检查当前是否在分路选择界面
        in_lane, current_lane = self._is_in_lane_select(img_gray)

        if in_lane:
            # 在分路选择界面，获取第一个优先级英雄的目标分路
            target_lane = self._get_first_available_lane()
            logger.info(
                f"检测到分路选择界面，当前分路: {current_lane}, 目标分路: {target_lane}"
            )
            return self._select_hero_in_lane(
                img_gray, current_lane, target_lane, img_color
            )
        else:
            # 在主界面，调用主界面选择逻辑
            return self._select_hero_in_main(img_gray, img_color)

    def _select_hero_in_main(self, img_gray, img_color=None) -> HeroSelectResult:
        """
        在主界面选择英雄（使用hero文件夹模板+技能验证+重试机制）

        参数说明：
        - img_gray: 灰度图像
        - img_color: 彩色图像，可选

        返回值说明：
        - 返回HeroSelectResult对象

        功能说明：
        1. 验证待确认的英雄（刚从分路返回）
        2. 检查当前英雄是否已选中（通过技能图标验证）
        3. 按优先级检测英雄状态并处理
        4. 未找到则进入分路选择流程
        """
        logger.info(f"在主界面选择英雄，优先级: {HERO_SELECT_PRIORITY}")

        # 初始化当前英雄（如果未设置）
        if self._current_hero_key is None:
            self._set_current_hero(HERO_SELECT_PRIORITY[0])

        logger.info(
            f"当前尝试: {self._current_hero_key}, 重试次数: {self._retry_count}/{HERO_SELECT_MAX_RETRY}"
        )

        # 第一步：验证待确认的英雄（刚从分路回来）
        if self._pending_hero:
            hero_key = self._pending_hero
            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)

            # 通过技能图标验证英雄是否已选中
            if self._verify_hero_by_skill(hero_key, img_gray):
                logger.info(f"✓ {hero_name} 技能验证通过，点击确认按钮")
                # 点击确认按钮
                self._click_confirm_button()
                self._reset_selection_state(completed=True, hero_key=hero_key)
                return HeroSelectResult(
                    success=True,
                    selected_hero=hero_name,
                    message=f"已完成选择优先级英雄: {hero_name}",
                )
            else:
                logger.warning(f"{hero_name} 技能验证失败")
                self._retry_count += 1
                self._pending_hero = None

                # 检查是否达到最大重试次数
                if self._retry_count < HERO_SELECT_MAX_RETRY:
                    # 再次进入分路选择重试
                    logger.info(f"第{self._retry_count}次失败，进入分路界面重试")
                    return self._enter_lane_select_flow(img_gray)
                else:
                    # 达到最大重试次数，尝试下一个英雄
                    logger.warning(
                        f"{hero_name} 达到最大重试次数({HERO_SELECT_MAX_RETRY})，尝试下一个优先级英雄"
                    )
                    return self._try_next_hero_in_lane(img_gray)

        # 第二步：检查当前英雄是否已选中（通过技能图标验证）
        if self._current_hero_key:
            if self._verify_hero_by_skill(self._current_hero_key, img_gray):
                hero_name = self.HERO_NAME_MAP.get(
                    self._current_hero_key, self._current_hero_key
                )
                logger.info(f"✓ {hero_name} 已通过技能验证，点击确认按钮")
                # 点击确认按钮
                self._click_confirm_button()
                self._reset_selection_state(
                    completed=True, hero_key=self._current_hero_key
                )
                return HeroSelectResult(
                    success=True,
                    selected_hero=hero_name,
                    message=f"已完成选择优先级英雄: {hero_name}",
                )
            else:
                # 当前英雄技能验证失败，进入分路选择
                logger.info(f"当前英雄技能验证失败，进入分路选择")
                return self._enter_lane_select_flow(img_gray)

        # 第三步：按优先级检测英雄状态并处理（从当前英雄开始）
        current_idx = self._get_current_hero_index()
        for i, hero_key in enumerate(HERO_SELECT_PRIORITY):
            # 从当前索引开始检查
            if i < current_idx:
                continue

            # 更新当前英雄
            if self._current_hero_key != hero_key:
                self._set_current_hero(hero_key)

            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)

            # 检查英雄状态（选中/未选中/未找到）
            state = self._check_hero_state(hero_key, img_gray, img_color)

            if state == "selected":
                # 已选中，通过技能验证确认
                if self._verify_hero_by_skill(hero_key, img_gray):
                    logger.info(f"✓ {hero_name} 已选中并通过技能验证")
                    self._reset_selection_state(completed=True, hero_key=hero_key)
                    return HeroSelectResult(
                        success=True,
                        selected_hero=hero_name,
                        message=f"已完成选择优先级英雄: {hero_name}",
                    )
                else:
                    logger.warning(
                        f"{hero_name} 灰度头像匹配但技能验证失败，进入分路选择重试"
                    )
                    # 技能验证失败，直接进入分路选择流程
                    return self._enter_lane_select_flow(img_gray)

            elif state == "unselected":
                # 未选中，获取位置并点击
                color_template = f"hero_color_{hero_key}"
                result = self.template_matcher.detect(
                    color_template, img_gray, min_confidence=0.6
                )

                if result.found:
                    # 计算点击位置（中心点）
                    x, y = result.location
                    w, h = result.size
                    click_x = x + w // 2
                    click_y = y + h // 2

                    # 防重复点击检查
                    current_time = time.time()
                    if (
                        self._last_click_hero == hero_name
                        and current_time - self._last_click_time < self._click_cooldown
                    ):
                        logger.info(f"{hero_name} 点击冷却中")
                        return HeroSelectResult(
                            success=True,
                            selected_hero=hero_name,
                            message=f"{hero_name} 已点击",
                        )

                    # 执行点击
                    logger.info(f"点击选择 {hero_name}: ({click_x}, {click_y})")
                    frame_h, frame_w = img_gray.shape[:2]
                    click_success = self.click_executor.click(
                        click_x, click_y, frame_width=frame_w, frame_height=frame_h
                    )

                    if click_success:
                        self._last_click_time = current_time
                        self._last_click_hero = hero_name
                        logger.info(f"✓ 成功选择 {hero_name}")
                        self._reset_selection_state(completed=True, hero_key=hero_key)
                        return HeroSelectResult(
                            success=True,
                            selected_hero=hero_name,
                            message=f"成功选择英雄: {hero_name}",
                        )

            # state == 'not_found'，尝试下一个英雄
            continue

        # 未找到可用英雄，进入分路选择
        logger.warning(f"主界面未找到可用优先级英雄，进入分路选择")
        return self._enter_lane_select_flow(img_gray)

    def _reset_selection_state(
        self, completed: bool = False, hero_key: Optional[str] = None
    ):
        """
        重置选择状态

        参数说明：
        - completed: 是否标记为选择完成
        - hero_key: 最终选中的英雄key

        功能说明：
        根据completed参数设置或清除选择完成状态
        同时重置当前英雄、重试计数等状态变量
        """
        if completed and hero_key:
            # 标记选择完成
            self._selection_completed = True
            self._selected_hero_key = hero_key
            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)
            logger.info(f"标记选择完成: {hero_name}")
        else:
            # 清除选择完成状态
            self._selection_completed = False
            self._selected_hero_key = None

        # 重置其他状态变量
        self._current_hero_key = None
        self._retry_count = 0
        self._pending_hero = None

    def _click_confirm_button(self):
        """
        点击确认按钮（Hero_Confirm）

        功能说明：
        使用预定义的ROI区域中心点点击确认按钮
        点击后等待0.5秒让操作生效
        """
        try:
            # 使用ROI区域中心点计算点击位置
            roi = self._confirm_btn_roi
            x = roi["x"] + roi["w"] // 2
            y = roi["y"] + roi["h"] // 2

            logger.info(f"点击确认按钮: ({x}, {y})")
            # 执行点击
            self.click_executor.click(x, y)
            # 等待点击生效
            time.sleep(0.5)
        except (AttributeError, OSError, RuntimeError) as e:
            # 记录点击失败的错误
            logger.error(f"点击确认按钮失败: {e}", exc_info=True)

    def _enter_lane_select_flow(self, img_gray) -> HeroSelectResult:
        """
        进入分路选择流程

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回HeroSelectResult对象，needs_refresh设为True

        功能说明：
        点击进入分路选择界面，等待界面刷新后再继续
        """
        # 尝试进入分路选择界面
        if not self._enter_lane_select(img_gray):
            return HeroSelectResult(success=False, message="无法进入分路选择界面")

        # 等待界面切换
        time.sleep(1.0)
        # 标记刚从分路返回（用于后续逻辑）
        self._just_returned_from_lane = True
        return HeroSelectResult(
            success=False, message="已进入分路选择，等待刷新", needs_refresh=True
        )

    def _try_next_hero_in_lane(self, img_gray) -> HeroSelectResult:
        """
        尝试下一个优先级英雄

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回HeroSelectResult对象

        功能说明：
        当前英雄达到最大重试次数后，切换到下一个优先级英雄
        """
        # 获取下一个英雄
        next_hero = self._get_next_hero_key()

        # 检查是否还有下一个英雄
        if next_hero is None:
            logger.warning(f"所有优先级英雄都尝试失败")
            self._reset_selection_state()
            return HeroSelectResult(success=False, message="所有优先级英雄都尝试失败")

        # 设置下一个英雄为当前英雄
        self._set_current_hero(next_hero)
        logger.info(f"尝试下一个英雄: {next_hero}")
        return self._enter_lane_select_flow(img_gray)

    def _select_hero_in_lane(
        self,
        img_gray,
        current_lane: Optional[str],
        target_lane: str = "lane_support",
        img_color=None,
    ) -> HeroSelectResult:
        """
        在分路选择界面选择英雄

        参数说明：
        - img_gray: 灰度图像
        - current_lane: 当前检测到的分路
        - target_lane: 目标分路（根据优先级英雄决定）
        - img_color: 彩色图像（BGR格式），用于RGB分析，可选

        返回值说明：
        - 返回HeroSelectResult对象

        功能说明：
        1. 检测当前是否在目标分路（高亮状态 + RGB验证）
        2. 如果在目标分路，直接选择英雄
        3. 如果在其他分路，切换到目标分路
        4. 点击后等待界面刷新并验证
        """
        # 分路名称映射字典
        lane_name_map = {
            "lane_top": "对抗路",
            "lane_jungle": "打野",
            "lane_mid": "中路",
            "lane_adc": "发育路",
            "lane_support": "游走",
            "all_lane": "全部分路",
        }
        current_lane_name = (
            lane_name_map.get(current_lane, current_lane)
            if current_lane is not None
            else "未知分路"
        )
        target_lane_name = lane_name_map.get(target_lane, target_lane)

        # 构建模板名称
        target_template = target_lane

        # 检查是否在目标分路
        if current_lane == target_lane:
            logger.info(f"已在目标分路{target_lane_name}，检测高亮状态...")
            # 检测是否是高亮状态（RGB亮度验证）
            highlight_result = self.template_matcher.detect(target_template, img_gray)

            if highlight_result.found:
                # RGB验证已通过，确认是高亮状态
                logger.info(
                    f"✓ 确认已进入{target_lane_name}（高亮状态，置信度={highlight_result.confidence:.2f}）"
                )
                logger.info(f"开始在{target_lane_name}选择英雄...")
                return self._select_hero_in_lane_select(img_gray, img_color)
            else:
                # RGB验证未通过，说明是灰度状态（未选中）
                logger.info(f"检测到{target_lane_name}但未高亮（灰度状态），等待...")
                return HeroSelectResult(success=False, message="等待分路高亮")
        else:
            # 在其他分路，切换到目标分路
            logger.info(f"当前在{current_lane_name}，准备切换到{target_lane_name}")

            # 检查是否有缓存的坐标
            cached_pos = self._lane_button_positions.get(target_lane)
            click_count = self._lane_click_count.get(target_lane, 0)
            # 判断是否需要重新验证坐标（每5次点击验证一次）
            need_verify = click_count % self._lane_position_verify_interval == 0

            if cached_pos and not need_verify:
                # 使用缓存坐标
                x, y, w, h = cached_pos
                logger.debug(
                    f"使用缓存坐标点击{target_lane_name}: ({x}, {y}, {w}, {h})"
                )
            else:
                # 首次或需要验证时，使用模板匹配获取坐标
                if need_verify:
                    logger.debug(
                        f"定期验证{target_lane_name}坐标（第{click_count}次点击）"
                    )

                target_result = self.template_matcher.detect(target_template, img_gray)

                if target_result.found:
                    # 模板匹配成功
                    x, y = target_result.location
                    w, h = target_result.size
                    logger.debug(
                        f"模板匹配成功{target_lane_name}: ({x}, {y}, {w}, {h})"
                    )
                else:
                    # 模板匹配失败，使用ROI配置中的位置
                    from wzry_ai.config import TEMPLATE_ROI

                    if target_template in TEMPLATE_ROI:
                        roi = TEMPLATE_ROI[target_template]
                        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
                        logger.debug(
                            f"使用ROI位置{target_lane_name}: ({x}, {y}, {w}, {h})"
                        )
                    else:
                        logger.warning(f"未检测到{target_lane_name}按钮，且无ROI配置")
                        return HeroSelectResult(
                            success=False, message=f"未找到{target_lane_name}按钮"
                        )

                # 缓存坐标
                self._lane_button_positions[target_lane] = (x, y, w, h)
                logger.debug(f"缓存{target_lane_name}坐标: ({x}, {y}, {w}, {h})")

            # 计算点击位置（中心点）
            click_x = x + w // 2
            click_y = y + h // 2

            # 更新点击计数
            self._lane_click_count[target_lane] = click_count + 1

            logger.info(f"点击切换到{target_lane_name}: ({click_x}, {click_y})")

            # 传递图像尺寸进行坐标转换
            frame_h, frame_w = img_gray.shape[:2]
            click_success = self.click_executor.click(
                click_x, click_y, frame_width=frame_w, frame_height=frame_h
            )

            if click_success:
                logger.info(f"✓ 点击执行成功")
            else:
                logger.warning(f"点击执行失败")
                # 点击失败时清除缓存，下次重新匹配
                if target_lane in self._lane_button_positions:
                    del self._lane_button_positions[target_lane]

            # 点击后等待界面切换
            logger.info(f"等待分路切换完成...")
            time.sleep(1.0)

            # 重新截图检测高亮状态
            img_data = self.click_executor.screenshot()
            if img_data:
                # 将截图转换为灰度图
                nparr = np.frombuffer(img_data, np.uint8)
                img_new = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

                # 检测高亮状态
                highlight_result = self.template_matcher.detect(
                    target_template, img_new
                )

                if highlight_result.found:
                    # RGB验证已通过，确认是高亮状态，分路切换成功
                    logger.info(
                        f"✓ 分路切换成功，检测到高亮状态: {target_lane_name} (置信度={highlight_result.confidence:.2f})"
                    )
                    logger.info(f"开始在{target_lane_name}选择英雄...")
                    return self._select_hero_in_lane_select(img_new, None)
                else:
                    # RGB验证未通过，说明是灰度状态
                    logger.warning(f"分路可能未切换成功（当前为灰度状态）")

            return HeroSelectResult(
                success=False,
                message=f"已点击切换到{target_lane_name}，等待刷新",
                needs_refresh=True,
            )

    def _select_hero_in_lane_select(self, img_gray, img_color=None) -> HeroSelectResult:
        """
        在分路选择界面下选择优先级英雄

        参数说明：
        - img_gray: 灰度图像
        - img_color: 彩色图像，可选

        返回值说明：
        - 返回HeroSelectResult对象

        功能说明：
        1. 检查是否已选中优先级英雄（通过技能图标验证）
        2. 按优先级检测英雄状态并处理
        3. 点击选择未选中的英雄
        """
        logger.info(f"开始选择英雄，优先级列表: {HERO_SELECT_PRIORITY}")

        # 分路中文名映射
        lane_name_map = {
            "lane_top": "对抗路",
            "lane_jungle": "打野",
            "lane_mid": "中路",
            "lane_adc": "发育路",
            "lane_support": "游走",
        }

        # 第一步：检查是否已选中优先级英雄（通过技能图标验证）
        logger.info(f"分路界面-开始技能验证，当前尝试英雄: {self._current_hero_key}")
        for hero_key in HERO_SELECT_PRIORITY:
            if self._verify_hero_by_skill(hero_key, img_gray, verbose=True):
                hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)
                hero_lane = HERO_LANE_MAP.get(hero_key, "lane_support")
                lane_name = lane_name_map.get(hero_lane, hero_lane)
                logger.info(f"✓ {hero_name} 已通过技能验证确认选中")
                return HeroSelectResult(
                    success=True, selected_hero=hero_name, message=f"{hero_name} 已选中"
                )

        # 第二步：按优先级检测英雄状态并处理
        for hero_key in HERO_SELECT_PRIORITY:
            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)
            hero_lane = HERO_LANE_MAP.get(hero_key, "lane_support")
            lane_name = lane_name_map.get(hero_lane, hero_lane)

            # 检查英雄状态
            state = self._check_hero_state(hero_key, img_gray, img_color)

            if state == "selected":
                # 已选中，通过技能验证确认
                if self._verify_hero_by_skill(hero_key, img_gray):
                    logger.info(f"✓ {hero_name} 已选中并通过技能验证")
                    return HeroSelectResult(
                        success=True,
                        selected_hero=hero_name,
                        message=f"{hero_name} 已选中",
                    )
                else:
                    logger.warning(
                        f"{hero_name} RGB分析为选中但技能验证失败，可能未真正选中"
                    )
                    continue

            elif state == "unselected":
                # 未选中，获取位置并点击
                color_template = f"hero_color_{hero_key}"
                result = self.template_matcher.detect(
                    color_template, img_gray, min_confidence=0.6
                )

                if result.found:
                    # 计算点击位置（中心点）
                    x, y = result.location
                    w, h = result.size
                    click_x = x + w // 2
                    click_y = y + h // 2

                    logger.info(f"点击选择 {hero_name}: ({click_x}, {click_y})")

                    # 传递图像尺寸进行坐标转换
                    frame_h, frame_w = img_gray.shape[:2]
                    click_success = self.click_executor.click(
                        click_x, click_y, frame_width=frame_w, frame_height=frame_h
                    )

                    if click_success:
                        logger.info(f"✓ 点击执行成功，已选择英雄: {hero_key}")
                        # 分路界面选择英雄后，英雄已锁定
                        self._reset_selection_state(completed=True, hero_key=hero_key)
                        return HeroSelectResult(
                            success=True,
                            selected_hero=hero_name,
                            message=f"已在{lane_name}选择英雄: {hero_name}",
                        )
                    else:
                        logger.warning(f"点击执行失败")
                        continue

            # state == 'not_found'，尝试下一个英雄
            continue

        # 未找到可用英雄
        logger.warning(f"未找到可用英雄")
        return HeroSelectResult(success=False, message="在当前分路未找到可用优先级英雄")

    def _enter_lane_select(self, img_gray) -> bool:
        """
        点击进入分路选择界面

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回True表示成功进入，False表示失败

        功能说明：
        检测右箭头按钮位置并点击，进入分路选择界面
        """
        # 检测 arrow_right 位置
        result = self.template_matcher.detect("arrow_right", img_gray)

        if not result.found:
            logger.warning(f"未找到分路选择入口 (arrow_right)")
            return False

        # 计算点击位置（中心点）
        x, y = result.location
        w, h = result.size
        click_x = x + w // 2
        click_y = y + h // 2

        logger.info(f"点击进入分路选择")

        try:
            # 执行点击
            self.click_executor.click(click_x, click_y)
            return True
        except (AttributeError, OSError, RuntimeError) as e:
            # 记录点击失败的错误
            logger.error(f"点击失败: {e}", exc_info=True)
            return False

    def _is_in_lane_select(self, img_gray) -> Tuple[bool, Optional[str]]:
        """
        检查是否在分路选择界面

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回元组 (是否在分路界面, 当前分路key)

        功能说明：
        1. 检测所有分路按钮模板
        2. 通过RGB亮度验证区分高亮和灰度状态
        3. 优先返回高亮状态的分路
        """
        # 分路key列表
        lane_keys = ["lane_top", "lane_jungle", "lane_mid", "lane_adc", "lane_support"]
        # 分路名称映射
        lane_name_map = {
            "lane_top": "对抗路",
            "lane_jungle": "打野",
            "lane_mid": "中路",
            "lane_adc": "发育路",
            "lane_support": "游走",
            "all_lane": "全部分路",
        }

        # 分路预期坐标（用于参考）
        lane_expected_positions = {
            "all_lane": (60, 20),
            "lane_top": (295, 20),
            "lane_jungle": (532, 20),
            "lane_mid": (769, 20),
            "lane_adc": (1006, 20),
            "lane_support": (1242, 20),
        }

        # 所有分路模板列表
        all_lane_templates = lane_keys + ["all_lane"]

        # 第一步：检测所有分路模板
        detected_lanes = {}  # 所有检测到的分路
        highlight_lanes = {}  # 高亮状态的分路

        logger.debug(f"开始检测分路模板（单模板+RGB亮度检测）...")
        for template_name in all_lane_templates:
            # 降低阈值以适应分路模板检测
            result = self.template_matcher.detect(
                template_name, img_gray, min_confidence=0.5
            )

            if result.found:
                # 检查RGB亮度状态（结果名称包含_highlight或_gray后缀）
                is_highlight = "_highlight" in result.template_name
                detected_lanes[template_name] = result.confidence

                if is_highlight:
                    highlight_lanes[template_name] = result.confidence
                    logger.debug(
                        f"检测 {template_name}: ✓高亮状态, conf={result.confidence:.2f}"
                    )
                else:
                    logger.debug(
                        f"检测 {template_name}: ✗灰度状态, conf={result.confidence:.2f}"
                    )
            else:
                logger.debug(f"检测 {template_name}: 未匹配")

        # 第二步：优先返回高亮状态的分路
        if highlight_lanes:
            # 找到置信度最高的高亮分路
            best_highlight = max(
                highlight_lanes, key=lambda lane_key: highlight_lanes[lane_key]
            )
            best_highlight_conf = highlight_lanes[best_highlight]

            # 检测到all_lane或至少1个分路就认为是分路界面
            if "all_lane" in detected_lanes or len(detected_lanes) >= 1:
                logger.info(
                    f"检测到高亮分路: {lane_name_map.get(best_highlight, best_highlight)} "
                    f"(置信度: {best_highlight_conf:.2f}, 共检测到{len(detected_lanes)}个分路, "
                    f"高亮{len(highlight_lanes)}个)"
                )
                return True, best_highlight
            else:
                logger.warning(
                    f"检测到高亮分路但分路数量不足({len(detected_lanes)}个)，可能不是分路界面"
                )
                return False, None

        # 第三步：没有高亮分路，返回检测到的第一个灰度分路
        if detected_lanes:
            best_gray = max(
                detected_lanes, key=lambda lane_key: detected_lanes[lane_key]
            )
            best_gray_conf = detected_lanes[best_gray]

            # 检测到all_lane或至少1个分路就认为是分路界面
            if "all_lane" in detected_lanes or len(detected_lanes) >= 1:
                logger.info(
                    f"检测到灰度分路: {lane_name_map.get(best_gray, best_gray)} "
                    f"(置信度: {best_gray_conf:.2f}, 共检测到{len(detected_lanes)}个分路)"
                )
                return True, best_gray
            else:
                logger.warning(
                    f"检测到分路但数量不足({len(detected_lanes)}个)，可能不是分路界面"
                )
                return False, None

        return False, None

    def _select_lane(self, lane_type: str, img_gray) -> bool:
        """
        选择分路

        Args:
            lane_type: 分路类型（如 'lane_support'）
            img_gray: 灰度图像

        Returns:
            bool: 是否成功
        """
        # 先检查分路是否已选中（亮态模板 + RGB亮度验证）
        selected_template = f"{lane_type}_selected"

        selected_result = self.template_matcher.detect(selected_template, img_gray)

        # RGB亮度验证：亮态模板匹配后，template_matcher会自动进行亮度验证
        # 如果亮度验证通过（得分 >= 0.5），则置信度保持不变
        # 如果亮度验证不通过（得分 < 0.5），则置信度会被降低
        # 这里我们只需要检查亮态模板是否找到且置信度足够高
        if selected_result.found and selected_result.confidence >= 0.5:
            lane_name_map = {
                "lane_top": "对抗路",
                "lane_jungle": "打野",
                "lane_mid": "中路",
                "lane_adc": "发育路",
                "lane_support": "游走",
            }
            lane_name = lane_name_map.get(lane_type, lane_type)
            logger.info(f"分路已选中: {lane_name}")
            return True

        # 未选中，点击选择
        result = self.template_matcher.detect(lane_type, img_gray)

        if not result.found:
            logger.warning(f"未找到分路: {lane_type}")
            return False

        # 计算点击位置
        x, y = result.location
        w, h = result.size
        click_x = x + w // 2
        click_y = y + h // 2

        lane_name_map = {
            "lane_top": "对抗路",
            "lane_jungle": "打野",
            "lane_mid": "中路",
            "lane_adc": "发育路",
            "lane_support": "游走",
        }
        lane_name = lane_name_map.get(lane_type, lane_type)

        logger.info(f"点击选择分路: {lane_name} (位置: {click_x}, {click_y})")

        try:
            self.click_executor.click(click_x, click_y)
            return True
        except (AttributeError, OSError, RuntimeError) as e:
            logger.error(f"点击失败: {e}", exc_info=True)
            return False

    def _verify_hero_by_skill(
        self, hero_key: str, img_gray, verbose: bool = True
    ) -> bool:
        """
        通过技能图标验证英雄是否已选中

        参数说明：
        - hero_key: 英雄的拼音key
        - img_gray: 灰度图像
        - verbose: 是否输出详细日志，默认为True

        返回值说明：
        - 返回True表示技能图标匹配成功（英雄已选中），False表示失败

        功能说明：
        1. 检查技能模板是否已注册，未注册则尝试加载
        2. 使用模板匹配检测技能图标
        3. 返回匹配结果
        """
        skill_template = f"skill_{hero_key}"
        hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)

        if verbose:
            logger.debug(f"技能验证-开始: {hero_name} (模板: {skill_template})")

        # 检查并注册技能模板
        if skill_template not in self.template_matcher.templates:
            skill_path = os.fspath(
                self.path_resolver.resolve_hero_skill(
                    f"{hero_key}_skill.png",
                    preferred_root=self.skill_folder_hint,
                )
            )
            if verbose:
                logger.debug(f"技能验证-模板未注册，尝试加载: {skill_path}")
            if os.path.exists(skill_path):
                # 注册技能模板
                self.template_matcher.register_template(skill_template, skill_path)
                if verbose:
                    logger.debug(f"技能验证-模板注册成功")
            else:
                if verbose:
                    logger.debug(f"技能验证-模板文件不存在: {skill_path}")
                return False

        # 检测技能图标
        result = self.template_matcher.detect(
            skill_template, img_gray, min_confidence=0.7
        )

        if verbose:
            status = "✓ 通过" if result.found else "✗ 未通过"
            logger.debug(
                f"技能验证-结果: {hero_name} {status} (置信度={result.confidence:.2f}, 阈值=0.7)"
            )

        if result.found:
            return True

        return False

    def _check_hero_state(self, hero_key: str, img_gray, img_bgr=None) -> str:
        """
        检查英雄状态

        参数说明：
        - hero_key: 英雄拼音key
        - img_gray: 灰度图像（用于模板匹配）
        - img_bgr: BGR彩色图像（用于RGB分析），可选

        返回值说明：
        - 返回字符串：'unselected'(未选中), 'selected'(已选中), 'not_found'(未找到)

        功能说明：
        1. 使用彩色头像模板匹配找到英雄位置
        2. 使用RGB分析判断选中状态（灰度=选中，彩色=未选中）
        """
        hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)

        # 1. 先检测彩色头像（匹配位置）
        color_template = f"hero_color_{hero_key}"
        if color_template not in self.template_matcher.templates:
            # 尝试注册彩色头像模板
            color_path = os.fspath(
                self.path_resolver.resolve_hero_portrait(
                    f"{hero_key}.jpg",
                    preferred_root=self.avatar_folder_hint,
                )
            )
            if not os.path.exists(color_path):
                color_path = os.fspath(
                    self.path_resolver.resolve_hero_portrait(
                        f"{hero_key}.png",
                        preferred_root=self.avatar_folder_hint,
                    )
                )
            if os.path.exists(color_path):
                self.template_matcher.register_template(color_template, color_path)

        # 检查模板是否注册成功
        if color_template not in self.template_matcher.templates:
            return "not_found"

        # 模板匹配找到英雄位置
        result = self.template_matcher.detect(
            color_template, img_gray, min_confidence=0.6
        )
        if not result.found:
            return "not_found"

        # 2. 使用RGB分析判断是否选中
        if img_bgr is not None:
            x, y = result.location
            w, h = result.size
            # 提取头像中心区域（避免边框干扰）
            margin = min(w, h) // 4
            avatar = img_bgr[y + margin : y + h - margin, x + margin : x + w - margin]

            if avatar.size > 0:
                # 计算RGB标准差（灰度图像三通道接近，标准差小）
                r_mean = np.mean(avatar[:, :, 2])
                g_mean = np.mean(avatar[:, :, 1])
                b_mean = np.mean(avatar[:, :, 0])
                color_variance = np.std([r_mean, g_mean, b_mean])

                # 阈值判断：方差<15认为是灰度（已选中）
                if color_variance < 15:
                    logger.debug(
                        f"{hero_name} RGB分析为灰度(已选中), 方差={color_variance:.1f}"
                    )
                    return "selected"
                else:
                    logger.debug(
                        f"{hero_name} RGB分析为彩色(未选中), 方差={color_variance:.1f}"
                    )
                    return "unselected"

        # 无彩色图像时，默认未选中
        logger.debug(f"{hero_name} 检测到头像(无RGB分析，默认未选中)")
        return "unselected"

    def get_selected_hero(self, img_gray) -> Optional[str]:
        """
        获取当前已选择的英雄

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回英雄中文名，如果没有则返回None

        功能说明：
        通过技能图标验证查找当前已选中的英雄
        """
        for hero_key in HERO_SELECT_PRIORITY:
            if self._verify_hero_by_skill(hero_key, img_gray):
                return self.HERO_NAME_MAP.get(hero_key, hero_key)
        return None

    def check_hero_lock_status(self, img_gray) -> Tuple[str, float, dict]:
        """
        检测英雄锁定状态

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回元组 (status, confidence, details)
        - status: 'not_selected'(未选择), 'locked'(已锁定), 'unknown'(未知)

        功能说明：
        使用两种方法联合判断：
        1. Hero_Confirm按钮亮度对比（权重60%）
        2. 技能图标区域检测（权重40%）
        """
        # 方法1：Hero_Confirm按钮亮度对比
        confirm_result, confirm_conf = self._check_confirm_brightness(img_gray)

        # 方法2：技能图标区域检测
        skill_result, skill_conf = self._check_skill_area(img_gray)

        # 综合判断
        final_status, final_conf = self._combine_lock_results(
            (confirm_result, confirm_conf, 0.6), (skill_result, skill_conf, 0.4)
        )

        # 构建详细信息字典
        details = {
            "confirm_btn": {"status": confirm_result, "confidence": confirm_conf},
            "skill_area": {"status": skill_result, "confidence": skill_conf},
        }

        return final_status, final_conf, details

    def _check_confirm_brightness(self, img_gray) -> Tuple[str, float]:
        """
        通过Hero_Confirm按钮亮度对比检测锁定状态

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回元组 (status, confidence)

        功能说明：
        比较确认按钮区域与周围背景的亮度差异来判断状态
        """
        # 获取确认按钮ROI
        roi = self._confirm_btn_roi
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]

        # 确保ROI在图像范围内
        h_img, w_img = img_gray.shape[:2]
        x = min(x, w_img - w)
        y = min(y, h_img - h)

        # 提取确认按钮区域
        confirm_region = img_gray[y : y + h, x : x + w]
        confirm_brightness = np.mean(confirm_region)

        # 提取周围背景区域
        margin = 30
        bg_regions = []

        if y >= margin:
            bg_regions.append(img_gray[y - margin : y, x : x + w])
        if x >= margin:
            bg_regions.append(img_gray[y : y + h, x - margin : x])

        # 如果没有背景区域，返回未知
        if not bg_regions:
            return "unknown", 0.0

        # 计算背景平均亮度
        bg_brightness = np.mean(np.concatenate([r.flatten() for r in bg_regions]))
        brightness_diff = confirm_brightness - bg_brightness

        # 根据亮度差异判断状态
        if abs(brightness_diff) < self._lock_thresholds["brightness_diff"]:
            # 亮度差异小，认为是未选择状态
            confidence = (
                1.0 - abs(brightness_diff) / self._lock_thresholds["brightness_diff"]
            )
            return "not_selected", max(0.5, confidence)
        elif brightness_diff > 0:
            # 按钮比背景亮，认为是已锁定状态
            confidence = min(1.0, brightness_diff / 20)
            return "locked", confidence
        else:
            return "unknown", 0.3

    def _check_skill_area(self, img_gray) -> Tuple[str, float]:
        """
        通过技能图标区域检测锁定状态

        参数说明：
        - img_gray: 灰度图像

        返回值说明：
        - 返回元组 (status, confidence)

        功能说明：
        通过分析技能区域的边缘密度和局部对比度来判断是否有技能图标显示
        """
        # 获取技能区域ROI
        roi = self._skill_area_roi
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]

        # 确保ROI在图像范围内
        h_img, w_img = img_gray.shape[:2]
        x = min(x, w_img - w)
        y = min(y, h_img - h)

        # 提取技能区域
        skill_region = img_gray[y : y + h, x : x + w]

        # 计算边缘密度（使用Sobel算子）
        sobelx = cv2.Sobel(skill_region, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(skill_region, cv2.CV_64F, 0, 1, ksize=3)
        edge_density = np.mean(np.sqrt(sobelx**2 + sobely**2))

        # 计算局部对比度
        local_std = np.std(skill_region)

        # 综合得分
        combined_score = edge_density * 0.7 + local_std * 2 * 0.3

        # 根据得分判断状态
        if combined_score < self._lock_thresholds["skill_edge_threshold"]:
            # 边缘密度低，认为是未选择状态
            confidence = (
                1.0 - combined_score / self._lock_thresholds["skill_edge_threshold"]
            )
            return "not_selected", max(0.5, confidence)
        else:
            # 边缘密度高，认为是已锁定状态（有技能图标）
            confidence = min(
                1.0,
                (combined_score - self._lock_thresholds["skill_edge_threshold"]) / 50,
            )
            return "locked", confidence

    def _combine_lock_results(self, result1, result2) -> Tuple[str, float]:
        """
        综合两个检测结果

        参数说明：
        - result1: 第一个结果元组 (status, confidence, weight)
        - result2: 第二个结果元组 (status, confidence, weight)

        返回值说明：
        - 返回综合后的 (status, confidence)

        功能说明：
        根据权重综合两个检测结果，返回最终状态
        """
        status1, conf1, weight1 = result1
        status2, conf2, weight2 = result2

        # 如果两个结果状态相同，直接加权平均
        if status1 == status2:
            avg_conf = (conf1 * weight1 + conf2 * weight2) / (weight1 + weight2)
            return status1, avg_conf

        # 状态不同，计算加权分数
        scores = {"not_selected": 0, "locked": 0, "unknown": 0}
        scores[status1] += conf1 * weight1
        scores[status2] += conf2 * weight2

        # 选择分数最高的状态
        max_status = max(scores, key=lambda status: scores[status])
        total_score = sum(scores.values())
        normalized_conf = scores[max_status] / total_score if total_score > 0 else 0.5

        return max_status, normalized_conf

    def select_hero_in_ranking(self, img_gray, img_color=None) -> HeroSelectResult:
        """
        在排位赛普通选英雄界面选择英雄

        参数说明：
        - img_gray: 灰度图像
        - img_color: 彩色图像，可选

        返回值说明：
        - 返回HeroSelectResult对象

        功能说明：
        1. 识别当前分路（通过分路模板）
        2. 根据分路筛选优先级英雄列表
        3. 在英雄网格区域模板匹配选择英雄
        4. 点击锁定按钮
        """
        logger.info(f"排位赛选英雄界面，开始选择英雄")

        # 分路模板映射
        lane_templates = {
            "ranking_top": "lane_top",
            "ranking_jungle": "lane_jungle",
            "ranking_mid": "lane_mid",
            "ranking_adc": "lane_adc",
            "ranking_support": "lane_support",
        }

        # 分路名称映射
        lane_name_map = {
            "lane_top": "对抗路",
            "lane_jungle": "打野",
            "lane_mid": "中路",
            "lane_adc": "发育路",
            "lane_support": "游走",
        }

        # 第一步：识别当前分路
        current_lane = None
        for template, lane_key in lane_templates.items():
            result = self.template_matcher.detect(
                template, img_gray, min_confidence=0.7
            )
            if result.found:
                current_lane = lane_key
                lane_name = lane_name_map.get(lane_key, lane_key)
                logger.info(f"识别到当前分路: {lane_name}")
                break

        # 如果未识别到分路，默认使用游走
        if not current_lane:
            logger.warning(f"未能识别分路，默认使用游走")
            current_lane = "lane_support"

        # 第二步：根据分路筛选优先级英雄
        from wzry_ai.config import HERO_LANE_MAP, HERO_SELECT_PRIORITY

        # 获取该分路的优先级英雄
        lane_heroes = []
        for hero_key in HERO_SELECT_PRIORITY:
            hero_lane = HERO_LANE_MAP.get(hero_key, "lane_support")
            if hero_lane == current_lane:
                lane_heroes.append(hero_key)

        # 如果当前分路无配置英雄，使用默认优先级
        if not lane_heroes:
            logger.warning(f"当前分路无配置英雄，使用默认优先级")
            lane_heroes = HERO_SELECT_PRIORITY

        logger.info(f"当前分路优先级英雄: {lane_heroes}")

        # 第三步：在英雄网格中查找并选择英雄
        # 排位赛选英雄界面网格配置：3行×7列，头像约138×138
        grid_config = {
            "start_x": 400,  # 网格左上角X
            "start_y": 218,  # 网格左上角Y
            "end_x": 1522,  # 网格右下角X
            "end_y": 716,  # 网格右下角Y
            "cols": 7,  # 每行7个头像
            "rows": 3,  # 共3行
            "avatar_size": 138,  # 头像大小约138×138
        }

        # 计算每个格子的尺寸
        grid_width = grid_config["end_x"] - grid_config["start_x"]
        grid_height = grid_config["end_y"] - grid_config["start_y"]
        cell_width = grid_width // grid_config["cols"]
        cell_height = grid_height // grid_config["rows"]

        logger.debug(
            f"英雄网格: {grid_config['cols']}列×{grid_config['rows']}行, "
            f"格子大小: {cell_width}×{cell_height}"
        )

        # 提取整个英雄网格区域进行匹配
        grid_x1 = grid_config["start_x"]
        grid_y1 = grid_config["start_y"]
        grid_x2 = grid_config["end_x"]
        grid_y2 = grid_config["end_y"]

        # 确保不超出图像边界
        img_h, img_w = img_gray.shape[:2]
        grid_x1 = max(0, grid_x1)
        grid_y1 = max(0, grid_y1)
        grid_x2 = min(img_w, grid_x2)
        grid_y2 = min(img_h, grid_y2)

        grid_roi = img_gray[grid_y1:grid_y2, grid_x1:grid_x2]
        logger.debug(
            f"网格ROI区域: ({grid_x1}, {grid_y1}) - ({grid_x2}, {grid_y2}), "
            f"尺寸: {grid_roi.shape[1]}×{grid_roi.shape[0]}"
        )

        # 在网格中查找优先级英雄
        for hero_key in lane_heroes:
            hero_name = self.HERO_NAME_MAP.get(hero_key, hero_key)

            # 检查英雄头像模板是否已注册
            if hero_key not in self.template_matcher.templates:
                logger.warning(f"英雄 {hero_name} 头像模板未注册")
                continue

            # 获取英雄头像模板尺寸
            hero_template = self.template_matcher.templates[hero_key]
            template_h, template_w = hero_template.shape[:2]

            # 初始化匹配结果
            found = False
            hero_x, hero_y = 0, 0

            # 检查网格ROI是否比模板大
            if grid_roi.shape[0] >= template_h and grid_roi.shape[1] >= template_w:
                # 在整个网格区域匹配英雄头像
                result = cv2.matchTemplate(
                    grid_roi, hero_template, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                # 计算在原图中的位置
                match_x = grid_x1 + max_loc[0]
                match_y = grid_y1 + max_loc[1]

                # 计算在哪个格子
                col = (match_x - grid_x1) // cell_width
                row = (match_y - grid_y1) // cell_height

                logger.debug(
                    f"英雄 {hero_name} 匹配结果: 置信度={max_val:.3f}, "
                    f"位置=({match_x}, {match_y}), 格子=({row + 1}, {col + 1})"
                )

                # 检查置信度是否超过阈值
                if max_val > 0.45:
                    hero_x = match_x + template_w // 2
                    hero_y = match_y + template_h // 2
                    found = True
                    logger.info(
                        f"✓ 找到英雄 {hero_name} 在第{row + 1}行第{col + 1}列 "
                        f"(置信度: {max_val:.3f})"
                    )
            else:
                logger.warning(
                    f"网格ROI ({grid_roi.shape[1]}×{grid_roi.shape[0]}) "
                    f"小于模板 ({template_w}×{template_h})"
                )

            if found:
                logger.info(f"点击选择英雄 {hero_name}: ({hero_x}, {hero_y})")

                # 点击选择英雄
                frame_h, frame_w = img_gray.shape[:2]
                click_success = self.click_executor.click(
                    hero_x, hero_y, frame_width=frame_w, frame_height=frame_h
                )

                if click_success:
                    logger.info(f"✓ 已选择英雄: {hero_name}")

                    # 等待界面响应
                    time.sleep(0.5)

                    # 第四步：点击锁定按钮
                    lock_result = self.template_matcher.detect(
                        "ranking_confirm", img_gray, min_confidence=0.7
                    )
                    if lock_result.found:
                        lx, ly = lock_result.location
                        lw, lh = lock_result.size
                        lock_click_x = lx + lw // 2
                        lock_click_y = ly + lh // 2

                        logger.info(f"点击锁定按钮: ({lock_click_x}, {lock_click_y})")
                        self.click_executor.click(
                            lock_click_x,
                            lock_click_y,
                            frame_width=frame_w,
                            frame_height=frame_h,
                        )
                    else:
                        logger.info(f"未找到锁定按钮，等待系统自动锁定")

                    return HeroSelectResult(
                        success=True,
                        selected_hero=hero_name,
                        message=f"已选择并锁定: {hero_name}",
                    )
                else:
                    logger.warning(f"点击选择英雄失败")
                    continue

        # 未找到可用英雄
        logger.warning(f"未找到可用英雄")
        return HeroSelectResult(
            success=False, message="在英雄网格中未找到可用优先级英雄"
        )
