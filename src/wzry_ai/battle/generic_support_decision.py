"""决策层 - 通用辅助英雄决策器（无附身/跳车机制）

适用于蔡文姬、明世隐等不具备附身技能的辅助英雄。
提供基础的技能优先级决策逻辑。
"""
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


class GenericSupportDecisionMaker:
    """
    通用辅助英雄决策模块
    
    与 YaoDecisionMaker 不同，此决策器不包含附身/跳车/护盾管理逻辑。
    移动逻辑通过 hasattr 检查判断是否调用 update_attach_state 等方法，
    因此本类不实现这些方法即可自动跳过附身相关逻辑。
    """
    
    def get_skill_priority(self, battle_state, world_state, threat_level) -> list:
        """
        返回当前情况下的技能优先级列表
        
        返回技能ID列表，按优先级从高到低排序
        """
        from wzry_ai.battle.battle_fsm import BattleState
        
        if world_state is None:
            return ["heal", "Q", "E", "R"]
        
        if battle_state == BattleState.FIGHT:
            return ["heal", "R", "Q", "E", "active_item"]
        
        elif battle_state == BattleState.RETREAT:
            return ["heal", "active_item"]
        
        elif battle_state == BattleState.FOLLOW:
            return ["Q", "recover"]
        
        elif battle_state == BattleState.RECALL:
            return []
        
        return ["heal", "Q", "E", "R"]
