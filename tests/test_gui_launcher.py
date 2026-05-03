"""Tests for the Tkinter GUI launcher helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import wzry_ai.app.gui_launcher as gui_launcher
from wzry_ai.app.gui_launcher import (
    GuiLauncherApp,
    RuntimeLaunchConfig,
    RuntimeProcessController,
    TrainingLaunchConfig,
    TrainingProcessController,
    build_training_report_summary,
    build_gui_default_settings,
    build_runtime_command,
    build_runtime_environment,
    build_training_command,
    build_training_environment,
    choose_default_device,
    parse_adb_devices,
    resolve_runtime_mode,
    validate_runtime_config,
    validate_training_config,
)


def test_gui_text_is_chinese():
    assert gui_launcher.UI_TEXT["title"] == "WZ-Agent 控制台"
    assert gui_launcher.UI_TEXT["tabs"]["runtime"] == "设备连接与运行"
    assert gui_launcher.UI_TEXT["buttons"]["start_runtime"] == "启动运行"
    assert gui_launcher.UI_TEXT["buttons"]["start_training"] == "开始训练策略模型"
    assert gui_launcher.UI_TEXT["labels"]["human_policy"] == "模仿学习策略权重"
    assert (
        gui_launcher.UI_TEXT["labels"]["human_policy_confidence"]
        == "策略接管置信度阈值"
    )


def test_gui_mode_and_record_source_labels_are_technical_chinese():
    app = object.__new__(GuiLauncherApp)

    assert app._mode_label("android") == "真机 ADB"
    assert app._mode_value("真机 ADB") == "android"
    assert app._source_label("windows_keyboard") == "Windows 键鼠采集"
    assert app._source_value("Windows 键鼠采集") == "windows_keyboard"


def test_gui_defaults_target_self_training_when_no_data_exists(tmp_path):
    defaults = build_gui_default_settings(tmp_path, env={})

    assert defaults.decision_recording_enabled is True
    assert defaults.training_source == "self_decision"
    assert defaults.training_dataset == "logs/decision_records"
    assert defaults.training_output == "models/self_policy.pt"
    assert defaults.human_policy_path == str(tmp_path / "models" / "self_policy.pt")
    assert defaults.human_policy_enabled is False


def test_gui_defaults_use_existing_human_demo_when_no_self_records(tmp_path):
    demo_dir = tmp_path / "logs" / "human_demos"
    demo_dir.mkdir(parents=True)
    (demo_dir / "demo.jsonl").write_text(
        '{"schema_version": 2, "human_action": {"action": "cast_q"}}\n',
        encoding="utf-8",
    )

    defaults = build_gui_default_settings(tmp_path, env={})

    assert defaults.training_source == "human_demo"
    assert defaults.training_dataset == "logs/human_demos"
    assert defaults.training_output == "models/human_policy.pt"


def test_gui_defaults_treat_stop_human_demo_as_trainable(tmp_path):
    demo_dir = tmp_path / "logs" / "human_demos"
    demo_dir.mkdir(parents=True)
    (demo_dir / "demo.jsonl").write_text(
        '{"schema_version": 2, "human_action": {"action": "stop"}}\n',
        encoding="utf-8",
    )

    defaults = build_gui_default_settings(tmp_path, env={})

    assert defaults.training_source == "human_demo"
    assert defaults.training_dataset == "logs/human_demos"


def test_gui_defaults_ignore_empty_or_invalid_jsonl_records(tmp_path):
    decision_dir = tmp_path / "logs" / "decision_records"
    demo_dir = tmp_path / "logs" / "human_demos"
    decision_dir.mkdir(parents=True)
    demo_dir.mkdir(parents=True)
    (decision_dir / "empty.jsonl").write_text("", encoding="utf-8")
    (demo_dir / "invalid.jsonl").write_text("{}\nnot-json\n", encoding="utf-8")

    defaults = build_gui_default_settings(tmp_path, env={})

    assert defaults.training_source == "self_decision"
    assert defaults.training_dataset == "logs/decision_records"


def test_gui_defaults_use_valid_self_decision_records(tmp_path):
    decision_dir = tmp_path / "logs" / "decision_records"
    decision_dir.mkdir(parents=True)
    (decision_dir / "decisions.jsonl").write_text(
        '{"schema_version": 1, "executed_action": {"action": "cast_q"}, "action_source": "rule"}\n',
        encoding="utf-8",
    )

    defaults = build_gui_default_settings(tmp_path, env={})

    assert defaults.training_source == "self_decision"


def test_gui_defaults_prefer_existing_self_policy_weight(tmp_path):
    model_path = tmp_path / "models" / "self_policy.pt"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"placeholder")

    defaults = build_gui_default_settings(tmp_path, env={"WZRY_HUMAN_POLICY_ENABLED": "1"})

    assert defaults.human_policy_path == str(model_path)
    assert defaults.human_policy_enabled is True


def test_parse_adb_devices_returns_connected_devices_only():
    output = """List of devices attached
