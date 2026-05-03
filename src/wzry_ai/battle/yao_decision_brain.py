"""Rule policy for Yao skill decisions.

This module is intentionally independent from raw screen coordinates and input
keys. It consumes normalized facts and returns ranked symbolic actions, which
can later be used as labels for imitation learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Any


@dataclass(frozen=True)
class TargetSummary:
    """Compact target facts needed by the Yao policy."""

    distance: float | None = None
    health: float | None = None
    in_q_range: bool = False
    in_e_range: bool = False
    in_r_range: bool = False
    in_f_range: bool = False
    in_active_item_range: bool = False
    in_attack_range: bool = False
    source: str = "model2"


@dataclass(frozen=True)
class CooldownState:
    """Ready flags for actions controlled by this policy."""

    q_ready: bool = False
    e_ready: bool = False
    r_ready: bool = False
    f_ready: bool = False
    active_item_ready: bool = False
    recover_ready: bool = False
    attack_ready: bool = False


@dataclass(frozen=True)
class YaoDecisionState:
    """Normalized state observed by Yao's decision policy."""

    yao_state: str = "unknown"
    battle_state: str = "follow"
    skill_policy: str = "aggressive"
    self_health: float | None = None
    is_moving: bool = False
    is_stable: bool = False
    teammates: tuple[TargetSummary, ...] = ()
    enemies: tuple[TargetSummary, ...] = ()
    cooldowns: CooldownState = field(default_factory=CooldownState)


@dataclass(frozen=True)
class YaoAction:
    """A symbolic action proposal."""

    action: str
    reason: str
    priority: int
    target: dict[str, Any] | None = None


@dataclass(frozen=True)
class YaoDecision:
    """Ranked decision result."""

    actions: tuple[YaoAction, ...]
    selected_action: YaoAction | None = None


