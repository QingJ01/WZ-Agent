"""
具体技能类型实现模块
实现各种技能类型的具体行为，包括伤害、控制、治疗、增益、附身等技能

[弃用说明] 此模块属于旧版技能体系，当前实际使用的技能逻辑已迁移到
hero_skill_logic_base.py + 各英雄的 *_skill_logic_v2.py 文件。
本模块保留以供 hero_skill_configs.py 中的 SkillConfig 数据结构引用。
"""

# 导入时间模块，用于处理技能冷却和状态超时
import time
# time: 提供time()函数获取当前时间戳

# 导入类型提示
from typing import Optional
# Optional: 可选类型，表示值可能为None

# 从keyboard_controller导入tap函数，用于模拟按键
from wzry_ai.utils.keyboard_controller import tap
# tap: 模拟键盘按键，参数为按键、次数、间隔

# 从skill_base模块导入基类和配置类
from .skill_base import SkillBase, SkillConfig, SkillType, SkillRegistry
# SkillBase: 技能抽象基类，所有技能类继承此类
# SkillConfig: 技能配置数据类
# SkillType: 技能类型枚举
# SkillRegistry: 技能注册表，用于动态创建技能实例

# 从skill_context模块导入技能上下文
from .skill_context import SkillContext
# SkillContext: 技能上下文，封装游戏状态数据


# ================= 从统一按键配置导入 =================
from wzry_ai.config.keys import (
    KEY_ATTACK, KEY_BUY_ITEM,
    KEY_LEVEL_ULT, KEY_LEVEL_1, KEY_LEVEL_2,
)


class DamageSkill(SkillBase):
    """
    伤害技能类 - 对敌人造成伤害的技能
    
    功能描述：
        继承自SkillBase，实现伤害类技能的具体行为
        包括技能释放和普攻管理功能
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化伤害技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        self._last_attack_time = 0  # 上次普攻时间戳，初始化为0
        
    def _do_cast(self, context: SkillContext):
        """
        执行伤害技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文，包含当前游戏状态
            
        功能说明：
            调用tap函数模拟按键，释放技能
        """
        tap(self.key, 1, 0.05)  # 模拟按下技能键，按下1次，间隔0.05秒
        
    def should_basic_attack(self, context: SkillContext) -> bool:
        """
        判断是否应该执行普攻
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示应该普攻，False表示不应该普攻
            
        判断逻辑：
            1. 检查是否处于附身状态，附身时不普攻
            2. 检查是否有敌人，没有敌人时不普攻
            3. 检查距离上次普攻是否超过0.5秒
        """
        if context.is_attached:  # 检查是否处于附身状态
            return False  # 附身时不普攻
        if not context.has_enemy:  # 检查是否有敌人
            return False  # 没有敌人时不普攻
        return time.time() - self._last_attack_time > 0.5  # 检查普攻间隔是否超过0.5秒
        
    def basic_attack(self):
        """
        执行普通攻击
        
        功能说明：
            模拟按下攻击键（空格键），并记录当前时间作为上次攻击时间
        """
        tap(KEY_ATTACK, 1, 0.05)  # 模拟按下空格键进行普攻
        self._last_attack_time = time.time()  # 记录当前时间为上次攻击时间


class ControlSkill(SkillBase):
    """
    控制技能类 - 眩晕、击飞、减速等控制效果的技能
    
    功能描述：
        继承自SkillBase，实现控制类技能的具体行为
        控制技能通常用于限制敌人的行动
    """
    
    def _do_cast(self, context: SkillContext):
        """
        执行控制技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文，包含当前游戏状态
        """
        tap(self.key, 1, 0.05)  # 模拟按下技能键，按下1次，间隔0.05秒


class HealShieldSkill(SkillBase):
    """
    治疗/护盾技能类 - 恢复血量或提供护盾的技能
    
    功能描述：
        继承自SkillBase，实现治疗/护盾类技能的具体行为
        当自身或队友血量低于阈值时触发
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化治疗/护盾技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        # 从配置中获取血量阈值参数，默认为50
        self._hp_threshold = config.trigger_params.get("hp_threshold", 50)
        
    def _check_trigger_conditions(self, context: SkillContext) -> bool:
        """
        检查治疗技能的触发条件
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示满足触发条件，False表示不满足
            
        触发逻辑：
            1. 先调用父类的触发条件检查
            2. 检查自身血量是否低于阈值
            3. 检查是否有队友血量低于阈值
        """
        if not super()._check_trigger_conditions(context):  # 调用父类检查
            return False  # 父类检查不通过，直接返回False
            
        # 检查自身血量是否低于阈值
        if context.is_self_low_hp(self._hp_threshold):
            return True  # 自身低血量，需要治疗
        # 检查是否有队友血量低于阈值
        if context.has_teammate_low_hp(self._hp_threshold):
            return True  # 队友低血量，需要治疗
            
        return False  # 没有低血量目标，不触发
        
    def _do_cast(self, context: SkillContext):
        """
        执行治疗技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文
        """
        tap(self.key, 1, 0.05)  # 模拟按下技能键，按下1次，间隔0.05秒


