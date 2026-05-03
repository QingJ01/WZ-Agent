"""
通用技能管理器模块 - 为非支持英雄提供基础技能释放能力
适用于没有在hero_skill_configs中配置的普通英雄
Q/E/R 统一为伤害技能，按优先级释放
"""

# 导入时间模块
import time
# time: 提供时间相关功能

# 导入日志模块
import logging
# logging: 提供日志记录功能

# 导入类型提示相关类
from typing import Dict, Optional, Tuple, List
# Dict: 字典类型
# Optional: 可选类型
# Tuple: 元组类型
# List: 列表类型

# 从dataclasses模块导入数据类工具
from dataclasses import dataclass, field
# dataclass: 数据类装饰器
# field: 字段定义

# 从queue模块导入队列相关类
from queue import Queue, Empty
# Queue: 线程安全的数据队列
# Empty: 队列空异常

# 从keyboard_controller导入tap函数
from wzry_ai.utils.keyboard_controller import tap
# tap: 模拟键盘按键

# 从logging_utils导入日志设置函数
from wzry_ai.utils.logging_utils import setup_colored_logger
# setup_colored_logger: 设置带颜色的日志记录器

# 设置模块日志记录器
logger = setup_colored_logger(__name__)
# __name__: 当前模块名称，作为日志记录器名称


# ========== 统一距离配置常量 ==========
UNIFIED_RANGES = {
    "skill_range": 600,      # 统一技能距离：600像素，适用于大多数技能
    "basic_attack": 550,     # 普攻距离：550像素
    "enemy_detect": 900,     # 敌人检测距离：900像素
}


# ========== 通用技能配置常量 ==========
GENERIC_SKILL_CONFIG = {
    "Q": {  # 一技能配置
        "key": "q",  # 按键：q键
        "name": "一技能",  # 技能名称
        "cooldown": 3.0,  # 冷却时间：3秒
        "range": UNIFIED_RANGES["skill_range"],  # 技能范围：使用统一范围
        "priority": 2,  # 优先级：2（中等优先级）
    },
    "E": {  # 二技能配置
        "key": "e",  # 按键：e键
        "name": "二技能",  # 技能名称
        "cooldown": 3.0,  # 冷却时间：3秒
        "range": UNIFIED_RANGES["skill_range"],  # 技能范围：使用统一范围
        "priority": 3,  # 优先级：3（较低优先级）
    },
    "R": {  # 大招配置
        "key": "r",  # 按键：r键
        "name": "大招",  # 技能名称
        "cooldown": 3.0,  # 冷却时间：3秒
        "range": UNIFIED_RANGES["skill_range"],  # 技能范围：使用统一范围
        "priority": 1,  # 优先级：1（最高优先级）
    },
    "heal": {  # 治疗术配置
        "key": "f",  # 按键：f键
        "name": "治疗术",  # 技能名称
        "cooldown": 15.0,  # 冷却时间：15秒
        "range": 0,  # 技能范围：0（范围效果）
        "priority": 1,  # 优先级：1（最高优先级）
    },
}


