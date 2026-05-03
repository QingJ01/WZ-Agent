"""Runtime helpers for human imitation policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


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
RUNTIME_EXECUTABLE_ACTION_NAMES = {
    "no_op",
    "stay_attached",
    "cast_q",
    "cast_e",
    "attach_teammate",
    "cast_f",
    "cast_active_item",
    "recover",
    "basic_attack",
    "level_ult",
    "level_1",
    "level_2",
    "buy_item",
}
MIN_RUNTIME_EXECUTABLE_ACTION_RATIO = 0.10
MAX_NO_OP_ACTION_RATIO = 0.90
MIN_VALIDATION_MACRO_RECALL = 0.35

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


@dataclass(frozen=True)
class HumanPolicyPrediction:
    action: str
    confidence: float


class HumanPolicyRuntime:
    """Small inference wrapper for trained human policy checkpoints."""

    def __init__(
        self,
        *,
        model: Any,
        actions: Iterable[str],
        input_dim: int,
        confidence_threshold: float,
        predictor: Optional[Callable[[list[float]], HumanPolicyPrediction]] = None,
    ):
        self.model = model
        self.actions = tuple(actions)
        self.input_dim = int(input_dim)
        self.confidence_threshold = float(confidence_threshold)
        self.predictor = predictor

    def predict(self, state: Any) -> HumanPolicyPrediction | None:
        features = self._resize_features(extract_features(_serialize(state)))
        if self.predictor is not None:
            return self.predictor(features)
        if self.model is None:
            return None

        try:
            import torch
        except ImportError:
            logger.warning("PyTorch unavailable; human policy disabled")
            return None

        with torch.no_grad():
            tensor = torch.tensor([features], dtype=torch.float32)
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)[0]
            confidence, index = torch.max(probs, dim=0)
        action_index = int(index.item())
        if action_index < 0 or action_index >= len(self.actions):
            return None
        return HumanPolicyPrediction(
            action=self.actions[action_index],
            confidence=float(confidence.item()),
        )

    def _resize_features(self, features: list[float]) -> list[float]:
        if len(features) < self.input_dim:
            return features + [0.0] * (self.input_dim - len(features))
        if len(features) > self.input_dim:
            return features[: self.input_dim]
        return features


def build_human_policy_from_env() -> HumanPolicyRuntime | None:
    if os.environ.get("WZRY_HUMAN_POLICY_ENABLED", "0").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    path = Path(os.environ.get("WZRY_HUMAN_POLICY_PATH", "models/human_policy.pt"))
    threshold_raw = os.environ.get("WZRY_HUMAN_POLICY_CONFIDENCE", "0.80")
    try:
        threshold = max(0.0, min(1.0, float(threshold_raw)))
    except ValueError:
        threshold = 0.80
    try:
        return load_human_policy(path, confidence_threshold=threshold)
    except Exception as exc:
        logger.warning("human policy load failed: %s", exc)
        return None


def load_human_policy(
    path: str | Path,
    *,
    confidence_threshold: float = 0.80,
) -> HumanPolicyRuntime:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for human policy inference") from exc

    checkpoint_path = Path(path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(str(checkpoint_path))
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    quality_error = validate_policy_training_report_for_runtime(
        _checkpoint_training_report(checkpoint)
        or _load_adjacent_training_report(checkpoint_path)
    )
    if quality_error is not None:
        raise RuntimeError(quality_error)
    input_dim = int(checkpoint["input_dim"])
    actions = tuple(checkpoint.get("actions") or ACTION_NAMES)
    model = HumanPolicyNetwork(input_dim=input_dim, output_dim=len(actions))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return HumanPolicyRuntime(
        model=model,
        actions=actions,
        input_dim=input_dim,
        confidence_threshold=confidence_threshold,
    )


def build_human_policy_model(input_dim: int, output_dim: int):
    """Build the PyTorch model used by the trainer and runtime loader."""
    try:
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch is required") from exc
    return nn.Sequential(
        nn.Linear(input_dim, 64),
        nn.ReLU(),
        nn.Linear(64, 64),
        nn.ReLU(),
        nn.Linear(64, output_dim),
    )


def HumanPolicyNetwork(input_dim: int, output_dim: int):
    return build_human_policy_model(input_dim, output_dim)


def validate_policy_training_report_for_runtime(report: Any) -> str | None:
    if report is None:
        return None
    if not isinstance(report, Mapping):
        return "策略模型质量检查失败: 训练报告格式无效"

    training = report.get("training")
    if isinstance(training, Mapping) and training.get("blocked"):
        return (
            "策略模型质量检查失败: 训练报告显示该模型已被阻止 "
            f"({training.get('reason', 'quality_check_failed')})"
        )

    data_quality = report.get("data_quality")
    if isinstance(data_quality, Mapping):
        bad_coordinates = _safe_int(data_quality.get("coordinate_out_of_bounds_count"))
        coordinate_samples = _safe_int(data_quality.get("coordinate_sample_count"))
        if bad_coordinates:
            return (
                "策略模型质量检查失败: "
                f"触摸坐标越界 {bad_coordinates}/{coordinate_samples}"
            )

    action_counts = _safe_action_counts(report.get("action_counts"))
    total_actions = sum(action_counts.values())
    if total_actions > 0:
        executable_count = sum(
            count
            for action, count in action_counts.items()
            if action in RUNTIME_EXECUTABLE_ACTION_NAMES
        )
        executable_ratio = executable_count / total_actions
        if executable_ratio < MIN_RUNTIME_EXECUTABLE_ACTION_RATIO:
            return (
                "策略模型质量检查失败: "
                f"运行时可执行动作样本过少 {executable_count}/{total_actions}"
            )

        no_op_count = action_counts.get("no_op", 0)
        no_op_ratio = no_op_count / total_actions
        if no_op_ratio > MAX_NO_OP_ACTION_RATIO:
            return (
                "策略模型质量检查失败: "
                f"no_op 占比过高 {no_op_count}/{total_actions}"
            )

    validation = report.get("validation")
    if isinstance(validation, Mapping) and validation.get("enabled"):
        macro_recall = _validation_macro_recall(validation.get("confusion_matrix"))
        if (
            macro_recall is not None
            and macro_recall < MIN_VALIDATION_MACRO_RECALL
        ):
            return (
                "策略模型质量检查失败: "
                f"验证宏召回率过低 {macro_recall * 100:.2f}%"
            )
    return None


def _checkpoint_training_report(checkpoint: Any) -> Any:
    if not isinstance(checkpoint, Mapping):
        return None
    metadata = checkpoint.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    return metadata.get("training_report")


def _load_adjacent_training_report(path: Path) -> Any:
    report_path = path.with_name(f"{path.stem}_report.json")
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"策略模型质量检查失败: 读取训练报告失败 - {exc}") from exc


def _safe_action_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    counts: dict[str, int] = {}
    for action, count in value.items():
        safe_count = _safe_int(count)
        if safe_count > 0:
            counts[str(action)] = safe_count
    return counts


def _validation_macro_recall(confusion_matrix: Any) -> float | None:
    if not isinstance(confusion_matrix, Mapping) or not confusion_matrix:
        return None
    recalls: list[float] = []
    for actual_action, predicted_counts in confusion_matrix.items():
        if not isinstance(predicted_counts, Mapping):
            continue
        total = sum(_safe_int(count) for count in predicted_counts.values())
        if total <= 0:
            continue
        correct = _safe_int(predicted_counts.get(actual_action))
        recalls.append(correct / total)
    if not recalls:
        return None
    return sum(recalls) / len(recalls)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _serialize(value: Any) -> Any:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    return {}


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
