"""测试配置模块"""

import pytest
import importlib
from wzry_ai.config import (
    GRID_SIZE,
    CELL_SIZE,
    DEFAULT_TEMPLATE_CONFIDENCE,
    KEY_MOVE_UP,
    KEY_MOVE_LEFT,
    KEY_MOVE_DOWN,
    KEY_MOVE_RIGHT,
)
from wzry_ai.config import base


class TestConfigConstants:
    """测试配置常量"""
    
    def test_grid_size(self):
        """测试网格大小配置"""
        assert isinstance(GRID_SIZE, int)
        assert GRID_SIZE > 0
    
    def test_cell_size(self):
        """测试单元格大小配置"""
        assert isinstance(CELL_SIZE, (int, float))
        assert CELL_SIZE > 0
    
    def test_default_template_confidence(self):
        """测试默认模板置信度"""
        assert isinstance(DEFAULT_TEMPLATE_CONFIDENCE, (int, float))
        assert 0.0 <= DEFAULT_TEMPLATE_CONFIDENCE <= 1.0
    
    def test_movement_keys(self):
        """测试移动按键配置"""
        assert isinstance(KEY_MOVE_UP, str)
        assert isinstance(KEY_MOVE_LEFT, str)
        assert isinstance(KEY_MOVE_DOWN, str)
        assert isinstance(KEY_MOVE_RIGHT, str)
        
        # 验证按键不为空
        assert len(KEY_MOVE_UP) > 0
        assert len(KEY_MOVE_LEFT) > 0
        assert len(KEY_MOVE_DOWN) > 0
        assert len(KEY_MOVE_RIGHT) > 0
    
    def test_movement_keys_unique(self):
        """测试移动按键唯一性"""
        keys = [KEY_MOVE_UP, KEY_MOVE_LEFT, KEY_MOVE_DOWN, KEY_MOVE_RIGHT]
        assert len(keys) == len(set(keys))


class TestConfigImports:
    """测试配置导入"""
    
    def test_import_base_config(self):
        """测试导入基础配置"""
        try:
            from wzry_ai.config import base
            assert base is not None
        except ImportError:
            pytest.skip("base config not available")
    
    def test_import_keys_config(self):
        """测试导入按键配置"""
        try:
            from wzry_ai.config import keys
            assert keys is not None
        except ImportError:
            pytest.skip("keys config not available")
    
    def test_import_templates_config(self):
        """测试导入模板配置"""
        try:
            from wzry_ai.config import templates
            assert templates is not None
        except ImportError:
            pytest.skip("templates config not available")
    
    def test_import_emulator_config(self):
        """测试导入模拟器配置"""
        try:
            from wzry_ai.config import emulator
            assert emulator is not None
        except ImportError:
            pytest.skip("emulator config not available")


class TestConfigValues:
    """测试配置值的合理性"""
    
    def test_grid_size_reasonable(self):
        """测试网格大小合理性"""
        assert 10 <= GRID_SIZE <= 1000
    
    def test_cell_size_reasonable(self):
        """测试单元格大小合理性"""
        assert 1 <= CELL_SIZE <= 100
    
    def test_confidence_in_valid_range(self):
        """测试置信度在有效范围内"""
        assert 0.0 <= DEFAULT_TEMPLATE_CONFIDENCE <= 1.0

    def test_find_adb_path_prefers_environment_override(self, monkeypatch, tmp_path):
        """测试ADB路径优先使用环境变量覆盖"""
        adb_path = tmp_path / "adb.exe"
        adb_path.write_text("", encoding="utf-8")
        monkeypatch.setenv("WZRY_ADB_PATH", str(adb_path))

        assert base._find_adb_path() == str(adb_path)

    def test_adb_device_serial_prefers_environment_override(self, monkeypatch):
        """测试ADB设备序列号优先使用环境变量覆盖"""
        monkeypatch.setenv("WZRY_ADB_DEVICE", "DEVICE1234567890")
        reloaded = importlib.reload(base)

        try:
            assert reloaded.ADB_DEVICE_SERIAL == "DEVICE1234567890"
        finally:
            monkeypatch.delenv("WZRY_ADB_DEVICE", raising=False)
            importlib.reload(base)

    def test_model_weights_prefer_environment_overrides(self, monkeypatch, tmp_path):
        model1 = tmp_path / "model1.pt"
        model2 = tmp_path / "model2.pt"
        model3 = tmp_path / "model3.pt"
        monkeypatch.setenv("WZRY_MODEL1_WEIGHTS", str(model1))
        monkeypatch.setenv("WZRY_MODEL2_WEIGHTS", str(model2))
        monkeypatch.setenv("WZRY_MODEL3_WEIGHTS", str(model3))
        reloaded = importlib.reload(base)

        try:
            assert reloaded.MODEL1_WEIGHTS == str(model1)
            assert reloaded.MODEL2_WEIGHTS == str(model2)
            assert reloaded.MODEL3_WEIGHTS == str(model3)
        finally:
            monkeypatch.delenv("WZRY_MODEL1_WEIGHTS", raising=False)
            monkeypatch.delenv("WZRY_MODEL2_WEIGHTS", raising=False)
            monkeypatch.delenv("WZRY_MODEL3_WEIGHTS", raising=False)
            importlib.reload(base)


class TestConfigHeroes:
    """测试英雄配置"""
    
    def test_import_hero_mapping(self):
        """测试导入英雄映射"""
        try:
            from wzry_ai.config.heroes import mapping
            assert mapping is not None
        except ImportError:
            pytest.skip("hero mapping not available")
    
    def test_import_hero_state_configs(self):
        """测试导入英雄状态配置"""
        try:
            from wzry_ai.config.heroes import state_configs
            assert state_configs is not None
        except ImportError:
            pytest.skip("hero state configs not available")
    
    def test_import_hero_support_config(self):
        """测试导入英雄辅助配置"""
        try:
            from wzry_ai.config.heroes import support_config
            assert support_config is not None
        except ImportError:
            pytest.skip("hero support config not available")
