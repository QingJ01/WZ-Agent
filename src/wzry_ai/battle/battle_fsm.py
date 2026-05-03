"""决策层 - 战斗状态机"""
from enum import Enum
import time
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.config import RETREAT_HP_THRESHOLD, FIGHT_ENEMY_DISTANCE

logger = get_logger(__name__)


class BattleState(Enum):
    FOLLOW = "follow"      # 跟随C位
    FIGHT = "fight"        # 附近有敌人，进入战斗
    RETREAT = "retreat"    # 血量低，撤退
    RECALL = "recall"      # 卡住保底/主动回城


class BattleFSM:
    """
    战斗状态机
    控制战斗行为：跟随/战斗/撤退/回城
    不控制数据源选择（模态1/模态2切换由移动层自行管理）
    """
    
    # 状态对应的移动策略
    MOVEMENT_STRATEGIES = {
        BattleState.FOLLOW: "follow_priority_target",
        BattleState.FIGHT: "follow_and_assist",
        BattleState.RETREAT: "retreat_from_enemies",
        BattleState.RECALL: "stop",
    }
    
    # 状态对应的技能策略
    SKILL_POLICIES = {
        BattleState.FOLLOW: "conservative",    # 仅探草/恢复
        BattleState.FIGHT: "aggressive",       # 全技能输出
        BattleState.RETREAT: "defensive",      # 治疗/保命优先
        BattleState.RECALL: "disabled",        # 禁止释放
    }
    
    # 撤退恢复血量阈值
    RETREAT_RECOVER_THRESHOLD = 60  # 血量恢复到60%以上才退出撤退
    
    def __init__(self):
        self.state = BattleState.FOLLOW
        self.state_enter_time = time.time()
        self.last_state = None
        self._last_log_time = 0
    
    def update(self, world_state, threat_level, stuck_detector=None) -> BattleState:
        """
        状态转移（每帧调用）
        
        参数：
            world_state: WorldState 实例
            threat_level: ThreatLevel 枚举值
            stuck_detector: StuckDetector 实例（用于检查回城状态）
        
        返回：
            当前 BattleState
        """
        from wzry_ai.battle.threat_analyzer import ThreatLevel  # 延迟导入避免循环
        
        prev_state = self.state
        now = time.time()
        
        # 最高优先级：回城状态
        if stuck_detector and stuck_detector.is_recalling:
            self.state = BattleState.RECALL
        elif self.state == BattleState.RECALL:
            # 回城完成或取消
            if stuck_detector is None or not stuck_detector.is_recalling:
                self.state = BattleState.FOLLOW
        
        # 非回城状态下的转移逻辑
        elif world_state is None:
            pass  # 无数据，保持当前状态
        
        elif self.state == BattleState.FOLLOW:
            # FOLLOW → RETREAT
            if (world_state.self_health is not None 
                    and world_state.self_health < RETREAT_HP_THRESHOLD 
                    and threat_level >= ThreatLevel.MEDIUM):
                self.state = BattleState.RETREAT
            # FOLLOW → FIGHT
            elif threat_level >= ThreatLevel.MEDIUM:
                # 检查是否有敌人在交战距离内
                has_close_enemy = any(
                    e.distance_to_self < FIGHT_ENEMY_DISTANCE 
                    for e in world_state.enemies
                )
                if has_close_enemy:
                    self.state = BattleState.FIGHT
        
        elif self.state == BattleState.FIGHT:
            # FIGHT → RETREAT
            if (world_state.self_health is not None 
                    and world_state.self_health < RETREAT_HP_THRESHOLD):
                self.state = BattleState.RETREAT
            # FIGHT → FOLLOW
            elif threat_level == ThreatLevel.SAFE:
                self.state = BattleState.FOLLOW
        
        elif self.state == BattleState.RETREAT:
            # RETREAT → FOLLOW（血量恢复或威胁解除）
            if (world_state.self_health is not None 
                    and world_state.self_health > self.RETREAT_RECOVER_THRESHOLD):
                self.state = BattleState.FOLLOW
            elif threat_level == ThreatLevel.SAFE:
                self.state = BattleState.FOLLOW
        
        # 状态变化日志
        if self.state != prev_state:
            self.last_state = prev_state
            self.state_enter_time = now
            logger.info(f"[战斗状态机] {prev_state.value} → {self.state.value}")
        
        return self.state
    
    def get_movement_strategy(self) -> str:
        """返回当前状态对应的移动策略名"""
        return self.MOVEMENT_STRATEGIES.get(self.state, "follow_priority_target")
    
    def get_skill_policy(self) -> str:
        """返回当前状态对应的技能策略名"""
        return self.SKILL_POLICIES.get(self.state, "aggressive")
    
    def get_state_duration(self) -> float:
        """获取当前状态持续时间（秒）"""
        return time.time() - self.state_enter_time