class YaoDecisionBrain:
    """First-stage rule policy for Yao.

    The action ranking deliberately favors survivability and attachment
    stability over repeated damage button presses.
    """

    def decide(self, state: YaoDecisionState) -> YaoDecision:
        policy = self._effective_policy(state)
        if policy == "disabled":
            return YaoDecision(actions=())

        actions: list[YaoAction] = []
        cooldowns = state.cooldowns
        is_attached = state.yao_state == "attached"
        is_deer = state.yao_state == "deer"

        if is_deer and cooldowns.q_ready:
            actions.append(
                YaoAction("cast_q", "deer_state_escape", 100)
            )

        allow_defensive = policy in (
            "aggressive",
            "conservative",
            "defensive",
        )
        if allow_defensive and state.is_stable:
            self._add_defensive_actions(state, actions)

        attach_target = self._select_attach_target(state)
        if (
            not is_attached
            and not is_deer
            and cooldowns.r_ready
            and attach_target is not None
        ):
            actions.append(
                YaoAction(
                    "attach_teammate",
                    "teammate_in_r_range",
                    70,
                    target=attach_target,
                )
            )

        if self._allow_offensive(state, policy):
            self._add_offensive_actions(state, actions)

        if is_attached:
            actions.append(YaoAction("stay_attached", "attached_state_hold", 1))

        ranked = tuple(sorted(actions, key=lambda action: action.priority, reverse=True))
        selected = ranked[0] if ranked else None
        return YaoDecision(actions=ranked, selected_action=selected)

    def _add_defensive_actions(
        self, state: YaoDecisionState, actions: list[YaoAction]
    ) -> None:
        cooldowns = state.cooldowns
        low_hp_count = self._low_hp_count(state)

        if cooldowns.f_ready and (
            low_hp_count >= 2
            or (state.self_health is not None and state.self_health < 30)
        ):
            actions.append(
                YaoAction(
                    "cast_f",
                    "low_health_summoner",
                    90,
                    target={"low_hp_count": low_hp_count},
                )
            )

        active_item_target = self._select_low_hp_teammate(
            state, attr="in_active_item_range"
        )
        if cooldowns.active_item_ready and active_item_target is not None:
            actions.append(
                YaoAction(
                    "cast_active_item",
                    "low_health_teammate_in_item_range",
                    85,
                    target=active_item_target,
                )
            )

        no_enemy_nearby = not state.enemies
        if (
            cooldowns.recover_ready
            and state.yao_state != "attached"
            and state.self_health is not None
            and state.self_health < 60
            and no_enemy_nearby
        ):
            actions.append(YaoAction("recover", "self_low_health_safe", 30))

    def _add_offensive_actions(
        self, state: YaoDecisionState, actions: list[YaoAction]
    ) -> None:
        cooldowns = state.cooldowns
        q_target = self._select_enemy_in_range(state, "in_q_range")
        e_target = self._select_enemy_in_range(state, "in_e_range")
        attack_target = self._select_enemy_in_range(state, "in_attack_range")

        if cooldowns.q_ready and q_target is not None:
            actions.append(
                YaoAction("cast_q", "enemy_in_q_range", 50, target=q_target)
            )

        allow_second_skill = (
            state.yao_state == "attached"
            or not state.is_moving
            or state.battle_state == "fight"
        )
        if (
            state.yao_state != "deer"
            and cooldowns.e_ready
            and e_target is not None
            and allow_second_skill
        ):
            actions.append(
                YaoAction("cast_e", "enemy_in_e_range", 40, target=e_target)
            )

        if (
            state.yao_state not in ("attached", "deer")
            and not state.is_moving
            and cooldowns.attack_ready
            and attack_target is not None
        ):
            actions.append(
                YaoAction("basic_attack", "enemy_in_attack_range", 20, target=attack_target)
            )

    def _effective_policy(self, state: YaoDecisionState) -> str:
        policy = (state.skill_policy or "aggressive").lower()
        battle_state = (state.battle_state or "follow").lower()

        if policy == "disabled" or battle_state == "recall":
            return "disabled"
        if battle_state == "retreat":
            return "defensive"
        if battle_state == "fight":
            return "aggressive"
        if battle_state == "follow" and policy == "aggressive":
            return "conservative"
        return policy

    def _allow_offensive(self, state: YaoDecisionState, policy: str) -> bool:
        if policy == "aggressive":
            return True
        return policy == "conservative" and bool(state.enemies)

    def _low_hp_count(self, state: YaoDecisionState) -> int:
        count = 0
        if state.self_health is not None and state.self_health < 60:
            count += 1
        for teammate in state.teammates:
            if teammate.in_f_range and teammate.health is not None and teammate.health < 50:
                count += 1
        return count

    def _select_attach_target(self, state: YaoDecisionState) -> dict[str, Any] | None:
        candidates = [
            (idx, teammate)
            for idx, teammate in enumerate(state.teammates)
            if teammate.in_r_range
        ]
        if not candidates:
            return None

        idx, teammate = min(
            candidates,
            key=lambda item: (
                item[1].health if item[1].health is not None else 101,
                item[1].distance if item[1].distance is not None else inf,
            ),
        )
        return {"index": idx, "source": teammate.source}

    def _select_low_hp_teammate(
        self, state: YaoDecisionState, attr: str
    ) -> dict[str, Any] | None:
        candidates = []
        for idx, teammate in enumerate(state.teammates):
            if not getattr(teammate, attr):
                continue
            if teammate.health is None or teammate.health >= 50:
                continue
            candidates.append((idx, teammate))

        if not candidates:
            return None

        idx, teammate = min(
            candidates,
            key=lambda item: (
                item[1].health if item[1].health is not None else 101,
                item[1].distance if item[1].distance is not None else inf,
            ),
        )
        return {"index": idx, "source": teammate.source}

    def _select_enemy_in_range(
        self, state: YaoDecisionState, attr: str
    ) -> dict[str, Any] | None:
        candidates = [
            (idx, enemy)
            for idx, enemy in enumerate(state.enemies)
            if getattr(enemy, attr)
        ]
        if not candidates:
            return None

        idx, enemy = min(
            candidates,
            key=lambda item: item[1].distance if item[1].distance is not None else inf,
        )
        return {"index": idx, "source": enemy.source}
