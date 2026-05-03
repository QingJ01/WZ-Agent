# -*- coding: utf-8 -*-
"""
状态定义模块 - 定义所有游戏状态和特征

功能说明：
    本模块定义了王者荣耀AI中所有可能的游戏状态，包括启动流程、
    对战流程、匹配流程、游戏核心流程和结算流程等。
    每个状态都有对应的特征签名，用于模板匹配检测。

主要组件：
    - GameState: 游戏状态枚举类
    - StateSignature: 状态特征签名数据类
    - STATE_SIGNATURES: 全局状态特征映射表
    - 辅助函数: get_state_flow, is_startup_state等
"""

# 导入枚举类，用于定义游戏状态枚举
from enum import Enum

# 导入数据类装饰器，用于创建状态特征签名类
from dataclasses import dataclass

# 导入类型提示，用于声明列表、可选类型和可调用对象
from typing import Callable, List, Optional

# 尝试从配置模块导入模板置信度配置
try:
    from wzry_ai.config import (
        TEMPLATE_CONFIDENCE_THRESHOLDS,
        DEFAULT_TEMPLATE_CONFIDENCE,
    )
except ImportError:
    # 如果导入失败（配置模块不存在），使用默认空字典和默认值
    TEMPLATE_CONFIDENCE_THRESHOLDS = {}  # 空字典表示没有特定模板的置信度配置
    DEFAULT_TEMPLATE_CONFIDENCE = 0.8  # 默认置信度阈值为0.8


def get_confidence(template_name: str) -> float:
    """
    从配置中获取模板置信度阈值

    参数说明:
        template_name: 模板名称字符串

    返回值:
        float: 该模板的置信度阈值，如果未配置则返回默认值

    功能描述:
        根据模板名称查询对应的置信度阈值，用于判断模板匹配是否成功
    """
    # 从配置字典中获取指定模板的配置
    config = TEMPLATE_CONFIDENCE_THRESHOLDS.get(
        template_name, DEFAULT_TEMPLATE_CONFIDENCE
    )
    # 如果获取到的是字典，提取其中的 threshold 值
    if isinstance(config, dict):
        return config.get("threshold", DEFAULT_TEMPLATE_CONFIDENCE)
    # 否则直接返回配置值（float 或默认值）
    return config


class GameState(Enum):
    """
    游戏状态枚举 - 按流程分组

    功能说明:
        定义了王者荣耀游戏中所有可能的界面状态，从启动游戏到结算的完整流程。
        每个状态对应一个字符串值，用于状态检测和转换。

    流程分组:
        - 启动流程组: 从启动器到大厅的初始流程
        - 防沉迷流程: 健康系统相关状态
        - 对战模式流程: 人机对战的选择流程
        - 排位模式流程: 排位赛的匹配和选英雄流程
        - 匹配流程组: 匹配中和确认流程
        - 游戏核心流程: 选英雄、加载、战斗
        - 结算流程组: 比赛结束后的结算流程
    """

    # ========== 启动流程组 ==========
    # 未知状态表示当前无法识别界面或初始状态
    UNKNOWN = "unknown"
    # 启动器状态，表示在MuMu模拟器桌面看到游戏图标
    LAUNCHER = "launcher"
    # 更新日志弹窗，游戏启动后可能显示的更新内容
    UPDATE_LOG = "update_log"
    # 选区界面，选择游戏服务器大区
    SELECT_ZONE = "select_zone"
    # 游戏大厅，主界面入口，可以进入对战或排位
    HALL = "hall"

    # ========== 防沉迷流程 ==========
    # 防沉迷弹窗，提示休息或健康系统警告
    REST_POPUP = "rest_popup"
    # 防沉迷冷却中，需要等待一段时间后才能继续游戏
    HEALTH_COOLDOWN = "health_cooldown"

    # ========== 对战模式流程 ==========
    # 对战模式选择界面，可以选择5V5、3V3等模式
    BATTLE_MODE_SELECT = "battle_mode_select"
    # 5V5子菜单，显示王者峡谷等选项
    BATTLE_5V5_SUB = "battle_5v5_sub"
    # 对战类型选择，可以选择匹配对战或人机对战
    BATTLE_5V5_TYPE = "battle_5v5_type"
    # 人机模式选择，标准模式或快速模式
    BATTLE_AI_MODE = "battle_ai_mode"
    # 人机难度选择界面，从青铜到王者
    BATTLE_AI_DIFFICULTY = "battle_ai_difficulty"
    # 已选难度状态，等待点击开始练习按钮
    BATTLE_START_PRACTICE = "battle_start_practice"
    # 对战房间，等待开始匹配
    BATTLE_ROOM = "battle_room"

    # ========== 排位模式流程 ==========
    # 排位赛模式选择界面，大厅点击排位按钮后进入
    RANKING_MATCH_SELECT = "ranking_match_select"
    # 排位赛普通选英雄界面，选择英雄并锁定
    RANKING_HERO_SELECT = "ranking_hero_select"
    # 禁选界面，征召模式的禁用和选择英雄阶段（预留）
    RANKING_BAN_PICK = "ranking_ban_pick"

    # ========== 匹配流程组 ==========
    # 匹配中状态，正在寻找对局
    MATCHING = "matching"
    # 匹配成功弹窗，显示匹配成功需要确认
    MATCH_FOUND = "match_found"
    # 已确认匹配状态，玩家已点击确认按钮
    MATCH_CONFIRMED = "match_confirmed"

    # ========== 游戏核心流程 ==========
    # 选英雄界面，人机模式下的英雄选择
    HERO_SELECT = "hero_select"
    # 分路选择，在选英雄界面内选择上路、中路等
    LANE_SELECT = "lane_select"
    # VS加载画面，显示双方阵容的加载界面
    GAME_LOADING_VS = "game_loading_vs"
    # 战斗中状态，实际游戏进行中的状态
    IN_GAME = "in_game"

    # ========== 结算流程组 ==========
    # 结算界面，显示胜利或失败
    GAME_END = "game_end"
    # MVP展示界面，显示本局MVP玩家
    MVP_DISPLAY = "mvp_display"
    # 赛后数据统计界面
    POST_MATCH_STATS = "post_match_stats"
    # 返回房间过渡状态
    RETURN_TO_ROOM = "return_to_room"


