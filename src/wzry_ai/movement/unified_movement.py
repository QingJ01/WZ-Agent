"""
统一移动控制器 - 合并模态1和模态2的移动逻辑
简化方案：谁有数据就用谁，模态2优先级更高
"""

# 导入time模块用于时间相关操作
import time

# 从math导入sqrt函数用于计算距离
from math import sqrt

# 本地模块导入
from wzry_ai.config import (
    MINIMAP_SCALE_FACTOR,
    MOVE_DEADZONE,
    MOVE_INTERVAL,
)  # 从配置导入移动相关参数
from wzry_ai.config import (
    KEY_MOVE_UP,
    KEY_MOVE_LEFT,
    KEY_MOVE_DOWN,
    KEY_MOVE_RIGHT,
)  # 从配置导入方向按键
from wzry_ai.config import (
    CELL_SIZE,
    PATH_REPLAN_DISTANCE,
    CORRIDOR_TOLERANCE,
    LOOKAHEAD_DISTANCE,
)  # 寻路配置
from wzry_ai.config.heroes.mapping import get_hero_chinese  # 导入英雄中文名获取函数
from wzry_ai.utils.keyboard_controller import (
    press,
    release,
    tap,
)  # 导入键盘按键控制函数
from wzry_ai.utils.logging_utils import get_logger  # 导入日志获取函数

import wzry_ai.detection.model1_astar_follow as model1_astar_follow  # 导入模态1跟随模块

# 获取当前模块的日志记录器
logger = get_logger(__name__)

# 最小跟随距离（像素）- 防止遮挡队友血条
MIN_FOLLOW_DISTANCE = 20  # 保持至少20像素距离，跟紧队友但避免完全重叠


