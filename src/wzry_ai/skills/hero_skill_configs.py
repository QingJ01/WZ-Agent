"""
英雄技能配置模块 - 定义所有辅助英雄的技能配置Schema
该模块包含瑶、明世隐、蔡文姬等辅助英雄的技能配置
"""

# 导入类型提示相关类
from typing import Dict, List, Any
# Dict: 字典类型，用于存储配置
# List: 列表类型
# Any: 任意类型

# 从skill_base模块导入配置类和枚举
from .skill_base import SkillConfig, SkillType, TriggerCondition, CooldownType
# SkillConfig: 技能配置数据类
# SkillType: 技能类型枚举
# TriggerCondition: 触发条件枚举
# CooldownType: 冷却类型枚举


# ================= 瑶的技能配置 =================
# 瑶是一名附身型辅助英雄，可以附身到队友身上提供保护和增益
YAO_SKILL_CONFIGS = {
    "skills": [  # 技能列表，包含所有主动技能和召唤师技能
        SkillConfig(
            skill_id="Q",  # 技能ID：一技能
            skill_type=SkillType.CONTROL,  # 技能类型：控制（击退+击飞效果）
            key="q",  # 按键：q键
            name="若有人兮",  # 技能名称
            cooldown=10.0,  # 冷却时间：10秒
            range=500,  # 技能范围：500像素
            trigger_conditions=[TriggerCondition.HAS_ENEMY, TriggerCondition.ENEMY_IN_RANGE],  # 触发条件：有敌人且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="E",  # 技能ID：二技能
            skill_type=SkillType.DAMAGE,  # 技能类型：伤害
            key="e",  # 按键：e键
            name="风飒木萧",  # 技能名称
            cooldown=8.0,  # 冷却时间：8秒
            range=400,  # 技能范围：400像素
            trigger_conditions=[TriggerCondition.HAS_ENEMY, TriggerCondition.ENEMY_IN_RANGE],  # 触发条件：有敌人且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=4,  # 优先级：4（中等优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="R",  # 技能ID：大招（附身技能）
            skill_type=SkillType.ATTACH,  # 技能类型：附身
            key="r",  # 按键：r键
            name="独立兮山之上",  # 技能名称
            cooldown=2.0,  # 冷却时间：2秒（附身本身冷却很短）
            range=350,  # 技能范围：350像素（附身距离）
            trigger_conditions=[TriggerCondition.HAS_TEAMMATE, TriggerCondition.TEAMMATE_IN_RANGE],  # 触发条件：有队友且在范围内
            trigger_params={
                "attach_protect_duration": 5.0,  # 触发参数：附身保护期5秒，防止频繁附身/脱离
            },
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=False,  # 附身时不可用（不能重复附身）
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="heal",  # 技能ID：治疗术（召唤师技能）
            skill_type=SkillType.SUMMONER,  # 技能类型：召唤师技能
            key="f",  # 按键：f键
            name="治疗术",  # 技能名称
            cooldown=15.0,  # 冷却时间：15秒
            range=0,  # 技能范围：0（范围效果，无需目标）
            trigger_conditions=[TriggerCondition.SELF_LOW_HP, TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：自身或队友低血量
            trigger_params={"hp_threshold": 50},  # 触发参数：血量阈值50
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="recover",  # 技能ID：恢复（召唤师技能）
            skill_type=SkillType.SUMMONER,  # 技能类型：召唤师技能
            key="c",  # 按键：c键
            name="恢复",  # 技能名称
            cooldown=5.0,  # 冷却时间：5秒
            range=0,  # 技能范围：0
            trigger_conditions=[TriggerCondition.SELF_LOW_HP, TriggerCondition.PEACE_STATE],  # 触发条件：自身低血量或和平状态
            trigger_params={"hp_threshold": 80},  # 触发参数：血量阈值80
            priority=6,  # 优先级：6（较低优先级）
            can_use_when_attached=False,  # 附身时不可用（附身时不需要恢复）
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="redemption",  # 技能ID：救赎（辅助装备主动技能）
            skill_type=SkillType.ACTIVE_ITEM,  # 技能类型：装备主动技能
            key="t",  # 按键：t键
            name="救赎",  # 技能名称
            cooldown=60.0,  # 冷却时间：60秒（救赎实际冷却）
            range=350,  # 技能范围：350像素（与大招范围一致）
            trigger_conditions=[TriggerCondition.HAS_TEAMMATE, TriggerCondition.TEAMMATE_IN_RANGE],  # 触发条件：有队友且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
    ],
    "auto_maintenance": {  # 自动维护配置
        "buy_item": {  # 买装备配置
            "enabled": True,  # 是否启用
            "interval": 3,  # 购买间隔：3秒
            "key": "4",  # 购买按键：数字键4
        },
        "level_up": {  # 升级技能配置
            "enabled": True,  # 是否启用
            "interval": 5,  # 升级间隔：5秒
            "priority": ["R", "Q", "E"],  # 升级优先级：先大招，再一技能，最后二技能
        },
    },
    "basic_attack": {  # 普攻配置
        "enabled": True,  # 是否启用普攻
        "interval": 0.5,  # 普攻间隔：0.5秒
        "can_attack_when_attached": False,  # 附身时是否可普攻：否（附身时不普攻）
    },
}


# ================= 明世隐的技能配置 =================
# 明世隐是一名链接型辅助英雄，通过链接队友提供增益或链接敌人造成伤害
MINGSHIYIN_SKILL_CONFIGS = {
    "skills": [  # 技能列表
        SkillConfig(
            skill_id="Q",  # 技能ID：一技能（链接技能）
            skill_type=SkillType.BUFF,  # 技能类型：增益/Buff
            key="q",  # 按键：q键
            name="临卦·无忧",  # 技能名称
            cooldown=8.0,  # 冷却时间：8秒
            range=600,  # 技能范围：600像素（链接距离较远）
            trigger_conditions=[TriggerCondition.HAS_TEAMMATE, TriggerCondition.TEAMMATE_IN_RANGE],  # 触发条件：有队友且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=False,  # 附身时不可用（明世隐没有附身机制）
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="E",  # 技能ID：二技能
            skill_type=SkillType.CONTROL,  # 技能类型：控制
            key="e",  # 按键：e键
            name="师卦·飞翼",  # 技能名称
            cooldown=6.0,  # 冷却时间：6秒
            range=400,  # 技能范围：400像素
            trigger_conditions=[TriggerCondition.HAS_ENEMY, TriggerCondition.ENEMY_IN_RANGE],  # 触发条件：有敌人且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=3,  # 优先级：3（中等优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="R",  # 技能ID：大招（治疗/伤害）
            skill_type=SkillType.HEAL_SHIELD,  # 技能类型：治疗/护盾
            key="r",  # 按键：r键
            name="泰卦·长生",  # 技能名称
            cooldown=60.0,  # 冷却时间：60秒
            range=500,  # 技能范围：500像素
            trigger_conditions=[TriggerCondition.IN_TEAMFIGHT, TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：团战且队友低血量
            trigger_params={
                "hp_threshold": 40,  # 触发参数：血量阈值40
                "enemy_count": 2,  # 触发参数：敌人数量阈值2（判断团战的敌人数量）
            },
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="heal",  # 技能ID：治疗术（召唤师技能）
            skill_type=SkillType.SUMMONER,  # 技能类型：召唤师技能
            key="f",  # 按键：f键
            name="治疗术",  # 技能名称
            cooldown=15.0,  # 冷却时间：15秒
            range=0,  # 技能范围：0
            trigger_conditions=[TriggerCondition.SELF_LOW_HP, TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：自身或队友低血量
            trigger_params={"hp_threshold": 50},  # 触发参数：血量阈值50
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="recover",  # 技能ID：恢复（召唤师技能）
            skill_type=SkillType.SUMMONER,  # 技能类型：召唤师技能
            key="c",  # 按键：c键
            name="恢复",  # 技能名称
            cooldown=5.0,  # 冷却时间：5秒
            range=0,  # 技能范围：0
            trigger_conditions=[TriggerCondition.SELF_LOW_HP, TriggerCondition.PEACE_STATE],  # 触发条件：自身低血量或和平状态
            trigger_params={"hp_threshold": 80},  # 触发参数：血量阈值80
            priority=6,  # 优先级：6（较低优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="redemption",  # 技能ID：救赎（辅助装备主动技能）
            skill_type=SkillType.ACTIVE_ITEM,  # 技能类型：装备主动技能
            key="t",  # 按键：t键
            name="救赎",  # 技能名称
            cooldown=60.0,  # 冷却时间：60秒（救赎实际冷却）
            range=600,  # 技能范围：600像素（明世隐链接范围较大，救赎范围也相应增大）
            trigger_conditions=[TriggerCondition.HAS_TEAMMATE, TriggerCondition.TEAMMATE_IN_RANGE],  # 触发条件：有队友且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
    ],
    "auto_maintenance": {  # 自动维护配置
        "buy_item": {  # 买装备配置
            "enabled": True,  # 是否启用
            "interval": 3,  # 购买间隔：3秒
            "key": "4",  # 购买按键：数字键4
        },
        "level_up": {  # 升级技能配置
            "enabled": True,  # 是否启用
            "interval": 5,  # 升级间隔：5秒
            "priority": ["R", "Q", "E"],  # 升级优先级：先大招，再一技能，最后二技能
        },
    },
    "basic_attack": {  # 普攻配置
        "enabled": True,  # 是否启用普攻
        "interval": 0.5,  # 普攻间隔：0.5秒
        "can_attack_when_attached": True,  # 附身时是否可普攻：是
    },
    "special_mechanics": {  # 特殊机制配置
        "link_timeout": 12.0,  # 链接超时时间：12秒（超过此时间需要重新链接）
        "link_priority": "team",  # 链接优先级：优先链接队友
    },
}


# ================= 蔡文姬的技能配置 =================
# 蔡文姬是一名治疗型辅助英雄，拥有强大的群体治疗能力
CAIWENJI_SKILL_CONFIGS = {
    "skills": [  # 技能列表
        SkillConfig(
            skill_id="Q",  # 技能ID：一技能（群体治疗）
            skill_type=SkillType.HEAL_SHIELD,  # 技能类型：治疗/护盾
            key="q",  # 按键：q键
            name="思无邪",  # 技能名称
            cooldown=8.0,  # 冷却时间：8秒
            range=400,  # 技能范围：400像素
            trigger_conditions=[TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：队友低血量
            trigger_params={"hp_threshold": 70},  # 触发参数：血量阈值70（较高阈值，提前治疗）
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="W",  # 技能ID：二技能（弹射控制）
            skill_type=SkillType.CONTROL,  # 技能类型：控制
            key="w",  # 按键：w键
            name="胡笳乐",  # 技能名称
            cooldown=10.0,  # 冷却时间：10秒
            range=450,  # 技能范围：450像素
            trigger_conditions=[TriggerCondition.HAS_ENEMY, TriggerCondition.ENEMY_IN_RANGE],  # 触发条件：有敌人且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=3,  # 优先级：3（中等优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="E",  # 技能ID：三技能（单体治疗+双抗）
            skill_type=SkillType.HEAL_SHIELD,  # 技能类型：治疗/护盾
            key="e",  # 按键：e键
            name="忘忧曲",  # 技能名称
            cooldown=12.0,  # 冷却时间：12秒
            range=350,  # 技能范围：350像素
            trigger_conditions=[TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：队友低血量
            trigger_params={"hp_threshold": 60},  # 触发参数：血量阈值60
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="R",  # 技能ID：大招（群体治疗+双抗）
            skill_type=SkillType.HEAL_SHIELD,  # 技能类型：治疗/护盾
            key="r",  # 按键：r键
            name="忘忧曲",  # 技能名称
            cooldown=60.0,  # 冷却时间：60秒
            range=500,  # 技能范围：500像素
            trigger_conditions=[
                TriggerCondition.IN_TEAMFIGHT,  # 触发条件1：团战状态
                TriggerCondition.TEAMMATE_LOW_HP  # 触发条件2：队友低血量
            ],
            trigger_params={
                "hp_threshold": 40,  # 触发参数：血量阈值40
                "enemy_count": 2,  # 触发参数：敌人数量阈值2（判断团战）
            },
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="heal",  # 技能ID：治疗术（召唤师技能）
            skill_type=SkillType.SUMMONER,  # 技能类型：召唤师技能
            key="f",  # 按键：f键
            name="治疗术",  # 技能名称
            cooldown=15.0,  # 冷却时间：15秒
            range=0,  # 技能范围：0
            trigger_conditions=[TriggerCondition.SELF_LOW_HP, TriggerCondition.TEAMMATE_LOW_HP],  # 触发条件：自身或队友低血量
            trigger_params={"hp_threshold": 50},  # 触发参数：血量阈值50
            priority=1,  # 优先级：1（最高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
        SkillConfig(
            skill_id="redemption",  # 技能ID：救赎（辅助装备主动技能）
            skill_type=SkillType.ACTIVE_ITEM,  # 技能类型：装备主动技能
            key="t",  # 按键：t键（统一使用T键）
            name="救赎",  # 技能名称
            cooldown=60.0,  # 冷却时间：60秒（救赎实际冷却）
            range=400,  # 技能范围：400像素（蔡文姬技能范围适中）
            trigger_conditions=[TriggerCondition.HAS_TEAMMATE, TriggerCondition.TEAMMATE_IN_RANGE],  # 触发条件：有队友且在范围内
            trigger_params={},  # 触发参数：无额外参数
            priority=2,  # 优先级：2（较高优先级）
            can_use_when_attached=True,  # 附身时可用
            can_use_when_detached=True,  # 非附身时可用
        ),
    ],
    "auto_maintenance": {  # 自动维护配置
        "buy_item": {  # 买装备配置
            "enabled": True,  # 是否启用
            "interval": 3,  # 购买间隔：3秒
            "key": "4",  # 购买按键：数字键4
        },
        "level_up": {  # 升级技能配置
            "enabled": True,  # 是否启用
            "interval": 5,  # 升级间隔：5秒
            "priority": ["R", "Q", "E", "W"],  # 升级优先级：先大招，再一技能、三技能，最后二技能
        },
    },
    "basic_attack": {  # 普攻配置
        "enabled": False,  # 是否启用普攻：否（蔡文姬不需要普攻，专注治疗）
        "interval": 0.5,  # 普攻间隔：0.5秒（配置存在但不用）
        "can_attack_when_attached": False,  # 附身时是否可普攻：否
    },
}


# ================= 配置注册表 =================
# 英雄技能配置注册表，存储所有支持的辅助英雄配置
HERO_SKILL_CONFIGS: Dict[str, Dict] = {
    "瑶": YAO_SKILL_CONFIGS,  # 瑶的技能配置
    "明世隐": MINGSHIYIN_SKILL_CONFIGS,  # 明世隐的技能配置
    "蔡文姬": CAIWENJI_SKILL_CONFIGS,  # 蔡文姬的技能配置
}


def get_hero_skill_config(hero_name: str) -> Dict:
    """
    获取指定英雄的技能配置
    
    参数说明：
        hero_name: 英雄名称，字符串类型，如"瑶"、"明世隐"等
        
    返回值说明：
        Dict: 英雄的技能配置字典，如果英雄不存在则返回空字典
        
    功能说明：
        根据英雄名称从HERO_SKILL_CONFIGS注册表中获取对应的配置
    """
    return HERO_SKILL_CONFIGS.get(hero_name, {})  # 从注册表获取配置，不存在返回空字典


def get_all_supported_heroes() -> List[str]:
    """
    获取所有支持的辅助英雄列表
    
    返回值说明：
        List[str]: 支持的辅助英雄名称列表
        
    功能说明：
        返回HERO_SKILL_CONFIGS注册表中所有已配置的英雄名称
    """
    return list(HERO_SKILL_CONFIGS.keys())  # 返回注册表的所有键（英雄名称）


def add_hero_skill_config(hero_name: str, config: Dict):
    """
    添加新英雄的技能配置
    
    参数说明：
        hero_name: 英雄名称，字符串类型
        config: 技能配置字典，包含skills、auto_maintenance、basic_attack等配置
        
    功能说明：
        将新英雄的技能配置添加到HERO_SKILL_CONFIGS注册表中
        如果英雄已存在，会覆盖原有配置
    """
    HERO_SKILL_CONFIGS[hero_name] = config  # 将配置存入注册表


# ================= 新英雄配置模板 =================
# 用于添加新英雄时的配置参考模板
NEW_HERO_CONFIG_TEMPLATE = {
    "skills": [  # 技能列表
        SkillConfig(
            skill_id="Q",  # 技能ID
            skill_type=SkillType.DAMAGE,  # 技能类型
            key="q",  # 按键
            name="技能名称",  # 技能名称
            cooldown=6.0,  # 冷却时间
            range=500,  # 技能范围
            trigger_conditions=[TriggerCondition.HAS_ENEMY],  # 触发条件
            trigger_params={},  # 触发参数
            priority=3,  # 优先级
            can_use_when_attached=True,  # 附身时是否可用
            can_use_when_detached=True,  # 非附身时是否可用
        ),
    ],
    "auto_maintenance": {  # 自动维护配置
        "buy_item": {  # 买装备配置
            "enabled": True,  # 是否启用
            "interval": 3,  # 购买间隔
            "key": "4",  # 购买按键
        },
        "level_up": {  # 升级技能配置
            "enabled": True,  # 是否启用
            "interval": 5,  # 升级间隔
            "priority": ["R", "Q", "E"],  # 升级优先级
        },
    },
    "basic_attack": {  # 普攻配置
        "enabled": True,  # 是否启用普攻
        "interval": 0.5,  # 普攻间隔
        "can_attack_when_attached": True,  # 附身时是否可普攻
    },
}
