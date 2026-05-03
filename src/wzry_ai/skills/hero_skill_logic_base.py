"""
英雄技能逻辑基类

提供所有英雄技能逻辑的公共基础设施，包括：
- 键位常量定义
- 通用初始化（计时器、状态标志）
- 工具方法（坐标转换、距离判断、技能释放）
- 自动维护逻辑（买装备、升级技能）
- 主循环框架
- 椭圆范围判断、冷却检查等通用工具

子类只需实现 check_and_use_skills() 方法即可。
"""

import time
from abc import ABC, abstractmethod
from queue import Empty

from wzry_ai.utils.keyboard_controller import tap
from wzry_ai.utils.logging_utils import get_logger

from wzry_ai.config import (
    HERO_HEIGHT_OFFSET,
    DEFAULT_SUPPORT_HERO,
    REDEMPTION_RANGE,
    HEAL_RANGE,
    HEAD_TO_FEET_OFFSET,
    HEAD_TO_FEET_OFFSET_GENERIC,
    KEY_SKILL_1, KEY_SKILL_2, KEY_SKILL_ULT,
    KEY_SUMMONER_F, KEY_SUMMONER_C,
    KEY_ACTIVE_ITEM,
    KEY_LEVEL_ULT, KEY_LEVEL_1, KEY_LEVEL_2,
    KEY_BUY_ITEM, KEY_ATTACK,
)

logger = get_logger(__name__)

# ===== 向后兼容的按键别名 =====
# 保留原有常量名称，映射到 config/keys.py 中的统一常量
# 各英雄 _v2 文件通过 from skills.hero_skill_logic_base import KEY_CAST_1 等使用
KEY_CAST_1   = KEY_SKILL_1     # 一技能按键：字母q
KEY_CAST_2   = KEY_SKILL_2     # 二技能按键：字母e
KEY_CAST_ULT = KEY_SKILL_ULT   # 大招按键：字母r
KEY_HEAL     = KEY_SUMMONER_F  # 召唤师技能-治疗术/汇流为兵按键：字母f
KEY_RECOVER  = KEY_SUMMONER_C  # 召唤师技能-恢复按键：字母c
KEY_SKILL_4  = KEY_ACTIVE_ITEM # 主动装备技能按键（救赎/星泉）：字母t

# ===== 坐标偏移配置 =====
# 获取当前英雄的偏移值元组 (dx, dy)，用于坐标转换
# 如果找不到当前英雄配置，使用默认值(0, 120)
_hero_offset = HERO_HEIGHT_OFFSET.get(DEFAULT_SUPPORT_HERO, (0, 120))

# 模态2血条坐标偏移（从血条中心/头顶位置转换为脚下坐标）
# 模态2检测的是血条中心（位于头顶上方），需要向下偏移到脚下位置才能正确计算攻击/技能范围
HEAD_TO_FEET_OFFSET_X = HEAD_TO_FEET_OFFSET["x"]  # X轴偏移量：向左偏移10像素
HEAD_TO_FEET_OFFSET_Y = HEAD_TO_FEET_OFFSET["y"]  # Y轴偏移量：从头顶到脚下的距离

# 救赎/治疗术范围配置（所有英雄统一使用）
# 救赎技能的范围配置，用于判断队友是否在救赎范围内
REDEMPTION_RANGE_X = REDEMPTION_RANGE[0]        # X轴半轴长度
REDEMPTION_RANGE_Y_UP = REDEMPTION_RANGE[1]     # Y轴上半轴长度（上方范围）
REDEMPTION_RANGE_Y_DOWN = REDEMPTION_RANGE[2]   # Y轴下半轴长度（下方范围）

# 治疗术的范围配置，用于判断队友是否在治疗范围内
HEAL_RANGE_X = HEAL_RANGE[0]                    # X轴半轴长度
HEAL_RANGE_Y_UP = HEAL_RANGE[1]                 # Y轴上半轴长度（上方范围）
HEAL_RANGE_Y_DOWN = HEAL_RANGE[2]               # Y轴下半轴长度（下方范围）


