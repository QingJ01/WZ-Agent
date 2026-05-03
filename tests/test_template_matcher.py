"""测试模板匹配器模块"""

import pytest
import numpy as np
import cv2
from wzry_ai.game_manager.template_matcher import (
    MatchResult,
    TemplateMatcher,
)


class TestMatchResult:
    """测试MatchResult数据类"""
    
    def test_match_result_creation(self):
        """测试创建匹配结果"""
        result = MatchResult(
            found=True,
            confidence=0.95,
            location=(100, 200),
            size=(50, 50),
            template_name="test_template"
        )
        assert result.found is True
        assert result.confidence == 0.95
        assert result.location == (100, 200)
        assert result.size == (50, 50)
        assert result.template_name == "test_template"
    
    def test_match_result_default_template_name(self):
        """测试默认模板名称"""
        result = MatchResult(
            found=False,
            confidence=0.0,
            location=(0, 0),
            size=(0, 0)
        )
        assert result.template_name == ""


class TestTemplateMatcher:
    """测试TemplateMatcher类"""
    
    @pytest.fixture
    def matcher(self):
        """创建测试用的模板匹配器"""
        return TemplateMatcher(match_scale=0.5, use_mtm=False)
    
    @pytest.fixture
    def test_image(self):
        """创建测试图像"""
        return np.zeros((1080, 1920), dtype=np.uint8)
    
    @pytest.fixture
    def test_template(self):
        """创建测试模板"""
        return np.ones((50, 50), dtype=np.uint8) * 255
    
    def test_matcher_initialization(self, matcher):
        """测试匹配器初始化"""
        assert matcher is not None
        assert matcher.match_scale == 0.5
        assert isinstance(matcher.templates, dict)
        assert isinstance(matcher.stats, dict)
    
    def test_register_template_success(self, matcher, tmp_path):
        """测试成功注册模板"""
        # 创建临时模板文件
        template_path = tmp_path / "test_template.png"
        test_img = np.ones((50, 50), dtype=np.uint8) * 255
        cv2.imwrite(str(template_path), test_img)
        
        # 注册模板
        result = matcher.register_template("test_template", str(template_path))
        assert result is True
        assert "test_template" in matcher.templates
    
    def test_register_template_file_not_found(self, matcher):
        """测试注册不存在的模板文件"""
        result = matcher.register_template("nonexistent", "/nonexistent/path.png")
        assert result is False
    
    def test_detect_template_not_found(self, matcher, test_image):
        """测试检测不存在的模板"""
        result = matcher.detect("nonexistent_template", test_image)
        assert result.found is False
        assert result.confidence == 0.0
    
    def test_detect_with_registered_template(self, matcher, test_image, test_template):
        """测试检测已注册的模板"""
        # 手动添加模板到缓存
        matcher.templates["test_template"] = test_template
        
        # 执行检测
        result = matcher.detect("test_template", test_image, min_confidence=0.5)
        assert isinstance(result, MatchResult)
        assert result.template_name == "test_template"
    
    def test_set_last_frame(self, matcher):
        """测试设置上一帧"""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        matcher.set_last_frame(frame)
        assert matcher._last_frame is not None
        assert matcher._last_frame.shape == frame.shape
    
    def test_set_last_frame_none(self, matcher):
        """测试设置None帧"""
        matcher.set_last_frame(None)
        assert matcher._last_frame is None
    
    def test_reset_screen_state(self, matcher):
        """测试重置界面状态"""
        matcher._current_screen = "TEST_SCREEN"
        matcher._screen_state_frames = 10
        
        matcher.reset_screen_state()
        
        assert matcher._current_screen is None
        assert matcher._screen_state_frames == 0
    
    def test_stats_tracking(self, matcher, test_image):
        """测试统计信息跟踪"""
        initial_calls = matcher.stats["total_calls"]
        
        # 执行几次检测
        matcher.detect("nonexistent", test_image)
        matcher.detect("nonexistent", test_image)
        
        assert matcher.stats["total_calls"] == initial_calls + 2
    
    def test_detect_group_empty_list(self, matcher, test_image):
        """测试检测空模板列表"""
        results = matcher.detect_group([], test_image)
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_detect_group_single_template(self, matcher, test_image, test_template):
        """测试检测单个模板组"""
        matcher.templates["test_template"] = test_template
        results = matcher.detect_group(["test_template"], test_image)
        assert isinstance(results, list)
    
    def test_rgb_check_templates_set(self, matcher):
        """测试RGB验证模板集合"""
        assert isinstance(matcher.rgb_check_templates, set)
        assert "ai_standard" in matcher.rgb_check_templates
        assert "lane_support" in matcher.rgb_check_templates
    
    def test_screen_template_groups(self, matcher):
        """测试界面模板分组"""
        assert isinstance(matcher.screen_template_groups, dict)
        assert "AI_MODE" in matcher.screen_template_groups
        assert "LOBBY" in matcher.screen_template_groups
        
        # 验证每个组的结构
        for group_name, group_config in matcher.screen_template_groups.items():
            assert "indicators" in group_config
            assert "templates" in group_config
            assert isinstance(group_config["indicators"], list)
            assert isinstance(group_config["templates"], list)
    
    def test_detect_smart_no_state(self, matcher, test_image):
        """测试智能检测（无状态）"""
        results = matcher.detect_smart(test_image)
        assert isinstance(results, list)
    
    def test_cache_mechanism(self, matcher, test_image):
        """测试缓存机制"""
        # 添加一个测试模板
        import numpy as np
        test_template = np.ones((50, 50), dtype=np.uint8) * 255
        matcher.templates["test_template"] = test_template
        
        # 第一次检测
        result1 = matcher.detect("test_template", test_image)
        cache_hits_before = matcher.stats["cache_hits"]
        
        # 第二次检测同一帧同一模板（应命中缓存）
        result2 = matcher.detect("test_template", test_image)
        cache_hits_after = matcher.stats["cache_hits"]
        
        # 验证缓存命中
        assert cache_hits_after > cache_hits_before
        assert result1.found == result2.found
        assert result1.confidence == result2.confidence


