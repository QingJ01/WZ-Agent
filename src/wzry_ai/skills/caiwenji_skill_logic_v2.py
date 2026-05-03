"""
蔡文姬技能逻辑 V2 - 基于新技能体系的重构版本
整合老代码的核心功能：坐标偏移、技能范围判断、自动维护
"""

# ===== 蔡文姬技能配置 =====
# 定义蔡文姬所有技能的配置参数，包括技能ID、类型、按键、冷却时间、触发条件等
CAIWENJI_SKILL_CONFIG = {
    "Q": {  # 一技能配置
        "skill_id": "Q",  # 技能唯一标识符
        "skill_type": "heal_shield",  # 技能类型：治疗/护盾
        "key": "q",  # 对应键盘按键
        "name": "思无邪",  # 技能中文名称
        "cooldown": 8.0,  # 技能冷却时间（秒）
        "range": 400,  # 技能作用范围（像素）
        "trigger_conditions": ["teammate_low_hp"],  # 触发条件：队友低血量
        "trigger_params": {"hp_threshold": 70},  # 触发参数：血量阈值70%
        "priority": 2,  # 技能优先级（数字越小优先级越高）
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
    "W": {  # 二技能配置
        "skill_id": "W",  # 技能唯一标识符
        "skill_type": "control",  # 技能类型：控制
        "key": "w",  # 对应键盘按键
        "name": "胡笳乐",  # 技能中文名称
        "cooldown": 10.0,  # 技能冷却时间（秒）
        "range": 450,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_enemy",
            "enemy_in_range",
        ],  # 触发条件：有敌人在范围内
        "priority": 3,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
    "E": {  # 三技能配置
        "skill_id": "E",  # 技能唯一标识符
        "skill_type": "heal_shield",  # 技能类型：治疗/护盾
        "key": "e",  # 对应键盘按键
        "name": "忘忧曲",  # 技能中文名称
        "cooldown": 12.0,  # 技能冷却时间（秒）
        "range": 350,  # 技能作用范围（像素）
        "trigger_conditions": ["teammate_low_hp"],  # 触发条件：队友低血量
        "trigger_params": {"hp_threshold": 60},  # 触发参数：血量阈值60%
        "priority": 1,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
    "R": {  # 大招配置
        "skill_id": "R",  # 技能唯一标识符
        "skill_type": "heal_shield",  # 技能类型：治疗/护盾
        "key": "r",  # 对应键盘按键
        "name": "忘忧曲",  # 技能中文名称
        "cooldown": 60.0,  # 技能冷却时间（秒）
        "range": 500,  # 技能作用范围（像素）
        "trigger_conditions": [
            "in_teamfight",
            "teammate_low_hp",
        ],  # 触发条件：团战且队友低血量
        "trigger_params": {
            "hp_threshold": 40,
            "enemy_count": 2,
        },  # 触发参数：血量40%，敌人数量2
        "priority": 1,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
    "confluence": {  # 召唤师技能-汇流为兵-辅助配置
        "skill_id": "confluence",  # 技能唯一标识符
        "skill_type": "summoner",  # 技能类型：召唤师技能
        "key": "f",  # 对应键盘按键（与治疗术共用F键位）
        "name": "汇流为兵-辅助",  # 技能中文名称
        "cooldown": 100.0,  # 技能冷却时间（秒）
        "range": 0,  # 技能作用范围（0表示以自身为中心）
        "trigger_conditions": [
            "self_low_hp",
            "teammate_low_hp",
        ],  # 触发条件：自身或队友低血量
        "trigger_params": {"hp_threshold": 50},  # 触发参数：血量阈值50%
        "priority": 1,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
        "extra_effect": "reduce_all_cd_50%",  # 额外效果：释放后减少所有技能当前50%冷却
    },
    "heal": {  # 召唤师技能-治疗术配置（与汇流为兵共用F键位，战前切换）
        "skill_id": "heal",  # 技能唯一标识符
        "skill_type": "summoner",  # 技能类型：召唤师技能
        "key": "f",  # 对应键盘按键
        "name": "治疗术",  # 技能中文名称
        "cooldown": 120.0,  # 技能冷却时间（秒）
        "range": 0,  # 技能作用范围（0表示以自身为中心）
        "trigger_conditions": [
            "self_low_hp",
            "teammate_low_hp",
        ],  # 触发条件：自身或队友低血量
        "trigger_params": {"hp_threshold": 50},  # 触发参数：血量阈值50%
        "priority": 1,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
    "active_item": {  # 主动装备配置
        "skill_id": "active_item",  # 技能唯一标识符
        "skill_type": "active_item",  # 技能类型：主动装备
        "key": "p",  # 对应键盘按键
        "name": "辅助装备",  # 技能中文名称
        "cooldown": 10.0,  # 技能冷却时间（秒）
        "range": 300,  # 技能作用范围（像素）
        "trigger_conditions": ["teammate_low_hp"],  # 触发条件：队友低血量
        "trigger_params": {"emergency_hp_threshold": 70},  # 触发参数：紧急血量阈值70%
        "priority": 2,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态是否可用
        "can_use_when_detached": True,  # 非附身状态是否可用
    },
}

# 导入时间模块，用于计算冷却时间和间隔
import time

# 从math模块导入sqrt函数，用于计算两点间距离
from math import sqrt

# 从基类导入需要的常量和基类
from wzry_ai.skills.hero_skill_logic_base import (
    HeroSkillLogicBase,
    KEY_CAST_1,
    KEY_CAST_2,
    KEY_CAST_ULT,
    KEY_SKILL_4,
    KEY_LEVEL_ULT,
    KEY_LEVEL_1,
    KEY_LEVEL_2,
    KEY_BUY_ITEM,
    KEY_ATTACK,
    KEY_HEAL,
    KEY_RECOVER,
    HEAD_TO_FEET_OFFSET_X,
    HEAD_TO_FEET_OFFSET_Y,
    REDEMPTION_RANGE_X,
    REDEMPTION_RANGE_Y_UP,
    REDEMPTION_RANGE_Y_DOWN,
    HEAL_RANGE_X,
    HEAL_RANGE_Y_UP,
    HEAL_RANGE_Y_DOWN,
)

# 从基类导入日志记录器
from wzry_ai.skills.hero_skill_logic_base import logger

# 从统一配置导入召唤师技能设置
from wzry_ai.config import ACTIVE_SUMMONER_F

# ===== Q技能攻击距离配置（上下非对称半椭圆）=====
# 基于1920x1080分辨率下的技能范围配置
# 使用椭圆公式判断目标是否在技能范围内：(dx/rx)^2 + (dy/ry)^2 < 1
Q_RANGE_X = 600  # Q技能X轴半轴长度（水平范围）
Q_RANGE_Y_UP = 300  # Q技能Y轴上半轴长度（上方范围）
Q_RANGE_Y_DOWN = 450  # Q技能Y轴下半轴长度（下方范围）

# ===== E技能攻击距离配置 =====
E_RANGE_X = 500  # E技能X轴半轴长度（水平范围）
E_RANGE_Y_UP = 250  # E技能Y轴上半轴长度（上方范围）
E_RANGE_Y_DOWN = 400  # E技能Y轴下半轴长度（下方范围）

# ===== R技能施法距离配置 =====
R_RANGE_X = 700  # R技能X轴半轴长度（水平范围）
R_RANGE_Y_UP = 350  # R技能Y轴上半轴长度（上方范围）
R_RANGE_Y_DOWN = 550  # R技能Y轴下半轴长度（下方范围）


class CaiwenjiSkillLogic(HeroSkillLogicBase):
    """
    蔡文姬技能逻辑 V2 主类

    功能说明：
        实现蔡文姬英雄的自动技能释放逻辑，包括治疗、控制、大招等技能的自动判断和释放
        整合坐标偏移计算、技能范围判断、自动维护（买装备/加点）等核心功能

    主要方法：
        check_and_use_skills: 核心技能判断和释放逻辑
        auto_maintenance: 自动买装备和加点
        basic_attack: 普通攻击控制
    """

    def _init_hero_specific(self):
        """
        蔡文姬特有的初始化
        """
        # 目标锁定机制相关变量（蔡文姬特有）
        self.locked_enemy = None  # 当前锁定的敌人位置
        self.locked_teammate = None  # 当前锁定的队友位置

    def check_and_use_skills(self):
        """
        检查并使用技能 - 核心逻辑方法

        功能说明：
            根据当前血量信息判断是否需要释放技能，并按优先级执行
            包含逃跑逻辑、大招逻辑、Q/E技能、治疗术、救赎、恢复等多个判断分支

        执行流程：
            1. 检查暂停状态和血量信息有效性
            2. 读取技能策略（来自战斗状态机）
            3. 解包血量数据（自身、队友、敌人）
            4. 坐标转换（头顶坐标转脚下坐标）
            5. 依次判断各技能释放条件
            6. 执行满足条件的技能释放

        注意事项：
            暂停状态下只执行自动维护，不释放技能
        """
        # ===== 战斗状态机技能策略 =====
        # 策略说明：
        #   aggressive   - 全技能输出（FIGHT状态，敌人在附近）
        #   conservative - 被动反击：有敌人时允许进攻，无敌人时仅恢复/治疗（FOLLOW状态）
        #   defensive    - 防御优先：治疗/保命，不主动进攻（RETREAT状态）
        #   disabled     - 完全禁止释放（RECALL回城状态）
        skill_policy = (
            self.health_info.get("skill_policy", "aggressive")
            if self.health_info
            else "aggressive"
        )

        # 回城中完全禁止技能释放
        if skill_policy == "disabled":
            return

        # 是否允许防御性/治疗技能（大招团队治疗、治疗术、救赎、恢复）
        allow_defensive = skill_policy in ("aggressive", "defensive", "conservative")
        # 注意：allow_offensive 在数据解包后计算（需要 enemy_health 信息）

        if self.paused:
            self.auto_maintenance()
            return

        if not self.health_info:
            return

        self.auto_maintenance()

        current_time = time.time()

        # --- 数据解包 ---
        # 从自身血量信息字典中提取各项数据
        self_health = self.health_info.get("self_health")  # 自身血量百分比
        team_health = self.health_info.get("team_health", [])  # 队友血量列表
        enemy_health = self.health_info.get("enemy_health", [])  # 敌人血量列表
        self_pos = self.health_info.get("self_pos")  # 自身位置坐标
        is_moving = self.health_info.get("is_moving", False)  # 是否正在移动

        # --- 计算进攻许可（依赖 enemy_health 数据） ---
        # aggressive: 全面进攻；conservative: 被动反击（有敌人才攻击）
        # defensive/disabled: 不进攻
        has_enemy_for_policy = len(enemy_health) > 0
        allow_offensive = (skill_policy == "aggressive") or (
            skill_policy == "conservative" and has_enemy_for_policy
        )

        # 更新移动状态，用于控制普攻
        self.set_moving(is_moving)

        # 计算状态稳定持续时间，用于防抖判断
        stable_duration = current_time - self.last_status_change_time
        is_stable = stable_duration > 0.6  # 稳定超过0.6秒才认为是稳定状态

        # --- 坐标转换（头顶→脚下）---
        # 将自身头顶坐标转换为脚下坐标，用于后续距离计算
        self_feet_pos = self._convert_to_feet_pos(self_pos)

        # --- 1. 逃跑逻辑（敌人近且没队友）---
        # 当检测到敌人很近且周围没有队友时，触发逃跑判断
        if self_feet_pos and enemy_health and not team_health:
            # 计算最近敌人的距离
            min_enemy_dist = float("inf")  # 初始化为无穷大
            for e in enemy_health:
                if isinstance(e, dict) and "pos" in e:
                    # 将敌人头顶坐标转换为脚下坐标
                    enemy_feet_pos = self._convert_to_feet_pos(
                        e["pos"], use_generic_offset=True
                    )
                    if enemy_feet_pos is None:
                        continue
                    # 计算与敌人的欧几里得距离
                    d = sqrt(
                        (self_feet_pos[0] - enemy_feet_pos[0]) ** 2
                        + (self_feet_pos[1] - enemy_feet_pos[1]) ** 2
                    )
                    if d < min_enemy_dist:
                        min_enemy_dist = d

            # 如果最近敌人距离小于300像素，认为需要逃跑
            if min_enemy_dist < 300:
                self._log("[逃跑] 敌人接近且无队友，撤退！")
                # 逃跑逻辑由移动模块处理，这里只记录状态并返回
                return

        # --- 2. 大招逻辑 (R) - 团队回血 ---
        # 当有多名队友血量较低时，释放大招进行团队治疗
        if self_feet_pos and team_health:
            # 统计低血量队友列表（血量低于50%）
            low_hp_teammates = []
            for t in team_health:
                if isinstance(t, dict) and "health" in t:
                    h = t["health"]
                    if h < 50:  # 血量低于50%认为是低血量
                        low_hp_teammates.append(t)

            # 如果有2个及以上低血量队友，且大招冷却完成，则释放大招
            if len(low_hp_teammates) >= 2:
                r_ready = current_time - self.last_ult_time > 5.0  # 检查5秒冷却时间
                if r_ready and is_stable:
                    self._log(f"[R] 大招回血 | 低血量队友:{len(low_hp_teammates)}")
                    self.tap_skill(KEY_CAST_ULT, "大招")
                    self.last_ult_time = current_time

        # --- 3. Q/E技能 ---
        # 检测是否有敌人，用于后续技能判断
        has_enemy = len(enemy_health) > 0

        # 策略检查：仅在 aggressive 模式下使用进攻技能（Q/E/普攻）
        # 如果有敌人且自身位置有效，计算最近敌人的距离和方向
        if has_enemy and self_feet_pos and allow_offensive:
            # 初始化最近敌人相关变量
            closest_dx = None  # 与最近敌人的水平距离
            closest_dy = None  # 与最近敌人的垂直距离
            raw_dy = None  # 与最近敌人的原始垂直偏移（带方向）
            min_dist = float("inf")  # 最小距离，初始化为无穷大

            # 遍历所有敌人，找到最近的一个
            for e in enemy_health:
                if isinstance(e, dict) and "pos" in e:
                    pos = e["pos"]
                    # 将敌人头顶坐标转换为脚下坐标
                    enemy_feet_pos = self._convert_to_feet_pos(
                        pos, use_generic_offset=True
                    )
                    if enemy_feet_pos is None:
                        continue
                    # 计算与敌人的欧几里得距离
                    d = sqrt(
                        (self_feet_pos[0] - enemy_feet_pos[0]) ** 2
                        + (self_feet_pos[1] - enemy_feet_pos[1]) ** 2
                    )
                    if d < min_dist:
                        min_dist = d
                        closest_dx = abs(self_feet_pos[0] - enemy_feet_pos[0])
                        closest_dy = abs(self_feet_pos[1] - enemy_feet_pos[1])
                        raw_dy = enemy_feet_pos[1] - self_feet_pos[1]

            # Q技能判断和释放
            # 使用椭圆范围判断敌人在不在Q技能范围内
            if closest_dx is not None and closest_dy is not None and raw_dy is not None:
                if raw_dy < 0:  # 敌人在上方，使用上方范围
                    q_ry = Q_RANGE_Y_UP
                else:  # 敌人在下方，使用下方范围
                    q_ry = Q_RANGE_Y_DOWN
                # 椭圆公式判断：(dx/rx)^2 + (dy/ry)^2 < 1 表示在范围内
                q_ellipse_val = (closest_dx / Q_RANGE_X) ** 2 + (closest_dy / q_ry) ** 2
                q_in_range = q_ellipse_val < 1
            else:
                q_in_range = False

            # 检查Q技能冷却（4秒）
            q_ready = current_time - self.last_q_time > 4.0
            if q_in_range and q_ready:
                self.tap_skill(KEY_CAST_1, "一技能")
                self.last_q_time = current_time

            # E技能判断和释放
            if closest_dx is not None and closest_dy is not None and raw_dy is not None:
                if raw_dy < 0:  # 敌人在上方，使用上方范围
                    e_ry = E_RANGE_Y_UP
                else:  # 敌人在下方，使用下方范围
                    e_ry = E_RANGE_Y_DOWN
                # 椭圆公式判断范围
                e_ellipse_val = (closest_dx / E_RANGE_X) ** 2 + (closest_dy / e_ry) ** 2
                e_in_range = e_ellipse_val < 1
            else:
                e_in_range = False

            # 检查E技能冷却（5秒）
            e_ready = current_time - self.last_e_time > 5.0
            if e_in_range and e_ready:
                self.tap_skill(KEY_CAST_2, "二技能")
                self.last_e_time = current_time

            # 普攻判断
            if closest_dx is not None and closest_dy is not None and raw_dy is not None:
                if raw_dy < 0:  # 敌人在上方
                    attack_ry = 333
                else:  # 敌人在下方
                    attack_ry = 522
                # 使用椭圆公式判断普攻范围
                attack_ellipse_val = (closest_dx / 630) ** 2 + (
                    closest_dy / attack_ry
                ) ** 2
                attack_in_range = attack_ellipse_val < 1

                # 如果在普攻范围内，执行普攻
                if attack_in_range:
                    self.basic_attack()

        # --- 4. 召唤师技能 F键（汇流为兵 / 治疗术，由 ACTIVE_SUMMONER_F 开关决定）---
        # 两者都是防御性技能，在 aggressive/defensive/conservative 下均可使用
        # 定义辅助函数：获取血量值，兼容字典格式和数值格式
        def get_health_value(h):
            return h["health"] if isinstance(h, dict) else h

        # 统计范围内低血量队友数量（两种召唤师技能共用的判断逻辑）
        low_hp_count = 0  # 低血量目标计数（包括自身和队友）
        in_range_team_count = 0  # 在技能范围内的队友数量

        # 如果自身血量低于60%，计入低血量计数
        if self_health is not None and self_health < 60:
            low_hp_count += 1

        # 遍历队友，检查是否在范围内且血量低
        if self_feet_pos and team_health:
            for t in team_health:
                if isinstance(t, dict) and "pos" in t and "health" in t:
                    tpos = t["pos"]
                    # 将队友头顶坐标转换为脚下坐标
                    team_feet_pos = self._convert_to_feet_pos(
                        tpos, use_generic_offset=True
                    )
                    if team_feet_pos is None:
                        continue
                    # 计算与队友的水平和垂直距离
                    t_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                    t_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                    t_raw_dy = team_feet_pos[1] - self_feet_pos[1]

                    # 根据队友方向选择对应的Y轴范围（汇流为兵/治疗术范围类似）
                    if t_raw_dy < 0:  # 队友在上方
                        f_ry = HEAL_RANGE_Y_UP
                    else:  # 队友在下方
                        f_ry = HEAL_RANGE_Y_DOWN
                    # 椭圆公式判断队友是否在范围内
                    f_ellipse_val = (t_dx / HEAL_RANGE_X) ** 2 + (t_dy / f_ry) ** 2

                    if f_ellipse_val < 1:
                        in_range_team_count += 1
                        h = get_health_value(t)
                        if h < 50:  # 血量低于50%认为是低血量
                            low_hp_count += 1

        # ===== 根据 ACTIVE_SUMMONER_F 开关选择释放哪个召唤师技能 =====
        if ACTIVE_SUMMONER_F == "confluence":
            # --- 汇流为兵-辅助 ---
            # 效果：召唤元流古琴治疗友方/伤害敌方，额外减少自身所有技能当前50%冷却
            need_confluence = False
            # 汇流为兵CD=100秒，用90秒做冷却检查（留10秒余量避免浪费按键）
            confluence_cooldown_ok = current_time - self.last_confluence_time > 90

            if is_stable and confluence_cooldown_ok:
                # 条件1：有2个及以上低血量目标
                if low_hp_count >= 2:
                    need_confluence = True
                # 条件2：只有1个低血量目标且自身血量低于30%（紧急自保）
                elif low_hp_count == 1 and self_health is not None and self_health < 30:
                    need_confluence = True

                if need_confluence:
                    self._log(
                        f"[F] 汇流为兵-辅助 | 受益人数:{low_hp_count} (范围内队友:{in_range_team_count})"
                    )
                    self.tap_skill(KEY_HEAL, "汇流为兵-辅助")
                    self.last_confluence_time = current_time

                    # ===== 汇流为兵额外效果：减少自身所有技能当前50%冷却 =====
                    # 计算每个技能的剩余CD，减半后更新 last_xxx_time
                    # 公式：new_last_time = current_time - cd + remaining * 0.5
                    skill_cds = {
                        "Q": (
                            self.last_q_time,
                            4.0,
                        ),  # Q技能（思无邪），代码内检查CD=4秒
                        "E": (
                            self.last_e_time,
                            5.0,
                        ),  # E技能（忘忧曲），代码内检查CD=5秒
                        "R": (
                            self.last_ult_time,
                            5.0,
                        ),  # 大招（团队回血），代码内检查CD=5秒
                    }
                    for skill_name, (last_time, cd) in skill_cds.items():
                        # 计算当前剩余冷却时间
                        remaining = max(0, cd - (current_time - last_time))
                        if remaining > 0:
                            # 减少50%剩余CD：将 last_time 提前，使剩余CD减半
                            new_last_time = current_time - cd + remaining * 0.5
                            if skill_name == "Q":
                                self.last_q_time = new_last_time
                            elif skill_name == "E":
                                self.last_e_time = new_last_time
                            elif skill_name == "R":
                                self.last_ult_time = new_last_time
                            self._log(
                                f"  [汇流] {skill_name} 剩余CD {remaining:.1f}s -> {remaining * 0.5:.1f}s"
                            )

        elif ACTIVE_SUMMONER_F == "heal":
            # --- 治疗术 ---
            # 效果：为自身和附近队友回复血量，CD较短
            need_heal = False
            # 治疗术CD=120秒，用5秒做按键防抖
            if is_stable and (current_time - self.last_heal_time > 5):
                # 条件1：有2个及以上低血量目标
                if low_hp_count >= 2:
                    need_heal = True
                # 条件2：只有1个低血量目标且自身血量低于30%
                elif low_hp_count == 1 and self_health is not None and self_health < 30:
                    need_heal = True

                if need_heal:
                    self._log(
                        f"[F] 治疗术 | 受益人数:{low_hp_count} (范围内队友:{in_range_team_count})"
                    )
                    self.tap_skill(KEY_HEAL, "治疗术")
                    self.last_heal_time = current_time

        # --- 5. 救赎 (T) ---
        # 检查救赎技能冷却（5秒）
        t_ready = current_time - self.last_skill4_time > 5
        t_in_range = False  # 标记是否有队友在救赎范围内
        # 状态稳定、冷却完成、有自身位置和队友数据时才判断
        if is_stable and t_ready and self_feet_pos and team_health:
            for t in team_health:
                if isinstance(t, dict) and "pos" in t:
                    tpos = t["pos"]
                    # 将队友头顶坐标转换为脚下坐标
                    team_feet_pos = self._convert_to_feet_pos(
                        tpos, use_generic_offset=True
                    )
                    if team_feet_pos is None:
                        continue
                    # 计算与队友的距离
                    t_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                    t_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                    t_raw_dy = team_feet_pos[1] - self_feet_pos[1]

                    # 根据队友方向选择对应的Y轴范围
                    if t_raw_dy < 0:  # 队友在上方
                        t_ry = REDEMPTION_RANGE_Y_UP
                    else:  # 队友在下方
                        t_ry = REDEMPTION_RANGE_Y_DOWN
                    # 椭圆公式判断队友是否在救赎范围内
                    t_ellipse_val = (t_dx / REDEMPTION_RANGE_X) ** 2 + (
                        t_dy / t_ry
                    ) ** 2

                    if t_ellipse_val < 1:
                        t_in_range = True
                        break  # 找到一个在范围内的队友即可

        # 如果有队友在救赎范围内，释放救赎
        if t_in_range:
            self._log(f"[T] 救赎")
            self.tap_skill(KEY_SKILL_4, "救赎")
            self.last_skill4_time = current_time

        # --- 6. 恢复 (C) ---
        # 检查附近是否有敌人（没有敌人才使用恢复）
        no_enemy_nearby = len(enemy_health) == 0
        # 状态稳定、有自身血量数据时才判断
        if is_stable and self_health is not None:
            # 自身血量低于60%且附近没有敌人，使用恢复技能
            if self_health < 60 and no_enemy_nearby:
                # 检查恢复技能冷却（5秒）
                if current_time - self.last_recover_time > 5:
                    self._log(f"[C] 恢复 | 自身:{self_health}%")
                    self.tap_skill(KEY_RECOVER, "恢复")
                    self.last_recover_time = current_time


# ===== 模块入口函数 =====
def run(queue):
    """
    运行蔡文姬技能逻辑的入口函数

    参数说明：
        queue: Queue对象，用于接收血量信息的队列

    功能说明：
        创建蔡文姬技能逻辑实例并启动主循环
        供外部模块调用以启动技能逻辑线程
    """
    caiwenji = CaiwenjiSkillLogic()
    caiwenji.run(queue)


# 当直接运行此文件时执行的测试代码
if __name__ == "__main__":
    from queue import Queue

    # 输出测试开始分隔线
    logger.info("=" * 60)
    logger.info("蔡文姬技能逻辑 V2 测试")
    logger.info("=" * 60)

    # 创建技能逻辑实例
    skill_logic = CaiwenjiSkillLogic()
    logger.info("实例创建成功")

    # 构造测试用的血量信息数据
    test_health_info = {
        "self_health": 80,  # 自身血量80%
        "team_health": [{"health": 60, "pos": (1000, 500)}],  # 1个队友，血量60%
        "enemy_health": [{"health": 70, "pos": (1100, 600)}],  # 1个敌人，血量70%
        "self_pos": (900, 400),  # 自身位置坐标
        "is_moving": False,  # 未在移动
    }

    # 设置测试数据并执行技能检查
    skill_logic.health_info = test_health_info
    logger.info("模拟技能检查...")
    skill_logic.check_and_use_skills()

    # 输出测试完成信息
    logger.info("测试完成")
    logger.info("=" * 60)
