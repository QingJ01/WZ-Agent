# -*- coding: utf-8 -*-
"""
状态转换规则模块 - 定义状态间的转换关系

功能说明:
    本模块定义了游戏状态之间的转换规则和约束。
    每个状态都有对应的转换规则列表，指定了可能转移到的目标状态及其优先级。
    这些规则用于状态机判断状态转换是否合法，以及预测下一个可能的状态。

主要组件:
    - TransitionRule: 状态转换规则数据类
    - STATE_TRANSITION_RULES: 全局状态转换规则字典
    - 辅助函数: get_transition_rules, get_possible_next_states等
"""

# 导入数据类装饰器，用于创建转换规则类
from dataclasses import dataclass
# 导入类型提示，用于声明列表、字典和可选类型
from typing import List, Dict, Optional
# 从状态定义模块导入游戏状态枚举
from .state_definitions import GameState


@dataclass
class TransitionRule:
    """
    状态转换规则数据类
    
    功能说明:
        定义了从一个状态转换到另一个状态的规则，
        包含目标状态、优先级和可选条件。
    
    参数说明:
        target_state: 转换的目标状态（GameState枚举值）
        priority: 转换优先级，数字越小优先级越高，默认0
        condition: 可选的条件描述字符串，用于说明转换条件
    """
    target_state: GameState      # 目标状态枚举值
    priority: int = 0            # 优先级，数字越小优先级越高
    condition: Optional[str] = None  # 可选条件描述


