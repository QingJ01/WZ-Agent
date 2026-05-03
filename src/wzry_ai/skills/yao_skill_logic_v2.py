"""
瑶技能逻辑 V2 - 基于新技能体系的重构版本
整合老代码的核心功能：坐标偏移、移动禁普攻、大招冷却检测

内置瑶状态检测器 - 基于大招图标颜色识别
检测区域：(1748, 608, 60, 60)
颜色参考值（BGR）：
  - 普通状态: (131, 164, 64)
  - 附身状态: (122, 137, 111)
  - 鹿灵状态: (155, 178, 112)
"""

# ===== 瑶技能配置 =====
# 定义瑶所有技能的配置参数，包括技能ID、类型、按键、冷却时间、触发条件等
YAO_SKILL_CONFIG = {
    "Q": {  # 一技能配置 - 伤害/控制技能
        "skill_id": "Q",  # 技能唯一标识符
        "skill_type": "damage",  # 技能类型：伤害
        "key": "q",  # 对应键盘按键
        "name": "若有人兮",  # 技能中文名称
        "cooldown": 6.0,  # 技能冷却时间（秒）
        "range": 500,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_enemy",
            "enemy_in_range",
        ],  # 触发条件：有敌人在范围内
        "priority": 3,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "E": {  # 二技能配置 - 伤害技能
        "skill_id": "E",  # 技能唯一标识符
        "skill_type": "damage",  # 技能类型：伤害
        "key": "e",  # 对应键盘按键
        "name": "风飒木萧",  # 技能中文名称
        "cooldown": 8.0,  # 技能冷却时间（秒）
        "range": 400,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_enemy",
            "enemy_in_range",
        ],  # 触发条件：有敌人在范围内
        "priority": 4,  # 技能优先级
        "can_use_when_attached": True,  # 附身状态可用
        "can_use_when_detached": True,  # 非附身状态可用
    },
    "R": {  # 大招配置 - 附身技能
        "skill_id": "R",  # 技能唯一标识符
        "skill_type": "attach",  # 技能类型：附身
        "key": "r",  # 对应键盘按键
        "name": "独立兮山之上",  # 技能中文名称
        "cooldown": 2.0,  # 技能冷却时间（秒）
        "range": 350,  # 技能作用范围（像素）
        "trigger_conditions": [
            "has_teammate",
            "teammate_in_range",
        ],  # 触发条件：有队友在范围内
        "trigger_params": {"attach_protect_duration": 5.0},  # 触发参数：附身保护期5秒
        "priority": 2,  # 技能优先级
        "can_use_when_attached": False,  # 附身状态不可用（已经附身）
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
        "can_use_when_attached": False,  # 附身状态不可用（无法使用恢复）
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

# 从queue模块导入Queue和Empty，用于线程间数据传递
from queue import Queue, Empty

# 从enum模块导入Enum，用于定义枚举类型
from enum import Enum

# 导入numpy模块，用于图像处理和数值计算
import numpy as np

# 注意：旧技能体系（HeroSkillManager/SkillContext）已弃用，不再使用
# 所有技能逻辑通过 HeroSkillLogicBase.check_and_use_skills() 实现

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
    HEAD_TO_FEET_OFFSET_GENERIC,
)

# 从基类导入日志记录器
from wzry_ai.skills.hero_skill_logic_base import logger

# 从统一配置导入召唤师技能设置
from wzry_ai.config import ACTIVE_SUMMONER_F
from wzry_ai.config import MINIMAP_SCALE_X, MINIMAP_SCALE_Y

from wzry_ai.battle.decision_recorder import DecisionRecorder
from wzry_ai.battle.yao_decision_brain import (
    CooldownState,
    TargetSummary,
    YaoAction,
    YaoDecisionBrain,
    YaoDecisionState,
)
from wzry_ai.learning.human_demo import build_human_demo_runtime_from_env
from wzry_ai.learning.human_policy import build_human_policy_from_env
from wzry_ai.utils.frame_manager import get_frame
from wzry_ai.utils.runtime_flags import is_ai_control_enabled


# ===== 瑶状态检测器（内置） =====
class YaoState(Enum):
    """
    瑶的三态枚举类

    枚举值说明：
        NORMAL: 普通状态 - 瑶独立行动，可以使用所有技能
        ATTACHED: 附身状态 - 瑶附身在队友身上，提供护盾和技能强化
        DEER: 鹿灵状态 - 瑶被控制技能命中后变成鹿，无法攻击但免疫控制
        UNKNOWN: 未知状态 - 无法确定当前状态
    """

    NORMAL = "normal"  # 普通状态
    ATTACHED = "attached"  # 附身状态
    DEER = "deer"  # 鹿灵状态
    UNKNOWN = "unknown"  # 未知状态


# 大招图标检测区域配置（在屏幕上的位置和大小）
ULT_ICON_REGION = (1748, 608, 60, 60)  # x坐标, y坐标, 宽度, 高度

# 颜色参考值（BGR格式，OpenCV默认格式）
# 通过检测大招图标区域的颜色来判断瑶的当前状态
COLOR_REF = {
    YaoState.NORMAL: (131, 164, 64),  # 普通状态 - 绿色图标
    YaoState.ATTACHED: (122, 137, 111),  # 附身状态 - 蓝灰色图标
    YaoState.DEER: (155, 178, 112),  # 鹿灵状态 - 浅绿色图标
}

# 颜色匹配阈值（欧氏距离阈值）
# 计算检测到的颜色与参考颜色的距离，小于阈值认为是匹配
COLOR_MATCH_THRESHOLD = 30


class YaoStateDetector:
    """
    瑶状态检测器类 - 基于大招图标颜色识别

    功能说明：
        通过检测游戏界面中大招图标区域的颜色来判断瑶的当前状态
        不同状态下大招图标显示不同的颜色

    检测原理：
        1. 提取大招图标区域的图像
        2. 计算区域的平均颜色值
        3. 与参考颜色进行比较，找出最接近的状态
    """

    def __init__(self):
        # 检测区域配置
        self.region = ULT_ICON_REGION
        # 上次检测到的状态，用于状态保持
        self.last_state = YaoState.UNKNOWN

    def detect(self, frame, yolo_self_detected=True):
        """
        检测瑶的当前状态

        参数说明：
            frame: numpy数组，游戏画面帧（BGR格式）
            yolo_self_detected: 布尔值，YOLO是否检测到自身（用于辅助判断）

        返回值：
            YaoState: 当前状态枚举值

        检测流程：
            1. 检查输入帧是否有效
            2. 提取大招图标区域
            3. 计算区域平均颜色
            4. 与参考颜色匹配，找出最接近的状态
            5. 如果匹配距离过大，返回未知状态
        """
        if frame is None:
            return YaoState.UNKNOWN

        try:
            # 提取大招图标区域
            x, y, w, h = self.region
            # 检查区域是否在图像范围内
            if y + h > frame.shape[0] or x + w > frame.shape[1]:
                return YaoState.UNKNOWN

            # 截取大招图标区域
            icon_region = frame[y : y + h, x : x + w]

            # 计算区域平均颜色（BGR三个通道）
            avg_color = np.mean(icon_region, axis=(0, 1))

            # 匹配最接近的状态
            min_distance = float("inf")  # 最小距离，初始化为无穷大
            best_state = YaoState.UNKNOWN  # 最佳匹配状态

            # 遍历所有参考颜色，找出最接近的
            for state, ref_color in COLOR_REF.items():
                # 计算欧几里得距离
                distance = sqrt(
                    sum((avg_color[i] - ref_color[i]) ** 2 for i in range(3))
                )
                if distance < min_distance:
                    min_distance = distance
                    best_state = state

            # 如果距离超过阈值的两倍，认为是未知状态（颜色不匹配任何已知状态）
            if min_distance > COLOR_MATCH_THRESHOLD * 2:
                best_state = YaoState.UNKNOWN

            # 保存并返回检测结果
            self.last_state = best_state
            return best_state

        except (AttributeError, ValueError, RuntimeError) as e:
            # 检测失败时记录错误并返回未知状态
            logger.error(f"检测失败: {e}", exc_info=True)
            return YaoState.UNKNOWN

    def get_state_name(self, state=None):
        """
        获取状态的中文名称

        参数说明：
            state: YaoState枚举值，要获取名称的状态
                   如果为None，使用上次检测到的状态

        返回值：
            字符串：状态的中文名称
        """
        state = state or self.last_state
        name_map = {
            YaoState.NORMAL: "普通",
            YaoState.ATTACHED: "附身",
            YaoState.DEER: "鹿灵",
            YaoState.UNKNOWN: "未知",
        }
        return name_map.get(state, "未知")


