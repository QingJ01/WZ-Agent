"""集成测试 - 测试模块间交互"""

import pytest
from unittest.mock import Mock, patch
import numpy as np


@pytest.mark.integration
class TestHeroSystemIntegration:
    """测试英雄系统集成"""
    
    def test_hero_registry_with_skill_logic(self):
        """测试英雄注册表与技能逻辑集成"""
        from wzry_ai.battle.hero_registry import get_skill_logic, SUPPORTED_HEROES
        
        for hero_name in SUPPORTED_HEROES:
            skill_logic = get_skill_logic(hero_name)
            assert skill_logic is not None
            assert hasattr(skill_logic, "paused")
    
    def test_hero_registry_with_decision_maker(self):
        """测试英雄注册表与决策器集成"""
        from wzry_ai.battle.hero_registry import get_decision_maker, SUPPORTED_HEROES
        
        for hero_name in SUPPORTED_HEROES:
            decision_maker = get_decision_maker(hero_name)
            assert decision_maker is not None


@pytest.mark.integration
class TestResourceSystemIntegration:
    """测试资源系统集成"""
    
    def test_resource_resolver_with_template_matcher(self):
        """测试资源解析器与模板匹配器集成"""
        from wzry_ai.utils.resource_resolver import get_runtime_path_resolver
        from wzry_ai.game_manager.template_matcher import TemplateMatcher
        
        resolver = get_runtime_path_resolver()
        templates_dir = resolver.templates_dir()
        
        # 创建模板匹配器
        matcher = TemplateMatcher(
            template_folder=str(templates_dir),
            match_scale=0.5,
            use_mtm=False
        )
        
        assert matcher is not None
        assert matcher.template_folder is not None
    
    def test_resource_paths_consistency(self):
        """测试资源路径一致性"""
        from wzry_ai.utils.resource_resolver import (
            get_repo_root,
            resolve_template_path,
            resolve_model_path,
            resolve_data_path,
        )
        
        repo_root = get_repo_root()
        
        # 所有路径应该在仓库根目录下
        template_path = resolve_template_path("test.png")
        model_path = resolve_model_path("test.pt")
        data_path = resolve_data_path("test.json")
        
        assert str(template_path).startswith(str(repo_root)) or "image" in str(template_path)
        assert str(model_path).startswith(str(repo_root))
        assert str(data_path).startswith(str(repo_root))


@pytest.mark.integration
class TestConfigSystemIntegration:
    """测试配置系统集成"""
    
    def test_config_imports_across_modules(self):
        """测试跨模块配置导入"""
        # 测试从不同模块导入配置
        from wzry_ai.config import GRID_SIZE, CELL_SIZE
        from wzry_ai.detection.model1_astar_follow import GRID_SIZE as GRID_SIZE_2
        
        # 应该是相同的值
        assert GRID_SIZE == GRID_SIZE_2
    
    def test_config_with_pathfinding(self):
        """测试配置与寻路集成"""
        from wzry_ai.config import GRID_SIZE, CELL_SIZE
        from wzry_ai.detection.model1_astar_follow import convert_to_grid_coordinates
        
        # 测试坐标转换使用配置
        pixel_x = CELL_SIZE * 10
        pixel_y = CELL_SIZE * 20
        grid_x, grid_y = convert_to_grid_coordinates(pixel_x, pixel_y)
        
        assert 0 <= grid_x < GRID_SIZE
        assert 0 <= grid_y < GRID_SIZE


@pytest.mark.integration
class TestDetectionSystemIntegration:
    """测试检测系统集成"""
    
    def test_template_matcher_with_mock_frame(self, mock_gray_frame):
        """测试模板匹配器与模拟帧集成"""
        from wzry_ai.game_manager.template_matcher import TemplateMatcher
        
        matcher = TemplateMatcher(match_scale=0.5, use_mtm=False)
        result = matcher.detect("test_template", mock_gray_frame)
        
        assert result is not None
        assert hasattr(result, "found")
        assert hasattr(result, "confidence")


@pytest.mark.integration
class TestServicesIntegration:
    """测试服务集成"""
    
    @patch('wzry_ai.app.services.init_emulator')
    @patch('wzry_ai.app.services.cv2')
    def test_services_initialization_flow(self, mock_cv2, mock_init_emulator):
        """测试服务初始化流程"""
        from wzry_ai.app.services import GameServices
        
        # 模拟模拟器配置
        mock_config = Mock()
        mock_config.serial = "test-device"
        mock_config.window_title = "Test"
        mock_config.client_size = (1920, 1080)
        mock_init_emulator.return_value = mock_config
        
        services = GameServices()
        assert services is not None
    
    @patch('wzry_ai.app.services.init_emulator')
    @patch('wzry_ai.app.services.cv2')
    def test_services_with_queues(self, mock_cv2, mock_init_emulator):
        """测试服务与队列集成"""
        from wzry_ai.app.services import GameServices
        
        mock_config = Mock()
        mock_config.serial = "test-device"
        mock_config.window_title = "Test"
        mock_config.client_size = (1920, 1080)
        mock_init_emulator.return_value = mock_config
        
        services = GameServices()
        
        # 测试队列可用性
        assert services.skill_queue is not None
        assert services.status_queue is not None
        assert services.model1_data_queue is not None
        assert services.model2_data_queue is not None


@pytest.mark.integration
class TestEndToEndScenarios:
    """端到端场景测试"""
    
    def test_hero_selection_to_skill_logic(self):
        """测试从英雄选择到技能逻辑的完整流程"""
        from wzry_ai.battle.hero_registry import (
            get_skill_logic,
            get_decision_maker,
            has_attach_skill,
        )
        
        hero_name = "瑶"
        
        # 获取技能逻辑
        skill_logic = get_skill_logic(hero_name)
        assert skill_logic is not None
        
        # 获取决策器
        decision_maker = get_decision_maker(hero_name)
        assert decision_maker is not None
        
        # 检查附身技能
        has_attach = has_attach_skill(hero_name)
        assert has_attach is True
    
    def test_resource_loading_pipeline(self):
        """测试资源加载管道"""
        from wzry_ai.utils.resource_resolver import (
            get_runtime_path_resolver,
            resolve_template_path,
        )
        
        resolver = get_runtime_path_resolver()
        
        # 解析模板路径
        template_path = resolver.resolve_template("test.png")
        assert template_path is not None
        
        # 解析英雄头像路径
        hero_path = resolver.resolve_hero_portrait("yao.png")
        assert hero_path is not None
    
    def test_game_initialization_pipeline(self):
        """测试游戏初始化管道"""
        from wzry_ai.app.services import GameServices
        from unittest.mock import patch, Mock
        
        with patch('wzry_ai.app.services.init_emulator') as mock_init_emulator, \
             patch('wzry_ai.app.services.cv2') as mock_cv2, \
             patch('wzry_ai.app.services.TemplateMatcher') as mock_matcher, \
             patch('wzry_ai.app.services.ClickExecutor') as mock_executor, \
             patch('wzry_ai.app.services.GameStateDetector') as mock_detector:
            
            # 模拟配置
            mock_config = Mock()
            mock_config.serial = "test-device"
            mock_config.window_title = "Test"
            mock_config.client_size = (1920, 1080)
            mock_init_emulator.return_value = mock_config
            
            # 创建服务
            services = GameServices()
            
            # 初始化状态检测
            services._init_state_detection()
            
            # 验证所有组件已初始化
            assert services.template_matcher is not None
            assert services.click_executor is not None
            assert services.state_detector is not None
