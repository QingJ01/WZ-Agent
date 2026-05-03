"""测试游戏服务模块"""

import pytest
import numpy as np
import cv2
import subprocess
from unittest.mock import Mock, patch, MagicMock
from wzry_ai.app.services import GameServices
import wzry_ai.app.services as services_module


class TestGameServices:
    """测试GameServices类"""
    
    @pytest.fixture
    def services(self):
        """创建测试用的游戏服务实例"""
        with patch('wzry_ai.app.services.init_emulator'):
            with patch('wzry_ai.app.services.cv2'):
                return GameServices(adb_device="test_device")
    
    def test_initialization(self, services):
        """测试初始化"""
        assert services.adb_device == "test_device"
        assert services.emulator_config is None
        assert services.scrcpy_tool is None
        assert services.frame_container == [None]
        assert services.frame_update_counter == [0]
        assert services.combat_active is False
        assert services.modules_loaded is False
        assert services.current_hero_name is None
    
    def test_queues_initialization(self, services):
        """测试队列初始化"""
        assert services.skill_queue is not None
        assert services.status_queue is not None
        assert services.model1_data_queue is not None
        assert services.model2_data_queue is not None
        assert services.pause_event is not None
    
    def test_pause_event_default_state(self, services):
        """测试暂停事件默认状态"""
        assert services.pause_event.is_set() is True
    
    def test_thread_supervisor_initialization(self, services):
        """测试线程监督器初始化"""
        assert services.thread_supervisor is not None
    
    @patch('wzry_ai.app.services.init_emulator')
    @patch('wzry_ai.app.services.cv2')
    def test_init_emulator_success(self, mock_cv2, mock_init_emulator):
        """测试成功初始化模拟器"""
        # 模拟模拟器配置
        mock_config = Mock()
        mock_config.serial = "emulator-5554"
        mock_config.window_title = "Test Emulator"
        mock_config.client_size = (1920, 1080)
        mock_init_emulator.return_value = mock_config
        
        services = GameServices()
        result = services._init_emulator()
        
        assert result is True
        assert services.emulator_config == mock_config
        assert services.adb_device == "emulator-5554"
    
    @patch('wzry_ai.app.services.init_emulator')
    def test_init_emulator_uses_mumu_for_local_tcp_serial(self, mock_init_emulator):
        """测试本地TCP序列号仍走MuMu初始化"""
        mock_config = Mock()
        mock_config.serial = "127.0.0.1:7555"
        mock_config.window_title = "MuMu"
        mock_config.client_size = (1920, 1080)
        mock_init_emulator.return_value = mock_config

        services = GameServices(adb_device="127.0.0.1:7555")
        result = services._init_emulator()

        assert result is True
        mock_init_emulator.assert_called_once()
        assert services.adb_device == "127.0.0.1:7555"
    
    @patch('wzry_ai.app.services.init_emulator')
    @patch.object(GameServices, '_query_android_device_size', return_value=(1080, 2400))
    @patch.object(GameServices, '_prepare_android_device')
    def test_init_emulator_skips_mumu_for_usb_phone_serial(
        self, mock_prepare_device, mock_query_size, mock_init_emulator
    ):
        """测试USB真机序列号跳过MuMu窗口初始化"""
        services = GameServices(adb_device="DEVICE1234567890")
        result = services._init_emulator()

        assert result is True
        mock_init_emulator.assert_not_called()
        mock_prepare_device.assert_called_once_with("DEVICE1234567890")
        mock_query_size.assert_called_once_with("DEVICE1234567890")
        assert services.adb_device == "DEVICE1234567890"
        assert services.emulator_config.serial == "DEVICE1234567890"
        assert services.emulator_config.window_title == "Android device DEVICE1234567890"
        assert services.emulator_config.client_size == (1080, 2400)
    
    @patch('wzry_ai.app.services.init_emulator')
    @patch.object(GameServices, '_query_android_device_size', return_value=None)
    @patch.object(GameServices, '_prepare_android_device')
    def test_init_emulator_skips_mumu_for_forced_android_mode(
        self, mock_prepare_device, mock_query_size, mock_init_emulator, monkeypatch
    ):
        """测试环境变量强制android模式时跳过MuMu"""
        monkeypatch.setenv("WZRY_DEVICE_MODE", "android")

        services = GameServices(adb_device="127.0.0.1:5555")
        result = services._init_emulator()

        assert result is True
        mock_init_emulator.assert_not_called()
        mock_prepare_device.assert_called_once_with("127.0.0.1:5555")
        mock_query_size.assert_called_once_with("127.0.0.1:5555")
        assert services.emulator_config.client_size == (1920, 1080)

    def test_prepare_android_device_wakes_and_keeps_screen_on(self, services):
        """测试真机初始化会唤醒屏幕并设置常亮。"""
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            result = Mock()
            result.returncode = 0
            result.stderr = ""
            return result

        services._prepare_android_device("serial", command_runner=fake_run)

        assert [command[3:] for command in commands] == [
            ["shell", "input", "keyevent", "KEYCODE_WAKEUP"],
            ["shell", "wm", "dismiss-keyguard"],
            ["shell", "svc", "power", "stayon", "true"],
        ]
    
    @patch('wzry_ai.app.services.init_emulator')
    def test_init_emulator_failure(self, mock_init_emulator):
        """测试模拟器初始化失败"""
        mock_init_emulator.side_effect = OSError("Connection failed")
        
        services = GameServices()
        result = services._init_emulator()
        
        assert result is False
    
    @patch('wzry_ai.app.services.cv2')
    def test_create_debug_windows(self, mock_cv2, services):
        """测试创建调试窗口"""
        services._create_debug_windows()
        
        # 验证窗口创建调用
        assert mock_cv2.namedWindow.called
        assert mock_cv2.moveWindow.called
        assert mock_cv2.imshow.called

    @patch('wzry_ai.app.services.cv2')
    def test_create_debug_windows_respects_env_disabled(self, mock_cv2, services, monkeypatch):
        monkeypatch.setenv("WZRY_DEBUG_WINDOWS", "0")

        services._create_debug_windows()

        mock_cv2.namedWindow.assert_not_called()
    
    @patch('wzry_ai.app.services.TemplateMatcher')
    @patch('wzry_ai.app.services.ClickExecutor')
    @patch('wzry_ai.app.services.GameStateDetector')
    def test_init_state_detection(self, mock_detector, mock_executor, mock_matcher, services):
        """测试初始化状态检测系统"""
        services._init_state_detection()
        
        assert services.template_matcher is not None
        assert services.click_executor is not None
        assert services.state_detector is not None

    @patch('wzry_ai.movement.movement_logic_yao.run_fusion_logic_v2')
    def test_start_battle_system_uses_thread_supervisor_register(self, mock_run, services):
        """测试战斗线程使用当前ThreadSupervisor注册接口"""
        result = services._start_battle_system()

        assert result is True
        assert len(services.thread_supervisor._threads) == 1
        managed = services.thread_supervisor._threads[0]
        assert managed.name == "battle_system"
        assert managed.args == (
            services.skill_queue,
            services.pause_event,
            services.status_queue,
            services.model1_data_queue,
            services.model2_data_queue,
        )

    @patch('wzry_ai.skills.yao_skill_logic_v2.YaoSkillLogic')
    def test_start_skill_system_uses_thread_supervisor_register(self, mock_logic, services):
        """测试技能线程使用当前ThreadSupervisor注册接口"""
        mock_logic.return_value.run = Mock()

        result = services._start_skill_system()

        assert result is True
        assert len(services.thread_supervisor._threads) == 1
        assert services.thread_supervisor._threads[0].name == "skill_system"
    
    def test_cleanup(self, services):
        """测试资源清理"""
        # 模拟scrcpy工具
        services.scrcpy_tool = Mock()
        services.scrcpy_tool.client = Mock()
        
        # 执行清理
        with patch('wzry_ai.app.services.cv2'):
            services.cleanup()
        
        # 验证清理调用
        services.scrcpy_tool.client.stop.assert_called_once()


