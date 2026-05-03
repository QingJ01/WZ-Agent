"""
英雄逻辑注册表 - 动态英雄技能/决策/移动逻辑派发

根据中文英雄名称（与 state_detector 的 selected_hero 一致），
延迟导入并实例化对应的技能逻辑类和战斗决策器。
"""

import importlib
from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)

# 英雄注册表：中文名 -> 模块/类/属性信息
HERO_REGISTRY = {
    "瑶": {
        "skill_module": "wzry_ai.skills.yao_skill_logic_v2",
        "skill_class": "YaoSkillLogic",
        "decision_module": "wzry_ai.battle.yao_decision",
        "decision_class": "YaoDecisionMaker",
        "has_attach": True,
    },
    "蔡文姬": {
        "skill_module": "wzry_ai.skills.caiwenji_skill_logic_v2",
        "skill_class": "CaiwenjiSkillLogic",
        "decision_module": "wzry_ai.battle.generic_support_decision",
        "decision_class": "GenericSupportDecisionMaker",
        "has_attach": False,
    },
    "明世隐": {
        "skill_module": "wzry_ai.skills.mingshiyin_skill_logic_v2",
        "skill_class": "MingshiyinSkillLogic",
        "decision_module": "wzry_ai.battle.generic_support_decision",
        "decision_class": "GenericSupportDecisionMaker",
        "has_attach": False,
    },
}

# 支持的英雄列表
SUPPORTED_HEROES = list(HERO_REGISTRY.keys())


def _import_class(module_path: str, class_name: str):
    """延迟导入并返回类对象"""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class _GenericSkillAdapter:
    """
    GenericSkillManager 的适配器，兼容 HeroSkillLogicBase 的 paused 接口。
    
    Master_Auto.py 通过 .paused 属性控制技能逻辑的暂停/恢复，
    但 GenericSkillManager 使用 .is_running 属性。此适配器桥接两套接口。
    """
    
    def __init__(self):
        from wzry_ai.skills.generic_skill_manager import GenericSkillManager
        self._manager = GenericSkillManager()
        self._paused = False
    
    @property
    def paused(self):
        return self._paused
    
    @paused.setter
    def paused(self, value):
        self._paused = value
    
    def run(self, queue):
        """运行技能逻辑，内部委托给 GenericSkillManager"""
        self._manager.run(queue)


def get_skill_logic(hero_name: str):
    """
    根据英雄名称获取技能逻辑实例。
    
    参数：
        hero_name: 中文英雄名称（如 "瑶"、"蔡文姬"、"明世隐"）
        
    返回：
        技能逻辑实例（HeroSkillLogicBase 子类或 GenericSkillAdapter）
    """
    entry = HERO_REGISTRY.get(hero_name)
    if entry is None:
        logger.warning(f"未注册的英雄 '{hero_name}'，使用通用技能管理器")
        return _GenericSkillAdapter()
    
    try:
        cls = _import_class(entry["skill_module"], entry["skill_class"])
        instance = cls()
        logger.info(f"已加载英雄技能逻辑: {hero_name} -> {entry['skill_class']}")
        return instance
    except (ImportError, AttributeError) as e:
        logger.error(f"加载英雄 '{hero_name}' 技能逻辑失败: {e}，回退到通用管理器")
        return _GenericSkillAdapter()


def get_decision_maker(hero_name: str):
    """
    根据英雄名称获取战斗决策器实例。
    
    参数：
        hero_name: 中文英雄名称
        
    返回：
        决策器实例（YaoDecisionMaker 或 GenericSupportDecisionMaker）
    """
    entry = HERO_REGISTRY.get(hero_name)
    if entry is None:
        logger.warning(f"未注册的英雄 '{hero_name}'，使用通用决策器")
        from wzry_ai.battle.generic_support_decision import GenericSupportDecisionMaker
        return GenericSupportDecisionMaker()
    
    try:
        cls = _import_class(entry["decision_module"], entry["decision_class"])
        instance = cls()
        logger.info(f"已加载英雄决策器: {hero_name} -> {entry['decision_class']}")
        return instance
    except (ImportError, AttributeError) as e:
        logger.error(f"加载英雄 '{hero_name}' 决策器失败: {e}，回退到通用决策器")
        from wzry_ai.battle.generic_support_decision import GenericSupportDecisionMaker
        return GenericSupportDecisionMaker()


def has_attach_skill(hero_name: str) -> bool:
    """
    查询英雄是否具备附身技能。
    
    参数：
        hero_name: 中文英雄名称（可为 None）
        
    返回：
        True 表示有附身技能（仅瑶），False 表示没有
    """
    if hero_name is None:
        return False
    entry = HERO_REGISTRY.get(hero_name)
    if entry is None:
        return False
    return entry.get("has_attach", False)


def get_hero_name_or_default(hero_name: str) -> str:
    """
    获取英雄名称，若为 None 或空则返回默认英雄。
    
    参数：
        hero_name: 中文英雄名称（可为 None）
        
    返回：
        有效的中文英雄名称
    """
    if hero_name:
        return hero_name
    from wzry_ai.config import DEFAULT_SUPPORT_HERO
    logger.info(f"未指定英雄，使用默认英雄: {DEFAULT_SUPPORT_HERO}")
    return DEFAULT_SUPPORT_HERO
