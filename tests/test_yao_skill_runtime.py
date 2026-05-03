"""Runtime tests for Yao skill logic."""

from __future__ import annotations

import time


def test_yao_maintenance_handles_minimap_only_health_info(monkeypatch):
    from wzry_ai.skills import hero_skill_logic_base
    from wzry_ai.skills import yao_skill_logic_v2

    taps = []
    monkeypatch.setattr(
        hero_skill_logic_base,
        "tap",
        lambda key, times=1, interval=None: taps.append(key),
    )
    monkeypatch.setattr(yao_skill_logic_v2, "get_frame", lambda timeout=0.02: None)

    skill_logic = yao_skill_logic_v2.YaoSkillLogic()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": None,
        "team_health": [],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
        "minimap_data": {
            "g_center": (120, 240),
            "b_centers": [],
            "r_centers": [],
        },
    }

    skill_logic.check_and_use_skills()

    assert taps[:4] == ["4", "3", "1", "2"]


def _prepare_skill_logic(monkeypatch):
    from wzry_ai.skills import hero_skill_logic_base
    from wzry_ai.skills import yao_skill_logic_v2

    taps = []
    monkeypatch.setattr(
        hero_skill_logic_base,
        "tap",
        lambda key, times=1, interval=None: taps.append(key),
    )
    monkeypatch.setattr(yao_skill_logic_v2, "get_frame", lambda timeout=0.02: None)

    skill_logic = yao_skill_logic_v2.YaoSkillLogic()
    now = time.time()
    skill_logic.last_buy_time = now
    skill_logic.last_levelup_time = now
    skill_logic.last_status_change_time = now - 2
    skill_logic._filter_self_health = lambda raw, current, raw_pos=None: raw
    skill_logic._filter_team_health = lambda raw, current: raw
    return skill_logic, taps