class TestGameServicesIntegration:
    """测试GameServices集成场景"""
    
    @pytest.mark.skip(reason="需要真实设备连接，跳过以避免ADB错误")
    @patch('wzry_ai.device.ScrcpyTool')
    @patch('wzry_ai.app.services.init_emulator')
    @patch('wzry_ai.app.services.cv2')
    @patch('wzry_ai.app.services.TemplateMatcher')
    @patch('wzry_ai.app.services.ClickExecutor')
    @patch('wzry_ai.app.services.GameStateDetector')
    @patch('scrcpy.EVENT_FRAME', 'frame')
    def test_full_initialization_success(
        self, mock_detector, mock_executor, 
        mock_matcher, mock_cv2, mock_init_emulator, mock_scrcpy
    ):
        """测试完整初始化流程成功"""
        # 模拟模拟器配置
        mock_config = Mock()
        mock_config.serial = "emulator-5554"
        mock_config.window_title = "Test Emulator"
        mock_config.client_size = (1920, 1080)
        mock_init_emulator.return_value = mock_config
        
        # 模拟scrcpy客户端
        mock_client = Mock()
        mock_client.start = Mock()
        mock_client.add_listener = Mock()
        mock_scrcpy_instance = Mock()
        mock_scrcpy_instance.client = mock_client
        mock_scrcpy.return_value = mock_scrcpy_instance
        
        services = GameServices()
        result = services.initialize()
        
        assert result is True
    
    @patch('wzry_ai.app.services.init_emulator')
    def test_full_initialization_failure(self, mock_init_emulator):
        """测试完整初始化流程失败"""
        mock_init_emulator.side_effect = RuntimeError("Emulator not found")
        
        services = GameServices()
        result = services.initialize()
        
        assert result is False


