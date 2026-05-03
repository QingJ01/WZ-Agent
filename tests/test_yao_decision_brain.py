"""Tests for Yao's first-stage rule decision brain."""

from __future__ import annotations


def _state(**overrides):
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionState,
    )

    values = {
        "yao_state": "normal",
        "battle_state": "follow",
        "skill_policy": "aggressive",
        "self_health": 90,
        "is_moving": False,
        "is_stable": True,
        "teammates": (),
        "enemies": (),
        "cooldowns": CooldownState(),
    }
    values.update(overrides)
    return YaoDecisionState(**values)


def test_attached_without_enemies_holds_attachment():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        yao_state="attached",
        enemies=(),
        teammates=(TargetSummary(health=95, in_r_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, r_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.selected_action is not None
    assert decision.selected_action.action == "stay_attached"
    assert [action.action for action in decision.actions] == ["stay_attached"]


def test_attached_with_enemy_uses_first_skill_before_second_skill():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        yao_state="attached",
        enemies=(TargetSummary(distance=240, health=80, in_q_range=True, in_e_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, r_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert [action.action for action in decision.actions[:3]] == [
        "cast_q",
        "cast_e",
        "stay_attached",
    ]
    assert decision.selected_action is not None
    assert decision.selected_action.action == "cast_q"


def test_normal_state_prefers_attach_when_teammate_is_in_range():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        teammates=(
            TargetSummary(distance=260, health=85, in_r_range=True),
            TargetSummary(distance=120, health=45, in_r_range=True),
        ),
        cooldowns=CooldownState(q_ready=True, e_ready=True, r_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.selected_action is not None
    assert decision.selected_action.action == "attach_teammate"
    assert decision.selected_action.target == {"index": 1, "source": "model2"}


def test_defensive_low_health_uses_summoner_before_attack():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        skill_policy="defensive",
        self_health=24,
        enemies=(TargetSummary(distance=180, in_q_range=True, in_e_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, f_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.selected_action is not None
    assert decision.selected_action.action == "cast_f"
    assert "cast_q" not in [action.action for action in decision.actions]
    assert "cast_e" not in [action.action for action in decision.actions]


def test_disabled_policy_returns_no_actions():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        skill_policy="disabled",
        enemies=(TargetSummary(distance=100, in_q_range=True, in_e_range=True),),
        teammates=(TargetSummary(distance=100, in_r_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, r_ready=True, f_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.actions == ()
    assert decision.selected_action is None


def test_recall_battle_state_returns_no_actions_even_if_policy_is_aggressive():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        battle_state="recall",
        skill_policy="aggressive",
        enemies=(TargetSummary(distance=100, in_q_range=True, in_e_range=True),),
        teammates=(TargetSummary(distance=100, in_r_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, r_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.actions == ()
    assert decision.selected_action is None


def test_retreat_battle_state_blocks_offense_even_if_policy_is_aggressive():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        battle_state="retreat",
        skill_policy="aggressive",
        self_health=24,
        enemies=(TargetSummary(distance=120, in_q_range=True, in_e_range=True),),
        cooldowns=CooldownState(q_ready=True, e_ready=True, f_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)
    actions = [action.action for action in decision.actions]

    assert decision.selected_action is not None
    assert decision.selected_action.action == "cast_f"
    assert "cast_q" not in actions
    assert "cast_e" not in actions


def test_active_item_protects_low_health_teammate_before_attach():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        TargetSummary,
        YaoDecisionBrain,
    )

    state = _state(
        teammates=(
            TargetSummary(
                distance=160,
                health=42,
                in_r_range=True,
                in_active_item_range=True,
            ),
        ),
        cooldowns=CooldownState(r_ready=True, active_item_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.selected_action is not None
    assert decision.selected_action.action == "cast_active_item"


def test_recover_when_low_health_and_no_enemy_nearby():
    from wzry_ai.battle.yao_decision_brain import (
        CooldownState,
        YaoDecisionBrain,
    )

    state = _state(
        self_health=55,
        enemies=(),
        teammates=(),
        cooldowns=CooldownState(recover_ready=True),
    )

    decision = YaoDecisionBrain().decide(state)

    assert decision.selected_action is not None
    assert decision.selected_action.action == "recover"
