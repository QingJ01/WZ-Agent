"""认知层 - 威胁评估与集火检测"""
import time
from enum import Enum
from typing import Optional
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.config import (
    THREAT_HIGH_THRESHOLD, THREAT_MEDIUM_THRESHOLD,
    FOCUS_FIRE_HP_DROP_RATE, FIGHT_ENEMY_DISTANCE
)

logger = get_logger(__name__)


class ThreatLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    
    def __ge__(self, other):
        return _THREAT_ORDER[self] >= _THREAT_ORDER[other]
    
    def __gt__(self, other):
        return _THREAT_ORDER[self] > _THREAT_ORDER[other]
    
    def __le__(self, other):
        return _THREAT_ORDER[self] <= _THREAT_ORDER[other]
    
    def __lt__(self, other):
        return _THREAT_ORDER[self] < _THREAT_ORDER[other]


# 威胁等级优先级映射（模块级变量，避免 Enum 元类将其误认为枚举成员）
_THREAT_ORDER = {
    ThreatLevel.SAFE: 0,
    ThreatLevel.LOW: 1,
    ThreatLevel.MEDIUM: 2,
    ThreatLevel.HIGH: 3,
}


class ThreatAnalyzer:
    """威胁评估引擎"""
    
    def __init__(self):
        self._last_log_time = 0
    
    def evaluate(self, world_state) -> ThreatLevel:
        """
        威胁等级评估
        算法：基于敌人数量 + 距离加权
        - 距离越近威胁越高（倒数衰减）
        - 正在接近的敌人额外加权 +0.3
        - 人数因子叠加
        - 归一化到 0-1 后映射到 ThreatLevel
        """
        if world_state is None or not world_state.enemies:
            return ThreatLevel.SAFE
        
        threat_score = 0.0
        for enemy in world_state.enemies:
            # 距离因子：距离越近越高，除以100归一化
            distance_factor = 1.0 / (enemy.distance_to_self / 100.0 + 1.0)
            # 接近加权
            approach_bonus = 0.3 if enemy.is_approaching else 0.0
            threat_score += (distance_factor + approach_bonus)
        
        # 人数因子：保底0.5，确保单个近距离敌人也有足够威胁权重
        count_factor = max(min(len(world_state.enemies) / 3.0, 1.5), 0.5)
        final_score = threat_score * count_factor
        
        # 归一化到 0-1（除数从3.0降到2.0，使分数更容易达到MEDIUM）
        normalized = min(final_score / 2.0, 1.0)
        
        # 映射到等级
        if normalized >= THREAT_HIGH_THRESHOLD:
            level = ThreatLevel.HIGH
        elif normalized >= THREAT_MEDIUM_THRESHOLD:
            level = ThreatLevel.MEDIUM
        elif normalized > 0.1:
            level = ThreatLevel.LOW
        else:
            level = ThreatLevel.SAFE
        
        # 节流日志（每2秒最多一次）
        now = time.time()
        if now - self._last_log_time > 2.0:
            if level >= ThreatLevel.MEDIUM:
                logger.info(f"[威胁评估] 等级={level.value}, 分数={normalized:.2f}, 敌人数={len(world_state.enemies)}")
            self._last_log_time = now
        
        return level
    
    def detect_focus_fire(self, world_state) -> Optional[object]:
        """
        集火检测 - 基于血量下降速率
        遍历 teammates，找血量下降速率超过阈值的队友
        返回血量下降最快的队友 EntityState，或 None
        """
        if world_state is None or not world_state.teammates:
            return None
        
        worst_target = None
        worst_delta = 0.0  # 保存最大掉血速度（绝对值）
        
        for teammate in world_state.teammates:
            # health_delta 为负值表示掉血
            if teammate.health_delta < -FOCUS_FIRE_HP_DROP_RATE:
                drop_rate = abs(teammate.health_delta)
                if drop_rate > worst_delta:
                    worst_delta = drop_rate
                    worst_target = teammate
        
        if worst_target:
            logger.info(f"[集火检测] 队友 {worst_target.entity_id} 正在被集火, 掉血速率={worst_delta:.1f}%/秒")
        
        return worst_target
    
    def detect_self_under_attack(self, world_state) -> bool:
        """自身被攻击检测：血量变化率 < -5%/秒"""
        if world_state is None or world_state.self_health_delta is None:
            return False
        return world_state.self_health_delta < -5.0