@dataclass
class SkillContext:
    """
    技能上下文类 - 包含释放技能所需的游戏状态
    
    功能描述：
        使用dataclass定义技能上下文数据结构
        封装了游戏状态信息，用于技能释放判断
    """
    
    # ========== 自身状态字段 ==========
    self_health: Optional[float] = None  # 自身血量，None表示未知
    self_position: Optional[Tuple[float, float]] = None  # 自身位置坐标(x, y)，None表示未知
    
    # ========== 队友状态字段 ==========
    team_health: List[float] = field(default_factory=list)  # 队友血量列表
    team_positions: List[Tuple[float, float]] = field(default_factory=list)  # 队友位置列表
    
    # ========== 敌人状态字段 ==========
    enemy_positions: List[Tuple[float, float]] = field(default_factory=list)  # 敌人位置列表
    
    # ========== 战斗状态字段 ==========
    is_attached: bool = False  # 是否处于附身状态
    
    @property
    def has_enemy(self) -> bool:
        """
        属性：是否有敌人
        
        返回值说明：
            bool: True表示enemy_positions列表不为空，存在敌人
        """
        return len(self.enemy_positions) > 0  # 检查敌人位置列表长度
    
    @property
    def closest_enemy_distance(self) -> float:
        """
        属性：最近敌人的距离
        
        返回值说明：
            float: 返回最近敌人的欧几里得距离（像素），
                   如果没有自身位置或敌人则返回无穷大
        """
        if not self.self_position or not self.enemy_positions:  # 检查必要数据是否存在
            return float('inf')  # 数据不足，返回无穷大
        # 计算到每个敌人的距离，使用欧几里得距离公式
        return min(
            ((self.self_position[0] - e[0]) ** 2 + (self.self_position[1] - e[1]) ** 2) ** 0.5
            for e in self.enemy_positions
        )
    
    def is_self_low_hp(self, threshold: float = 40) -> bool:
        """
        判断自身是否低血量
        
        参数说明：
            threshold: 血量阈值，默认为40，低于此值视为低血量
            
        返回值说明：
            bool: True表示自身血量低于阈值，False表示血量正常或未知
        """
        return self.self_health is not None and self.self_health < threshold  # 检查血量是否低于阈值
    
    def has_teammate_low_hp(self, threshold: float = 40) -> bool:
        """
        判断是否有队友低血量
        
        参数说明：
            threshold: 血量阈值，默认为40，低于此值视为低血量
            
        返回值说明：
            bool: True表示至少有一个队友血量低于阈值
        """
        return any(hp < threshold for hp in self.team_health)  # 使用any检查是否有低血量队友
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SkillContext":
        """
        类方法：从字典创建SkillContext实例
        
        参数说明：
            data: 包含游戏状态的字典
            
        返回值说明：
            SkillContext: 根据字典数据创建的上下文实例
        """
        return cls(
            self_health=data.get('self_health'),  # 从字典获取自身血量
            self_position=data.get('self_position'),  # 从字典获取自身位置
            team_health=data.get('team_health', []),  # 从字典获取队友血量，默认为空列表
            team_positions=data.get('team_positions', []),  # 从字典获取队友位置，默认为空列表
            enemy_positions=data.get('enemy_positions', []),  # 从字典获取敌人位置，默认为空列表
            is_attached=data.get('is_attached', False),  # 从字典获取附身状态，默认为False
        )


