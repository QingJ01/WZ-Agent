"""
统一配置包 - 分层配置管理架构

功能说明：
    此模块作为所有配置的统一入口，将分散在各个子模块中的配置集中导出，
    保持向后兼容性，原有代码中的 `from config import XXX` 仍然有效。

配置分层结构:
    config/
    ├── base.py          # 基础配置（路径、阈值、模型）
    ├── templates.py     # 模板ROI和阈值配置
    ├── emulator.py      # 模拟器配置
    └── heroes/          # 英雄配置
        ├── lanes.py     # 英雄分路
        ├── mapping.py   # 名称映射
        └── support_config.py  # 辅助英雄配置

参数说明：
    无直接参数，通过导入语句使用

返回值说明：
    无直接返回值，导出各类配置变量和函数
"""

# ========== 从 base 模块导入基础配置 ==========
# base模块包含最核心的配置参数
from wzry_ai.config.base import (
    # 自动启动开关
    AUTO_LAUNCH,             # 是否自动启动游戏流程
    
    # 游戏模式配置
    GAME_MODE,               # 游戏模式（如'ai'人机模式）
    BATTLE_MODE,             # 对战模式（如'5v5'）
    V5_MODE,                 # 5V5具体模式
    AI_BATTLE_MODE,          # 人机对战模式
    AI_DIFFICULTY,           # 人机难度
    
    # 辅助英雄配置
    DEFAULT_SUPPORT_HERO,    # 默认辅助英雄
    
    # 选英雄配置
    HERO_SELECT_PRIORITY,    # 选英雄优先级列表
    HERO_SELECT_MAX_RETRY,   # 选英雄最大重试次数
    
    # scrcpy屏幕镜像配置
    SCRCPY_MAX_SIZE,         # 最大画面尺寸
    SCRCPY_BITRATE,          # 视频比特率
    SCRCPY_MAX_FPS,          # 最大帧率
    LOCAL_SCRCPY_DIR,        # 项目内本地scrcpy工具目录
    LOCAL_SCRCPY_ADB_PATH,   # 项目内本地adb路径
    LOCAL_SCRCPY_EXE_PATH,   # 项目内本地scrcpy.exe路径
    
    # ADB设备配置
    ADB_DEVICE_IP,           # ADB设备IP地址
    ADB_DEVICE_PORT,         # ADB设备端口
    ADB_DEVICE_SERIAL,       # ADB设备序列号
    DEVICE_MODE,             # 设备模式：auto/mumu/android
    ADB_PATH,                # ADB工具路径
    
    # 截图区域配置
    DEFAULT_REGIONS,         # 默认截图区域字典
    
    # 模型检测配置
    MODEL1_CONFIDENCE_THRESHOLD,  # 模型1置信度阈值
    MODEL2_CONFIDENCE_THRESHOLD,  # 模型2置信度阈值
    YOLO_CONF,               # YOLO基础置信度
    YOLO_IOU,                # YOLO的IOU阈值
    
    # 帧率配置
    FPS,                     # 目标帧率
    FRAME_TIME,              # 每帧理论耗时
    MODEL2_DISPLAY_SCALE,    # 模型2显示缩放比例
    M2_DETECT_INTERVAL,      # 模态2检测间隔
    M3_DETECT_INTERVAL,      # 模态3检测间隔
    
    # 移动逻辑配置
    FOLLOW_THRESHOLD,        # 跟随阈值
    SAFE_ENEMY_DISTANCE,     # 安全距离
    AVOID_ENEMY_WEIGHT,      # 避敌权重
    MINIMAP_SCALE_FACTOR,    # 小地图缩放因子
    MINIMAP_SCALE_X,         # 小地图X轴到全屏的缩放比例
    MINIMAP_SCALE_Y,         # 小地图Y轴到全屏的缩放比例
    MOVE_INTERVAL,           # 移动指令间隔
    MOVE_DEADZONE,           # 移动死区
    DIAGONAL_THRESHOLD,      # 对角线移动阈值
    MOVE_SCALE_FACTOR,       # 移动缩放因子
    
    # 状态机配置
    MENU_CHECK_INTERVAL,          # 菜单检测间隔
    GAME_DETECTION_THRESHOLD,     # 游戏检测阈值
    MENU_GONE_THRESHOLD,          # 菜单消失判定时间
    STATE_STUCK_THRESHOLD,        # 状态卡住判定时间
    STATE_STUCK_VERIFY_COUNT,     # 状态卡住验证次数
    STATE_STUCK_VERIFY_INTERVAL,  # 状态卡住验证间隔
    
    # 字体配置
    FONT_PATH,               # 系统字体路径
    
    # 模型文件路径
    MODEL1_WEIGHTS,          # 模型1权重文件
    MODEL2_WEIGHTS,          # 模型2权重文件
    MODEL3_WEIGHTS,          # 模型3权重文件
    MODEL3_CONFIDENCE_THRESHOLD,  # 模型3置信度阈值
    CLASS_NAMES_FILE,        # 类别名称文件
    
    # 类别ID范围定义
    SELF_CLASS_ID_RANGE,     # 自己（绿色血条）类别ID范围
    TEAM_CLASS_ID_RANGE,     # 队友（蓝色血条）类别ID范围
    ENEMY_CLASS_ID_MIN,      # 敌人（红色血条）最小类别ID
    MODEL2_CLASS_NAMES,      # 模型2血条类别名称列表
    
    # 网格地图配置
    GRID_SIZE,               # 网格大小
    CELL_SIZE,               # 单元格大小
    G_CENTER_CACHE_DURATION, # G点中心缓存持续时间
    G_CENTER_MISS_THRESHOLD, # G点中心丢失阈值
    
    # 召唤师技能配置
    ACTIVE_SUMMONER_F,       # F键召唤师技能类型
    
    # 技能范围配置
    REDEMPTION_RANGE,        # 救赎技能范围
    HEAL_RANGE,              # 治疗术范围
    
    # 英雄身高偏移配置
    HERO_HEIGHT_OFFSET,      # 英雄身高偏移字典
    
    # 模态2血条坐标偏移配置
    HEAD_TO_FEET_OFFSET,              # 头顶到脚下的偏移
    HEAD_TO_FEET_OFFSET_GENERIC,      # 通用偏移
    
    # 战斗系统配置
    THREAT_DISTANCE_WEIGHT,           # 威胁评估中距离权重
    THREAT_COUNT_WEIGHT,              # 威胁评估中人数权重
    THREAT_HIGH_THRESHOLD,            # 高威胁等级阈值
    THREAT_MEDIUM_THRESHOLD,          # 中威胁等级阈值
    FOCUS_FIRE_HP_DROP_RATE,          # 集火判定血量下降速率阈值
    FOCUS_FIRE_TIME_WINDOW,           # 集火判定时间窗口
    RETREAT_HP_THRESHOLD,             # 撤退血量阈值
    FIGHT_ENEMY_DISTANCE,             # 交战判定距离
    SAFE_DISTANCE_FOR_RECALL,         # 安全回城距离

    # 地图预处理与寻路系统配置
    HERO_INFLATION_RADIUS,            # 障碍物膨胀半径
    PATHFINDING_MAX_ITERATIONS,       # A*最大迭代次数
    CLEARANCE_PENALTY_THRESHOLD,      # 间距惩罚阈值
    CLEARANCE_PENALTY_WEIGHT,         # 间距惩罚权重
    TURN_PENALTY,                     # 转向惩罚
    PATH_CACHE_SIZE,                  # 路径缓存大小
    PATH_REPLAN_DISTANCE,             # 重规划距离阈值
    SKELETON_MIN_CLEARANCE,           # 骨架最小间距
    LOOKAHEAD_DISTANCE,               # 前瞻距离
    CORRIDOR_TOLERANCE,               # 走廊容差
)