def test_yao_runtime_attached_without_enemy_holds_attachment(monkeypatch):
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [{"health": 95, "pos": (930, 410)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == []


def test_yao_runtime_attached_enemy_casts_only_first_skill(monkeypatch):
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [{"health": 80, "pos": (930, 405)}],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["q"]


def test_yao_runtime_normal_teammate_in_range_casts_ult(monkeypatch):
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    skill_logic.health_info = {
        "self_health": 88,
        "self_pos": (900, 400),
        "team_health": [{"health": 74, "pos": (930, 405)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["r"]


def test_yao_runtime_raw_self_health_prevents_first_frame_attached_misread(monkeypatch):
    from wzry_ai.skills import yao_skill_logic_v2

    skill_logic, _ = _prepare_skill_logic(monkeypatch)
    skill_logic._filter_self_health = lambda raw, current, raw_pos=None: None
    skill_logic.health_info = {
        "self_health": 100,
        "self_pos": (900, 400),
        "team_health": [{"health": 80, "pos": (930, 405)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    state = skill_logic._build_decision_state(time.time(), "aggressive")

    assert state.yao_state == yao_skill_logic_v2.YaoState.NORMAL.value


def test_yao_runtime_uses_active_item_for_low_health_teammate(monkeypatch):
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    skill_logic.health_info = {
        "self_health": 88,
        "self_pos": (900, 400),
        "team_health": [{"health": 42, "pos": (930, 405)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["t"]


def test_yao_runtime_recovers_when_low_and_safe(monkeypatch):
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    skill_logic.health_info = {
        "self_health": 55,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["c"]


def test_yao_runtime_records_latest_human_demo_action(monkeypatch):
    from wzry_ai.learning.human_demo import HumanAction

    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    recorded = []

    class FakeHumanDemoRuntime:
        def consume_latest_action(self, now=None, max_age=0.5):
            return HumanAction("cast_q", "windows_keyboard", time.time(), {})

        def record_state_action(self, state, human_action):
            recorded.append((state, human_action))

    skill_logic.human_demo_runtime = FakeHumanDemoRuntime()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [{"health": 95, "pos": (930, 410)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == []
    assert recorded
    assert recorded[0][0].yao_state == "attached"
    assert recorded[0][1].action == "cast_q"


def test_yao_runtime_uses_enabled_human_policy_prediction(monkeypatch):
    from wzry_ai.learning.human_policy import HumanPolicyPrediction

    skill_logic, taps = _prepare_skill_logic(monkeypatch)

    class FakeHumanPolicyRuntime:
        confidence_threshold = 0.7

        def predict(self, state):
            return HumanPolicyPrediction("cast_e", 0.95)

    skill_logic.human_policy_runtime = FakeHumanPolicyRuntime()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["e"]


def test_yao_runtime_ignores_low_confidence_human_policy_prediction(monkeypatch):
    from wzry_ai.learning.human_policy import HumanPolicyPrediction

    skill_logic, taps = _prepare_skill_logic(monkeypatch)

    class FakeHumanPolicyRuntime:
        confidence_threshold = 0.7

        def predict(self, state):
            return HumanPolicyPrediction("cast_e", 0.2)

    skill_logic.human_policy_runtime = FakeHumanPolicyRuntime()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == []


def test_yao_runtime_allows_policy_to_hold_attachment(monkeypatch):
    from wzry_ai.learning.human_policy import HumanPolicyPrediction

    skill_logic, taps = _prepare_skill_logic(monkeypatch)

    class FakeHumanPolicyRuntime:
        confidence_threshold = 0.7

        def predict(self, state):
            return HumanPolicyPrediction("stay_attached", 0.96)

    skill_logic.human_policy_runtime = FakeHumanPolicyRuntime()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [{"distance": 200, "health": 70, "in_q_range": True}],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == []


def test_yao_runtime_policy_cannot_suppress_protected_item_action(monkeypatch):
    from wzry_ai.learning.human_policy import HumanPolicyPrediction

    skill_logic, taps = _prepare_skill_logic(monkeypatch)

    class FakeHumanPolicyRuntime:
        confidence_threshold = 0.7

        def predict(self, state):
            return HumanPolicyPrediction("no_op", 0.99)

    skill_logic.human_policy_runtime = FakeHumanPolicyRuntime()
    skill_logic.health_info = {
        "self_health": 88,
        "self_pos": (900, 400),
        "team_health": [{"health": 42, "pos": (930, 405)}],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == ["t"]


def test_yao_runtime_records_model_action_source(monkeypatch):
    from wzry_ai.learning.human_policy import HumanPolicyPrediction

    skill_logic, _ = _prepare_skill_logic(monkeypatch)
    recorded = []

    class FakeHumanPolicyRuntime:
        confidence_threshold = 0.7

        def predict(self, state):
            return HumanPolicyPrediction("cast_e", 0.93)

    class FakeDecisionRecorder:
        def record(self, **kwargs):
            recorded.append(kwargs)

    skill_logic.human_policy_runtime = FakeHumanPolicyRuntime()
    skill_logic.decision_recorder = FakeDecisionRecorder()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert recorded[0]["action_source"] == "model"
    assert recorded[0]["model_confidence"] == 0.93
    assert recorded[0]["selected_action"].action == "cast_e"


def test_yao_runtime_control_disabled_records_human_demo_without_tapping(monkeypatch):
    from wzry_ai.learning.human_demo import HumanAction

    monkeypatch.setenv("WZRY_AI_CONTROL_ENABLED", "0")
    skill_logic, taps = _prepare_skill_logic(monkeypatch)
    demo_records = []
    decision_records = []

    class FakeHumanDemoRuntime:
        def consume_latest_action(self, now=None, max_age=0.5):
            return HumanAction("cast_q", "adb_touch", time.time(), {})

        def record_state_action(self, state, human_action):
            demo_records.append((state, human_action))

    class FakeDecisionRecorder:
        def record(self, **kwargs):
            decision_records.append(kwargs)

    skill_logic.human_demo_runtime = FakeHumanDemoRuntime()
    skill_logic.decision_recorder = FakeDecisionRecorder()
    skill_logic.health_info = {
        "self_health": None,
        "self_pos": (900, 400),
        "team_health": [],
        "enemy_health": [{"health": 80, "pos": (930, 405)}],
        "is_moving": False,
        "skill_policy": "aggressive",
    }

    skill_logic.check_and_use_skills()

    assert taps == []
    assert demo_records
    assert demo_records[0][1].action == "cast_q"
    assert decision_records[0]["action_source"] == "control_disabled"
    assert decision_records[0]["executed_action"] is None


def test_yao_runtime_check_and_use_skills_has_no_unreachable_legacy_body():
    import inspect

    from wzry_ai.skills.yao_skill_logic_v2 import YaoSkillLogic

    source = inspect.getsource(YaoSkillLogic.check_and_use_skills)

    assert "return self._check_and_use_skills_with_decision_brain()" in source
    assert "skill_policy =" not in source