# 全局状态转换规则字典
# 键是源状态（GameState枚举值），值是该状态可以转换到的规则列表
# 每个规则列表按优先级排序（数字小的在前）
STATE_TRANSITION_RULES: Dict[GameState, List[TransitionRule]] = {
    # ========== 启动流程组 ==========
    # 未知状态可以转换到多种初始状态
    GameState.UNKNOWN: [
        TransitionRule(GameState.LAUNCHER, priority=0),      # 优先检测启动器
        TransitionRule(GameState.HALL, priority=1),          # 可能游戏已在大厅
        TransitionRule(GameState.HERO_SELECT, priority=2),   # 可能已在选英雄
        TransitionRule(GameState.IN_GAME, priority=3),       # 可能已在游戏中
        TransitionRule(GameState.GAME_END, priority=0),      # 结算最高优先级
    ],
    
    # 启动器状态转换规则
    GameState.LAUNCHER: [
        TransitionRule(GameState.SELECT_ZONE, priority=0),   # 点击游戏图标后进入选区
        TransitionRule(GameState.HALL, priority=1),          # 如果游戏已在运行
    ],
    
    # 更新日志弹窗转换规则
    GameState.UPDATE_LOG: [
        TransitionRule(GameState.SELECT_ZONE, priority=0),   # 关闭弹窗后进入选区
        TransitionRule(GameState.HALL, priority=1),          # 可能直接到大厅
    ],
    
    # 选区界面转换规则
    GameState.SELECT_ZONE: [
        TransitionRule(GameState.HALL, priority=0),          # 点击进入游戏后到大厅
        TransitionRule(GameState.UPDATE_LOG, priority=1),    # 可能有更新弹窗
    ],
    
    # ========== 大厅分支选择 ==========
    # 大厅可以进入对战或排位模式
    GameState.HALL: [
        TransitionRule(GameState.BATTLE_MODE_SELECT, priority=0),   # 点击对战按钮
        TransitionRule(GameState.RANKING_MATCH_SELECT, priority=0), # 点击排位按钮
        TransitionRule(GameState.HERO_SELECT, priority=1),          # 可能已在房间
    ],
    
    # ========== 对战模式流程 ==========
    # 对战模式选择界面转换规则
    GameState.BATTLE_MODE_SELECT: [
        TransitionRule(GameState.BATTLE_5V5_SUB, priority=0),       # 点击5V5选项
        TransitionRule(GameState.HALL, priority=1),                 # 返回大厅
    ],
    
    # 5V5子菜单转换规则
    GameState.BATTLE_5V5_SUB: [
        TransitionRule(GameState.BATTLE_5V5_TYPE, priority=0),      # 点击王者峡谷
        TransitionRule(GameState.BATTLE_MODE_SELECT, priority=1),   # 返回上级
    ],
    
    # 对战类型选择转换规则
    GameState.BATTLE_5V5_TYPE: [
        TransitionRule(GameState.BATTLE_AI_MODE, priority=0),       # 选择人机对战
        TransitionRule(GameState.BATTLE_ROOM, priority=1),          # 选择匹配对战
        TransitionRule(GameState.BATTLE_5V5_SUB, priority=2),       # 返回
    ],
    
    # 人机模式选择转换规则
    GameState.BATTLE_AI_MODE: [
        TransitionRule(GameState.BATTLE_AI_DIFFICULTY, priority=0), # 选择模式后进入难度选择
        TransitionRule(GameState.BATTLE_5V5_TYPE, priority=1),      # 返回
    ],
    
    # 人机难度选择转换规则
    GameState.BATTLE_AI_DIFFICULTY: [
        TransitionRule(GameState.BATTLE_ROOM, priority=0),          # 选择难度后进入房间
        TransitionRule(GameState.BATTLE_AI_MODE, priority=1),       # 返回
    ],
    
    # 对战房间转换规则
    GameState.BATTLE_ROOM: [
        TransitionRule(GameState.MATCHING, priority=0),             # 点击开始匹配
        TransitionRule(GameState.MATCH_FOUND, priority=0),          # 匹配成功弹窗
        TransitionRule(GameState.HALL, priority=1),                 # 返回大厅
    ],
    
    # ========== 排位模式流程 ==========
    # 排位赛模式选择界面转换规则
    GameState.RANKING_MATCH_SELECT: [
        TransitionRule(GameState.BATTLE_ROOM, priority=0),          # 点击进入房间
        TransitionRule(GameState.HALL, priority=1),                 # 返回大厅
    ],
    
    # 排位赛选英雄界面转换规则
    GameState.RANKING_HERO_SELECT: [
        TransitionRule(GameState.GAME_LOADING_VS, priority=0),      # 锁定英雄后进入加载
        TransitionRule(GameState.BATTLE_ROOM, priority=1),          # 返回房间
    ],
    
    # 排位禁选界面转换规则（预留）
    GameState.RANKING_BAN_PICK: [
        TransitionRule(GameState.GAME_LOADING_VS, priority=0),      # 禁选完成后进入加载
        TransitionRule(GameState.BATTLE_ROOM, priority=1),          # 返回房间
    ],
    
    # ========== 通用匹配流程 ==========
    # 匹配中状态转换规则
    GameState.MATCHING: [
        TransitionRule(GameState.MATCH_FOUND, priority=0),          # 匹配成功
        TransitionRule(GameState.BATTLE_ROOM, priority=1),          # 取消匹配
    ],
    
    # 匹配成功弹窗转换规则
    GameState.MATCH_FOUND: [
        TransitionRule(GameState.MATCH_CONFIRMED, priority=0),      # 点击确认
        TransitionRule(GameState.BATTLE_ROOM, priority=1),          # 拒绝匹配
    ],
    
    # 已确认匹配转换规则
    GameState.MATCH_CONFIRMED: [
        TransitionRule(GameState.HERO_SELECT, priority=0),          # 人机模式选英雄
        TransitionRule(GameState.RANKING_HERO_SELECT, priority=0),  # 排位赛选英雄
        TransitionRule(GameState.MATCHING, priority=1),             # 可能重新匹配
    ],
    
    # ========== 游戏核心 ==========
    # 选英雄界面转换规则
    GameState.HERO_SELECT: [
        TransitionRule(GameState.GAME_LOADING_VS, priority=0),      # 选择英雄后进入加载
        TransitionRule(GameState.IN_GAME, priority=1),              # 可能跳过VS画面
        TransitionRule(GameState.LANE_SELECT, priority=2),          # 进入分路选择
    ],
    
    # 分路选择转换规则（子状态）
    GameState.LANE_SELECT: [
        TransitionRule(GameState.HERO_SELECT, priority=0),          # 分路是子状态，返回选英雄
    ],
    
    # VS加载画面转换规则
    GameState.GAME_LOADING_VS: [
        TransitionRule(GameState.IN_GAME, priority=0),              # 加载完成后进入游戏
    ],
    
    # 游戏中状态转换规则
    GameState.IN_GAME: [
        TransitionRule(GameState.GAME_END, priority=0),             # 游戏结束
        TransitionRule(GameState.HEALTH_COOLDOWN, priority=1),      # 触发防沉迷
    ],
    
    # ========== 结算流程 ==========
    # 结算界面转换规则
    GameState.GAME_END: [
        TransitionRule(GameState.MVP_DISPLAY, priority=0),          # 显示MVP
        TransitionRule(GameState.POST_MATCH_STATS, priority=1),     # 可能跳过MVP
    ],
    
    # MVP展示转换规则
    GameState.MVP_DISPLAY: [
        TransitionRule(GameState.POST_MATCH_STATS, priority=0),     # 进入赛后数据
    ],
    
    # 赛后数据转换规则
    GameState.POST_MATCH_STATS: [
        TransitionRule(GameState.RETURN_TO_ROOM, priority=0),       # 返回房间
        TransitionRule(GameState.HALL, priority=1),                 # 可能直接回大厅
    ],
    
    # 返回房间转换规则
    GameState.RETURN_TO_ROOM: [
        TransitionRule(GameState.BATTLE_ROOM, priority=0),          # 返回对战/排位房间
        TransitionRule(GameState.HALL, priority=1),                 # 返回大厅
    ],
    
    # ========== 特殊状态 ==========
    # 防沉迷冷却转换规则
    GameState.HEALTH_COOLDOWN: [
        TransitionRule(GameState.HALL, priority=0),                 # 冷却结束后返回大厅
    ],
}


