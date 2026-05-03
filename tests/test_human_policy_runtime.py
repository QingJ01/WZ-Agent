"""Tests for runtime human policy inference helpers."""

from __future__ import annotations

import pytest

from wzry_ai.learning.human_policy import (
    ACTION_TO_INDEX,
    HumanPolicyPrediction,
    HumanPolicyRuntime,
    build_human_policy_model,
    extract_features,
    load_human_policy,
)


def test_human_policy_runtime_uses_injected_predictor():
    state = {
        "yao_state": "attached",
        "battle_state": "fight",
        "skill_policy": "aggressive",
        "self_health": 80,
    }
    feature_len = len(extract_features(state))
    seen = {}

    def predictor(features):
        seen["features"] = features
        return HumanPolicyPrediction("cast_q", 0.92)

    runtime = HumanPolicyRuntime(
        model=None,
        actions=tuple(ACTION_TO_INDEX),
        input_dim=feature_len,
        confidence_threshold=0.7,
        predictor=predictor,
    )

    prediction = runtime.predict(state)

    assert prediction == HumanPolicyPrediction("cast_q", 0.92)
    assert len(seen["features"]) == feature_len


def test_human_policy_runtime_pads_feature_vector_for_saved_input_dim():
    runtime = HumanPolicyRuntime(
        model=None,
        actions=("no_op", "cast_e"),
        input_dim=50,
        confidence_threshold=0.7,
        predictor=lambda features: HumanPolicyPrediction("cast_e", 0.8),
    )

    prediction = runtime.predict({"self_health": 50})

    assert prediction.action == "cast_e"


def test_load_human_policy_rejects_collapsed_training_report(tmp_path):
    torch = pytest.importorskip("torch")
    policy_path = tmp_path / "self_policy.pt"
    model = build_human_policy_model(input_dim=2, output_dim=2)
    torch.save(
        {
            "model_state": model.state_dict(),
            "input_dim": 2,
            "actions": ("no_op", "cast_q"),
            "metadata": {
                "training_report": {
                    "sample_count": 100,
                    "action_counts": {"no_op": 96, "cast_q": 4},
                }
            },
        },
        policy_path,
    )

    with pytest.raises(RuntimeError, match="no_op 占比过高"):
        load_human_policy(policy_path)
