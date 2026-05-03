"""Human demonstration capture for imitation-learning datasets.

The runtime keeps using the current rule policy. This module only observes
operator input and records state-action rows that can be used for training.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from math import sqrt
from typing import Any, Callable, Iterable, Optional

from wzry_ai.utils.keyboard_controller import build_android_touch_layout
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)
_CAPABILITY_MAX_RE = re.compile(r"\bmax\s+(-?\d+)\b", re.IGNORECASE)
DEFAULT_TOUCH_SIZE = (2400, 1080)
RAW_LIKE_TOUCH_THRESHOLD = 4096


ACTION_BY_KEY = {
    "q": "cast_q",
    "e": "cast_e",
    "r": "attach_teammate",
    "f": "cast_f",
    "t": "cast_active_item",
    "c": "recover",
    "space": "basic_attack",
    "b": "recall",
    "1": "level_ult",
    "2": "level_1",
    "3": "level_2",
    "4": "buy_item",
}

KEY_PRIORITY = ("q", "e", "r", "f", "t", "c", "space", "b", "1", "2", "3", "4")
MOVEMENT_KEYS = ("w", "a", "s", "d")
DEFAULT_SOURCE_KEYS = (
    "W",
    "A",
    "S",
    "D",
    "Q",
    "E",
    "R",
    "F",
    "T",
    "C",
    "SPACE",
    "B",
    "1",
    "2",
    "3",
    "4",
)
VK_CODES = {
    "W": 0x57,
    "A": 0x41,
    "S": 0x53,
    "D": 0x44,
    "Q": 0x51,
    "E": 0x45,
    "R": 0x52,
    "F": 0x46,
    "T": 0x54,
    "C": 0x43,
    "SPACE": 0x20,
    "B": 0x42,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
}


@dataclass(frozen=True)
class HumanAction:
    """A symbolic action observed from a human operator."""

    action: str
    source: str
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)


class HumanActionMapper:
    """Map raw phone touches or MuMu keyboard snapshots to symbolic actions."""

    def __init__(
        self,
        *,
        width: int = 2400,
        height: int = 1080,
        tap_radius: Optional[float] = None,
        deadzone: float = 0.2,
    ):
        self.width = width
        self.height = height
        self.layout = build_android_touch_layout(width, height)
        self.tap_radius = tap_radius or max(75.0, min(width, height) * 0.12)
        self.deadzone = deadzone

    def map_tap(
        self,
        x: int | float,
        y: int | float,
        *,
        source: str = "adb_touch",
        timestamp: Optional[float] = None,
    ) -> HumanAction:
        timestamp = time.time() if timestamp is None else timestamp
        closest_key = self._closest_skill_key(x, y)
        if closest_key is not None:
            return HumanAction(
                ACTION_BY_KEY[closest_key],
                source,
                timestamp,
                {"x": int(x), "y": int(y), "key": closest_key},
            )

        if self._distance((x, y), self.layout.joystick_center) <= self.layout.joystick_radius * 1.4:
            return self.map_touch_hold(x, y, source=source, timestamp=timestamp)

        return HumanAction("touch", source, timestamp, {"x": int(x), "y": int(y)})

    def map_touch_hold(
        self,
        x: int | float,
        y: int | float,
        *,
        source: str = "adb_touch",
        timestamp: Optional[float] = None,
    ) -> HumanAction:
        timestamp = time.time() if timestamp is None else timestamp
        cx, cy = self.layout.joystick_center
        radius = max(1.0, float(self.layout.joystick_radius))
        dx = max(-1.0, min(1.0, (float(x) - cx) / radius))
        dy = max(-1.0, min(1.0, (float(y) - cy) / radius))
        magnitude = sqrt(dx * dx + dy * dy)
        if magnitude < self.deadzone:
            direction = "center"
            action = "stop"
        else:
            direction = self._direction_from_delta(dx, dy)
            action = "move"
        return HumanAction(
            action,
            source,
            timestamp,
            {
                "x": int(x),
                "y": int(y),
                "dx": round(dx, 4),
                "dy": round(dy, 4),
                "direction": direction,
            },
        )

    def map_key_snapshot(
        self,
        keys: Iterable[str],
        *,
        source: str = "windows_keyboard",
        timestamp: Optional[float] = None,
    ) -> HumanAction:
        timestamp = time.time() if timestamp is None else timestamp
        normalized = {self._normalize_key(key) for key in keys}
        normalized.discard("")

        for key in KEY_PRIORITY:
            if key in normalized:
                return HumanAction(
                    ACTION_BY_KEY[key],
                    source,
                    timestamp,
                    {"key": key},
                )

        dx = (1 if "d" in normalized else 0) - (1 if "a" in normalized else 0)
        dy = (1 if "s" in normalized else 0) - (1 if "w" in normalized else 0)
        if dx or dy:
            return HumanAction(
                "move",
                source,
                timestamp,
                {
                    "keys": sorted(normalized),
                    "dx": float(dx),
                    "dy": float(dy),
                    "direction": self._direction_from_delta(dx, dy),
                },
            )

        return HumanAction("no_op", source, timestamp, {})

    def _closest_skill_key(self, x: int | float, y: int | float) -> str | None:
        best_key = None
        best_distance = float("inf")
        for key, pos in self.layout.skill_taps.items():
            distance = self._distance((x, y), pos)
            if distance < best_distance:
                best_key = key
                best_distance = distance
        if best_key is not None and best_distance <= self.tap_radius:
            return best_key
        return None

    def _direction_from_delta(self, dx: int | float, dy: int | float) -> str:
        horizontal = ""
        vertical = ""
        if dx > self.deadzone:
            horizontal = "right"
        elif dx < -self.deadzone:
            horizontal = "left"

        if dy > self.deadzone:
            vertical = "down"
        elif dy < -self.deadzone:
            vertical = "up"

        if vertical and horizontal:
            return f"{vertical}_{horizontal}"
        return vertical or horizontal or "center"

    @staticmethod
    def _distance(a: tuple[int | float, int | float], b: tuple[int, int]) -> float:
        return sqrt((float(a[0]) - b[0]) ** 2 + (float(a[1]) - b[1]) ** 2)

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = str(key).strip().lower()
        if normalized in {" ", "spacebar"}:
            return "space"
        return normalized


class AdbGeteventParser:
    """Parse ``adb shell getevent -lt`` touch events into human actions."""

    _HEX_RE = re.compile(r"\b[0-9a-fA-F]{4,8}\b")
    _EVENT_TYPE_BY_LABEL = {
        "EV_SYN": "0000",
        "EV_KEY": "0001",
        "EV_ABS": "0003",
    }
    _EVENT_CODE_BY_LABEL = {
        "SYN_REPORT": "0000",
        "BTN_TOUCH": "014a",
        "ABS_X": "0000",
        "ABS_Y": "0001",
        "ABS_MT_SLOT": "002f",
        "ABS_MT_TRACKING_ID": "0039",
        "ABS_MT_POSITION_X": "0035",
        "ABS_MT_POSITION_Y": "0036",
    }

    def __init__(
        self,
        *,
        width: int = 2400,
        height: int = 1080,
        raw_width: Optional[int] = None,
        raw_height: Optional[int] = None,
        raw_transform: str = "identity",
        mapper: Optional[HumanActionMapper] = None,
    ):
        self.width = width
        self.height = height
        self.raw_width = raw_width
        self.raw_height = raw_height
        self.raw_transform = raw_transform.strip().lower()
        self.mapper = mapper or HumanActionMapper(width=width, height=height)
        self.x: int | None = None
        self.y: int | None = None
        self.last_x: int | None = None
        self.last_y: int | None = None
        self.touching = False
        self.pending_release = False

    def feed_line(self, line: str) -> list[HumanAction]:
        fields = self._event_fields(line)
        if fields is None:
            return []

        event_type, code, value = fields
        actions: list[HumanAction] = []
        if event_type == "0003" and code in {"0035", "0000"}:
            self.x = self._hex_to_int(value)
            self.last_x = self.x
        elif event_type == "0003" and code in {"0036", "0001"}:
            self.y = self._hex_to_int(value)
            self.last_y = self.y
        elif event_type == "0003" and code == "0039":
            tracking_id = self._hex_to_int(value)
            if tracking_id < 0:
                self.touching = False
                self.pending_release = True
            else:
                self.touching = True
                self.pending_release = False
        elif event_type == "0001" and code == "014a":
            pressed = self._hex_to_int(value) != 0
            self.touching = pressed
            self.pending_release = not pressed
        elif event_type == "0000" and code == "0000":
            if self.pending_release:
                if self.last_x is not None and self.last_y is not None:
                    screen_x, screen_y = self._screen_point(self.last_x, self.last_y)
                    actions.append(
                        self.mapper.map_tap(
                            screen_x,
                            screen_y,
                            source="adb_touch",
                        )
                    )
                self.pending_release = False
                self.x = None
                self.y = None
            elif self.touching and self.x is not None and self.y is not None:
                screen_x, screen_y = self._screen_point(self.x, self.y)
                actions.append(
                    self.mapper.map_touch_hold(
                        screen_x,
                        screen_y,
                        source="adb_touch",
                    )
                )
        return actions

    def _event_fields(self, line: str) -> tuple[str, str, str] | None:
        symbolic_fields = self._symbolic_event_fields(line)
        if symbolic_fields is not None:
            return symbolic_fields

        tokens = self._HEX_RE.findall(line)
        if len(tokens) < 3:
            return None
        event_type, code, value = tokens[-3:]
        return event_type.lower(), code.lower(), value.lower()

    def _symbolic_event_fields(self, line: str) -> tuple[str, str, str] | None:
        parts = line.replace(":", " ").split()
        event_type = None
        code = None
        for part in parts:
            if event_type is None and part in self._EVENT_TYPE_BY_LABEL:
                event_type = self._EVENT_TYPE_BY_LABEL[part]
                continue
            if part in self._EVENT_CODE_BY_LABEL:
                code = self._EVENT_CODE_BY_LABEL[part]

        if event_type is None or code is None:
            return None
        value = None
        for part in reversed(parts):
            if self._HEX_RE.fullmatch(part):
                value = part
                break
        if value is None:
            return None
        return event_type, code, value.lower()

    @staticmethod
    def _hex_to_int(value: str) -> int:
        parsed = int(value, 16)
        if parsed >= 0x80000000:
            parsed -= 0x100000000
        return parsed

    def _screen_point(self, raw_x: int, raw_y: int) -> tuple[int, int]:
        if not self.raw_width or not self.raw_height:
            return raw_x, raw_y

        raw_width = max(1, self.raw_width)
        raw_height = max(1, self.raw_height)
        x_ratio = max(0.0, min(1.0, raw_x / raw_width))
        y_ratio = max(0.0, min(1.0, raw_y / raw_height))

        if self.raw_transform == "rotate_cw":
            screen_x = y_ratio * self.width
            screen_y = (1.0 - x_ratio) * self.height
        elif self.raw_transform == "rotate_ccw":
            screen_x = (1.0 - y_ratio) * self.width
            screen_y = x_ratio * self.height
        elif self.raw_transform == "flip_180":
            screen_x = (1.0 - x_ratio) * self.width
            screen_y = (1.0 - y_ratio) * self.height
        else:
            screen_x = x_ratio * self.width
            screen_y = y_ratio * self.height
        return int(round(screen_x)), int(round(screen_y))


class AdbTouchDemoSource:
    """ADB source that observes physical Android touch events."""

    def __init__(
        self,
        *,
        adb_path: str = "adb",
        device_serial: str = "",
        parser: Optional[AdbGeteventParser] = None,
    ):
        self.adb_path = adb_path
        self.device_serial = device_serial
        self.parser = parser or AdbGeteventParser()
        self._process: Optional[subprocess.Popen[str]] = None

    def build_command(self) -> list[str]:
        command = [self.adb_path]
        if self.device_serial:
            command.extend(["-s", self.device_serial])
        command.extend(["shell", "getevent", "-lt"])
        return command

    def iter_actions(self, stop_event: threading.Event):
        self._process = subprocess.Popen(
            self.build_command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=_windows_startupinfo(),
        )
        try:
            if self._process.stdout is None:
                return
            for line in self._process.stdout:
                if stop_event.is_set():
                    break
                for action in self.parser.feed_line(line):
                    yield action
        finally:
            self.close()

    def close(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def detect_adb_touch_raw_size(
    adb_path: str,
    device_serial: str = "",
) -> tuple[int, int] | None:
    command = [adb_path]
    if device_serial:
        command.extend(["-s", device_serial])
    command.extend(["shell", "getevent", "-pl"])
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            startupinfo=_windows_startupinfo(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("ADB touch raw size detection skipped: %s", exc)
        return None
    if result.returncode != 0:
        logger.debug(
            "ADB touch raw size detection failed: %s",
            (result.stderr or result.stdout or "").strip(),
        )
        return None
    detected = parse_getevent_touch_raw_size(
        (result.stdout or "") + "\n" + (result.stderr or "")
    )
    if detected is not None:
        logger.info("ADB touch raw size detected: %sx%s", detected[0], detected[1])
    return detected


def parse_getevent_touch_raw_size(output: str) -> tuple[int, int] | None:
    max_x: int | None = None
    max_y: int | None = None
    for line in output.splitlines():
        normalized = line.upper()
        value = _parse_capability_max(line)
        if value is None:
            continue
        if "ABS_MT_POSITION_X" in normalized or re.search(r"\b0035\b", normalized):
            max_x = max(value, max_x or value)
        elif "ABS_MT_POSITION_Y" in normalized or re.search(r"\b0036\b", normalized):
            max_y = max(value, max_y or value)
    if max_x is None or max_y is None:
        return None
    return max_x + 1, max_y + 1


def _parse_capability_max(line: str) -> int | None:
    match = _CAPABILITY_MAX_RE.search(line)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


class WindowsKeyboardDemoSource:
    """Windows keyboard polling source for MuMu demonstrations."""

    def __init__(
        self,
        *,
        mapper: Optional[HumanActionMapper] = None,
        key_state_reader: Optional[Callable[[str], bool]] = None,
        poll_interval: float = 0.05,
        keys: Iterable[str] = DEFAULT_SOURCE_KEYS,
    ):
        self.mapper = mapper or HumanActionMapper()
        self.key_state_reader = key_state_reader or self._build_default_reader()
        self.poll_interval = poll_interval
        self.keys = tuple(keys)

    def read_pressed_keys(self) -> set[str]:
        pressed = set()
        for key in self.keys:
            try:
                is_pressed = bool(self.key_state_reader(key))
            except Exception as exc:
                logger.debug("keyboard demo read skipped: %s", exc)
                is_pressed = False
            if is_pressed:
                pressed.add("space" if key == "SPACE" else key.lower())
        return pressed

    def iter_actions(self, stop_event: threading.Event):
        last_keys: set[str] | None = None
        while not stop_event.is_set():
            keys = self.read_pressed_keys()
            if keys != last_keys:
                last_keys = set(keys)
                yield self.mapper.map_key_snapshot(keys, source="windows_keyboard")
            stop_event.wait(self.poll_interval)

    def _build_default_reader(self) -> Callable[[str], bool]:
        try:
            import win32api  # type: ignore
        except ImportError:
            warned = False

            def missing_reader(_key: str) -> bool:
                nonlocal warned
                if not warned:
                    logger.warning("win32api unavailable; Windows demo input disabled")
                    warned = True
                return False

            return missing_reader

        def read_key(key: str) -> bool:
            vk_code = VK_CODES.get(key)
            return bool(vk_code and (win32api.GetAsyncKeyState(vk_code) & 0x8000))

        return read_key


class HumanDemoRecorder:
    """Best-effort JSONL recorder for human demonstration rows."""

    def __init__(
        self,
        base_dir: str | Path = "logs/human_demos",
        enabled: Optional[bool] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self.base_dir = Path(base_dir)
        self.enabled = enabled
        self.session_id = session_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.metadata = dict(metadata or {})

    def is_enabled(self) -> bool:
        if self.enabled is not None:
            return bool(self.enabled)
        value = os.environ.get("WZRY_HUMAN_DEMO_ENABLED", "0").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def record_demo(
        self,
        *,
        state: Any,
        human_action: HumanAction,
        source: str = "human_demo",
    ) -> None:
        if not self.is_enabled():
            return
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            event = {
                "schema_version": 2,
                "timestamp": now.isoformat(timespec="milliseconds"),
                "source": source,
                "session_id": self.session_id,
                "state": self._serialize(state),
                "human_action": self._serialize(human_action),
            }
            if self.metadata:
                event["metadata"] = self._serialize(self.metadata)
            path = self.base_dir / f"{now:%Y-%m-%d}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        except (OSError, TypeError, ValueError) as exc:
            logger.debug("human demo record skipped: %s", exc)

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, tuple):
            return [self._serialize(item) for item in value]
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._serialize(item) for key, item in value.items()}
        return value


class HumanDemoRuntime:
    """Background bridge between an input source and the game loop recorder."""

    def __init__(
        self,
        *,
        source: Any,
        recorder: HumanDemoRecorder,
    ):
        self.source = source
        self.recorder = recorder
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest_action: HumanAction | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.source is None or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="HumanDemoInput",
            daemon=True,
        )
        self._thread.start()
        logger.info("human demo runtime started")

    def stop(self) -> None:
        self._stop.set()
        if hasattr(self.source, "close"):
            try:
                self.source.close()
            except Exception as exc:
                logger.debug("human demo source close skipped: %s", exc)
        if self._thread is not None:
            self._thread.join(timeout=1)

    def publish_action(self, action: HumanAction) -> None:
        if action.action == "no_op":
            return
        with self._lock:
            self._latest_action = action

    def consume_latest_action(
        self,
        *,
        now: Optional[float] = None,
        max_age: float = 0.5,
    ) -> HumanAction | None:
        now = time.time() if now is None else now
        with self._lock:
            action = self._latest_action
            self._latest_action = None
        if action is None:
            return None
        if now - action.timestamp > max_age:
            return None
        return action

    def record_state_action(self, state: Any, human_action: HumanAction) -> None:
        self.recorder.record_demo(state=state, human_action=human_action)

    def _run(self) -> None:
        try:
            for action in self.source.iter_actions(self._stop):
                if self._stop.is_set():
                    break
                if action is not None:
                    self.publish_action(action)
        except Exception as exc:
            logger.warning("human demo runtime stopped: %s", exc)


def build_human_demo_runtime_from_env() -> HumanDemoRuntime | None:
    """Create a demo runtime from environment variables if recording is enabled."""
    enabled = _env_bool("WZRY_HUMAN_DEMO_ENABLED")
    if not enabled:
        return None

    width, height, raw_width, raw_height = _resolve_touch_coordinate_sizes(
        os.environ.get("WZRY_TOUCH_SIZE", ""),
        os.environ.get("WZRY_TOUCH_RAW_SIZE", ""),
    )
    mapper = HumanActionMapper(width=width, height=height)
    source_name = _resolve_source_name(os.environ.get("WZRY_HUMAN_DEMO_SOURCE", ""))
    if source_name == "adb_touch":
        adb_path = os.environ.get("WZRY_ADB_PATH", "adb")
        device_serial = os.environ.get("WZRY_ADB_DEVICE", "")
        raw_transform = os.environ.get("WZRY_TOUCH_RAW_TRANSFORM", "identity")
        if not raw_width or not raw_height:
            detected_size = detect_adb_touch_raw_size(adb_path, device_serial)
            if detected_size is not None:
                raw_width, raw_height = detected_size
        parser = AdbGeteventParser(
            width=width,
            height=height,
            raw_width=raw_width,
            raw_height=raw_height,
            raw_transform=raw_transform,
            mapper=mapper,
        )
        source = AdbTouchDemoSource(
            adb_path=adb_path,
            device_serial=device_serial,
            parser=parser,
        )
    elif source_name == "windows_keyboard":
        source = WindowsKeyboardDemoSource(mapper=mapper)
    else:
        logger.warning("unknown WZRY_HUMAN_DEMO_SOURCE=%r", source_name)
        return None

    recording_metadata: dict[str, Any] = {
        "input_source": source_name,
        "touch_size": [width, height],
    }
    if raw_width and raw_height:
        recording_metadata["raw_touch_size"] = [raw_width, raw_height]
    if source_name == "adb_touch":
        recording_metadata["raw_transform"] = raw_transform

    recorder = HumanDemoRecorder(
        base_dir=os.environ.get("WZRY_HUMAN_DEMO_DIR", "logs/human_demos"),
        enabled=True,
        metadata=recording_metadata,
    )
    logger.info("human demo recording enabled: source=%s", source_name)
    return HumanDemoRuntime(source=source, recorder=recorder)


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_source_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized:
        return normalized
    device_mode = os.environ.get("WZRY_DEVICE_MODE", "").strip().lower()
    return "adb_touch" if device_mode in {"android", "phone", "device"} else "windows_keyboard"


def _parse_touch_size(value: str) -> tuple[int, int]:
    parsed = _parse_optional_size(value)
    if parsed[0] and parsed[1]:
        return parsed[0], parsed[1]
    return DEFAULT_TOUCH_SIZE


def _resolve_touch_coordinate_sizes(
    touch_size_value: str,
    raw_size_value: str,
) -> tuple[int, int, Optional[int], Optional[int]]:
    touch_width, touch_height = _parse_optional_size(touch_size_value)
    raw_width, raw_height = _parse_optional_size(raw_size_value)
    if (
        (not raw_width or not raw_height)
        and touch_width
        and touch_height
        and _looks_like_raw_touch_size(touch_width, touch_height)
    ):
        logger.warning(
            "WZRY_TOUCH_SIZE=%sx%s looks like a raw touch range; "
            "using %sx%s as game coordinate plane and treating it as raw size",
            touch_width,
            touch_height,
            DEFAULT_TOUCH_SIZE[0],
            DEFAULT_TOUCH_SIZE[1],
        )
        return DEFAULT_TOUCH_SIZE[0], DEFAULT_TOUCH_SIZE[1], touch_width, touch_height

    width = touch_width or DEFAULT_TOUCH_SIZE[0]
    height = touch_height or DEFAULT_TOUCH_SIZE[1]
    return width, height, raw_width, raw_height


def _looks_like_raw_touch_size(width: int, height: int) -> bool:
    return max(width, height) > RAW_LIKE_TOUCH_THRESHOLD


def _parse_optional_size(value: str) -> tuple[Optional[int], Optional[int]]:
    parts = value.lower().replace("x", ",").split(",")
    if len(parts) == 2:
        try:
            width = int(parts[0].strip())
            height = int(parts[1].strip())
        except ValueError:
            pass
        else:
            if width > 0 and height > 0:
                return width, height
    return None, None


def _windows_startupinfo() -> Optional[subprocess.STARTUPINFO]:
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo
