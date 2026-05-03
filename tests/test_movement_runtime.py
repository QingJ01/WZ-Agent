"""Runtime movement control tests."""

from __future__ import annotations

import threading

from wzry_ai.movement.movement_logic_yao import (
    auto_resume_if_game_detected,
    build_minimap_only_health_info,
)


def test_auto_resume_clears_pause_when_model2_self_position_detected():
    pause_event = threading.Event()
    pause_event.set()

    resumed = auto_resume_if_game_detected(
        pause_event,
        model1_result=None,
        model2_result={"self_pos": (1200, 700)},
    )

    assert resumed is True
    assert pause_event.is_set() is False


def test_auto_resume_keeps_pause_without_game_detection():
    pause_event = threading.Event()
    pause_event.set()

    resumed = auto_resume_if_game_detected(
        pause_event,
        model1_result=None,
        model2_result={"self_pos": None},
    )

    assert resumed is False
    assert pause_event.is_set() is True


def test_build_minimap_only_health_info_keeps_skill_thread_active():
    health_info = build_minimap_only_health_info(
        {
            "g_center": (120, 240),
            "b_centers": [(130, 250)],
            "r_centers": [(180, 280)],
        }
    )

    assert health_info["self_pos"] is None
    assert health_info["game_detected"] is True
    assert health_info["skill_policy"] == "aggressive"
    assert health_info["minimap_data"]["g_center"] == (120, 240)
