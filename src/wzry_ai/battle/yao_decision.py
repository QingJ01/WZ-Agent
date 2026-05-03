"""决策层 - 瑶特化决策（附身/跳车/护盾管理）"""
import time
from typing import Optional
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


class YaoDecisionMaker:
    """
    瑶专属决策模块
    处理附身时机、主动跳车、护盾管理等瑶特有的决策逻辑
    """
    
    # 附身触发血量阈值
    ATTACH_HP_THRESHOLD = 40        # 队友血量低于此值触发附身
    # 附身切换冷却
    ATTACH_SWITCH_COOLDOWN = 3.0    # 秒
    # 护盾持续时间
    SHIELD_DURATION = 5.0           # 秒
    # 护盾跳车线（剩余比例）
    SHIELD_DETACH_RATIO = 0.1       # 10%
    # 跳车后目标血量安全线
    DETACH_SAFE_HP = 60             # 附身对象血量高于此值才主动跳车
    
    def __init__(self):
        self.last_attach_time = 0           # 上次附身时间
        self.last_detach_time = 0           # 上次跳车时间
        self.shield_start_time = None       # 护盾开始时间（附身时刻）
        self.current_attach_target_id = None  # 当前附身目标ID
        self._last_log_time = 0
    
    def update_attach_state(self, is_attached: bool):
        """更新附身状态（由外部调用，当检测到状态变化时）"""
        now = time.time()
        if is_attached and self.shield_start_time is None:
            # 刚附身
            self.shield_start_time = now
            self.last_attach_time = now
        elif not is_attached and self.shield_start_time is not None:
            # 刚脱离
            self.shield_start_time = None
            self.last_detach_time = now
    
    def should_attach(self, world_state, threat_level, target_selector) -> Optional[object]:
        """
        判断是否应该附身
        
        条件：
        1. 当前是人形态（非附身）
        2. 有队友血量 < ATTACH_HP_THRESHOLD 或 threat_level >= MEDIUM
        3. 附身冷却已过
        4. 通过 target_selector 选择最优目标
        
        返回：
            EntityState（建议附身目标）或 None（不需要附身）
        """
        from wzry_ai.battle.threat_analyzer import ThreatLevel  # 延迟导入
        
        if world_state is None:
            return None
        
        # 已经附身，不重复触发
        if world_state.is_attached:
            return None
        
        # 冷却检查
        now = time.time()
        if now - self.last_detach_time < self.ATTACH_SWITCH_COOLDOWN:
            return None
        
        # 条件判断
        should_try = False
        
        # 条件1：有队友低血量
        for teammate in world_state.teammates:
            if teammate.health < self.ATTACH_HP_THRESHOLD:
                should_try = True
                break
        
        # 条件2：威胁等级达到中等
        if not should_try and threat_level >= ThreatLevel.MEDIUM:
            should_try = True
        
        if not should_try:
            return None
        
        # 选择目标
        target = target_selector.select_attach_target(world_state, threat_level)
        
        if target:
            now = time.time()
            if now - self._last_log_time > 2.0:
                logger.info(f"[瑶决策] 建议附身 {target.entity_id}, 血量={target.health}%")
                self._last_log_time = now
        
        return target
    
    def should_detach(self, world_state) -> bool:
        """
        判断是否应该主动跳车（刷盾CD）
        
        条件：
        1. 当前附身中
        2. 护盾估计剩余 < SHIELD_DETACH_RATIO (10%)
        3. 附身对象血量 > DETACH_SAFE_HP (60%)
        """
        if world_state is None or not world_state.is_attached:
            return False
        
        if self.shield_start_time is None:
            return False
        
        now = time.time()
        elapsed = now - self.shield_start_time
        shield_remaining = max(0, 1.0 - elapsed / self.SHIELD_DURATION)
        
        # 护盾即将到期
        if shield_remaining > self.SHIELD_DETACH_RATIO:
            return False
        
        # 检查附身对象是否安全（取最近队友作为附身对象近似）
        if world_state.teammates:
            closest = min(world_state.teammates, key=lambda t: t.distance_to_self)
            if closest.health > self.DETACH_SAFE_HP:
                logger.info(f"[瑶决策] 护盾即将到期(剩余{shield_remaining:.0%})，附身对象安全(HP={closest.health}%)，建议跳车刷CD")
                return True
        
        return False
    
    def get_skill_priority(self, battle_state, world_state, threat_level) -> list:
        """
        返回当前情况下的技能优先级列表
        
        返回技能ID列表，按优先级从高到低排序
        """
        from wzry_ai.battle.battle_fsm import BattleState  # 延迟导入
        from wzry_ai.battle.threat_analyzer import ThreatLevel
        
        if world_state is None:
            return ["heal", "Q", "E"]
        
        is_attached = world_state.is_attached
        
        if battle_state == BattleState.FIGHT:
            if is_attached:
                return ["heal", "active_item", "Q", "E"]
            else:
                return ["R", "heal", "Q", "E"]
        
        elif battle_state == BattleState.RETREAT:
            if is_attached:
                return ["heal", "active_item"]
            else:
                return ["heal", "R"]  # R 用于附身逃生
        
        elif battle_state == BattleState.FOLLOW:
            return ["Q", "recover"]  # Q 用于探草
        
        elif battle_state == BattleState.RECALL:
            return []  # 回城中不释放技能
        
        return ["heal", "Q", "E"]
