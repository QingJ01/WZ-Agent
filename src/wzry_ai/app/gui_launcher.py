"""Tkinter launcher for the packaged runtime."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

from wzry_ai.learning.human_policy import validate_policy_training_report_for_runtime

_POLICY_ACTION_NAMES = {
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
}
_POLICY_ACTION_ALIASES = {
    "stop": "no_op",
}


UI_TEXT = {
    "title": "WZ-Agent 控制台",
    "status": {
        "runtime": "运行状态",
        "training": "训练状态",
        "stopped": "已停止",
        "running": "运行中",
        "idle": "空闲",
    },
    "tabs": {
        "runtime": "设备连接与运行",
        "learning": "示范数据采集",
        "training": "策略模型训练",
        "models": "模型与推理配置",
    },
    "frames": {
        "log": "日志",
        "runtime": "运行配置",
        "devices": "ADB 设备列表",
    },
    "labels": {
        "mode": "设备模式",
        "adb": "ADB 可执行文件",
        "serial": "ADB 设备序列号",
        "frame_source": "视觉帧源模式",
        "scrcpy_timeout": "scrcpy 首帧超时(秒)",
        "source": "采集输入源",
        "demo_dir": "示范数据目录",
        "decision_record_dir": "自训练决策记录目录",
        "touch_size": "游戏画面分辨率",
        "raw_touch_size": "原始触摸分辨率",
        "raw_transform": "触摸坐标变换",
        "debug_windows": "OpenCV 调试窗口",
        "minimap_preview": "小地图预览",
        "ai_control": "AI 自动操作",
        "dataset": "训练数据目录",
        "training_source": "训练数据类型",
        "output": "策略模型输出",
        "epochs": "训练轮数",
        "model1_weights": "小地图英雄检测权重",
        "model2_weights": "血条检测权重",
        "model3_weights": "事件检测权重",
        "human_policy": "模仿学习策略权重",
        "human_policy_confidence": "策略接管置信度阈值",
    },
    "buttons": {
        "browse": "选择",
        "phone_mode": "真机 ADB 模式",
        "mumu_mode": "MuMu ADB 模式",
        "start_runtime": "启动运行",
        "stop_runtime": "停止运行",
        "refresh_devices": "刷新 ADB 设备",
        "clear_log": "清空日志",
        "record_human_demo": "启用示范数据采集",
        "show_debug_windows": "显示 EVE / EVE Check 调试窗口",
        "show_minimap_preview": "启用 GUI 小地图预览",
        "enable_ai_control": "启用 AI 自动操作",
        "open_demo_folder": "打开示范数据目录",
        "use_demo_dir_for_training": "设为训练数据",
        "record_decisions": "记录运行决策样本",
        "use_decision_dir_for_training": "使用自训练记录",
        "start_training": "开始训练策略模型",
        "stop_training": "停止训练",
        "use_human_policy": "启用模仿学习策略",
    },
    "dialogs": {
        "adb": "选择 adb.exe",
        "demo_dir": "选择示范数据目录",
        "training_dataset": "选择训练数据目录",
        "training_output": "选择策略模型输出位置",
        "model_weights": "选择模型权重",
    },
    "logs": {
        "starting_runtime": "启动运行进程",
        "stopping_runtime": "正在停止运行进程...",
        "runtime_kill": "运行进程未正常退出，正在强制结束。",
        "runtime_exit": "运行进程已退出，退出码",
        "starting_training": "启动策略模型训练",
        "stopping_training": "正在停止训练...",
        "training_kill": "训练进程未正常停止，正在强制结束。",
        "training_exit": "训练进程已退出，退出码",
        "open_demo_failed": "打开示范数据目录失败",
        "refreshing_devices": "正在刷新设备",
        "adb_refresh_failed": "ADB 刷新失败",
        "no_adb_output": "没有 ADB 输出。",
        "runtime_already_running": "运行进程已经在运行。",
        "android_requires_serial": "真机 ADB 模式需要选择或填写设备序列号。",
        "start_failed": "启动失败",
        "training_already_running": "训练进程已经在运行。",
        "epochs_integer": "训练轮数必须是整数。",
        "epochs_positive": "训练轮数必须大于 0。",
        "training_start_failed": "训练启动失败",
        "model_file_missing": "模型权重文件不存在",
        "human_policy_confidence_invalid": "策略接管置信度阈值必须是 0 到 1 之间的小数。",
        "frame_source_invalid": "视觉帧源模式必须是 scrcpy、auto 或 adb。",
        "scrcpy_timeout_invalid": "scrcpy 首帧超时必须是 1 到 30 秒之间的数字。",
        "training_selection_applied": "已切换到策略模型训练",
        "training_dataset_empty": "当前目录没有可训练 JSONL，先采集数据再训练",
        "training_report": "训练报告",
        "training_report_missing": "未找到训练报告",
        "training_report_read_failed": "读取训练报告失败",
        "training_source_mismatch": "训练数据类型和目录不匹配",
        "training_source_defaults_applied": "已根据训练数据类型更新训练目录和输出模型",
    },
}


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AdbDeviceSummary:
    """Summary of a connected ADB device."""

    serial: str
    state: str
    model: str = ""
    product: str = ""
    device: str = ""
    raw: str = ""

    @property
    def display_name(self) -> str:
        if self.model:
            return f"{self.serial} ({self.model})"
        return self.serial


@dataclass(frozen=True)
class RuntimeLaunchConfig:
    """Inputs needed to launch the runtime process."""

    mode: str
    adb_path: str
    adb_serial: str
    repo_root: Path
    frame_source_mode: str = "scrcpy"
    scrcpy_first_frame_timeout: str = "10.0"
    human_demo_enabled: bool = False
    human_demo_source: str = ""
    human_demo_dir: str = "logs/human_demos"
    touch_size: str = ""
    touch_raw_size: str = ""
    touch_raw_transform: str = "identity"
    debug_windows_enabled: bool = False
    minimap_preview_enabled: bool = True
    minimap_preview_path: str = ""
    ai_control_enabled: bool = False
    decision_recording_enabled: bool = False
    decision_record_dir: str = "logs/decision_records"
    model1_weights: str = ""
    model2_weights: str = ""
    model3_weights: str = ""
    human_policy_enabled: bool = False
    human_policy_path: str = "models/human_policy.pt"
    human_policy_confidence: str = "0.80"


@dataclass(frozen=True)
class TrainingLaunchConfig:
    """Inputs needed to train the human imitation policy."""

    dataset_path: Path
    output_path: Path
    epochs: int
    repo_root: Path
    source: str = "human_demo"


@dataclass(frozen=True)
class GuiDefaultSettings:
    """Computed GUI defaults based on local data and environment flags."""

    decision_recording_enabled: bool
    decision_record_dir: str
    training_source: str
    training_dataset: str
    training_output: str
    human_policy_enabled: bool
    human_policy_path: str


def parse_adb_devices(output: str) -> list[AdbDeviceSummary]:
    """Parse ``adb devices -l`` output, returning devices in the ready state."""
    devices: list[AdbDeviceSummary] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial, state = parts[0], parts[1]
        if state != "device":
            continue

        attrs: dict[str, str] = {}
        for token in parts[2:]:
            key, sep, value = token.partition(":")
            if sep:
                attrs[key] = value

        devices.append(
            AdbDeviceSummary(
                serial=serial,
                state=state,
                model=attrs.get("model", ""),
                product=attrs.get("product", ""),
                device=attrs.get("device", ""),
                raw=raw_line,
            )
        )

    return devices


def is_local_tcp_serial(serial: str) -> bool:
    """Return whether an ADB serial points at a local emulator endpoint."""
    normalized = serial.strip().lower()
    return (
        normalized.startswith("127.0.0.1:")
        or normalized.startswith("localhost:")
        or normalized.startswith("[::1]:")
    )


def resolve_runtime_mode(mode: str, adb_serial: str) -> str:
    """Resolve GUI auto mode into the runtime mode services should use."""
    normalized_mode = (mode or "auto").strip().lower()
    serial = adb_serial.strip()
    if normalized_mode != "auto":
        return normalized_mode
    if not serial:
        return "auto"
    return "mumu" if is_local_tcp_serial(serial) else "android"


def choose_default_device(
    devices: list[AdbDeviceSummary],
    current_serial: str,
) -> Optional[AdbDeviceSummary]:
    """Choose a GUI default without overwriting an explicitly connected serial."""
    if not devices:
        return None

    serial = current_serial.strip()
    if serial:
        for device in devices:
            if device.serial == serial:
                return device
        if not is_local_tcp_serial(serial):
            return None

    for device in devices:
        if not is_local_tcp_serial(device.serial):
            return device
    return devices[0]


def build_gui_default_settings(
    repo_root: Path,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> GuiDefaultSettings:
    env_map = env if env is not None else os.environ
    decision_dir = "logs/decision_records"
    demo_dir = "logs/human_demos"
    self_policy_path = Path(repo_root) / "models" / "self_policy.pt"
    human_policy_path = Path(repo_root) / "models" / "human_policy.pt"

    if _has_jsonl_records(Path(repo_root) / decision_dir, schema_version=1):
        training_source = "self_decision"
    elif _has_jsonl_records(Path(repo_root) / demo_dir, schema_version=2):
        training_source = "human_demo"
    else:
        training_source = "self_decision"

    if training_source == "self_decision":
        training_dataset = decision_dir
        training_output = "models/self_policy.pt"
    else:
        training_dataset = demo_dir
        training_output = "models/human_policy.pt"

    if self_policy_path.exists():
        policy_path = self_policy_path
    elif human_policy_path.exists():
        policy_path = human_policy_path
    else:
        policy_path = self_policy_path

    decision_recording_enabled = _env_flag(
        env_map,
        "WZRY_DECISION_RECORDING",
        default=True,
    )
    human_policy_enabled = _env_flag(
        env_map,
        "WZRY_HUMAN_POLICY_ENABLED",
        default=False,
    )

    return GuiDefaultSettings(
        decision_recording_enabled=decision_recording_enabled,
        decision_record_dir=decision_dir,
        training_source=training_source,
        training_dataset=training_dataset,
        training_output=training_output,
        human_policy_enabled=human_policy_enabled,
        human_policy_path=str(policy_path),
    )


def _has_jsonl_records(path: Path, *, schema_version: int | None = None) -> bool:
    if not path.exists():
        return False
    for jsonl_path in _iter_jsonl_files(path):
        if _jsonl_file_has_trainable_row(jsonl_path, schema_version=schema_version):
            return True
    return False


def _iter_jsonl_files(path: Path):
    if path.is_file():
        if path.suffix.lower() == ".jsonl":
            yield path
        return
    yield from sorted(path.rglob("*.jsonl"))


def _jsonl_file_has_trainable_row(
    path: Path,
    *,
    schema_version: int | None,
) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if schema_version is not None and row.get("schema_version") != schema_version:
                    continue
                if _row_is_trainable_policy_sample(row):
                    return True
    except OSError:
        return False
    return False


def _row_is_trainable_policy_sample(row: Mapping[str, object]) -> bool:
    schema_version = row.get("schema_version")
    if schema_version == 2:
        action_payload = row.get("human_action")
        if not isinstance(action_payload, Mapping):
            return False
        return _canonical_policy_action(action_payload.get("action")) in _POLICY_ACTION_NAMES

    if schema_version == 1:
        if str(row.get("action_source", "")).lower() == "model":
            return False
        saw_explicit_action = False
        for key in ("executed_action", "selected_action", "fallback_action"):
            action_payload = row.get(key)
            if isinstance(action_payload, Mapping):
                saw_explicit_action = True
                if _canonical_policy_action(action_payload.get("action")) in _POLICY_ACTION_NAMES:
                    return True
        if saw_explicit_action:
            return False
        return isinstance(row.get("state"), Mapping)

    return False


def _canonical_policy_action(action: object) -> str:
    normalized = str(action or "").strip()
    return _POLICY_ACTION_ALIASES.get(normalized, normalized)


def _env_flag(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw_value = env.get(key)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_frame_source_mode(value: str) -> str:
    normalized = (value or "scrcpy").strip().lower()
    aliases = {
        "scrcpy_only": "scrcpy",
        "force_scrcpy": "scrcpy",
        "forced_scrcpy": "scrcpy",
        "adb_screenshot": "adb",
        "screencap": "adb",
        "screenshot": "adb",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"scrcpy", "auto", "adb"} else "scrcpy"


def build_runtime_environment(
    config: RuntimeLaunchConfig,
    *,
    base_env: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Build the child process environment for ``Master_Auto.py``."""
    env = _build_repo_environment(config.repo_root, base_env=base_env)
    resolved_mode = resolve_runtime_mode(config.mode, config.adb_serial)
    env["WZRY_DEVICE_MODE"] = resolved_mode
    env["WZRY_FRAME_SOURCE"] = _normalize_frame_source_mode(config.frame_source_mode)
    env["WZRY_SCRCPY_FIRST_FRAME_TIMEOUT"] = (
        config.scrcpy_first_frame_timeout or "10.0"
    )
    env["WZRY_HUMAN_DEMO_ENABLED"] = "1" if config.human_demo_enabled else "0"
    env["WZRY_HUMAN_DEMO_SOURCE"] = _resolve_human_demo_source(
        config.human_demo_source,
        resolved_mode,
    )
    env["WZRY_HUMAN_DEMO_DIR"] = config.human_demo_dir or "logs/human_demos"
    env["WZRY_TOUCH_RAW_TRANSFORM"] = config.touch_raw_transform or "identity"
    env["WZRY_DEBUG_WINDOWS"] = "1" if config.debug_windows_enabled else "0"
    env["WZRY_GUI_MINIMAP_PREVIEW"] = "1" if config.minimap_preview_enabled else "0"
    env["WZRY_GUI_MINIMAP_PATH"] = (
        config.minimap_preview_path
        or str(Path(config.repo_root) / "logs" / "gui_preview" / "minimap.png")
    )
    env["WZRY_AI_CONTROL_ENABLED"] = "1" if config.ai_control_enabled else "0"
    env["WZRY_DECISION_RECORDING"] = "1" if config.decision_recording_enabled else "0"
    env["WZRY_DECISION_RECORD_DIR"] = str(
        _resolve_config_path(
            config.repo_root,
            config.decision_record_dir or "logs/decision_records",
        )
    )
    env["WZRY_HUMAN_POLICY_ENABLED"] = "1" if config.human_policy_enabled else "0"
    env["WZRY_HUMAN_POLICY_PATH"] = config.human_policy_path or "models/human_policy.pt"
    env["WZRY_HUMAN_POLICY_CONFIDENCE"] = config.human_policy_confidence or "0.80"
    if config.model1_weights:
        env["WZRY_MODEL1_WEIGHTS"] = config.model1_weights
    if config.model2_weights:
        env["WZRY_MODEL2_WEIGHTS"] = config.model2_weights
    if config.model3_weights:
        env["WZRY_MODEL3_WEIGHTS"] = config.model3_weights
    if config.touch_size:
        env["WZRY_TOUCH_SIZE"] = config.touch_size
    if config.touch_raw_size:
        env["WZRY_TOUCH_RAW_SIZE"] = config.touch_raw_size

    if config.adb_path:
        env["WZRY_ADB_PATH"] = config.adb_path
    if config.adb_serial:
        env["WZRY_ADB_DEVICE"] = config.adb_serial

    return env