class BuffSkill(SkillBase):
    """
    增益/Buff技能类 - 为队友提供属性加成的技能
    
    功能描述：
        继承自SkillBase，实现增益类技能的具体行为
        主要用于明世隐等英雄的链接类技能，管理链接状态
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化增益技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        self._link_state = False  # 链接状态标志，初始为False
        self._link_start_time = 0  # 链接开始时间戳，初始为0
        
    def _do_cast(self, context: SkillContext):
        """
        执行增益技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        功能说明：
            释放技能并设置链接状态为True，记录链接开始时间
        """
        tap(self.key, 1, 0.05)  # 模拟按下技能键
        self._link_state = True  # 设置链接状态为已链接
        self._link_start_time = time.time()  # 记录当前时间为链接开始时间
        
    def is_linked(self, timeout: float = 12.0) -> bool:
        """
        检查是否处于链接状态
        
        参数说明：
            timeout: 链接超时时间，默认为12.0秒
            
        返回值说明：
            bool: True表示处于链接状态，False表示链接已断开或超时
            
        检查逻辑：
            1. 检查_link_state标志
            2. 检查链接是否超过超时时间
        """
        if not self._link_state:  # 检查链接状态标志
            return False  # 未链接状态
        # 检查链接是否超时
        if time.time() - self._link_start_time > timeout:
            self._link_state = False  # 超时，更新状态为断开
            return False  # 返回已断开
        return True  # 链接正常
        
    def break_link(self):
        """
        断开链接
        
        功能说明：
            手动断开链接状态，将_link_state设置为False
        """
        self._link_state = False  # 设置链接状态为断开


class AttachSkill(SkillBase):
    """
    位移/附身技能类 - 附身到队友身上的技能
    
    功能描述：
        继承自SkillBase，实现附身类技能的具体行为
        主要用于瑶的大招，包含附身保护期逻辑
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化附身技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        # 从配置获取附身保护期时长，默认为5.0秒
        self._attach_protect_duration = config.trigger_params.get(
            "attach_protect_duration", 5.0
        )
        self._last_attach_time = 0  # 上次附身时间戳，初始为0
        
    def _check_trigger_conditions(self, context: SkillContext) -> bool:
        """
        检查附身技能的触发条件
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示满足触发条件，False表示不满足
            
        触发逻辑：
            1. 调用父类的触发条件检查
            2. 检查是否已处于附身状态
            3. 检查附身保护期（防止频繁附身/脱离）
        """
        if not super()._check_trigger_conditions(context):  # 调用父类检查
            return False  # 父类检查不通过
            
        # 检查是否已处于附身状态
        if context.is_attached:
            return False  # 已经附身了，不能再附身
            
        # 检查附身保护期（防止频繁切换）
        if time.time() - self._last_attach_time < self._attach_protect_duration:
            return False  # 保护期内，不能再次附身
            
        return True  # 满足所有条件，可以附身
        
    def _do_cast(self, context: SkillContext):
        """
        执行附身技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        功能说明：
            释放附身技能并记录当前时间为上次附身时间
        """
        tap(self.key, 1, 0.05)  # 模拟按下技能键
        self._last_attach_time = time.time()  # 记录当前时间为上次附身时间
        
    def get_time_since_last_attach(self) -> float:
        """
        获取距离上次附身的时间
        
        返回值说明：
            float: 距离上次附身的秒数，如果从未附身则返回无穷大
        """
        if self._last_attach_time == 0:  # 检查是否从未附身过
            return float('inf')  # 返回无穷大表示从未附身
        return time.time() - self._last_attach_time  # 计算时间差


class ActiveItemSkill(SkillBase):
    """
    辅助装备主动技能类 - 救赎之翼、奔狼纹章等装备技能
    
    功能描述：
        继承自SkillBase，实现辅助装备主动技能的具体行为
        在紧急情况下（自身危险或队友低血量）触发
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化辅助装备主动技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        # 从配置获取紧急血量阈值，默认为40
        self._emergency_threshold = config.trigger_params.get(
            "emergency_hp_threshold", 40
        )
        
    def _check_trigger_conditions(self, context: SkillContext) -> bool:
        """
        检查辅助装备技能的触发条件
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示满足触发条件，False表示不满足
            
        触发逻辑：
            1. 调用父类的触发条件检查
            2. 检查自身是否处于危险状态
            3. 检查是否有队友血量低于紧急阈值
        """
        if not super()._check_trigger_conditions(context):  # 调用父类检查
            return False  # 父类检查不通过
            
        # 检查自身是否处于危险状态
        if context.is_self_in_danger():
            return True  # 自身危险，触发装备技能
        # 检查是否有队友血量低于紧急阈值
        if context.has_teammate_low_hp(self._emergency_threshold):
            return True  # 队友低血量，触发装备技能
            
        return False  # 不满足触发条件
        
    def _do_cast(self, context: SkillContext):
        """
        执行辅助装备技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文
        """
        tap(self.key, 1, 0.05)  # 模拟按下装备技能键


class SummonerSkill(SkillBase):
    """
    召唤师技能类 - 治疗术、恢复、闪现、眩晕等
    
    功能描述：
        继承自SkillBase，实现召唤师技能的具体行为
        根据技能ID不同执行不同的触发逻辑
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化召唤师技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        # 从配置获取血量阈值，默认为50
        self._hp_threshold = config.trigger_params.get("hp_threshold", 50)
        
    def _check_trigger_conditions(self, context: SkillContext) -> bool:
        """
        检查召唤师技能的触发条件
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示满足触发条件，False表示不满足
            
        触发逻辑：
            治疗术（heal）：自身或队友血量低于阈值时触发
            恢复（recover）：脱战状态且自身血量低于80时触发
        """
        if not super()._check_trigger_conditions(context):  # 调用父类检查
            return False  # 父类检查不通过
            
        # 治疗术触发逻辑
        if self.config.skill_id == "heal":
            if context.is_self_low_hp(self._hp_threshold):  # 检查自身低血量
                return True  # 自身低血量，触发治疗术
            if context.has_teammate_low_hp(self._hp_threshold):  # 检查队友低血量
                return True  # 队友低血量，触发治疗术
                
        # 恢复技能触发逻辑 - 仅在脱战状态下使用
        elif self.config.skill_id == "recover":
            # 检查是否没有敌人且自身血量低于80
            if not context.has_enemy and context.is_self_low_hp(80):
                return True  # 脱战且低血量，触发恢复
                
        return False  # 不满足任何触发条件
        
    def _do_cast(self, context: SkillContext):
        """
        执行召唤师技能释放
        
        参数说明：
            context: SkillContext类型，技能上下文
        """
        tap(self.key, 1, 0.05)  # 模拟按下召唤师技能键