# ===== 卡地形检测器 =====
# 基于小地图坐标的卡地形检测器类
#
# 【设计说明】
# 这个类合并了两套检测系统的优点：
# 1. 原 StuckDetector：基于坐标范围判断 + 回城保底机制
# 2. 原 WallAvoidanceNavigator：死路记忆 + 成功路径记忆 + 多角度尝试
# 合并后统一使用这一个类，避免两套检测逻辑冲突
#
class StuckDetector:
    """
    基于小地图坐标的卡地形检测器

    功能说明：
    - 通过监测小地图上自身坐标(g_center)的变化来判断是否卡在地形上
    - 卡住后自动尝试多个方向绕路（45°, -45°, 90°, -90°, 135°, -135°, 180°）
    - 记录"死路"位置和"成功脱困"方向，避免重复走死路
    - 卡住次数过多时触发回城保底机制

    使用场景：
    - 由 UnifiedMovement 持有并在 execute_move() 中调用
    - 在 run_fusion_logic_v2() 中通过 movement.stuck_detector 访问
    """

    def __init__(self):
        # ===== 坐标历史 =====
        # 小地图坐标历史列表，存储元组 (x, y, timestamp)
        self.minimap_history = []
        self.history_size = 20  # 历史记录最大数量，约0.6-0.7秒的数据

        # ===== 卡住判定参数 =====
        # 这些阈值经过实测调优：太灵敏会误判（英雄在原地释放技能时也不动），太迟钝会卡很久
        self.stuck_threshold = 10  # X或Y轴变化小于此值认为可能卡住（小地图像素）
        self.time_threshold = (
            0.5  # 最少需要0.5秒的数据才进行判断（防止刚开始移动就误判）
        )

        # 连续判定次数（避免误判）—— 单次判定可能是技能释放中的短暂停留
        self.stuck_confirm_count = 0  # 当前连续判定卡住的次数
        self.stuck_confirm_required = 8  # 连续8次判定卡住才真正确认（约0.3秒）

        # ===== 绕路状态 =====
        self.is_avoiding = False  # 是否正在绕路中
        self.avoid_start_time: float | None = None  # 绕路开始时间戳
        self.avoid_direction: float | None = None  # 当前绕路方向角度（弧度）
        self.avoid_attempts = 0  # 当前连续绕路尝试次数（每次方向不同）
        self.max_avoid_attempts = 5  # 最大尝试次数，超过则放弃绕路（防止无限循环）

        # ===== 路径记忆系统 =====
        # 【核心改进】记录走过的死路和成功脱困的方向，下次遇到同样的位置可以直接用成功方向
        # dead_zones: 用网格坐标记录"走不通"的位置，避免重复尝试
        # success_exits: 记录某个网格位置成功脱困时使用的方向角度
        self.dead_zones = set()  # 死路位置集合，格式：{(grid_x, grid_y), ...}
        self.success_exits = {}  # 成功脱困路径，格式：{(grid_x, grid_y): 角度弧度}
        self.grid_size = 60  # 网格大小（小地图像素），60像素一个格子

        # ===== 统计信息 =====
        self.stuck_count = 0  # 累计卡住次数（跨绕路周期累加）
        self.avoid_success_count = 0  # 成功脱困次数

        # ===== 回城保底机制 =====
        # 当卡住次数达到阈值且周围没有敌人时，触发回城（回到泉水重新出发）
        self.is_recalling = False  # 是否正在回城
        self.recall_start_time: float | None = None  # 回城开始时间
        self.RECALL_DURATION = 8.0  # 回城需要的时间（秒），王者荣耀回城约8秒
        self.STUCK_RECALL_THRESHOLD = 30  # 触发回城的卡住次数阈值
        self._avoid_start_pos: tuple[float, float] | None = None

    def update(self, g_center):
        """
        更新小地图坐标历史

        参数说明：
            g_center: 自身在小地图上的坐标 (x, y)，由模态1检测器提供
                      如果为None表示当前帧未检测到自身，跳过

        功能说明：
            每次收到新的坐标就存入历史列表，用于后续的卡住判断
            历史列表保持固定长度，超出时移除最旧的记录
        """
        if g_center is None:
            return  # 如果位置为空，直接返回

        current_time = time.time()  # 获取当前时间戳
        self.minimap_history.append(
            (g_center[0], g_center[1], current_time)
        )  # 添加新记录

        # 保持历史记录在限制大小内，超出则移除最旧的记录
        if len(self.minimap_history) > self.history_size:
            self.minimap_history.pop(0)

    def _to_grid(self, pos):
        """
        将像素坐标转换为网格坐标

        参数说明：
            pos: 像素坐标 (x, y)

        返回值：
            元组 (grid_x, grid_y)，用于死路记忆和成功路径记忆

        原理说明：
            把小地图划分成 grid_size x grid_size 像素的网格
            同一个网格内的位置视为"同一个地方"
            这样可以用网格坐标作为字典的key来记忆路径
        """
        return (int(pos[0] / self.grid_size), int(pos[1] / self.grid_size))

    def is_stuck(self, current_time=None):
        """
        判断是否卡住

        参数说明：
            current_time: 可选，当前时间戳（不传则自动获取）

        返回值：
            True = 确认卡住（连续多次判定都卡住），False = 未卡住

        判断逻辑：
            1. 提取历史坐标中所有X值和Y值
            2. 计算X轴变化范围(max-min)和Y轴变化范围(max-min)
            3. 如果两个轴的变化都小于阈值 → 认为当前帧可能卡住
            4. 连续多帧都判定为卡住 → 确认卡住
        """
        # 历史记录不足15条时无法可靠判断，直接返回未卡住
        history_len = len(self.minimap_history)
        if history_len < 15:
            return False

        # 检查时间跨度是否足够（防止刚开始移动就误判）
        time_span = self.minimap_history[-1][2] - self.minimap_history[0][2]
        if time_span < self.time_threshold:
            return False

        # 计算X轴和Y轴的变化范围
        xs = [p[0] for p in self.minimap_history]  # 提取所有X坐标
        ys = [p[1] for p in self.minimap_history]  # 提取所有Y坐标

        x_range = max(xs) - min(xs)  # X轴变化范围
        y_range = max(ys) - min(ys)  # Y轴变化范围

        # 两个轴的变化都很小 = 当前帧判定为卡住
        is_currently_stuck = (
            x_range < self.stuck_threshold and y_range < self.stuck_threshold
        )

        # 连续判定机制 —— 单次卡住可能是误判（比如正在释放技能），需要连续多次才确认
        if is_currently_stuck:
            self.stuck_confirm_count += 1  # 增加确认计数
        else:
            self.stuck_confirm_count = 0  # 一旦移动了就重置计数
            # 如果之前正在绕路且现在脱离了卡住，说明绕路成功
            if self.is_avoiding:
                self._end_avoidance_success()

        return self.stuck_confirm_count >= self.stuck_confirm_required

    def reset(self):
        """
        重置卡地形检测器状态

        使用场景：
            - 瑶附身队友后不需要自己移动，重置检测器避免误判
            - 有队友跟随时重置，因为跟随移动不需要卡墙检测
        """
        self.minimap_history.clear()  # 清空历史记录
        self.stuck_confirm_count = 0  # 重置确认计数
        self.is_avoiding = False  # 重置绕路状态
        self.avoid_direction = None  # 清空绕路方向
        self.avoid_attempts = 0  # 重置绕路尝试次数

    def start_avoidance(self, current_direction):
        """
        开始绕路模式 —— 检测到卡住后调用此方法选择一个绕路方向

        参数说明：
            current_direction: 当前移动方向（弧度），即从自身指向目标的角度
                              用于计算偏移方向（比如在原方向基础上偏转45°、90°等）

        返回值：
            float: 绕路方向角度（弧度），调用方应使用此角度移动

        【核心改进：多角度尝试策略】
        旧版本只交替尝试 ±90°（左右两个方向），很容易在复杂地形上失败
        新版本按优先级尝试 7 个方向：45°, -45°, 90°, -90°, 135°, -135°, 180°
        并且会检查目标方向是否在"死路"记忆中，跳过已知走不通的方向
        """
        import math

        self.is_avoiding = True  # 标记正在绕路
        self.avoid_start_time = time.time()  # 记录开始时间
        self.avoid_attempts += 1  # 增加当前绕路周期的尝试次数
        self.stuck_count += 1  # 增加总卡住次数统计

        # 记录绕路开始时的位置，用于后续判断角色是否真正卡住
        if self.minimap_history:
            latest = self.minimap_history[-1]
            self._avoid_start_pos = (latest[0], latest[1])

        # 获取当前位置的网格坐标（用于死路记忆查询）
        # 从历史记录中取最新的坐标
        current_pos = None
        if self.minimap_history:
            latest = self.minimap_history[-1]
            current_pos = (latest[0], latest[1])

        # 记录当前位置为"死路"（走到这里卡住了，下次避开）
        if current_pos:
            grid_pos = self._to_grid(current_pos)
            self.dead_zones.add(grid_pos)

            # 优先使用历史上在这个位置成功脱困的方向（如果有的话）
            if grid_pos in self.success_exits:
                success_direction = self.success_exits[grid_pos]
                self.avoid_direction = success_direction
                logger.info(
                    f"检测到卡住 #{self.stuck_count}，使用历史成功方向: {math.degrees(success_direction):.1f}°"
                )
                return self.avoid_direction

        # ===== 多角度尝试策略 =====
        # 按优先级尝试7个偏移角度：先尝试小角度偏移（更接近目标），再尝试大角度
        # 45°和-45°：轻微偏移，适合小障碍物
        # 90°和-90°：垂直偏移，适合墙壁
        # 135°和-135°：大幅偏移，适合凹形地形
        # 180°：完全反方向，最后手段
        test_offsets_deg = [45, -45, 90, -90, 135, -135, 180]

        if current_direction is not None:
            for offset_deg in test_offsets_deg:
                test_angle = current_direction + math.radians(offset_deg)

                # 检查这个方向是否会走进已知的死路
                if current_pos:
                    # 预测沿此方向前进100像素后的位置
                    test_x = current_pos[0] + math.cos(test_angle) * 100
                    test_y = current_pos[1] + math.sin(test_angle) * 100
                    test_grid = self._to_grid((test_x, test_y))

                    # 如果预测位置在死路中，跳过这个方向
                    if test_grid in self.dead_zones:
                        continue

                # 这个方向可以尝试，使用它
                # 将角度标准化到 [-pi, pi] 范围（防止角度溢出）
                self.avoid_direction = math.atan2(
                    math.sin(test_angle), math.cos(test_angle)
                )
                logger.info(
                    f"检测到卡住 #{self.stuck_count}，尝试偏移{offset_deg}°绕路，角度={math.degrees(self.avoid_direction):.1f}°"
                )
                return self.avoid_direction

            # 所有方向都在死路中，只能硬闯原方向
            self.avoid_direction = math.atan2(
                math.sin(current_direction), math.cos(current_direction)
            )
            logger.warning(
                f"检测到卡住 #{self.stuck_count}，所有方向都尝试过，沿原方向硬闯"
            )
        else:
            # 没有方向信息时（极端情况），交替尝试上下
            if self.stuck_count % 2 == 1:
                self.avoid_direction = -math.pi / 2  # 向上（小地图坐标系中Y轴向下为正）
            else:
                self.avoid_direction = math.pi / 2  # 向下
            logger.info(
                f"检测到卡住 #{self.stuck_count}，无方向信息，向{'上' if self.avoid_direction < 0 else '下'}绕路"
            )

        return self.avoid_direction

    def update_avoidance(self):
        """
        更新绕路状态，在绕路过程中每帧调用

        返回值：
            float: 当前应该使用的绕路方向角度（弧度），如果绕路结束返回None

        功能说明：
            1. 检查是否已经脱离卡住（最近几帧的移动距离大于阈值）
            2. 如果绕路超时（1.5秒），尝试切换到新方向
            3. 如果尝试次数超过上限，放弃绕路
        """
        if not self.is_avoiding:
            return None  # 不在绕路状态，返回None
        if self.avoid_start_time is None:
            return None

        avoid_duration = time.time() - self.avoid_start_time  # 计算已绕路时长

        # 检查是否已经脱离卡住（绕路成功的早期检测）
        # 看最近5帧的总移动距离，如果移动距离够大说明已经脱离
        if len(self.minimap_history) >= 5:
            recent = self.minimap_history[-5:]  # 取最近5帧
            recent_move = 0
            for i in range(1, len(recent)):
                dx = recent[i][0] - recent[i - 1][0]
                dy = recent[i][1] - recent[i - 1][1]
                recent_move += sqrt(dx**2 + dy**2)

            # 移动距离大于卡住阈值的2倍，且绕路已超过0.3秒（排除刚开始的误判）
            if recent_move > self.stuck_threshold * 2 and avoid_duration > 0.3:
                self._end_avoidance_success()
                return None  # 绕路成功，返回None让调用方恢复正常移动

        # 绕路超时（1.5秒还没脱离），尝试换一个方向
        if avoid_duration > 1.5:
            if self.avoid_attempts < self.max_avoid_attempts:
                # 检查角色位置是否有明显变化
                current_pos = None
                if self.minimap_history:
                    latest = self.minimap_history[-1]
                    current_pos = (latest[0], latest[1])

                # 判断位置是否有明显变化（距离 > 20像素）
                has_moved = False
                move_distance = 0.0
                if current_pos and self._avoid_start_pos is not None:
                    dx = current_pos[0] - self._avoid_start_pos[0]
                    dy = current_pos[1] - self._avoid_start_pos[1]
                    move_distance = sqrt(dx**2 + dy**2)
                    has_moved = move_distance > 20  # 20像素阈值

                if has_moved:
                    # 角色有移动，只是绕路方向不对，不递增stuck_count，只重置计时器和尝试次数
                    logger.debug(
                        f"绕路超时但角色已移动({move_distance:.1f}px)，重置绕路计时器 ({self.avoid_attempts}/{self.max_avoid_attempts})"
                    )
                    self.avoid_start_time = time.time()  # 重置绕路开始时间
                    self._avoid_start_pos = current_pos  # 更新绕路起始位置
                    # 尝试新方向但不递增stuck_count
                    self.avoid_attempts += 1
                    import math

                    # 获取当前方向作为基准，重新选择绕路方向（不调用start_avoidance以避免递增stuck_count）
                    self.is_avoiding = True
                    # 多角度尝试策略
                    test_offsets_deg = [45, -45, 90, -90, 135, -135, 180]
                    current_avoid_direction = self.avoid_direction
                    if current_avoid_direction is None:
                        return self.start_avoidance(None)
                    for offset_deg in test_offsets_deg:
                        test_angle = current_avoid_direction + math.radians(offset_deg)
                        # 标准化角度到 [-pi, pi]
                        test_angle = math.atan2(
                            math.sin(test_angle), math.cos(test_angle)
                        )
                        # 检查这个方向是否与当前方向明显不同
                        angle_diff = abs(test_angle - current_avoid_direction)
                        if angle_diff > math.radians(30):  # 至少偏离30度
                            self.avoid_direction = test_angle
                            logger.info(
                                f"尝试偏移{offset_deg}°新绕路方向，角度={math.degrees(self.avoid_direction):.1f}°"
                            )
                            break
                    return self.avoid_direction
                else:
                    # 角色确实卡住，递增stuck_count并重新开始绕路
                    logger.debug(
                        f"绕路方向无效且角色未移动，尝试新方向 ({self.avoid_attempts}/{self.max_avoid_attempts})"
                    )
                    # 获取当前方向作为基准，重新选择绕路方向
                    return self.start_avoidance(self.avoid_direction)
            else:
                # 尝试次数超过上限，放弃绕路
                logger.warning(
                    f"绕路尝试次数超过上限({self.max_avoid_attempts})，放弃绕路"
                )
                self.is_avoiding = False
                self.avoid_direction = None
                self.avoid_attempts = 0
                return None

        return self.avoid_direction

    def _end_avoidance_success(self):
        """
        绕路成功处理 —— 记录成功方向到路径记忆中

        功能说明：
            1. 将当前位置的成功脱困方向记录到 success_exits 字典中
            2. 下次在同一网格位置卡住时，可以直接使用这个方向（不用再逐个尝试）
            3. 重置绕路状态，恢复正常移动
        """
        # 记录成功方向到路径记忆
        if self.minimap_history and self.avoid_direction is not None:
            latest = self.minimap_history[-1]
            grid_pos = self._to_grid((latest[0], latest[1]))
            self.success_exits[grid_pos] = (
                self.avoid_direction
            )  # 记住这个位置的成功方向

        self.avoid_success_count += 1  # 增加成功计数
        self.is_avoiding = False  # 结束绕路状态
        self.avoid_direction = None  # 清空绕路方向
        self.stuck_confirm_count = 0  # 重置确认计数
        self.avoid_attempts = 0  # 重置尝试次数
        logger.info(f"绕路成功 #{self.avoid_success_count}，恢复正常跟随")

    def start_recall(self):
        """
        开始回城 —— 回城保底机制

        使用场景：
            当卡住次数达到 STUCK_RECALL_THRESHOLD (30次) 且周围没有敌人时
            说明当前位置可能在复杂地形中无法脱困，回城重新出发
        """
        self.is_recalling = True
        self.recall_start_time = time.time()
        logger.warning(f"卡住次数已达 {self.stuck_count}，触发回城保底机制")

    def cancel_recall(self, reason=""):
        """
        取消回城

        参数说明：
            reason: 取消原因（字符串），用于日志输出

        使用场景：
            回城过程中发现周围有敌人，需要取消回城参与战斗
        """
        if self.is_recalling:
            self.is_recalling = False
            self.recall_start_time = None
            logger.info(f"回城已取消：{reason}")

    def finish_recall(self):
        """
        回城完成，重置所有状态

        功能说明：
            回城成功后回到泉水，之前记录的卡住信息和死路记忆都不再有效
            因为英雄位置已经完全改变，需要从头开始
        """
        self.is_recalling = False
        self.recall_start_time = None
        self.stuck_count = 0  # 重置卡住计数
        self.stuck_confirm_count = 0  # 重置确认计数
        self.avoid_attempts = 0  # 重置尝试次数
        self.minimap_history.clear()  # 清空坐标历史
        self.dead_zones.clear()  # 清空死路记忆（回城后位置完全不同了）
        self.success_exits.clear()  # 清空成功路径记忆
        logger.info("回城完成，所有卡住状态和路径记忆已重置")

    def get_status(self):
        """
        获取当前状态信息（用于调试日志输出）

        返回值：
            dict: 包含所有关键状态的字典
        """
        return {
            "is_stuck_confirmed": self.stuck_confirm_count
            >= self.stuck_confirm_required,  # 是否确认卡住
            "stuck_confirm_count": self.stuck_confirm_count,  # 当前确认计数
            "is_avoiding": self.is_avoiding,  # 是否正在绕路
            "avoid_attempts": self.avoid_attempts,  # 当前绕路尝试次数
            "stuck_count": self.stuck_count,  # 累计卡住次数
            "avoid_success": self.avoid_success_count,  # 成功脱困次数
            "history_size": len(self.minimap_history),  # 当前历史记录数量
            "is_recalling": self.is_recalling,  # 是否正在回城
            "dead_zones_count": len(self.dead_zones),  # 已记录的死路数量
            "success_exits_count": len(self.success_exits),  # 已记录的成功路径数量
        }


