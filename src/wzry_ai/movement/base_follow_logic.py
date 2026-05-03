"""
通用跟随逻辑基类 - 为所有跟随型辅助提供统一的移动逻辑框架
支持英雄: 瑶、蔡文姬、明世隐等
"""

# 导入日志模块用于记录运行信息
import logging
from math import sqrt

# 导入线程模块用于多线程操作
import threading

# 导入time模块用于时间相关操作
import time

# 从abc导入抽象基类相关功能
from abc import ABC, abstractmethod

# 从queue导入队列相关类
from queue import Empty, Queue

# 从typing导入类型提示相关功能
from typing import Any, Callable, Dict, List, Optional, Tuple

# 本地模块导入
from wzry_ai.config import (
    AVOID_ENEMY_WEIGHT,  # 避敌权重系数
    FOLLOW_THRESHOLD,  # 跟随距离阈值
    MOVE_SCALE_FACTOR,  # 移动缩放因子
    SAFE_ENEMY_DISTANCE,  # 安全距离（离敌人的最小距离）
    KEY_MOVE_UP,  # 向上移动按键
    KEY_MOVE_LEFT,  # 向左移动按键
    KEY_MOVE_DOWN,  # 向下移动按键
    KEY_MOVE_RIGHT,  # 向右移动按键
)
from wzry_ai.utils.keyboard_controller import press, release  # 导入键盘按键控制函数
from wzry_ai.utils.logging_utils import setup_colored_logger  # 导入彩色日志设置函数
from wzry_ai.utils.utils import find_closest_target, safe_queue_put  # 导入工具函数

import wzry_ai.detection.model1_astar_follow as model1_astar_follow  # 导入模态1跟随模块


