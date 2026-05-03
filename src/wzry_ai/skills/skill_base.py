"""
技能基类模块 - 定义所有技能的抽象基类和枚举类型
该模块是技能系统的核心，提供技能类型定义、配置类和抽象基类

[弃用说明] 此模块属于旧版技能体系，当前实际使用的技能逻辑已迁移到
hero_skill_logic_base.py + 各英雄的 *_skill_logic_v2.py 文件。
本模块保留以供 hero_skill_configs.py 中的 SkillConfig 数据结构使用。
"""

# 从abc模块导入抽象基类相关工具
from abc import ABC, abstractmethod
# ABC: 抽象基类，用于定义抽象类
# abstractmethod: 抽象方法装饰器，标记必须在子类实现的方法

# 从enum模块导入枚举相关工具
from enum import Enum, auto
# Enum: 枚举基类，用于创建枚举类型
# auto: 自动赋值，用于自动分配枚举值

# 导入类型提示相关类
from typing import Dict, List, Optional, Any, Callable
# Dict: 字典类型
# List: 列表类型
# Optional: 可选类型
# Any: 任意类型
# Callable: 可调用类型

# 从dataclasses模块导入数据类装饰器
from dataclasses import dataclass, field
# dataclass: 数据类装饰器，自动生成__init__等方法

# 导入时间模块
import time
# time: 提供时间相关功能

# 导入日志模块
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SkillType(Enum):
    """
    技能类型枚举类

    功能描述：
        定义游戏中所有技能的分类类型
        用于区分不同功能的技能，便于统一管理和处理
    """

    DAMAGE = "damage"  # 伤害技能类型，对敌人造成伤害
    CONTROL = "control"  # 控制技能类型，眩晕、击飞、减速等效果
    HEAL_SHIELD = "heal_shield"  # 治疗/护盾技能类型，恢复血量或提供护盾
    BUFF = "buff"  # 增益/Buff技能类型，为队友提供属性加成
    ATTACH = "attach"  # 位移/附身技能类型，附身到队友身上
    ACTIVE_ITEM = "active_item"  # 辅助装备主动技能类型，救赎之翼、奔狼纹章等
    SUMMONER = "summoner"  # 召唤师技能类型，治疗、闪现、眩晕等


class TriggerCondition(Enum):
    """
    技能触发条件枚举类

    功能描述：
        定义技能可以触发的各种条件
        技能可以根据配置的条件列表判断是否满足释放条件
    """

    # ========== 敌人相关条件 ==========
    HAS_ENEMY = "has_enemy"  # 有敌人在视野中
    ENEMY_IN_RANGE = "enemy_in_range"  # 敌人在技能范围内
    ENEMY_COUNT_GTE = "enemy_count_gte"  # 敌人数量大于等于阈值
    ENEMY_CLOSEST_DIST = "enemy_closest_dist"  # 最近敌人距离小于阈值

    # ========== 队友相关条件 ==========
    HAS_TEAMMATE = "has_teammate"  # 有队友在视野中
    TEAMMATE_IN_RANGE = "teammate_in_range"  # 队友在技能范围内
    TEAMMATE_LOW_HP = "teammate_low_hp"  # 有队友血量低于阈值
    TEAMMATE_PRIORITY = "teammate_priority"  # 优先队友在范围内

    # ========== 自身相关条件 ==========
    SELF_LOW_HP = "self_low_hp"  # 自身血量低于阈值
    SELF_ATTACHED = "self_attached"  # 自身处于附身状态
    SELF_NOT_ATTACHED = "self_not_attached"  # 自身未处于附身状态
    SELF_IN_DANGER = "self_in_danger"  # 自身处于危险状态

    # ========== 战斗状态条件 ==========
    IN_TEAMFIGHT = "in_teamfight"  # 处于团战状态
    PEACE_STATE = "peace_state"  # 处于脱战/和平状态
    ESCAPE_STATE = "escape_state"  # 需要逃跑的状态


