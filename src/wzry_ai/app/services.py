"""Game services initialization and management."""

from __future__ import annotations

import cv2
import numpy as np
import os
import re
import subprocess
import time
import threading
from dataclasses import dataclass
from queue import Queue
from typing import Optional

from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.device.emulator_manager import init_emulator
from wzry_ai.game_manager import ClickExecutor, GameStateDetector, TemplateMatcher
from wzry_ai.utils.thread_supervisor import ThreadSupervisor

logger = get_logger(__name__)


@dataclass
class AndroidDeviceConfig:
    """已连接Android设备的运行时配置。"""

    serial: str
    window_title: str
    client_size: tuple[int, int]
    port: int = 0
    window_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    saved_at: str = ""


class GameServices:
    """管理所有游戏服务的生命周期"""

    def __init__(self, adb_device: Optional[str] = None):
        self.adb_device = adb_device
        self.emulator_config = None
        self.scrcpy_tool = None
        self.frame_container = [None]
        self.frame_update_counter = [0]
        self._adb_screenshot_stop = threading.Event()
        self._adb_screenshot_thread: Optional[threading.Thread] = None

        # 队列
        self.skill_queue = Queue(maxsize=1)
        self.status_queue = Queue(maxsize=5)
        self.model1_data_queue = Queue(maxsize=1)
        self.model2_data_queue = Queue(maxsize=1)
        self.pause_event = threading.Event()
        self.pause_event.set()  # 默认暂停

        # 检测器和执行器
        self.template_matcher = None
        self.click_executor = None
        self.state_detector = None
        self.thread_supervisor = ThreadSupervisor()

        # 状态
        self.combat_active = False
        self.modules_loaded = False
        self.current_hero_name = None

    def initialize(self) -> bool:
        """初始化所有服务"""
        try:
            # 初始化模拟器
            if not self._init_emulator():
                return False

            # 创建调试窗口
            self._create_debug_windows()

            # 初始化状态检测系统
            self._init_state_detection()

            # 初始化scrcpy连接
            self._init_scrcpy()

            # 启动战斗系统线程
            if not self._start_battle_system():
                logger.error("战斗系统启动失败")
                return False

            # 启动技能系统线程
            if not self._start_skill_system():
                logger.error("技能系统启动失败")
                return False

            # 设置线程监督
            self._setup_thread_supervision()

            logger.info("✓ 所有服务初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False

    def _init_emulator(self) -> bool:
        """初始化设备连接（MuMu模拟器或已连接Android设备）"""
        try:
            if self._should_use_android_device():
                return self._init_android_device()

            from wzry_ai.config import ADB_PATH

            self.emulator_config = init_emulator(adb_path=ADB_PATH)
            self.adb_device = self.emulator_config.serial
            logger.info(f"模拟器窗口: {self.emulator_config.window_title}")
            logger.info(f"ADB设备: {self.adb_device}")
            logger.info(
                f"分辨率: {self.emulator_config.client_size[0]}x{self.emulator_config.client_size[1]}"
            )
            return True
        except (OSError, RuntimeError, ConnectionError) as e:
            logger.error(f"模拟器初始化失败: {e}")
            logger.error("请确保模拟器已启动，分辨率为 1920x1080")
            return False

    def _init_android_device(self) -> bool:
        """初始化已通过ADB连接的Android设备。"""
        from wzry_ai.config import ADB_DEVICE_SERIAL, DEFAULT_REGIONS

        serial = self.adb_device or ADB_DEVICE_SERIAL
        if not serial:
            logger.error("未指定Android设备序列号")
            return False

        fallback_size = (
            DEFAULT_REGIONS["full"]["width"],
            DEFAULT_REGIONS["full"]["height"],
        )
        self._prepare_android_device(serial)
        client_size = self._query_android_device_size(serial) or fallback_size

        self.adb_device = serial
        self.emulator_config = AndroidDeviceConfig(
            serial=serial,
            window_title=f"Android device {serial}",
            client_size=client_size,
            saved_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        logger.info("=" * 50)
        logger.info("初始化成功")
        logger.info("  设备类型: Android真机/通用ADB设备")
        logger.info(f"  ADB Serial: {serial}")
        logger.info(f"  屏幕大小: {client_size[0]}x{client_size[1]}")
        logger.info("=" * 50)
        return True

    def _should_use_android_device(self) -> bool:
        """判断是否跳过MuMu窗口探测，直接使用已连接Android设备。"""
        from wzry_ai.config import DEVICE_MODE

        mode = os.environ.get("WZRY_DEVICE_MODE", DEVICE_MODE).strip().lower()
        if mode in {"android", "phone", "device", "physical"}:
            return True
        if mode in {"mumu", "emulator", "simulator"}:
            return False

        if not self.adb_device:
            return False
        return not self._is_local_tcp_serial(self.adb_device)

    @staticmethod
    def _is_local_tcp_serial(serial: str) -> bool:
        """MuMu等本地模拟器通常使用127.0.0.1:port形式。"""
        normalized = serial.strip().lower()
        return (
            normalized.startswith("127.0.0.1:")
            or normalized.startswith("localhost:")
            or normalized.startswith("[::1]:")
        )

    def _query_android_device_size(self, serial: str) -> Optional[tuple[int, int]]:
        """通过ADB读取Android设备屏幕尺寸。"""
        from wzry_ai.config import ADB_PATH

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            result = subprocess.run(
                [ADB_PATH, "-s", serial, "shell", "wm", "size"],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=startupinfo,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"读取Android设备屏幕尺寸失败: {e}")
            return None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.warning(f"读取Android设备屏幕尺寸失败: {stderr}")
            return None

        match = re.search(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", result.stdout)
        if match is None:
            logger.warning(f"无法解析Android设备屏幕尺寸: {result.stdout.strip()}")
            return None

        return int(match.group(1)), int(match.group(2))

    def _prepare_android_device(self, serial: str, command_runner=None) -> None:
        """唤醒Android设备，并尽量保持连接期间屏幕常亮。"""
        from wzry_ai.config import ADB_PATH

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        runner = command_runner or subprocess.run
        commands = [
            [ADB_PATH, "-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
            [ADB_PATH, "-s", serial, "shell", "wm", "dismiss-keyguard"],
            [ADB_PATH, "-s", serial, "shell", "svc", "power", "stayon", "true"],
        ]

        for command in commands:
            try:
                result = runner(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    startupinfo=startupinfo,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                logger.warning(f"Android设备准备命令失败: {command[3:]}: {e}")
                continue

            if getattr(result, "returncode", 0) != 0:
                stderr = getattr(result, "stderr", "") or ""
                logger.debug(
                    f"Android设备准备命令未生效: {command[3:]}: {stderr.strip()}"
                )

        logger.info("已发送Android设备唤醒/常亮指令")

    def _create_debug_windows(self):
        """创建调试窗口"""
        if os.environ.get("WZRY_DEBUG_WINDOWS", "1").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            logger.info("OpenCV debug windows disabled")
            return
        from wzry_ai.config import DEFAULT_REGIONS

        cv2.namedWindow("EVE", cv2.WINDOW_NORMAL)
        cv2.namedWindow("EVE Check", cv2.WINDOW_NORMAL)
        cv2.moveWindow("EVE", 50, 50)
        cv2.moveWindow("EVE Check", 700, 50)
        cv2.imshow("EVE", np.zeros((360, 640, 3), dtype=np.uint8))

        _mm = DEFAULT_REGIONS["minimap"]
        cv2.resizeWindow("EVE Check", _mm["width"], _mm["height"])
        cv2.imshow("EVE Check", np.zeros((300, 300, 3), dtype=np.uint8))
        cv2.waitKey(1)
        logger.info("调试窗口已创建 (EVE / EVE Check)")

    def _init_state_detection(self):
        """初始化状态检测系统"""
        logger.info("初始化状态检测系统...")
        self.template_matcher = TemplateMatcher(match_scale=1.0)
        self.click_executor = ClickExecutor(adb_device=self.adb_device, use_adb=True)  # pyright: ignore[reportArgumentType]
        self.state_detector = GameStateDetector(
            self.template_matcher,
            self.click_executor,
            confirm_threshold=3,
            unknown_threshold=10,
        )
        logger.info("状态检测系统初始化完成")

    def _init_scrcpy(self):
        """初始化scrcpy连接"""
        import scrcpy
        from wzry_ai.device.ScrcpyTool import ScrcpyTool

        logger.info("初始化 ScrcpyTool 连接...")

        def on_frame(frame):
            if frame is not None:
                self.frame_container[0] = frame
                self.frame_update_counter[0] += 1

        device_serial = self.adb_device
        if device_serial is None:
            raise RuntimeError("ADB device not initialized")
        try:
            self.scrcpy_tool = ScrcpyTool(device_serial=device_serial)
            self.scrcpy_tool.client.add_listener(scrcpy.EVENT_FRAME, on_frame)
            self.scrcpy_tool.client.max_fps = 30
            self.scrcpy_tool.client.start(threaded=True)
        except Exception as exc:
            if self._should_use_android_device():
                logger.warning(f"scrcpy 启动失败，切换到 ADB 截图帧源: {exc}")
                self._start_adb_screenshot_fallback(on_frame)
                return
            raise

        if self._wait_for_first_scrcpy_frame(timeout=2.0):
            logger.info("ScrcpyTool 连接成功")
            return

        if self._should_use_android_device():
            logger.warning("scrcpy 未收到有效首帧，切换到 ADB 截图帧源")
            try:
                self.scrcpy_tool.client.stop()
            except Exception as exc:
                logger.debug(f"停止无帧 scrcpy 客户端失败: {exc}")
            self._start_adb_screenshot_fallback(on_frame)
            return

        logger.warning("scrcpy 已连接但暂未收到有效首帧")

    def _wait_for_first_scrcpy_frame(self, timeout: float = 2.0) -> bool:
        """等待scrcpy首帧，避免无帧黑窗口继续运行。"""
        deadline = time.time() + timeout
        start_counter = self.frame_update_counter[0]
        while time.time() < deadline:
            if (
                self.frame_container[0] is not None
                and self.frame_update_counter[0] > start_counter
            ):
                return True
            time.sleep(0.05)
        return False

    def _start_adb_screenshot_fallback(self, on_frame) -> None:
        """启动ADB screencap后备帧源，用于不兼容scrcpy视频流的真机。"""
        if (
            self._adb_screenshot_thread is not None
            and self._adb_screenshot_thread.is_alive()
        ):
            return

        self._adb_screenshot_stop.clear()
        fps_raw = os.environ.get("WZRY_ADB_SCREENSHOT_FPS", "8")
        try:
            fps = max(1.0, min(15.0, float(fps_raw)))
        except ValueError:
            fps = 8.0
        interval = 1.0 / fps

        def run_loop() -> None:
            logger.info(f"ADB截图帧源启动，目标FPS: {fps:.1f}")
            while not self._adb_screenshot_stop.is_set():
                started = time.time()
                frame = self._capture_adb_screenshot_frame()
                if frame is not None:
                    on_frame(frame)
                elapsed = time.time() - started
                self._adb_screenshot_stop.wait(max(0.0, interval - elapsed))
            logger.info("ADB截图帧源已停止")

        self._adb_screenshot_thread = threading.Thread(
            target=run_loop,
            name="AdbScreenshotFrameSource",
            daemon=True,
        )
        self._adb_screenshot_thread.start()

    def _capture_adb_screenshot_frame(self) -> Optional[np.ndarray]:
        """通过ADB screencap抓取一帧并解码成BGR图像。"""
        from wzry_ai.config import ADB_PATH

        if not self.adb_device:
            return None

        try:
            result = subprocess.run(
                [ADB_PATH, "-s", self.adb_device, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug(f"ADB截图失败: {exc}")
            return None

        if result.returncode != 0 or not result.stdout:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            logger.debug(f"ADB截图命令失败: {stderr or result.returncode}")
            return None

        data = np.frombuffer(result.stdout, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            logger.debug("ADB截图解码失败")
            return None
        return frame

    def _start_battle_system(self) -> bool:
        """启动战斗系统线程"""
        logger.info("正在启动战斗系统...")

        try:
            from wzry_ai.movement.movement_logic_yao import run_fusion_logic_v2

            battle_managed = self.thread_supervisor.register(
                "battle_system",
                run_fusion_logic_v2,
                args=(
                    self.skill_queue,
                    self.pause_event,
                    self.status_queue,
                    self.model1_data_queue,
                    self.model2_data_queue,
                ),
                daemon=True,
            )
            battle_managed.create_thread().start()
            logger.info("✓ 战斗系统线程已启动")
            return True

        except Exception as e:
            logger.error(f"战斗系统启动失败: {e}", exc_info=True)
            return False

    def _start_skill_system(self) -> bool:
        """启动技能系统线程"""
        logger.info("正在启动技能系统...")

        try:
            from wzry_ai.config import DEFAULT_SUPPORT_HERO

            # 动态加载技能逻辑类
            if DEFAULT_SUPPORT_HERO == "瑶":
                from wzry_ai.skills.yao_skill_logic_v2 import YaoSkillLogic

                skill_logic = YaoSkillLogic()
            elif DEFAULT_SUPPORT_HERO == "蔡文姬":
                from wzry_ai.skills.caiwenji_skill_logic_v2 import CaiwenjiSkillLogic

                skill_logic = CaiwenjiSkillLogic()
            elif DEFAULT_SUPPORT_HERO == "明世隐":
                from wzry_ai.skills.mingshiyin_skill_logic_v2 import (
                    MingshiyinSkillLogic,
                )

                skill_logic = MingshiyinSkillLogic()
            else:
                logger.error(f"不支持的英雄: {DEFAULT_SUPPORT_HERO}")
                logger.error("支持的英雄: 瑶, 蔡文姬, 明世隐")
                return False

            skill_managed = self.thread_supervisor.register(
                "skill_system",
                skill_logic.run,
                args=(self.skill_queue,),
                daemon=True,
            )
            skill_managed.create_thread().start()
            logger.info(f"✓ 技能系统线程已启动 (英雄: {DEFAULT_SUPPORT_HERO})")
            return True

        except Exception as e:
            logger.error(f"技能系统启动失败: {e}", exc_info=True)
            return False

    def _setup_thread_supervision(self):
        """设置线程监督"""
        logger.info("正在设置线程监督...")

        try:
            # ThreadSupervisor 使用 check_and_restart() 方法
            # 需要在主循环中定期调用，这里只是标记已设置
            logger.info("✓ 线程监督已配置（将在主循环中定期检查）")
        except Exception as e:
            logger.error(f"线程监督配置失败: {e}", exc_info=True)

    def cleanup(self):
        """清理资源"""
        try:
            self._adb_screenshot_stop.set()
            if self._adb_screenshot_thread is not None:
                self._adb_screenshot_thread.join(timeout=2)
            if self.scrcpy_tool:
                self.scrcpy_tool.client.stop()
            self.thread_supervisor.stop_all()
            cv2.destroyAllWindows()
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")


__all__ = ["GameServices"]