@dataclass
class StateSignature:
    """
    状态特征签名数据类

    功能说明:
        定义了每个游戏状态的检测特征，包括用于识别的模板、
        置信度阈值、所属流程组等信息。

    参数说明:
        primary_templates: 主要检测模板列表，任一模板匹配成功即认为可能处于该状态
        exclude_templates: 排除模板列表，如果匹配到这些模板则排除该状态
        required_confidence: 识别该状态所需的最小置信度，默认0.7
        group: 该状态所属的流程组名称，如"startup"、"game_core"等
        description: 该状态的中文描述文本
        validator: 可选的辅助验证函数，用于额外验证状态是否匹配
    """

    # 主要检测模板列表，存储模板名称字符串，任一匹配即可认为可能处于该状态
    primary_templates: List[str]
    # 排除模板列表，如果画面中出现这些模板，则排除当前状态的可能性
    exclude_templates: List[str]
    # 识别该状态所需的最小置信度阈值，低于此值认为匹配失败
    required_confidence: float = 0.7
    # 所属流程组，用于状态分组管理，如"startup"表示启动流程
    group: str = "unknown"
    # 状态描述文本，用于日志输出和调试显示
    description: str = ""
    # 可选的辅助验证函数，用于进行额外的自定义验证逻辑
    validator: Optional[Callable[..., bool]] = None