# ===== Q技能攻击距离配置（上下非对称半椭圆）=====
# 基于1920x1080分辨率，与verify_attack_range.py保持一致
# 使用椭圆公式判断目标是否在技能范围内：(dx/rx)^2 + (dy/ry)^2 < 1
# 普通状态下的Q技能范围
Q_RANGE_X_NORMAL = 689  # Q技能X轴半轴长度（普通状态）
Q_RANGE_Y_UP_NORMAL = 364  # Q技能Y轴上半轴长度（普通状态）
Q_RANGE_Y_DOWN_NORMAL = 571  # Q技能Y轴下半轴长度（普通状态）
# 附身状态下的Q技能范围（比普通状态提升20%，基于椭圆公式计算）
Q_RANGE_X_ATTACHED = 827  # Q技能X轴半轴长度（附身状态）
Q_RANGE_Y_UP_ATTACHED = 437  # Q技能Y轴上半轴长度（附身状态）
Q_RANGE_Y_DOWN_ATTACHED = 685  # Q技能Y轴下半轴长度（附身状态）

# ===== R技能施法距离配置 =====
# 附身范围和E技能一样，用于判断是否可以附身到队友
R_RANGE_X = 599  # R技能X轴半轴长度
R_RANGE_Y_UP = 316  # R技能Y轴上半轴长度（上方范围）
R_RANGE_Y_DOWN = 496  # R技能Y轴下半轴长度（下方范围）

# ===== E技能攻击距离配置 =====
# 普通状态下的E技能范围
E_RANGE_X = 599  # E技能X轴半轴长度（普通状态）
E_RANGE_Y_UP = 316  # E技能Y轴上半轴长度（普通状态）
E_RANGE_Y_DOWN = 496  # E技能Y轴下半轴长度（普通状态）
# 附身状态下的E技能范围（比普通状态提升20%，基于椭圆公式计算）
E_RANGE_X_ATTACHED = 719  # E技能X轴半轴长度（附身状态）：599 * 1.20 = 718.8 ≈ 719
E_RANGE_Y_UP_ATTACHED = 379  # E技能Y轴上半轴长度（附身状态）：316 * 1.20 = 379.2 ≈ 379
E_RANGE_Y_DOWN_ATTACHED = (
    595  # E技能Y轴下半轴长度（附身状态）：496 * 1.20 = 595.2 ≈ 595
)

# ===== 普攻攻击距离配置 =====
# 在E技能基础上减少5%（累计约10%）
BASIC_ATTACK_RANGE_X = 569  # 普攻X轴半轴长度
BASIC_ATTACK_RANGE_Y_UP = 300  # 普攻Y轴上半轴长度
BASIC_ATTACK_RANGE_Y_DOWN = 471  # 普攻Y轴下半轴长度