class HeroSkillLogicBase(ABC):
    """
    英雄技能逻辑基类
    
    功能说明：
        提供所有英雄技能逻辑的公共基础设施
        子类只需实现 check_and_use_skills() 方法即可
    
    主要方法：
        check_and_use_skills: 抽象方法，子类必须实现英雄特有的技能释放逻辑
        auto_maintenance: 自动买装备和加点
        basic_attack: 普通攻击控制
    """
    
    # 类属性配置
    QUEUE_TIMEOUT = 0.1
    LOOP_SLEEP = 0.02
    SKILL_LOG_ENABLED = True
    
    def __init__(self):
        # 存储从队列接收到的血量信息字典，包含自身、队友、敌人的血量和位置
        self.health_info = None
        
        # 上次普攻时间戳，用于控制普攻间隔
        self.last_attack_time = 0
        # 上次购买装备时间戳，用于控制买装备频率
        self.last_buy_time = 0
        # 上次升级技能时间戳，用于控制加点频率
        self.last_levelup_time = 0
        
        # 冷却计时器：记录各个技能上次释放的时间戳
        self.last_heal_time = 0        # 召唤师技能-治疗术(F)上次使用时间
        self.last_confluence_time = 0  # 召唤师技能-汇流为兵(F)上次使用时间
        self.last_recover_time = 0     # 召唤师技能-恢复(C)上次使用时间
        self.last_skill4_time = 0   # 主动装备技能(T)上次使用时间
        self.last_ult_time = 0      # 大招(R)上次使用时间
        self.last_q_time = 0        # 一技能(Q)上次使用时间
        self.last_e_time = 0        # 二技能(E)上次使用时间

        # 状态防抖：记录上次状态变化的时间戳，用于防抖处理
        self.last_status_change_time = 0
        
        # 移动状态标志：True表示正在移动，False表示静止
        # 用于控制普攻（移动时不普攻）
        self.is_moving = False
        
        # 目标锁定机制相关变量
        self.locked_target = None       # 当前锁定的目标（敌人或队友）
        self.lock_frame_count = 0       # 锁定持续帧数计数器
        self.TARGET_LOCK_FRAMES = 10    # 目标锁定持续时间（帧数）
        
        # 暂停标志：True表示暂停技能释放，False表示正常运行
        self.paused = False
        
        # 调用子类特定的初始化
        self._init_hero_specific()
        
        # 输出初始化成功日志，根据日志开关状态显示不同提示
        logger.info("技能逻辑初始化成功" + ("（日志已屏蔽）" if not self.SKILL_LOG_ENABLED else ""))

    def _init_hero_specific(self):
        """
        子类特定的初始化方法
        
        子类可以覆盖此方法以添加英雄特定的初始化逻辑
        """
        pass

    def _log(self, msg):
        """
        技能日志输出方法
        
        参数说明：
            msg: 要输出的日志消息字符串
        
        功能说明：
            根据SKILL_LOG_ENABLED开关决定是否输出调试日志
            用于控制技能释放相关的日志输出量
        """
        if self.SKILL_LOG_ENABLED:
            logger.debug(msg)
    
    def set_moving(self, is_moving: bool):
        """
        设置移动状态
        
        参数说明：
            is_moving: 布尔值，True表示正在移动，False表示静止
        
        功能说明：
            更新当前移动状态，用于控制普攻（移动时不进行普攻）
            由移动逻辑模块调用
        """
        self.is_moving = is_moving

    def tap_skill(self, skill_key, skill_name="", silent=False):
        """
        使用键盘发送技能按键
        
        参数说明：
            skill_key: 字符串，要按下的键盘按键（如'q'、'r'等）
            skill_name: 字符串，技能的显示名称，用于日志输出
            silent: 布尔值，True表示不输出日志，False表示输出日志
        
        功能说明：
            调用键盘控制器模拟按键操作，实现技能释放
            根据silent参数控制是否输出技能释放日志
        """
        if not silent:
            name = skill_name or skill_key.upper()
            self._log(f"[技能释放] {name}")
        tap(skill_key, 1, 0.05)

    def basic_attack(self):
        """
        普通攻击方法
        
        功能说明：
            执行普通攻击，仅在未移动且攻击间隔达标时执行
            攻击间隔为0.5秒，避免过于频繁的普攻操作
        
        注意事项：
            移动状态下不会执行普攻
        """
        if self.is_moving:
            return
        
        current_time = time.time()
        if current_time - self.last_attack_time > 0.5:
            self._log(f"[普攻] 攻击间隔达标，执行普攻")
            self.tap_skill(KEY_ATTACK, "普攻")
            self.last_attack_time = current_time

    def auto_maintenance(self):
        """
        自动维护方法 - 买装备和加点
        
        功能说明：
            自动执行购买装备和升级技能操作
            买装备间隔为3秒，加点间隔为5秒
            暂停状态下不执行任何操作
        
        升级顺序：
            优先升级大招，然后一技能，最后二技能
        """
        if self.paused:
            return
        
        current_time = time.time()
        if current_time - self.last_buy_time > 3:
            self.tap_skill(KEY_BUY_ITEM, "买装备", silent=True)
            self.last_buy_time = current_time

        if current_time - self.last_levelup_time > 5:
            self.tap_skill(KEY_LEVEL_ULT, "升级大招", silent=True)
            self.tap_skill(KEY_LEVEL_1, "升级技能1", silent=True)
            self.tap_skill(KEY_LEVEL_2, "升级技能2", silent=True)
            self.last_levelup_time = current_time

    def _convert_to_feet_pos(self, head_pos, use_generic_offset=False):
        """
        将头顶坐标转换为脚下坐标
        
        功能说明：
            所有基于模态2血条坐标的逻辑都需要先调用此方法进行偏移计算
            模态2检测的是血条中心（位于头顶上方），需要向下偏移到脚下位置
            才能正确计算攻击/技能范围
        
        参数说明：
            head_pos: 元组(x, y)，头顶坐标（模态2血条检测到的位置）
            use_generic_offset: 布尔值，是否使用通用偏移
                - True: 用于敌人/队友（不知道具体英雄类型时使用通用偏移）
                - False: 用于自身英雄（使用配置中的特定偏移）
        
        返回值：
            tuple: 脚下坐标 (x, y)，作为攻击/技能的中心点
            如果输入为None，则返回None
        """
        if head_pos is None:
            return None
        if use_generic_offset:
            # 敌人/队友使用通用偏移（来自config的HEAD_TO_FEET_OFFSET_GENERIC）
            return (head_pos[0] + HEAD_TO_FEET_OFFSET_GENERIC[0],
                    head_pos[1] + HEAD_TO_FEET_OFFSET_GENERIC[1])
        else:
            # 自身使用配置偏移（来自config的HEAD_TO_FEET_OFFSET）
            return (head_pos[0] + HEAD_TO_FEET_OFFSET_X, head_pos[1] + HEAD_TO_FEET_OFFSET_Y)

    def _is_same_target(self, pos1, pos2, threshold=50):
        """
        判断两个位置是否是同一目标
        
        参数说明：
            pos1: 元组(x, y)，第一个位置坐标
            pos2: 元组(x, y)，第二个位置坐标
            threshold: 数值，距离阈值（像素），默认50像素
        
        返回值：
            布尔值：True表示两个位置距离小于阈值，认为是同一目标；False表示不是同一目标
        
        计算方式：
            使用欧几里得距离公式计算两点间距离
        """
        from math import sqrt
        if pos1 is None or pos2 is None:
            return False
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        return sqrt(dx*dx + dy*dy) < threshold

    def _unpack_health_info(self):
        """
        解包 health_info 字典
        
        返回值：
            tuple: (self_health, team_health, enemy_health, self_pos, is_moving)
        """
        if not self.health_info:
            return None, [], [], None, False
        
        self_health = self.health_info.get('self_health')
        team_health = self.health_info.get('team_health', [])
        enemy_health = self.health_info.get('enemy_health', [])
        self_pos = self.health_info.get('self_pos')
        is_moving = self.health_info.get('is_moving', False)
        
        return self_health, team_health, enemy_health, self_pos, is_moving

    def _check_ellipse_range(self, dx, dy, raw_dy, range_x, range_y_up, range_y_down):
        """
        椭圆范围判断
        
        参数说明：
            dx: 水平距离
            dy: 垂直距离（绝对值）
            raw_dy: 原始垂直偏移（带方向，用于判断上下）
            range_x: X轴半轴长度
            range_y_up: Y轴上半轴长度（上方范围）
            range_y_down: Y轴下半轴长度（下方范围）
        
        返回值：
            bool: 是否在椭圆范围内
        """
        from math import sqrt
        if dx is None or dy is None or raw_dy is None:
            return False
        
        # 根据方向选择Y轴范围
        if raw_dy < 0:  # 目标在上方
            range_y = range_y_up
        else:  # 目标在下方
            range_y = range_y_down
        
        # 椭圆公式判断：(dx/rx)^2 + (dy/ry)^2 < 1 表示在范围内
        ellipse_val = (dx / range_x) ** 2 + (dy / range_y) ** 2
        return ellipse_val < 1

    def _check_cooldown(self, last_time, cooldown_seconds):
        """
        冷却检查
        
        参数说明：
            last_time: 上次释放时间戳
            cooldown_seconds: 冷却时间（秒）
        
        返回值：
            bool: 冷却是否完成
        """
        current_time = time.time()
        return current_time - last_time > cooldown_seconds

    def _check_stable(self, min_duration=0.6):
        """
        状态稳定性检查
        
        参数说明：
            min_duration: 最小稳定持续时间（秒），默认0.6秒
        
        返回值：
            bool: 状态是否稳定
        """
        current_time = time.time()
        stable_duration = current_time - self.last_status_change_time
        return stable_duration > min_duration

    def run(self, queue):
        """
        主循环方法 - 持续从队列接收血量信息并处理
        
        参数说明：
            queue: Queue对象，用于接收来自其他线程的血量信息
        
        功能说明：
            无限循环，从队列中获取血量信息
            获取到数据后调用check_and_use_skills进行技能判断和释放
            队列为空时，如果处于暂停状态则执行自动维护，否则也调用check_and_use_skills
            每次循环间隔由LOOP_SLEEP控制，避免CPU占用过高
        """
        logger.info("技能逻辑线程启动")
        while True:
            try:
                # 从队列获取血量信息，超时时间为QUEUE_TIMEOUT
                self.health_info = queue.get(timeout=self.QUEUE_TIMEOUT)
                # 调用技能判断和释放方法
                self.check_and_use_skills()
            except Empty:
                # 队列超时，没有新数据
                if self.paused:
                    # 暂停状态下执行自动维护
                    self.auto_maintenance()
                else:
                    # 非暂停状态下也调用check_and_use_skills（参考瑶的修复历史）
                    self.check_and_use_skills()
            # 短暂休眠，避免CPU占用过高
            time.sleep(self.LOOP_SLEEP)

    @abstractmethod
    def check_and_use_skills(self):
        """子类必须实现：英雄特有的技能释放逻辑"""
        pass