class CooldownType(Enum):
    """
    技能冷却类型枚举类

    功能描述：
        定义技能的不同冷却机制类型
        不同冷却类型影响技能的冷却计算方式
    """

    FIXED = "fixed"  # 固定冷却，释放后固定时间后才能再次使用
    CHARGE = "charge"  # 充能制，可以存储多次使用次数
    NO_COOLDOWN = "no_cooldown"  # 无冷却，可以连续使用
    CONDITIONAL = "conditional"  # 条件冷却，根据特定条件决定冷却时间


@dataclass
class SkillConfig:
    """
    技能配置数据类

    功能描述：
        使用dataclass定义技能的所有配置属性
        创建技能实例时需要传入此配置对象

    参数说明：
        skill_id: 技能唯一标识符，如"Q"、"W"、"E"、"R"
        skill_type: 技能类型，SkillType枚举值
        key: 技能按键，如"q"、"w"、"e"、"r"
        name: 技能显示名称
        cooldown: 技能冷却时间，单位秒
        range: 技能有效范围，单位像素
        cooldown_type: 冷却类型，默认为固定冷却
        trigger_conditions: 触发条件列表，默认为空列表
        trigger_params: 触发条件参数字典，默认为空字典
        priority: 技能优先级，1-10，数字越小优先级越高，默认为5
        can_use_when_attached: 附身时是否可用，默认可用
        can_use_when_detached: 非附身时是否可用，默认可用
    """

    skill_id: str  # 技能ID，字符串类型，如"Q"、"W"、"E"、"R"
    skill_type: SkillType  # 技能类型，SkillType枚举值
    key: str  # 技能按键，字符串类型，如"q"、"e"、"r"、"f"
    name: str  # 技能名称，字符串类型，用于显示和日志
    cooldown: float  # 冷却时间，浮点数类型，单位秒
    range: int  # 技能范围，整数类型，单位像素
    cooldown_type: CooldownType = CooldownType.FIXED  # 冷却类型，默认为固定冷却
    trigger_conditions: List[TriggerCondition] = field(
        default_factory=list
    )  # 触发条件列表，默认为空列表
    trigger_params: Dict[str, Any] = field(
        default_factory=dict
    )  # 触发条件参数，字典类型，默认为空字典
    priority: int = 5  # 优先级，整数类型，1-10，数字越小优先级越高
    can_use_when_attached: bool = True  # 附身时是否可用，布尔类型，默认可用
    can_use_when_detached: bool = True  # 非附身时是否可用，布尔类型，默认可用

    def __post_init__(self):
        """
        数据类初始化后的后置处理方法

        功能说明：
            处理默认值初始化，将None值替换为实际的空容器
        """
        if self.trigger_conditions is None:  # 检查触发条件列表是否为None
            self.trigger_conditions = []  # 初始化为空列表
        if self.trigger_params is None:  # 检查触发参数字典是否为None
            self.trigger_params = {}  # 初始化为空字典