class GenericSkillManager:
    """
    通用技能管理器类
    
    功能描述：
        为没有在hero_skill_configs中配置的英雄提供基础技能管理能力
        Q/E/R 统一视为伤害技能，按优先级释放
        适用于大多数普通英雄的简化技能管理
    """
    
    # 类常量：技能释放优先级顺序（数字越小优先级越高，越早检查）
    SKILL_ORDER = ["heal", "R", "Q", "E"]  # 治疗术 > 大招 > 一技能 > 二技能
    
    def __init__(self):
        """
        初始化通用技能管理器
        
        功能说明：
            初始化冷却时间字典、运行标志和普攻时间记录
        """
        self.cooldowns: Dict[str, float] = {}  # 技能冷却字典，key为skill_id，value为下次可用时间戳
        self.is_running = False  # 运行标志，控制主循环是否继续
        self._last_attack_time = 0  # 上次普攻时间戳
        
        logger.info("[GenericSkill] 通用技能管理器初始化完成")  # 输出初始化日志
    
    def _is_ready(self, skill_id: str, cooldown: float) -> bool:
        """
        内部方法：检查技能是否冷却完成
        
        参数说明：
            skill_id: 技能ID字符串
            cooldown: 技能冷却时间（秒）
            
        返回值说明：
            bool: True表示技能已冷却完成，可以释放；False表示还在冷却中
        """
        if skill_id not in self.cooldowns:  # 检查是否首次使用
            return True  # 首次使用，直接返回True
        return time.time() >= self.cooldowns[skill_id]  # 比较当前时间与下次可用时间
    
    def _cast(self, skill_id: str):
        """
        内部方法：执行技能释放
        
        参数说明：
            skill_id: 技能ID字符串
            
        功能说明：
            根据技能ID获取配置，模拟按键，并记录冷却时间
        """
        config = GENERIC_SKILL_CONFIG[skill_id]  # 从配置字典获取技能配置
        key = config["key"]  # 获取技能按键
        cooldown = config["cooldown"]  # 获取技能冷却时间
        
        # 发送按键指令
        tap(key, 1, 0.05)  # 模拟按下按键，按下1次，间隔0.05秒
        
        # 记录技能冷却（当前时间 + 冷却时间 = 下次可用时间）
        self.cooldowns[skill_id] = time.time() + cooldown
        
        logger.debug(f"[GenericSkill] 释放 {config['name']} (按键: {key})")  # 输出释放日志
    
    def _should_cast(self, skill_id: str, context: SkillContext) -> bool:
        """
        内部方法：判断是否应该释放技能
        
        参数说明：
            skill_id: 技能ID字符串
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示应该释放，False表示不应该释放
            
        判断逻辑：
            1. 检查技能冷却
            2. 治疗技能：检查是否紧急低血量
            3. Q/E/R技能：检查是否有敌人在范围内
        """
        config = GENERIC_SKILL_CONFIG[skill_id]  # 获取技能配置
        
        # 检查技能是否在冷却中
        if not self._is_ready(skill_id, config["cooldown"]):
            return False  # 技能还在冷却，不能释放
        
        # 治疗技能触发逻辑：紧急低血量
        if skill_id == "heal":
            return context.is_self_low_hp(40) or context.has_teammate_low_hp(40)  # 自身或队友血量低于40
        
        # Q/E/R技能触发逻辑：有敌人在范围内
        if not context.has_enemy:  # 检查是否有敌人
            return False  # 没有敌人，不释放伤害技能
        
        return context.closest_enemy_distance <= config["range"]  # 检查最近敌人是否在技能范围内
    
    def process(self, context: SkillContext):
        """
        处理技能释放的主方法
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        返回值说明：
            bool: True表示本轮已释放技能，False表示没有释放技能
            
        功能说明：
            按优先级顺序检查每个技能，满足条件就释放
            如果没有技能可释放，尝试执行普攻
        """
        # 按优先级顺序检查技能
        for skill_id in self.SKILL_ORDER:  # 遍历优先级列表
            if self._should_cast(skill_id, context):  # 检查是否应该释放
                self._cast(skill_id)  # 执行技能释放
                return True  # 本轮已释放技能，返回True
        
        # 没有技能可释放，尝试普攻
        self._try_basic_attack(context)  # 调用普攻方法
        return False  # 本轮未释放技能，返回False
    
    def _try_basic_attack(self, context: SkillContext):
        """
        内部方法：尝试执行普通攻击
        
        参数说明：
            context: SkillContext类型，技能上下文
            
        功能说明：
            检查普攻条件并执行普攻：
            1. 检查是否有敌人且不在附身状态
            2. 检查是否在普攻范围内
            3. 检查普攻间隔（0.8秒）
        """
        # 检查是否有敌人且不在附身状态
        if not context.has_enemy or context.is_attached:
            return  # 没有敌人或处于附身状态，不普攻
        
        # 检查普攻距离
        if context.closest_enemy_distance > UNIFIED_RANGES["basic_attack"]:
            return  # 敌人超出普攻范围，不普攻
        
        # 检查普攻间隔（0.8秒）
        current_time = time.time()  # 获取当前时间
        if current_time - self._last_attack_time < 0.8:
            return  # 距离上次普攻不足0.8秒，不普攻
        
        # 执行普攻
        tap('space', 1, 0.05)  # 模拟按下空格键（普攻键）
        self._last_attack_time = current_time  # 记录本次普攻时间
        logger.debug("[GenericSkill] 执行普攻")  # 输出普攻日志
    
    def run(self, skill_queue: Queue):
        """
        主循环方法 - 从队列接收状态并处理技能
        
        参数说明：
            skill_queue: Queue类型，技能队列，接收来自跟随系统的状态更新
            
        功能说明：
            持续运行，从队列获取数据并调用process方法处理技能
            队列为空时继续等待，异常处理确保循环不会中断
        """
        self.is_running = True  # 设置运行标志为True
        logger.info("[GenericSkill] 技能逻辑主循环启动")  # 输出启动日志
        
        while self.is_running:  # 主循环，直到is_running被设为False
            try:
                # 从队列获取状态（阻塞等待，超时1秒）
                data = skill_queue.get(timeout=1.0)
                
                if isinstance(data, dict):  # 检查数据是否为字典类型
                    context = SkillContext.from_dict(data)  # 从字典创建技能上下文
                    self.process(context)  # 调用process处理技能
                    
            except Empty:  # 队列空异常（超时）
                continue  # 继续下一次循环等待
            except (ValueError, AttributeError, RuntimeError) as e:  # 捕获其他异常
                logger.error(f"[GenericSkill] 错误: {e}")  # 输出错误日志
        
        logger.info("[GenericSkill] 技能逻辑主循环结束")  # 输出结束日志
    
    def stop(self):
        """
        停止技能管理器
        
        功能说明：
            将is_running标志设置为False，使主循环结束
        """
        self.is_running = False  # 设置运行标志为False
        logger.info("[GenericSkill] 停止技能管理器")  # 输出停止日志
    
    def get_cooldown_status(self) -> Dict[str, float]:
        """
        获取所有技能的冷却状态
        
        返回值说明：
            Dict[str, float]: 技能冷却状态字典，key为skill_id，value为剩余冷却时间（秒）
        """
        current_time = time.time()  # 获取当前时间
        return {
            skill_id: max(0, ready_time - current_time)  # 计算剩余时间，最小为0
            for skill_id, ready_time in self.cooldowns.items()  # 遍历冷却字典
        }