class YaoSkillLogic(HeroSkillLogicBase):
    """
    瑶技能逻辑 V2 主类

    功能说明：
        实现瑶英雄的自动技能释放逻辑，包括Q/E技能、大招附身、治疗术等技能的自动判断和释放
        整合坐标偏移计算、技能范围判断、自动维护（买装备/加点）等核心功能
        瑶特色：可以附身到队友身上提供护盾和技能强化

    主要方法：
        check_and_use_skills: 核心技能判断和释放逻辑
        auto_maintenance: 自动买装备和加点
        basic_attack: 普通攻击控制
        _filter_self_health: 自身血量防干扰过滤
        _filter_team_health: 队友血量防干扰过滤
    """

    # 瑶需要更频繁的更新
    QUEUE_TIMEOUT = 0.05

    def _init_hero_specific(self):
        """
        瑶特有的初始化
        """
        # 状态防抖相关变量（瑶特有）
        self.last_attach_status = False  # 上次的附身状态

        # 大招保护期检测相关变量（瑶特有）
        self.last_detach_time = 0  # 上次解除附身时间戳
        self.ULT_PROTECT_DURATION = 2.0  # 大招保护期时长（秒），保护期内禁止再次附身

        # 瑶状态检测器（基于大招图标颜色识别）
        self.state_detector = YaoStateDetector()
        self.current_yao_state = YaoState.UNKNOWN  # 当前瑶的状态

        # 血量防干扰过滤历史记录（预初始化，消除运行时 hasattr 检查）
        self._health_history = {
            "self": [],
            "team": {},  # {idx: [health_values]}
            "last_valid_self": None,
            "last_valid_team": {},
            "confirm_count": 0,
            "pending_health": None,
            "last_pos": None,
            "stable_frames": 0,
        }

        self.decision_brain = YaoDecisionBrain()
        self.decision_recorder = DecisionRecorder()
        self.human_demo_runtime = build_human_demo_runtime_from_env()
        if self.human_demo_runtime is not None:
            self.human_demo_runtime.start()
        self.human_policy_runtime = build_human_policy_from_env()

    def _filter_self_health(self, raw_health, current_time, raw_pos=None):
        """
        自身血量防干扰过滤（含多帧确认 + 检测框稳定性）
        - 连续性检查：None值过多时保持上一次有效值
        - 突变检测：血量突变超过30%时视为干扰（但上升突变更可信）
        - 多帧确认：新检测到的血量需要连续3帧一致才确认
        - 检测框稳定性：位置变化大时延长确认帧数
        - 低血量额外确认：<20%血量需要5帧确认
        """
        history = self._health_history["self"]
        last_valid = self._health_history["last_valid_self"]

        # 添加到历史记录（最多保留3帧）
        history.append((raw_health, current_time))
        if len(history) > 3:
            history.pop(0)

        # 检测框稳定性检查
        pos_stable = True
        if raw_pos is not None and self._health_history["last_pos"] is not None:
            last_x, last_y = self._health_history["last_pos"]
            curr_x, curr_y = raw_pos
            pos_change = ((curr_x - last_x) ** 2 + (curr_y - last_y) ** 2) ** 0.5
            if pos_change > 50:  # 位置变化超过50像素，认为检测框不稳定
                pos_stable = False
                self._health_history["stable_frames"] = 0
            else:
                self._health_history["stable_frames"] += 1

        # 更新位置记录
        if raw_pos is not None:
            self._health_history["last_pos"] = raw_pos

        # 如果当前值为None，但有历史有效值，检查是否需要保持
        if raw_health is None:
            recent_valid = [h for h, t in history[-3:] if h is not None]
            if recent_valid and last_valid is not None:
                return last_valid
            return None

        # 动态确认参数
        CONFIRM_THRESHOLD = 5  # 血量变化在5%以内视为一致
        BASE_CONFIRM_FRAMES = 2  # 基础确认帧数

        # 低血量需要更多确认帧
        LOW_HP_THRESHOLD = 20
        LOW_HP_CONFIRM_FRAMES = 3

        # 检测框不稳定时需要更多确认帧
        UNSTABLE_CONFIRM_FRAMES = 3

        # 计算实际需要的确认帧数
        required_frames = BASE_CONFIRM_FRAMES
        if raw_health < LOW_HP_THRESHOLD:
            required_frames = max(required_frames, LOW_HP_CONFIRM_FRAMES)
        if not pos_stable:
            required_frames = max(required_frames, UNSTABLE_CONFIRM_FRAMES)

        pending = self._health_history["pending_health"]
        confirm_count = self._health_history["confirm_count"]

        if last_valid is None:
            # 首次检测到血量，启动确认流程
            if pending is None:
                self._health_history["pending_health"] = raw_health
                self._health_history["confirm_count"] = 1
                self._log(
                    f"[血量确认] 首次检测到自身血量 {raw_health}%，开始确认(需{required_frames}帧)..."
                )
                return None
            else:
                if abs(raw_health - pending) <= CONFIRM_THRESHOLD:
                    confirm_count += 1
                    self._health_history["confirm_count"] = confirm_count
                    if confirm_count >= required_frames:
                        # 低血量额外检查：确认值是否合理
                        if pending < LOW_HP_THRESHOLD:
                            self._log(f"[血量警告] 确认低血量 {pending}%，延长观察")
                        self._log(
                            f"[血量确认] 自身血量 {pending}% 已确认（连续{confirm_count}帧）"
                        )
                        self._health_history["last_valid_self"] = pending
                        self._health_history["pending_health"] = None
                        self._health_history["confirm_count"] = 0
                        return pending
                    else:
                        self._log(
                            f"[血量确认] 自身血量 {pending}% 确认中 ({confirm_count}/{required_frames})"
                        )
                        return None
                else:
                    self._log(
                        f"[血量确认] 血量波动 {pending}% -> {raw_health}%，重置确认"
                    )
                    self._health_history["pending_health"] = raw_health
                    self._health_history["confirm_count"] = 1
                    return None

        # 已有有效值，进行突变检测
        # 注：25%以内的血量变化视为正常（接受战斗中的伤害/治疗）
        MUTATION_THRESHOLD = 25
        change = abs(raw_health - last_valid)
        if change > MUTATION_THRESHOLD:
            # 突变方向判断：上升突变更可信（可能是从错误恢复）
            is_rising = raw_health > last_valid

            # 下降突变到极低血量（<10%），极可能是检测错误
            if not is_rising and raw_health < 10:
                self._log(
                    f"[血量过滤] 下降突变到极低血量 {last_valid:.0f}% -> {raw_health:.0f}%，视为干扰"
                )
                return last_valid

            if len(history) >= 2:
                prev_health = (
                    history[-2][0] if history[-2][0] is not None else last_valid
                )
                prev_change = abs(raw_health - prev_health)

                if is_rising and raw_health > 80:
                    # 上升突变到高血量（如1%->93%），更可能是恢复正常
                    self._log(
                        f"[血量过滤] 上升突变 {last_valid:.0f}% -> {raw_health:.0f}%，可能是恢复，接受新值"
                    )
                    self._health_history["last_valid_self"] = raw_health
                    return raw_health
                elif prev_change > MUTATION_THRESHOLD:
                    # 连续两帧变化都超过阈值，视为干扰
                    self._log(
                        f"[血量过滤] 自身血量突变 {last_valid:.0f}% -> {raw_health:.0f}%，视为干扰"
                    )
                    return last_valid
                else:
                    # 前一帧稳定，当前帧突变，可能是真实变化
                    self._log(
                        f"[血量过滤] 血量变化 {last_valid:.0f}% -> {raw_health:.0f}%（前一帧稳定），接受新值"
                    )
            else:
                # 历史记录不足，但变化超过阈值，谨慎处理
                if not is_rising and raw_health < 20:
                    # 下降突变到较低血量，可能是错误
                    self._log(
                        f"[血量过滤] 下降突变 {last_valid:.0f}% -> {raw_health:.0f}%（历史不足），视为干扰"
                    )
                    return last_valid
                else:
                    # 其他情况接受变化
                    self._log(
                        f"[血量过滤] 血量变化 {last_valid:.0f}% -> {raw_health:.0f}%（历史不足但合理），接受新值"
                    )

        # 通过过滤，更新有效值
        self._health_history["last_valid_self"] = raw_health
        return raw_health

    def _filter_team_health(self, raw_team_health, current_time):
        """
        队友血量防干扰过滤（含多帧确认 + 位置跟踪）
        - 去除血量异常的目标（如野怪、小兵）
        - 平滑处理：血量突变时进行插值
        - 多帧确认：新检测到的队友需要连续2帧一致才确认
        - 位置跟踪：基于位置匹配确保同一索引指向同一目标
        """
        filtered = []
        team_history = self._health_history["team"]
        last_valid_team = self._health_history["last_valid_team"]

        # 初始化确认状态和位置跟踪
        if "team_confirm" not in self._health_history:
            self._health_history["team_confirm"] = {}  # {idx: count}
        if "team_pending" not in self._health_history:
            self._health_history["team_pending"] = {}  # {idx: (health, pos)}
        if "team_positions" not in self._health_history:
            self._health_history["team_positions"] = {}  # {idx: (x, y)}

        team_confirm = self._health_history["team_confirm"]
        team_pending = self._health_history["team_pending"]
        team_positions = self._health_history["team_positions"]

        # 多帧确认参数
        CONFIRM_THRESHOLD = 5  # 队友血量变化在5%以内视为一致
        BASE_CONFIRM_FRAMES = 2  # 基础确认帧数
        POSITION_THRESHOLD = 100  # 位置变化阈值，超过100像素认为是不同目标

        # 大幅下降阈值：超过此值视为可疑下降（需要更多确认）
        SUSPICIOUS_DROP = 40  # 下降超过40%视为可疑
        DROP_CONFIRM_FRAMES = 4  # 可疑下降需要4帧确认
        LOW_HP_THRESHOLD = 25  # 低血量阈值

        # 基于位置匹配重新索引队友
        matched_teammates = []
        for idx, teammate in enumerate(raw_team_health):
            if (
                not isinstance(teammate, dict)
                or "health" not in teammate
                or "pos" not in teammate
            ):
                continue

            current_pos = teammate["pos"]
            current_hp = teammate["health"]

            # 尝试匹配到已知队友
            matched_idx = None
            for known_idx, known_pos in team_positions.items():
                if known_pos is not None:
                    dist = sqrt(
                        (current_pos[0] - known_pos[0]) ** 2
                        + (current_pos[1] - known_pos[1]) ** 2
                    )
                    if dist < POSITION_THRESHOLD:
                        matched_idx = known_idx
                        break

            if matched_idx is None:
                # 新队友，分配新索引
                matched_idx = idx

            matched_teammates.append((matched_idx, teammate, current_pos, current_hp))

        # 更新位置记录
        new_positions = {}
        for matched_idx, teammate, pos, hp in matched_teammates:
            new_positions[matched_idx] = pos
        team_positions.clear()
        team_positions.update(new_positions)

        # 处理每个匹配的队友
        for matched_idx, teammate, current_pos, raw_hp in matched_teammates:
            # 创建 teammate 的副本，避免修改原始对象
            teammate = dict(teammate)

            # 初始化该队友的历史记录
            if matched_idx not in team_history:
                team_history[matched_idx] = []

            history = team_history[matched_idx]
            history.append((raw_hp, current_time))
            if len(history) > 5:
                history.pop(0)

            last_valid = last_valid_team.get(matched_idx)
            last_pos = team_positions.get(matched_idx)

            # 合理性检查：血量应该在0-100之间
            if raw_hp < 0 or raw_hp > 100:
                if last_valid is not None:
                    teammate = dict(teammate)
                    teammate["health"] = last_valid
                    filtered.append(teammate)
                continue

            # 位置突变检测：如果位置变化太大，可能是不同目标
            if last_pos is not None:
                dist = sqrt(
                    (current_pos[0] - last_pos[0]) ** 2
                    + (current_pos[1] - last_pos[1]) ** 2
                )
                if dist > POSITION_THRESHOLD:
                    self._log(
                        f"[血量过滤] 队友{matched_idx}位置突变 ({last_pos[0]:.0f},{last_pos[1]:.0f}) -> ({current_pos[0]:.0f},{current_pos[1]:.0f})，可能是不同目标"
                    )
                    # 重置该索引的历史记录
                    team_history[matched_idx] = [(raw_hp, current_time)]
                    team_pending[matched_idx] = (raw_hp, current_pos)
                    team_confirm[matched_idx] = 1
                    if last_valid is not None:
                        teammate = dict(teammate)
                        teammate["health"] = last_valid
                        filtered.append(teammate)
                    continue

            # 多帧确认：新队友或血量大幅变化时需要确认
            change = abs(raw_hp - last_valid) if last_valid is not None else 0
            is_drop = last_valid is not None and raw_hp < last_valid  # 是否是下降
            is_suspicious_drop = is_drop and change > SUSPICIOUS_DROP  # 是否可疑下降

            # 计算需要的确认帧数
            required_frames = BASE_CONFIRM_FRAMES
            if is_suspicious_drop:
                required_frames = DROP_CONFIRM_FRAMES  # 可疑下降需要更多确认
            elif raw_hp < LOW_HP_THRESHOLD:
                required_frames = 3  # 低血量需要3帧确认

            if last_valid is None or change > 20:
                pending_info = team_pending.get(matched_idx)

                if pending_info is None:
                    # 首次检测到该队友或血量大幅变化，启动确认
                    team_pending[matched_idx] = (raw_hp, current_pos)
                    team_confirm[matched_idx] = 1
                    if is_suspicious_drop:
                        self._log(
                            f"[血量警告] 队友{matched_idx}血量大幅下降 {last_valid}%->{raw_hp}%，需{required_frames}帧确认"
                        )
                    else:
                        self._log(
                            f"[血量确认] 队友{matched_idx}血量 {raw_hp}% 开始确认(需{required_frames}帧)..."
                        )
                    if last_valid is not None:
                        teammate = dict(teammate)
                        teammate["health"] = last_valid
                        filtered.append(teammate)
                    continue
                else:
                    pending_hp, pending_pos = pending_info
                    # 检查是否一致（血量和位置）
                    hp_consistent = abs(raw_hp - pending_hp) <= CONFIRM_THRESHOLD
                    pos_dist = sqrt(
                        (current_pos[0] - pending_pos[0]) ** 2
                        + (current_pos[1] - pending_pos[1]) ** 2
                    )
                    pos_consistent = pos_dist < POSITION_THRESHOLD / 2

                    if hp_consistent and pos_consistent:
                        team_confirm[matched_idx] = team_confirm.get(matched_idx, 0) + 1
                        if team_confirm[matched_idx] >= required_frames:
                            # 最终确认前检查：可疑下降到低血量需要额外验证
                            if is_suspicious_drop and pending_hp < LOW_HP_THRESHOLD:
                                self._log(
                                    f"[血量警告] 队友{matched_idx}确认低血量 {pending_hp}%，可能存在检测错误"
                                )
                            self._log(
                                f"[血量确认] 队友{matched_idx}血量 {pending_hp}% 已确认"
                            )
                            last_valid_team[matched_idx] = pending_hp
                            team_pending[matched_idx] = None
                            team_confirm[matched_idx] = 0
                            teammate = dict(teammate)
                            teammate["health"] = pending_hp
                            filtered.append(teammate)
                            continue
                        else:
                            self._log(
                                f"[血量确认] 队友{matched_idx}血量 {pending_hp}% 确认中 ({team_confirm[matched_idx]}/{required_frames})"
                            )
                            if last_valid is not None:
                                teammate = dict(teammate)
                                teammate["health"] = last_valid
                                filtered.append(teammate)
                            continue
                    else:
                        # 不一致，重置
                        self._log(
                            f"[血量确认] 队友{matched_idx}波动 血量:{pending_hp}%->{raw_hp}% 位置变化:{pos_dist:.0f}px，重置确认"
                        )
                        team_pending[matched_idx] = (raw_hp, current_pos)
                        team_confirm[matched_idx] = 1
                        if last_valid is not None:
                            teammate = dict(teammate)
                            teammate["health"] = last_valid
                            filtered.append(teammate)
                        continue

            # 突变检测（已通过多帧确认的）
            if last_valid is not None:
                change = abs(raw_hp - last_valid)
                if change > 40:
                    if len(history) >= 2:
                        trend = sum(
                            [h for h, t in history[-3:] if h is not None]
                        ) / len([h for h, t in history[-3:] if h is not None])
                        if abs(raw_hp - trend) > 30:
                            self._log(
                                f"[血量过滤] 队友{matched_idx}血量突变 {last_valid:.0f}% -> {raw_hp:.0f}%，平滑处理"
                            )
                            teammate = dict(teammate)
                            teammate["health"] = int((last_valid + raw_hp) / 2)

            last_valid_team[matched_idx] = teammate["health"]
            filtered.append(teammate)

        # 清理已消失的队友历史记录
        current_indices = set(idx for idx, _, _, _ in matched_teammates)
        for idx in list(team_history.keys()):
            if idx not in current_indices:
                del team_history[idx]
                if idx in last_valid_team:
                    del last_valid_team[idx]
                if idx in team_pending:
                    del team_pending[idx]
                if idx in team_confirm:
                    del team_confirm[idx]
                if idx in team_positions:
                    del team_positions[idx]

        return filtered

    def _minimap_distance_to_screen(self, m1_self, m1_target):
        """
        将小地图上两点的距离转换为全屏像素距离

        参数说明：
            m1_self: 自身在小地图的位置 (x, y)
            m1_target: 目标在小地图的位置 (x, y) 或 (x, y, class_id)

        返回值：
            tuple: (dx, dy) 全屏像素距离（带符号，正值=右/下，负值=左/上）
        """
        dx = (m1_target[0] - m1_self[0]) * MINIMAP_SCALE_X
        dy = (m1_target[1] - m1_self[1]) * MINIMAP_SCALE_Y
        return dx, dy

    def _check_and_use_skills_with_decision_brain(self):
        skill_policy = (
            self.health_info.get("skill_policy", "aggressive")
            if self.health_info
            else "aggressive"
        )

        if skill_policy == "disabled":
            return

        control_enabled = is_ai_control_enabled()

        if self.paused:
            if control_enabled:
                self.auto_maintenance()
            return

        if not self.health_info:
            return

        if control_enabled:
            self.auto_maintenance()

        current_time = time.time()
        state = self._build_decision_state(current_time, skill_policy)
        if state is None:
            return

        self._record_human_demo_action(state, current_time)
        decision = self.decision_brain.decide(state)
        selected_action = self._select_human_policy_action(
            state, decision.selected_action
        )
        if control_enabled:
            executed_action = self._execute_decision_action(
                selected_action, current_time, state
            )
            action_source = self._decision_action_source(
                selected_action,
                decision.selected_action,
            )
        else:
            executed_action = None
            action_source = "control_disabled"
        self.decision_recorder.record(
            state=state,
            actions=decision.actions,
            fallback_action=decision.selected_action,
            selected_action=selected_action,
            executed_action=executed_action,
            action_source=action_source,
            model_confidence=self._decision_model_confidence(selected_action),
            source="yao_policy_v2",
        )

    def _select_human_policy_action(self, state, fallback_action):
        runtime = getattr(self, "human_policy_runtime", None)
        if runtime is None:
            return fallback_action
        prediction = runtime.predict(state)
        if prediction is None:
            return fallback_action
        if prediction.confidence < runtime.confidence_threshold:
            return fallback_action
        allowed = {
            "no_op",
            "stay_attached",
            "cast_q",
            "cast_e",
            "attach_teammate",
            "cast_f",
            "cast_active_item",
            "recover",
            "basic_attack",
            "level_ult",
            "level_1",
            "level_2",
            "buy_item",
        }
        if prediction.action not in allowed:
            return fallback_action
        if self._policy_would_override_protected_rule(prediction.action, fallback_action):
            return fallback_action
        return YaoAction(
            prediction.action,
            f"human_policy_confidence_{prediction.confidence:.2f}",
            999,
            target={"source": "human_policy", "confidence": prediction.confidence},
        )

    def _policy_would_override_protected_rule(self, prediction_action, fallback_action):
        if fallback_action is None:
            return False
        if prediction_action == fallback_action.action:
            return False
        protected_actions = {
            "attach_teammate",
            "cast_f",
            "cast_active_item",
            "recover",
        }
        if fallback_action.action in protected_actions:
            return True
        if fallback_action.action == "cast_q" and fallback_action.reason == "deer_state_escape":
            return True
        return False

    def _decision_action_source(self, selected_action, fallback_action) -> str:
        if selected_action is None:
            return "none"
        target = selected_action.target if isinstance(selected_action.target, dict) else {}
        if target.get("source") == "human_policy":
            return "model"
        if fallback_action is not None and selected_action.action == fallback_action.action:
            return "rule"
        return "rule"

    def _decision_model_confidence(self, selected_action):
        if selected_action is None or not isinstance(selected_action.target, dict):
            return None
        if selected_action.target.get("source") != "human_policy":
            return None
        confidence = selected_action.target.get("confidence")
        try:
            return float(confidence)
        except (TypeError, ValueError):
            return None

    def _record_human_demo_action(self, state, current_time):
        runtime = getattr(self, "human_demo_runtime", None)
        if runtime is None:
            return
        human_action = runtime.consume_latest_action(now=current_time, max_age=0.6)
        if human_action is None:
            return
        runtime.record_state_action(state, human_action)

    def _build_decision_state(self, current_time, skill_policy):
        raw_self_health = self.health_info.get("self_health")
        raw_team_health = self.health_info.get("team_health", [])
        enemy_health = self.health_info.get("enemy_health", [])
        self_pos = self.health_info.get("self_pos")
        is_moving = self.health_info.get("is_moving", False)
        minimap_data = self.health_info.get("minimap_data")

        self_health = self._filter_self_health(
            raw_self_health, current_time, self_pos
        )
        team_health = self._filter_team_health(raw_team_health, current_time)
        self.set_moving(is_moving)

        frame = get_frame(timeout=0.02)
        if frame is not None:
            yolo_self_detected = raw_self_health is not None or self_health is not None
            self.current_yao_state = self.state_detector.detect(
                frame, yolo_self_detected
            )
        else:
            if raw_self_health is None and self_pos is not None:
                self.current_yao_state = YaoState.ATTACHED
            elif raw_self_health is not None or self_health is not None:
                self.current_yao_state = YaoState.NORMAL
            else:
                self.current_yao_state = YaoState.UNKNOWN

        yao_state = self.current_yao_state
        is_attached = yao_state == YaoState.ATTACHED
        is_deer = yao_state == YaoState.DEER

        if is_attached != self.last_attach_status:
            self.last_status_change_time = current_time
            if self.last_attach_status and not is_attached:
                self.last_detach_time = current_time
                self._log(
                    f"[R] detached, protect window {self.ULT_PROTECT_DURATION:.1f}s"
                )
            self.last_attach_status = is_attached

        is_stable = current_time - self.last_status_change_time > 0.6
        protect_duration = current_time - self.last_detach_time
        is_in_protect = protect_duration < self.ULT_PROTECT_DURATION

        self_feet_pos = (
            self._convert_to_feet_pos(self_pos) if self_pos is not None else None
        )
        teammates = self._build_teammate_targets(
            self_feet_pos, team_health, minimap_data
        )
        enemies = self._build_enemy_targets(
            self_feet_pos, enemy_health, minimap_data, is_attached, is_deer
        )

        if ACTIVE_SUMMONER_F == "confluence":
            f_ready = current_time - self.last_confluence_time > 90
        else:
            f_ready = current_time - self.last_heal_time > 5

        cooldowns = CooldownState(
            q_ready=current_time - self.last_q_time > 4,
            e_ready=current_time - self.last_e_time > 5,
            r_ready=(
                current_time - self.last_ult_time > 5
                and not is_attached
                and raw_self_health is not None
                and not is_in_protect
            ),
            f_ready=f_ready,
            active_item_ready=current_time - self.last_skill4_time > 5,
            recover_ready=current_time - self.last_recover_time > 5,
            attack_ready=current_time - self.last_attack_time > 0.5,
        )

        return YaoDecisionState(
            yao_state=yao_state.value,
            battle_state=self.health_info.get("battle_state", "follow"),
            skill_policy=skill_policy,
            self_health=self_health,
            is_moving=is_moving,
            is_stable=is_stable,
            teammates=tuple(teammates),
            enemies=tuple(enemies),
            cooldowns=cooldowns,
        )

    def _build_teammate_targets(self, self_feet_pos, team_health, minimap_data):
        teammates = []
        if self_feet_pos and team_health:
            for target in team_health:
                if not isinstance(target, dict) or "pos" not in target:
                    continue
                team_feet_pos = self._convert_to_feet_pos(
                    target["pos"], use_generic_offset=True
                )
                if team_feet_pos is None:
                    continue
                dx, dy, raw_dy, distance = self._delta_from_feet(
                    self_feet_pos, team_feet_pos
                )
                teammates.append(
                    TargetSummary(
                        distance=distance,
                        health=self._health_value(target),
                        in_r_range=self._ellipse_in_range(
                            dx, dy, raw_dy, R_RANGE_X, R_RANGE_Y_UP, R_RANGE_Y_DOWN
                        ),
                        in_f_range=self._ellipse_in_range(
                            dx,
                            dy,
                            raw_dy,
                            HEAL_RANGE_X,
                            HEAL_RANGE_Y_UP,
                            HEAL_RANGE_Y_DOWN,
                        ),
                        in_active_item_range=self._ellipse_in_range(
                            dx,
                            dy,
                            raw_dy,
                            REDEMPTION_RANGE_X,
                            REDEMPTION_RANGE_Y_UP,
                            REDEMPTION_RANGE_Y_DOWN,
                        ),
                    )
                )

        if not teammates and minimap_data:
            m1_self = minimap_data.get("g_center")
            m1_teammates = minimap_data.get("b_centers", [])
            if m1_self and m1_teammates:
                for target in m1_teammates:
                    dx_screen, dy_screen = self._minimap_distance_to_screen(
                        m1_self, target
                    )
                    dx = abs(dx_screen)
                    dy = abs(dy_screen)
                    distance = sqrt(dx_screen**2 + dy_screen**2)
                    teammates.append(
                        TargetSummary(
                            distance=distance,
                            source="minimap",
                            in_r_range=self._ellipse_in_range(
                                dx,
                                dy,
                                dy_screen,
                                R_RANGE_X,
                                R_RANGE_Y_UP,
                                R_RANGE_Y_DOWN,
                            ),
                            in_f_range=self._ellipse_in_range(
                                dx,
                                dy,
                                dy_screen,
                                HEAL_RANGE_X,
                                HEAL_RANGE_Y_UP,
                                HEAL_RANGE_Y_DOWN,
                            ),
                            in_active_item_range=self._ellipse_in_range(
                                dx,
                                dy,
                                dy_screen,
                                REDEMPTION_RANGE_X,
                                REDEMPTION_RANGE_Y_UP,
                                REDEMPTION_RANGE_Y_DOWN,
                            ),
                        )
                    )
        return teammates

    def _build_enemy_targets(
        self, self_feet_pos, enemy_health, minimap_data, is_attached, is_deer
    ):
        enemies = []
        if self_feet_pos and enemy_health:
            for target in enemy_health:
                if not isinstance(target, dict) or "pos" not in target:
                    continue
                enemy_feet_pos = self._convert_to_feet_pos(
                    target["pos"], use_generic_offset=True
                )
                if enemy_feet_pos is None:
                    continue
                dx, dy, raw_dy, distance = self._delta_from_feet(
                    self_feet_pos, enemy_feet_pos
                )
                enemies.append(
                    TargetSummary(
                        distance=distance,
                        health=self._health_value(target),
                        in_q_range=is_deer
                        or self._ellipse_in_range(
                            dx,
                            dy,
                            raw_dy,
                            Q_RANGE_X_ATTACHED if is_attached else Q_RANGE_X_NORMAL,
                            Q_RANGE_Y_UP_ATTACHED
                            if is_attached
                            else Q_RANGE_Y_UP_NORMAL,
                            Q_RANGE_Y_DOWN_ATTACHED
                            if is_attached
                            else Q_RANGE_Y_DOWN_NORMAL,
                        ),
                        in_e_range=(
                            not is_deer
                            and self._ellipse_in_range(
                                dx,
                                dy,
                                raw_dy,
                                E_RANGE_X_ATTACHED if is_attached else E_RANGE_X,
                                E_RANGE_Y_UP_ATTACHED
                                if is_attached
                                else E_RANGE_Y_UP,
                                E_RANGE_Y_DOWN_ATTACHED
                                if is_attached
                                else E_RANGE_Y_DOWN,
                            )
                        ),
                        in_attack_range=self._ellipse_in_range(
                            dx,
                            dy,
                            raw_dy,
                            BASIC_ATTACK_RANGE_X,
                            BASIC_ATTACK_RANGE_Y_UP,
                            BASIC_ATTACK_RANGE_Y_DOWN,
                        ),
                    )
                )

        if not enemies and minimap_data:
            m1_self = minimap_data.get("g_center")
            m1_enemies = minimap_data.get("r_centers", [])
            if m1_self and m1_enemies:
                for target in m1_enemies:
                    dx_screen, dy_screen = self._minimap_distance_to_screen(
                        m1_self, target
                    )
                    dx = abs(dx_screen)
                    dy = abs(dy_screen)
                    distance = sqrt(dx_screen**2 + dy_screen**2)
                    enemies.append(
                        TargetSummary(
                            distance=distance,
                            source="minimap",
                            in_q_range=is_deer
                            or self._ellipse_in_range(
                                dx,
                                dy,
                                dy_screen,
                                Q_RANGE_X_ATTACHED
                                if is_attached
                                else Q_RANGE_X_NORMAL,
                                Q_RANGE_Y_UP_ATTACHED
                                if is_attached
                                else Q_RANGE_Y_UP_NORMAL,
                                Q_RANGE_Y_DOWN_ATTACHED
                                if is_attached
                                else Q_RANGE_Y_DOWN_NORMAL,
                            ),
                            in_e_range=(
                                not is_deer
                                and self._ellipse_in_range(
                                    dx,
                                    dy,
                                    dy_screen,
                                    E_RANGE_X_ATTACHED if is_attached else E_RANGE_X,
                                    E_RANGE_Y_UP_ATTACHED
                                    if is_attached
                                    else E_RANGE_Y_UP,
                                    E_RANGE_Y_DOWN_ATTACHED
                                    if is_attached
                                    else E_RANGE_Y_DOWN,
                                )
                            ),
                            in_attack_range=self._ellipse_in_range(
                                dx,
                                dy,
                                dy_screen,
                                BASIC_ATTACK_RANGE_X,
                                BASIC_ATTACK_RANGE_Y_UP,
                                BASIC_ATTACK_RANGE_Y_DOWN,
                            ),
                        )
                    )
        return enemies

    def _delta_from_feet(self, self_feet_pos, target_feet_pos):
        raw_dx = target_feet_pos[0] - self_feet_pos[0]
        raw_dy = target_feet_pos[1] - self_feet_pos[1]
        dx = abs(raw_dx)
        dy = abs(raw_dy)
        return dx, dy, raw_dy, sqrt(raw_dx**2 + raw_dy**2)

    def _ellipse_in_range(self, dx, dy, raw_dy, range_x, range_y_up, range_y_down):
        if range_x <= 0:
            return False
        range_y = range_y_up if raw_dy < 0 else range_y_down
        if range_y <= 0:
            return False
        return (dx / range_x) ** 2 + (dy / range_y) ** 2 < 1

    def _health_value(self, value):
        if isinstance(value, dict):
            return value.get("health")
        return value

    def _execute_decision_action(
        self, action: YaoAction | None, current_time, state: YaoDecisionState
    ):
        if action is None:
            return None

        if action.action == "no_op":
            return action

        if action.action == "stay_attached":
            return action

        if action.action == "cast_q":
            self.tap_skill(KEY_CAST_1, "一技能")
            self.last_q_time = current_time
            if state.yao_state == "deer":
                self.last_e_time = 0
                self.last_q_time = 0
                self.last_ult_time = 0
                self._log("[Q] deer state cleared, Q/E/R cooldowns refreshed")
            return action

        if action.action == "cast_e":
            self.tap_skill(KEY_CAST_2, "二技能")
            self.last_e_time = current_time
            return action

        if action.action == "attach_teammate":
            self.tap_skill(KEY_CAST_ULT, "大招(附身)")
            self.last_ult_time = current_time
            self.locked_target = None
            self.lock_frame_count = 0
            return action

        if action.action == "cast_f":
            if ACTIVE_SUMMONER_F == "confluence":
                self.tap_skill(KEY_HEAL, "汇流为兵-辅助")
                self.last_confluence_time = current_time
                self._apply_confluence_cooldown_reduction(current_time)
            else:
                self.tap_skill(KEY_HEAL, "治疗术")
                self.last_heal_time = current_time
            return action

        if action.action == "cast_active_item":
            self.tap_skill(KEY_SKILL_4, "救赎")
            self.last_skill4_time = current_time
            return action

        if action.action == "recover":
            self.tap_skill(KEY_RECOVER, "恢复")
            self.last_recover_time = current_time
            return action

        if action.action == "basic_attack":
            self.basic_attack()
            return action

        if action.action == "level_ult":
            self.tap_skill(KEY_LEVEL_ULT, "升级大招")
            self.last_levelup_time = current_time
            return action

        if action.action == "level_1":
            self.tap_skill(KEY_LEVEL_1, "升级技能1")
            self.last_levelup_time = current_time
            return action

        if action.action == "level_2":
            self.tap_skill(KEY_LEVEL_2, "升级技能2")
            self.last_levelup_time = current_time
            return action

        if action.action == "buy_item":
            self.tap_skill(KEY_BUY_ITEM, "买装备")
            self.last_buy_time = current_time
            return action

        return None

    def _apply_confluence_cooldown_reduction(self, current_time):
        skill_cds = {
            "Q": (self.last_q_time, 4.0),
            "E": (self.last_e_time, 5.0),
            "R": (self.last_ult_time, 5.0),
        }
        for skill_name, (last_time, cd) in skill_cds.items():
            remaining = max(0, cd - (current_time - last_time))
            if remaining <= 0:
                continue
            new_last_time = current_time - cd + remaining * 0.5
            if skill_name == "Q":
                self.last_q_time = new_last_time
            elif skill_name == "E":
                self.last_e_time = new_last_time
            elif skill_name == "R":
                self.last_ult_time = new_last_time

    def _legacy_check_and_use_skills(self):
        """检查并使用技能 - 核心逻辑"""

        # ===== 战斗状态机技能策略 =====
        # 从移动融合逻辑传来的战斗状态，决定当前应该使用哪些技能
        # 策略说明：
        #   aggressive   - 全技能输出（FIGHT状态，敌人在附近）
        #   conservative - 被动反击：有敌人时允许进攻，无敌人时仅恢复/探草（FOLLOW状态）
        #   defensive    - 防御技能优先：治疗/保命/恢复，不主动进攻（RETREAT状态）
        #   disabled     - 完全禁止释放（RECALL回城状态）
        skill_policy = (
            self.health_info.get("skill_policy", "aggressive")
            if self.health_info
            else "aggressive"
        )

        # 回城中完全禁止技能释放
        if skill_policy == "disabled":
            return

        # 是否允许防御性/治疗技能（治疗术、救赎、恢复）
        allow_defensive = skill_policy in ("aggressive", "defensive", "conservative")
        # 是否允许大招附身（任何非禁用状态都允许，附身是瑶的核心保命手段）
        allow_ult = skill_policy != "disabled"
        # 注意：allow_offensive 在数据解包后计算（需要 enemy_health 信息）

        if self.paused:
            self.auto_maintenance()
            return

        if not self.health_info:
            return

        self.auto_maintenance()

        current_time = time.time()

        # --- 数据解包 ---
        raw_self_health = self.health_info.get("self_health")
        raw_team_health = self.health_info.get("team_health", [])
        enemy_health = self.health_info.get("enemy_health", [])
        self_pos = self.health_info.get("self_pos")
        is_moving = self.health_info.get("is_moving", False)
        frame = get_frame(timeout=0.02)

        # --- 小地图坐标数据（模态2补充方案） ---
        minimap_data = self.health_info.get("minimap_data")

        # --- 计算进攻许可（依赖 enemy_health 数据） ---
        # aggressive: 全面进攻（FIGHT状态）
        # conservative: 被动反击——有敌人时允许攻击，无敌人时不攻击（FOLLOW状态）
        # defensive/disabled: 不进攻（撤退/回城时专注逃跑）
        has_enemy = len(enemy_health) > 0
        allow_offensive = (skill_policy == "aggressive") or (
            skill_policy == "conservative" and has_enemy
        )

        # --- 血量防干扰过滤 ---
        # 自身血量过滤：连续性检查 + 突变检测 + 检测框稳定性
        raw_self_pos = self.health_info.get("self_pos") if self.health_info else None
        self_health = self._filter_self_health(
            raw_self_health, current_time, raw_self_pos
        )

        # 队友血量过滤：去除异常值 + 平滑处理
        team_health = self._filter_team_health(raw_team_health, current_time)

        # 更新移动状态
        self.set_moving(is_moving)

        # --- 瑶三态检测（基于大招图标颜色） ---
        if frame is not None:
            yolo_self_detected = self_health is not None
            self.current_yao_state = self.state_detector.detect(
                frame, yolo_self_detected
            )
        else:
            # 备用方案：基于血量数据判断
            if self_health is None and self_pos is not None:
                self.current_yao_state = YaoState.ATTACHED
            elif self_health is not None:
                self.current_yao_state = YaoState.NORMAL
            else:
                self.current_yao_state = YaoState.UNKNOWN

        yao_state = self.current_yao_state
        is_attached = yao_state == YaoState.ATTACHED
        is_deer = yao_state == YaoState.DEER

        # 状态切换防抖 & 大招保护期检测
        if is_attached != self.last_attach_status:
            self.last_status_change_time = current_time
            # 记录解除附身时间（用于保护期检测）
            if self.last_attach_status and not is_attached:
                self.last_detach_time = current_time
                self._log(f"[大招] 解除附身，保护期开始 {self.ULT_PROTECT_DURATION}秒")
            self.last_attach_status = is_attached

        stable_duration = current_time - self.last_status_change_time
        is_stable = stable_duration > 0.6

        # 检测是否在大招保护期内
        protect_duration = current_time - self.last_detach_time
        is_in_protect = protect_duration < self.ULT_PROTECT_DURATION

        # --- 坐标转换（头顶→脚下）---
        self_feet_pos = (
            self._convert_to_feet_pos(self_pos) if self_pos is not None else None
        )

        # --- 1. 大招逻辑 (R) - 最高优先级 ---
        # 初始化大招释放标志（确保变量始终有定义）
        can_ult = False

        # 强制保护：附身状态时绝对禁止释放大招（避免下车）
        # 双重检查：is_attached 或 raw_self_health is None 都表示附身
        # 注意：使用 raw_self_health 而不是过滤后的 self_health，因为过滤会保留历史值

        if is_attached or raw_self_health is None:
            self._log(f"[R] 强制保护: 附身状态，禁止释放大招避免下车")
        elif not is_deer:
            closest_team = None
            closest_team_dx = None
            closest_team_dy = None
            closest_team_raw_dy = None

            # 目标锁定：优先保持已锁定的队友
            if (
                self.locked_target is not None
                and self.lock_frame_count < self.TARGET_LOCK_FRAMES
            ):
                # 查找锁定的目标是否仍在视野中
                for t in team_health:
                    if isinstance(t, dict) and "pos" in t:
                        if self._is_same_target(t["pos"], self.locked_target):
                            closest_team = t
                            break
                self.lock_frame_count += 1

            # 如果没有锁定目标或锁定已过期，重新选择最近队友
            if closest_team is None and self_feet_pos and team_health:
                min_team_dist = float("inf")
                for t in team_health:
                    if isinstance(t, dict) and "pos" in t:
                        tpos = t["pos"]
                        team_feet_pos = self._convert_to_feet_pos(
                            tpos, use_generic_offset=True
                        )
                        if team_feet_pos is None:
                            continue
                        td = sqrt(
                            (self_feet_pos[0] - team_feet_pos[0]) ** 2
                            + (self_feet_pos[1] - team_feet_pos[1]) ** 2
                        )
                        if td < min_team_dist:
                            min_team_dist = td
                            closest_team = t
                            closest_team_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                            closest_team_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                            closest_team_raw_dy = team_feet_pos[1] - self_feet_pos[1]

                # 锁定新目标（小地图来源的目标不锁定）
                if closest_team is not None and not closest_team.get("_from_minimap"):
                    self.locked_target = closest_team["pos"]
                    self.lock_frame_count = 0

            # === 小地图补充：模态2无队友时，用小地图坐标判断R技能范围 ===
            if closest_team is None and minimap_data:
                m1_self = minimap_data.get("g_center")
                m1_teammates = minimap_data.get("b_centers", [])

                if m1_self and m1_teammates:
                    m1_min_dist = float("inf")
                    m1_best_dx = None
                    m1_best_dy = None
                    m1_best_raw_dy = None

                    for t in m1_teammates:
                        dx_screen, dy_screen = self._minimap_distance_to_screen(
                            m1_self, t
                        )
                        d = sqrt(dx_screen**2 + dy_screen**2)
                        if d < m1_min_dist:
                            m1_min_dist = d
                            m1_best_dx = abs(dx_screen)
                            m1_best_dy = abs(dy_screen)
                            m1_best_raw_dy = dy_screen

                    if m1_best_dx is not None:
                        # 用小地图转换的距离填充椭圆判断变量
                        closest_team_dx = m1_best_dx
                        closest_team_dy = m1_best_dy
                        closest_team_raw_dy = m1_best_raw_dy
                        # 创建一个虚拟的closest_team对象（标记来源为小地图）
                        closest_team = {
                            "pos": None,
                            "health": None,
                            "_from_minimap": True,
                        }
                        self._log(
                            f"[R-小地图] 使用小地图坐标判断R技能 | 距离={m1_min_dist:.0f}px"
                        )

            # 如果找到目标，计算范围
            if (
                closest_team is not None
                and closest_team_dx is None
                and self_feet_pos is not None
            ):
                # 重新计算锁定目标的距离
                tpos = closest_team["pos"]
                team_feet_pos = self._convert_to_feet_pos(tpos, use_generic_offset=True)
                if team_feet_pos is not None:
                    closest_team_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                    closest_team_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                    closest_team_raw_dy = team_feet_pos[1] - self_feet_pos[1]

            # 椭圆范围判断
            r_in_range = False
            r_ellipse_val = float("inf")
            if (
                closest_team_dx is not None
                and closest_team_dy is not None
                and closest_team_raw_dy is not None
            ):
                # 根据队友方向选择Y轴范围
                if closest_team_raw_dy < 0:  # 队友在上方
                    r_ry = R_RANGE_Y_UP
                else:  # 敌人在下方
                    r_ry = R_RANGE_Y_DOWN
                r_ellipse_val = (closest_team_dx / R_RANGE_X) ** 2 + (
                    closest_team_dy / r_ry
                ) ** 2
                r_in_range = r_ellipse_val < 1

            r_ready = current_time - self.last_ult_time > 5.0

            # 大招释放条件：范围满足 + 冷却完成
            can_ult = r_in_range and r_ready

            # 大招释放（未附身状态）
            if can_ult and not is_in_protect:
                self._log(
                    f"[R] 释放 | 范围:椭圆{r_ellipse_val:.2f} | dx={closest_team_dx}, dy={closest_team_dy} | 目标锁定:{self.lock_frame_count}帧"
                )
                self.tap_skill(KEY_CAST_ULT, "大招(附身)")
                self.last_ult_time = current_time
                self.locked_target = None  # 附身后清除锁定
                self.lock_frame_count = 0
            elif can_ult and is_in_protect:
                # 保护期内但条件满足，记录日志
                self._log(
                    f"[R] 保护期内无法附身 | 剩余{self.ULT_PROTECT_DURATION - protect_duration:.1f}秒"
                )

        # --- 2. Q/E技能 ---
        # 策略检查：aggressive 始终允许，conservative 有敌人时允许（被动反击）

        # 诊断日志低频输出控制
        should_log_diag = (int(current_time) % 5 == 0) and (
            current_time - getattr(self, "_last_diag_log_time", 0) > 1
        )
        if should_log_diag:
            self._last_diag_log_time = current_time

        if has_enemy and self_feet_pos and allow_offensive:
            # 计算最近敌人（使用脚下坐标）
            closest_dx = None
            closest_dy = None
            raw_dy = None
            min_dist = float("inf")

            for e in enemy_health:
                if isinstance(e, dict) and "pos" in e:
                    pos = e["pos"]
                    enemy_feet_pos = self._convert_to_feet_pos(
                        pos, use_generic_offset=True
                    )
                    if enemy_feet_pos is None:
                        continue
                    d = sqrt(
                        (self_feet_pos[0] - enemy_feet_pos[0]) ** 2
                        + (self_feet_pos[1] - enemy_feet_pos[1]) ** 2
                    )
                    if d < min_dist:
                        min_dist = d
                        closest_dx = abs(self_feet_pos[0] - enemy_feet_pos[0])
                        closest_dy = abs(self_feet_pos[1] - enemy_feet_pos[1])
                        raw_dy = enemy_feet_pos[1] - self_feet_pos[1]

            # Q技能
            if is_deer:
                q_in_range = True
            elif (
                closest_dx is not None and closest_dy is not None and raw_dy is not None
            ):
                # 根据方向和附身状态选择范围（清晰的if-elif结构）
                if raw_dy < 0:  # 敌人在上方
                    if is_attached:
                        q_range_y = Q_RANGE_Y_UP_ATTACHED
                    else:
                        q_range_y = Q_RANGE_Y_UP_NORMAL
                else:  # 敌人在下方
                    if is_attached:
                        q_range_y = Q_RANGE_Y_DOWN_ATTACHED
                    else:
                        q_range_y = Q_RANGE_Y_DOWN_NORMAL

                q_range_x = Q_RANGE_X_ATTACHED if is_attached else Q_RANGE_X_NORMAL
                ellipse_val = (closest_dx / q_range_x) ** 2 + (
                    closest_dy / q_range_y
                ) ** 2
                q_in_range = ellipse_val < 1
            else:
                q_in_range = False

            q_ready = current_time - self.last_q_time > 4.0

            # 调试日志：Q技能条件（仅在满足或低频时输出）
            if (q_in_range and q_ready) or should_log_diag:
                self._log(f"[技能诊断-Q] 范围={q_in_range}, 冷却={q_ready}")

            if q_in_range and q_ready:
                self.tap_skill(KEY_CAST_1, "一技能")
                self.last_q_time = current_time
                if is_deer:
                    # 鹿灵状态Q技能：提前结束鹿灵并刷新所有技能冷却
                    self.last_e_time = 0
                    self.last_q_time = 0
                    self.last_ult_time = 0
                    self._log("[Q] 鹿灵结束 → 所有技能冷却已刷新（Q/E/R）")

            # E技能
            if (
                not is_deer
                and closest_dx is not None
                and closest_dy is not None
                and raw_dy is not None
            ):
                # 根据方向和附身状态选择范围（清晰的if-elif结构）
                if is_attached:
                    e_rx = E_RANGE_X_ATTACHED
                    if raw_dy < 0:  # 敌人在上方
                        e_ry = E_RANGE_Y_UP_ATTACHED
                    else:  # 敌人在下方
                        e_ry = E_RANGE_Y_DOWN_ATTACHED
                else:
                    e_rx = E_RANGE_X
                    if raw_dy < 0:  # 敌人在上方
                        e_ry = E_RANGE_Y_UP
                    else:  # 敌人在下方
                        e_ry = E_RANGE_Y_DOWN
                e_ellipse_val = (closest_dx / e_rx) ** 2 + (closest_dy / e_ry) ** 2
                e_in_range = e_ellipse_val < 1
            else:
                e_in_range = False

            e_ready = current_time - self.last_e_time > 5.0

            # 调试日志：E技能条件（仅在满足或低频时输出）
            if (e_in_range and e_ready) or should_log_diag:
                self._log(f"[技能诊断-E] 范围={e_in_range}, 冷却={e_ready}")

            if e_in_range and e_ready:
                self.tap_skill(KEY_CAST_2, "二技能")
                self.last_e_time = current_time

            # 调试日志：普攻条件（低频）
            if should_log_diag:
                self._log(
                    f"[技能诊断-普攻] 未附身={not is_attached}, 未移动={not self.is_moving}"
                )

            # 普攻（未附身时，添加范围判断）
            if (
                not is_attached
                and closest_dx is not None
                and closest_dy is not None
                and raw_dy is not None
            ):
                # 使用E技能数值（临时，后续可独立配置）
                if raw_dy < 0:  # 敌人在上方
                    attack_ry = 333
                else:  # 敌人在下方
                    attack_ry = 522
                attack_ellipse_val = (closest_dx / 630) ** 2 + (
                    closest_dy / attack_ry
                ) ** 2
                attack_in_range = attack_ellipse_val < 1

                if attack_in_range:
                    self.basic_attack()

        elif not has_enemy and allow_offensive and minimap_data:
            # === 小地图补充：模态2无敌人，用小地图坐标判断 ===
            m1_self = minimap_data.get("g_center")
            m1_enemies = minimap_data.get("r_centers", [])

            if m1_self and m1_enemies:
                # 找最近的小地图敌人
                m1_closest_dx = None
                m1_closest_dy = None
                m1_raw_dy = None
                m1_min_dist = float("inf")

                for e in m1_enemies:
                    dx_screen, dy_screen = self._minimap_distance_to_screen(m1_self, e)
                    d = sqrt(dx_screen**2 + dy_screen**2)
                    if d < m1_min_dist:
                        m1_min_dist = d
                        m1_closest_dx = abs(dx_screen)
                        m1_closest_dy = abs(dy_screen)
                        m1_raw_dy = dy_screen

                if m1_closest_dx is not None:
                    # Q技能（小地图补充）
                    if is_deer:
                        q_in_range = True
                    elif m1_closest_dy is not None and m1_raw_dy is not None:
                        if m1_raw_dy < 0:
                            if is_attached:
                                q_range_y = Q_RANGE_Y_UP_ATTACHED
                            else:
                                q_range_y = Q_RANGE_Y_UP_NORMAL
                        else:
                            if is_attached:
                                q_range_y = Q_RANGE_Y_DOWN_ATTACHED
                            else:
                                q_range_y = Q_RANGE_Y_DOWN_NORMAL

                        q_range_x = (
                            Q_RANGE_X_ATTACHED if is_attached else Q_RANGE_X_NORMAL
                        )
                        ellipse_val = (m1_closest_dx / q_range_x) ** 2 + (
                            m1_closest_dy / q_range_y
                        ) ** 2
                        q_in_range = ellipse_val < 1
                    else:
                        q_in_range = False

                    q_ready = current_time - self.last_q_time > 4.0

                    if q_in_range and q_ready:
                        self._log(
                            f"[Q-小地图] 释放（小地图补充） | 距离={m1_min_dist:.0f}px"
                        )
                        self.tap_skill(KEY_CAST_1, "一技能")
                        self.last_q_time = current_time
                        if is_deer:
                            self.last_e_time = 0
                            self.last_q_time = 0
                            self.last_ult_time = 0
                            self._log("[Q] 鹿灵结束 → 所有技能冷却已刷新（Q/E/R）")

                    # E技能（小地图补充）
                    if (
                        not is_deer
                        and m1_closest_dy is not None
                        and m1_raw_dy is not None
                    ):
                        if is_attached:
                            e_rx = E_RANGE_X_ATTACHED
                            if m1_raw_dy < 0:
                                e_ry = E_RANGE_Y_UP_ATTACHED
                            else:
                                e_ry = E_RANGE_Y_DOWN_ATTACHED
                        else:
                            e_rx = E_RANGE_X
                            if m1_raw_dy < 0:
                                e_ry = E_RANGE_Y_UP
                            else:
                                e_ry = E_RANGE_Y_DOWN
                        e_ellipse_val = (m1_closest_dx / e_rx) ** 2 + (
                            m1_closest_dy / e_ry
                        ) ** 2
                        e_in_range = e_ellipse_val < 1
                    else:
                        e_in_range = False

                    e_ready = current_time - self.last_e_time > 5.0

                    if e_in_range and e_ready:
                        self._log(
                            f"[E-小地图] 释放（小地图补充） | 距离={m1_min_dist:.0f}px"
                        )
                        self.tap_skill(KEY_CAST_2, "二技能")
                        self.last_e_time = current_time

        # --- 3. 召唤师技能 F键（汇流为兵 / 治疗术，由 ACTIVE_SUMMONER_F 开关决定）---
        # 两者都是防御性技能，在 aggressive/defensive/conservative 下均可使用
        if not allow_defensive:
            return  # 仅 disabled 时到不了这里，但做防御性检查

        # 辅助函数：获取血量值，兼容字典和数值格式
        def get_health_value(h):
            return h["health"] if isinstance(h, dict) else h

        team_health_values = [get_health_value(h) for h in team_health]

        # 统计范围内低血量队友（两种召唤师技能共用的判断逻辑）
        low_hp_count = 0
        in_range_team_health = []

        if self_health is not None and self_health < 60:
            low_hp_count += 1  # 自身始终算受益（以自己为中心释放）

        # 检查队友是否在范围内
        if self_feet_pos and team_health:
            for idx, t in enumerate(team_health):
                if isinstance(t, dict) and "pos" in t and "health" in t:
                    tpos = t["pos"]
                    team_feet_pos = self._convert_to_feet_pos(
                        tpos, use_generic_offset=True
                    )
                    if team_feet_pos is None:
                        continue
                    t_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                    t_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                    t_raw_dy = team_feet_pos[1] - self_feet_pos[1]

                    # 使用治疗术/汇流为兵的范围配置（两者范围类似）
                    if t_raw_dy < 0:  # 队友在上方
                        f_ry = HEAL_RANGE_Y_UP
                    else:  # 队友在下方
                        f_ry = HEAL_RANGE_Y_DOWN
                    f_ellipse_val = (t_dx / HEAL_RANGE_X) ** 2 + (t_dy / f_ry) ** 2

                    in_range = f_ellipse_val < 1
                    h = get_health_value(t)

                    if in_range:
                        in_range_team_health.append(h)
                        if h < 50:
                            low_hp_count += 1

        # ===== 根据 ACTIVE_SUMMONER_F 开关选择释放哪个召唤师技能 =====
        if ACTIVE_SUMMONER_F == "confluence":
            # --- 汇流为兵-辅助 ---
            # 效果：召唤元流古琴治疗友方/伤害敌方，额外减少自身所有技能当前50%冷却
            need_confluence = False
            # 汇流为兵CD=100秒，用90秒做冷却检查（留10秒余量避免浪费按键）
            confluence_cooldown_ok = current_time - self.last_confluence_time > 90

            if is_stable and confluence_cooldown_ok:
                if low_hp_count >= 2:
                    need_confluence = True
                elif low_hp_count == 1 and self_health is not None and self_health < 30:
                    need_confluence = True

                if need_confluence:
                    self._log(
                        f"[F] 汇流为兵-辅助 | 受益人数:{low_hp_count} (范围内队友:{len(in_range_team_health)})"
                    )
                    self.tap_skill(KEY_HEAL, "汇流为兵-辅助")
                    self.last_confluence_time = current_time

                    # ===== 汇流为兵额外效果：减少自身所有技能当前50%冷却 =====
                    # 计算每个技能的剩余CD，减半后更新 last_xxx_time
                    skill_cds = {
                        "Q": (self.last_q_time, 4.0),  # Q技能，实际检查CD=4秒
                        "E": (self.last_e_time, 5.0),  # E技能，实际检查CD=5秒
                        "R": (self.last_ult_time, 5.0),  # 大招，实际检查CD=5秒
                    }
                    for skill_name, (last_time, cd) in skill_cds.items():
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
                if low_hp_count >= 2:
                    need_heal = True
                elif low_hp_count == 1 and self_health is not None and self_health < 30:
                    need_heal = True

                if need_heal:
                    self._log(
                        f"[F] 治疗术 | 受益人数:{low_hp_count} (范围内队友:{len(in_range_team_health)})"
                    )
                    self.tap_skill(KEY_HEAL, "治疗术")
                    self.last_heal_time = current_time

        # --- 4. 救赎 (T) ---
        # 救赎：范围内有低血量队友时使用
        t_ready = current_time - self.last_skill4_time > 5

        # 重新计算队友距离和血量（避免依赖大招逻辑的变量）
        t_should_use = False
        t_low_hp_teammate = None

        if is_stable and t_ready and self_feet_pos and team_health:
            for idx, t in enumerate(team_health):
                if isinstance(t, dict) and "pos" in t and "health" in t:
                    tpos = t["pos"]
                    thp = get_health_value(t)
                    team_feet_pos = self._convert_to_feet_pos(
                        tpos, use_generic_offset=True
                    )
                    if team_feet_pos is None:
                        continue
                    t_dx = abs(self_feet_pos[0] - team_feet_pos[0])
                    t_dy = abs(self_feet_pos[1] - team_feet_pos[1])
                    t_raw_dy = team_feet_pos[1] - self_feet_pos[1]

                    # 使用救赎配置的范围
                    if t_raw_dy < 0:  # 队友在上方
                        t_ry = REDEMPTION_RANGE_Y_UP
                    else:  # 队友在下方
                        t_ry = REDEMPTION_RANGE_Y_DOWN
                    t_ellipse_val = (t_dx / REDEMPTION_RANGE_X) ** 2 + (
                        t_dy / t_ry
                    ) ** 2

                    in_range = t_ellipse_val < 1
                    low_hp = thp < 50  # 血量低于50%认为是低血量

                    # 救赎触发条件：队友在范围内 AND 血量低
                    if in_range and low_hp:
                        t_should_use = True
                        t_low_hp_teammate = idx
                        break

        if t_should_use:
            self._log(f"[T] 救赎 | 保护低血量队友{t_low_hp_teammate}")
            self.tap_skill(KEY_SKILL_4, "救赎")
            self.last_skill4_time = current_time

        # --- 5. 恢复 (C) ---
        no_enemy_nearby = len(enemy_health) == 0
        if is_stable and not is_attached and self_health is not None:
            if self_health < 60 and no_enemy_nearby:
                if current_time - self.last_recover_time > 5:
                    self._log(f"[C] 恢复 | 自身:{self_health}%")
                    self.tap_skill(KEY_RECOVER, "恢复")
                    self.last_recover_time = current_time


# ===== 模块入口函数 =====
    def check_and_use_skills(self):
        """Check and execute the active Yao decision-brain skill policy."""
        return self._check_and_use_skills_with_decision_brain()


def run(queue):
    """
    运行瑶技能逻辑的入口函数

    参数说明：
        queue: Queue对象，用于接收血量信息的队列

    功能说明：
        创建瑶技能逻辑实例并启动主循环
        供外部模块调用以启动技能逻辑线程
    """
    yao = YaoSkillLogic()
    yao.run(queue)


# 当直接运行此文件时执行的测试代码
if __name__ == "__main__":
    from queue import Queue

    # 输出测试开始分隔线
    logger.info("=" * 60)
    logger.info("瑶技能逻辑 V2 测试")
    logger.info("=" * 60)

    # 创建技能逻辑实例
    skill_logic = YaoSkillLogic()
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
