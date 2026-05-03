"""
瑶移动逻辑模块 - 双模态融合跟随系统

功能：整合模态1（小地图）和模态2（血条）检测数据，实现智能跟随
核心特性：
  1. 双模态融合 - 自动切换模态1/模态2
  2. 附身状态保护 - 附身后不轻易切换模态
  3. 卡住检测与脱困 - 由 unified_movement.StuckDetector 统一处理
  4. 统一移动控制器集成
"""

# 导入time模块用于时间相关操作
import time

# 导入traceback用于详细错误追踪
import traceback

# 导入threading用于线程安全锁
import threading

# 从queue导入队列相关类
from queue import Queue, Empty

# 导入日志模块
import logging

# 从config模块导入统一配置参数
from wzry_ai.config import (
    FOLLOW_THRESHOLD,  # 跟随距离阈值
    SAFE_ENEMY_DISTANCE,  # 安全距离（离敌人的最小距离）
    AVOID_ENEMY_WEIGHT,  # 避敌权重系数
    SUPPORT_HERO_CONFIG,  # 辅助英雄配置
)
from wzry_ai.config.heroes.mapping import (
    convert_priority_heroes,
    get_hero_chinese,
)  # 导入英雄名称转换函数
from wzry_ai.utils.utils import safe_queue_put, find_closest_target  # 导入工具函数
from wzry_ai.utils.runtime_flags import is_ai_control_enabled

# 战斗AI四层架构
from wzry_ai.battle.world_state import WorldStateBuilder
from wzry_ai.battle.threat_analyzer import ThreatAnalyzer
from wzry_ai.battle.target_selector import TargetSelector
from wzry_ai.battle.battle_fsm import BattleFSM, BattleState
# YaoDecisionMaker 按需延迟导入（当 decision_maker 参数为 None 时）

# 从logging_utils导入彩色日志设置函数
from wzry_ai.utils.logging_utils import setup_colored_logger

# 注意：原 WallAvoidanceNavigator 类已合并到 unified_movement.py 的 StuckDetector 中
# 统一使用 movement.stuck_detector 进行卡地形检测和避障

# 配置日志记录器
logger = setup_colored_logger(__name__)

_log_throttle = {
    "last_stuck_update_log": 0.0,
    "last_skill_queue_log": 0.0,
}

# 导入检测模块
import wzry_ai.detection.model1_detector as model1_detector  # 模态1检测器
import wzry_ai.detection.model2_detector as model2_detector  # 模态2检测器
import wzry_ai.detection.model1_astar_follow as model1_astar_follow  # 模态1跟随逻辑
from wzry_ai.utils.keyboard_controller import press, release  # 键盘控制函数

# 从统一按键配置导入移动方向按键
from wzry_ai.config.keys import (
    KEY_MOVE_UP,
    KEY_MOVE_DOWN,
    KEY_MOVE_LEFT,
    KEY_MOVE_RIGHT,
)

# 导入统一移动控制器
from wzry_ai.movement.unified_movement import get_movement_controller

# 导入地图约束定位器
from wzry_ai.detection.map_constrained_localizer import MapConstrainedLocalizer


# 移动控制函数（简单的方向移动）
def move_direction(dx, dy):
    """使用键盘 WASD 移动"""
    # 根据方向计算按键
    keys = []
    if abs(dx) > abs(dy):
        # 主要X方向移动
        if dx > 0:
            keys.append(KEY_MOVE_RIGHT)  # 向右
        else:
            keys.append(KEY_MOVE_LEFT)  # 向左
    else:
        # 主要Y方向移动
        if dy > 0:
            keys.append(KEY_MOVE_DOWN)  # 向下
        else:
            keys.append(KEY_MOVE_UP)  # 向上

    # 执行按键（按下后立即释放）
    for key in keys:
        press(key)
        release(key)


# 注意：此函数已不再使用，Master_Auto.py 现在使用 run_fusion_logic_v2
# [已删除] 原 model1_thread_legacy 函数使用 WindowCapture，已废弃并移除

# 全局变量用于存储模态1的最新数据，供模态2使用
# 使用线程锁保护，防止多线程同时读写导致数据不一致
_model1_data_lock = threading.Lock()
latest_model1_data = {}