class SkillBase(ABC):
    """
    技能抽象基类

    功能描述：
        所有具体技能类的抽象基类，定义了技能的通用接口和行为
        子类必须继承此类并实现_do_cast抽象方法

    抽象方法：
        _do_cast: 子类必须实现，定义具体的技能释放逻辑

    属性说明：
        config: 技能配置对象
        last_cast_time: 上次释放时间戳
        cast_count: 释放次数计数
        _enabled: 技能启用状态
    """

    def __init__(self, config: SkillConfig):
        """
        初始化技能基类

        参数说明：
            config: SkillConfig类型，技能配置对象，包含技能的所有配置信息
        """
        self.config = config  # 保存技能配置对象
        self.last_cast_time: float = 0  # 上次释放时间戳，初始为0
        self.cast_count: int = 0  # 技能释放次数计数，初始为0
        self._enabled: bool = True  # 技能启用标志，默认为True（启用）

    @property
    def skill_id(self) -> str:
        """
        属性：获取技能ID

        返回值说明：
            str: 返回配置中的技能ID
        """
        return self.config.skill_id  # 从配置中获取技能ID

    @property
    def skill_type(self) -> SkillType:
        """
        属性：获取技能类型

        返回值说明：
            SkillType: 返回配置中的技能类型枚举值
        """
        return self.config.skill_type  # 从配置中获取技能类型

    @property
    def key(self) -> str:
        """
        属性：获取技能按键

        返回值说明：
            str: 返回配置中的技能按键字符串
        """
        return self.config.key  # 从配置中获取技能按键

    @property
    def name(self) -> str:
        """
        属性：获取技能名称

        返回值说明：
            str: 返回配置中的技能名称
        """
        return self.config.name  # 从配置中获取技能名称

    @property
    def is_enabled(self) -> bool:
        """
        属性：获取技能启用状态

        返回值说明：
            bool: True表示技能已启用，False表示已禁用
        """
        return self._enabled  # 返回内部启用标志

    def enable(self):
        """
        启用技能

        功能说明：
            将技能设置为启用状态，允许技能被释放
        """
        self._enabled = True  # 设置启用标志为True

    def disable(self):
        """
        禁用技能

        功能说明：
            将技能设置为禁用状态，阻止技能被释放
        """
        self._enabled = False  # 设置启用标志为False

    def get_remaining_cooldown(self) -> float:
        """
        获取技能剩余冷却时间

        返回值说明：
            float: 剩余冷却时间（秒），0表示冷却已完成

        计算逻辑：
            1. 如果冷却类型为NO_COOLDOWN，直接返回0
            2. 计算已过去的时间
            3. 计算剩余时间 = 总冷却时间 - 已过去时间
            4. 返回max(0, 剩余时间)，确保不为负数
        """
        if (
            self.config.cooldown_type == CooldownType.NO_COOLDOWN
        ):  # 检查是否为无冷却类型
            return 0  # 无冷却，直接返回0
        elapsed = time.time() - self.last_cast_time  # 计算已过去的时间
        remaining = self.config.cooldown - elapsed  # 计算剩余冷却时间
        return max(0, remaining)  # 返回剩余时间，最小为0

    def is_on_cooldown(self) -> bool:
        """
        检查技能是否处于冷却中

        返回值说明：
            bool: True表示技能还在冷却中，False表示冷却已完成
        """
        return self.get_remaining_cooldown() > 0  # 剩余时间大于0表示在冷却中

    def can_cast(self, context) -> bool:
        """
        检查技能是否可以释放

        参数说明：
            context: SkillContext类型，技能上下文，包含当前游戏状态

        返回值说明：
            bool: True表示可以释放，False表示不能释放

        检查逻辑：
            1. 检查技能是否被启用
            2. 检查技能是否在冷却中
            3. 检查附身状态限制
            4. 检查触发条件
        """
        if not self._enabled:  # 检查技能是否被启用
            return False  # 技能被禁用，不能释放

        # 检查技能是否在冷却中
        if self.is_on_cooldown():
            return False  # 技能在冷却中，不能释放

        # 检查附身状态限制
        if context.is_attached and not self.config.can_use_when_attached:
            return False  # 已附身但技能不可在附身时使用
        if not context.is_attached and not self.config.can_use_when_detached:
            return False  # 未附身但技能不可在非附身时使用

        # 检查触发条件
        return self._check_trigger_conditions(context)  # 调用子类或本类的条件检查

    def _check_trigger_conditions(self, context) -> bool:
        """
        检查所有触发条件是否满足

        参数说明：
            context: SkillContext类型，技能上下文

        返回值说明：
            bool: True表示所有条件都满足，False表示至少有一个条件不满足

        检查逻辑：
            遍历配置中的所有触发条件，逐个评估
            如果任何一个条件不满足，立即返回False
            所有条件都满足时返回True
        """
        for condition in self.config.trigger_conditions:  # 遍历所有触发条件
            if not self._evaluate_condition(condition, context):  # 评估单个条件
                return False  # 条件不满足，返回False
        return True  # 所有条件都满足，返回True

    def _evaluate_condition(self, condition: TriggerCondition, context) -> bool:
        """
        评估单个触发条件

        参数说明：
            condition: TriggerCondition类型，要评估的触发条件枚举值
            context: SkillContext类型，技能上下文

        返回值说明：
            bool: True表示条件满足，False表示条件不满足

        功能说明：
            根据条件类型，从上下文中获取相应数据进行判断
            支持的条件类型包括敌人相关、队友相关、自身相关、战斗状态等
        """
        params = self.config.trigger_params or {}  # 获取触发参数，None时使用空字典

        # ========== 敌人相关条件评估 ==========
        if condition == TriggerCondition.HAS_ENEMY:
            return context.has_enemy  # 检查是否有敌人

        elif condition == TriggerCondition.ENEMY_IN_RANGE:
            closest = context.get_closest_enemy_distance()  # 获取最近敌人距离
            return (
                closest is not None and closest <= self.config.range
            )  # 检查是否在技能范围内

        elif condition == TriggerCondition.ENEMY_COUNT_GTE:
            threshold = params.get("count", 1)  # 从参数获取数量阈值，默认为1
            return context.enemy_count >= threshold  # 检查敌人数量是否大于等于阈值

        elif condition == TriggerCondition.ENEMY_CLOSEST_DIST:
            max_dist = params.get("max_distance", self.config.range)  # 获取最大距离参数
            closest = context.get_closest_enemy_distance()  # 获取最近敌人距离
            return closest is not None and closest <= max_dist  # 检查是否在指定距离内

        # ========== 队友相关条件评估 ==========
        elif condition == TriggerCondition.HAS_TEAMMATE:
            return context.has_teammate  # 检查是否有队友

        elif condition == TriggerCondition.TEAMMATE_IN_RANGE:
            closest = context.get_closest_teammate_distance()  # 获取最近队友距离
            return (
                closest is not None and closest <= self.config.range
            )  # 检查是否在技能范围内

        elif condition == TriggerCondition.TEAMMATE_LOW_HP:
            threshold = params.get("hp_threshold", 50)  # 从参数获取血量阈值，默认为50
            return context.has_teammate_low_hp(threshold)  # 检查是否有队友低血量

        elif condition == TriggerCondition.TEAMMATE_PRIORITY:
            return context.has_priority_teammate_in_range(
                self.config.range
            )  # 检查优先队友是否在范围内

        # ========== 自身相关条件评估 ==========
        elif condition == TriggerCondition.SELF_LOW_HP:
            threshold = params.get("hp_threshold", 50)  # 从参数获取血量阈值，默认为50
            return context.is_self_low_hp(threshold)  # 检查自身是否低血量

        elif condition == TriggerCondition.SELF_ATTACHED:
            return context.is_attached  # 检查是否处于附身状态

        elif condition == TriggerCondition.SELF_NOT_ATTACHED:
            return not context.is_attached  # 检查是否未处于附身状态

        elif condition == TriggerCondition.SELF_IN_DANGER:
            return context.is_self_in_danger()  # 检查自身是否处于危险状态

        # ========== 战斗状态条件评估 ==========
        elif condition == TriggerCondition.IN_TEAMFIGHT:
            threshold = params.get("enemy_count", 2)  # 从参数获取敌人数量阈值，默认为2
            return (
                context.enemy_count >= threshold and context.has_teammate
            )  # 检查是否团战（敌人多且有队友）

        elif condition == TriggerCondition.PEACE_STATE:
            return not context.has_enemy  # 检查是否处于和平/脱战状态（没有敌人）

        elif condition == TriggerCondition.ESCAPE_STATE:
            return context.is_escape_state()  # 检查是否需要逃跑

        return True  # 未知条件默认返回True

    def cast(self, context) -> bool:
        """
        释放技能

        参数说明：
            context: SkillContext类型，技能上下文

        返回值说明：
            bool: True表示技能成功释放，False表示释放失败

        释放流程：
            1. 检查是否可以释放（can_cast）
            2. 调用_do_cast执行具体释放逻辑
            3. 更新释放时间和计数
            4. 异常处理，防止技能错误影响系统
        """
        if not self.can_cast(context):  # 检查是否可以释放
            return False  # 不能释放，返回False

        try:
            self._do_cast(context)  # 调用子类实现的释放逻辑
            self.last_cast_time = time.time()  # 更新上次释放时间为当前时间
            self.cast_count += 1  # 增加释放次数计数
            return True  # 释放成功，返回True
        except Exception as e:  # 保留: 抽象基类需捕获所有子类实现可能的异常
            # 捕获异常，记录错误日志但不中断程序
            logger.error(f"[技能错误] {self.name} 释放失败: {e}")
            return False  # 释放失败，返回False

    @abstractmethod
    def _do_cast(self, context):
        """
        抽象方法：具体的技能释放实现

        参数说明：
            context: SkillContext类型，技能上下文

        功能说明：
            子类必须实现此方法，定义具体的技能释放行为
            如模拟按键、执行特殊逻辑等

        注意事项：
            这是一个抽象方法，不能直接调用，必须在子类中重写
        """
        pass  # 抽象方法，子类必须实现

    def get_status(self) -> Dict:
        """
        获取技能状态信息

        返回值说明：
            Dict: 包含技能状态信息的字典，包括：
                - skill_id: 技能ID
                - name: 技能名称
                - enabled: 是否启用
                - on_cooldown: 是否在冷却中
                - remaining_cd: 剩余冷却时间
                - cast_count: 释放次数
        """
        return {
            "skill_id": self.skill_id,  # 技能ID
            "name": self.name,  # 技能名称
            "enabled": self._enabled,  # 启用状态
            "on_cooldown": self.is_on_cooldown(),  # 是否在冷却中
            "remaining_cd": self.get_remaining_cooldown(),  # 剩余冷却时间
            "cast_count": self.cast_count,  # 释放次数
        }