# 状态特征映射表
# 该字典存储了每个游戏状态对应的检测特征签名
# 键是GameState枚举值，值是StateSignature对象
STATE_SIGNATURES = {
    # ========== 启动流程组 ==========
    # 启动器状态特征：检测到wzry_icon图标，排除大厅相关模板避免误判
    GameState.LAUNCHER: StateSignature(
        primary_templates=["wzry_icon"],  # 主要检测王者荣耀游戏图标
        exclude_templates=[
            "game_lobby",
            "start_game",
            "battle",
            "ranking",
        ],  # 排除大厅相关模板
        required_confidence=0.85,  # 提高置信度阈值到0.85，避免误检测
        group="startup",  # 属于启动流程组
        description="MuMu桌面 - 启动游戏入口",
    ),
    # 更新日志弹窗特征：检测到关闭按钮，排除大厅
    GameState.UPDATE_LOG: StateSignature(
        primary_templates=["close1", "close2", "close3", "close4"],  # 检测各种关闭按钮
        exclude_templates=["game_lobby"],  # 排除大厅避免误判
        required_confidence=0.8,
        group="startup",
        description="弹窗",
    ),
    # 选区界面特征：检测到开始游戏按钮，排除大厅
    GameState.SELECT_ZONE: StateSignature(
        primary_templates=["start_game"],  # 检测开始游戏按钮
        exclude_templates=["game_lobby"],  # 排除大厅
        group="startup",
        description="选区界面 - 点击进入游戏",
    ),
    # 游戏大厅特征：检测到大厅界面，排除峡谷匹配等子界面
    GameState.HALL: StateSignature(
        primary_templates=["game_lobby"],  # 检测游戏大厅主界面
        exclude_templates=[
            "canyon_match",
            "ranking",
            "select_hero",
            "match_confirm",
        ],  # 添加 match_confirm
        group="startup",
        description="游戏大厅 - 主界面（对战/排位入口）",
    ),
    # ========== 防沉迷流程 ==========
    # 防沉迷弹窗特征：检测到休息提示
    GameState.REST_POPUP: StateSignature(
        primary_templates=["rest"],  # 检测休息提示模板
        exclude_templates=[],  # 无排除模板
        required_confidence=get_confidence("rest"),  # 从配置读取置信度
        group="anti_addiction",
        description="防沉迷弹窗 - 需要点击确认",
    ),
    # 防沉迷冷却状态特征：无主要模板，通过逻辑判断
    GameState.HEALTH_COOLDOWN: StateSignature(
        primary_templates=[],  # 无主要检测模板
        exclude_templates=[],  # 无排除模板
        group="anti_addiction",
        description="防沉迷冷却中 - 等待15分钟",
    ),
    # ========== 对战模式流程 ==========
    # 对战模式选择界面特征
    GameState.BATTLE_MODE_SELECT: StateSignature(
        primary_templates=["battle_mode"],  # battle_mode.png - 对战模式选择界面
        exclude_templates=["canyon_match", "ai_mode"],  # 排除子界面
        required_confidence=get_confidence("battle_mode"),  # 从配置读取
        group="battle_flow",
        description="对战模式选择",
    ),
    # 5V5子菜单特征（王者峡谷界面：显示人机和匹配按钮）
    GameState.BATTLE_5V5_SUB: StateSignature(
        primary_templates=["wangzhe_canyon"],  # 王者峡谷标题（此界面的唯一标识）
        exclude_templates=[
            "ai_standard",
            "ai_quick",
            "start_match",
        ],  # 排除下一级界面的模板
        group="battle_flow",
        description="5V5王者峡谷",
    ),
    # 对战类型选择特征
    GameState.BATTLE_5V5_TYPE: StateSignature(
        primary_templates=["canyon_match", "ai_mode"],  # 检测峡谷匹配或人机模式按钮
        exclude_templates=["ai_standard", "ai_quick", "start_match"],  # 排除已选状态
        group="battle_flow",
        description="对战类型 - 匹配对战/人机对战",
    ),
    # 人机模式设置界面特征（模式+难度+开始练习 在同一个界面上）
    # 深度检测用ai_mode_choose标题作为唯一标识，排除其他界面的模板
    GameState.BATTLE_AI_MODE: StateSignature(
        primary_templates=[
            "ai_mode_choose"
        ],  # 人机模式设置界面的标题（此界面唯一标识）
        exclude_templates=[
            "wangzhe_canyon",
            "battle_mode",
            "start_match",
        ],  # 排除其他界面
        group="battle_flow",
        description="人机模式设置界面",
    ),
    # 注意：BATTLE_AI_DIFFICULTY 和 BATTLE_START_PRACTICE 与 BATTLE_AI_MODE 是同一界面
    # 深度检测不应检测这两个状态（它们的模板都在同一界面上，无法通过排除区分）
    # 统一由 BATTLE_AI_MODE 处理器负责检查模式、难度并点击开始练习
    GameState.BATTLE_AI_DIFFICULTY: StateSignature(
        primary_templates=["ai_mode_choose"],  # 同样使用标题识别
        exclude_templates=["wangzhe_canyon", "battle_mode", "start_match"],
        group="battle_flow",
        description="人机难度选择（同BATTLE_AI_MODE界面）",
    ),
    GameState.BATTLE_START_PRACTICE: StateSignature(
        primary_templates=["ai_mode_choose"],  # 同样使用标题识别
        exclude_templates=["wangzhe_canyon", "battle_mode", "start_match"],
        required_confidence=get_confidence("start_practice"),
        group="battle_flow",
        description="等待开始练习（同BATTLE_AI_MODE界面）",
    ),
    # 对战房间特征
    GameState.BATTLE_ROOM: StateSignature(
        primary_templates=["start_match"],  # 检测开始匹配按钮
        exclude_templates=["match_confirm"],  # 排除匹配确认弹窗
        group="battle_flow",
        description="对战房间 - 等待开始匹配",
    ),
    # ========== 排位模式流程 ==========
    # 排位赛模式选择界面特征
    GameState.RANKING_MATCH_SELECT: StateSignature(
        primary_templates=["ranking_match"],  # 检测排位赛匹配按钮
        exclude_templates=["5v5_canyon"],  # 排除峡谷相关
        required_confidence=get_confidence("ranking_match"),  # 从配置读取
        group="ranking_flow",
        description="排位赛模式选择界面 - 大厅点击排位按钮后进入",
    ),
    # 排位赛选英雄界面特征
    GameState.RANKING_HERO_SELECT: StateSignature(
        primary_templates=["ranking_hero_select"],  # 检测排位选英雄界面
        exclude_templates=["game_loading_vs"],  # 排除加载画面
        required_confidence=get_confidence("ranking_hero_select"),  # 从配置读取
        group="ranking_flow",
        description="排位赛普通选英雄界面 - 选择英雄并锁定",
    ),
    # 排位禁选界面特征（预留）
    GameState.RANKING_BAN_PICK: StateSignature(
        primary_templates=["ban_pick"],  # 检测禁选界面
        exclude_templates=[],  # 无排除模板
        group="ranking_flow",
        description="排位禁选界面（征召模式，预留）",
    ),
    # ========== 匹配流程组 ==========
    # 匹配中状态特征：无主要模板，通过状态转换逻辑确定
    GameState.MATCHING: StateSignature(
        primary_templates=[],  # 匹配中无主要检测模板
        exclude_templates=["select_hero", "match_confirm"],  # 排除其他状态
        required_confidence=0.0,  # 置信度为0，由转换逻辑确定
        group="matching",
        description="匹配中 - 过渡状态（由状态转换逻辑确定，非模板匹配）",
    ),
    # 匹配成功弹窗特征
    GameState.MATCH_FOUND: StateSignature(
        primary_templates=["match_confirm"],  # 检测匹配确认按钮
        exclude_templates=["game_lobby"],  # 添加 game_lobby，防止在大厅误判
        group="matching",
        description="匹配成功弹窗",
    ),
    # 已确认匹配特征
    GameState.MATCH_CONFIRMED: StateSignature(
        primary_templates=["confirmed"],  # 检测已确认按钮（灰色）
        exclude_templates=[],  # 无排除模板
        group="matching",
        description="已确认匹配",
    ),
    # ========== 游戏核心流程 ==========
    # 人机模式选英雄界面特征
    GameState.HERO_SELECT: StateSignature(
        primary_templates=["select_hero", "hero_selection"],  # 检测选英雄界面
        exclude_templates=[
            "game_lobby",  # 排除大厅
            "victory",
            "defeat",
            "continue",  # 排除结算
            "match_statistics",
            "return_room",
            "Hero_Confirm",  # 排除赛后
            "close1",
            "close2",
            "close3",
            "close4",
        ],  # 排除弹窗
        required_confidence=get_confidence("select_hero"),  # 从配置读取
        group="game_core",
        description="人机模式选英雄界面",
    ),
    # 分路选择特征
    GameState.LANE_SELECT: StateSignature(
        primary_templates=[
            "lane_top",
            "lane_jungle",
            "lane_mid",  # 检测各分路按钮
            "lane_adc",
            "lane_support",
            "all_lane",
        ],
        exclude_templates=[],  # 无排除模板
        group="game_core",
        description="分路选择",
    ),
    # VS加载画面特征
    GameState.GAME_LOADING_VS: StateSignature(
        primary_templates=["VS"],  # 检测VS标志
        exclude_templates=[],  # 无排除模板
        required_confidence=0.7,
        group="game_core",
        description="VS加载画面",
    ),
    # 战斗中状态特征：无主要模板，由模态检测确认
    GameState.IN_GAME: StateSignature(
        primary_templates=[],  # 战斗中不进行模板匹配，由模态检测确认
        exclude_templates=[
            "close1",
            "close2",
            "close3",
            "close4",
            "game_lobby",
            "select_hero",
            "wzry_icon",
            "victory",
            "victory1",
            "defeat",
        ],  # 排除其他所有状态
        required_confidence=0.0,
        group="game_core",
        description="战斗中（由模态检测确认，非模板匹配）",
    ),
    # ========== 结算流程组 ==========
    # 结算界面特征
    GameState.GAME_END: StateSignature(
        primary_templates=["victory", "victory1", "defeat"],  # 检测胜利或失败标志
        exclude_templates=["wzry_icon", "game_lobby", "battle"],  # 排除游戏外状态
        required_confidence=0.75,
        group="settlement",
        description="结算界面",
    ),
    # MVP展示特征
    GameState.MVP_DISPLAY: StateSignature(
        primary_templates=["continue"],  # 检测继续按钮
        exclude_templates=["match_statistics", "return_room"],  # 排除赛后数据
        required_confidence=0.7,
        group="settlement",
        description="MVP展示",
    ),
    # 赛后数据特征
    GameState.POST_MATCH_STATS: StateSignature(
        primary_templates=["match_statistics", "stats"],  # 检测赛后统计界面
        exclude_templates=["continue", "return_room"],  # 排除MVP和返回
        required_confidence=0.7,
        group="settlement",
        description="赛后数据",
    ),
    # 返回房间特征
    GameState.RETURN_TO_ROOM: StateSignature(
        primary_templates=["return_room", "Match_Statistics"],  # 检测返回按钮
        exclude_templates=["continue"],  # 排除继续按钮
        required_confidence=0.7,
        group="settlement",
        description="返回",
    ),
    # ========== 特殊状态 ==========
    # 防沉迷冷却特征
    GameState.HEALTH_COOLDOWN: StateSignature(
        primary_templates=["health_cooldown"],  # 检测健康系统冷却提示
        exclude_templates=[],  # 无排除模板
        group="special",
        description="防沉迷",
    ),
}