class TestTemplateMatcherWithROI:
    """测试带ROI的模板匹配"""
    
    @pytest.fixture
    def matcher(self):
        """创建测试用的模板匹配器"""
        return TemplateMatcher(match_scale=0.5, use_mtm=False)
    
    @pytest.fixture
    def test_image(self):
        """创建测试图像"""
        return np.zeros((1080, 1920), dtype=np.uint8)
    
    def test_detect_with_roi_disabled(self, matcher, test_image):
        """测试禁用ROI的检测"""
        result = matcher.detect("test_template", test_image, use_roi=False)
        assert isinstance(result, MatchResult)
    
    def test_detect_with_roi_enabled(self, matcher, test_image):
        """测试启用ROI的检测"""
        result = matcher.detect("test_template", test_image, use_roi=True)
        assert isinstance(result, MatchResult)


class TestTemplateMatcherEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture
    def matcher(self):
        """创建测试用的模板匹配器"""
        return TemplateMatcher(match_scale=0.5, use_mtm=False)
    
    def test_detect_with_very_small_image(self, matcher):
        """测试非常小的图像"""
        small_image = np.zeros((10, 10), dtype=np.uint8)
        result = matcher.detect("test_template", small_image)
        assert isinstance(result, MatchResult)
    
    def test_detect_with_large_template(self, matcher):
        """测试模板比图像大的情况"""
        small_image = np.zeros((50, 50), dtype=np.uint8)
        large_template = np.ones((100, 100), dtype=np.uint8) * 255
        matcher.templates["large_template"] = large_template
        
        result = matcher.detect("large_template", small_image)
        assert result.found is False
    
    def test_detect_with_zero_confidence(self, matcher, test_image=None):
        """测试零置信度阈值"""
        if test_image is None:
            test_image = np.zeros((100, 100), dtype=np.uint8)
        result = matcher.detect("test_template", test_image, min_confidence=0.0)
        assert isinstance(result, MatchResult)
    
    def test_detect_with_high_confidence(self, matcher, test_image=None):
        """测试高置信度阈值"""
        if test_image is None:
            test_image = np.zeros((100, 100), dtype=np.uint8)
        result = matcher.detect("test_template", test_image, min_confidence=0.99)
        assert isinstance(result, MatchResult)