# ========== 从 templates 模块导入模板配置 ==========
# templates模块包含模板ROI和匹配阈值配置
from wzry_ai.config.templates import (
    TEMPLATE_ROI,                    # 模板ROI配置字典
    TEMPLATE_CONFIDENCE_THRESHOLDS,  # 模板匹配置信度阈值
    DEFAULT_TEMPLATE_CONFIDENCE,     # 默认模板置信度
    POPUP_DETECTION_THRESHOLD,       # 弹窗检测阈值
    TEMPLATE_GROUPS,                 # 多模板匹配分组
)

# ========== 从 heroes 包导入英雄配置 ==========
# heroes包包含英雄相关的所有配置
from wzry_ai.config.heroes import (
    # 分路相关
    LANE_HEROES,             # 分路英雄字典
    LANE_NAME_MAP,           # 分路名称映射
    HERO_LANE_MAP,           # 英雄分路反向映射
    get_heroes_by_lane,      # 获取分路英雄函数
    get_lane_by_hero,        # 获取英雄分路函数
    
    # 名称映射相关
    HERO_NAME_MAP,           # 英雄名称映射字典
    get_hero_pinyin,         # 中文转拼音函数
    get_hero_chinese,        # 拼音转中文函数
    get_hero_chinese_name,   # 获取中文名函数
    convert_priority_heroes, # 转换英雄列表函数
    PINYIN_TO_CHINESE,       # 拼音到中文映射（带后缀）
    PINYIN_BASE_TO_CHINESE,  # 基础拼音到中文映射
    
    # 辅助配置相关
    SUPPORTED_SUPPORT_HEROES,  # 支持的辅助英雄列表
    SUPPORT_HERO_CONFIG,       # 辅助英雄配置字典
    get_hero_config,           # 获取英雄配置函数
)

