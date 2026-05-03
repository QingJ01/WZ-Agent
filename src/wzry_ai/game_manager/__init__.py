"""Game Manager Package - 游戏状态管理模块

功能说明：
    本模块是王者荣耀AI的核心状态管理包，负责检测游戏界面状态、
    执行状态转换、处理弹窗等任务。

主要组件：
    - state_detector: 状态检测器主类
    - state_definitions: 游戏状态定义
    - state_transitions: 状态转换规则
    - detection_strategies: 检测策略实现
    - template_matcher: 模板匹配器
    - click_executor: 点击执行器
"""

# 从状态检测器模块导入核心类
from .state_detector import GameStateDetector, DetectionResult
# 从模板匹配器模块导入匹配相关类
from .template_matcher import TemplateMatcher, MatchResult
# 从点击执行器模块导入点击执行类
from .click_executor import ClickExecutor

# 从状态定义模块导入状态枚举和工具函数
from .state_definitions import (
    GameState,              # 游戏状态枚举类，定义所有可能的游戏状态
    STATE_SIGNATURES,       # 状态特征映射表，存储每个状态的检测特征
    get_state_flow,         # 获取状态所属流程组的函数
    get_state_description,  # 获取状态描述文本的函数
    is_startup_state,       # 判断是否为启动流程状态的函数
    is_game_active          # 判断游戏是否处于活跃状态的函数
)

# 从状态转换模块导入转换规则和工具函数
from .state_transitions import (
    TransitionRule,           # 状态转换规则数据类
    STATE_TRANSITION_RULES,   # 全局状态转换规则字典
    get_transition_rules,     # 获取指定状态转换规则的函数
    get_possible_next_states, # 获取可能的下一个状态列表的函数
    is_valid_transition       # 检查状态转换是否有效的函数
)

# 从检测策略模块导入策略相关类和常量
from .detection_strategies import (
    DetectionLevel,               # 检测级别枚举（普通/深度/紧急）
    DetectionStrategy,            # 检测策略抽象基类
    HierarchicalDetectionStrategy, # 层级检测策略类（母-子模式检测）
    DeepDetectionStrategy,        # 深度检测策略类（全量扫描）
    DetectionStrategyFactory,     # 检测策略工厂类（创建策略实例）
    HERO_AVATAR_PARENT_MODES,     # 需要进行英雄头像检测的母模式集合
    PARENT_MODE_TO_STATE          # 母模式到状态名的映射字典
)

# 从状态可视化模块导入可视化相关类
from .state_visualizer import StateVisualizer, StateTransition, FlowProgress
# 从弹窗处理模块导入弹窗处理相关类
from .popup_handler import PopupHandler, PopupAction

# 模块版本号
__version__ = '1.0.0'

# 公开接口列表（控制from module import *时导入的内容）
__all__ = [
    # 核心检测类
    'GameStateDetector',      # 游戏状态检测器主类
    'DetectionResult',        # 检测结果数据类
    # 模板匹配和点击执行类
    'TemplateMatcher',        # 模板匹配器类
    'MatchResult',            # 匹配结果数据类
    'ClickExecutor',          # 点击执行器类
    # 状态定义相关
    'GameState',              # 游戏状态枚举
    'STATE_SIGNATURES',       # 状态特征映射表
    'get_state_flow',         # 获取状态流程组函数
    'get_state_description',  # 获取状态描述函数
    'is_startup_state',       # 判断是否启动状态函数
    'is_game_active',         # 判断是否游戏活跃函数
    # 状态转换相关
    'TransitionRule',         # 转换规则数据类
    'STATE_TRANSITION_RULES', # 全局转换规则字典
    'get_transition_rules',   # 获取转换规则函数
    'get_possible_next_states', # 获取可能下一状态函数
    'is_valid_transition',    # 检查转换有效性函数
    # 检测策略相关
    'DetectionLevel',         # 检测级别枚举
    'DetectionStrategy',      # 策略抽象基类
    'HierarchicalDetectionStrategy', # 层级检测策略
    'DeepDetectionStrategy',  # 深度检测策略
    'DetectionStrategyFactory', # 策略工厂
    'HERO_AVATAR_PARENT_MODES', # 英雄头像检测母模式集合
    'PARENT_MODE_TO_STATE',   # 母模式到状态映射
    # 可视化和弹窗处理
    'StateVisualizer',        # 状态可视化器
    'StateTransition',        # 状态转换记录类
    'FlowProgress',           # 流程进度类
    'PopupHandler',           # 弹窗处理器
    'PopupAction',            # 弹窗动作枚举
]