# 跟随型辅助英雄基类
class BaseSupportHero:
    """
    跟随型辅助英雄基类
    提供统一的双模态跟随逻辑框架
    子类需要覆盖HERO_NAME等属性来实现特定英雄逻辑
    """

    # 英雄名称（子类需要覆盖）
    HERO_NAME = "基础辅助"

    # 英雄特有的跟随配置（子类可覆盖）
    FOLLOW_DISTANCE = FOLLOW_THRESHOLD  # 跟随距离阈值（像素）
    SAFE_DISTANCE = SAFE_ENEMY_DISTANCE  # 安全距离（像素）
    AVOID_WEIGHT = AVOID_ENEMY_WEIGHT  # 避敌权重系数

    # 是否有附身技能（如瑶的三技能）
    HAS_ATTACH_SKILL = False

    # 附身保护时长（秒），附身后在此时间内不轻易切换模态
    ATTACHED_PROTECT_DURATION = 5.0

    def __init__(
        self,
        skill_queue: Optional[Queue[Any]] = None,
        pause_event: Optional[threading.Event] = None,
    ):
        """
        初始化跟随型辅助

        参数：
            skill_queue: 技能逻辑队列，用于传递血量信息
            pause_event: 暂停事件，用于控制移动暂停/恢复
        """
        self.logger = setup_colored_logger(
            f"{self.HERO_NAME}_follow"
        )  # 创建带颜色的日志记录器
        self.skill_queue = skill_queue or Queue(
            maxsize=1
        )  # 技能队列，用于与技能逻辑通信
        self.pause_event = pause_event or threading.Event()  # 暂停事件，控制移动暂停

        # 模态状态
        self.current_mode = 2  # 默认使用模态2（血条跟随）
        self.last_check_time = time.time()  # 上次检查时间戳
        self.force_mode1_until = 0  # 强制使用模态1的截止时间

        # 附身状态
        self.last_attached_time = 0  # 上次附身时间戳
        self.is_attached = False  # 当前是否处于附身状态

        # 游戏状态
        self.game_active = False  # 游戏是否进行中
        self.no_detection_count = 0  # 连续未检测到游戏的计数

        # 最近的检测数据缓存
        self.last_model1_result = None  # 上次模态1检测结果
        self.last_model2_result = None  # 上次模态2检测结果

        # 健康信息
        self.last_health_info = None  # 上次发送的血量信息

        self.logger.info(f"[{self.HERO_NAME}] 跟随逻辑初始化完成")

    def find_closest_target(
        self, self_pos: Tuple[float, float], targets: List[Tuple]
    ) -> Optional[Tuple]:
        """
        找到最近的队友目标

        参数：
            self_pos: 自身位置 (x, y)
            targets: 队友列表 [(x, y, health), ...]

        返回：
            最近的队友信息或None
        """
        return find_closest_target(self_pos, targets)

    def calculate_move_direction(
        self,
        self_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        enemies: Optional[List[Tuple]] = None,
    ) -> Tuple[float, float]:
        """
        计算移动方向，考虑避敌
        如果有敌人且距离太近，会调整方向以远离敌人

        参数：
            self_pos: 自身位置 (x, y)
            target_pos: 目标位置 (x, y)
            enemies: 敌人列表 [(x, y, health), ...]

        返回：
            移动方向向量 (dx, dy)
        """
        dx = target_pos[0] - self_pos[0]  # 计算X方向向量
        dy = target_pos[1] - self_pos[1]  # 计算Y方向向量

        # 如果有敌人且距离太近，调整方向
        if enemies and self_pos:
            # 找到最近的敌人
            closest_enemy = min(
                enemies,
                key=lambda e: sqrt(
                    (self_pos[0] - e[0]) ** 2 + (self_pos[1] - e[1]) ** 2
                ),
            )
            # 计算与最近敌人的距离
            dist_enemy = sqrt(
                (self_pos[0] - closest_enemy[0]) ** 2
                + (self_pos[1] - closest_enemy[1]) ** 2
            )

            # 如果敌人距离小于安全距离，进行避敌调整
            if dist_enemy < self.SAFE_DISTANCE:
                # 计算远离敌人的方向向量
                dx_away = self_pos[0] - closest_enemy[0]
                dy_away = self_pos[1] - closest_enemy[1]

                # 混合方向：原方向 + 避敌方向 * 权重
                dx = dx + dx_away * self.AVOID_WEIGHT
                dy = dy + dy_away * self.AVOID_WEIGHT

                self.logger.debug(
                    f"[{self.HERO_NAME}] 避敌调整: 敌人距离={dist_enemy:.0f}px"
                )

        return dx, dy

    def _move_direction(self, dx: float, dy: float):
        """
        执行方向移动（使用键盘 WASD）
        根据方向向量的主方向按下对应按键

        参数：
            dx: X方向移动量
            dy: Y方向移动量
        """
        # 根据方向计算按键（选择绝对值较大的方向）
        if abs(dx) > abs(dy):
            # 主要X方向移动
            if dx > 0:
                press(KEY_MOVE_RIGHT)  # 按下右键，保持按住
            else:
                press(KEY_MOVE_LEFT)  # 按下左键，保持按住
        else:
            # 主要Y方向移动
            if dy > 0:
                press(KEY_MOVE_DOWN)  # 按下下键，保持按住
            else:
                press(KEY_MOVE_UP)  # 按下上键，保持按住

    def _release_all_keys(self):
        """释放所有移动按键（WASD）"""
        for key in [KEY_MOVE_UP, KEY_MOVE_LEFT, KEY_MOVE_DOWN, KEY_MOVE_RIGHT]:
            release(key)  # 释放按键

    def process_mode2_movement(self, detection: Dict) -> Dict:
        """
        处理模态2（血条跟随）的移动逻辑
        模态2通过检测血条来确定队友和敌人位置

        参数：
            detection: 检测结果字典

        返回：
            健康信息字典，包含血量、位置等信息
        """
        self_pos = detection.get("self_pos")  # 获取自身位置
        self_health = detection.get("self_health")  # 获取自身血量
        team_targets = detection.get("team_targets", [])  # 获取队友列表
        enemies = detection.get("enemies", [])  # 获取敌人列表

        # 判断是否附身状态：自身血量为空但位置存在（说明附身在队友身上）
        self.is_attached = self_health is None and self_pos is not None

        if self.is_attached:
            self.last_attached_time = time.time()  # 记录附身时间
            if self.HAS_ATTACH_SKILL:
                self.logger.debug(f"[{self.HERO_NAME}] 附身状态中")

        # 构建健康信息字典
        health_info = {
            "self_health": self_health,  # 自身血量
            "team_health": [t[2] for t in team_targets],  # 队友血量列表
            "enemy_health": [e[2] for e in enemies],  # 敌人血量列表
            "enemy_positions": [],  # 敌人距离列表（待计算）
            "team_positions": [],  # 队友距离列表（待计算）
            "is_attached": self.is_attached,  # 是否附身
        }

        # 计算距离信息（如果有自身位置）
        if self_pos:
            health_info["enemy_positions"] = [
                sqrt((self_pos[0] - e[0]) ** 2 + (self_pos[1] - e[1]) ** 2)
                for e in enemies
            ]
            health_info["team_positions"] = [
                sqrt((self_pos[0] - t[0]) ** 2 + (self_pos[1] - t[1]) ** 2)
                for t in team_targets
            ]

        # 如果暂停或附身，不执行移动
        if self.pause_event.is_set():
            self._release_all_keys()  # 释放所有按键
            return health_info

        if self.is_attached:
            self._release_all_keys()  # 附身时不需要移动
            return health_info

        # 正常跟随逻辑
        if self_pos and team_targets:
            closest = self.find_closest_target(self_pos, team_targets)  # 找到最近的队友
            if closest:
                dx, dy = self.calculate_move_direction(
                    self_pos, closest[:2], enemies
                )  # 计算移动方向
                distance = sqrt(dx**2 + dy**2)  # 计算距离

                if distance > self.FOLLOW_DISTANCE:
                    # 距离大于跟随阈值，执行移动（放大移动向量）
                    move_x = dx * MOVE_SCALE_FACTOR
                    move_y = dy * MOVE_SCALE_FACTOR
                    self.logger.debug(
                        f"[{self.HERO_NAME}] 跟随移动: 距离={distance:.0f}px"
                    )
                    self._move_direction(move_x, move_y)
                else:
                    # 距离足够近，停止移动
                    self.logger.debug(f"[{self.HERO_NAME}] 距离足够近，停止移动")
                    self._release_all_keys()
            else:
                self._release_all_keys()
        else:
            self._release_all_keys()

        return health_info

    def process_mode1_movement(self, detection: Dict) -> Dict:
        """
        处理模态1（小地图跟随）的移动逻辑
        模态1通过小地图检测自身和队友位置

        参数：
            detection: 检测结果字典

        返回：
            移动状态信息字典
        """
        g_center = detection.get("g_center")  # 获取自身在小地图的位置
        b_centers = detection.get("b_centers", [])  # 获取友方英雄列表
        r_centers = detection.get("r_centers", [])  # 获取敌方英雄列表

        # 构建健康信息（模态1没有血量数据）
        health_info = {
            "self_health": None,  # 模态1无法获取血量
            "team_health": [],  # 队友血量列表为空
            "enemy_health": [],  # 敌人血量列表为空
            "enemy_positions": [],  # 敌人距离列表为空
            "team_positions": [],  # 队友距离列表为空
            "is_attached": False,  # 模态1无法判断是否附身
            "game_detected": g_center is not None,  # 是否检测到游戏
        }

        if self.pause_event.is_set():
            self._release_all_keys()  # 暂停时释放按键
            return health_info

        if g_center and b_centers:
            # 使用 model1_astar_follow 的逻辑执行移动
            movement = model1_astar_follow.model1_movement_logic(detection)
            health_info["is_moving"] = movement.get(
                "is_moving", False
            )  # 记录是否正在移动
        else:
            self._release_all_keys()  # 没有目标时释放按键

        return health_info

    def check_mode_switch(
        self, model1_result: Optional[Tuple], model2_result: Optional[Tuple]
    ) -> int:
        """
        检查是否需要切换模态（模态1/模态2）
        根据检测结果决定使用哪种模态进行跟随

        参数：
            model1_result: 模态1检测结果
            model2_result: 模态2检测结果

        返回：
            建议的模态编号 (1 或 2)
        """
        current_time = time.time()

        # 每10秒检查一次高优先级切换（优先英雄检测）
        if current_time - self.last_check_time >= 10:
            self.last_check_time = current_time

            # 检查是否应该强制切换到模态1（检测到优先英雄时）
            if model2_result:
                detection = (
                    model2_result[0]
                    if isinstance(model2_result, tuple)
                    else model2_result
                )
                enemies = detection.get("enemies", [])

                # 如果没有敌人且模态1有结果，检查是否有优先英雄
                if not enemies and model1_result:
                    m1_det = (
                        model1_result[0]
                        if isinstance(model1_result, tuple)
                        else model1_result
                    )
                    b_centers = m1_det.get("b_centers", [])

                    # 检查是否有优先跟随的英雄（射手等）
                    for b in b_centers:
                        if len(b) > 2:
                            hero_name = model1_astar_follow.class_names.get(b[2], "")
                            if hero_name in model1_astar_follow.priority_heroes:
                                self.force_mode1_until = (
                                    current_time + 10
                                )  # 强制使用模态1 10秒
                                self.logger.info(
                                    f"[{self.HERO_NAME}] 检测到优先英雄，强制模态1"
                                )
                                return 1

        # 常规模态切换逻辑
        if current_time < self.force_mode1_until:
            return 1  # 在强制模态1期间

        # 附身保护期间不轻易切换模态
        in_attach_protection = self.HAS_ATTACH_SKILL and (
            current_time - self.last_attached_time < self.ATTACHED_PROTECT_DURATION
        )

        # 有队友血条时使用模态2（更精确）
        if model2_result:
            detection = (
                model2_result[0] if isinstance(model2_result, tuple) else model2_result
            )
            team_targets = detection.get("team_targets", [])
            if team_targets:
                return 2

        # 无队友血条且不在附身保护期，切换模态1
        if not in_attach_protection:
            return 1

        return self.current_mode

    def update_game_state(
        self, model1_result: Optional[Tuple], model2_result: Optional[Tuple]
    ) -> bool:
        """
        更新游戏状态（检测游戏是否进行中）

        参数：
            model1_result: 模态1检测结果
            model2_result: 模态2检测结果

        返回：
            游戏是否进行中（True/False）
        """
        # 检查两个模型是否都检测不到游戏画面
        model1_has_detection = False
        model2_has_detection = False

        if model1_result:
            m1_det = (
                model1_result[0] if isinstance(model1_result, tuple) else model1_result
            )
            model1_has_detection = m1_det.get("g_center") is not None

        if model2_result:
            m2_det = (
                model2_result[0] if isinstance(model2_result, tuple) else model2_result
            )
            model2_has_detection = m2_det.get("self_pos") is not None

        if not model1_has_detection and not model2_has_detection:
            # 两个模型都未检测到，增加未检测计数
            self.no_detection_count += 1
            if self.no_detection_count >= 10:
                # 连续10次未检测到，认为游戏未开始或已结束
                if self.game_active:
                    self.game_active = False
                    self.logger.info(f"[{self.HERO_NAME}] 游戏未开始/已结束")
                # 释放所有按键
                self._release_all_keys()
                model1_astar_follow.release_all_keys()
                return False
        else:
            # 至少有一个模型检测到游戏
            if self.no_detection_count > 0:
                self.no_detection_count = 0  # 重置计数
            if not self.game_active:
                self.game_active = True
                self.logger.info(f"[{self.HERO_NAME}] 游戏进行中")

        return self.game_active

    def send_health_info(
        self, health_info: Dict, status_queue: Optional[Queue[Any]] = None
    ):
        """
        发送健康信息到技能队列和状态队列
        只在信息变化时发送，避免重复

        参数：
            health_info: 健康信息字典
            status_queue: 状态队列（可选）
        """
        if health_info != self.last_health_info:
            safe_queue_put(self.skill_queue, health_info)  # 发送到技能队列
            if status_queue:
                safe_queue_put(status_queue, health_info)  # 发送到状态队列
            self.last_health_info = health_info  # 更新上次发送的信息

    @abstractmethod
    def get_skill_logic_function(self) -> Callable[[Queue[Any]], None]:
        """
        获取英雄特定的技能逻辑函数
        子类必须实现此方法

        返回：
            技能逻辑运行函数
        """
        pass

    def run(self, status_queue: Optional[Queue[Any]] = None):
        """
        运行跟随逻辑主循环
        子类可以覆盖此方法实现自定义逻辑

        参数：
            status_queue: 状态队列，用于发送状态信息
        """
        self.logger.info(f"[{self.HERO_NAME}] 跟随逻辑主循环启动")

        # 子类应该实现具体的运行逻辑
        raise NotImplementedError("子类需要实现 run 方法")


