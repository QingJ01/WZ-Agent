"""Tests for decision recording used by future imitation training."""

from __future__ import annotations

import json
import logging


def test_decision_recorder_writes_jsonl_event(tmp_path):
    from wzry_ai.battle.decision_recorder import DecisionRecorder
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoAction,
        YaoDecisionState,
    )

    recorder = DecisionRecorder(base_dir=tmp_path, enabled=True)
    state = YaoDecisionState(
        yao_state="attached",
        skill_policy="aggressive",
        self_health=88,
        teammates=(TargetSummary(distance=120, health=76, in_r_range=True),),
        enemies=(TargetSummary(distance=240, health=61, in_q_range=True),),
        cooldowns=CooldownState(q_ready=True),
    )
    action = YaoAction(action="cast_q", reason="enemy_in_q_range", priority=40)

    recorder.record(
        state=state,
        actions=(action,),
        executed_action=action,
        source="unit_test",
    )

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    event = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert event["schema_version"] == 1
    assert event["source"] == "unit_test"
    assert event["state"]["yao_state"] == "attached"
    assert event["state"]["enemies"][0]["in_q_range"] is True
    assert event["actions"][0]["action"] == "cast_q"
    assert event["executed_action"]["action"] == "cast_q"


def test_decision_recorder_can_be_disabled(tmp_path):
    from wzry_ai.battle.decision_recorder import DecisionRecorder
    from wzry_ai.battle.yao_decision_brain import YaoDecisionState

    recorder = DecisionRecorder(base_dir=tmp_path, enabled=False)

    recorder.record(
        state=YaoDecisionState(),
        actions=(),
        executed_action=None,
        source="unit_test",
    )

    assert list(tmp_path.glob("*.jsonl")) == []


def test_decision_recorder_uses_environment_directory(monkeypatch, tmp_path):
    from wzry_ai.battle.decision_recorder import DecisionRecorder
    from wzry_ai.battle.yao_decision_brain import YaoAction, YaoDecisionState

    monkeypatch.setenv("WZRY_DECISION_RECORDING", "1")
    monkeypatch.setenv("WZRY_DECISION_RECORD_DIR", str(tmp_path / "records"))
    recorder = DecisionRecorder()

    recorder.record(
        state=YaoDecisionState(),
        actions=(),
        executed_action=YaoAction(action="cast_q", reason="unit", priority=1),
        source="unit_test",
    )

    assert len(list((tmp_path / "records").glob("*.jsonl"))) == 1


def test_decision_recorder_writes_policy_source_metadata(tmp_path):
    from wzry_ai.battle.decision_recorder import DecisionRecorder
    from wzry_ai.battle.yao_decision_brain import YaoAction, YaoDecisionState

    recorder = DecisionRecorder(base_dir=tmp_path, enabled=True)
    fallback = YaoAction(action="stay_attached", reason="rule_hold", priority=1)
    selected = YaoAction(
        action="cast_q",
        reason="human_policy_confidence_0.92",
        priority=999,
        target={"source": "human_policy", "confidence": 0.92},
    )

    recorder.record(
        state=YaoDecisionState(yao_state="attached"),
        actions=(fallback,),
        fallback_action=fallback,
        selected_action=selected,
        executed_action=selected,
        action_source="model",
        model_confidence=0.92,
        source="unit_test",
    )

    event = json.loads(next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8"))
    assert event["action_source"] == "model"
    assert event["fallback_action"]["action"] == "stay_attached"
    assert event["selected_action"]["action"] == "cast_q"
    assert event["model_confidence"] == 0.92


def test_decision_recorder_warns_when_recording_fails(tmp_path, caplog):
    from wzry_ai.battle.decision_recorder import DecisionRecorder
    from wzry_ai.battle.yao_decision_brain import YaoDecisionState

    recorder = DecisionRecorder(base_dir=tmp_path, enabled=True)

    caplog.set_level(logging.WARNING, logger="wzry_ai.battle.decision_recorder")
    recorder.record(
        state=YaoDecisionState(),
        actions=(),
        executed_action={"bad": object()},
        source="unit_test",
    )

    assert "decision record failed" in caplog.text