# 全局变量存储 run_fusion_logic_v2 锁定的目标，供 model1_thread_legacy 使用
_locked_target_lock = threading.Lock()
_locked_target_for_model1 = None  # 格式：(target_x, target_y, target_name, target_id)

# 注意：此函数已不再使用，Master_Auto.py 现在使用 run_fusion_logic_v2
# [已删除] 原 model2_thread_legacy 函数使用 WindowCapture，已废弃并移除

# find_closest_target 函数已移至 utils.py


def auto_resume_if_game_detected(pause_event, model1_result=None, model2_result=None):
    """检测链路已经看到对局目标时解除战斗暂停。"""
    game_detected = False
    if model2_result and model2_result.get("self_pos") is not None:
        game_detected = True
    if model1_result and model1_result.get("g_center") is not None:
        game_detected = True

    if game_detected and pause_event.is_set():
        pause_event.clear()
        return True
    return False


def build_minimap_only_health_info(model1_cache):
    """用小地图数据构建最小技能状态，避免技能线程依赖血条检测。"""
    minimap_data = dict(model1_cache) if model1_cache else {}
    return {
        "self_health": None,
        "self_pos": None,
        "team_health": [],
        "enemy_health": [],
        "is_attached": False,
        "is_moving": False,
        "game_detected": minimap_data.get("g_center") is not None,
        "minimap_data": minimap_data or None,
        "battle_state": "follow",
        "threat_level": "safe",
        "skill_policy": "aggressive",
        "focus_fire_target": None,
    }

# ================= 主逻辑入口 =================

# 注意：此函数已不再使用，Master_Auto.py 现在使用 run_fusion_logic_v2
# [已删除] 原 run_fusion_logic 函数依赖已废弃的线程函数，已移除
# 请使用 run_fusion_logic_v2

# ================= 新版本：接收外部检测数据 =================


