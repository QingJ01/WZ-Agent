"""
明世隐技能逻辑 V2 - 基于新技能体系的重构版本
整合老代码的核心功能：坐标偏移、技能范围判断、链接逻辑
"""

# ===== 明世隐技能配置 =====
# 定义明世隐所有技能的配置参数，包括技能ID、类型、按键、冷却时间、触发条件等
MINGSHIYIN_SKILL_CONFIG = {
    "Q": {  # 一技能配置 - 链接技能
        "skill_id": "Q",  # 技能唯一标识符
        "skill_type": "buff",  # 技能类型：增益/减益
        "key": "q",  # 对应键盘按键
        "name": "临卦·无忧",  # 技能中文名称
        "cooldown": 8.0,  # 技能冷却时间（秒）
        "range": 600,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_teammate",
            "teammate_in_range",
        ],  # 触发条件：有队友在范围内
        "priority": 2,  # 技能优先级
        "can_use_when_attached": False,  # 附身状态不可用（明世隐没有附身机制）
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "E": {  # 二技能配置 - 控制/切换技能
        "skill_id": "E",  # 技能唯一标识符
        "skill_type": "control",  # 技能类型：控制
        "key": "e",  # 对应键盘按键
        "name": "师卦·飞翼",  # 技能中文名称
        "cooldown": 6.0,  # 技能冷却时间（秒）
        "range": 400,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_enemy",
            "enemy_in_range",
        ],  # 触发条件：有敌人在范围内
        "priority": 3,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "R": {  # 大招配置 - 团队增益/治疗
        "skill_id": "R",  # 技能唯一标识符
        "skill_type": "heal_shield",  # 技能类型：治疗/护盾
        "key": "r",  # 对应键盘按键
        "name": "泰卦·长生",  # 技能中文名称
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
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
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
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
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
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "recover": {  # 召唤师技能-恢复配置
        "skill_id": "recover",  # 技能唯一标识符
        "skill_type": "summoner",  # 技能类型：召唤师技能
        "key": "c",  # 对应键盘按键
        "name": "恢复",  # 技能中文名称
        "cooldown": 5.0,  # 技能冷却时间（秒）
        "range": 0,  # 技能作用范围（0表示以自身为中心）
        "trigger_conditions": [
            "self_low_hp",
            "peace_state",
        ],  # 触发条件：自身低血量且和平状态
        "trigger_params": {"hp_threshold": 80},  # 触发参数：血量阈值80%
        "priority": 6,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "active_item": {  # 主动装备配置
        "skill_id": "active_item",  # 技能唯一标识符
        "skill_type": "active_item",  # 技能类型：主动装备
        "key": "t",  # 对应键盘按键
        "name": "辅助装备",  # 技能中文名称
        "cooldown": 10.0,  # 技能冷却时间（秒）
        "range": 300,  # 技能作用范围（像素）
        "trigger_conditions": [
            "self_low_hp",
            "teammate_low_hp",
        ],  # 触发条件：自身或队友低血量
        "trigger_params": {"emergency_hp_threshold": 50},  # 触发参数：紧急血量阈值50%
        "priority": 2,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
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

# ===== Q技能（链接）距离配置 =====
# 使用椭圆公式判断目标是否在技能范围内：(dx/rx)^2 + (dy/ry)^2 < 1
Q_RANGE_X = 600  # Q技能X轴半轴长度（水平链接范围）
Q_RANGE_Y_UP = 350  # Q技能Y轴上半轴长度（上方范围）
Q_RANGE_Y_DOWN = 550  # Q技能Y轴下半轴长度（下方范围）

# ===== E技能（控制）距离配置 =====
E_RANGE_X = 400  # E技能X轴半轴长度（水平范围）
E_RANGE_Y_UP = 250  # E技能Y轴上半轴长度（上方范围）
E_RANGE_Y_DOWN = 400  # E技能Y轴下半轴长度（下方范围）

# ===== R技能（大招）距离配置 =====
R_RANGE_X = 800  # R技能X轴半轴长度（水平范围）
R_RANGE_Y_UP = 400  # R技能Y轴上半轴长度（上方范围）
R_RANGE_Y_DOWN = 600  # R技能Y轴下半轴长度（下方范围）


class MingshiyinSkillLogic(HeroSkillLogicBase):
    """
    明世隐技能逻辑 V2 主类

    功能说明：
        实现明世隐英雄的自动技能释放逻辑，包括链接、控制、大招等技能的自动判断和释放
        整合坐标偏移计算、技能范围判断、自动维护（买装备/加点）等核心功能
        明世隐特色：Q技能链接队友提供增益或链接敌人提供减益

    主要方法：
        check_and_use_skills: 核心技能判断和释放逻辑
        auto_maintenance: 自动买装备和加点
        basic_attack: 普通攻击控制
    """

    def _init_hero_specific(self):
        """
        明世隐特有的初始化
        """
        # 链接状态相关变量（明世隐特有）
        self.is_linked = False  # 当前是否处于链接状态
        self.link_target_type = None  # 链接目标类型：'team'表示队友，'enemy'表示敌人
        self.last_link_time = 0  # 上次链接时间戳，用于链接超时检测

    def get_health_value(self, h):
        """
        获取血量值，兼容整数和字典格式

        参数说明：
            h: 血量数据，可以是数值（如80）或字典格式（如{'health': 80, 'pos': (x, y)}）

        返回值：
            数值：血量百分比（0-100）

        功能说明：
            统一处理不同格式的血量数据，方便后续逻辑处理
        """
        return h["health"] if isinstance(h, dict) else h

    def check_and_use_skills(self):
        """
        检查并使用技能 - 核心逻辑方法

        功能说明：
            根据当前血量信息判断是否需要释放技能，并按优先级执行
            包含链接逻辑、控制技能、大招、治疗术、辅助装备、恢复等多个判断分支
            明世隐特色：优先链接队友提供增益，无队友时链接敌人提供减益

        执行流程：
            1. 检查暂停状态和血量信息有效性
            2. 读取技能策略（来自战斗状态机）
            3. 解包血量数据（自身、队友、敌人）
            4. 坐标转换（头顶坐标转脚下坐标）
            5. 依次判断各技能释放条件（Q链接、E控制、R大招等）
            6. 执行满足条件的技能释放

        注意事项：
            暂停状态下只执行自动维护，不释放技能
        """
        # ===== 战斗状态机技能策略 =====
        # 策略说明：
        #   aggressive   - 全技能输出（FIGHT状态，敌人在附近）
        #   conservative - 被动反击：有敌人时允许进攻，无敌人时仅链接/恢复（FOLLOW状态）
        #   defensive    - 防御优先：治疗/链接/保命，不主动进攻（RETREAT状态）
        #   disabled     - 完全禁止释放（RECALL回城状态）
        skill_policy = (
            self.health_info.get("skill_policy", "aggressive")
            if self.health_info
            else "aggressive"
        )

        # 回城中完全禁止技能释放
        if skill_policy == "disabled":
            return

        # 是否允许防御性/辅助技能（Q链接、治疗术、救赎、恢复）
        allow_defensive = skill_policy in ("aggressive", "defensive", "conservative")
        # 注意：allow_offensive 在数据解包后计算（需要 enemy_health 信息）

        if self.paused:
            self.auto_maintenance()
            return

        self.auto_maintenance()

        if not self.health_info:
            return

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

        current_time = time.time()
        # 计算状态稳定持续时间，用于防抖判断
        stable_duration = current_time - self.last_status_change_time
        is_stable = stable_duration > 0.6  # 稳定超过0.6秒才认为是稳定状态

        # 转换血量值为统一格式（数值列表）
        team_health_values = [self.get_health_value(h) for h in team_health]
        enemy_health_values = [self.get_health_value(h) for h in enemy_health]

        # 标记是否有敌人和队友
        has_enemy = len(enemy_health) > 0
        has_team = len(team_health) > 0

        # --- 坐标转换 ---
        # 将自身头顶坐标转换为脚下坐标，用于后续距离计算
        self_feet_pos = self._convert_to_feet_pos(self_pos)

        # =================================================================
        # 1. 链接逻辑 (Q) - 明世隐核心技能
        # 优先链接队友（提供增益效果），如果没有队友则链接敌人（提供减益效果）
        # =================================================================
        # 检查Q技能冷却（8秒）
        if current_time - self.last_q_time > 8:
            q_target = None  # 链接目标
            q_target_type = None  # 目标类型：'team'队友或'enemy'敌人
            min_dist = float("inf")  # 最小距离，初始化为无穷大

            # 优先寻找血量最低的队友进行链接
            min_team_hp = 100  # 记录最低血量，初始化为100%
            if has_team and self_feet_pos:
                for t in team_health:
                    if isinstance(t, dict) and "pos" in t and "health" in t:
                        h = t["health"]
                        # 寻找血量比当前记录更低的队友
                        if h < min_team_hp:
                            tpos = t["pos"]
                            # 将队友头顶坐标转换为脚下坐标
                            team_feet_pos = self._convert_to_feet_pos(
                                tpos, use_generic_offset=True
                            )
                            if team_feet_pos is None:
                                continue
                            # 计算与队友的距离
                            d = sqrt(
                                (self_feet_pos[0] - team_feet_pos[0]) ** 2
                                + (self_feet_pos[1] - team_feet_pos[1]) ** 2
                            )
                            # 在扩大搜索范围内（1.5倍Q范围）寻找最近队友
                            if d < min_dist and d < Q_RANGE_X * 1.5:
                                min_dist = d
                                q_target = t
                                q_target_type = "team"
                                min_team_hp = h

            # 如果没有找到合适的队友，寻找最近的敌人进行链接
            if q_target is None and has_enemy and self_feet_pos:
                for e in enemy_health:
                    if isinstance(e, dict) and "pos" in e:
                        epos = e["pos"]
                        # 将敌人头顶坐标转换为脚下坐标
                        enemy_feet_pos = self._convert_to_feet_pos(
                            epos, use_generic_offset=True
                        )
                        if enemy_feet_pos is None:
                            continue
                        # 计算与敌人的距离
                        d = sqrt(
                            (self_feet_pos[0] - enemy_feet_pos[0]) ** 2
                            + (self_feet_pos[1] - enemy_feet_pos[1]) ** 2
                        )
                        # 在扩大搜索范围内寻找最近敌人
                        if d < min_dist and d < Q_RANGE_X * 1.5:
                            min_dist = d
                            q_target = e
                            q_target_type = "enemy"

            # 椭圆范围判断：检查目标是否在Q技能实际范围内
            if q_target is not None and self_feet_pos:
                tpos = q_target["pos"]
                target_feet_pos = self._convert_to_feet_pos(
                    tpos, use_generic_offset=True
                )
                if target_feet_pos is not None:
                    # 计算与目标的水平和垂直距离
                    q_dx = abs(self_feet_pos[0] - target_feet_pos[0])
                    q_dy = abs(self_feet_pos[1] - target_feet_pos[1])
                    q_raw_dy = target_feet_pos[1] - self_feet_pos[1]

                    # 根据目标方向选择对应的Y轴范围
                    if q_raw_dy < 0:  # 目标在上方
                        q_ry = Q_RANGE_Y_UP
                    else:  # 目标在下方
                        q_ry = Q_RANGE_Y_DOWN
                    # 椭圆公式判断目标是否在范围内：(dx/rx)^2 + (dy/ry)^2 < 1
                    q_ellipse_val = (q_dx / Q_RANGE_X) ** 2 + (q_dy / q_ry) ** 2
                    q_in_range = q_ellipse_val < 1

                    # 如果在范围内，执行链接
                    if q_in_range:
                        if q_target_type == "team":
                            self._log(
                                f"[Q] 链接队友 | 血量:{min_team_hp}% | 距离:{min_dist:.0f}"
                            )
                            self.tap_skill(KEY_CAST_1, "一技能(链接队友)")
                        else:
                            self._log(f"[Q] 链接敌人 | 距离:{min_dist:.0f}")
                            self.tap_skill(KEY_CAST_1, "一技能(链接敌人)")
                        self.last_q_time = current_time
                        self.is_linked = True
                        self.link_target_type = q_target_type
                        self.last_link_time = current_time

        # 链接超时重置：超过12秒没有链接操作，重置链接状态
        if current_time - self.last_link_time > 12:
            self.is_linked = False
            self.link_target_type = None

        # =================================================================
        # 2. 控制技能 (E) - 有敌人时使用
        # E技能用于控制敌人或切换链接形态
        # =================================================================
        # 检查是否有敌人、E技能冷却（6秒）完成、有自身位置、策略允许进攻
        if (
            has_enemy
            and current_time - self.last_e_time > 6
            and self_feet_pos
            and allow_offensive
        ):
            # 寻找最近的敌人
            closest_enemy = None  # 最近的敌人
            min_e_dist = float("inf")  # 最小距离

            for e in enemy_health:
                if isinstance(e, dict) and "pos" in e:
                    epos = e["pos"]
                    # 将敌人头顶坐标转换为脚下坐标
                    enemy_feet_pos = self._convert_to_feet_pos(
                        epos, use_generic_offset=True
                    )
                    if enemy_feet_pos is None:
                        continue
                    # 计算与敌人的距离
                    d = sqrt(
                        (self_feet_pos[0] - enemy_feet_pos[0]) ** 2
                        + (self_feet_pos[1] - enemy_feet_pos[1]) ** 2
                    )
                    if d < min_e_dist:
                        min_e_dist = d
                        closest_enemy = e

            # 如果找到最近敌人，检查是否在E技能范围内
            if closest_enemy is not None:
                epos = closest_enemy["pos"]
                enemy_feet_pos = self._convert_to_feet_pos(
                    epos, use_generic_offset=True
                )
                if enemy_feet_pos is not None:
                    # 计算与敌人的水平和垂直距离
                    e_dx = abs(self_feet_pos[0] - enemy_feet_pos[0])
                    e_dy = abs(self_feet_pos[1] - enemy_feet_pos[1])
                    e_raw_dy = enemy_feet_pos[1] - self_feet_pos[1]

                    # 根据敌人方向选择对应的Y轴范围
                    if e_raw_dy < 0:  # 敌人在上方
                        e_ry = E_RANGE_Y_UP
                    else:  # 敌人在下方
                        e_ry = E_RANGE_Y_DOWN
                    # 椭圆公式判断敌人是否在范围内
                    e_ellipse_val = (e_dx / E_RANGE_X) ** 2 + (e_dy / e_ry) ** 2
                    e_in_range = e_ellipse_val < 1

                    # 如果在范围内，释放E技能
                    if e_in_range:
                        enemy_count = len(enemy_health)
                        self._log(
                            f"[E] 控制 | 敌人数量:{enemy_count} | 距离:{min_e_dist:.0f}"
                        )
                        self.tap_skill(KEY_CAST_2, "二技能(控制)")
                        self.last_e_time = current_time

        # =================================================================
        # 3. 大招逻辑 (R) - 团战/危急时使用
        # 明世隐大招可以为链接目标提供大量治疗或伤害
        # =================================================================
        # 检查大招冷却（60秒）
        if current_time - self.last_ult_time > 60:
            ult_reason = ""  # 记录释放大招的原因
            should_ult = False  # 是否释放大招的标志

            # 条件1：多人团战（敌人2个及以上且有队友）
            if len(enemy_health) >= 2 and len(team_health) >= 1:
                should_ult = True
                ult_reason = f"团战(敌人{len(enemy_health)}个,队友{len(team_health)}个)"

            # 条件2：队友血量危急（最低血量低于40%）
            elif team_health_values and min(team_health_values) < 40:
                should_ult = True
                ult_reason = f"队友危急(最低血量{min(team_health_values)}%)"

            # 条件3：自身血量危急（低于40%）且有敌人
            elif self_health is not None and self_health < 40 and has_enemy:
                should_ult = True
                ult_reason = f"自身危急({self_health}%)"

            # 如果满足释放条件且状态稳定，释放大招
            if should_ult and is_stable:
                self._log(f"[R] 大招 | 原因:{ult_reason}")
                self.tap_skill(KEY_CAST_ULT, "大招(团队增益)")
                self.last_ult_time = current_time

        # =================================================================
        # 4. 普攻 - 有敌人且自身安全时
        # 明世隐普攻为远程攻击，可以在安全距离输出
        # =================================================================
        # 有敌人、自身血量数据有效、血量高于50%、策略允许进攻时执行普攻
        if (
            has_enemy
            and self_health is not None
            and self_health > 50
            and allow_offensive
        ):
            self.basic_attack()

        # =================================================================
        # 5. 召唤师技能 F键（汇流为兵 / 治疗术，由 ACTIVE_SUMMONER_F 开关决定）
        # =================================================================
        if ACTIVE_SUMMONER_F == "confluence":
            # --- 汇流为兵-辅助 ---
            # 效果：召唤元流古琴治疗友方/伤害敌方，额外减少自身所有技能当前50%冷却
            need_confluence = False  # 是否需要使用汇流为兵
            confluence_reason = ""  # 使用原因

            # 条件1：自身血量低于50%
            if self_health is not None and self_health < 50:
                need_confluence = True
                confluence_reason = f"自身血量低({self_health}%)"
            # 条件2：队友血量低于40%
            elif team_health_values and min(team_health_values) < 40:
                need_confluence = True
                confluence_reason = f"队友血量低(最低{min(team_health_values)}%)"

            # 汇流为兵CD=100秒，用90秒做冷却检查（留10秒余量避免浪费按键）
            if (
                need_confluence
                and current_time - self.last_confluence_time > 90
                and is_stable
            ):
                self._log(f"[F] 汇流为兵-辅助 | 原因:{confluence_reason}")
                self.tap_skill(KEY_HEAL, "汇流为兵-辅助")
                self.last_confluence_time = current_time

                # ===== 汇流为兵额外效果：减少自身所有技能当前50%冷却 =====
                # 计算每个技能的剩余CD，减半后更新 last_xxx_time
                # 公式：new_last_time = current_time - cd + remaining * 0.5
                skill_cds = {
                    "Q": (self.last_q_time, 8.0),  # Q技能（链接），代码内检查CD=8秒
                    "E": (self.last_e_time, 6.0),  # E技能（控制），代码内检查CD=6秒
                    "R": (
                        self.last_ult_time,
                        60.0,
                    ),  # 大招（团队增益），代码内检查CD=60秒
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
            need_heal = False  # 是否需要使用治疗术
            heal_reason = ""  # 使用原因

            # 条件1：自身血量低于50%
            if self_health is not None and self_health < 50:
                need_heal = True
                heal_reason = f"自身血量低({self_health}%)"
            # 条件2：队友血量低于40%
            elif team_health_values and min(team_health_values) < 40:
                need_heal = True
                heal_reason = f"队友血量低(最低{min(team_health_values)}%)"

            # 治疗术CD=120秒，用15秒做按键防抖
            if need_heal and current_time - self.last_heal_time > 15 and is_stable:
                self._log(f"[F] 治疗术 | 原因:{heal_reason}")
                self.tap_skill(KEY_HEAL, "治疗术")
                self.last_heal_time = current_time

        # =================================================================
        # 6. 辅助装备技能 (T) - 危急时使用
        # 救赎/星泉等主动装备技能，为队友提供护盾或回血
        # =================================================================
        need_skill4 = False  # 是否需要使用辅助装备技能
        skill4_reason = ""  # 使用原因

        # 条件1：自身血量低于50%
        if self_health is not None and self_health < 50:
            need_skill4 = True
            skill4_reason = f"自身危急({self_health}%)"
        # 条件2：队友血量低于50%且有敌人
        elif team_health_values and min(team_health_values) < 50 and has_enemy:
            need_skill4 = True
            skill4_reason = "队友危急且有敌人"

        # 如果需要、冷却完成（10秒）、状态稳定，则释放辅助装备技能
        if need_skill4 and current_time - self.last_skill4_time > 10 and is_stable:
            self._log(f"[T] 救赎 | 原因:{skill4_reason}")
            self.tap_skill(KEY_SKILL_4, "救赎")
            self.last_skill4_time = current_time

        # =================================================================
        # 7. 恢复 (C) - 脱战后恢复
        # 召唤师技能，在非战斗状态下缓慢恢复血量
        # =================================================================
        # 自身血量低于80%、没有敌人、状态稳定、冷却完成（5秒）
        if self_health is not None and self_health < 80 and not has_enemy:
            if current_time - self.last_recover_time > 5:
                self._log(f"[C] 恢复 | 自身血量:{self_health}%")
                self.tap_skill(KEY_RECOVER, "恢复")
                self.last_recover_time = current_time


# ===== 模块入口函数 =====
def run(queue):
    """
    运行明世隐技能逻辑的入口函数

    参数说明：
        queue: Queue对象，用于接收血量信息的队列

    功能说明：
        创建明世隐技能逻辑实例并启动主循环
        供外部模块调用以启动技能逻辑线程
    """
    mingshiyin = MingshiyinSkillLogic()
    mingshiyin.run(queue)


# 当直接运行此文件时执行的测试代码
if __name__ == "__main__":
    from queue import Queue

    # 输出测试开始分隔线
    logger.info("=" * 60)
    logger.info("明世隐技能逻辑 V2 测试")
    logger.info("=" * 60)

    # 创建技能逻辑实例
    skill_logic = MingshiyinSkillLogic()
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