def create_generic_skill_logic():
    """
    创建通用技能逻辑的便捷函数
    
    返回值说明：
        function: 技能逻辑运行函数，接受skill_queue参数
        
    功能说明：
        返回一个包装函数，用于在新线程中启动技能管理器
    """
    def skill_logic_wrapper(skill_queue: Queue):
        """
        技能逻辑包装函数
        
        参数说明：
            skill_queue: Queue类型，技能数据队列
        """
        manager = GenericSkillManager()  # 创建通用技能管理器实例
        manager.run(skill_queue)  # 启动主循环
    
    return skill_logic_wrapper  # 返回包装函数


# ========== 测试代码区域 ==========
if __name__ == "__main__":
    # 当直接运行此文件时执行的测试代码
    logger.info("=" * 60)  # 输出分隔线
    logger.info("通用技能管理器测试")  # 输出测试标题
    logger.info("=" * 60)  # 输出分隔线
    
    logger.info("技能配置:")  # 输出配置标题
    for skill_id, config in GENERIC_SKILL_CONFIG.items():  # 遍历技能配置
        logger.info(f"  {skill_id}: {config['name']}")  # 输出技能ID和名称
        logger.info(f"    按键: {config['key']}, 冷却: {config['cooldown']}s, 范围: {config['range']}px")  # 输出详细配置
    
    logger.info("统一距离配置:")  # 输出距离配置标题
    for key, value in UNIFIED_RANGES.items():  # 遍历距离配置
        logger.info(f"  {key}: {value}px")  # 输出距离配置
    
    logger.info(f"技能释放优先级: {GenericSkillManager.SKILL_ORDER}")  # 输出优先级顺序
    
    logger.info("=" * 60)  # 输出分隔线
    logger.info("测试完成")  # 输出完成信息
    logger.info("=" * 60)  # 输出分隔线