# 瑶的跟随逻辑类
class YaoFollowLogic(BaseSupportHero):
    """瑶的跟随逻辑"""

    HERO_NAME = "瑶"
    HAS_ATTACH_SKILL = True  # 瑶有三技能可以附身队友
    FOLLOW_DISTANCE = 50  # 跟随距离更近（瑶需要贴近队友）

    def get_skill_logic_function(self) -> Callable[[Queue[Any]], None]:
        from wzry_ai.skills.yao_skill_logic_v2 import YaoSkillLogic

        return lambda q: None  # V2版本使用类方式，此处返回空函数兼容处理


# 蔡文姬的跟随逻辑类
class CaiwenjiFollowLogic(BaseSupportHero):
    """蔡文姬的跟随逻辑"""

    HERO_NAME = "蔡文姬"
    HAS_ATTACH_SKILL = False  # 蔡文姬没有附身技能
    FOLLOW_DISTANCE = 80  # 蔡文姬保持稍远的距离（技能有范围）
    SAFE_DISTANCE = 250  # 更注重安全距离（蔡文姬较脆弱）

    def get_skill_logic_function(self) -> Callable[[Queue[Any]], None]:
        from wzry_ai.skills.caiwenji_skill_logic_v2 import CaiwenjiSkillLogic

        return lambda q: None  # V2版本使用类方式，此处返回空函数兼容处理


