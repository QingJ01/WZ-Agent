"""
模板配置模块 - ROI和模板匹配阈值配置

功能说明：
    本模块配置模板匹配所需的ROI（感兴趣区域）坐标和置信度阈值，
    用于游戏状态检测、界面识别和自动化操作。

参数说明：
    无直接参数，通过导入变量使用

返回值说明：
    无直接返回值，提供模板ROI和阈值配置常量
"""

# ========== 模板ROI配置 ==========
# TEMPLATE_ROI字典定义各界面元素在屏幕上的位置和大小
# 格式：'模板名': {'x': 横坐标, 'y': 纵坐标, 'w': 宽度, 'h': 高度}
TEMPLATE_ROI = {
    # 启动相关界面元素
    'start_game': {'x': 836, 'y': 792, 'w': 238, 'h': 106}, # 开始游戏按钮
    
    # 大厅相关界面元素
    'game_lobby': {'x': 379, 'y': 770, 'w': 208, 'h': 104}, # 游戏大厅入口
    
    # 对战模式选择
    'battle': {'x': 688, 'y': 762, 'w': 162, 'h': 114},     # 对战模式按钮
    
    # 排位模式选择
    'ranking': {'x': 1076, 'y': 763, 'w': 160, 'h': 112},   # 排位赛按钮
    
    # 5V5王者峡谷模式
    '5v5_canyon': {'x': 479, 'y': 645, 'w': 236, 'h': 194}, # 5V5王者峡谷图标
    
    # 对战模式选择标题
    'battle_mode': {'x': 184, 'y': 38, 'w': 198, 'h': 65},  # 对战模式标题

    # 王者峡谷界面标题
    'wangzhe_canyon': {'x': 194, 'y': 26, 'w': 197, 'h': 65},  # 王者峡谷标题

    # 峡谷对战按钮
    'canyon_match': {'x': 1445, 'y': 845, 'w': 303, 'h': 93},   # 开始匹配按钮
    
    # 人机模式相关
    'ai_mode': {'x': 1037, 'y': 842, 'w': 247, 'h': 104},       # 人机模式按钮
    'ai_mode_choose': {'x': 166, 'y': 17, 'w': 212, 'h': 88},   # 人机模式选择标题
    
    # 人机难度选择
    'ai_bronze': {'x': 658, 'y': 232, 'w': 444, 'h': 58},       # 青铜难度
    'ai_diamond': {'x': 658, 'y': 566, 'w': 442, 'h': 60},      # 钻石难度
    'ai_gold': {'x': 658, 'y': 400, 'w': 452, 'h': 57},         # 黄金难度
    'ai_master': {'x': 657, 'y': 903, 'w': 413, 'h': 59},       # 王者难度
    'ai_quick': {'x': 31, 'y': 517, 'w': 493, 'h': 190},        # 快速模式
    'ai_recommend': {'x': 567, 'y': 179, 'w': 105, 'h': 113},    # 推荐难度
    'ai_standard': {'x': 34, 'y': 294, 'w': 491, 'h': 189},     # 标准模式
    'ai_star': {'x': 656, 'y': 732, 'w': 423, 'h': 61},         # 星耀难度
    'ai_mode1': {'x': 176, 'y': 27, 'w': 192, 'h': 68},         # 人机模式标题
    'start_practice': {'x': 1416, 'y': 811, 'w': 339, 'h': 86}, # 开始练习按钮
    
    # 组队房间界面
    'start_match': {'x': 985, 'y': 940, 'w': 356, 'h': 104},     # 开始匹配按钮
    
    # 匹配确认界面
    'match_successful': {'x': 849, 'y': 188, 'w': 226, 'h': 62},  # 匹配成功提示
    # 'match_confirm': {'x': 798, 'y': 789, 'w': 437, 'h': 109},  # 已改为全局匹配
    
    # 选英雄主界面
    'select_hero': {'x': 43, 'y': 17, 'w': 100, 'h': 58},       # 选英雄标题
    'arrow_right': {'x': 360, 'y': 439, 'w': 80, 'h': 115},     # 右箭头按钮
    
    # 分路选择界面
    'all_lane': {'x': 50, 'y': 10, 'w': 140, 'h': 70},          # 全部分路
    'lane_top': {'x': 285, 'y': 10, 'w': 140, 'h': 70},         # 对抗路
    'lane_jungle': {'x': 522, 'y': 10, 'w': 140, 'h': 70},      # 打野
    'lane_mid': {'x': 759, 'y': 10, 'w': 140, 'h': 70},         # 中路
    'lane_adc': {'x': 996, 'y': 10, 'w': 140, 'h': 70},         # 发育路
    'lane_support': {'x': 1232, 'y': 10, 'w': 140, 'h': 70},    # 游走
    
    # 结算界面
    'continue': {'x': 839, 'y': 894, 'w': 240, 'h': 72},              # 继续按钮
    'return_to_the_room': {'x': 963, 'y': 925, 'w': 289, 'h': 104},   # 返回房间按钮
    'match_statistics': {'x': 21, 'y': 925, 'w': 350, 'h': 99},       # 比赛统计按钮
    'defeat': {'x': 793, 'y': 440, 'w': 324, 'h': 132},               # 失败标志
}