class TestGameServicesState:
    """测试GameServices状态管理"""
    
    @pytest.fixture
    def services(self):
        """创建测试用的游戏服务实例"""
        with patch('wzry_ai.app.services.init_emulator'):
            with patch('wzry_ai.app.services.cv2'):
                return GameServices()
    
    def test_combat_active_state(self, services):
        """测试战斗激活状态"""
        assert services.combat_active is False
        services.combat_active = True
        assert services.combat_active is True
    
    def test_modules_loaded_state(self, services):
        """测试模块加载状态"""
        assert services.modules_loaded is False
        services.modules_loaded = True
        assert services.modules_loaded is True
    
    def test_current_hero_name_state(self, services):
        """测试当前英雄名称状态"""
        assert services.current_hero_name is None
        services.current_hero_name = "瑶"
        assert services.current_hero_name == "瑶"
    
    def test_frame_container_update(self, services):
        """测试帧容器更新"""
        test_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        services.frame_container[0] = test_frame
        assert services.frame_container[0] is not None
        assert services.frame_container[0].shape == (1080, 1920, 3)
    
    def test_frame_update_counter(self, services):
        """测试帧更新计数器"""
        initial_count = services.frame_update_counter[0]
        services.frame_update_counter[0] += 1
        assert services.frame_update_counter[0] == initial_count + 1

    def test_bootstrap_adds_local_scrcpy_dir_to_path(self, monkeypatch):
        """测试运行时启动时全局加入本地scrcpy工具目录。"""
        import logging
        import os
        from wzry_ai.app import bootstrap
        from wzry_ai.config import LOCAL_SCRCPY_DIR

        if not os.path.isdir(LOCAL_SCRCPY_DIR):
            pytest.skip("local scrcpy tool directory not present")

        monkeypatch.setenv("PATH", "")
        bootstrap._prepend_adb_to_path(logging.getLogger("test"))

        path_parts = os.environ["PATH"].split(os.pathsep)
        assert LOCAL_SCRCPY_DIR in path_parts

    def test_init_scrcpy_falls_back_to_adb_screenshot_for_android_without_first_frame(
        self, services, monkeypatch
    ):
        """测试真机scrcpy无首帧时切换到ADB截图后备"""
        import wzry_ai.device.ScrcpyTool as scrcpy_tool_module

        class FakeClient:
            def __init__(self):
                self.listeners = []
                self.started = False
                self.stopped = False
                self.max_fps = None

            def add_listener(self, event, callback):
                self.listeners.append((event, callback))

            def start(self, threaded=False):
                self.started = threaded

            def stop(self):
                self.stopped = True

        fake_client = FakeClient()

        class FakeScrcpyTool:
            def __init__(self, device_serial=None):
                self.device_serial = device_serial
                self.client = fake_client

        fallback_calls = []
        services.adb_device = "DEVICE1234567890"
        monkeypatch.setenv("WZRY_FRAME_SOURCE", "auto")
        monkeypatch.setattr(scrcpy_tool_module, "ScrcpyTool", FakeScrcpyTool)
        monkeypatch.setattr(services, "_should_use_android_device", lambda: True)
        monkeypatch.setattr(
            services, "_wait_for_first_scrcpy_frame", lambda timeout=2.0: False
        )
        monkeypatch.setattr(
            services,
            "_start_adb_screenshot_fallback",
            lambda on_frame: fallback_calls.append(on_frame),
        )

        services._init_scrcpy()

        assert fake_client.started is True
        assert fake_client.stopped is True
        assert len(fallback_calls) == 1

    def test_init_scrcpy_forced_scrcpy_raises_without_first_frame(
        self, services, monkeypatch
    ):
        """Forced scrcpy mode must not fall back to ADB screenshots."""
        import wzry_ai.device.ScrcpyTool as scrcpy_tool_module

        class FakeClient:
            def __init__(self):
                self.listeners = []
                self.started = False
                self.stopped = False
                self.max_fps = None

            def add_listener(self, event, callback):
                self.listeners.append((event, callback))

            def start(self, threaded=False):
                self.started = threaded

            def stop(self):
                self.stopped = True

        fake_client = FakeClient()

        class FakeScrcpyTool:
            def __init__(self, device_serial=None):
                self.device_serial = device_serial
                self.client = fake_client

        fallback_calls = []
        services.adb_device = "DEVICE1234567890"
        monkeypatch.setenv("WZRY_FRAME_SOURCE", "scrcpy")
        monkeypatch.setattr(scrcpy_tool_module, "ScrcpyTool", FakeScrcpyTool)
        monkeypatch.setattr(services, "_should_use_android_device", lambda: True)
        monkeypatch.setattr(
            services, "_wait_for_first_scrcpy_frame", lambda timeout=10.0: False
        )
        monkeypatch.setattr(
            services,
            "_start_adb_screenshot_fallback",
            lambda on_frame: fallback_calls.append(on_frame),
        )

        with pytest.raises(RuntimeError, match="scrcpy"):
            services._init_scrcpy()

        assert fake_client.started is True
        assert fake_client.stopped is True
        assert fallback_calls == []

    def test_init_scrcpy_uses_adb_frame_source_when_requested(
        self, services, monkeypatch
    ):
        """Explicit ADB frame source remains available as a manual compatibility mode."""
        fallback_calls = []
        services.adb_device = "DEVICE1234567890"
        monkeypatch.setenv("WZRY_FRAME_SOURCE", "adb")
        monkeypatch.setattr(
            services,
            "_start_adb_screenshot_fallback",
            lambda on_frame: fallback_calls.append(on_frame),
        )

        services._init_scrcpy()

        assert services.scrcpy_tool is None
        assert len(fallback_calls) == 1

    def test_init_scrcpy_falls_back_to_adb_screenshot_when_scrcpy_start_fails(
        self, services, monkeypatch
    ):
        """测试真机scrcpy启动失败时也切换到ADB截图后备"""
        import wzry_ai.device.ScrcpyTool as scrcpy_tool_module

        class FakeClient:
            def __init__(self):
                self.max_fps = None

            def add_listener(self, event, callback):
                pass

            def start(self, threaded=False):
                raise OSError("scrcpy failed")

        class FakeScrcpyTool:
            def __init__(self, device_serial=None):
                self.device_serial = device_serial
                self.client = FakeClient()

        fallback_calls = []
        services.adb_device = "DEVICE1234567890"
        monkeypatch.setenv("WZRY_FRAME_SOURCE", "auto")
        monkeypatch.setattr(scrcpy_tool_module, "ScrcpyTool", FakeScrcpyTool)
        monkeypatch.setattr(services, "_should_use_android_device", lambda: True)
        monkeypatch.setattr(
            services,
            "_start_adb_screenshot_fallback",
            lambda on_frame: fallback_calls.append(on_frame),
        )

        services._init_scrcpy()

        assert len(fallback_calls) == 1

    def test_capture_adb_screenshot_frame_decodes_png(self, services, monkeypatch):
        """测试ADB截图后备能解码screencap PNG"""
        image = np.full((2, 3, 3), 127, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        assert ok

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=encoded.tobytes(),
                stderr=b"",
            )

        services.adb_device = "DEVICE1234567890"
        monkeypatch.setattr(services_module.subprocess, "run", fake_run)

        frame = services._capture_adb_screenshot_frame()

        assert frame is not None
        assert frame.shape == (2, 3, 3)
