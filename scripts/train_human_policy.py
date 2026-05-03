"""Train a first-stage human imitation policy from schema-v2 demo JSONL."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from wzry_ai.learning.human_policy import build_human_policy_model


ACTION_NAMES = (
    "no_op",
    "stay_attached",
    "move",
    "cast_q",
    "cast_e",
    "attach_teammate",
    "cast_f",
    "cast_active_item",
    "recover",
    "basic_attack",
    "recall",
    "level_ult",
    "level_1",
    "level_2",
    "buy_item",
    "touch",
)
ACTION_TO_INDEX = {name: index for index, name in enumerate(ACTION_NAMES)}
INDEX_TO_ACTION = {index: name for name, index in ACTION_TO_INDEX.items()}
ACTION_ALIASES = {
    "stop": "no_op",
}
RUNTIME_EXECUTABLE_ACTIONS = {
    "no_op",
    "stay_attached",
    "cast_q",
    "cast_e",
    "attach_teammate",
    "cast_f",
    "cast_active_item",
    "recover",
    "basic_attack",
}
DEFAULT_COORDINATE_PLANE = (2400, 1080)
COORDINATE_PAIRS = (
    ("x", "y"),
    ("start_x", "start_y"),
    ("end_x", "end_y"),
)

YAO_STATES = ("unknown", "normal", "attached", "deer")
BATTLE_STATES = ("follow", "fight", "retreat", "push")
SKILL_POLICIES = ("disabled", "conservative", "aggressive", "defensive")
COOLDOWN_KEYS = (
    "q_ready",
    "e_ready",
    "r_ready",
    "f_ready",
    "active_item_ready",
    "recover_ready",
    "attack_ready",
)
RANGE_KEYS = (
    "in_q_range",
    "in_e_range",
    "in_r_range",
    "in_f_range",
    "in_active_item_range",
    "in_attack_range",
)


def load_demo_rows(
    paths: Iterable[str | Path],
    *,
    return_skipped: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    skipped_actions: Counter[str] = Counter()
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
                if row.get("schema_version") != 2:
                    continue
                action = normalize_policy_action((row.get("human_action") or {}).get("action"))
                if action in ACTION_TO_INDEX:
                    row = _replace_human_action(row, action)
                    rows.append(row)
                elif action:
                    skipped_actions[str(action)] += 1
    if return_skipped:
        return rows, dict(sorted(skipped_actions.items()))
    return rows


def prepare_dataset(paths: Iterable[str | Path]) -> tuple[list[list[float]], list[int]]:
    rows = load_demo_rows(paths)
    return _dataset_from_rows(rows)


def normalize_policy_action(action: Any) -> str | None:
    if action is None:
        return None
    normalized = str(action).strip()
    return ACTION_ALIASES.get(normalized, normalized)


def _replace_human_action(row: dict[str, Any], action: str) -> dict[str, Any]:
    human_action = row.get("human_action")
    if not isinstance(human_action, dict):
        human_action = {}
    if human_action.get("action") == action:
        return row
    replaced = dict(row)
    replaced["human_action"] = dict(human_action)
    replaced["human_action"]["action"] = action
    return replaced


def _dataset_from_rows(rows: list[dict[str, Any]]) -> tuple[list[list[float]], list[int]]:
    features = [extract_features(row.get("state") or {}) for row in rows]
    labels = [ACTION_TO_INDEX[row["human_action"]["action"]] for row in rows]
    return features, labels


def extract_features(state: dict[str, Any]) -> list[float]:
    teammates = _target_list(state.get("teammates"))
    enemies = _target_list(state.get("enemies"))
    cooldowns = _mapping(state.get("cooldowns"))

    features: list[float] = []
    features.extend(_one_hot(str(state.get("yao_state", "unknown")), YAO_STATES))
    features.extend(_one_hot(str(state.get("battle_state", "follow")), BATTLE_STATES))
    features.extend(_one_hot(str(state.get("skill_policy", "aggressive")), SKILL_POLICIES))
    features.append(_scale_health(state.get("self_health")))
    features.append(_bool(state.get("is_moving")))
    features.append(_bool(state.get("is_stable")))
    features.extend(_target_features(teammates))
    features.extend(_target_features(enemies))
    for key in COOLDOWN_KEYS:
        features.append(_bool(cooldowns.get(key)))
    return features


def train_policy(
    paths: Iterable[str | Path],
    *,
    output: str | Path = "models/human_policy.pt",
    epochs: int = 20,
    lr: float = 1e-3,
    metadata: dict[str, Any] | None = None,
    report_path: str | Path | None = None,
    validation_fraction: float = 0.2,
    min_action_samples: int = 20,
    max_coordinate_out_of_bounds_ratio: float = 0.05,
) -> Path:
    rows, skipped_actions = load_demo_rows(paths, return_skipped=True)
    features, labels = _dataset_from_rows(rows)
    merged_metadata = dict(metadata or {})
    data_quality = build_human_demo_quality_report(rows)
    merged_metadata["data_quality"] = data_quality
    if skipped_actions:
        merged_metadata["skipped_actions"] = skipped_actions
    coordinate_error = _coordinate_quality_error(
        data_quality,
        max_out_of_bounds_ratio=max_coordinate_out_of_bounds_ratio,
    )
    if coordinate_error is not None:
        preflight_report = build_policy_training_report(
            labels,
            source=str(merged_metadata.get("source", "human_demo")),
            min_action_samples=min_action_samples,
            training={
                "blocked": True,
                "reason": "coordinate_out_of_bounds",
            },
            validation={
                "enabled": False,
                "sample_count": 0,
                "reason": "preflight quality check failed",
            },
        )
        preflight_report["data_quality"] = data_quality
        if skipped_actions:
            preflight_report["skipped_actions"] = dict(sorted(skipped_actions.items()))
        write_policy_training_report(
            preflight_report,
            report_path or default_report_path(output),
        )
        raise RuntimeError(coordinate_error)
    return train_policy_from_dataset(
        features,
        labels,
        output=output,
        epochs=epochs,
        lr=lr,
        metadata=merged_metadata,
        report_path=report_path,
        validation_fraction=validation_fraction,
        min_action_samples=min_action_samples,
    )


def train_policy_from_dataset(
    features: list[list[float]],
    labels: list[int],
    *,
    output: str | Path = "models/human_policy.pt",
    epochs: int = 20,
    lr: float = 1e-3,
    metadata: dict[str, Any] | None = None,
    report_path: str | Path | None = None,
    validation_fraction: float = 0.2,
    min_action_samples: int = 20,
    random_seed: int = 42,
) -> Path:
    if not features:
        raise RuntimeError("no policy training rows found")
    if len(features) != len(labels):
        raise RuntimeError("features and labels length mismatch")

    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for training") from exc

    x = torch.tensor(features, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.long)
    train_indices, validation_indices = _split_train_validation_indices(
        labels,
        validation_fraction=validation_fraction,
        random_seed=random_seed,
    )
    train_x = x[train_indices]
    train_y = y[train_indices]
    dataset = TensorDataset(train_x, train_y)
    loader = DataLoader(dataset, batch_size=min(64, len(dataset)), shuffle=True)

    model = build_human_policy_model(input_dim=x.shape[1], output_dim=len(ACTION_NAMES))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    loss_history: list[float] = []
    for _ in range(max(1, epochs)):
        total_loss = 0.0
        total_samples = 0
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
            batch_size = int(batch_y.shape[0])
            total_loss += float(loss.item()) * batch_size
            total_samples += batch_size
        loss_history.append(round(total_loss / max(1, total_samples), 6))

    train_metrics = _evaluate_model(model, train_x, train_y, loss_fn)
    if validation_indices:
        validation_metrics = _evaluate_model(
            model,
            x[validation_indices],
            y[validation_indices],
            loss_fn,
        )
        validation_report = {
            "enabled": True,
            "sample_count": len(validation_indices),
            **validation_metrics,
        }
    else:
        validation_report = {
            "enabled": False,
            "sample_count": 0,
            "reason": "not enough repeated action classes for holdout validation",
        }

    source = str((metadata or {}).get("source", "human_demo"))
    training_report = build_policy_training_report(
        labels,
        source=source,
        min_action_samples=min_action_samples,
        training={
            "epochs": max(1, epochs),
            "lr": lr,
            "train_sample_count": len(train_indices),
            "loss_history": loss_history,
            "train_accuracy": train_metrics["accuracy"],
            "train_loss": train_metrics["loss"],
        },
        validation=validation_report,
    )
    existing_report = (metadata or {}).get("training_report")
    if isinstance(existing_report, dict):
        merged_report = dict(existing_report)
        merged_report.update(training_report)
        training_report = merged_report
    skipped_actions = (metadata or {}).get("skipped_actions")
    if isinstance(skipped_actions, dict) and skipped_actions:
        training_report["skipped_actions"] = dict(sorted(skipped_actions.items()))
    data_quality = (metadata or {}).get("data_quality")
    if isinstance(data_quality, dict) and data_quality:
        training_report["data_quality"] = data_quality

    checkpoint_metadata = dict(metadata or {"source": source})
    checkpoint_metadata.setdefault("source", source)
    checkpoint_metadata["training_report"] = training_report

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "input_dim": x.shape[1],
            "actions": ACTION_NAMES,
            "feature_schema": {
                "yao_states": YAO_STATES,
                "battle_states": BATTLE_STATES,
                "skill_policies": SKILL_POLICIES,
                "cooldown_keys": COOLDOWN_KEYS,
                "range_keys": RANGE_KEYS,
            },
            "metadata": checkpoint_metadata,
        },
        output_path,
    )
    write_policy_training_report(
        training_report,
        report_path or default_report_path(output_path),
    )
    return output_path


def build_policy_training_report(
    labels: list[int],
    *,
    source: str,
    min_action_samples: int = 20,
    training: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action_counts = Counter(INDEX_TO_ACTION[label] for label in labels)
    rare_actions = {
        action: count
        for action, count in sorted(action_counts.items())
        if count < min_action_samples
    }
    runtime_unsupported_actions = {
        action: count
        for action, count in sorted(action_counts.items())
        if action not in RUNTIME_EXECUTABLE_ACTIONS
    }
    return {
        "source": source,
        "sample_count": len(labels),
        "action_counts": dict(sorted(action_counts.items())),
        "covered_action_count": len(action_counts),
        "missing_actions": [
            action for action in ACTION_NAMES if action_counts.get(action, 0) == 0
        ],
        "per_action_min_samples": min_action_samples,
        "rare_actions": rare_actions,
        "runtime_unsupported_actions": runtime_unsupported_actions,
        "training": training or {},
        "validation": validation
        or {
            "enabled": False,
            "sample_count": 0,
            "reason": "not evaluated",
        },
    }


def build_human_demo_quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coordinate_sample_count = 0
    coordinate_out_of_bounds_count = 0
    coordinate_plane_counts: Counter[str] = Counter()
    coordinate_out_of_bounds_actions: Counter[str] = Counter()

    for row in rows:
        width, height = _row_coordinate_plane(row)
        human_action = row.get("human_action")
        if not isinstance(human_action, dict):
            continue
        payload = human_action.get("payload")
        if not isinstance(payload, dict):
            continue
        action = str(human_action.get("action") or "unknown")
        for x, y in _payload_coordinate_pairs(payload):
            coordinate_sample_count += 1
            coordinate_plane_counts[f"{width}x{height}"] += 1
            if x < 0 or y < 0 or x > width or y > height:
                coordinate_out_of_bounds_count += 1
                coordinate_out_of_bounds_actions[action] += 1

    ratio = (
        coordinate_out_of_bounds_count / coordinate_sample_count
        if coordinate_sample_count
        else 0.0
    )
    warnings: list[dict[str, Any]] = []
    if coordinate_out_of_bounds_count:
        warnings.append(
            {
                "code": "coordinate_out_of_bounds",
                "message": (
                    "human action coordinates exceed the recorded game coordinate plane"
                ),
                "count": coordinate_out_of_bounds_count,
                "sample_count": coordinate_sample_count,
                "ratio": round(ratio, 6),
            }
        )

    return {
        "coordinate_sample_count": coordinate_sample_count,
        "coordinate_out_of_bounds_count": coordinate_out_of_bounds_count,
        "coordinate_out_of_bounds_ratio": round(ratio, 6),
        "coordinate_plane_counts": dict(sorted(coordinate_plane_counts.items())),
        "coordinate_out_of_bounds_actions": dict(
            sorted(coordinate_out_of_bounds_actions.items())
        ),
        "warnings": warnings,
    }


def _coordinate_quality_error(
    data_quality: dict[str, Any],
    *,
    max_out_of_bounds_ratio: float,
) -> str | None:
    sample_count = int(data_quality.get("coordinate_sample_count") or 0)
    bad_count = int(data_quality.get("coordinate_out_of_bounds_count") or 0)
    if sample_count <= 0 or bad_count <= 0:
        return None
    ratio = bad_count / sample_count
    if ratio <= max(0.0, max_out_of_bounds_ratio):
        return None
    plane_counts = data_quality.get("coordinate_plane_counts")
    planes = ", ".join(str(key) for key in plane_counts) if isinstance(plane_counts, dict) else ""
    return (
        "人工示范数据坐标检查失败: "
        f"{bad_count}/{sample_count} 条触摸坐标超出游戏坐标平面"
        + (f" ({planes})" if planes else "")
        + "。这通常是把原始触摸分辨率当成游戏分辨率录进了数据；"
        "请清理旧的 logs/human_demos 后重新录制。"
    )


def _payload_coordinate_pairs(payload: dict[str, Any]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for x_key, y_key in COORDINATE_PAIRS:
        x_value = payload.get(x_key)
        y_value = payload.get(y_key)
        if isinstance(x_value, (int, float)) and isinstance(y_value, (int, float)):
            pairs.append((float(x_value), float(y_value)))
    return pairs


def _row_coordinate_plane(row: dict[str, Any]) -> tuple[int, int]:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        for key in ("touch_size", "game_size", "coordinate_plane"):
            parsed = _parse_size_like(metadata.get(key))
            if parsed is not None:
                return parsed
    state = row.get("state")
    if isinstance(state, dict):
        parsed = _parse_size_like(state.get("game_size"))
        if parsed is not None:
            return parsed
    return DEFAULT_COORDINATE_PLANE


def _parse_size_like(value: Any) -> tuple[int, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            width = int(value[0])
            height = int(value[1])
        except (TypeError, ValueError):
            return None
        if width > 0 and height > 0:
            return width, height
        return None
    if isinstance(value, dict):
        try:
            width = int(value.get("width"))
            height = int(value.get("height"))
        except (TypeError, ValueError):
            return None
        if width > 0 and height > 0:
            return width, height
        return None
    if isinstance(value, str):
        parts = value.lower().replace("x", ",").split(",")
        if len(parts) == 2:
            try:
                width = int(parts[0].strip())
                height = int(parts[1].strip())
            except ValueError:
                return None
            if width > 0 and height > 0:
                return width, height
    return None


def default_report_path(output: str | Path) -> Path:
    output_path = Path(output)
    return output_path.with_name(f"{output_path.stem}_report.json")


def write_policy_training_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report_path


def _split_train_validation_indices(
    labels: list[int],
    *,
    validation_fraction: float,
    random_seed: int,
) -> tuple[list[int], list[int]]:
    all_indices = list(range(len(labels)))
    if len(all_indices) < 2 or validation_fraction <= 0:
        return all_indices, []

    by_label: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        by_label[label].append(index)

    rng = random.Random(random_seed)
    train_indices: list[int] = []
    validation_indices: list[int] = []
    for indices in by_label.values():
        shuffled = list(indices)
        rng.shuffle(shuffled)
        if len(shuffled) < 2:
            train_indices.extend(shuffled)
            continue
        validation_count = max(1, int(round(len(shuffled) * validation_fraction)))
        validation_count = min(validation_count, len(shuffled) - 1)
        validation_indices.extend(shuffled[:validation_count])
        train_indices.extend(shuffled[validation_count:])

    train_indices.sort()
    validation_indices.sort()
    if not train_indices:
        return all_indices, []
    return train_indices, validation_indices


def _evaluate_model(model, x, y, loss_fn) -> dict[str, Any]:
    import torch

    if int(y.shape[0]) == 0:
        return {
            "loss": None,
            "accuracy": None,
            "confusion_matrix": {},
        }

    was_training = model.training
    model.eval()
    with torch.no_grad():
        logits = model(x)
        loss = float(loss_fn(logits, y).item())
        predictions = torch.argmax(logits, dim=1)
        accuracy = float((predictions == y).float().mean().item())
    if was_training:
        model.train()
    return {
        "loss": round(loss, 6),
        "accuracy": round(accuracy, 6),
        "confusion_matrix": _build_confusion_matrix(
            y.tolist(),
            predictions.tolist(),
        ),
    }


def _build_confusion_matrix(actual: list[int], predicted: list[int]) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = {}
    for actual_index, predicted_index in zip(actual, predicted):
        actual_action = INDEX_TO_ACTION.get(int(actual_index), str(actual_index))
        predicted_action = INDEX_TO_ACTION.get(int(predicted_index), str(predicted_index))
        matrix.setdefault(actual_action, Counter())[predicted_action] += 1
    return {
        actual_action: dict(sorted(predicted_counts.items()))
        for actual_action, predicted_counts in sorted(matrix.items())
    }


def _iter_jsonl_paths(paths: Iterable[str | Path]):
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            yield from sorted(path.rglob("*.jsonl"))
        elif path.exists():
            yield path


def _target_features(targets: list[dict[str, Any]]) -> list[float]:
    if not targets:
        return [0.0] * (4 + len(RANGE_KEYS))
    distances = [_scale_distance(target.get("distance")) for target in targets]
    healths = [_scale_health(target.get("health")) for target in targets]
    features = [
        min(len(targets), 10) / 10.0,
        min(distances) if distances else 0.0,
        min(healths) if healths else 0.0,
        sum(1 for value in healths if 0.0 < value < 0.5) / 10.0,
    ]
    for key in RANGE_KEYS:
        features.append(1.0 if any(_bool(target.get(key)) for target in targets) else 0.0)
    return features


def _target_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _one_hot(value: str, choices: tuple[str, ...]) -> list[float]:
    normalized = value.strip().lower()
    return [1.0 if normalized == choice else 0.0 for choice in choices]


def _bool(value: Any) -> float:
    return 1.0 if bool(value) else 0.0


def _scale_health(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed / 100.0))


def _scale_distance(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed / 1500.0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="JSONL file or directory paths")
    parser.add_argument("--output", default="models/human_policy.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--report")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--min-action-samples", type=int, default=20)
    parser.add_argument(
        "--max-coordinate-out-of-bounds-ratio",
        type=float,
        default=0.05,
        help="Abort human-demo training if too many touch coordinates exceed the game plane.",
    )
    args = parser.parse_args(argv)

    try:
        output = train_policy(
            args.paths,
            output=args.output,
            epochs=args.epochs,
            lr=args.lr,
            report_path=args.report,
            validation_fraction=args.validation_fraction,
            min_action_samples=args.min_action_samples,
            max_coordinate_out_of_bounds_ratio=args.max_coordinate_out_of_bounds_ratio,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1
    print(f"saved {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
