"""Tests for Android touch input fallback."""

from __future__ import annotations

from wzry_ai.utils.keyboard_controller import (
    AndroidTouchController,
    build_android_touch_layout,
)


def test_build_android_touch_layout_uses_frame_dimensions():
    layout = build_android_touch_layout(2400, 1080)

    assert layout.joystick_center == (360, 885)
    assert layout.skill_taps["space"] == (2184, 864)
    assert layout.skill_taps["q"] == (1812, 934)
    assert layout.skill_taps["e"] == (1944, 793)
    assert layout.skill_taps["r"] == (2136, 675)
    assert layout.skill_taps["1"] == (1764, 837)
    assert layout.skill_taps["2"] == (1840, 667)
    assert layout.skill_taps["3"] == (2059, 550)
    assert layout.skill_taps["4"] == (2112, 160)


def test_android_touch_controller_taps_mapped_key():
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
    )

    controller.tap("space", duration=0)

    assert commands == [["adb", "-s", "serial", "shell", "input", "tap", "2184", "864"]]


def test_android_touch_controller_sends_swipe_for_pressed_direction(monkeypatch):
    monkeypatch.setenv("WZRY_ADB_MOVE_MODE", "swipe")
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
        auto_start=False,
    )

    controller.press("d")
    sent = controller.pump_once(duration_ms=180)

    assert sent is True
    assert commands == [
        [
            "adb",
            "-s",
            "serial",
            "shell",
            "input",
            "swipe",
            "360",
            "885",
            "468",
            "885",
            "180",
        ]
    ]


def test_android_touch_controller_uses_sustained_swipe_duration(monkeypatch):
    monkeypatch.setenv("WZRY_ADB_MOVE_MODE", "swipe")
    monkeypatch.delenv("WZRY_ADB_MOVE_SWIPE_MS", raising=False)
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
        auto_start=False,
    )

    controller.press("d")
    sent = controller.pump_once()

    assert sent is True
    assert commands[-1][-1] == "650"


def test_android_touch_controller_uses_motion_events_by_default(monkeypatch):
    monkeypatch.delenv("WZRY_ADB_MOVE_MODE", raising=False)
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
        auto_start=False,
    )

    controller.press("d")
    sent = controller.pump_once()
    controller.release("d")
    released = controller.pump_once()

    assert sent is True
    assert released is False
    assert commands == [
        ["adb", "-s", "serial", "shell", "input", "motionevent", "DOWN", "360", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "MOVE", "468", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "UP", "468", "885"],
    ]


def test_android_touch_controller_keeps_motion_touch_held(monkeypatch):
    monkeypatch.delenv("WZRY_ADB_MOVE_MODE", raising=False)
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
        auto_start=False,
    )

    controller.press("d")
    first_sent = controller.pump_once()
    still_holding = controller.pump_once()

    assert first_sent is True
    assert still_holding is True
    assert commands == [
        ["adb", "-s", "serial", "shell", "input", "motionevent", "DOWN", "360", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "MOVE", "468", "885"],
    ]


def test_android_touch_controller_resumes_motion_after_tap(monkeypatch):
    monkeypatch.delenv("WZRY_ADB_MOVE_MODE", raising=False)
    commands = []
    controller = AndroidTouchController(
        adb_path="adb",
        device_serial="serial",
        screen_size=(2400, 1080),
        command_runner=lambda command: commands.append(command),
        auto_start=False,
    )

    controller.press("d")
    controller.pump_once()
    controller.tap("q", duration=0)

    assert commands == [
        ["adb", "-s", "serial", "shell", "input", "motionevent", "DOWN", "360", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "MOVE", "468", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "UP", "468", "885"],
        ["adb", "-s", "serial", "shell", "input", "tap", "1812", "934"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "DOWN", "360", "885"],
        ["adb", "-s", "serial", "shell", "input", "motionevent", "MOVE", "468", "885"],
    ]
