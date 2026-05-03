"""检测系统模块 - 小地图检测、血条检测、模态融合。"""

from importlib import import_module
from typing import Any

model1_detect: Any
MinimapTracker: Any
model2_detect: Any
clear_entity_cache: Any
HealthBar: Any
fuse_modal_data: Any
match_entities_by_angle: Any
angle_difference: Any
model1_movement_logic: Any
a_star: Any
find_priority_target: Any
release_all_keys: Any

__all__ = [
    "model1_detect",
    "MinimapTracker",
    "model2_detect",
    "clear_entity_cache",
    "HealthBar",
    "fuse_modal_data",
    "match_entities_by_angle",
    "angle_difference",
    "model1_movement_logic",
    "a_star",
    "find_priority_target",
    "release_all_keys",
]

_EXPORTS = {
    "model1_detect": ("wzry_ai.detection.model1_detector", "detect"),
    "MinimapTracker": ("wzry_ai.detection.model1_detector", "MinimapTracker"),
    "model2_detect": ("wzry_ai.detection.model2_detector", "detect"),
    "clear_entity_cache": ("wzry_ai.detection.model2_detector", "clear_entity_cache"),
    "HealthBar": ("wzry_ai.detection.model2_detector", "HealthBar"),
    "fuse_modal_data": ("wzry_ai.detection.modal_fusion", "fuse_modal_data"),
    "match_entities_by_angle": (
        "wzry_ai.detection.modal_fusion",
        "match_entities_by_angle",
    ),
    "angle_difference": ("wzry_ai.detection.modal_fusion", "angle_difference"),
    "model1_movement_logic": (
        "wzry_ai.detection.model1_astar_follow",
        "model1_movement_logic",
    ),
    "a_star": ("wzry_ai.detection.model1_astar_follow", "a_star"),
    "find_priority_target": (
        "wzry_ai.detection.model1_astar_follow",
        "find_priority_target",
    ),
    "release_all_keys": ("wzry_ai.detection.model1_astar_follow", "release_all_keys"),
}


def __getattr__(name):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
