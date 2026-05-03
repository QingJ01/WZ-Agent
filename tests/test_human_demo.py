"""Tests for human demonstration capture."""

from __future__ import annotations

import json
import threading

from wzry_ai.learning.human_demo import (
    AdbGeteventParser,
    AdbTouchDemoSource,
    HumanAction,
    HumanActionMapper,
    HumanDemoRecorder,
    HumanDemoRuntime,
    WindowsKeyboardDemoSource,
    build_human_demo_runtime_from_env,
    parse_getevent_touch_raw_size,
)


def test_touch_mapper_maps_skill_buttons():
    mapper = HumanActionMapper(width=2400, height=1080)

    assert mapper.map_tap(1812, 934).action == "cast_q"
    assert mapper.map_tap(2136, 675).action == "attach_teammate"
    assert mapper.map_tap(1548, 832).action == "cast_active_item"


def test_touch_mapper_maps_joystick_direction():
    mapper = HumanActionMapper(width=2400, height=1080)

    action = mapper.map_touch_hold(520, 760)

    assert action.action == "move"
    assert action.payload["direction"] in {"up_right", "right"}
    assert action.payload["dx"] > 0


def test_keyboard_mapper_maps_mumu_keys():
    mapper = HumanActionMapper(width=2400, height=1080)

    assert mapper.map_key_snapshot({"w", "d"}).payload["direction"] == "up_right"
    assert mapper.map_key_snapshot({"q"}).action == "cast_q"
    assert mapper.map_key_snapshot({"4"}).action == "buy_item"


def test_keyboard_mapper_uses_runtime_level_key_mapping():
    mapper = HumanActionMapper(width=2400, height=1080)

    assert mapper.map_key_snapshot({"1"}).action == "level_1"
    assert mapper.map_key_snapshot({"2"}).action == "level_2"
    assert mapper.map_key_snapshot({"3"}).action == "level_ult"