# 主融合逻辑函数V2：接收外部检测数据，实现双模态融合跟随
def run_fusion_logic_v2(
    skill_queue,
    pause_event,
    status_queue=None,
    model1_data_queue=None,
    model2_data_queue=None,
    decision_maker=None,
):
    """
    双模态融合移动逻辑V2：接收 Master_Auto.py 传来的检测数据

    参数：
        skill_queue: 技能队列，用于向技能逻辑发送血量信息
        pause_event: 暂停事件，控制逻辑暂停/恢复
        status_queue: 状态队列（可选），用于发送状态信息
        model1_data_queue: 模态1数据队列，接收 model1_result
        model2_data_queue: 模态2数据队列，接收 model2_result
        decision_maker: 英雄决策器实例（可选），None 时回退到 YaoDecisionMaker
    """
    logger.info("=" * 50)
    logger.info("[Fusion V2] 融合逻辑启动 (接收外部数据)")
    logger.info("=" * 50)
    control_enabled = is_ai_control_enabled()
    if not control_enabled:
        logger.info("[Fusion V2] AI 自动操作已关闭，仅进行感知与记录")

    current_mode = 2  # 初始模式为模态2（血条跟随）
    last_check_time = time.time()  # 上次检查时间戳
    force_mode1_until = 0  # 强制使用模态1的截止时间
    last_health_info = None  # 上次发送的血量信息
    mode_switch_count = 0  # 模态切换计数

    # 附身状态保护
    last_attached_time = 0  # 上次附身时间戳
    ATTACHED_PROTECT_DURATION = 5.0  # 附身保护时长（秒）

    # 游戏状态检测
    game_active = False  # 游戏是否进行中
    last_game_active_time = time.time()  # 上次检测到游戏的时间
    no_detection_count = 0  # 连续未检测到游戏的计数

    # ===== 四层战斗架构初始化 =====
    world_builder = WorldStateBuilder()
    threat_analyzer = ThreatAnalyzer()
    target_selector = TargetSelector(SUPPORT_HERO_CONFIG.get("priority_heroes", []))
    battle_fsm = BattleFSM()
    # 使用传入的决策器，若未提供则回退到 YaoDecisionMaker（向后兼容）
    if decision_maker is None:
        from wzry_ai.battle.yao_decision import YaoDecisionMaker

        decision_maker = YaoDecisionMaker()
    last_cognition_time = 0  # 认知层上次更新时间
    COGNITION_INTERVAL = 0.05  # 认知层更新间隔（约20Hz）
    current_threat_level = None  # 当前威胁等级缓存
    current_focus_target = None  # 当前集火目标缓存
    current_battle_state = None  # 当前战斗状态缓存

    logger.info(f"[Fusion V2] 初始模式: 模态{current_mode}")

    while True:
        try:
            current_time = time.time()  # 获取当前时间戳

            # 从队列获取检测数据（非阻塞方式）
            model1_result = None
            model2_result = None
            enemies = []  # 初始化敌人列表，用于回城保底机制

            # 从模态1数据队列获取数据
            if model1_data_queue:
                try:
                    while not model1_data_queue.empty():
                        model1_result = model1_data_queue.get_nowait()
                except Empty:
                    pass

            # 从模态2数据队列获取数据
            if model2_data_queue:
                try:
                    while not model2_data_queue.empty():
                        model2_result = model2_data_queue.get_nowait()
                except Empty:
                    pass

            if auto_resume_if_game_detected(pause_event, model1_result, model2_result):
                logger.info("[Fusion V2] 检测到对局目标，自动解除暂停")

            # 检查暂停状态
            is_paused = pause_event.is_set()

            # 获取统一移动控制器实例
            movement = get_movement_controller()

            # 处理模态1数据 - 更新目标
            if model1_result:
                g_center = model1_result.get("g_center")  # 自身在小地图的位置
                b_centers = model1_result.get("b_centers", [])  # 友方英雄列表

                # 只要有自身位置就更新卡地形检测器（不管有没有队友）
                if g_center:
                    # 地图约束定位滤波
                    localizer = MapConstrainedLocalizer.get()
                    localizer.update_keys(movement.key_status)
                    fx, fy, conf = localizer.filter(g_center, current_time)
                    if fx is not None and conf > 0.3:
                        g_center = (fx, fy)

                    with _model1_data_lock:
                        latest_model1_data.clear()
                        latest_model1_data.update(
                            {
                                "g_center": g_center,
                                "b_centers": b_centers,
                                "r_centers": model1_result.get(
                                    "r_centers", []
                                ),  # 敌方英雄列表
                            }
                        )
                    # 更新统一移动控制器（模态1优先级低）
                    # 注意：卡地形检测器在 update_from_model1 内部更新
                    if control_enabled and not is_paused:
                        movement.update_from_model1(
                            g_center, b_centers, model1_astar_follow.class_names
                        )
                        # 调试日志：确认卡地形检测器已更新
                        if current_time - _log_throttle["last_stuck_update_log"] > 3.0:
                            stuck_status = movement.stuck_detector.get_status()
                            logger.debug(
                                f"[卡地形调试] 历史大小:{stuck_status['history_size']}, 确认计数:{stuck_status['stuck_confirm_count']}, 绕路中:{stuck_status['is_avoiding']}"
                            )
                            _log_throttle["last_stuck_update_log"] = current_time

            # 处理模态2数据 - 更新目标并打包血量信息
            if model2_result:
                self_pos = model2_result.get("self_pos")  # 自身位置
                self_health = model2_result.get("self_health")  # 自身血量
                team_targets = model2_result.get("team_targets", [])  # 队友列表
                enemies = model2_result.get("enemies", [])  # 敌人列表
                is_attached = (
                    self_health is None and self_pos is not None
                )  # 判断是否附身

                # 更新统一移动控制器（模态2优先级高）
                if control_enabled and not is_paused and self_pos:
                    if team_targets:
                        movement.update_from_model2(
                            self_pos, team_targets, model1_astar_follow.class_names
                        )
                    else:
                        # 没有队友血条时，不更新mode2目标，让模态切换逻辑处理
                        # 不要clear()，让mode1有机会接管
                        pass  # 静默处理，避免日志刷屏

                # 判断是否在移动
                is_moving = bool(team_targets) and self_pos is not None

                # 读取最近的模态1缓存数据（供技能逻辑使用小地图坐标）
                with _model1_data_lock:
                    _m1_cache = dict(latest_model1_data) if latest_model1_data else None

                # 打包血量信息字典
                health_info = {
                    "self_health": self_health,  # 自身血量百分比
                    "self_pos": self_pos,  # 自身坐标，用于技能距离计算
                    "team_health": [
                        {"pos": t[:2], "health": t[2]} for t in team_targets
                    ],  # 队友血量列表
                    "enemy_health": [
                        {"pos": e[:2], "health": e[2]} for e in enemies
                    ],  # 敌人血量列表
                    "is_attached": is_attached,  # 是否附身
                    "is_moving": is_moving,  # 移动状态，用于控制普攻
                    "game_detected": self_pos is not None,  # 是否检测到游戏
                    "minimap_data": _m1_cache,  # 小地图坐标数据（g_center, b_centers, r_centers）
                }

                # ===== 四层战斗架构：感知→认知→决策 =====
                # 构建 WorldState（感知层，每帧更新）
                world_state = world_builder.build(
                    model1_result, model2_result, current_time
                )

                # 认知层评估（降频到约20Hz）
                if current_time - last_cognition_time >= COGNITION_INTERVAL:
                    last_cognition_time = current_time
                    current_threat_level = threat_analyzer.evaluate(world_state)
                    current_focus_target = threat_analyzer.detect_focus_fire(
                        world_state
                    )

                # 决策层：状态机更新
                if current_threat_level is not None:
                    current_battle_state = battle_fsm.update(
                        world_state, current_threat_level, movement.stuck_detector
                    )
                    # 英雄特化决策：更新附身状态（仅附身类英雄如瑶有此方法）
                    if hasattr(decision_maker, "update_attach_state"):
                        decision_maker.update_attach_state(is_attached)

                # 将战斗架构信息附加到 health_info（供技能逻辑使用）
                health_info["battle_state"] = (
                    current_battle_state.value if current_battle_state else "follow"
                )
                health_info["threat_level"] = (
                    current_threat_level.value if current_threat_level else "safe"
                )
                health_info["skill_policy"] = (
                    battle_fsm.get_skill_policy()
                    if current_battle_state
                    else "aggressive"
                )
                health_info["focus_fire_target"] = current_focus_target

                # 发送到技能队列（回城期间不发送技能指令）
                if skill_queue and not movement.stuck_detector.is_recalling:
                    try:
                        while not skill_queue.empty():
                            skill_queue.get_nowait()  # 清空旧数据
                        skill_queue.put(health_info)  # 放入新数据
                        # 调试日志：每2秒输出一次发送状态
                        if current_time - _log_throttle["last_skill_queue_log"] > 2:
                            logger.debug(
                                f"[Fusion V2] 发送技能队列: 自身血量={self_health}, 队友数={len(team_targets)}, 敌人数={len(enemies)}"
                            )
                            _log_throttle["last_skill_queue_log"] = current_time
                    except Empty:
                        pass

                # 发送到状态队列
                if status_queue:
                    try:
                        while not status_queue.empty():
                            status_queue.get_nowait()  # 清空旧数据
                        status_queue.put(health_info)  # 放入新数据
                    except Empty:
                        pass

                # 先执行模态切换逻辑（确保移动使用正确的模式）
                # 检查是否有队友血条
                has_team_targets = False
                if model2_result and model2_result.get("team_targets"):
                    has_team_targets = len(model2_result["team_targets"]) > 0

                # 检查是否附身
                is_currently_attached = False
                if (
                    model2_result
                    and model2_result.get("self_health") is None
                    and model2_result.get("self_pos")
                ):
                    is_currently_attached = True

                if is_currently_attached:
                    last_attached_time = current_time  # 更新附身时间

                in_attach_protection = (
                    current_time - last_attached_time < ATTACHED_PROTECT_DURATION
                )

                # 模态切换逻辑
                if has_team_targets and current_mode != 2:
                    # 有队友血条，切换到模态2
                    if current_time - last_check_time >= 1.0:
                        last_check_time = current_time
                        logger.info(f"[Fusion V2] 切换到模态2 (检测到队友血条)")
                    current_mode = 2
                elif (
                    not has_team_targets
                    and current_mode == 2
                    and not in_attach_protection
                ):
                    # 无队友血条且不在附身保护期，切换到模态1
                    if current_time - last_check_time >= 1.0:
                        last_check_time = current_time
                        logger.info(f"[Fusion V2] 切换到模态1 (无队友血条)")
                    current_mode = 1

                # 执行统一移动（使用更新后的 current_mode）
                if not control_enabled:
                    movement.clear()
                elif not is_paused:
                    # 获取小地图自身位置（用于卡地形检测）
                    g_center_for_stuck = None
                    if model1_result:
                        g_center_for_stuck = model1_result.get("g_center")

                    # 更新卡地形检测器（只在无队友且未附身时更新）
                    # 有队友时不需要卡地形检测，瑶会跟随队友移动
                    if (
                        g_center_for_stuck
                        and not has_team_targets
                        and not is_currently_attached
                    ):
                        movement.stuck_detector.update(g_center_for_stuck)
                    else:
                        # 有队友或附身时重置卡地形检测器
                        movement.stuck_detector.reset()

                    if current_mode == 2 and self_pos and team_targets:
                        # Mode2：有队友时才执行移动
                        movement.execute_move(
                            self_pos,
                            enemies=enemies,
                            battle_state=current_battle_state.value
                            if current_battle_state
                            else None,
                        )
                    elif current_mode == 1 and model1_result:
                        # Mode1：使用小地图坐标
                        g_center = model1_result.get("g_center")
                        b_centers = model1_result.get("b_centers", [])
                        if g_center and b_centers:
                            movement.update_from_model1(
                                g_center, b_centers, model1_astar_follow.class_names
                            )
                            movement.execute_move(
                                g_center,
                                enemies=enemies,
                                battle_state=current_battle_state.value
                                if current_battle_state
                                else None,
                            )
                        elif g_center:
                            # 有自身位置但没有队友，朝右下方向移动（用于卡地形检测）
                            # 目标点 (330, 210) 在小地图右下方，产生向右下的移动向量
                            target_point = (330, 210)
                            movement.execute_move(
                                g_center,
                                target_pos=target_point,
                                enemies=enemies,
                                battle_state=current_battle_state.value
                                if current_battle_state
                                else None,
                            )
                        else:
                            movement.clear()  # 没有自身位置，停止移动
                    elif current_mode == 2 and self_pos and not team_targets:
                        # Mode2 但无队友，获取小地图位置并朝右下移动

                        if g_center_for_stuck:
                            # 朝右下方向移动
                            target_point = (330, 210)
                            movement.execute_move(
                                g_center_for_stuck,
                                target_pos=target_point,
                                enemies=enemies,
                                battle_state=current_battle_state.value
                                if current_battle_state
                                else None,
                            )
                        else:
                            movement.clear()  # 停止移动
                else:
                    # 暂停时释放按键
                    movement.clear()

            elif model1_result:
                with _model1_data_lock:
                    _m1_cache = dict(latest_model1_data) if latest_model1_data else None

                health_info = build_minimap_only_health_info(_m1_cache)
                if health_info["game_detected"]:
                    if skill_queue and not movement.stuck_detector.is_recalling:
                        try:
                            while not skill_queue.empty():
                                skill_queue.get_nowait()
                            skill_queue.put(health_info)
                            if (
                                current_time
                                - _log_throttle["last_skill_queue_log"]
                                > 2
                            ):
                                logger.debug(
                                    "[Fusion V2] 发送技能队列: 小地图补充数据"
                                )
                                _log_throttle["last_skill_queue_log"] = current_time
                        except Empty:
                            pass

                    if status_queue:
                        try:
                            while not status_queue.empty():
                                status_queue.get_nowait()
                            status_queue.put(health_info)
                        except Empty:
                            pass

            time.sleep(0.03)  # 休眠30ms，匹配数据更新频率(~30Hz)

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"[Fusion V2] 错误: {e}\n{traceback.format_exc()}")
            time.sleep(0.1)  # 出错时延长休眠时间


# 程序入口点
if __name__ == "__main__":
    logger.info("请运行 Master_Auto.py")  # 提示用户运行主程序
