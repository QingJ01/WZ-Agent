"""测试英雄注册表模块"""

import pytest
from wzry_ai.battle.hero_registry import (
    HERO_REGISTRY,
    SUPPORTED_HEROES,
    get_skill_logic,
    get_decision_maker,
    has_attach_skill,
    get_hero_name_or_default,
)


class TestHeroRegistry:
    """测试英雄注册表"""

    def test_hero_registry_structure(self):
        """测试注册表结构完整性"""
        assert isinstance(HERO_REGISTRY, dict)
        assert len(HERO_REGISTRY) > 0

        for hero_name, config in HERO_REGISTRY.items():
            assert "skill_module" in config
            assert "skill_class" in config
            assert "decision_module" in config
            assert "decision_class" in config
            assert "has_attach" in config
            assert isinstance(config["has_attach"], bool)

    def test_supported_heroes_list(self):
        """测试支持的英雄列表"""
        assert isinstance(SUPPORTED_HEROES, list)
        assert len(SUPPORTED_HEROES) > 0
        assert "瑶" in SUPPORTED_HEROES
        assert "蔡文姬" in SUPPORTED_HEROES
        assert "明世隐" in SUPPORTED_HEROES

    def test_yao_configuration(self):
        """测试瑶的配置"""
        yao_config = HERO_REGISTRY.get("瑶")
        assert yao_config is not None
        assert yao_config["skill_module"] == "wzry_ai.skills.yao_skill_logic_v2"
        assert yao_config["skill_class"] == "YaoSkillLogic"
        assert yao_config["decision_module"] == "wzry_ai.battle.yao_decision"
        assert yao_config["decision_class"] == "YaoDecisionMaker"
        assert yao_config["has_attach"] is True

    def test_caiwenji_configuration(self):
        """测试蔡文姬的配置"""
        caiwenji_config = HERO_REGISTRY.get("蔡文姬")
        assert caiwenji_config is not None
        assert caiwenji_config["has_attach"] is False

    def test_mingshiyin_configuration(self):
        """测试明世隐的配置"""
        mingshiyin_config = HERO_REGISTRY.get("明世隐")
        assert mingshiyin_config is not None
        assert mingshiyin_config["has_attach"] is False


class TestGetSkillLogic:
    """测试获取技能逻辑"""

    def test_get_skill_logic_yao(self):
        """测试获取瑶的技能逻辑"""
        skill_logic = get_skill_logic("瑶")
        assert skill_logic is not None
        assert hasattr(skill_logic, "paused")

    def test_get_skill_logic_caiwenji(self):
        """测试获取蔡文姬的技能逻辑"""
        skill_logic = get_skill_logic("蔡文姬")
        assert skill_logic is not None
        assert hasattr(skill_logic, "paused")

    def test_get_skill_logic_mingshiyin(self):
        """测试获取明世隐的技能逻辑"""
        skill_logic = get_skill_logic("明世隐")
        assert skill_logic is not None
        assert hasattr(skill_logic, "paused")

    def test_get_skill_logic_unknown_hero(self):
        """测试获取未知英雄的技能逻辑（应返回通用管理器）"""
        skill_logic = get_skill_logic("未知英雄")
        assert skill_logic is not None
        # 应该返回通用适配器
        assert hasattr(skill_logic, "paused")

    def test_get_skill_logic_none(self):
        """测试空英雄名时回退到通用技能逻辑"""
        skill_logic = get_skill_logic("")
        assert skill_logic is not None


class TestGetDecisionMaker:
    """测试获取决策器"""

    def test_get_decision_maker_yao(self):
        """测试获取瑶的决策器"""
        decision_maker = get_decision_maker("瑶")
        assert decision_maker is not None

    def test_get_decision_maker_caiwenji(self):
        """测试获取蔡文姬的决策器"""
        decision_maker = get_decision_maker("蔡文姬")
        assert decision_maker is not None

    def test_get_decision_maker_mingshiyin(self):
        """测试获取明世隐的决策器"""
        decision_maker = get_decision_maker("明世隐")
        assert decision_maker is not None

    def test_get_decision_maker_unknown_hero(self):
        """测试获取未知英雄的决策器（应返回通用决策器）"""
        decision_maker = get_decision_maker("未知英雄")
        assert decision_maker is not None

    def test_get_decision_maker_none(self):
        """测试空英雄名时回退到通用决策器"""
        decision_maker = get_decision_maker("")
        assert decision_maker is not None


class TestHasAttachSkill:
    """测试附身技能查询"""

    def test_has_attach_skill_yao(self):
        """测试瑶有附身技能"""
        assert has_attach_skill("瑶") is True

    def test_has_attach_skill_caiwenji(self):
        """测试蔡文姬没有附身技能"""
        assert has_attach_skill("蔡文姬") is False

    def test_has_attach_skill_mingshiyin(self):
        """测试明世隐没有附身技能"""
        assert has_attach_skill("明世隐") is False

    def test_has_attach_skill_unknown_hero(self):
        """测试未知英雄没有附身技能"""
        assert has_attach_skill("未知英雄") is False

    def test_has_attach_skill_none(self):
        """测试空英雄名返回False"""
        assert has_attach_skill("") is False


class TestGetHeroNameOrDefault:
    """测试获取英雄名称或默认值"""

    def test_get_hero_name_or_default_with_name(self):
        """测试提供英雄名称时返回该名称"""
        result = get_hero_name_or_default("瑶")
        assert result == "瑶"

    def test_get_hero_name_or_default_with_none(self):
        """测试未提供英雄名称时返回默认值"""
        result = get_hero_name_or_default("")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_hero_name_or_default_with_empty_string(self):
        """测试空字符串时返回默认值"""
        result = get_hero_name_or_default("")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