def test_adb_getevent_parser_extracts_touch_coordinates():
    parser = AdbGeteventParser(width=2400, height=1080)
    events = [
        "0003 0035 00000208",
        "0003 0036 000002f8",
        "0001 014a 00000001",
        "0000 0000 00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "move"
    assert actions[-1].payload["direction"] in {"up_right", "right"}


def test_adb_getevent_parser_maps_release_near_skill_to_tap():
    parser = AdbGeteventParser(width=2400, height=1080)
    events = [
        "0003 0035 00000714",
        "0003 0036 000003a6",
        "0001 014a 00000001",
        "0000 0000 00000000",
        "0001 014a 00000000",
        "0000 0000 00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "cast_q"


def test_adb_getevent_parser_maps_tracking_id_release_to_tap():
    parser = AdbGeteventParser(width=2400, height=1080)
    events = [
        "/dev/input/event3: 0003 002f 00000000",
        "/dev/input/event3: 0003 0039 00000027",
        "/dev/input/event3: 0003 0035 00000714",
        "/dev/input/event3: 0003 0036 000003a6",
        "/dev/input/event3: 0000 0000 00000000",
        "/dev/input/event3: 0003 002f 00000000",
        "/dev/input/event3: 0003 0039 ffffffff",
        "/dev/input/event3: 0000 0000 00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "cast_q"


def test_adb_getevent_parser_maps_labeled_getevent_output():
    parser = AdbGeteventParser(width=2400, height=1080)
    events = [
        "[  470892.815890] EV_ABS       ABS_MT_SLOT          00000000",
        "[  470892.815890] EV_ABS       ABS_MT_TRACKING_ID   0000ee72",
        "[  470892.815890] EV_ABS       ABS_MT_POSITION_X    00000714",
        "[  470892.815890] EV_ABS       ABS_MT_POSITION_Y    000003a6",
        "[  470892.815890] EV_SYN       SYN_REPORT           00000000",
        "[  470892.915890] EV_ABS       ABS_MT_SLOT          00000000",
        "[  470892.915890] EV_ABS       ABS_MT_TRACKING_ID   ffffffff",
        "[  470892.915890] EV_SYN       SYN_REPORT           00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "cast_q"


def test_adb_getevent_parser_scales_raw_touch_coordinates():
    parser = AdbGeteventParser(
        width=2400,
        height=1080,
        raw_width=1080,
        raw_height=2400,
        raw_transform="rotate_cw",
    )
    events = [
        "0003 0035 00000092",
        "0003 0036 00000714",
        "0001 014a 00000001",
        "0000 0000 00000000",
        "0001 014a 00000000",
        "0000 0000 00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "cast_q"


def test_adb_getevent_parser_scales_vivo_landscape_identity_coordinates():
    parser = AdbGeteventParser(
        width=2400,
        height=1080,
        raw_width=10800,
        raw_height=24000,
        raw_transform="identity",
    )
    events = [
        f"0003 0035 {8663:08x}",
        f"0003 0036 {20613:08x}",
        "0001 014a 00000001",
        "0000 0000 00000000",
        "0001 014a 00000000",
        "0000 0000 00000000",
    ]

    actions = [action for line in events for action in parser.feed_line(line)]

    assert actions[-1].action == "cast_q"


def test_parse_getevent_touch_raw_size_from_capabilities():
    output = """
add device 1: /dev/input/event3
  name:     "vivo_ts"
  events:
    ABS (0003):
      ABS_MT_POSITION_X    : value 0, min 0, max 10799, fuzz 0, flat 0, resolution 0
      ABS_MT_POSITION_Y    : value 0, min 0, max 23999, fuzz 0, flat 0, resolution 0
"""

    assert parse_getevent_touch_raw_size(output) == (10800, 24000)


def test_human_demo_runtime_auto_detects_adb_raw_touch_size(monkeypatch):
    monkeypatch.setenv("WZRY_HUMAN_DEMO_ENABLED", "1")
    monkeypatch.setenv("WZRY_HUMAN_DEMO_SOURCE", "adb_touch")
    monkeypatch.setenv("WZRY_TOUCH_SIZE", "2400x1080")
    monkeypatch.delenv("WZRY_TOUCH_RAW_SIZE", raising=False)
    monkeypatch.setenv("WZRY_TOUCH_RAW_TRANSFORM", "rotate_cw")
    monkeypatch.setenv("WZRY_ADB_PATH", "adb")
    monkeypatch.setenv("WZRY_ADB_DEVICE", "phone-1")
    monkeypatch.setattr(
        "wzry_ai.learning.human_demo.detect_adb_touch_raw_size",
        lambda adb_path, device_serial: (10800, 24000),
    )

    runtime = build_human_demo_runtime_from_env()

    assert runtime is not None
    assert isinstance(runtime.source, AdbTouchDemoSource)
    assert runtime.source.parser.raw_width == 10800
    assert runtime.source.parser.raw_height == 24000
    assert runtime.source.parser.raw_transform == "rotate_cw"
    assert runtime.recorder.metadata["touch_size"] == [2400, 1080]
    assert runtime.recorder.metadata["raw_touch_size"] == [10800, 24000]


def test_human_demo_runtime_treats_large_touch_size_as_raw_size(monkeypatch):
    monkeypatch.setenv("WZRY_HUMAN_DEMO_ENABLED", "1")
    monkeypatch.setenv("WZRY_HUMAN_DEMO_SOURCE", "adb_touch")
    monkeypatch.setenv("WZRY_TOUCH_SIZE", "10800x24000")
    monkeypatch.delenv("WZRY_TOUCH_RAW_SIZE", raising=False)
    monkeypatch.setenv("WZRY_TOUCH_RAW_TRANSFORM", "identity")
    monkeypatch.setenv("WZRY_ADB_PATH", "adb")
    monkeypatch.setenv("WZRY_ADB_DEVICE", "phone-1")
    monkeypatch.setattr(
        "wzry_ai.learning.human_demo.detect_adb_touch_raw_size",
        lambda adb_path, device_serial: None,
    )

    runtime = build_human_demo_runtime_from_env()

    assert runtime is not None
    assert isinstance(runtime.source, AdbTouchDemoSource)
    assert runtime.source.parser.width == 2400
    assert runtime.source.parser.height == 1080
    assert runtime.source.parser.raw_width == 10800
    assert runtime.source.parser.raw_height == 24000
    assert runtime.source.parser.mapper.map_tap(1925, 928).action == "cast_q"
    assert runtime.recorder.metadata["touch_size"] == [2400, 1080]
    assert runtime.recorder.metadata["raw_touch_size"] == [10800, 24000]


def test_adb_touch_demo_source_builds_serial_command():
    source = AdbTouchDemoSource(adb_path=r"C:\adb\adb.exe", device_serial="phone-1")

    assert source.build_command() == [
        r"C:\adb\adb.exe",
        "-s",
        "phone-1",
        "shell",
        "getevent",
        "-lt",
    ]


def test_windows_keyboard_source_snapshot_uses_injected_reader():
    source = WindowsKeyboardDemoSource(key_state_reader=lambda key: key in {"W", "Q"})

    assert source.read_pressed_keys() == {"w", "q"}


def test_demo_recorder_writes_human_action(tmp_path):
    recorder = HumanDemoRecorder(
        base_dir=tmp_path,
        enabled=True,
        session_id="s1",
        metadata={"touch_size": [2400, 1080]},
    )
    recorder.record_demo(
        state={"self_health": 100},
        human_action=HumanAction("cast_q", "windows_keyboard", 1.0, {}),
    )

    event = json.loads(next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8"))

    assert event["schema_version"] == 2
    assert event["session_id"] == "s1"
    assert event["metadata"]["touch_size"] == [2400, 1080]
    assert event["human_action"]["action"] == "cast_q"
    assert event["state"]["self_health"] == 100


def test_human_demo_runtime_consumes_latest_action():
    recorder = HumanDemoRecorder(enabled=False)
    runtime = HumanDemoRuntime(source=None, recorder=recorder)
    runtime.publish_action(HumanAction("cast_e", "test", 10.0, {}))

    action = runtime.consume_latest_action(now=10.1, max_age=0.5)

    assert action is not None
    assert action.action == "cast_e"
    assert runtime.consume_latest_action(now=10.2, max_age=0.5) is None


def test_human_demo_runtime_ignores_stale_action():
    recorder = HumanDemoRecorder(enabled=False)
    runtime = HumanDemoRuntime(source=None, recorder=recorder)
    runtime.publish_action(HumanAction("cast_e", "test", 10.0, {}))

    assert runtime.consume_latest_action(now=11.0, max_age=0.5) is None


def test_human_demo_runtime_records_state_action(tmp_path):
    recorder = HumanDemoRecorder(base_dir=tmp_path, enabled=True, session_id="runtime")
    runtime = HumanDemoRuntime(source=None, recorder=recorder)
    runtime.record_state_action(
        {"battle_state": "fight"},
        HumanAction("attach_teammate", "test", 1.0, {}),
    )

    event = json.loads(next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8"))

    assert event["state"]["battle_state"] == "fight"
    assert event["human_action"]["action"] == "attach_teammate"


def test_human_demo_runtime_start_stop_with_empty_source():
    class EmptySource:
        def __init__(self):
            self.stopped = False

        def iter_actions(self, stop_event: threading.Event):
            assert isinstance(stop_event, threading.Event)
            if False:
                yield None

        def close(self):
            self.stopped = True

    source = EmptySource()
    runtime = HumanDemoRuntime(source=source, recorder=HumanDemoRecorder(enabled=False))

    runtime.start()
    runtime.stop()

    assert source.stopped is True
