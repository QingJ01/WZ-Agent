"""
世界状态模块 - 聚合检测结果为统一的数据结构

功能说明：
    本模块聚合 model1 和 model2 的检测结果为统一的 WorldState 数据结构。
    提供 EntityState 和 WorldState 数据类，以及 WorldStateBuilder 构建器。

数据流：
    model1_result + model2_result -> WorldStateBuilder -> WorldState
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from math import sqrt
import time
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)

Position = Tuple[int, int]
HistoryEntry = Tuple[Position, int, float]


@dataclass
class EntityState:
    """
    实体状态数据类

    表示游戏中的一个实体（英雄），包含位置、血量、速度等信息。

    属性说明：
        entity_id: 实体标识符（英雄名或 "unknown_N"）
        pos: 当前坐标 (x, y)，使用屏幕像素坐标
        health: 血量百分比 0-100
        health_delta: 血量变化率（%/秒），负值表示掉血
        velocity: 速度向量 (vx, vy) 像素/秒
        distance_to_self: 与自身的距离（像素）
        is_approaching: 是否在接近自身
        lane_role: 分路角色（adc/mid/top/jungle/support/unknown）
    """

    entity_id: str  # 标识（英雄名或 "unknown_N"）
    pos: Position  # 当前坐标 (x, y)，使用屏幕像素坐标
    health: int  # 血量百分比 0-100
    health_delta: float = 0.0  # 血量变化率（%/秒），负值=掉血
    velocity: Tuple[float, float] = (0.0, 0.0)  # 速度向量 (vx, vy) 像素/秒
    distance_to_self: float = 0.0  # 与自身的距离（像素）
    is_approaching: bool = False  # 是否在接近自身
    lane_role: str = "unknown"  # 分路角色（adc/mid/top/jungle/support/unknown）


@dataclass
class WorldState:
    """
    世界状态数据类

    聚合当前游戏帧的所有感知信息。

    属性说明：
        timestamp: 构建时间戳
        self_pos: 自身位置 (x, y)
        self_health: 自身血量百分比
        self_health_delta: 自身血量变化率
        is_attached: 是否附身（瑶的附身状态）
        teammates: 队友列表
        enemies: 敌人列表
        enemy_count: 附近敌人数量
        teammate_count: 附近队友数量
    """

    timestamp: float  # 构建时间戳
    self_pos: Optional[Position] = None  # 自身位置 (x, y)
    self_health: Optional[int] = None  # 自身血量百分比
    self_health_delta: float = 0.0  # 自身血量变化率
    is_attached: bool = False  # 是否附身
    teammates: List[EntityState] = field(default_factory=list)
    enemies: List[EntityState] = field(default_factory=list)
    enemy_count: int = 0  # 附近敌人数量
    teammate_count: int = 0  # 附近队友数量


class WorldStateBuilder:
    """
    世界状态构建器

    核心类，负责将 model1 和 model2 的检测结果聚合为统一的 WorldState。
    缓存上一帧数据用于计算速度和血量变化率。

    使用方法：
        builder = WorldStateBuilder()
        world_state = builder.build(model1_result, model2_result, current_time)

    属性说明：
        _prev_self: 上一帧自身状态 (pos, health, timestamp)
        _prev_teammates: 上一帧队友状态列表 [(pos, health, timestamp), ...]
        _prev_enemies: 上一帧敌人状态列表 [(pos, health, timestamp), ...]
    """

    # 实体匹配距离阈值（像素）
    ENTITY_MATCH_THRESHOLD = 100

    # 分路名称映射
    LANE_ROLE_MAP = {
        "lane_top": "top",
        "lane_jungle": "jungle",
        "lane_mid": "mid",
        "lane_adc": "adc",
        "lane_support": "support",
    }

    def __init__(self):
        """
        初始化世界状态构建器

        初始化缓存结构，用于存储上一帧的数据。
        """
        self._prev_self: Optional[HistoryEntry] = None
        self._prev_teammates: List[HistoryEntry] = []
        self._prev_enemies: List[HistoryEntry] = []
        logger.debug("WorldStateBuilder 初始化完成")

    def build(
        self,
        model1_result: Optional[Dict],
        model2_result: Optional[Dict],
        current_time: float,
    ) -> WorldState:
        """
        构建世界状态

        将 model1 和 model2 的检测结果聚合为 WorldState 对象。

        参数说明：
            model1_result: model1 检测结果，结构如下：
                {
                    'g_center': (x, y),           # 自身位置
                    'b_centers': [(x,y,class_id), ...],  # 队友位置
                    'r_centers': [(x,y,class_id), ...],  # 敌人位置
                    'class_names': {class_id: "hero_name_blue/red"},
                    'self_class_id': int
                }
            model2_result: model2 检测结果，结构如下：
                {
                    'self_pos': (x, y),           # 自身位置
                    'self_health': int/None,      # 自身血量，None 表示附身
                    'team_targets': [(x,y,health), ...],  # 队友
                    'enemies': [(x,y,health), ...],       # 敌人
                    'frame': ndarray
                }
            current_time: 当前时间戳（秒）

        返回值说明：
            WorldState: 构建好的世界状态对象
        """
        # 如果 model2_result 为 None，返回空的世界状态
        if model2_result is None:
            return WorldState(timestamp=current_time)

        # 提取自身信息
        self_pos: Optional[Position] = model2_result.get("self_pos")
        self_health: Optional[int] = model2_result.get("self_health")

        # 判断是否附身：self_health 为 None 但 self_pos 不为 None
        is_attached = self_health is None and self_pos is not None

        # 如果附身，设置默认血量（无法获取实际血量）
        effective_self_health: Optional[int] = self_health
        if is_attached:
            effective_self_health = 100  # 附身时无法获取自身血量，设为默认值

        # 计算自身速度和血量变化率
        self_velocity = (0.0, 0.0)
        self_health_delta = 0.0

        if (
            self_pos is not None
            and effective_self_health is not None
            and self._prev_self is not None
        ):
            prev_pos, prev_health, prev_time = self._prev_self
            dt = current_time - prev_time

            if dt >= 0.001:  # 防止除零
                # 计算速度
                self_velocity = (
                    (self_pos[0] - prev_pos[0]) / dt,
                    (self_pos[1] - prev_pos[1]) / dt,
                )
                # 计算血量变化率
                self_health_delta = (effective_self_health - prev_health) / dt

        # 构建队友列表
        teammates = self._build_entity_list(
            model2_result.get("team_targets", []),
            model1_result.get("b_centers", []) if model1_result else [],
            model1_result.get("class_names", {}) if model1_result else {},
            self_pos,
            current_time,
            self._prev_teammates,
            is_teammate=True,
        )

        # 构建敌人列表
        enemies = self._build_entity_list(
            model2_result.get("enemies", []),
            model1_result.get("r_centers", []) if model1_result else [],
            model1_result.get("class_names", {}) if model1_result else {},
            self_pos,
            current_time,
            self._prev_enemies,
            is_teammate=False,
        )

        # 更新缓存
        if self_pos is not None:
            self._prev_self = (
                self_pos,
                effective_self_health if effective_self_health is not None else 0,
                current_time,
            )
        self._prev_teammates = [(e.pos, e.health, current_time) for e in teammates]
        self._prev_enemies = [(e.pos, e.health, current_time) for e in enemies]

        # 创建并返回 WorldState
        world_state = WorldState(
            timestamp=current_time,
            self_pos=self_pos,
            self_health=effective_self_health,
            self_health_delta=self_health_delta,
            is_attached=is_attached,
            teammates=teammates,
            enemies=enemies,
            enemy_count=len(enemies),
            teammate_count=len(teammates),
        )

        return world_state

    def _build_entity_list(
        self,
        m2_entities: List,
        m1_entities: List,
        class_names: Dict,
        self_pos: Optional[Position],
        current_time: float,
        prev_entities: List[HistoryEntry],
        is_teammate: bool,
    ) -> List[EntityState]:
        """
        构建实体列表

        根据 model2 和 model1 的检测结果构建 EntityState 列表。

        参数说明：
            m2_entities: model2 检测的实体列表 [(x, y, health), ...]
            m1_entities: model1 检测的实体列表 [(x, y, class_id), ...]
            class_names: model1 的类别名称映射 {class_id: "hero_name"}
            self_pos: 自身位置 (x, y)
            current_time: 当前时间戳
            prev_entities: 上一帧实体状态列表 [(pos, health, timestamp), ...]
            is_teammate: 是否为队友（True=队友，False=敌人）

        返回值说明：
            List[EntityState]: 构建好的实体状态列表
        """
        result = []
        used_prev_indices = set()

        for idx, entity in enumerate(m2_entities):
            if len(entity) < 3:
                continue

            pos = (entity[0], entity[1])
            health = entity[2]

            # 计算与自身的距离
            distance_to_self = 0.0
            if self_pos is not None:
                distance_to_self = sqrt(
                    (pos[0] - self_pos[0]) ** 2 + (pos[1] - self_pos[1]) ** 2
                )

            # 尝试匹配上一帧的实体
            matched_prev = self._match_previous_entity(
                pos, prev_entities, used_prev_indices
            )

            # 计算速度和血量变化率
            velocity = (0.0, 0.0)
            health_delta = 0.0
            prev_distance = distance_to_self

            if matched_prev is not None:
                prev_pos, prev_health, prev_time = matched_prev
                dt = current_time - prev_time

                if dt >= 0.001:  # 防止除零
                    velocity = (
                        (pos[0] - prev_pos[0]) / dt,
                        (pos[1] - prev_pos[1]) / dt,
                    )
                    health_delta = (health - prev_health) / dt
                    prev_distance = (
                        sqrt(
                            (prev_pos[0] - self_pos[0]) ** 2
                            + (prev_pos[1] - self_pos[1]) ** 2
                        )
                        if self_pos is not None
                        else 0.0
                    )

            # 判断是否接近自身
            is_approaching = distance_to_self < prev_distance

            # 获取实体ID（英雄名）
            entity_id = self._get_entity_id(idx, pos, m1_entities, class_names)

            # 推断分路角色
            lane_role = self._infer_lane_role(entity_id)

            # 创建 EntityState
            entity_state = EntityState(
                entity_id=entity_id,
                pos=pos,
                health=health,
                health_delta=health_delta,
                velocity=velocity,
                distance_to_self=distance_to_self,
                is_approaching=is_approaching,
                lane_role=lane_role,
            )

            result.append(entity_state)

        return result

    def _match_previous_entity(
        self, pos: Position, prev_entities: List[HistoryEntry], used_indices: set[int]
    ) -> Optional[HistoryEntry]:
        """
        匹配上一帧的实体

        使用最近距离匹配算法找到当前实体在上一帧中的对应实体。

        参数说明：
            pos: 当前实体位置 (x, y)
            prev_entities: 上一帧实体状态列表 [(pos, health, timestamp), ...]
            used_indices: 已使用的上一帧实体索引集合

        返回值说明：
            Optional[Tuple]: 匹配的上一帧实体状态 (pos, health, timestamp)，
                            未找到则返回 None
        """
        min_distance = float("inf")
        best_match = None
        best_idx = -1

        for idx, (prev_pos, prev_health, prev_time) in enumerate(prev_entities):
            if idx in used_indices:
                continue

            distance = sqrt((pos[0] - prev_pos[0]) ** 2 + (pos[1] - prev_pos[1]) ** 2)

            if distance < min_distance and distance < self.ENTITY_MATCH_THRESHOLD:
                min_distance = distance
                best_match = (prev_pos, prev_health, prev_time)
                best_idx = idx

        if best_match is not None:
            used_indices.add(best_idx)

        return best_match

    def _get_entity_id(
        self, idx: int, pos: Position, m1_entities: List, class_names: Dict
    ) -> str:
        """
        获取实体标识符

        尝试从 model1 的检测结果中获取实体ID（英雄名）。
        如果无法匹配，返回 "unknown_N" 格式。

        参数说明：
            idx: 实体索引
            pos: 实体位置 (x, y)
            m1_entities: model1 检测的实体列表 [(x, y, class_id), ...]
            class_names: model1 的类别名称映射 {class_id: "hero_name"}

        返回值说明：
            str: 实体标识符（英雄名或 "unknown_N"）
        """
        # 尝试匹配 model1 的实体
        for m1_entity in m1_entities:
            if len(m1_entity) < 3:
                continue

            m1_pos = (m1_entity[0], m1_entity[1])
            class_id = m1_entity[2]

            # 计算距离
            distance = sqrt((pos[0] - m1_pos[0]) ** 2 + (pos[1] - m1_pos[1]) ** 2)

            # 如果距离足够近，认为是同一个实体
            if distance < self.ENTITY_MATCH_THRESHOLD:
                class_name = class_names.get(class_id, f"unknown_{idx}")
                # 去掉 _blue 或 _red 后缀
                if "_" in class_name:
                    return class_name.rsplit("_", 1)[0]
                return class_name

        # 无法匹配，返回 unknown 格式
        return f"unknown_{idx}"

    def _infer_lane_role(self, entity_id: str) -> str:
        """
        推断实体的分路角色

        根据实体ID（英雄名）推断其分路角色。

        参数说明：
            entity_id: 实体标识符（英雄拼音名）

        返回值说明：
            str: 分路角色（adc/mid/top/jungle/support/unknown）
        """
        if entity_id.startswith("unknown_"):
            return "unknown"

        try:
            # 导入必要的模块
            from wzry_ai.config.heroes.mapping import get_hero_chinese, LANE_HEROES

            # 获取中文名
            chinese_name = get_hero_chinese(entity_id)

            # 在 LANE_HEROES 中查找
            for lane_key, heroes in LANE_HEROES.items():
                if chinese_name in heroes:
                    return self.LANE_ROLE_MAP.get(lane_key, "unknown")

            return "unknown"
        except (KeyError, AttributeError, ValueError) as e:
            logger.debug(f"推断分路角色失败: {entity_id}, 错误: {e}")
            return "unknown"

    def reset(self):
        """
        重置构建器状态

        清除所有缓存数据，用于重新开始或错误恢复。
        """
        self._prev_self = None
        self._prev_teammates = []
        self._prev_enemies = []
        logger.debug("WorldStateBuilder 已重置")