# 统一移动控制器类
class UnifiedMovement:
    """统一移动控制器"""

    # 目标保护时间（秒），防止频繁切换目标
    PRIORITY_TARGET_PROTECT_TIME = 3.0  # 优先英雄保护时间（秒）
    NORMAL_TARGET_PROTECT_TIME = 2.0  # 普通目标保护时间（秒）

    def __init__(self):
        self.logger = logger
        self.target_pos = None  # 目标位置坐标 (x, y)
        self.target_name = None  # 目标名称（字符串）
        self.source = None  # 数据来源：'model1' 或 'model2'
        self.is_priority_target = False  # 是否是优先目标（射手等）
        self.last_move_time = 0  # 上次移动时间戳
        self.key_status = {
            KEY_MOVE_UP: False,
            KEY_MOVE_LEFT: False,
            KEY_MOVE_DOWN: False,
            KEY_MOVE_RIGHT: False,
        }  # 当前按键状态
        self._last_log_time = 0  # 上次日志输出时间（用于节流）

        # 目标切换保护机制
        self.target_lock_time = 0  # 目标锁定时间戳
        self.locked_target_pos = None  # 锁定的目标位置（用于判断是否是同一目标）

        # 队友移动检测（用于动态调整最小跟随距离）
        self._prev_target_pos = None  # 上一次目标位置
        self._target_moving = False  # 队友是否在移动
        self._target_move_threshold = 5  # 位置变化超过5px判定为移动

        # 卡地形检测器实例
        self.stuck_detector = StuckDetector()
        self._last_stuck_log_time = 0  # 卡地形日志节流时间戳

        # 路径跟随状态
        self._pathfinder = None  # OptimizedAStarPathfinder（懒加载）
        self._current_path = None  # [(grid_x, grid_y), ...] 路点列表
        self._path_index = 0  # 当前路点索引
        self._path_target_pos = None  # 此路径对应的目标网格坐标
        self._last_replan_time = 0  # 上次规划时间

    def update_from_model2(self, self_pos, team_targets, class_names=None):
        """
        模态2更新目标（优先级高）
        模态2通过血条检测队友位置，但无法识别英雄身份

        参数：
            self_pos: 自身位置 (x, y)
            team_targets: 队友列表 [(x, y, health_percentage), ...]
            class_names: 类别名称字典 {class_id: name} (模态2无此信息，忽略)

        返回：
            bool: 是否成功更新目标
        """
        if not self_pos or not team_targets:
            return False  # 缺少必要数据，返回失败

        # 模态2只能检测血条，无法识别英雄身份
        # team_targets 格式: [(x, y, health_percentage), ...]
        # 选择最近的队友（无法区分优先英雄）
        closest = min(
            team_targets,
            key=lambda t: sqrt((t[0] - self_pos[0]) ** 2 + (t[1] - self_pos[1]) ** 2),
        )

        new_pos = (closest[0], closest[1])
        # 检测队友是否在移动（位置变化超过阈值）
        if self._prev_target_pos is not None:
            move_dist = sqrt(
                (new_pos[0] - self._prev_target_pos[0]) ** 2
                + (new_pos[1] - self._prev_target_pos[1]) ** 2
            )
            self._target_moving = move_dist > self._target_move_threshold
        self._prev_target_pos = new_pos
        self.target_pos = new_pos  # 更新目标位置

        # 模态2无法识别英雄名称，统一显示为"队友"
        # 优先目标标记为False（因为无法识别）
        self.target_name = "队友"
        self.is_priority_target = False

        self.source = "model2"  # 标记数据来源
        return True

    def update_from_model1(self, g_center, b_centers, class_names=None):
        """
        模态1更新目标（模态2无数据时使用）
        模态1通过小地图检测队友位置和英雄身份

        参数：
            g_center: 自身在小地图的位置 (x, y)
            b_centers: 队友在小地图的列表 [(x, y, class_id), ...]
            class_names: 类别名称字典 {class_id: name}

        返回：
            bool: 是否成功更新目标
        """
        # 更新卡地形检测器的小地图坐标历史（只要有自身位置就更新）
        if g_center:
            self.stuck_detector.update(g_center)

        # 切换到mode1时，清除mode2的source标记，允许更新目标
        if self.source == "model2":
            self.source = None

        # 没有自身位置或没有队友时，无法更新跟随目标
        if not g_center or not b_centers:
            return False

        # 获取优先英雄列表（射手等高优先级英雄）
        priority_heroes = getattr(model1_astar_follow, "priority_heroes", [])

        # 分类：优先英雄和普通队友
        priority_targets = []  # 优先英雄列表
        normal_targets = []  # 普通队友列表

        for b in b_centers:
            if class_names and len(b) > 2:
                hero_name = class_names.get(b[2], "")  # 获取英雄拼音名
                # 检查是否是优先英雄
                # hero_name 是拼音格式如 "yuji_blue"
                # priority_heroes 也是拼音格式 ["yuji_blue", ...]
                if hero_name in priority_heroes:
                    priority_targets.append(b)
                else:
                    # 再尝试用中文名匹配
                    hero_chinese = get_hero_chinese(hero_name)
                    if hero_chinese in priority_heroes:
                        priority_targets.append(b)
                    else:
                        normal_targets.append(b)
            else:
                normal_targets.append(b)

        # 计算所有候选目标的距离（用于后续可能的优化）
        all_targets = priority_targets + normal_targets
        for target in all_targets:
            target_distance = sqrt(
                (target[0] - g_center[0]) ** 2 + (target[1] - g_center[1]) ** 2
            )
            target_distance_key = f"_dist_{target[0]}_{target[1]}"
            setattr(self, target_distance_key, target_distance)

        # 优先选择优先英雄，否则选择最近的普通队友
        if priority_targets:
            # 在优先英雄中选择最近的
            closest = min(
                priority_targets,
                key=lambda b: sqrt(
                    (b[0] - g_center[0]) ** 2 + (b[1] - g_center[1]) ** 2
                ),
            )
            is_priority = True
        else:
            # 没有优先英雄，选择最近的普通队友
            closest = min(
                normal_targets,
                key=lambda b: sqrt(
                    (b[0] - g_center[0]) ** 2 + (b[1] - g_center[1]) ** 2
                ),
            )
            is_priority = False

        # 检查目标切换保护（防止频繁切换目标）
        current_time = time.time()
        protect_time = (
            self.PRIORITY_TARGET_PROTECT_TIME
            if self.is_priority_target
            else self.NORMAL_TARGET_PROTECT_TIME
        )
        in_protect = (current_time - self.target_lock_time) < protect_time

        # 判断是否是新目标（位置不同）
        is_new_target = (
            self.locked_target_pos is None
            or abs(self.locked_target_pos[0] - closest[0]) > 10
            or abs(self.locked_target_pos[1] - closest[1]) > 10
        )

        # 在保护期内且是新目标，检查是否值得切换
        if in_protect and is_new_target and self.target_pos is not None:
            # 计算当前目标和新目标的距离
            new_dist = sqrt(
                (closest[0] - g_center[0]) ** 2 + (closest[1] - g_center[1]) ** 2
            )
            old_dist = sqrt(
                (self.target_pos[0] - g_center[0]) ** 2
                + (self.target_pos[1] - g_center[1]) ** 2
            )

            # 新目标必须明显更近才切换（差距大于50像素）
            if old_dist - new_dist < 50:
                # 不切换，保持当前目标
                return True

        # 更新目标信息
        self.target_pos = (closest[0], closest[1])
        self.locked_target_pos = (closest[0], closest[1])
        self.target_lock_time = current_time

        # 获取目标名称
        if class_names and len(closest) > 2:
            name = class_names.get(closest[2], "队友")
            self.target_name = get_hero_chinese(name)
        else:
            self.target_name = "队友"

        # 记录是否是优先目标
        self.is_priority_target = is_priority

        self.source = "model1"  # 标记数据来源
        return True

    def execute_move(self, self_pos, target_pos=None, enemies=None, battle_state=None):
        """
        执行移动
        根据目标位置计算方向并发送键盘指令

        参数：
            self_pos: 当前自身位置 (x, y)
            target_pos: 可选，直接指定目标位置（用于卡地形检测等场景）
            enemies: 可选，敌人列表，用于回城保底机制判断
            battle_state: 可选，战斗状态（如 'retreat' 表示撤退）
        """
        import math

        current_time = time.time()  # 获取当前时间戳

        # ===== 回城保底机制 =====
        # 正在回城中
        if self.stuck_detector.is_recalling:
            recall_start_time = self.stuck_detector.recall_start_time
            if recall_start_time is None:
                self.stuck_detector.cancel_recall("缺少回城起始时间")
                self._release_all_keys()
                return
            elapsed = current_time - recall_start_time

            # 检查周围是否有敌人，有则取消回城
            if enemies and len(enemies) > 0:
                self.stuck_detector.cancel_recall("周围发现敌人")
                tap("b")  # 再按一次B取消回城
            elif elapsed >= self.stuck_detector.RECALL_DURATION:
                # 回城完成
                self.stuck_detector.finish_recall()
            else:
                # 回城进行中，释放所有按键，不做任何移动
                self._release_all_keys()
                return

        # 检查是否需要触发回城（stuck_count >= 30 且周围无敌人）
        if (
            self.stuck_detector.stuck_count
            >= self.stuck_detector.STUCK_RECALL_THRESHOLD
            and not self.stuck_detector.is_recalling
        ):
            has_enemies = enemies and len(enemies) > 0
            if not has_enemies:
                self._release_all_keys()
                tap("b")  # 按B键开始回城
                self.stuck_detector.start_recall()
                return

        # 移动间隔控制（使用统一的 MOVE_INTERVAL）
        if current_time - self.last_move_time < MOVE_INTERVAL:
            return  # 间隔不足，直接返回
        self.last_move_time = current_time

        # 使用传入的目标位置或 self.target_pos
        actual_target = target_pos if target_pos is not None else self.target_pos

        # 没有目标，释放按键
        if not actual_target or not self_pos:
            self._release_all_keys()
            return

        # ===== 路径跟随（仅 model1 小地图坐标） =====
        if self.source == "model1":
            waypoint = self._get_path_waypoint(self_pos, actual_target)
            if waypoint is not None:
                actual_target = waypoint

        # 计算原始方向向量（目标位置 - 自身位置）
        dx = actual_target[0] - self_pos[0]
        dy = actual_target[1] - self_pos[1]
        original_distance = sqrt(dx**2 + dy**2)  # 计算欧氏距离

        # 撤退逻辑：RETREAT状态下向远离敌人方向移动
        if (
            battle_state is not None
            and battle_state == "retreat"
            and enemies
            and len(enemies) > 0
        ):
            # 计算所有敌人的平均位置
            enemy_positions = [
                (e[0], e[1]) for e in enemies
            ]  # enemies格式: [(x, y, health%), ...]
            avg_enemy_x = sum(p[0] for p in enemy_positions) / len(enemy_positions)
            avg_enemy_y = sum(p[1] for p in enemy_positions) / len(enemy_positions)

            # 远离敌人的方向
            retreat_dx = self_pos[0] - avg_enemy_x
            retreat_dy = self_pos[1] - avg_enemy_y

            retreat_dist = math.sqrt(retreat_dx**2 + retreat_dy**2)
            if retreat_dist > 1:
                # 用撤退方向覆盖原始方向
                dx = retreat_dx
                dy = retreat_dy
                original_distance = retreat_dist
                # 日志
                self.logger.info(
                    f"[RETREAT] 远离敌人移动, 敌人中心=({avg_enemy_x:.0f},{avg_enemy_y:.0f}), 方向=({dx:.0f},{dy:.0f})"
                )

        # 使用欧氏距离检查是否足够近（在死区内）
        if original_distance <= MOVE_DEADZONE:
            self._release_all_keys()
            return

        # 检查是否太近（防止遮挡队友血条）
        # 队友在移动时不停止，保持紧密跟随；队友静止时保持最小距离
        if original_distance < MIN_FOLLOW_DISTANCE and not self._target_moving:
            self._release_all_keys()
            if (current_time - self._last_log_time) > 1.0:  # 每秒输出一次
                logger.debug(
                    f"距离队友过近({int(original_distance)}px)，队友静止，停止移动避免遮挡血条"
                )
                self._last_log_time = current_time
            return

        # 计算原始方向角度（弧度）
        original_angle = math.atan2(dy, dx)

        # ----- 卡地形检测与绕路逻辑 -----
        final_dx, final_dy = dx, dy  # 初始化最终移动向量为原始向量
        is_avoiding = False  # 标记是否正在绕路

        # 调试：确认卡地形检测被调用
        is_stuck_result = self.stuck_detector.is_stuck(current_time)
        avoid_angle = None
        if not hasattr(self, "_last_stuck_check_log"):
            self._last_stuck_check_log = 0
        if current_time - self._last_stuck_check_log > 3.0:
            stuck_status = self.stuck_detector.get_status()
            logger.debug(
                f"[卡地形检查] is_stuck={is_stuck_result}, 历史={stuck_status['history_size']}, 确认={stuck_status['stuck_confirm_count']}, stuck_count={stuck_status['stuck_count']}, 阈值={self.stuck_detector.stuck_threshold}"
            )
            self._last_stuck_check_log = current_time

        # 检查是否卡住
        if is_stuck_result:
            # 路径感知：先强制重规划，再试绕路
            if self._current_path is not None:
                self._current_path = None
                self.stuck_detector.stuck_confirm_count = 0
            else:
                # 开始绕路
                avoid_angle = self.stuck_detector.start_avoidance(original_angle)
            if avoid_angle is not None:
                # 使用绕路方向（100像素的移动向量）
                final_dx = math.cos(avoid_angle) * 100
                final_dy = math.sin(avoid_angle) * 100
                is_avoiding = True
        elif self.stuck_detector.is_avoiding:
            # 正在绕路中，更新绕路状态
            avoid_angle = self.stuck_detector.update_avoidance()
            if avoid_angle is not None:
                final_dx = math.cos(avoid_angle) * 100
                final_dy = math.sin(avoid_angle) * 100
                is_avoiding = True

        abs_dx, abs_dy = abs(final_dx), abs(final_dy)  # 计算最终向量的绝对值

        # 计算移动方向（8方向）
        new_keys = {
            KEY_MOVE_UP: False,
            KEY_MOVE_LEFT: False,
            KEY_MOVE_DOWN: False,
            KEY_MOVE_RIGHT: False,
        }

        # 当X和Y方向都有位移时，触发斜向移动
        if abs_dx > MOVE_DEADZONE and abs_dy > MOVE_DEADZONE:
            new_keys[KEY_MOVE_RIGHT] = final_dx > 0  # 向右
            new_keys[KEY_MOVE_LEFT] = final_dx < 0  # 向左
            new_keys[KEY_MOVE_DOWN] = final_dy > 0  # 向下
            new_keys[KEY_MOVE_UP] = final_dy < 0  # 向上
        elif abs_dx > abs_dy:
            # 主要X方向移动
            new_keys[KEY_MOVE_RIGHT] = final_dx > 0  # 向右
            new_keys[KEY_MOVE_LEFT] = final_dx < 0  # 向左
        else:
            # 主要Y方向移动
            new_keys[KEY_MOVE_DOWN] = final_dy > 0  # 向下
            new_keys[KEY_MOVE_UP] = final_dy < 0  # 向上

        # 应用按键（持续按压）
        active_keys = []  # 记录当前激活的按键
        for key in new_keys:
            if new_keys[key]:
                press(key)  # 按下按键
                active_keys.append(key.upper())  # 记录大写按键名
            else:
                release(key)  # 释放按键
            self.key_status[key] = new_keys[key]  # 更新按键状态

        # 输出日志（每1.0秒一次）
        if active_keys and (current_time - self._last_log_time) > 1.0:
            priority_mark = (
                "⭐优先" if getattr(self, "is_priority_target", False) else ""
            )  # 优先目标标记
            avoid_mark = "🔄绕路" if is_avoiding else ""  # 绕路标记
            pos_str = (
                f"({int(self.target_pos[0])},{int(self.target_pos[1])})"
                if self.target_pos is not None
                else "(None)"
            )
            logger.debug(
                f"[移动指令] {'+'.join(active_keys)} -> {self.target_name}{priority_mark}{avoid_mark}{pos_str} [{self.source}]"
            )
            self._last_log_time = current_time

        # 输出卡地形状态日志（每5秒一次）
        if current_time - self._last_stuck_log_time > 5.0:
            status = self.stuck_detector.get_status()
            if status["stuck_count"] > 0 or status["is_avoiding"]:
                logger.debug(
                    f"[卡地形状态] 历史次数:{status['stuck_count']}, 成功脱困:{status['avoid_success']}, 正在绕路:{status['is_avoiding']}"
                )
            self._last_stuck_log_time = current_time

    def _release_all_keys(self):
        """释放所有按键"""
        for key in self.key_status:
            if self.key_status[key]:  # 如果该键处于按下状态
                release(key)  # 释放该键
                self.key_status[key] = False  # 更新状态为未按下

    def clear(self):
        """清除目标（切换场景时用）"""
        self.target_pos = None
        self.target_name = None
        self.source = None
        self._current_path = None
        self._release_all_keys()  # 释放所有按键

    # ===== 路径跟随辅助方法 =====

    def _get_pathfinder(self):
        """懒加载寻路器。"""
        if self._pathfinder is None:
            from wzry_ai.detection.map_preprocessor import MapLayers
            from wzry_ai.detection.pathfinding_optimized import OptimizedAStarPathfinder

            self._pathfinder = OptimizedAStarPathfinder(MapLayers.get())
        return self._pathfinder

    def _get_path_waypoint(self, self_pos, target_pos):
        """
        计算或跟随路径，返回前瞻路点（小地图像素坐标）。
        返回 None 时回退到直接向量跟随。
        """
        self_grid = (int(self_pos[0] / CELL_SIZE), int(self_pos[1] / CELL_SIZE))
        target_grid = (int(target_pos[0] / CELL_SIZE), int(target_pos[1] / CELL_SIZE))

        # 距离太近不需要寻路
        if self._grid_distance(self_grid, target_grid) < 5:
            self._current_path = None
            return None

        # 判断是否需要重新规划
        need_replan = (
            self._current_path is None
            or self._path_target_pos is None
            or self._grid_distance(target_grid, self._path_target_pos)
            > PATH_REPLAN_DISTANCE
            or self._distance_to_path(self_grid) > CORRIDOR_TOLERANCE
            or time.time() - self._last_replan_time > 3.0
        )

        if need_replan:
            pathfinder = self._get_pathfinder()
            path = pathfinder.find_path(self_grid, target_grid)
            if path and len(path) >= 2:
                self._current_path = path
                self._path_index = 0
                self._path_target_pos = target_grid
                self._last_replan_time = time.time()
                # 通知 localizer 有活跃路径
                try:
                    from wzry_ai.detection.map_constrained_localizer import (
                        MapConstrainedLocalizer,
                    )

                    MapConstrainedLocalizer.get().set_active_path(path)
                except Exception:
                    pass
            else:
                self._current_path = None
                return None

        # 推进路点索引
        self._advance_path_index(self_grid)

        # 找前瞻点
        lookahead = self._find_lookahead(self_grid, LOOKAHEAD_DISTANCE)
        if lookahead is None:
            return None

        # 转回小地图像素坐标
        return (
            lookahead[0] * CELL_SIZE + CELL_SIZE / 2,
            lookahead[1] * CELL_SIZE + CELL_SIZE / 2,
        )

    def _advance_path_index(self, self_grid):
        """推进路点索引，跳过已到达的路点。"""
        if self._current_path is None:
            return
        while self._path_index < len(self._current_path) - 1:
            wp = self._current_path[self._path_index]
            if self._grid_distance(self_grid, wp) < 3:
                self._path_index += 1
            else:
                break

    def _find_lookahead(self, self_grid, distance):
        """找前方 distance 格处的路点。"""
        if self._current_path is None:
            return None

        accumulated = 0.0
        for i in range(self._path_index, len(self._current_path) - 1):
            seg_len = self._grid_distance(
                self._current_path[i], self._current_path[i + 1]
            )
            accumulated += seg_len
            if accumulated >= distance:
                return self._current_path[i + 1]

        # 路径比前瞻距离短，返回终点
        return self._current_path[-1]

    def _distance_to_path(self, self_grid) -> float:
        """当前位置到路径最近点的距离。"""
        if self._current_path is None:
            return float("inf")

        start = max(0, self._path_index - 2)
        end = min(len(self._current_path), self._path_index + 6)

        min_dist = float("inf")
        for i in range(start, end):
            d = self._grid_distance(self_grid, self._current_path[i])
            if d < min_dist:
                min_dist = d
        return min_dist

    @staticmethod
    def _grid_distance(a, b) -> float:
        """两个网格坐标间的欧氏距离。"""
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


# 全局移动控制器实例（单例模式）
_movement_controller = None


# 获取全局移动控制器实例的函数
def get_movement_controller():
    """获取全局移动控制器实例（单例）"""
    global _movement_controller
    if _movement_controller is None:
        _movement_controller = UnifiedMovement()  # 创建新实例
    return _movement_controller