def build_training_environment(
    config: TrainingLaunchConfig,
    *,
    base_env: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Build the child process environment for human policy training."""
    return _build_repo_environment(config.repo_root, base_env=base_env)


def validate_runtime_config(config: RuntimeLaunchConfig) -> str | None:
    if _normalize_frame_source_mode(config.frame_source_mode) != (
        config.frame_source_mode or "scrcpy"
    ).strip().lower():
        return UI_TEXT["logs"]["frame_source_invalid"]

    try:
        first_frame_timeout = float(config.scrcpy_first_frame_timeout or "10.0")
    except ValueError:
        return UI_TEXT["logs"]["scrcpy_timeout_invalid"]
    if first_frame_timeout < 1.0 or first_frame_timeout > 30.0:
        return UI_TEXT["logs"]["scrcpy_timeout_invalid"]

    for label_key, raw_path in (
        ("model1_weights", config.model1_weights),
        ("model2_weights", config.model2_weights),
        ("model3_weights", config.model3_weights),
    ):
        if raw_path and not _resolve_config_path(config.repo_root, raw_path).exists():
            return (
                f"{UI_TEXT['logs']['model_file_missing']}: "
                f"{UI_TEXT['labels'][label_key]} - {raw_path}"
            )

    if not config.human_policy_enabled:
        return None

    try:
        confidence = float(config.human_policy_confidence or "0.80")
    except ValueError:
        return UI_TEXT["logs"]["human_policy_confidence_invalid"]
    if confidence < 0.0 or confidence > 1.0:
        return UI_TEXT["logs"]["human_policy_confidence_invalid"]

    policy_path = config.human_policy_path or "models/human_policy.pt"
    if not _resolve_config_path(config.repo_root, policy_path).exists():
        return (
            f"{UI_TEXT['logs']['model_file_missing']}: "
            f"{UI_TEXT['labels']['human_policy']} - {policy_path}"
        )
    policy_report_error = validate_policy_runtime_report(
        config.repo_root,
        policy_path,
    )
    if policy_report_error is not None:
        return policy_report_error
    return None


def _resolve_config_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(repo_root) / path


def _build_repo_environment(
    repo_root: Path,
    *,
    base_env: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)
    local_scrcpy_dir = Path(repo_root) / "scrcpy"
    if local_scrcpy_dir.is_dir():
        current_path = env.get("PATH", "")
        current_parts = [
            os.path.normcase(os.path.abspath(part))
            for part in current_path.split(os.pathsep)
            if part
        ]
        normalized_scrcpy_dir = os.path.normcase(os.path.abspath(local_scrcpy_dir))
        if normalized_scrcpy_dir not in current_parts:
            env["PATH"] = (
                str(local_scrcpy_dir)
                if not current_path
                else str(local_scrcpy_dir) + os.pathsep + current_path
            )
    src_path = str(Path(repo_root) / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else src_path + os.pathsep + existing_pythonpath
    )
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUTF8"] = "1"
    return env


def _resolve_human_demo_source(source: str, resolved_mode: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized in {"adb_touch", "windows_keyboard"}:
        return normalized
    return "adb_touch" if resolved_mode == "android" else "windows_keyboard"


def build_runtime_command(
    config: RuntimeLaunchConfig,
    *,
    python_executable: str = sys.executable,
) -> list[str]:
    """Build the command used to start the packaged runtime."""
    return [python_executable, str(Path(config.repo_root) / "Master_Auto.py")]


def build_training_command(
    config: TrainingLaunchConfig,
    *,
    python_executable: str = sys.executable,
) -> list[str]:
    """Build the command used to train the human policy."""
    script_name = (
        "train_self_policy.py"
        if config.source == "self_decision"
        else "train_human_policy.py"
    )
    return [
        python_executable,
        str(Path(config.repo_root) / "scripts" / script_name),
        str(config.dataset_path),
        "--output",
        str(config.output_path),
        "--epochs",
        str(max(1, int(config.epochs))),
    ]


def validate_training_config(config: TrainingLaunchConfig) -> str | None:
    selected_source = (
        config.source if config.source in {"human_demo", "self_decision"} else "human_demo"
    )
    dataset_hint = _training_source_from_dataset_path(config.dataset_path)
    output_hint = _training_source_from_output_path(config.output_path)

    for hint, source_label in (
        (dataset_hint, "目录"),
        (output_hint, "输出模型"),
    ):
        if hint is not None and hint != selected_source:
            return _training_source_mismatch_message(
                selected_source,
                hint,
                source_label,
            )

    return None


def _training_source_mismatch_message(
    selected_source: str,
    detected_source: str,
    source_label: str,
) -> str:
    return (
        f"{UI_TEXT['logs']['training_source_mismatch']}: "
        f"当前选择 {training_source_display_name(selected_source)}，"
        f"但{source_label}像是 {training_source_display_name(detected_source)}。"
        "人工示范数据请选择 logs/human_demos 并输出 models/human_policy.pt；"
        "自训练决策记录请选择 logs/decision_records 并输出 models/self_policy.pt。"
    )


def training_source_display_name(source: str) -> str:
    if source == "self_decision":
        return "自训练决策记录"
    return "人工示范数据"


def resolve_training_source_for_paths(
    source: str,
    dataset_path: str | Path,
    output_path: str | Path,
) -> str:
    dataset_hint = _training_source_from_dataset_path(dataset_path)
    if dataset_hint is not None:
        return dataset_hint

    output_hint = _training_source_from_output_path(output_path)
    if output_hint is not None:
        return output_hint

    return source if source in {"human_demo", "self_decision"} else "human_demo"


def _training_source_from_dataset_path(path: str | Path) -> str | None:
    parts = _normalized_path_parts(path)
    if "decision_records" in parts:
        return "self_decision"
    if "human_demos" in parts:
        return "human_demo"
    return None


def _training_source_from_output_path(path: str | Path) -> str | None:
    parts = _normalized_path_parts(path)
    filename = parts[-1] if parts else ""
    stem = filename.rsplit(".", 1)[0]
    if stem == "self_policy":
        return "self_decision"
    if stem == "human_policy":
        return "human_demo"
    return None


def _normalized_path_parts(path: str | Path) -> list[str]:
    return [
        part
        for part in str(path).replace("\\", "/").lower().split("/")
        if part
    ]


def default_training_report_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_name(f"{path.stem}_report.json")


def validate_policy_runtime_report(
    repo_root: Path,
    policy_path: str | Path,
) -> str | None:
    resolved_policy_path = _resolve_config_path(repo_root, str(policy_path))
    report_path = default_training_report_path(resolved_policy_path)
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"策略模型质量检查失败: 读取训练报告失败 - {exc}"
    return validate_policy_training_report_for_runtime(report)


def build_training_report_summary(report: Mapping[str, object]) -> list[str]:
    lines = [
        f"{UI_TEXT['logs']['training_report']}:",
        f"样本数: {_safe_int(report.get('sample_count'))}",
        f"动作覆盖: {_safe_int(report.get('covered_action_count'))}/{len(_POLICY_ACTION_NAMES)}",
    ]

    training = report.get("training")
    if isinstance(training, Mapping):
        if training.get("blocked"):
            lines.append(f"训练已阻止: {training.get('reason', 'quality_check_failed')}")
        if "epochs" in training:
            lines.append(f"训练轮数: {_safe_int(training.get('epochs'))}")
        if "train_accuracy" in training:
            lines.append(f"训练准确率: {_format_percent(training.get('train_accuracy'))}")

    validation = report.get("validation")
    if isinstance(validation, Mapping):
        if validation.get("enabled"):
            lines.append(
                f"验证准确率: {_format_percent(validation.get('accuracy'))} "
                f"(验证样本: {_safe_int(validation.get('sample_count'))})"
            )
        else:
            lines.append("验证集: 未启用")

    action_counts = report.get("action_counts")
    if isinstance(action_counts, Mapping) and action_counts:
        top_actions = sorted(
            ((str(action), _safe_int(count)) for action, count in action_counts.items()),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        lines.append(
            "动作分布Top5: "
            + ", ".join(f"{action}={count}" for action, count in top_actions)
        )

    missing_actions = report.get("missing_actions")
    if isinstance(missing_actions, list) and missing_actions:
        lines.append("缺失动作: " + ", ".join(str(action) for action in missing_actions))

    rare_actions = report.get("rare_actions")
    if isinstance(rare_actions, Mapping) and rare_actions:
        lines.append(
            "样本过少: "
            + ", ".join(
                f"{action}={_safe_int(count)}" for action, count in rare_actions.items()
            )
        )

    unsupported_actions = report.get("runtime_unsupported_actions")
    if isinstance(unsupported_actions, Mapping) and unsupported_actions:
        lines.append(
            "当前运行时不直接执行: "
            + ", ".join(
                f"{action}={_safe_int(count)}"
                for action, count in unsupported_actions.items()
            )
        )

    data_quality = report.get("data_quality")
    if isinstance(data_quality, Mapping):
        out_of_bounds = _safe_int(data_quality.get("coordinate_out_of_bounds_count"))
        coordinate_samples = _safe_int(data_quality.get("coordinate_sample_count"))
        if out_of_bounds:
            lines.append(f"触摸坐标越界: {out_of_bounds}/{coordinate_samples}")
            bad_actions = data_quality.get("coordinate_out_of_bounds_actions")
            if isinstance(bad_actions, Mapping) and bad_actions:
                lines.append(
                    "越界动作: "
                    + ", ".join(
                        f"{action}={_safe_int(count)}"
                        for action, count in bad_actions.items()
                    )
                )

    runtime_report_error = validate_policy_training_report_for_runtime(report)
    if runtime_report_error is not None:
        lines.append(f"模型不可启用: {runtime_report_error}")

    return lines


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _format_percent(value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "N/A"
    return f"{number * 100:.2f}%"


def _windows_startupinfo() -> Optional[subprocess.STARTUPINFO]:
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def run_adb_devices(adb_path: str) -> tuple[list[AdbDeviceSummary], str]:
    """Run ``adb devices -l`` and return parsed devices plus raw output."""
    result = subprocess.run(
        [adb_path, "devices", "-l"],
        capture_output=True,
        text=True,
        timeout=10,
        startupinfo=_windows_startupinfo(),
    )
    raw = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(raw.strip() or f"adb exited with {result.returncode}")
    return parse_adb_devices(raw), raw


class RuntimeProcessController:
    """Owns the runtime subprocess lifecycle for the GUI."""

    def __init__(self, log_queue: Optional["queue.Queue[str]"] = None):
        self.log_queue = log_queue or queue.Queue()
        self._process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, config: RuntimeLaunchConfig) -> None:
        if self.is_running:
            raise RuntimeError("runtime is already running")

        command = build_runtime_command(config)
        env = build_runtime_environment(config)
        self._put_log(f"{UI_TEXT['logs']['starting_runtime']}: {' '.join(command)}")
        self._process = subprocess.Popen(
            command,
            cwd=str(config.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=_windows_startupinfo(),
        )
        self._reader_thread = threading.Thread(
            target=self._read_output,
            daemon=True,
            name="RuntimeOutputReader",
        )
        self._reader_thread.start()

    def stop(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return

        self._put_log(UI_TEXT["logs"]["stopping_runtime"])
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._put_log(UI_TEXT["logs"]["runtime_kill"])
            process.kill()
            process.wait(timeout=5)

    def poll_exit(self) -> Optional[int]:
        if self._process is None:
            return None
        return self._process.poll()

    def _read_output(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return

        for line in process.stdout:
            self._put_log(line.rstrip())

        exit_code = process.wait()
        self._put_log(f"{UI_TEXT['logs']['runtime_exit']}: {exit_code}")

    def _put_log(self, message: str) -> None:
        self.log_queue.put(message)


class TrainingProcessController:
    """Owns the human-policy training subprocess lifecycle."""

    def __init__(self, log_queue: Optional["queue.Queue[str]"] = None):
        self.log_queue = log_queue or queue.Queue()
        self._process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, config: TrainingLaunchConfig) -> None:
        if self.is_running:
            raise RuntimeError("training is already running")

        command = build_training_command(config)
        env = build_training_environment(config)
        self._put_log(f"{UI_TEXT['logs']['starting_training']}: {' '.join(command)}")
        self._process = subprocess.Popen(
            command,
            cwd=str(config.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=_windows_startupinfo(),
        )
        self._reader_thread = threading.Thread(
            target=self._read_output,
            daemon=True,
            name="TrainingOutputReader",
        )
        self._reader_thread.start()

    def stop(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return

        self._put_log(UI_TEXT["logs"]["stopping_training"])
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._put_log(UI_TEXT["logs"]["training_kill"])
            process.kill()
            process.wait(timeout=5)

    def poll_exit(self) -> Optional[int]:
        if self._process is None:
            return None
        return self._process.poll()

    def _read_output(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return

        for line in process.stdout:
            self._put_log(line.rstrip())

        exit_code = process.wait()
        self._put_log(f"{UI_TEXT['logs']['training_exit']}: {exit_code}")

    def _put_log(self, message: str) -> None:
        self.log_queue.put(message)


class GuiLauncherApp:
    """Tkinter operator surface for device selection and runtime control."""

    MODES = ("auto", "android", "mumu")
    FRAME_SOURCE_MODES = ("scrcpy", "auto", "adb")
    MODE_LABELS = {
        "auto": "自动模式",
        "android": "真机 ADB",
        "mumu": "MuMu 模拟器",
    }
    FRAME_SOURCE_LABELS = {
        "scrcpy": "scrcpy 强制模式",
        "auto": "scrcpy 优先，失败后 ADB 截图",
        "adb": "ADB 截图兼容模式",
    }
    SOURCE_LABELS = {
        "auto": "自动选择输入源",
        "adb_touch": "ADB 触摸事件采集",
        "windows_keyboard": "Windows 键鼠采集",
    }
    TRAINING_SOURCE_LABELS = {
        "human_demo": "人工示范数据",
        "self_decision": "自训练决策记录",
    }

    def __init__(self, root, *, repo_root: Optional[Path] = None):
        import tkinter as tk
        from tkinter import scrolledtext, ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.repo_root = Path(repo_root or _default_repo_root())
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.controller = RuntimeProcessController(self.log_queue)
        self.training_controller = TrainingProcessController(self.log_queue)
        self.devices: list[AdbDeviceSummary] = []

        try:
            from wzry_ai.config import (
                ADB_DEVICE_SERIAL,
                ADB_PATH,
                DEVICE_MODE,
                LOCAL_SCRCPY_ADB_PATH,
            )
        except ImportError:
            ADB_PATH = "adb"
            ADB_DEVICE_SERIAL = ""
            DEVICE_MODE = "auto"
            LOCAL_SCRCPY_ADB_PATH = ""

        defaults = build_gui_default_settings(self.repo_root)
        initial_mode = DEVICE_MODE if DEVICE_MODE in self.MODES else "auto"
        adb_default = (
            LOCAL_SCRCPY_ADB_PATH
            if LOCAL_SCRCPY_ADB_PATH and Path(LOCAL_SCRCPY_ADB_PATH).is_file()
            else ADB_PATH
        )
        self.mode_var = tk.StringVar(value=self._mode_label(initial_mode))
        self.adb_path_var = tk.StringVar(value=adb_default)
        self.serial_var = tk.StringVar(value=ADB_DEVICE_SERIAL)
        self.frame_source_var = tk.StringVar(
            value=self._frame_source_label(
                _normalize_frame_source_mode(os.environ.get("WZRY_FRAME_SOURCE", "scrcpy"))
            )
        )
        self.scrcpy_timeout_var = tk.StringVar(
            value=os.environ.get("WZRY_SCRCPY_FIRST_FRAME_TIMEOUT", "10.0")
        )
        self.human_demo_enabled_var = tk.BooleanVar(value=False)
        self.human_demo_source_var = tk.StringVar(value=self._source_label("auto"))
        self.demo_dir_var = tk.StringVar(value="logs/human_demos")
        self.decision_recording_enabled_var = tk.BooleanVar(
            value=defaults.decision_recording_enabled
        )
        self.decision_record_dir_var = tk.StringVar(value=defaults.decision_record_dir)
        self.touch_size_var = tk.StringVar(value=os.environ.get("WZRY_TOUCH_SIZE", "2400x1080"))
        self.touch_raw_size_var = tk.StringVar(value=os.environ.get("WZRY_TOUCH_RAW_SIZE", ""))
        self.touch_raw_transform_var = tk.StringVar(
            value=os.environ.get("WZRY_TOUCH_RAW_TRANSFORM", "identity")
        )
        self.debug_windows_enabled_var = tk.BooleanVar(value=False)
        self.minimap_preview_enabled_var = tk.BooleanVar(value=True)
        self.minimap_preview_path_var = tk.StringVar(
            value=str(self.repo_root / "logs" / "gui_preview" / "minimap.png")
        )
        self.ai_control_enabled_var = tk.BooleanVar(
            value=_env_flag(os.environ, "WZRY_AI_CONTROL_ENABLED", default=False)
        )
        self.training_dataset_var = tk.StringVar(value=defaults.training_dataset)
        self.training_source_var = tk.StringVar(
            value=self._training_source_label(defaults.training_source)
        )
        self.training_output_var = tk.StringVar(value=defaults.training_output)
        self.training_epochs_var = tk.StringVar(value="20")
        self.model1_weights_var = tk.StringVar(value=str(self.repo_root / "models" / "best_perfect.pt"))
        self.model2_weights_var = tk.StringVar(value=str(self.repo_root / "models" / "WZRY-health.pt"))
        self.model3_weights_var = tk.StringVar(value=str(self.repo_root / "models" / "wzry.pt"))
        self.human_policy_enabled_var = tk.BooleanVar(
            value=defaults.human_policy_enabled
        )
        self.human_policy_path_var = tk.StringVar(value=defaults.human_policy_path)
        self.human_policy_confidence_var = tk.StringVar(value="0.80")
        self.status_var = tk.StringVar(value=UI_TEXT["status"]["stopped"])
        self.training_status_var = tk.StringVar(value=UI_TEXT["status"]["idle"])
        self._minimap_photo = None
        self._minimap_preview_mtime = 0.0
        self._last_training_output_path: Path | None = None
        self._training_completion_reported = True

        root.title(UI_TEXT["title"])
        root.geometry("1040x760")
        root.minsize(900, 640)

        self._build_layout(scrolledtext)
        self._schedule_poll()
        self.refresh_devices()

    def _build_layout(self, scrolledtext_module) -> None:
        from tkinter import filedialog

        self.filedialog = filedialog
        root = self.root
        ttk = self.ttk
        tk = self.tk

        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

        status = ttk.Frame(root)
        status.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        status.columnconfigure(2, weight=1)
        ttk.Label(status, text=UI_TEXT["status"]["runtime"]).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Label(status, text=UI_TEXT["status"]["training"]).grid(row=0, column=2, sticky="e")
        ttk.Label(status, textvariable=self.training_status_var).grid(row=0, column=3, sticky="e", padx=(6, 0))

        notebook = ttk.Notebook(root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        self.training_notebook = notebook

        runtime_tab = ttk.Frame(notebook)
        learning_tab = ttk.Frame(notebook)
        training_tab = ttk.Frame(notebook)
        models_tab = ttk.Frame(notebook)
        self.training_tab = training_tab
        notebook.add(runtime_tab, text=UI_TEXT["tabs"]["runtime"])
        notebook.add(learning_tab, text=UI_TEXT["tabs"]["learning"])
        notebook.add(training_tab, text=UI_TEXT["tabs"]["training"])
        notebook.add(models_tab, text=UI_TEXT["tabs"]["models"])

        self._build_runtime_tab(runtime_tab)
        self._build_learning_tab(learning_tab)
        self._build_training_tab(training_tab)
        self._build_models_tab(models_tab)

        log_frame = ttk.LabelFrame(root, text=UI_TEXT["frames"]["log"])
        log_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = scrolledtext_module.ScrolledText(log_frame, height=18, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.log_text.configure(state="disabled")

        log_actions = ttk.Frame(log_frame)
        log_actions.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(log_actions, text=UI_TEXT["buttons"]["clear_log"], command=self.clear_log).pack(side="left")

    def _build_runtime_tab(self, parent) -> None:
        ttk = self.ttk
        tk = self.tk

        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        settings = ttk.LabelFrame(parent, text=UI_TEXT["frames"]["runtime"])
        settings.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=6)
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text=UI_TEXT["labels"]["mode"]).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.mode_combo = ttk.Combobox(
            settings,
            textvariable=self.mode_var,
            values=tuple(self.MODE_LABELS[mode] for mode in self.MODES),
            state="readonly",
            width=16,
        )
        self.mode_combo.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(settings, text=UI_TEXT["labels"]["adb"]).grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(settings, textvariable=self.adb_path_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(settings, text=UI_TEXT["buttons"]["browse"], command=self.browse_adb).grid(
            row=1, column=2, sticky="e", padx=8, pady=6
        )

        ttk.Label(settings, text=UI_TEXT["labels"]["serial"]).grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(settings, textvariable=self.serial_var).grid(
            row=2, column=1, sticky="ew", padx=8, pady=6
        )

        ttk.Label(settings, text=UI_TEXT["labels"]["frame_source"]).grid(
            row=3, column=0, sticky="w", padx=8, pady=6
        )
        self.frame_source_combo = ttk.Combobox(
            settings,
            textvariable=self.frame_source_var,
            values=tuple(
                self.FRAME_SOURCE_LABELS[mode] for mode in self.FRAME_SOURCE_MODES
            ),
            state="readonly",
            width=28,
        )
        self.frame_source_combo.grid(row=3, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(settings, text=UI_TEXT["labels"]["scrcpy_timeout"]).grid(
            row=4, column=0, sticky="w", padx=8, pady=6
        )
        ttk.Entry(settings, textvariable=self.scrcpy_timeout_var, width=10).grid(
            row=4, column=1, sticky="w", padx=8, pady=6
        )

        quick = ttk.Frame(settings)
        quick.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        ttk.Button(quick, text=UI_TEXT["buttons"]["phone_mode"], command=self.use_phone_mode).pack(side="left")
        ttk.Button(quick, text=UI_TEXT["buttons"]["mumu_mode"], command=self.use_mumu_mode).pack(side="left", padx=8)

        ttk.Checkbutton(
            settings,
            text=UI_TEXT["buttons"]["enable_ai_control"],
            variable=self.ai_control_enabled_var,
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))

        actions = ttk.Frame(settings)
        actions.grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=10)
        ttk.Button(actions, text=UI_TEXT["buttons"]["start_runtime"], command=self.start_runtime).pack(side="left")
        ttk.Button(actions, text=UI_TEXT["buttons"]["stop_runtime"], command=self.stop_runtime).pack(side="left", padx=8)

        devices_frame = ttk.LabelFrame(parent, text=UI_TEXT["frames"]["devices"])
        devices_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(6, 0), pady=6)
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)
        self.device_list = tk.Listbox(devices_frame, height=8, exportselection=False)
        self.device_list.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self.device_list.bind("<<ListboxSelect>>", self.on_device_selected)
        device_actions = ttk.Frame(devices_frame)
        device_actions.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(device_actions, text=UI_TEXT["buttons"]["refresh_devices"], command=self.refresh_devices).pack(side="left")

        preview_frame = ttk.LabelFrame(devices_frame, text=UI_TEXT["labels"]["minimap_preview"])
        preview_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.minimap_preview_label = ttk.Label(
            preview_frame,
            text="还没收到小地图画面",
            anchor="center",
        )
        self.minimap_preview_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    def _build_learning_tab(self, parent) -> None:
        ttk = self.ttk

        parent.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            parent,
            text=UI_TEXT["buttons"]["record_human_demo"],
            variable=self.human_demo_enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 6))

        ttk.Checkbutton(
            parent,
            text=UI_TEXT["buttons"]["record_decisions"],
            variable=self.decision_recording_enabled_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=6)

        ttk.Label(parent, text=UI_TEXT["labels"]["source"]).grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.human_demo_source_combo = ttk.Combobox(
            parent,
            textvariable=self.human_demo_source_var,
            values=tuple(self.SOURCE_LABELS.values()),
            state="readonly",
            width=24,
        )
        self.human_demo_source_combo.grid(row=2, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(parent, text=UI_TEXT["labels"]["demo_dir"]).grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.demo_dir_var).grid(
            row=3, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(parent, text=UI_TEXT["buttons"]["browse"], command=self.browse_demo_dir).grid(
            row=3, column=2, sticky="e", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["decision_record_dir"]).grid(row=4, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.decision_record_dir_var).grid(
            row=4, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(parent, text=UI_TEXT["buttons"]["browse"], command=self.browse_decision_record_dir).grid(
            row=4, column=2, sticky="e", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["touch_size"]).grid(row=5, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.touch_size_var, width=22).grid(
            row=5, column=1, sticky="w", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["raw_touch_size"]).grid(row=6, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.touch_raw_size_var, width=22).grid(
            row=6, column=1, sticky="w", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["raw_transform"]).grid(row=7, column=0, sticky="w", padx=8, pady=6)
        ttk.Combobox(
            parent,
            textvariable=self.touch_raw_transform_var,
            values=("identity", "rotate_cw", "rotate_ccw", "flip_180"),
            state="readonly",
            width=20,
        ).grid(row=7, column=1, sticky="w", padx=8, pady=6)

        ttk.Checkbutton(
            parent,
            text=UI_TEXT["buttons"]["show_debug_windows"],
            variable=self.debug_windows_enabled_var,
        ).grid(row=8, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        ttk.Checkbutton(
            parent,
            text=UI_TEXT["buttons"]["show_minimap_preview"],
            variable=self.minimap_preview_enabled_var,
        ).grid(row=9, column=0, columnspan=3, sticky="w", padx=8, pady=6)

        actions = ttk.Frame(parent)
        actions.grid(row=10, column=0, columnspan=3, sticky="ew", padx=8, pady=10)
        ttk.Button(actions, text=UI_TEXT["buttons"]["open_demo_folder"], command=self.open_demo_dir).pack(side="left")
        ttk.Button(actions, text=UI_TEXT["buttons"]["use_demo_dir_for_training"], command=self.copy_demo_dir_to_training).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text=UI_TEXT["buttons"]["use_decision_dir_for_training"], command=self.copy_decision_dir_to_training).pack(
            side="left", padx=8
        )

    def _build_training_tab(self, parent) -> None:
        ttk = self.ttk

        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text=UI_TEXT["labels"]["training_source"]).grid(row=0, column=0, sticky="w", padx=8, pady=(10, 6))
        self.training_source_combo = ttk.Combobox(
            parent,
            textvariable=self.training_source_var,
            values=tuple(self.TRAINING_SOURCE_LABELS.values()),
            state="readonly",
            width=24,
        )
        self.training_source_combo.grid(row=0, column=1, sticky="w", padx=8, pady=(10, 6))
        self.training_source_combo.bind("<<ComboboxSelected>>", self.on_training_source_changed)

        ttk.Label(parent, text=UI_TEXT["labels"]["dataset"]).grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.training_dataset_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(parent, text=UI_TEXT["buttons"]["browse"], command=self.browse_training_dataset).grid(
            row=1, column=2, sticky="e", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["output"]).grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.training_output_var).grid(
            row=2, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(parent, text=UI_TEXT["buttons"]["browse"], command=self.browse_training_output).grid(
            row=2, column=2, sticky="e", padx=8, pady=6
        )

        ttk.Label(parent, text=UI_TEXT["labels"]["epochs"]).grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.training_epochs_var, width=10).grid(
            row=3, column=1, sticky="w", padx=8, pady=6
        )

        actions = ttk.Frame(parent)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=10)
        ttk.Button(actions, text=UI_TEXT["buttons"]["start_training"], command=self.start_training).pack(side="left")
        ttk.Button(actions, text=UI_TEXT["buttons"]["stop_training"], command=self.stop_training).pack(side="left", padx=8)

    def _build_models_tab(self, parent) -> None:
        ttk = self.ttk

        parent.columnconfigure(1, weight=1)
        model_rows = (
            ("model1_weights", self.model1_weights_var, self.browse_model1_weights),
            ("model2_weights", self.model2_weights_var, self.browse_model2_weights),
            ("model3_weights", self.model3_weights_var, self.browse_model3_weights),
            ("human_policy", self.human_policy_path_var, self.browse_human_policy),
        )
        for row, (label_key, variable, command) in enumerate(model_rows):
            ttk.Label(parent, text=UI_TEXT["labels"][label_key]).grid(
                row=row, column=0, sticky="w", padx=8, pady=(10 if row == 0 else 6, 6)
            )
            ttk.Entry(parent, textvariable=variable).grid(
                row=row, column=1, sticky="ew", padx=8, pady=(10 if row == 0 else 6, 6)
            )
            ttk.Button(parent, text=UI_TEXT["buttons"]["browse"], command=command).grid(
                row=row, column=2, sticky="e", padx=8, pady=(10 if row == 0 else 6, 6)
            )

        ttk.Checkbutton(
            parent,
            text=UI_TEXT["buttons"]["use_human_policy"],
            variable=self.human_policy_enabled_var,
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        ttk.Label(parent, text=UI_TEXT["labels"]["human_policy_confidence"]).grid(
            row=5, column=0, sticky="w", padx=8, pady=6
        )
        ttk.Entry(parent, textvariable=self.human_policy_confidence_var, width=10).grid(
            row=5, column=1, sticky="w", padx=8, pady=6
        )

    def browse_adb(self) -> None:
        selected = self.filedialog.askopenfilename(
            title=UI_TEXT["dialogs"]["adb"],
            filetypes=(("ADB executable", "adb.exe"), ("Executables", "*.exe"), ("All files", "*.*")),
        )
        if selected:
            self.adb_path_var.set(selected)

    def browse_demo_dir(self) -> None:
        selected = self.filedialog.askdirectory(title=UI_TEXT["dialogs"]["demo_dir"])
        if selected:
            self.demo_dir_var.set(selected)
            self.training_dataset_var.set(selected)

    def browse_decision_record_dir(self) -> None:
        selected = self.filedialog.askdirectory(title=UI_TEXT["labels"]["decision_record_dir"])
        if selected:
            self.decision_record_dir_var.set(selected)

    def browse_training_dataset(self) -> None:
        selected = self.filedialog.askdirectory(title=UI_TEXT["dialogs"]["training_dataset"])
        if selected:
            self.training_dataset_var.set(selected)

    def browse_training_output(self) -> None:
        selected = self.filedialog.asksaveasfilename(
            title=UI_TEXT["dialogs"]["training_output"],
            defaultextension=".pt",
            filetypes=(("PyTorch model", "*.pt"), ("All files", "*.*")),
        )
        if selected:
            self.training_output_var.set(selected)
            self.human_policy_path_var.set(selected)

    def browse_model1_weights(self) -> None:
        self._browse_model_path_into(self.model1_weights_var)

    def browse_model2_weights(self) -> None:
        self._browse_model_path_into(self.model2_weights_var)

    def browse_model3_weights(self) -> None:
        self._browse_model_path_into(self.model3_weights_var)

    def browse_human_policy(self) -> None:
        self._browse_model_path_into(self.human_policy_path_var)

    def _browse_model_path_into(self, variable) -> None:
        selected = self.filedialog.askopenfilename(
            title=UI_TEXT["dialogs"]["model_weights"],
            filetypes=(("PyTorch model", "*.pt"), ("All files", "*.*")),
        )
        if selected:
            variable.set(selected)

    def use_phone_mode(self) -> None:
        self.mode_var.set(self._mode_label("android"))
        self.human_demo_source_var.set(self._source_label("adb_touch"))

    def use_mumu_mode(self) -> None:
        self.mode_var.set(self._mode_label("mumu"))
        if not self.serial_var.get().strip():
            self.serial_var.set("127.0.0.1:7555")
        self.human_demo_source_var.set(self._source_label("windows_keyboard"))

    def open_demo_dir(self) -> None:
        path = self._resolve_user_path(self.demo_dir_var.get().strip() or "logs/human_demos")
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self._append_log(f"{UI_TEXT['logs']['open_demo_failed']}: {exc}")

    def copy_demo_dir_to_training(self) -> None:
        self._apply_training_selection(
            source="human_demo",
            dataset=self.demo_dir_var.get().strip() or "logs/human_demos",
            output="models/human_policy.pt",
            policy_path=self.repo_root / "models" / "human_policy.pt",
            schema_version=2,
        )

    def copy_decision_dir_to_training(self) -> None:
        self._apply_training_selection(
            source="self_decision",
            dataset=self.decision_record_dir_var.get().strip() or "logs/decision_records",
            output="models/self_policy.pt",
            policy_path=self.repo_root / "models" / "self_policy.pt",
            schema_version=1,
        )

    def on_training_source_changed(self, _event=None) -> None:
        source = self._training_source_value(self.training_source_var.get())
        self._apply_training_source_defaults(source)

    def _apply_training_source_defaults(self, source: str) -> None:
        if source == "self_decision":
            dataset = self.decision_record_dir_var.get().strip() or "logs/decision_records"
            output = "models/self_policy.pt"
            policy_path = self.repo_root / "models" / "self_policy.pt"
        else:
            dataset = self.demo_dir_var.get().strip() or "logs/human_demos"
            output = "models/human_policy.pt"
            policy_path = self.repo_root / "models" / "human_policy.pt"

        self.training_dataset_var.set(dataset)
        self.training_output_var.set(output)
        self.human_policy_path_var.set(str(policy_path))
        self._append_log(
            f"{UI_TEXT['logs']['training_source_defaults_applied']}: "
            f"{self._training_source_label(source)}，目录: {dataset}，输出: {output}"
        )

    def _apply_training_selection(
        self,
        *,
        source: str,
        dataset: str,
        output: str,
        policy_path: Path,
        schema_version: int,
    ) -> None:
        self.training_dataset_var.set(dataset)
        self.training_source_var.set(self._training_source_label(source))
        self.training_output_var.set(output)
        self.human_policy_path_var.set(str(policy_path))
        self._show_training_tab()
        self._append_log(
            f"{UI_TEXT['logs']['training_selection_applied']}: "
            f"{self._training_source_label(source)}，目录: {dataset}"
        )
        if not _has_jsonl_records(self._resolve_user_path(dataset), schema_version=schema_version):
            self._append_log(f"{UI_TEXT['logs']['training_dataset_empty']}: {dataset}")

    def _show_training_tab(self) -> None:
        notebook = getattr(self, "training_notebook", None)
        training_tab = getattr(self, "training_tab", None)
        if notebook is None or training_tab is None:
            return
        try:
            notebook.select(training_tab)
        except Exception as exc:
            self._append_log(f"切换策略模型训练页失败: {exc}")

    def refresh_devices(self) -> None:
        adb_path = self.adb_path_var.get().strip() or "adb"
        self._append_log(f"{UI_TEXT['logs']['refreshing_devices']}: {adb_path}")
        try:
            self.devices, raw = run_adb_devices(adb_path)
        except Exception as exc:
            self.devices = []
            self._append_log(f"{UI_TEXT['logs']['adb_refresh_failed']}: {exc}")
        else:
            self._append_log(raw.strip() or UI_TEXT["logs"]["no_adb_output"])

        self.device_list.delete(0, self.tk.END)
        for device in self.devices:
            self.device_list.insert(self.tk.END, device.display_name)
        preferred_device = choose_default_device(
            self.devices,
            self.serial_var.get().strip(),
        )
        if preferred_device is not None:
            index = self.devices.index(preferred_device)
            self.device_list.selection_clear(0, self.tk.END)
            self.device_list.selection_set(index)
            self.device_list.see(index)
            self.serial_var.set(preferred_device.serial)
            resolved_mode = resolve_runtime_mode(
                self._selected_mode(),
                preferred_device.serial,
            )
            if resolved_mode != "auto":
                self.mode_var.set(self._mode_label(resolved_mode))

    def on_device_selected(self, _event=None) -> None:
        selection = self.device_list.curselection()
        if not selection:
            return
        device = self.devices[selection[0]]
        self.serial_var.set(device.serial)

    def start_runtime(self) -> None:
        if self.controller.is_running:
            self._append_log(UI_TEXT["logs"]["runtime_already_running"])
            return

        mode = self._selected_mode()
        serial = self.serial_var.get().strip()
        if mode == "android" and not serial:
            self._append_log(UI_TEXT["logs"]["android_requires_serial"])
            return

        config = RuntimeLaunchConfig(
            mode=mode,
            adb_path=self.adb_path_var.get().strip(),
            adb_serial=serial,
            repo_root=self.repo_root,
            frame_source_mode=self._selected_frame_source_mode(),
            scrcpy_first_frame_timeout=self.scrcpy_timeout_var.get().strip() or "10.0",
            human_demo_enabled=bool(self.human_demo_enabled_var.get()),
            human_demo_source=self._selected_human_demo_source(),
            human_demo_dir=self.demo_dir_var.get().strip() or "logs/human_demos",
            touch_size=self.touch_size_var.get().strip(),
            touch_raw_size=self.touch_raw_size_var.get().strip(),
            touch_raw_transform=self.touch_raw_transform_var.get().strip() or "identity",
            debug_windows_enabled=bool(self.debug_windows_enabled_var.get()),
            minimap_preview_enabled=bool(self.minimap_preview_enabled_var.get()),
            minimap_preview_path=self.minimap_preview_path_var.get().strip(),
            ai_control_enabled=bool(self.ai_control_enabled_var.get()),
            decision_recording_enabled=bool(self.decision_recording_enabled_var.get()),
            decision_record_dir=self.decision_record_dir_var.get().strip()
            or "logs/decision_records",
            model1_weights=self.model1_weights_var.get().strip(),
            model2_weights=self.model2_weights_var.get().strip(),
            model3_weights=self.model3_weights_var.get().strip(),
            human_policy_enabled=bool(self.human_policy_enabled_var.get()),
            human_policy_path=self.human_policy_path_var.get().strip(),
            human_policy_confidence=self.human_policy_confidence_var.get().strip() or "0.80",
        )
        validation_error = validate_runtime_config(config)
        if validation_error:
            self._append_log(validation_error)
            self.status_var.set(UI_TEXT["status"]["stopped"])
            return
        try:
            self.controller.start(config)
        except Exception as exc:
            self._append_log(f"{UI_TEXT['logs']['start_failed']}: {exc}")
            self.status_var.set(UI_TEXT["status"]["stopped"])
        else:
            self.status_var.set(UI_TEXT["status"]["running"])

    def _selected_human_demo_source(self) -> str:
        source = self._source_value(self.human_demo_source_var.get())
        return "" if source == "auto" else source

    def _selected_mode(self) -> str:
        raw_mode = self.mode_var.get().strip()
        return self._mode_value(raw_mode) or "auto"

    def _selected_frame_source_mode(self) -> str:
        raw_mode = self.frame_source_var.get().strip()
        return self._frame_source_value(raw_mode) or "scrcpy"

    def _mode_label(self, mode: str) -> str:
        return self.MODE_LABELS.get(mode, mode)

    def _mode_value(self, raw_mode: str) -> str:
        if raw_mode in self.MODES:
            return raw_mode
        label_to_value = {label: value for value, label in self.MODE_LABELS.items()}
        return label_to_value.get(raw_mode, "auto")

    def _frame_source_label(self, mode: str) -> str:
        return self.FRAME_SOURCE_LABELS.get(mode, self.FRAME_SOURCE_LABELS["scrcpy"])

    def _frame_source_value(self, raw_mode: str) -> str:
        normalized = raw_mode.strip()
        if normalized in self.FRAME_SOURCE_LABELS:
            return normalized
        label_to_value = {
            label: value for value, label in self.FRAME_SOURCE_LABELS.items()
        }
        return label_to_value.get(normalized, "scrcpy")

    def _source_label(self, source: str) -> str:
        return self.SOURCE_LABELS.get(source, source)

    def _source_value(self, raw_source: str) -> str:
        normalized = raw_source.strip()
        if normalized in self.SOURCE_LABELS:
            return normalized
        label_to_value = {label: value for value, label in self.SOURCE_LABELS.items()}
        return label_to_value.get(normalized, "auto")

    def _training_source_label(self, source: str) -> str:
        return self.TRAINING_SOURCE_LABELS.get(source, source)

    def _training_source_value(self, raw_source: str) -> str:
        normalized = raw_source.strip()
        if normalized in self.TRAINING_SOURCE_LABELS:
            return normalized
        label_to_value = {
            label: value for value, label in self.TRAINING_SOURCE_LABELS.items()
        }
        return label_to_value.get(normalized, "human_demo")

    def start_training(self) -> None:
        if self.training_controller.is_running:
            self._append_log(UI_TEXT["logs"]["training_already_running"])
            return

        dataset_path = self._resolve_user_path(
            self.training_dataset_var.get().strip() or "logs/human_demos"
        )
        output_path = self._resolve_user_path(
            self.training_output_var.get().strip() or "models/human_policy.pt"
        )
        try:
            epochs = int(self.training_epochs_var.get().strip() or "20")
        except ValueError:
            self._append_log(UI_TEXT["logs"]["epochs_integer"])
            return
        if epochs <= 0:
            self._append_log(UI_TEXT["logs"]["epochs_positive"])
            return

        config = TrainingLaunchConfig(
            dataset_path=dataset_path,
            output_path=output_path,
            epochs=epochs,
            repo_root=self.repo_root,
            source=self._training_source_value(self.training_source_var.get()),
        )
        validation_error = validate_training_config(config)
        if validation_error is not None:
            self._append_log(validation_error)
            self.training_status_var.set(UI_TEXT["status"]["idle"])
            return
        try:
            self.training_controller.start(config)
        except Exception as exc:
            self._append_log(f"{UI_TEXT['logs']['training_start_failed']}: {exc}")
            self.training_status_var.set(UI_TEXT["status"]["idle"])
        else:
            self._last_training_output_path = output_path
            self._training_completion_reported = False
            self.training_status_var.set(UI_TEXT["status"]["running"])

    def stop_training(self) -> None:
        self.training_controller.stop()
        self.training_status_var.set(UI_TEXT["status"]["idle"])

    def _resolve_user_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.repo_root / path

    def stop_runtime(self) -> None:
        self.controller.stop()
        self.status_var.set(UI_TEXT["status"]["stopped"])

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", self.tk.END)
        self.log_text.configure(state="disabled")

    def _schedule_poll(self) -> None:
        self._drain_log_queue()
        self._refresh_minimap_preview()
        if self.controller.poll_exit() is not None and not self.controller.is_running:
            self.status_var.set(UI_TEXT["status"]["stopped"])
        self._update_training_completion_state()
        self.root.after(200, self._schedule_poll)

    def _update_training_completion_state(self) -> None:
        exit_code = self.training_controller.poll_exit()
        if exit_code is None or self.training_controller.is_running:
            return
        self.training_status_var.set(UI_TEXT["status"]["idle"])
        if self._training_completion_reported:
            return
        self._training_completion_reported = True
        output_path = self._last_training_output_path
        if exit_code != 0:
            if output_path is not None:
                self._append_training_report_summary(output_path)
            return
        if output_path is None:
            return
        self._append_training_report_summary(output_path)

    def _append_training_report_summary(self, output_path: Path) -> None:
        report_path = default_training_report_path(output_path)
        if not report_path.exists():
            self._append_log(f"{UI_TEXT['logs']['training_report_missing']}: {report_path}")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._append_log(f"{UI_TEXT['logs']['training_report_read_failed']}: {exc}")
            return
        if not isinstance(report, Mapping):
            self._append_log(f"{UI_TEXT['logs']['training_report_read_failed']}: {report_path}")
            return
        for line in build_training_report_summary(report):
            self._append_log(line)

    def _refresh_minimap_preview(self) -> None:
        label = getattr(self, "minimap_preview_label", None)
        if label is None or not self.minimap_preview_enabled_var.get():
            return

        path = Path(self.minimap_preview_path_var.get().strip())
        if not path.is_absolute():
            path = self.repo_root / path
        if not path.exists():
            return

        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if mtime <= self._minimap_preview_mtime:
            return

        try:
            from PIL import Image, ImageTk

            image = Image.open(path)
            image.thumbnail((300, 300))
            self._minimap_photo = ImageTk.PhotoImage(image)
            label.configure(image=self._minimap_photo, text="")
            self._minimap_preview_mtime = mtime
        except Exception as exc:
            label.configure(text=f"小地图画面读取失败: {exc}", image="")

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(message)

    def _append_log(self, message: str) -> None:
        if not message:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert(self.tk.END, message + "\n")
        self.log_text.see(self.tk.END)
        self.log_text.configure(state="disabled")


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run the GUI launcher."""
    import tkinter as tk

    _ = argv
    root = tk.Tk()
    GuiLauncherApp(root)
    root.mainloop()
    return 0


__all__ = [
    "AdbDeviceSummary",
    "GuiLauncherApp",
    "GuiDefaultSettings",
    "RuntimeLaunchConfig",
    "RuntimeProcessController",
    "TrainingLaunchConfig",
    "TrainingProcessController",
    "UI_TEXT",
    "build_gui_default_settings",
    "build_runtime_command",
    "build_runtime_environment",
    "build_training_command",
    "build_training_environment",
    "build_training_report_summary",
    "default_training_report_path",
    "validate_policy_runtime_report",
    "choose_default_device",
    "is_local_tcp_serial",
    "main",
    "parse_adb_devices",
    "resolve_training_source_for_paths",
    "resolve_runtime_mode",
    "run_adb_devices",
    "training_source_display_name",
    "validate_training_config",
]