DEVICE1234567890        device product:PD2238 model:V2238A device:PD2238 transport_id:10
offline-1              offline product:x model:y device:z
"""

    devices = parse_adb_devices(output)

    assert len(devices) == 1
    assert devices[0].serial == "DEVICE1234567890"
    assert devices[0].state == "device"
    assert devices[0].model == "V2238A"
    assert devices[0].display_name == "DEVICE1234567890 (V2238A)"


def test_build_runtime_environment_sets_device_variables(tmp_path):
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path=r"C:\Tools\adb.exe",
        adb_serial="DEVICE1234567890",
        repo_root=tmp_path,
        human_demo_enabled=True,
        human_demo_source="adb_touch",
        human_demo_dir=str(tmp_path / "demos"),
        touch_size="2400x1080",
        touch_raw_size="1080x2400",
        touch_raw_transform="rotate_cw",
        debug_windows_enabled=False,
        minimap_preview_enabled=True,
        minimap_preview_path=str(tmp_path / "preview" / "minimap.png"),
        ai_control_enabled=True,
        decision_recording_enabled=True,
        decision_record_dir=str(tmp_path / "decision_records"),
        model1_weights=str(tmp_path / "models" / "m1.pt"),
        model2_weights=str(tmp_path / "models" / "m2.pt"),
        model3_weights=str(tmp_path / "models" / "m3.pt"),
        human_policy_enabled=True,
        human_policy_path=str(tmp_path / "models" / "human_policy.pt"),
        human_policy_confidence="0.81",
    )

    env = build_runtime_environment(config, base_env={"PATH": "base"})

    assert env["WZRY_DEVICE_MODE"] == "android"
    assert env["WZRY_ADB_PATH"] == r"C:\Tools\adb.exe"
    assert env["WZRY_ADB_DEVICE"] == "DEVICE1234567890"
    assert env["WZRY_HUMAN_DEMO_ENABLED"] == "1"
    assert env["WZRY_HUMAN_DEMO_SOURCE"] == "adb_touch"
    assert env["WZRY_HUMAN_DEMO_DIR"] == str(tmp_path / "demos")
    assert env["WZRY_TOUCH_SIZE"] == "2400x1080"
    assert env["WZRY_TOUCH_RAW_SIZE"] == "1080x2400"
    assert env["WZRY_TOUCH_RAW_TRANSFORM"] == "rotate_cw"
    assert env["WZRY_DEBUG_WINDOWS"] == "0"
    assert env["WZRY_GUI_MINIMAP_PREVIEW"] == "1"
    assert env["WZRY_GUI_MINIMAP_PATH"] == str(tmp_path / "preview" / "minimap.png")
    assert env["WZRY_AI_CONTROL_ENABLED"] == "1"
    assert env["WZRY_DECISION_RECORDING"] == "1"
    assert env["WZRY_DECISION_RECORD_DIR"] == str(tmp_path / "decision_records")
    assert env["WZRY_MODEL1_WEIGHTS"] == str(tmp_path / "models" / "m1.pt")
    assert env["WZRY_MODEL2_WEIGHTS"] == str(tmp_path / "models" / "m2.pt")
    assert env["WZRY_MODEL3_WEIGHTS"] == str(tmp_path / "models" / "m3.pt")
    assert env["WZRY_HUMAN_POLICY_ENABLED"] == "1"
    assert env["WZRY_HUMAN_POLICY_PATH"] == str(tmp_path / "models" / "human_policy.pt")
    assert env["WZRY_HUMAN_POLICY_CONFIDENCE"] == "0.81"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONPATH"] == str(tmp_path / "src")


def test_build_runtime_environment_disables_human_demo_by_default(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
    )

    env = build_runtime_environment(config, base_env={"PATH": "base"})

    assert env["WZRY_HUMAN_DEMO_ENABLED"] == "0"
    assert env["WZRY_HUMAN_DEMO_SOURCE"] == "windows_keyboard"
    assert env["WZRY_DEBUG_WINDOWS"] == "0"
    assert env["WZRY_GUI_MINIMAP_PREVIEW"] == "1"
    assert env["WZRY_GUI_MINIMAP_PATH"] == str(tmp_path / "logs" / "gui_preview" / "minimap.png")
    assert env["WZRY_AI_CONTROL_ENABLED"] == "0"
    assert env["WZRY_DECISION_RECORDING"] == "0"
    assert env["WZRY_DECISION_RECORD_DIR"] == str(tmp_path / "logs" / "decision_records")
    assert env["WZRY_FRAME_SOURCE"] == "scrcpy"
    assert env["WZRY_SCRCPY_FIRST_FRAME_TIMEOUT"] == "10.0"


def test_build_runtime_environment_allows_auto_frame_source(tmp_path):
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path="adb",
        adb_serial="DEVICE1234567890",
        repo_root=tmp_path,
        frame_source_mode="auto",
        scrcpy_first_frame_timeout="7.5",
    )

    env = build_runtime_environment(config, base_env={"PATH": "base"})

    assert env["WZRY_FRAME_SOURCE"] == "auto"
    assert env["WZRY_SCRCPY_FIRST_FRAME_TIMEOUT"] == "7.5"


def test_validate_runtime_config_rejects_missing_detection_model(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
        model1_weights=str(tmp_path / "models" / "missing.pt"),
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "missing.pt" in error


def test_validate_runtime_config_rejects_missing_enabled_human_policy(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
        human_policy_enabled=True,
        human_policy_path="models/human_policy.pt",
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "human_policy.pt" in error


def test_validate_runtime_config_allows_disabled_missing_human_policy(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
        human_policy_enabled=False,
        human_policy_path="models/human_policy.pt",
    )

    assert validate_runtime_config(config) is None


def test_validate_runtime_config_rejects_invalid_human_policy_confidence(tmp_path):
    policy_path = tmp_path / "models" / "human_policy.pt"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_bytes(b"placeholder")
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
        human_policy_enabled=True,
        human_policy_path=str(policy_path),
        human_policy_confidence="1.5",
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "0" in error and "1" in error


def test_validate_runtime_config_rejects_invalid_scrcpy_timeout(tmp_path):
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path="adb",
        adb_serial="phone-1",
        repo_root=tmp_path,
        scrcpy_first_frame_timeout="bad",
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "scrcpy" in error


def test_validate_runtime_config_rejects_policy_with_bad_coordinate_report(tmp_path):
    policy_path = tmp_path / "models" / "human_policy.pt"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_bytes(b"placeholder")
    (policy_path.parent / "human_policy_report.json").write_text(
        json.dumps(
            {
                "sample_count": 10,
                "action_counts": {"cast_q": 10},
                "data_quality": {
                    "coordinate_sample_count": 10,
                    "coordinate_out_of_bounds_count": 8,
                },
            }
        ),
        encoding="utf-8",
    )
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path="adb",
        adb_serial="phone-1",
        repo_root=tmp_path,
        human_policy_enabled=True,
        human_policy_path=str(policy_path),
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "触摸坐标越界" in error


def test_validate_runtime_config_rejects_policy_with_too_few_runtime_actions(tmp_path):
    policy_path = tmp_path / "models" / "human_policy.pt"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_bytes(b"placeholder")
    (policy_path.parent / "human_policy_report.json").write_text(
        json.dumps(
            {
                "sample_count": 151,
                "action_counts": {"move": 100, "touch": 50, "cast_q": 1},
            }
        ),
        encoding="utf-8",
    )
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path="adb",
        adb_serial="phone-1",
        repo_root=tmp_path,
        human_policy_enabled=True,
        human_policy_path=str(policy_path),
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "运行时可执行动作样本过少" in error


def test_validate_runtime_config_rejects_collapsed_no_op_policy(tmp_path):
    policy_path = tmp_path / "models" / "self_policy.pt"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_bytes(b"placeholder")
    (policy_path.parent / "self_policy_report.json").write_text(
        json.dumps(
            {
                "sample_count": 100,
                "action_counts": {"no_op": 96, "cast_q": 4},
                "validation": {
                    "enabled": True,
                    "confusion_matrix": {
                        "cast_q": {"no_op": 4},
                        "no_op": {"no_op": 20},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config = RuntimeLaunchConfig(
        mode="android",
        adb_path="adb",
        adb_serial="phone-1",
        repo_root=tmp_path,
        human_policy_enabled=True,
        human_policy_path=str(policy_path),
    )

    error = validate_runtime_config(config)

    assert error is not None
    assert "no_op 占比过高" in error


def test_build_runtime_environment_resolves_auto_phone_serial_to_android(tmp_path):
    config = RuntimeLaunchConfig(
        mode="auto",
        adb_path=r"C:\Tools\adb.exe",
        adb_serial="DEVICE1234567890",
        repo_root=tmp_path,
    )

    env = build_runtime_environment(config, base_env={"PATH": "base"})

    assert env["WZRY_DEVICE_MODE"] == "android"
    assert env["WZRY_ADB_DEVICE"] == "DEVICE1234567890"


def test_resolve_runtime_mode_keeps_auto_for_blank_serial():
    assert resolve_runtime_mode("auto", "") == "auto"


def test_choose_default_device_replaces_local_default_with_detected_phone():
    phone = parse_adb_devices(
        "List of devices attached\n"
        "DEVICE1234567890        device product:PD2238 model:V2238A device:PD2238 transport_id:10\n"
    )[0]

    assert choose_default_device([phone], "127.0.0.1:7555") == phone


def test_choose_default_device_preserves_connected_serial():
    devices = parse_adb_devices(
        "List of devices attached\n"
        "127.0.0.1:7555        device product:mumu model:MuMu device:mumu\n"
        "DEVICE1234567890       device product:PD2238 model:V2238A device:PD2238\n"
    )

    assert choose_default_device(devices, "127.0.0.1:7555") == devices[0]


def test_build_runtime_environment_preserves_existing_pythonpath(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
    )

    env = build_runtime_environment(config, base_env={"PYTHONPATH": "existing"})

    assert env["PYTHONPATH"] == str(tmp_path / "src") + ";" + "existing"


def test_build_runtime_command_uses_master_auto(tmp_path):
    config = RuntimeLaunchConfig(
        mode="mumu",
        adb_path="adb",
        adb_serial="127.0.0.1:7555",
        repo_root=tmp_path,
    )

    command = build_runtime_command(config, python_executable="python")

    assert command == ["python", str(tmp_path / "Master_Auto.py")]


def test_build_training_command_uses_human_policy_script(tmp_path):
    config = TrainingLaunchConfig(
        dataset_path=tmp_path / "logs" / "human_demos",
        output_path=tmp_path / "models" / "human_policy.pt",
        epochs=7,
        repo_root=tmp_path,
    )

    command = build_training_command(config, python_executable="python")

    assert command == [
        "python",
        str(tmp_path / "scripts" / "train_human_policy.py"),
        str(tmp_path / "logs" / "human_demos"),
        "--output",
        str(tmp_path / "models" / "human_policy.pt"),
        "--epochs",
        "7",
    ]


def test_build_training_command_uses_self_policy_script(tmp_path):
    config = TrainingLaunchConfig(
        dataset_path=tmp_path / "logs" / "decision_records",
        output_path=tmp_path / "models" / "self_policy.pt",
        epochs=5,
        repo_root=tmp_path,
        source="self_decision",
    )

    command = build_training_command(config, python_executable="python")

    assert command == [
        "python",
        str(tmp_path / "scripts" / "train_self_policy.py"),
        str(tmp_path / "logs" / "decision_records"),
        "--output",
        str(tmp_path / "models" / "self_policy.pt"),
        "--epochs",
        "5",
    ]


def test_build_training_command_respects_explicit_source_for_mismatched_path(tmp_path):
    config = TrainingLaunchConfig(
        dataset_path=tmp_path / "logs" / "decision_records",
        output_path=tmp_path / "models" / "self_policy.pt",
        epochs=20,
        repo_root=tmp_path,
        source="human_demo",
    )

    command = build_training_command(config, python_executable="python")

    assert command[1] == str(tmp_path / "scripts" / "train_human_policy.py")


def test_validate_training_config_rejects_human_source_with_decision_records(tmp_path):
    config = TrainingLaunchConfig(
        dataset_path=tmp_path / "logs" / "decision_records",
        output_path=tmp_path / "models" / "self_policy.pt",
        epochs=20,
        repo_root=tmp_path,
        source="human_demo",
    )

    error = validate_training_config(config)

    assert error is not None
    assert "训练数据类型和目录不匹配" in error
    assert "logs/human_demos" in error


def test_build_training_environment_preserves_pythonpath(tmp_path):
    config = TrainingLaunchConfig(
        dataset_path=tmp_path / "logs" / "human_demos",
        output_path=tmp_path / "models" / "human_policy.pt",
        epochs=3,
        repo_root=tmp_path,
    )

    env = build_training_environment(config, base_env={"PYTHONPATH": "existing"})

    assert env["PYTHONPATH"] == str(tmp_path / "src") + ";" + "existing"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"
    assert env["PYTHONUTF8"] == "1"


def test_process_controller_reports_not_running_initially():
    controller = RuntimeProcessController()

    assert controller.is_running is False


def test_process_controller_reads_runtime_output_as_utf8(monkeypatch, tmp_path):
    captured = {}

    class FakeStdout:
        def __iter__(self):
            return iter(())

    class FakeProcess:
        stdout = FakeStdout()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(gui_launcher.subprocess, "Popen", fake_popen)

    controller = RuntimeProcessController()
    controller.start(
        RuntimeLaunchConfig(
            mode="android",
            adb_path="adb",
            adb_serial="DEVICE1234567890",
            repo_root=tmp_path,
        )
    )

    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"


def test_training_controller_reads_output_as_utf8(monkeypatch, tmp_path):
    captured = {}

    class FakeStdout:
        def __iter__(self):
            return iter(())

    class FakeProcess:
        stdout = FakeStdout()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(gui_launcher.subprocess, "Popen", fake_popen)

    controller = TrainingProcessController()
    controller.start(
        TrainingLaunchConfig(
            dataset_path=tmp_path / "logs" / "human_demos",
            output_path=tmp_path / "models" / "human_policy.pt",
            epochs=2,
            repo_root=tmp_path,
        )
    )

    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"
    assert captured["kwargs"]["cwd"] == str(tmp_path)


def test_build_training_report_summary_highlights_quality_warnings():
    lines = build_training_report_summary(
        {
            "sample_count": 3136,
            "covered_action_count": 5,
            "action_counts": {"move": 2411, "touch": 722, "cast_q": 1},
            "missing_actions": ["attach_teammate", "cast_e"],
            "rare_actions": {"cast_q": 1},
            "data_quality": {
                "coordinate_sample_count": 100,
                "coordinate_out_of_bounds_count": 3,
                "coordinate_out_of_bounds_actions": {"touch": 3},
            },
            "training": {"train_accuracy": 0.768526, "epochs": 3},
            "validation": {"enabled": True, "accuracy": 0.769968, "sample_count": 626},
        }
    )

    joined = "\n".join(lines)
    assert "样本数: 3136" in joined
    assert "动作覆盖: 5/16" in joined
    assert "训练准确率: 76.85%" in joined
    assert "验证准确率: 77.00%" in joined
    assert "缺失动作" in joined
    assert "样本过少" in joined
    assert "触摸坐标越界: 3/100" in joined


def test_build_training_report_summary_shows_blocked_preflight():
    lines = build_training_report_summary(
        {
            "sample_count": 1,
            "covered_action_count": 1,
            "action_counts": {"touch": 1},
            "training": {"blocked": True, "reason": "coordinate_out_of_bounds"},
            "validation": {"enabled": False},
            "data_quality": {
                "coordinate_sample_count": 1,
                "coordinate_out_of_bounds_count": 1,
                "coordinate_out_of_bounds_actions": {"touch": 1},
            },
        }
    )

    joined = "\n".join(lines)
    assert "训练已阻止: coordinate_out_of_bounds" in joined
    assert "触摸坐标越界: 1/1" in joined


def test_build_training_report_summary_marks_unusable_policy():
    lines = build_training_report_summary(
        {
            "sample_count": 100,
            "covered_action_count": 2,
            "action_counts": {"no_op": 96, "cast_q": 4},
            "training": {"epochs": 3},
            "validation": {"enabled": False},
        }
    )

    joined = "\n".join(lines)
    assert "模型不可启用" in joined
    assert "no_op 占比过高" in joined


def test_gui_logs_training_report_once_after_process_exit(tmp_path):
    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeController:
        is_running = False

        def poll_exit(self):
            return 0

    output = tmp_path / "models" / "human_policy.pt"
    output.parent.mkdir(parents=True)
    (output.parent / "human_policy_report.json").write_text(
        json.dumps(
            {
                "sample_count": 2,
                "covered_action_count": 1,
                "action_counts": {"move": 2},
                "missing_actions": ["cast_q"],
                "rare_actions": {},
                "training": {"train_accuracy": 1.0, "epochs": 1},
                "validation": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    app = object.__new__(GuiLauncherApp)
    app.repo_root = tmp_path
    app.training_controller = FakeController()
    app.training_status_var = FakeVar()
    app._last_training_output_path = output
    app._training_completion_reported = False
    logs = []
    app._append_log = logs.append

    GuiLauncherApp._update_training_completion_state(app)
    GuiLauncherApp._update_training_completion_state(app)

    joined = "\n".join(logs)
    assert app.training_status_var.get() == gui_launcher.UI_TEXT["status"]["idle"]
    assert joined.count("训练报告") == 1
    assert "样本数: 2" in joined


def test_gui_logs_training_report_after_failed_preflight(tmp_path):
    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeController:
        is_running = False

        def poll_exit(self):
            return 1

    output = tmp_path / "models" / "human_policy.pt"
    output.parent.mkdir(parents=True)
    (output.parent / "human_policy_report.json").write_text(
        json.dumps(
            {
                "sample_count": 1,
                "covered_action_count": 1,
                "action_counts": {"touch": 1},
                "training": {"blocked": True, "reason": "coordinate_out_of_bounds"},
                "validation": {"enabled": False},
                "data_quality": {
                    "coordinate_sample_count": 1,
                    "coordinate_out_of_bounds_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    app = object.__new__(GuiLauncherApp)
    app.repo_root = tmp_path
    app.training_controller = FakeController()
    app.training_status_var = FakeVar()
    app._last_training_output_path = output
    app._training_completion_reported = False
    logs = []
    app._append_log = logs.append

    GuiLauncherApp._update_training_completion_state(app)

    joined = "\n".join(logs)
    assert "训练报告" in joined
    assert "训练已阻止" in joined


def test_start_training_blocks_mismatched_source_and_dataset(tmp_path):
    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeTrainingController:
        is_running = False

        def start(self, config):
            captured["config"] = config

    captured = {}
    logs = []
    app = object.__new__(GuiLauncherApp)
    app.repo_root = tmp_path
    app.training_controller = FakeTrainingController()
    app.training_dataset_var = FakeVar("logs/decision_records")
    app.training_output_var = FakeVar("models/self_policy.pt")
    app.training_epochs_var = FakeVar("20")
    app.training_source_var = FakeVar(app._training_source_label("human_demo"))
    app.training_status_var = FakeVar()
    app._append_log = logs.append
    app._last_training_output_path = None
    app._training_completion_reported = True

    GuiLauncherApp.start_training(app)

    assert "config" not in captured
    assert app.training_source_var.get() == app._training_source_label("human_demo")
    assert any("训练数据类型和目录不匹配" in line for line in logs)


def test_training_source_dropdown_updates_dataset_and_output(tmp_path):
    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    app = object.__new__(GuiLauncherApp)
    app.repo_root = tmp_path
    app.demo_dir_var = FakeVar("logs/human_demos")
    app.decision_record_dir_var = FakeVar("logs/decision_records")
    app.training_dataset_var = FakeVar("logs/decision_records")
    app.training_output_var = FakeVar("models/self_policy.pt")
    app.human_policy_path_var = FakeVar()
    app.training_source_var = FakeVar(app._training_source_label("human_demo"))
    logs = []
    app._append_log = logs.append

    GuiLauncherApp.on_training_source_changed(app)

    assert app.training_dataset_var.get() == "logs/human_demos"
    assert app.training_output_var.get() == "models/human_policy.pt"
    assert app.human_policy_path_var.get() == str(tmp_path / "models" / "human_policy.pt")
    assert logs

    app.training_source_var.set(app._training_source_label("self_decision"))
    GuiLauncherApp.on_training_source_changed(app)

    assert app.training_dataset_var.get() == "logs/decision_records"
    assert app.training_output_var.get() == "models/self_policy.pt"
    assert app.human_policy_path_var.get() == str(tmp_path / "models" / "self_policy.pt")


def test_learning_tab_buttons_select_training_tab_and_log_selection(tmp_path):
    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeNotebook:
        def __init__(self):
            self.selected = None

        def select(self, tab):
            self.selected = tab

    app = object.__new__(GuiLauncherApp)
    app.repo_root = tmp_path
    app.demo_dir_var = FakeVar("logs/human_demos")
    app.decision_record_dir_var = FakeVar("logs/decision_records")
    app.training_dataset_var = FakeVar()
    app.training_source_var = FakeVar()
    app.training_output_var = FakeVar()
    app.human_policy_path_var = FakeVar()
    app.training_notebook = FakeNotebook()
    app.training_tab = object()
    logs = []
    app._append_log = logs.append

    GuiLauncherApp.copy_demo_dir_to_training(app)

    assert app.training_dataset_var.get() == "logs/human_demos"
    assert app.training_source_var.get() == app._training_source_label("human_demo")
    assert app.training_output_var.get() == "models/human_policy.pt"
    assert app.training_notebook.selected is app.training_tab
    assert logs

    logs.clear()
    app.training_notebook.selected = None

    GuiLauncherApp.copy_decision_dir_to_training(app)

    assert app.training_dataset_var.get() == "logs/decision_records"
    assert app.training_source_var.get() == app._training_source_label("self_decision")
    assert app.training_output_var.get() == "models/self_policy.pt"
    assert app.training_notebook.selected is app.training_tab
    assert logs


def test_gui_entrypoints_are_importable():
    assert callable(importlib.util.find_spec("wzry_ai.app.gui_launcher").loader.exec_module)
    assert importlib.util.find_spec("scripts.gui_launcher") is not None
    assert importlib.util.find_spec("GUI") is not None
