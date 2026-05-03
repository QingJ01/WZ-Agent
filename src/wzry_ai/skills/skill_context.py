"""
技能上下文模块 - 封装游戏状态数据
为技能判断提供统一的数据接口，所有技能在判断是否可释放时都需要使用此上下文

[弃用说明] 此模块属于旧版技能体系，当前实际使用的技能逻辑已迁移到
hero_skill_logic_base.py + 各英雄的 *_skill_logic_v2.py 文件。
本模块保留但不再被核心逻辑直接使用。
"""

# 导入类型提示相关的类
from typing import Dict, List, Optional, Any
# Dict: 字典类型，用于键值对数据
# List: 列表类型，用于有序集合
# Optional: 可选类型，表示值可能为None
# Any: 任意类型，用于不确定类型的数据

# 从dataclasses模块导入装饰器和字段工厂
from dataclasses import dataclass, field
# dataclass: 数据类装饰器，自动生成__init__等方法
# field: 字段定义，用于设置默认值工厂

# 导入时间模块
import time
# time: 提供时间相关功能，如获取当前时间戳


# 使用dataclass装饰器定义数据类，自动生成初始化等方法
@dataclass
class SkillContext:
    """
    技能上下文类 - 包含释放技能所需的所有游戏状态信息

    该类封装了游戏中与技能释放相关的所有状态数据，
    包括自身状态、队友状态、敌人状态、附身状态等，
    为技能系统提供统一的数据访问接口。

    参数说明：
        所有参数都有默认值，创建实例时可根据需要传入特定值

    返回值说明：
        实例化后返回SkillContext对象，可通过属性访问各项状态
    """

    # ========== 基础状态字段 ==========
    self_health: Optional[int] = (
        None  # 自身血量值，整数类型，None表示处于附身状态无法获取自身血量
    )
    team_health: List[Any] = field(
        default_factory=list
    )  # 队友血量列表，存储每个队友的血量信息
    enemy_health: List[Any] = field(
        default_factory=list
    )  # 敌人血量列表，存储每个敌人的血量信息
    team_positions: List[float] = field(
        default_factory=list
    )  # 队友距离列表，存储每个队友与自身的距离（像素）
    enemy_positions: List[float] = field(
        default_factory=list
    )  # 敌人距离列表，存储每个敌人与自身的距离（像素）

    # ========== 附身状态字段（新版：优先使用is_attached字段判断） ==========
    is_attached: bool = (
        False  # 是否处于附身状态，True表示已附身到队友身上，由model2_detector检测提供
    )
    yao_state: str = "unknown"  # 瑶的详细状态字符串：normal（正常）/attached（附身）/deer（鹿灵）/unknown（未知）
    attached_hero_name: Optional[str] = (
        None  # 附身的英雄名称，字符串类型，None表示未附身或未知
    )
    attach_start_time: Optional[float] = (
        None  # 附身开始时间，时间戳（秒），用于计算附身持续时间
    )

    # ========== 扩展信息字段 ==========
    priority_teammates: List[str] = field(
        default_factory=list
    )  # 优先队友列表，存储需要优先保护或附身的队友英雄名称
    teamfight_detected: bool = False  # 是否检测到团战，True表示当前处于团战状态
    escape_needed: bool = False  # 是否需要逃跑，True表示当前处于需要逃跑的紧急状态

    # ========== 时间戳字段 ==========
    timestamp: float = field(
        default_factory=time.time
    )  # 上下文创建时间戳，默认为当前时间

    def __post_init__(self):
        """
        数据类初始化后的后置处理方法
        用于处理兼容旧逻辑：如果is_attached为False但self_health为None，则推断为附身状态
        """
        # 兼容旧逻辑：如果is_attached为False但self_health为None，则设置为True
        if not self.is_attached and self.self_health is None:
            self.is_attached = True  # 设置附身状态为True
            self.yao_state = "attached"  # 设置瑶的状态为附身

    @property
    def has_enemy(self) -> bool:
        """
        属性：是否有敌人

        返回值说明：
            bool: True表示enemy_health列表不为空，存在敌人；False表示没有检测到敌人
        """
        return len(self.enemy_health) > 0  # 判断敌人血量列表长度是否大于0

    @property
    def has_teammate(self) -> bool:
        """
        属性：是否有队友

        返回值说明：
            bool: True表示team_health列表不为空，存在队友；False表示没有检测到队友
        """
        return len(self.team_health) > 0  # 判断队友血量列表长度是否大于0

    @property
    def enemy_count(self) -> int:
        """
        属性：敌人数量

        返回值说明：
            int: 返回enemy_health列表的长度，即检测到的敌人数量
        """
        return len(self.enemy_health)  # 返回敌人血量列表的长度

    @property
    def teammate_count(self) -> int:
        """
        属性：队友数量

        返回值说明：
            int: 返回team_health列表的长度，即检测到的队友数量
        """
        return len(self.team_health)  # 返回队友血量列表的长度

    def get_closest_enemy_distance(self) -> Optional[float]:
        """
        获取最近敌人的距离

        返回值说明：
            Optional[float]: 返回enemy_positions列表中的最小值（最近距离），
                            如果没有敌人则返回None
        """
        if not self.enemy_positions:  # 检查敌人距离列表是否为空
            return None  # 没有敌人时返回None
        return min(self.enemy_positions)  # 返回列表中的最小值，即最近敌人的距离

    def get_closest_teammate_distance(self) -> Optional[float]:
        """
        获取最近队友的距离

        返回值说明：
            Optional[float]: 返回team_positions列表中的最小值（最近距离），
                            如果没有队友则返回None
        """
        if not self.team_positions:  # 检查队友距离列表是否为空
            return None  # 没有队友时返回None
        return min(self.team_positions)  # 返回列表中的最小值，即最近队友的距离

    def _get_health_value(self, h: Any) -> int:
        """
        统一获取血量值的内部辅助方法

        参数说明：
            h: 血量数据，可能是字典或数值类型

        返回值说明：
            int: 返回解析后的血量整数值，默认为100
        """
        if isinstance(h, dict):  # 判断数据是否为字典类型
            return h.get("health", 100)  # 从字典中获取health字段，默认值为100
        return int(h) if h is not None else 100  # 转换为整数，None时返回默认值100

    def is_self_low_hp(self, threshold: int = 50) -> bool:
        """
        判断自身血量是否低于阈值

        参数说明：
            threshold: 血量阈值，默认为50，低于此值视为低血量

        返回值说明：
            bool: True表示自身血量低于阈值，False表示血量正常或处于附身状态
        """
        if (
            self.is_attached or self.self_health is None
        ):  # 检查是否处于附身状态或血量未知
            return False  # 附身状态或血量未知时返回False
        return self.self_health < threshold  # 比较自身血量与阈值

    def has_teammate_low_hp(self, threshold: int = 50) -> bool:
        """
        判断是否有队友血量低于阈值

        参数说明：
            threshold: 血量阈值，默认为50，低于此值视为低血量

        返回值说明：
            bool: True表示至少有一个队友血量低于阈值，False表示所有队友血量正常
        """
        for h in self.team_health:  # 遍历所有队友的血量数据
            if self._get_health_value(h) < threshold:  # 检查是否有队友血量低于阈值
                return True  # 发现低血量队友，返回True
        return False  # 遍历完成，没有发现低血量队友，返回False

    def get_lowest_teammate_hp(self) -> Optional[int]:
        """
        获取血量最低的队友的血量值

        返回值说明：
            Optional[int]: 返回所有队友中最低的血量值，如果没有队友则返回None
        """
        if not self.team_health:  # 检查队友列表是否为空
            return None  # 没有队友时返回None
        # 使用生成器表达式遍历所有队友血量，返回最小值
        return min(self._get_health_value(h) for h in self.team_health)

    def has_priority_teammate_in_range(self, max_distance: float) -> bool:
        """
        判断优先队友是否在指定范围内

        参数说明：
            max_distance: 最大距离阈值，单位像素

        返回值说明：
            bool: True表示有队友在范围内，False表示没有队友或都在范围外

        注意事项：
            当前为简化实现，假设team_positions对应的就是优先队友
            实际实现可能需要根据英雄名称匹配
        """
        if not self.team_positions:  # 检查队友位置列表是否为空
            return False  # 没有队友时返回False
        return min(self.team_positions) <= max_distance  # 判断最近队友是否在范围内

    def is_self_in_danger(self) -> bool:
        """
        判断自身是否处于危险状态

        返回值说明：
            bool: True表示自身处于危险中（敌人很近且血量低），False表示安全

        危险判断逻辑：
            1. 检查是否处于附身状态
            2. 检查是否有敌人
            3. 检查最近敌人距离是否小于200像素
            4. 检查自身血量是否低于40
        """
        if self.is_attached:  # 检查是否处于附身状态
            return False  # 附身状态下自身不处于危险
        if not self.has_enemy:  # 检查是否有敌人
            return False  # 没有敌人时不处于危险
        closest_enemy = self.get_closest_enemy_distance()  # 获取最近敌人的距离
        if closest_enemy is None:  # 检查距离值是否有效
            return False  # 距离无效时不处于危险
        # 敌人很近（小于200像素）且自身血量低（低于40）时判定为危险
        return closest_enemy < 200 and self.is_self_low_hp(40)

    def is_escape_state(self) -> bool:
        """
        判断当前是否需要逃跑

        返回值说明：
            bool: True表示需要逃跑，False表示不需要逃跑
        """
        return self.escape_needed  # 直接返回escape_needed字段的值

    def get_attach_duration(self) -> Optional[float]:
        """
        获取附身持续时间

        返回值说明：
            Optional[float]: 返回附身持续的秒数，如果没有附身或开始时间未知则返回None
        """
        if (
            not self.is_attached or self.attach_start_time is None
        ):  # 检查是否处于附身状态且开始时间有效
            return None  # 未附身或时间未知时返回None
        return time.time() - self.attach_start_time  # 计算当前时间与附身开始时间的差值

    @classmethod
    def from_health_info(
        cls, health_info: Dict, priority_teammates: Optional[List[str]] = None
    ) -> "SkillContext":
        """
        类方法：从health_info字典创建SkillContext实例

        参数说明：
            health_info: 包含游戏状态的字典，通常由状态检测模块提供
                        包含字段：self_health, team_health, enemy_health等
            priority_teammates: 优先队友列表，字符串列表类型，默认为None

        返回值说明：
            SkillContext: 根据health_info数据创建的SkillContext实例

        使用场景：
            当从状态检测模块获取到health_info字典后，使用此方法快速创建上下文对象
        """
        context = cls(
            self_health=health_info.get("self_health"),  # 从字典获取自身血量
            team_health=health_info.get(
                "team_health", []
            ),  # 从字典获取队友血量，默认为空列表
            enemy_health=health_info.get(
                "enemy_health", []
            ),  # 从字典获取敌人血量，默认为空列表
            team_positions=health_info.get(
                "team_positions", []
            ),  # 从字典获取队友位置，默认为空列表
            enemy_positions=health_info.get(
                "enemy_positions", []
            ),  # 从字典获取敌人位置，默认为空列表
            is_attached=health_info.get(
                "is_attached", False
            ),  # 从字典获取附身状态，默认为False，由model2_detector提供
            yao_state=health_info.get(
                "yao_state", "unknown"
            ),  # 从字典获取瑶的状态，默认为unknown
            priority_teammates=priority_teammates
            or [],  # 设置优先队友列表，None时默认为空列表
        )
        return context  # 返回创建的上下文实例

    def to_dict(self) -> Dict:
        """
        将SkillContext实例转换为字典格式

        返回值说明：
            Dict: 包含所有状态数据的字典，便于序列化或日志记录

        包含字段：
            - self_health: 自身血量
            - team_health: 队友血量列表
            - enemy_health: 敌人血量列表
            - team_positions: 队友位置列表
            - enemy_positions: 敌人位置列表
            - is_attached: 附身状态
            - has_enemy: 是否有敌人
            - has_teammate: 是否有队友
            - enemy_count: 敌人数量
            - closest_enemy: 最近敌人距离
            - closest_teammate: 最近队友距离
        """
        return {
            "self_health": self.self_health,  # 自身血量值
            "team_health": self.team_health,  # 队友血量列表
            "enemy_health": self.enemy_health,  # 敌人血量列表
            "team_positions": self.team_positions,  # 队友距离列表
            "enemy_positions": self.enemy_positions,  # 敌人距离列表
            "is_attached": self.is_attached,  # 附身状态标志
            "has_enemy": self.has_enemy,  # 是否有敌人（通过属性计算）
            "has_teammate": self.has_teammate,  # 是否有队友（通过属性计算）
            "enemy_count": self.enemy_count,  # 敌人数量（通过属性计算）
            "closest_enemy": self.get_closest_enemy_distance(),  # 最近敌人距离（通过方法计算）
            "closest_teammate": self.get_closest_teammate_distance(),  # 最近队友距离（通过方法计算）
        }