# ========== 模板匹配置信度阈值配置 ==========
# TEMPLATE_CONFIDENCE_THRESHOLDS字典定义各游戏状态的模板匹配阈值
# 用于判断当前处于哪个游戏界面/状态
# 格式说明：
#   'parent_template': 主模板名称（用于确认当前状态）
#   'threshold': 主模板匹配的最低置信度
#   'sub_modes': 子模式及其阈值（用于进一步确认子状态）
#   'exclude_templates': 需要排除的模板列表
TEMPLATE_CONFIDENCE_THRESHOLDS = {
    'simulator_desktop': {  # 模拟器桌面状态
        'parent_template': 'wzry_icon',  # 主模板：王者荣耀图标
        'threshold': 0.70,               # 匹配阈值：70%
        'sub_modes': None,               # 无子模式
    },
    'server_select': {      # 服务器选择界面
        'parent_template': 'start_game',  # 主模板：开始游戏按钮
        'threshold': 0.90,
        'sub_modes': None,
    },
    'game_hall': {          # 游戏大厅界面
        'parent_template': 'game_lobby',  # 主模板：游戏大厅
        'threshold': 0.90,
        'sub_modes': {                    # 子模式：大厅内的不同入口
            'battle': 0.90,   # 对战模式入口
            'ranking': 0.90,  # 排位赛入口
        },
    },
    'battle_mode_select': {  # 对战模式选择界面
        'parent_template': 'battle_mode',
        'threshold': 0.80,
        'sub_modes': {
            '5v5_canyon': 0.80,  # 5V5王者峡谷选项
        },
        'exclude_templates': ['ai_mode', 'canyon_match'],  # 排除王者峡谷界面的按钮，防止跨界面误检测
    },
    'wangzhe_canyon': {     # 王者峡谷界面
        'parent_template': 'wangzhe_canyon',
        'threshold': 0.75,
        'sub_modes': {
            'ai_mode': 0.75,       # 人机模式按钮
            'canyon_match': 0.75,  # 峡谷对战按钮
        },
        'exclude_templates': ['match_confirm'],  # 排除匹配确认模板
    },
    'ai_mode_select': {     # 人机模式设置界面
        'parent_template': 'ai_mode_choose',
        'threshold': 0.80,
        'sub_modes': {                    # 各种人机模式和难度选项
            'ai_standard': 0.80,          # 标准模式
            'ai_quick': 0.80,             # 快速模式
            'ai_recommend': 0.80,         # 推荐难度
            'ai_bronze': 0.80,            # 青铜难度
            'ai_gold': 0.80,              # 黄金难度
            'ai_diamond': 0.80,           # 钻石难度
            'ai_star': 0.80,              # 星耀难度
            'ai_master': 0.80,            # 王者难度
            'start_practice': 0.80,       # 开始练习按钮
        },
    },
    'ranking_match_select': {  # 排位赛匹配选择
        'parent_template': 'ranking_match',
        'threshold': 0.85,
        'sub_modes': None,
    },
    'team_5v5_room': {      # 5V5组队房间
        'parent_template': 'start_match',  # 主模板：开始匹配按钮
        'threshold': 0.85,
        'sub_modes': None,
        'exclude_templates': ['match_confirm'],
    },
    'match_confirmation': {  # 匹配确认界面
        'parent_template': 'match_confirm',
        'threshold': 0.75,    # 从 0.55 提升到 0.75，防止在大厅界面误匹配
        'sub_modes': None,
    },
    'hero_select_main': {   # 选英雄主界面
        'parent_template': 'select_hero',
        'threshold': 0.90,
        'sub_modes': None,  # 英雄选择由 hero_selector 处理，无需子模式检测
    },
    'lane_select': {        # 分路选择界面
        'parent_template': ['all_lane', 'lane_top', 'lane_jungle', 'lane_mid', 'lane_adc', 'lane_support'],
        'threshold': 0.80,
        'sub_modes': {        # 各分路选项
            'lane_top': 0.80,      # 对抗路
            'lane_jungle': 0.80,   # 打野
            'lane_mid': 0.80,      # 中路
            'lane_adc': 0.80,      # 发育路
            'lane_support': 0.80,  # 游走
        },
    },
    'ranking_hero_select': {  # 排位赛选英雄
        'parent_template': 'ranking_hero_select',
        'threshold': 0.80,
        'sub_modes': None,
    },
    'loading_screen': {     # 游戏加载界面
        'parent_template': 'VS',  # VS标志
        'threshold': 0.90,
        'sub_modes': None,
    },
    'game_result': {        # 游戏结果界面（胜利/失败）
        'parent_template': ['victory', 'victory1', 'defeat'],
        'threshold': 0.90,
        'sub_modes': None,
    },
    'mvp_settlement': {     # MVP结算界面
        'parent_template': 'continue',  # 继续按钮
        'threshold': 0.80,
        'sub_modes': None,
    },
    'post_match_stats': {   # 赛后统计界面
        'parent_template': 'match_statistics',
        'threshold': 0.80,
        'sub_modes': {
            'return_to_the_room': 0.80,  # 返回房间按钮
        },
    },
}

