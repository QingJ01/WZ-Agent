"""
辅助英雄特定配置模块

功能说明：
    本模块定义各辅助英雄的详细配置参数，包括跟随距离、安全距离、
    优先跟随的英雄列表、自动维护设置等，用于AI控制辅助英雄的行为决策。

参数说明：
    无直接参数，通过导入变量和调用函数使用

返回值说明：
    无直接返回值，提供配置字典和查询函数
"""

# 从基础配置模块导入相关阈值参数
from wzry_ai.config.base import FOLLOW_THRESHOLD, SAFE_ENEMY_DISTANCE, AVOID_ENEMY_WEIGHT

# 从英雄映射模块导入分路英雄配置
from wzry_ai.config.heroes.mapping import LANE_HEROES

# 瑶的跟随优先级：发育路 > 中路 > 打野 > 对抗路
_yao_priority = (
    LANE_HEROES.get('lane_adc', []) +
    LANE_HEROES.get('lane_mid', []) +
    LANE_HEROES.get('lane_jungle', []) +
    LANE_HEROES.get('lane_top', [])
)

# ========== 支持的辅助英雄列表 ==========
# SUPPORTED_SUPPORT_HEROES列表定义了当前AI支持自动操作的辅助英雄
SUPPORTED_SUPPORT_HEROES = ["瑶", "蔡文姬", "明世隐"]

# ========== 各辅助英雄特定配置 ==========
# SUPPORT_HERO_CONFIG字典包含每个辅助英雄的详细行为配置参数
SUPPORT_HERO_CONFIG = {
    # 瑶的配置
    "瑶": {
        "follow_distance": 50,       # 跟随距离：与目标保持50像素的距离
        "safe_distance": 200,        # 安全距离：与敌人保持200像素以上
        "avoid_weight": 0.5,         # 避敌权重：躲避敌人的权重系数
        "has_attach_skill": True,    # 是否有附身技能：瑶的大招可以附身队友
        "attach_protect_duration": 5.0,  # 附身保护时长：附身后5秒内不会自动解除
        "priority_heroes": _yao_priority,  # 优先跟随的英雄列表（按分路优先级动态生成）
        "auto_maintenance": {        # 自动维护设置
            "buy_item": {"enabled": True, "interval": 3, "key": "4"},  # 自动购买装备
            "level_up": {"enabled": True, "interval": 5, "priority": ["R", "Q", "E"]},  # 自动升级技能
        },
        "basic_attack": {            # 普通攻击设置
            "enabled": True,          # 是否启用自动普攻
            "interval": 0.5,          # 普攻间隔（秒）
            "can_attack_when_attached": False,  # 附身状态下是否可以普攻
        },
    },
    # 蔡文姬的配置
    "蔡文姬": {
        "follow_distance": 80,       # 跟随距离：与目标保持80像素的距离
        "safe_distance": 250,        # 安全距离：与敌人保持250像素以上
        "avoid_weight": 0.6,         # 避敌权重：躲避敌人的权重系数（较高）
        "has_attach_skill": False,   # 是否有附身技能：蔡文姬没有附身技能
        "attach_protect_duration": 0,  # 附身保护时长：无
        "priority_heroes": [         # 优先跟随的英雄列表（包括射手和部分坦克）
            "敖隐", "莱西奥", "戈娅", "艾琳", "蒙犽", "伽罗",
            "公孙离", "黄忠", "虞姬", "李元芳",
            "后羿", "狄仁杰", "马可波罗", "鲁班七号", "孙尚香",
            "张飞", "牛魔", "廉颇", "项羽", "刘邦", "白起"
        ],
        "auto_maintenance": {        # 自动维护设置
            "buy_item": {"enabled": True, "interval": 3, "key": "4"},
            "level_up": {"enabled": True, "interval": 5, "priority": ["R", "Q", "E", "W"]},
        },
        "basic_attack": {            # 普通攻击设置
            "enabled": False,         # 蔡文姬不需要自动普攻
            "interval": 0.5,
            "can_attack_when_attached": False,
        },
    },
    # 明世隐的配置
    "明世隐": {
        "follow_distance": 100,      # 跟随距离：与目标保持100像素的距离
        "safe_distance": 200,        # 安全距离：与敌人保持200像素以上
        "avoid_weight": 0.5,         # 避敌权重：躲避敌人的权重系数
        "has_attach_skill": False,   # 是否有附身技能：明世隐没有附身技能
        "has_link_skill": True,      # 是否有链接技能：明世隐的一技能可以链接队友
        "link_range": 600,           # 链接技能范围：最大链接距离600像素
        "attach_protect_duration": 0,  # 附身保护时长：无
        "priority_heroes": [         # 优先跟随的英雄列表（包括射手和刺客）
            "敖隐", "莱西奥", "戈娅", "艾琳", "蒙犽", "伽罗",
            "公孙离", "黄忠", "虞姬", "李元芳",
            "后羿", "狄仁杰", "马可波罗", "鲁班七号", "孙尚香",
            "李白", "韩信", "露娜", "裴擒虎", "镜", "云缨"
        ],
        "auto_maintenance": {        # 自动维护设置
            "buy_item": {"enabled": True, "interval": 3, "key": "4"},
            "level_up": {"enabled": True, "interval": 5, "priority": ["R", "Q", "E"]},
        },
        "basic_attack": {            # 普通攻击设置
            "enabled": True,          # 明世隐可以普攻
            "interval": 0.5,
            "can_attack_when_attached": True,  # 链接状态下可以普攻
        },
        "special_mechanics": {       # 特殊机制设置
            "link_timeout": 12.0,     # 链接超时时间：12秒后需要重新链接
            "link_priority": "team",  # 链接优先级：优先链接队友
        },
    },
}


def get_hero_config(hero_name: str) -> dict:
    """
    获取指定英雄的配置，如果不存在则返回默认配置
    
    功能说明：
        查询指定辅助英雄的详细配置，如果该英雄没有特定配置，
        则返回基于基础配置生成的默认配置
    
    参数说明：
        hero_name: 英雄中文名字符串，如"瑶"、"蔡文姬"等
        
    返回值说明：
        dict: 英雄配置字典，包含跟随距离、安全距离、技能设置等参数
    """
    # 定义默认配置，使用从base模块导入的阈值参数
    default_config = {
        "follow_distance": FOLLOW_THRESHOLD,      # 默认跟随距离
        "safe_distance": SAFE_ENEMY_DISTANCE,     # 默认安全距离
        "avoid_weight": AVOID_ENEMY_WEIGHT,       # 默认避敌权重
        "has_attach_skill": False,                # 默认没有附身技能
        "attach_protect_duration": 0,             # 默认附身保护时长为0
        "priority_heroes": [],                    # 默认优先英雄列表为空
    }
    # 从配置字典中获取指定英雄的配置，不存在则返回默认配置
    return SUPPORT_HERO_CONFIG.get(hero_name, default_config)