def get_transition_rules(state: str) -> List[TransitionRule]:
    """
    获取指定状态的转换规则
    
    参数说明:
        state: 状态名称字符串
    
    返回值:
        List[TransitionRule]: 该状态的转换规则列表，按优先级排序
                              如果状态不存在则返回空列表
    
    功能描述:
        根据状态名称查找对应的转换规则，并按优先级排序返回。
        优先级数字越小，排序越靠前。
    """
    try:
        # 将字符串转换为GameState枚举值
        state_enum = GameState(state)
        # 从规则字典中获取该状态的规则列表
        rules = STATE_TRANSITION_RULES.get(state_enum, [])
        # 按优先级排序（数字小的在前）
        return sorted(rules, key=lambda r: r.priority)
    except ValueError:
        # 状态字符串无效，返回空列表
        return []


def get_possible_next_states(state: str) -> List[str]:
    """
    获取可能的下一个状态列表
    
    参数说明:
        state: 状态名称字符串
    
    返回值:
        List[str]: 可能的下一个状态名称列表，按优先级排序
    
    功能描述:
        获取从指定状态可以转换到的所有目标状态名称。
        用于状态机预测下一个可能的状态。
    """
    # 获取该状态的所有转换规则
    rules = get_transition_rules(state)
    # 提取规则中的目标状态名称
    return [rule.target_state.value for rule in rules]


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """
    检查状态转换是否有效
    
    参数说明:
        from_state: 源状态名称字符串
        to_state: 目标状态名称字符串
    
    返回值:
        bool: 如果转换有效返回True，否则返回False
    
    功能描述:
        检查从源状态转换到目标状态是否在规则允许范围内。
        用于验证状态转换的合法性。
    """
    # 获取源状态可以转换到的所有状态
    next_states = get_possible_next_states(from_state)
    # 检查目标状态是否在允许列表中
    return to_state in next_states