class SkillRegistry:
    """
    技能注册表类

    功能描述：
        用于动态创建技能实例的工厂类
        维护SkillType到技能类的映射关系
        支持根据配置动态创建对应的技能实例

    使用方式：
        1. 使用register方法注册技能类型
        2. 使用create_skill方法根据配置创建技能实例
        3. 使用get_supported_types获取所有支持的类型
    """

    _registry: Dict[SkillType, type] = {}  # 类属性：存储SkillType到技能类的映射字典

    @classmethod
    def register(cls, skill_type: SkillType, skill_class: type):
        """
        注册技能类型

        参数说明：
            skill_type: SkillType类型，技能类型枚举值
            skill_class: type类型，技能类（必须是SkillBase的子类）

        功能说明：
            将技能类型与对应的技能类建立映射关系
            注册后可以使用create_skill动态创建该类型的技能实例
        """
        cls._registry[skill_type] = skill_class  # 将技能类型和类存入注册表

    @classmethod
    def create_skill(cls, config: SkillConfig) -> SkillBase:
        """
        根据配置创建技能实例

        参数说明：
            config: SkillConfig类型，技能配置对象

        返回值说明：
            SkillBase: 创建的技能实例

        异常说明：
            ValueError: 如果技能类型未注册，抛出异常

        功能说明：
            根据配置中的skill_type查找对应的技能类
            使用配置实例化技能类并返回
        """
        skill_class = cls._registry.get(config.skill_type)  # 从注册表获取技能类
        if skill_class is None:  # 检查技能类是否存在
            raise ValueError(
                f"未注册的技能类型: {config.skill_type}"
            )  # 未注册则抛出异常
        return skill_class(config)  # 使用配置实例化技能类并返回

    @classmethod
    def get_supported_types(cls) -> List[SkillType]:
        """
        获取所有已注册的技能类型

        返回值说明：
            List[SkillType]: 已注册的技能类型列表

        功能说明：
            返回注册表中所有已注册的技能类型枚举值
        """
        return list(cls._registry.keys())  # 返回注册表字典的所有键（技能类型）
