"""Tests for human policy training data preparation."""

from __future__ import annotations

import json

import pytest

from scripts.train_human_policy import (
    ACTION_TO_INDEX,
    build_human_demo_quality_report,
    build_policy_training_report,
    extract_features,
    load_demo_rows,
    prepare_dataset,
    train_policy,
)


def test_load_demo_rows_reads_schema_v2_jsonl(tmp_path):
    path = tmp_path / "demo.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "state": {"self_health": 80, "yao_state": "attached"},
                "human_action": {"action": "cast_q"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_demo_rows([path])

    assert len(rows) == 1
    assert rows[0]["human_action"]["action"] == "cast_q"


def test_extract_features_returns_stable_numeric_vector():
    state = {
        "yao_state": "attached",
        "battle_state": "fight",
        "skill_policy": "aggressive",
        "self_health": 75,
        "is_moving": True,
        "is_stable": False,
        "teammates": [{"distance": 240, "health": 60, "in_r_range": True}],
        "enemies": [{"distance": 320, "health": 70, "in_q_range": True}],
        "cooldowns": {
            "q_ready": True,
            "e_ready": False,
            "r_ready": True,
            "f_ready": False,
            "active_item_ready": True,
            "recover_ready": False,
            "attack_ready": True,
        },
    }

    features = extract_features(state)

    assert all(isinstance(value, float) for value in features)
    assert len(features) >= 20
    assert features == extract_features(state)


def test_prepare_dataset_converts_rows_to_features_and_labels(tmp_path):
    path = tmp_path / "demo.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 2,
                        "state": {"self_health": 90, "yao_state": "normal"},
                        "human_action": {"action": "attach_teammate"},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 2,
                        "state": {"self_health": 50, "yao_state": "attached"},
                        "human_action": {"action": "cast_q"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    features, labels = prepare_dataset([path])

    assert len(features) == 2
    assert len(labels) == 2
    assert labels[0] == ACTION_TO_INDEX["attach_teammate"]
    assert labels[1] == ACTION_TO_INDEX["cast_q"]


def test_prepare_dataset_normalizes_stop_to_no_op(tmp_path):
    path = tmp_path / "demo.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "state": {"self_health": 90, "yao_state": "normal"},
                "human_action": {"action": "stop"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_demo_rows([path])
    _, labels = prepare_dataset([path])

    assert rows[0]["human_action"]["action"] == "no_op"
    assert labels == [ACTION_TO_INDEX["no_op"]]


def test_load_demo_rows_reports_skipped_unknown_actions(tmp_path):
    path = tmp_path / "demo.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 2,
                        "state": {},
                        "human_action": {"action": "cast_q"},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 2,
                        "state": {},
                        "human_action": {"action": "unknown_action"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, skipped = load_demo_rows([path], return_skipped=True)

    assert len(rows) == 1
    assert skipped == {"unknown_action": 1}


def test_build_human_demo_quality_report_flags_coordinate_pollution():
    report = build_human_demo_quality_report(
        [
            {
                "metadata": {"touch_size": [2400, 1080]},
                "human_action": {
                    "action": "cast_q",
                    "payload": {"x": 1925, "y": 928, "dx": 1.0, "dy": -1.0},
                },
            },
            {
                "human_action": {
                    "action": "touch",
                    "payload": {"x": 10177, "y": 22748},
                },
            },
            {
                "metadata": {"touch_size": "1920x1080"},
                "human_action": {
                    "action": "move",
                    "payload": {"x": 1900, "y": 900, "dx": 1.0, "dy": -1.0},
                },
            },
        ]
    )

    assert report["coordinate_sample_count"] == 3
    assert report["coordinate_out_of_bounds_count"] == 1
    assert report["coordinate_out_of_bounds_actions"] == {"touch": 1}
    assert report["coordinate_plane_counts"] == {"1920x1080": 1, "2400x1080": 2}
    assert report["warnings"][0]["code"] == "coordinate_out_of_bounds"


def test_train_policy_blocks_heavily_coordinate_polluted_dataset(tmp_path):
    path = tmp_path / "demo.jsonl"
    output = tmp_path / "human_policy.pt"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "state": {},
                "human_action": {
                    "action": "touch",
                    "payload": {"x": 10177, "y": 22748},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="坐标检查失败"):
        train_policy([path], output=output)

    report = json.loads((tmp_path / "human_policy_report.json").read_text(encoding="utf-8"))
    assert not output.exists()
    assert report["training"]["blocked"] is True
    assert report["data_quality"]["coordinate_out_of_bounds_count"] == 1


def test_build_policy_training_report_includes_data_quality_and_validation():
    report = build_policy_training_report(
        [
            ACTION_TO_INDEX["cast_q"],
            ACTION_TO_INDEX["cast_q"],
            ACTION_TO_INDEX["no_op"],
            ACTION_TO_INDEX["move"],
        ],
        source="human_demo",
        min_action_samples=2,
        training={
            "epochs": 1,
            "lr": 0.001,
            "train_sample_count": 2,
            "loss_history": [1.2],
            "train_accuracy": 0.5,
        },
        validation={
            "enabled": True,
            "sample_count": 1,
            "loss": 1.1,
            "accuracy": 1.0,
            "confusion_matrix": {"cast_q": {"cast_q": 1}},
        },
    )

    assert report["source"] == "human_demo"
    assert report["sample_count"] == 4
    assert report["action_counts"]["cast_q"] == 2
    assert report["rare_actions"] == {"move": 1, "no_op": 1}
    assert report["runtime_unsupported_actions"] == {"move": 1}
    assert report["validation"]["accuracy"] == 1.0
    assert report["training"]["loss_history"] == [1.2]