# ========== 从 emulator 模块导入模拟器配置 ==========
# emulator模块包含模拟器连接和识别配置
from wzry_ai.config.emulator import (
    EMULATOR_ADB_PATHS,      # 模拟器ADB路径字典
    EMULATOR_PORTS,          # 模拟器端口字典
    EMULATOR_MODELS,         # 模拟器型号标识
    WINDOW_PATTERNS,         # 窗口标题模式
    EXPECTED_WIDTH,          # 期望窗口宽度
    EXPECTED_HEIGHT,         # 期望窗口高度
    BORDER_WIDTH,            # 窗口边框宽度
    TITLE_HEIGHT,            # 窗口标题栏高度
    SCAN_DRIVES,             # 扫描磁盘分区
    CONFIG_FILE,             # 配置文件名
    EMULATOR_MODELS_FILE,    # 模拟器型号文件
)

# ========== 从 keys 模块导入按键映射配置 ==========
# keys模块集中管理所有游戏按键映射，避免硬编码分散在各模块
from wzry_ai.config.keys import (
    KEY_SKILL_1, KEY_SKILL_2, KEY_SKILL_ULT,       # 技能按键
    KEY_SUMMONER_F, KEY_SUMMONER_C,                  # 召唤师技能按键
    KEY_ACTIVE_ITEM,                                  # 装备主动技能按键
    KEY_LEVEL_ULT, KEY_LEVEL_1, KEY_LEVEL_2,         # 升级技能按键
    KEY_BUY_ITEM, KEY_ATTACK,                         # 购买装备/普攻按键
    KEY_MOVE_UP, KEY_MOVE_LEFT, KEY_MOVE_DOWN, KEY_MOVE_RIGHT,  # 移动方向按键
)

# ========== 向后兼容的别名 ==========
# FOLLOW_PRIORITY保持与原hero_lanes_config.py的兼容性
# 定义跟随优先级：优先跟随发育路，其次游走
FOLLOW_PRIORITY = [
    {'type': 'lane', 'value': 'lane_adc'},      # 第一优先级：发育路
    {'type': 'lane', 'value': 'lane_support'},  # 第二优先级：游走
]

