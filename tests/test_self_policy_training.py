"""Tests for self-training from recorded runtime decisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.train_human_policy import ACTION_TO_INDEX
import pytest

from scripts.train_self_policy import (
    build_training_report,
    default_report_path,
    load_decision_rows,
    prepare_dataset,
    train_self_policy,
)


def test_train_self_policy_script_help_runs_without_pythonpath():
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "scripts/train_self_policy.py", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Train an imitation policy from runtime decision records" in result.stdout


def test_load_decision_rows_reads_executed_actions(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": {"self_health": 80, "yao_state": "attached"},
                "executed_action": {"action": "cast_q"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_decision_rows([path])

    assert len(rows) == 1
    assert rows[0]["executed_action"]["action"] == "cast_q"


def test_prepare_dataset_converts_decision_records_to_labels(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80, "yao_state": "attached"},
                        "executed_action": {"action": "cast_q"},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 60, "yao_state": "normal"},
                        "executed_action": {"action": "attach_teammate"},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 60},
                        "executed_action": None,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    features, labels = prepare_dataset([path])

    assert len(features) == 3
    assert labels == [
        ACTION_TO_INDEX["cast_q"],
        ACTION_TO_INDEX["attach_teammate"],
        ACTION_TO_INDEX["no_op"],
    ]


def test_load_decision_rows_skips_model_generated_actions_by_default(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": {"action": "cast_q"},
                        "action_source": "model",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": {"action": "cast_e"},
                        "action_source": "rule",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_decision_rows([path])

    assert len(rows) == 1
    assert rows[0]["executed_action"]["action"] == "cast_e"


def test_load_decision_rows_includes_control_disabled_explicit_actions(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": None,
                        "selected_action": {"action": "cast_q"},
                        "action_source": "control_disabled",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": None,
                        "selected_action": None,
                        "action_source": "control_disabled",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": {"action": "cast_e"},
                        "action_source": "rule",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_decision_rows([path])

    assert len(rows) == 2
    assert rows[0]["selected_action"]["action"] == "cast_q"
    assert rows[1]["executed_action"]["action"] == "cast_e"


def test_load_decision_rows_can_exclude_control_disabled_actions(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": None,
                        "selected_action": {"action": "cast_q"},
                        "action_source": "control_disabled",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": {"action": "cast_e"},
                        "action_source": "rule",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_decision_rows([path], include_control_disabled_actions=False)

    assert len(rows) == 1
    assert rows[0]["executed_action"]["action"] == "cast_e"


def test_prepare_dataset_can_learn_hold_and_no_op_actions(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"yao_state": "attached"},
                        "executed_action": {"action": "stay_attached"},
                        "action_source": "rule",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"yao_state": "normal"},
                        "executed_action": None,
                        "selected_action": None,
                        "action_source": "rule",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _, labels = prepare_dataset([path])

    assert labels == [ACTION_TO_INDEX["stay_attached"], ACTION_TO_INDEX["no_op"]]


def test_load_decision_rows_skips_unknown_explicit_actions(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": {"action": "unknown_action"},
                        "action_source": "rule",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "state": {"self_health": 80},
                        "executed_action": None,
                        "selected_action": None,
                        "action_source": "rule",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_decision_rows([path])

    assert len(rows) == 1
    _, labels = prepare_dataset([path])
    assert labels == [ACTION_TO_INDEX["no_op"]]


def test_build_training_report_counts_actions_and_minimum_samples():
    report = build_training_report(
        [ACTION_TO_INDEX["cast_q"], ACTION_TO_INDEX["stay_attached"]],
        min_samples=3,
    )

    assert report["sample_count"] == 2
    assert report["min_samples"] == 3
    assert report["ready"] is False
    assert report["action_counts"]["cast_q"] == 1
    assert report["action_counts"]["stay_attached"] == 1
    assert report["per_action_min_samples"] == 20
    assert report["rare_actions"] == {"cast_q": 1, "stay_attached": 1}


def test_train_self_policy_rejects_too_few_samples_and_writes_report(tmp_path):
    path = tmp_path / "decisions.jsonl"
    output = tmp_path / "models" / "self_policy.pt"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": {"self_health": 80},
                "executed_action": {"action": "cast_q"},
                "action_source": "rule",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="not enough self-training rows"):
        train_self_policy([path], output=output, min_samples=2)

    report = json.loads(default_report_path(output).read_text(encoding="utf-8"))
    assert report["sample_count"] == 1
    assert report["ready"] is False


def test_train_self_policy_writes_validation_metrics(tmp_path):
    path = tmp_path / "decisions.jsonl"
    output = tmp_path / "models" / "self_policy.pt"
    rows = []
    for idx in range(24):
        action = "cast_q" if idx % 2 == 0 else "stay_attached"
        rows.append(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": {
                        "self_health": 80 if action == "cast_q" else 100,
                        "yao_state": "attached",
                        "enemies": [{"distance": 200, "health": 70, "in_q_range": True}]
                        if action == "cast_q"
                        else [],
                    },
                    "executed_action": {"action": action},
                    "action_source": "rule",
                }
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    train_self_policy([path], output=output, min_samples=20, epochs=1)

    report = json.loads(default_report_path(output).read_text(encoding="utf-8"))
    assert report["sample_count"] == 24
    assert report["ready"] is True
    assert report["validation"]["enabled"] is True
    assert "accuracy" in report["validation"]
    assert "loss" in report["validation"]
    assert "confusion_matrix" in report["validation"]
    assert report["training"]["loss_history"]