# 明世隐的跟随逻辑类
class MingshiyinFollowLogic(BaseSupportHero):
    """明世隐的跟随逻辑"""

    HERO_NAME = "明世隐"
    HAS_ATTACH_SKILL = False  # 明世隐没有附身技能，但有连接技能
    FOLLOW_DISTANCE = 100  # 保持中等距离
    SAFE_DISTANCE = 200  # 安全距离

    # 明世隐特有属性：链接状态
    HAS_LINK_SKILL = True  # 明世隐有链接技能
    LINK_RANGE = 600  # 链接技能范围（像素）

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_linked = False  # 是否已链接队友
        self.linked_target = None  # 当前链接的目标

    def get_skill_logic_function(self) -> Callable[[Queue[Any]], None]:
        from wzry_ai.skills.mingshiyin_skill_logic_v2 import MingshiyinSkillLogic

        return lambda q: None  # V2版本使用类方式，此处返回空函数兼容处理


# 英雄工厂函数：根据英雄名称创建对应的跟随逻辑实例
def create_support_hero(
    hero_name: str,
    skill_queue: Optional[Queue[Any]] = None,
    pause_event: Optional[threading.Event] = None,
) -> BaseSupportHero:
    """
    根据英雄名称创建对应的跟随逻辑实例

    参数：
        hero_name: 英雄名称 ("瑶", "蔡文姬", "明世隐")
        skill_queue: 技能队列（可选）
        pause_event: 暂停事件（可选）

    返回：
        对应的跟随逻辑实例

    异常：
        ValueError: 如果英雄名称不在支持列表中
    """
    hero_map = {
        "瑶": YaoFollowLogic,
        "蔡文姬": CaiwenjiFollowLogic,
        "明世隐": MingshiyinFollowLogic,
    }

    hero_class = hero_map.get(hero_name)
    if hero_class is None:
        raise ValueError(f"未知的辅助英雄: {hero_name}")

    return hero_class(skill_queue=skill_queue, pause_event=pause_event)


# 支持的辅助英雄列表
SUPPORTED_SUPPORT_HEROES = ["瑶", "蔡文姬", "明世隐"]


# 程序入口点
if __name__ == "__main__":
    # 测试代码：创建各英雄实例并打印配置信息
    from queue import Queue
    import threading

    # 创建测试实例
    for hero_name in SUPPORTED_SUPPORT_HEROES:
        try:
            hero = create_support_hero(hero_name)
            print(f"创建 {hero.HERO_NAME} 成功")
            print(f"  - 跟随距离: {hero.FOLLOW_DISTANCE}")
            print(f"  - 安全距离: {hero.SAFE_DISTANCE}")
            print(f"  - 附身技能: {hero.HAS_ATTACH_SKILL}")
        except (KeyError, ValueError, AttributeError) as e:
            print(f"创建 {hero_name} 失败: {e}")