# ========== 定义模块公开接口 ==========
# __all__列表声明了当使用"from config import *"时应该导入哪些名称
__all__ = [
    # base模块导出的变量
    'AUTO_LAUNCH',
    'GAME_MODE', 'BATTLE_MODE', 'V5_MODE', 'AI_BATTLE_MODE', 'AI_DIFFICULTY',
    'DEFAULT_SUPPORT_HERO',
    'HERO_SELECT_PRIORITY', 'HERO_SELECT_MAX_RETRY',
    'SCRCPY_MAX_SIZE', 'SCRCPY_BITRATE', 'SCRCPY_MAX_FPS',
    'LOCAL_SCRCPY_DIR', 'LOCAL_SCRCPY_ADB_PATH', 'LOCAL_SCRCPY_EXE_PATH',
    'ADB_DEVICE_IP', 'ADB_DEVICE_PORT', 'ADB_DEVICE_SERIAL', 'DEVICE_MODE', 'ADB_PATH',
    'DEFAULT_REGIONS',
    'MODEL1_CONFIDENCE_THRESHOLD', 'MODEL2_CONFIDENCE_THRESHOLD', 'YOLO_CONF', 'YOLO_IOU',
    'FPS', 'FRAME_TIME', 'MODEL2_DISPLAY_SCALE', 'M2_DETECT_INTERVAL', 'M3_DETECT_INTERVAL',
    'FOLLOW_THRESHOLD', 'SAFE_ENEMY_DISTANCE', 'AVOID_ENEMY_WEIGHT',
    'MINIMAP_SCALE_FACTOR', 'MINIMAP_SCALE_X', 'MINIMAP_SCALE_Y', 'MOVE_INTERVAL', 'MOVE_DEADZONE', 'DIAGONAL_THRESHOLD', 'MOVE_SCALE_FACTOR',
    'MENU_CHECK_INTERVAL', 'GAME_DETECTION_THRESHOLD', 'MENU_GONE_THRESHOLD',
    'STATE_STUCK_THRESHOLD', 'STATE_STUCK_VERIFY_COUNT', 'STATE_STUCK_VERIFY_INTERVAL',
    'FONT_PATH',
    'MODEL1_WEIGHTS', 'MODEL2_WEIGHTS', 'MODEL3_WEIGHTS', 'MODEL3_CONFIDENCE_THRESHOLD', 'CLASS_NAMES_FILE',
    'SELF_CLASS_ID_RANGE', 'TEAM_CLASS_ID_RANGE', 'ENEMY_CLASS_ID_MIN', 'MODEL2_CLASS_NAMES',
    'GRID_SIZE', 'CELL_SIZE', 'G_CENTER_CACHE_DURATION', 'G_CENTER_MISS_THRESHOLD',
    'REDEMPTION_RANGE', 'HEAL_RANGE', 'ACTIVE_SUMMONER_F', 'HERO_HEIGHT_OFFSET',
    'HEAD_TO_FEET_OFFSET', 'HEAD_TO_FEET_OFFSET_GENERIC',
    
    # 战斗系统配置
    'THREAT_DISTANCE_WEIGHT', 'THREAT_COUNT_WEIGHT',
    'THREAT_HIGH_THRESHOLD', 'THREAT_MEDIUM_THRESHOLD',
    'FOCUS_FIRE_HP_DROP_RATE', 'FOCUS_FIRE_TIME_WINDOW',
    'RETREAT_HP_THRESHOLD', 'FIGHT_ENEMY_DISTANCE', 'SAFE_DISTANCE_FOR_RECALL',

    # 地图预处理与寻路系统配置
    'HERO_INFLATION_RADIUS', 'PATHFINDING_MAX_ITERATIONS',
    'CLEARANCE_PENALTY_THRESHOLD', 'CLEARANCE_PENALTY_WEIGHT', 'TURN_PENALTY',
    'PATH_CACHE_SIZE', 'PATH_REPLAN_DISTANCE', 'SKELETON_MIN_CLEARANCE',
    'LOOKAHEAD_DISTANCE', 'CORRIDOR_TOLERANCE',

    # templates模块导出的变量
    'TEMPLATE_ROI',
    'TEMPLATE_CONFIDENCE_THRESHOLDS',
    'DEFAULT_TEMPLATE_CONFIDENCE',
    'POPUP_DETECTION_THRESHOLD',
    'TEMPLATE_GROUPS',
    
    # heroes模块导出的变量和函数
    'LANE_HEROES', 'LANE_NAME_MAP', 'HERO_LANE_MAP',
    'get_heroes_by_lane', 'get_lane_by_hero',
    'HERO_NAME_MAP', 'get_hero_pinyin', 'get_hero_chinese', 'get_hero_chinese_name',
    'convert_priority_heroes', 'PINYIN_TO_CHINESE', 'PINYIN_BASE_TO_CHINESE',
    'SUPPORTED_SUPPORT_HEROES', 'SUPPORT_HERO_CONFIG', 'get_hero_config',
    
    # emulator模块导出的变量
    'EMULATOR_ADB_PATHS', 'EMULATOR_PORTS', 'EMULATOR_MODELS', 'WINDOW_PATTERNS',
    'EXPECTED_WIDTH', 'EXPECTED_HEIGHT', 'BORDER_WIDTH', 'TITLE_HEIGHT',
    'SCAN_DRIVES', 'CONFIG_FILE', 'EMULATOR_MODELS_FILE',
    
    # 向后兼容的变量
    'FOLLOW_PRIORITY',
    
    # keys模块导出的按键映射常量
    'KEY_SKILL_1', 'KEY_SKILL_2', 'KEY_SKILL_ULT',
    'KEY_SUMMONER_F', 'KEY_SUMMONER_C',
    'KEY_ACTIVE_ITEM',
    'KEY_LEVEL_ULT', 'KEY_LEVEL_1', 'KEY_LEVEL_2',
    'KEY_BUY_ITEM', 'KEY_ATTACK',
    'KEY_MOVE_UP', 'KEY_MOVE_LEFT', 'KEY_MOVE_DOWN', 'KEY_MOVE_RIGHT',
]