# ========== 状态检测的默认置信度阈值 ==========
DEFAULT_TEMPLATE_CONFIDENCE = 0.90   # 默认模板匹配置信度阈值
POPUP_DETECTION_THRESHOLD = 0.90     # 弹窗检测阈值

# ========== MTM 多模板匹配分组配置 ==========
# TEMPLATE_GROUPS定义多模板匹配的分组配置
# 用于同时检测一组相关模板，提高检测效率
# 格式说明：
#   'templates': 模板名称列表
#   'threshold': 该组的匹配阈值
#   'N_object': 期望检测到的目标数量
#   'description': 分组描述
TEMPLATE_GROUPS = {
    'settlement': {  # 结算界面组
        'templates': ['victory', 'victory1', 'defeat'],  # 胜利和失败模板
        'threshold': 0.70,
        'N_object': 1,  # 期望检测到1个结果
        'description': '游戏结算界面（胜利/失败）',
    },
    'confirm': {     # 确认按钮组
        'templates': ['match_confirm'],
        'threshold': 0.60,
        'N_object': 1,
        'description': '匹配确认按钮',
    },
    'close': {       # 关闭按钮组
        'templates': ['close1', 'close2', 'close3', 'close4'],  # 多种关闭按钮样式
        'threshold': 0.80,
        'N_object': 1,
        'description': '关闭/返回按钮',
    },
    'continue': {    # 继续按钮组
        'templates': ['continue'],
        'threshold': 0.70,
        'N_object': 1,
        'description': '结算后继续按钮',
    },
}