class AutoMaintenanceSkill(SkillBase):
    """
    自动维护技能类 - 买装备、升级技能等自动化操作
    
    功能描述：
        继承自SkillBase，实现自动购买装备和自动升级技能的功能
        这些操作不需要复杂的触发条件，只需要按固定间隔执行
    """
    
    def __init__(self, config: SkillConfig):
        """
        初始化自动维护技能
        
        参数说明：
            config: SkillConfig类型，技能配置对象
        """
        super().__init__(config)  # 调用父类初始化方法
        self._last_buy_time = 0  # 上次购买装备时间戳，初始为0
        self._last_levelup_time = 0  # 上次升级技能时间戳，初始为0
        # 从配置获取购买间隔，默认为3秒
        self._buy_interval = config.trigger_params.get("buy_interval", 3)
        # 从配置获取升级间隔，默认为5秒
        self._levelup_interval = config.trigger_params.get("levelup_interval", 5)
        
    def can_cast(self, context: SkillContext) -> bool:
        """
        检查自动维护技能是否可以执行
        
        参数说明：
            context: SkillContext类型，技能上下文（自动维护技能不使用）
            
        返回值说明：
            bool: True表示可以执行，False表示还在冷却中
            
        功能说明：
            自动维护技能使用自己的冷却逻辑，不依赖父类的冷却检查
            买装备和升级技能按各自的间隔时间独立计算
        """
        if not self._enabled:  # 检查技能是否被启用
            return False  # 技能被禁用，不能执行
            
        current_time = time.time()  # 获取当前时间戳
        
        # 买装备技能冷却检查
        if self.config.skill_id == "buy_item":
            return current_time - self._last_buy_time > self._buy_interval  # 检查是否超过购买间隔
        # 升级技能冷却检查
        elif self.config.skill_id == "level_up":
            return current_time - self._last_levelup_time > self._levelup_interval  # 检查是否超过升级间隔
            
        return False  # 未知的自动维护技能类型
        
    def _do_cast(self, context: SkillContext):
        """
        执行自动维护操作
        
        参数说明：
            context: SkillContext类型，技能上下文（自动维护技能不使用）
            
        功能说明：
            根据技能ID执行对应的自动维护操作
            buy_item: 购买装备
            level_up: 升级技能（按优先级：大招 > 一技能 > 二技能）
        """
        current_time = time.time()  # 获取当前时间戳
        
        # 执行购买装备操作
        if self.config.skill_id == "buy_item":
            tap(KEY_BUY_ITEM, 1, 0.05)  # 模拟按下购买装备键（数字键4）
            self._last_buy_time = current_time  # 记录本次购买时间
            
        # 执行升级技能操作
        elif self.config.skill_id == "level_up":
            # 优先升级顺序：大招 > 一技能 > 二技能
            tap(KEY_LEVEL_ULT, 1, 0.05)  # 先升级大招（数字键3）
            tap(KEY_LEVEL_1, 1, 0.05)  # 再升级一技能（数字键1）
            tap(KEY_LEVEL_2, 1, 0.05)  # 最后升级二技能（数字键2）
            self._last_levelup_time = current_time  # 记录本次升级时间


# ================= 技能类型注册函数 =================
def register_skill_types():
    """
    注册所有技能类型到技能注册表
    
    功能说明：
        将各个技能类与对应的SkillType枚举值关联，
        使得SkillRegistry可以根据SkillType动态创建技能实例
        
    注册映射关系：
        DAMAGE -> DamageSkill（伤害技能）
        CONTROL -> ControlSkill（控制技能）
        HEAL_SHIELD -> HealShieldSkill（治疗/护盾技能）
        BUFF -> BuffSkill（增益技能）
        ATTACH -> AttachSkill（附身技能）
        ACTIVE_ITEM -> ActiveItemSkill（装备主动技能）
        SUMMONER -> SummonerSkill（召唤师技能）
    """
    SkillRegistry.register(SkillType.DAMAGE, DamageSkill)  # 注册伤害技能类型
    SkillRegistry.register(SkillType.CONTROL, ControlSkill)  # 注册控制技能类型
    SkillRegistry.register(SkillType.HEAL_SHIELD, HealShieldSkill)  # 注册治疗/护盾技能类型
    SkillRegistry.register(SkillType.BUFF, BuffSkill)  # 注册增益技能类型
    SkillRegistry.register(SkillType.ATTACH, AttachSkill)  # 注册附身技能类型
    SkillRegistry.register(SkillType.ACTIVE_ITEM, ActiveItemSkill)  # 注册装备主动技能类型
    SkillRegistry.register(SkillType.SUMMONER, SummonerSkill)  # 注册召唤师技能类型


# 模块加载时自动执行技能类型注册
register_skill_types()  # 调用注册函数，建立技能类型与类的映射关系
