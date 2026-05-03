"""移动控制模块 - 统一移动、跟随逻辑"""

from wzry_ai.movement.unified_movement import (
    UnifiedMovement,
    StuckDetector,
    get_movement_controller,
    MIN_FOLLOW_DISTANCE,
)

from wzry_ai.movement.movement_logic_yao import (
    run_fusion_logic_v2,
    move_direction,
    latest_model1_data,
    _locked_target_for_model1,
)

from wzry_ai.movement.base_follow_logic import (
    BaseSupportHero,
    YaoFollowLogic,
    CaiwenjiFollowLogic,
    MingshiyinFollowLogic,
    create_support_hero,
    SUPPORTED_SUPPORT_HEROES,
)

__all__ = [
    # unified_movement
    'UnifiedMovement',
    'StuckDetector',
    'get_movement_controller',
    'MIN_FOLLOW_DISTANCE',
    # movement_logic_yao
    'run_fusion_logic_v2',
    'move_direction',
    'latest_model1_data',
    '_locked_target_for_model1',
    # base_follow_logic
    'BaseSupportHero',
    'YaoFollowLogic',
    'CaiwenjiFollowLogic',
    'MingshiyinFollowLogic',
    'create_support_hero',
    'SUPPORTED_SUPPORT_HEROES',
]
