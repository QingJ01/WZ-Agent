"""
英雄状态检测配置

功能说明：
    定义各英雄的状态检测区域和参考颜色
    用于AI识别英雄当前的状态（如附身、技能冷却等）
"""

# 从typing模块导入类型提示
from typing import Any, Dict, List, Optional, Tuple

# 从enum模块导入Enum，用于定义枚举类型
from enum import Enum


class StateType(Enum):
    """
    状态检测类型枚举

    功能说明：
        定义不同类型的状态检测方式
        枚举值用于标识检测的是哪种状态
    """

    ULT_ICON = "ult_icon"  # 大招图标状态（如瑶的附身状态）
    PASSIVE_ICON = "passive_icon"  # 被动技能图标状态
    BUFF_ICON = "buff_icon"  # 增益效果图标状态
    HP_BAR_COLOR = "hp_bar_color"  # 血条颜色变化检测
    MANA_BAR_COLOR = "mana_bar_color"  # 蓝条/能量条颜色检测
    CUSTOM_REGION = "custom_region"  # 自定义区域颜色检测


# 状态检测配置结构类型别名
# StateConfig是一个字典类型，用于存储单个状态的配置信息
StateConfig = Dict[str, Any]

# 英雄状态配置表（基于1920x1080分辨率）
# 存储各英雄的状态检测配置，包括检测区域、颜色阈值等
HERO_STATE_CONFIGS: Dict[str, StateConfig] = {
    # 瑶的状态配置
    "瑶": {
        "description": "瑶 - 大招附身状态检测",  # 配置描述
        "states": {  # 状态列表
            "附身状态": {  # 状态名称
                "type": StateType.ULT_ICON,  # 检测类型：大招图标
                "region": (1738, 608, 40, 40),  # 检测区域：x坐标, y坐标, 宽度, 高度
                "description": "大招图标区域，用于检测未附身/附身/鹿灵三种状态",
                "colors": {  # 不同状态对应的颜色配置
                    "未附身": {
                        "bgr": (151, 181, 83),  # BGR颜色值（OpenCV使用BGR而非RGB）
                        "description": "普通状态，绿色图标",
                    },
                    "附身": {
                        "bgr": (150, 155, 109),
                        "description": "附身队友状态，黄绿色图标",
                    },
                    "鹿灵": {
                        "bgr": (107, 84, 213),
                        "description": "鹿灵状态，蓝色图标",
                    },
                },
                "threshold": 40.0,  # 颜色匹配阈值，小于此值认为匹配成功
            }
        },
    },
    # 蔡文姬的状态配置
    "蔡文姬": {
        "description": "蔡文姬 - 大招状态检测",
        "states": {
            "大招状态": {
                "type": StateType.ULT_ICON,
                "region": (1738, 608, 40, 40),
                "description": "大招图标区域",
                "colors": {
                    "冷却中": {
                        "bgr": (128, 128, 128),
                        "description": "灰色，技能冷却中",
                    },
                    "可用": {"bgr": (255, 200, 100), "description": "金黄色，技能可用"},
                    "释放中": {
                        "bgr": (100, 255, 255),
                        "description": "亮黄色，技能释放中",
                    },
                },
                "threshold": 40.0,
            }
        },
    },
    # 明世隐的状态配置
    "明世隐": {
        "description": "明世隐 - 链接状态检测",
        "states": {
            "链接状态": {
                "type": StateType.ULT_ICON,
                "region": (1738, 608, 40, 40),
                "description": "一技能链接状态",
                "colors": {
                    "未链接": {"bgr": (128, 128, 128), "description": "未链接任何目标"},
                    "链接队友": {
                        "bgr": (100, 255, 100),
                        "description": "绿色，链接队友",
                    },
                    "链接敌人": {
                        "bgr": (100, 100, 255),
                        "description": "红色，链接敌人",
                    },
                },
                "threshold": 40.0,
            }
        },
    },
}


def get_hero_state_config(hero_name: str) -> Optional[StateConfig]:
    """
    获取英雄状态检测配置

    功能说明：
        根据英雄中文名获取其状态检测配置

    参数说明：
        hero_name: 英雄名称（中文），如"瑶"、"蔡文姬"

    返回值：
        Optional[StateConfig]: 该英雄的状态检测配置字典，如果不存在则返回None
    """
    # 使用字典的get方法获取配置
    return HERO_STATE_CONFIGS.get(hero_name)


def get_all_hero_names() -> List[str]:
    """
    获取所有已配置的英雄名称列表

    功能说明：
        返回当前已配置状态检测的所有英雄名称

    参数说明：
        无参数

    返回值：
        List[str]: 英雄中文名列表
    """
    # 将字典的键转换为列表返回
    return list(HERO_STATE_CONFIGS.keys())


def add_hero_state_config(hero_name: str, config: StateConfig) -> None:
    """
    添加新的英雄状态配置（运行时动态添加）

    功能说明：
        在程序运行期间动态添加新的英雄状态配置
        用于扩展支持新的英雄

    参数说明：
        hero_name: 英雄名称（中文）
        config: 状态配置字典，格式与HERO_STATE_CONFIGS中的配置相同
    """
    # 将新配置添加到全局配置字典中
    HERO_STATE_CONFIGS[hero_name] = config


def update_state_color(
    hero_name: str, state_name: str, color_name: str, bgr: Tuple[int, int, int]
) -> None:
    """
    更新状态颜色配置

    功能说明：
        更新指定英雄、指定状态、指定颜色的BGR值
        用于校准或调整颜色识别参数

    参数说明：
        hero_name: 英雄名称（中文）
        state_name: 状态名称，如"附身状态"
        color_name: 颜色名称，如"未附身"
        bgr: BGR颜色值，格式为(B, G, R)的元组
    """
    # 检查英雄是否存在于配置中
    if hero_name in HERO_STATE_CONFIGS:
        # 获取该英雄的所有状态配置
        states = HERO_STATE_CONFIGS[hero_name].get("states", {})
        # 检查状态是否存在
        if state_name in states:
            # 获取该状态的所有颜色配置
            colors = states[state_name].get("colors", {})
            # 检查颜色是否存在
            if color_name in colors:
                # 更新BGR颜色值
                colors[color_name]["bgr"] = bgr


# 校准工具默认配置
# 用于颜色校准工具的默认参数设置
CALIBRATION_CONFIG: Dict[str, Any] = {
    "window_title": "MuMu模拟器12",  # 模拟器窗口标题
    "preview_size": (400, 400),  # 预览窗口大小（像素）
    "click_delay": 0.1,  # 点击延迟（秒）
    "sample_size": (40, 40),  # 采样区域大小（宽, 高）
}
