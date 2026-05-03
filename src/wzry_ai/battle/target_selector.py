"""认知层 - 目标选择器（复用跟随优先级）"""
from typing import Optional, List
from math import sqrt
import time
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)

# 分路角色到优先级的默认映射（数值越小优先级越高）
DEFAULT_LANE_PRIORITY = {
    'adc': 1,       # 射手最高优先
    'mid': 2,       # 法师次之
    'top': 3,       # 对抗路
    'jungle': 4,    # 打野
    'support': 5,   # 辅助最低
    'unknown': 6,   # 未知
}


class TargetSelector:
    """目标选择器 - 跟随和附身目标选择"""
    
    SWITCH_COOLDOWN = 3.0  # 切换冷却时间（秒）
    SWITCH_SCORE_RATIO = 0.7  # 当前目标分数低于次高的此比例才切换
    
    def __init__(self, priority_heroes=None):
        """
        参数：
            priority_heroes: 优先跟随英雄列表（中文名），如 ['后羿', '鲁班七号']
                           从 SUPPORT_HERO_CONFIG['priority_heroes'] 获取
        """
        self.priority_heroes = priority_heroes or []
        self._last_switch_time = 0
        self._current_target_id = None
        self._last_log_time = 0
    
    def select_follow_target(self, world_state) -> Optional[object]:
        """
        选择跟随目标
        1. 优先选择 priority_heroes 中的英雄
        2. 优先选择分路角色优先级高的（adc > mid > top > jungle > support）
        3. 同优先级选最近的
        """
        if world_state is None or not world_state.teammates:
            return None
        
        best_target = None
        best_score = -1
        
        for teammate in world_state.teammates:
            score = self._calculate_follow_score(teammate)
            if score > best_score:
                best_score = score
                best_target = teammate
        
        return best_target
    
    def select_attach_target(self, world_state, threat_level=None) -> Optional[object]:
        """
        选择附身目标 = 跟随优先级 + 血量权重
        低血量的队友加权更高
        score = priority_bonus + (100 - health) * 0.3 - distance_penalty
        """
        if world_state is None or not world_state.teammates:
            return None
        
        best_target = None
        best_score = -999
        
        for teammate in world_state.teammates:
            score = self._calculate_attach_score(teammate)
            if score > best_score:
                best_score = score
                best_target = teammate
        
        return best_target
    
    def should_switch_attach(self, current_target, world_state) -> Optional[object]:
        """
        是否应该切换附身目标
        - 当前目标分数 < 次高分的 70% 时建议切换
        - 切换冷却 3 秒
        """
        if world_state is None or not world_state.teammates:
            return None
        
        now = time.time()
        if now - self._last_switch_time < self.SWITCH_COOLDOWN:
            return None  # 冷却中
        
        if current_target is None:
            return self.select_attach_target(world_state)
        
        current_score = self._calculate_attach_score(current_target)
        
        best_other = None
        best_other_score = -999
        
        for teammate in world_state.teammates:
            if teammate.entity_id == current_target.entity_id:
                continue
            score = self._calculate_attach_score(teammate)
            if score > best_other_score:
                best_other_score = score
                best_other = teammate
        
        # 当前分数 < 次高分的 70% 才切换
        if best_other and current_score < best_other_score * self.SWITCH_SCORE_RATIO:
            self._last_switch_time = now
            logger.info(f"[目标切换] {current_target.entity_id}({current_score:.1f}) -> {best_other.entity_id}({best_other_score:.1f})")
            return best_other
        
        return None
    
    def _calculate_follow_score(self, teammate) -> float:
        """计算跟随优先级分数"""
        score = 0.0
        
        # 优先英雄加分（在 priority_heroes 列表中的顺序越前分数越高）
        # entity_id 可能是中文名或拼音
        for i, hero_name in enumerate(self.priority_heroes):
            if hero_name in teammate.entity_id or teammate.entity_id in hero_name:
                score += (100 - i * 10)  # 列表越前分数越高
                break
        
        # 分路角色优先级
        lane_priority = DEFAULT_LANE_PRIORITY.get(teammate.lane_role, 6)
        score += (7 - lane_priority) * 10  # adc=60, mid=50, top=40...
        
        # 距离惩罚（距离越远分数越低）
        distance_penalty = min(teammate.distance_to_self / 100.0, 5.0)
        score -= distance_penalty
        
        return score
    
    def _calculate_attach_score(self, teammate) -> float:
        """计算附身优先级分数（跟随优先级 + 血量权重）"""
        # 基础分 = 跟随分数
        score = self._calculate_follow_score(teammate)
        
        # 血量缺失加权（血量越低分数越高）
        health_bonus = (100 - teammate.health) * 0.3
        score += health_bonus
        
        return score
