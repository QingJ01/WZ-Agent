"""Train an imitation policy from runtime decision records."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from scripts.train_human_policy import (
    ACTION_TO_INDEX,
    INDEX_TO_ACTION,
    extract_features,
    train_policy_from_dataset,
)


def load_decision_rows(
    paths: Iterable[str | Path],
    *,
    include_model_actions: bool = False,
    include_control_disabled_actions: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _iter_jsonl_paths(paths):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if row.get("schema_version") != 1:
                    continue
                action_source = str(row.get("action_source", "")).lower()
                if not include_model_actions and action_source == "model":
                    continue
                action = _action_from_row(row)
                if action_source == "control_disabled":
                    if not include_control_disabled_actions:
                        continue
                    if action in {None, "no_op"}:
                        continue
                if action is not None and action in ACTION_TO_INDEX:
                    rows.append(row)
    return rows


def prepare_dataset(
    paths: Iterable[str | Path],
    *,
    include_model_actions: bool = False,
    include_control_disabled_actions: bool = True,
) -> tuple[list[list[float]], list[int]]:
    rows = load_decision_rows(
        paths,
        include_model_actions=include_model_actions,
        include_control_disabled_actions=include_control_disabled_actions,
    )
    features = [extract_features(row.get("state") or {}) for row in rows]
    labels = []
    for row in rows:
        action = _action_from_row(row)
        if action is not None:
            labels.append(ACTION_TO_INDEX[action])
    return features, labels


def train_self_policy(
    paths: Iterable[str | Path],
    *,
    output: str | Path = "models/self_policy.pt",
    epochs: int = 20,
    lr: float = 1e-3,
    min_samples: int = 20,
    min_action_samples: int = 20,
    report_path: str | Path | None = None,
    include_model_actions: bool = False,
    include_control_disabled_actions: bool = True,
) -> Path:
    features, labels = prepare_dataset(
        paths,
        include_model_actions=include_model_actions,
        include_control_disabled_actions=include_control_disabled_actions,
    )
    output_path = Path(output)
    resolved_report_path = report_path or default_report_path(output_path)
    report = build_training_report(
        labels,
        min_samples=min_samples,
        min_action_samples=min_action_samples,
    )
    write_training_report(report, resolved_report_path)
    if report["sample_count"] < min_samples:
        raise RuntimeError(
            f"not enough self-training rows: {report['sample_count']}/{min_samples}"
        )
    return train_policy_from_dataset(
        features,
        labels,
        output=output_path,
        epochs=epochs,
        lr=lr,
        report_path=resolved_report_path,
        min_action_samples=min_action_samples,
        metadata={
            "source": "self_decision_records",
            "min_samples": min_samples,
            "min_action_samples": min_action_samples,
            "include_model_actions": include_model_actions,
            "include_control_disabled_actions": include_control_disabled_actions,
            "training_report": report,
        },
    )


def build_training_report(
    labels: list[int],
    *,
    min_samples: int = 20,
    min_action_samples: int = 20,
) -> dict[str, Any]:
    action_counts = Counter(INDEX_TO_ACTION[label] for label in labels)
    rare_actions = {
        action: count
        for action, count in sorted(action_counts.items())
        if count < min_action_samples
    }
    return {
        "source": "self_decision_records",
        "sample_count": len(labels),
        "min_samples": min_samples,
        "ready": len(labels) >= min_samples,
        "action_counts": dict(sorted(action_counts.items())),
        "covered_action_count": len(action_counts),
        "missing_actions": [
            action for action in INDEX_TO_ACTION.values() if action_counts.get(action, 0) == 0
        ],
        "per_action_min_samples": min_action_samples,
        "rare_actions": rare_actions,
    }


def default_report_path(output: str | Path) -> Path:
    output_path = Path(output)
    return output_path.with_name(f"{output_path.stem}_report.json")


def write_training_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report_path


def _action_from_row(row: dict[str, Any]) -> str | None:
    saw_explicit_action = False
    for key in ("executed_action", "selected_action", "fallback_action"):
        action_payload = row.get(key)
        if isinstance(action_payload, dict):
            action = action_payload.get("action")
            saw_explicit_action = True
            if isinstance(action, str) and action in ACTION_TO_INDEX:
                return action
    if saw_explicit_action:
        return None
    return "no_op"


def _iter_jsonl_paths(paths: Iterable[str | Path]):
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            yield from sorted(path.rglob("*.jsonl"))
        elif path.exists():
            yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Decision JSONL file or directory paths")
    parser.add_argument("--output", default="models/self_policy.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--min-action-samples", type=int, default=20)
    parser.add_argument("--report")
    parser.add_argument(
        "--include-model-actions",
        action="store_true",
        help="Include actions generated by a previously loaded policy model.",
    )
    parser.add_argument(
        "--exclude-control-disabled-actions",
        action="store_true",
        help="Exclude dry-run rule decisions recorded while AI control was disabled.",
    )
    args = parser.parse_args(argv)

    try:
        output = train_self_policy(
            args.paths,
            output=args.output,
            epochs=args.epochs,
            lr=args.lr,
            min_samples=args.min_samples,
            min_action_samples=args.min_action_samples,
            report_path=args.report,
            include_model_actions=args.include_model_actions,
            include_control_disabled_actions=not args.exclude_control_disabled_actions,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1
    print(f"saved {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
