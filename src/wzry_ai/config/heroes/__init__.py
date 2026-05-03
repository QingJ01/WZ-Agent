"""
英雄配置包 - 统一导出所有英雄相关配置

功能说明：
    本模块作为英雄配置的统一入口，将分散在不同子模块中的配置集中导出，
    方便其他模块通过单一入口导入所有英雄相关配置。

参数说明：
    无直接参数，通过导入语句使用

返回值说明：
    无直接返回值，导出各类配置变量和函数
"""

# ========== 从 mapping 模块导出所有英雄相关配置 ==========
# mapping模块包含英雄中文名与拼音之间的双向转换功能和分路配置
from wzry_ai.config.heroes.mapping import (
    # 名称映射相关变量和函数
    HERO_NAME_MAP,           # 英雄名称映射字典（中文→拼音）
    get_hero_pinyin,         # 函数：中文名转拼音
    get_hero_chinese,        # 函数：拼音转中文名
    convert_priority_heroes, # 函数：转换英雄列表格式
    PINYIN_TO_CHINESE,       # 字典：拼音到中文的映射（带_blue后缀）
    PINYIN_BASE_TO_CHINESE,  # 字典：基础拼音到中文的映射
    
    # 分路相关变量和函数
    LANE_HEROES,             # 字典：分路到英雄列表的映射
    LANE_NAME_MAP,           # 字典：分路代码到中文名的映射
    HERO_LANE_MAP,           # 字典：英雄到分路的反向映射
    get_heroes_by_lane,      # 函数：获取指定分路的所有英雄
    get_lane_by_hero,        # 函数：获取英雄所属分路
    get_hero_chinese_name,   # 函数：获取英雄中文名
)

# ========== 从 support_config 模块导出辅助英雄配置 ==========
# support_config模块包含辅助英雄的详细配置参数
from wzry_ai.config.heroes.support_config import (
    SUPPORTED_SUPPORT_HEROES,  # 列表：支持的辅助英雄名称
    SUPPORT_HERO_CONFIG,       # 字典：各辅助英雄的详细配置
    get_hero_config,           # 函数：获取指定英雄的配置
)

# ========== 从 state_configs 模块导出英雄状态检测配置 ==========
# state_configs模块包含英雄状态检测的配置参数
from wzry_ai.config.heroes.state_configs import (
    StateType,                 # 枚举：状态检测类型
    HERO_STATE_CONFIGS,        # 字典：英雄状态配置
    get_hero_state_config,     # 函数：获取英雄状态配置
    get_all_hero_names,        # 函数：获取所有已配置英雄名称
    add_hero_state_config,     # 函数：添加英雄状态配置
    update_state_color,        # 函数：更新状态颜色配置
    CALIBRATION_CONFIG,        # 字典：校准工具默认配置
)

# ========== 定义模块公开接口 ==========
# __all__列表声明了当使用"from config.heroes import *"时应该导入哪些名称
__all__ = [
    # 名称映射相关变量和函数
    'HERO_NAME_MAP',         # 英雄名称映射字典
    'get_hero_pinyin',       # 中文转拼音函数
    'get_hero_chinese',      # 拼音转中文函数
    'get_hero_chinese_name', # 获取中文名函数
    'convert_priority_heroes',  # 转换英雄列表函数
    'PINYIN_TO_CHINESE',     # 拼音到中文映射（带后缀）
    'PINYIN_BASE_TO_CHINESE',  # 基础拼音到中文映射
    
    # 分路相关变量和函数
    'LANE_HEROES',           # 分路英雄字典
    'LANE_NAME_MAP',         # 分路名称映射
    'HERO_LANE_MAP',         # 英雄分路反向映射
    'get_heroes_by_lane',    # 获取分路英雄函数
    'get_lane_by_hero',      # 获取英雄分路函数
    
    # 辅助配置相关变量和函数
    'SUPPORTED_SUPPORT_HEROES',  # 支持的辅助英雄列表
    'SUPPORT_HERO_CONFIG',       # 辅助英雄配置字典
    'get_hero_config',           # 获取英雄配置函数
    
    # 状态检测相关变量和函数
    'StateType',                 # 状态检测类型枚举
    'HERO_STATE_CONFIGS',        # 英雄状态配置字典
    'get_hero_state_config',     # 获取英雄状态配置函数
    'get_all_hero_names',        # 获取所有英雄名称函数
    'add_hero_state_config',     # 添加英雄状态配置函数
    'update_state_color',        # 更新状态颜色函数
    'CALIBRATION_CONFIG',        # 校准工具配置
]