# ========== 辅助函数 ==========
# 以下函数提供对状态信息的便捷查询功能


def get_state_flow(state: str) -> str:
    """
    获取状态所属流程组

    参数说明:
        state: 状态名称字符串

    返回值:
        str: 状态所属的流程组名称，如"startup"、"game_core"等
             如果状态不存在则返回"unknown"

    功能描述:
        根据状态名称查询其所属的流程组，用于状态分组管理和流程控制
    """
    try:
        # 将字符串转换为GameState枚举值
        state_enum = GameState(state)
        # 从特征映射表中获取该状态的特征签名
        signature = STATE_SIGNATURES.get(state_enum)
        # 如果找到签名，返回其流程组
        if signature:
            return signature.group
    except ValueError:
        # 状态字符串无效，忽略异常
        pass
    # 返回未知流程组
    return "unknown"


def is_startup_state(state: str) -> bool:
    """
    判断是否为启动流程状态

    参数说明:
        state: 状态名称字符串

    返回值:
        bool: 如果是启动流程状态返回True，否则返回False

    功能描述:
        检查指定状态是否属于启动流程组（startup），
        用于判断当前是否处于游戏启动阶段
    """
    # 调用get_state_flow获取流程组并判断是否等于"startup"
    return get_state_flow(state) == "startup"


