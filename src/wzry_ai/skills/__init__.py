# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，支持中文字符

"""
技能系统模块 - 统一技能管理
该模块是技能系统的入口，负责导出所有技能相关的类和接口
"""

# 从skill_base模块导入技能基类和枚举类型
from .skill_base import SkillBase, SkillType, TriggerCondition, CooldownType
# SkillBase: 所有技能类的抽象基类
# SkillType: 技能类型枚举（伤害、控制、治疗等）
# TriggerCondition: 技能触发条件枚举
# CooldownType: 冷却类型枚举（固定、充能等）

# 从skill_context模块导入技能上下文类
from .skill_context import SkillContext
# SkillContext: 封装游戏状态数据，为技能判断提供统一数据接口

# 从skill_types模块导入具体技能类型实现类
from .skill_types import (
    DamageSkill,
    ControlSkill,
    HealShieldSkill,
    BuffSkill,
    AttachSkill,
    ActiveItemSkill,
    SummonerSkill,
)
# DamageSkill: 伤害技能类，对敌人造成伤害
# ControlSkill: 控制技能类，眩晕、击飞、减速等效果
# HealShieldSkill: 治疗/护盾技能类，恢复血量或提供护盾
# BuffSkill: 增益技能类，为队友提供属性加成
# AttachSkill: 位移/附身技能类，附身到队友身上
# ActiveItemSkill: 辅助装备主动技能类，救赎之翼、奔狼纹章等
# SummonerSkill: 召唤师技能类，治疗、闪现、眩晕等

# 从hero_skill_logic_base模块导入英雄技能逻辑基类
from .hero_skill_logic_base import HeroSkillLogicBase
# HeroSkillLogicBase: 英雄技能逻辑基类，提供公共基础设施

# 从各英雄技能逻辑模块导入具体实现类
from .yao_skill_logic_v2 import YaoSkillLogic
# YaoSkillLogic: 瑶英雄技能逻辑实现

from .caiwenji_skill_logic_v2 import CaiwenjiSkillLogic
# CaiwenjiSkillLogic: 蔡文姬英雄技能逻辑实现

from .mingshiyin_skill_logic_v2 import MingshiyinSkillLogic
# MingshiyinSkillLogic: 明世隐英雄技能逻辑实现

from .generic_skill_manager import (
    GenericSkillManager,
    SkillContext as GenericSkillContext,
)
# GenericSkillManager: 通用技能管理器
# GenericSkillContext: 通用技能上下文

# __all__列表定义了当使用"from skills import *"时导出的符号
__all__ = [
    "SkillBase",  # 技能基类
    "SkillType",  # 技能类型枚举
    "TriggerCondition",  # 触发条件枚举
    "CooldownType",  # 冷却类型枚举
    "SkillContext",  # 技能上下文
    "DamageSkill",  # 伤害技能
    "ControlSkill",  # 控制技能
    "HealShieldSkill",  # 治疗/护盾技能
    "BuffSkill",  # 增益技能
    "AttachSkill",  # 附身技能
    "ActiveItemSkill",  # 装备主动技能
    "SummonerSkill",  # 召唤师技能
    "HeroSkillLogicBase",  # 英雄技能逻辑基类
    "YaoSkillLogic",  # 瑶技能逻辑
    "CaiwenjiSkillLogic",  # 蔡文姬技能逻辑
    "MingshiyinSkillLogic",  # 明世隐技能逻辑
    "GenericSkillManager",  # 通用技能管理器
    "GenericSkillContext",  # 通用技能上下文
]