def is_game_active(state: str) -> bool:
    """
    判断是否处于游戏活跃状态

    参数说明:
        state: 状态名称字符串

    返回值:
        bool: 如果处于游戏活跃状态返回True，否则返回False

    功能描述:
        检查指定状态是否属于游戏核心流程组（game_core）或匹配流程组（matching），
        用于判断当前是否处于选英雄或战斗等活跃游戏阶段
    """
    # 获取状态所属流程组
    flow = get_state_flow(state)
    # 判断是否为核心游戏流程或匹配流程
    return flow in ["game_core", "matching"]


def get_state_description(state: str) -> str:
    """
    获取状态描述文本

    参数说明:
        state: 状态名称字符串

    返回值:
        str: 状态的中文描述文本，如果状态不存在则返回"未知状态"

    功能描述:
        根据状态名称查询其描述文本，用于日志输出和界面显示
    """
    try:
        # 将字符串转换为GameState枚举值
        state_enum = GameState(state)
        # 从特征映射表中获取该状态的特征签名
        signature = STATE_SIGNATURES.get(state_enum)
        # 如果找到签名，返回其描述文本
        if signature:
            return signature.description
    except ValueError:
        # 状态字符串无效，忽略异常
        pass
    # 返回默认未知状态描述
    return "未知状态"


def get_state_confidence_threshold(state: str) -> float:
    """
    获取状态的置信度阈值

    参数说明:
        state: 状态名称字符串

    返回值:
        float: 该状态识别所需的最小置信度阈值，默认返回0.7

    功能描述:
        根据状态名称查询其识别所需的置信度阈值，
        用于判断模板匹配结果是否足够可靠
    """
    try:
        # 将字符串转换为GameState枚举值
        state_enum = GameState(state)
        # 从特征映射表中获取该状态的特征签名
        signature = STATE_SIGNATURES.get(state_enum)
        # 如果找到签名，返回其置信度阈值
        if signature:
            return signature.required_confidence
    except ValueError:
        # 状态字符串无效，忽略异常
        pass
    # 返回默认置信度阈值0.7
    return 0.7
