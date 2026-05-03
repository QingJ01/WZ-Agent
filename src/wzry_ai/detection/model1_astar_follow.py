"""
模态1（小地图）A* 寻路跟随模块

功能：基于小地图目标检测结果，使用 A* 算法计算最优路径并控制英雄移动
核心逻辑：
  1. 加载障碍物地图进行寻路
  2. 优先跟随指定英雄（射手优先级）
  3. 将小地图坐标转换为键盘 WASD 指令
使用场景：小地图检测到友方英雄时的自动跟随
"""

# 导入numpy库用于数值计算和数组操作
import numpy as np

# 从heapq导入堆操作函数，用于A*算法的优先队列
from heapq import heappop, heappush

# 从math导入sqrt函数用于计算距离
from math import sqrt

# 导入time模块用于时间相关操作
import time

# 从keyboard_controller导入按键控制函数
from wzry_ai.utils.keyboard_controller import press, release

# 从utils导入寻找最近目标的工具函数
from wzry_ai.utils.utils import find_closest_target

# 从config模块导入统一配置参数
from wzry_ai.config import (
    GRID_SIZE,  # 网格大小，用于寻路网格划分
    CELL_SIZE,  # 每个网格单元的大小（像素）
    G_CENTER_CACHE_DURATION,  # 自身位置缓存的有效时长（秒）
    G_CENTER_MISS_THRESHOLD,  # 自身位置丢失的阈值次数
    MOVE_INTERVAL,  # 两次移动指令之间的最小间隔（秒）
    MOVE_DEADZONE,  # 移动死区，小于此值不移动（像素）
    DIAGONAL_THRESHOLD,  # 斜向移动的阈值
    MINIMAP_SCALE_FACTOR,  # 小地图坐标到移动向量的缩放因子
    CLASS_NAMES_FILE,  # 类别名称映射文件路径
    KEY_MOVE_UP,  # 向上移动按键
    KEY_MOVE_LEFT,  # 向左移动按键
    KEY_MOVE_DOWN,  # 向下移动按键
    KEY_MOVE_RIGHT,  # 向右移动按键
)

# 从hero_mapping导入英雄名称转换函数
from wzry_ai.config.heroes.mapping import convert_priority_heroes

# 尝试加载障碍物网格文件，用于A*寻路避障
try:
    # 从资源解析器加载 map_grid.txt，避免手工拼接仓库根目录
    from wzry_ai.utils.resource_resolver import resolve_data_path

    map_grid_path = resolve_data_path("map_grid.txt")
    obstacle_map = np.loadtxt(map_grid_path, dtype=int)
    if obstacle_map.shape != (GRID_SIZE, GRID_SIZE):
        raise ValueError(f"invalid map grid shape: {obstacle_map.shape}")
except FileNotFoundError:
    # 如果文件不存在，创建一个全零的空地图（无障碍物）
    obstacle_map = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
except (ValueError, OSError) as e:
    # 其他异常时也创建空地图，确保程序不崩溃
    obstacle_map = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)

# 全局变量：存储当前自身在小地图上的位置坐标
g_center = None
# 全局变量：缓存的自身位置，用于位置丢失时的临时恢复
g_center_cache = None
# 全局变量：记录上次更新自身位置的时间戳
g_center_last_update_time = 0

# 初始化按键状态字典，记录每个方向键是否被按下
key_status = {
    KEY_MOVE_UP: False,
    KEY_MOVE_LEFT: False,
    KEY_MOVE_DOWN: False,
    KEY_MOVE_RIGHT: False,
}
# 全局变量：记录上次执行移动指令的时间戳
last_move_time = 0
# 记录移动日志时间戳，避免依赖函数属性
move_direction_last_log_time = 0.0

# 定义优先跟随的英雄列表（中文名），会自动转换为拼音_blue格式
_priority_heroes_raw = [
    "敖隐",
    "莱西奥",
    "戈娅",
    "艾琳",
    "蒙犺",
    "伽罗",
    "公孙离",
    "黄忠",
    "虞姬",
    "李元芳",
    "后羿",
    "狄仁杰",
    "马可波罗",
    "鲁班七号",
    "孙尚香",
]
# 将中文英雄名转换为拼音格式的优先级列表
priority_heroes = convert_priority_heroes(_priority_heroes_raw)

# 加载类别名称映射表（YOLO检测的类别ID到英雄名称的映射）
try:
    # 打开类别名称文件进行读取
    with open(CLASS_NAMES_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()  # 读取所有行
        class_names = {}  # 初始化空字典存储映射关系
        for line in lines:
            line = line.strip()  # 去除行首行尾空白字符
            # 检查行是否有效：非空、包含冒号、不是注释行
            if line and ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)  # 按第一个冒号分割键值
                try:
                    key = int(key)  # 将键转换为整数（类别ID）
                    # 提取格式: "huangzhong_blue | 黄忠 | 队友" -> "huangzhong_blue"
                    value = value.strip().strip("'")
                    if "|" in value:
                        value = value.split("|")[0].strip()  # 只取管道符前的部分
                    class_names[key] = value  # 存入字典
                except ValueError:
                    continue  # 转换失败则跳过该行
except FileNotFoundError:
    # 文件不存在时使用空字典
    class_names = {}
except (ValueError, OSError, UnicodeDecodeError) as e:
    # 其他异常时也使用空字典
    class_names = {}


# A*寻路算法的节点类，用于表示寻路网格中的每个节点
class Node:
    def __init__(self, x, y, cost, parent=None):
        self.x = x  # 节点的X坐标（网格坐标）
        self.y = y  # 节点的Y坐标（网格坐标）
        self.cost = cost  # 节点的总代价（g + h）
        self.parent = parent  # 父节点指针，用于回溯路径

    def __lt__(self, other):
        # 定义小于运算符，用于优先队列比较（比较代价）
        return self.cost < other.cost


# 切比雪夫启发函数，用于A*算法估算两点间的距离
# 切比雪夫距离允许8方向移动，更适合网格寻路
def heuristic_chebyshev(a, b):
    D, D2 = 1, sqrt(2)  # D是直线移动代价，D2是斜线移动代价
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])  # 计算X和Y方向的距离差
    return D * (dx + dy) + (D2 - 2 * D) * min(dx, dy)  # 切比雪夫距离公式


# A*寻路算法主函数
# 参数：start起点坐标，goal目标点坐标，obstacle_map障碍物地图
# 返回：从起点到目标点的路径列表，如果无法到达则返回None
def a_star(start, goal, obstacle_map):
    open_set = []  # 开放列表，存储待探索的节点
    heappush(open_set, (0, Node(start[0], start[1], 0)))  # 将起点加入开放列表
    closed_set = set()  # 关闭列表，存储已探索的节点
    g_score: dict[tuple[int, int], float] = {start: 0.0}  # 记录从起点到各节点的实际代价
    while open_set:
        current_node = heappop(open_set)[1]  # 取出代价最小的节点
        current = (current_node.x, current_node.y)  # 获取当前节点坐标
        if current == goal:
            # 到达目标，回溯构建路径
            path = []
            while current_node:
                path.append((current_node.x, current_node.y))
                current_node = current_node.parent
            return path[::-1]  # 反转路径使其从起点到终点
        closed_set.add(current)  # 将当前节点加入关闭列表
        # 遍历8个方向的邻居节点（上下左右+4个对角线）
        for dx, dy in [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]:
            neighbor = (current[0] + dx, current[1] + dy)  # 计算邻居坐标
            # 检查邻居是否在网格范围内且不是障碍物
            if (
                0 <= neighbor[0] < GRID_SIZE
                and 0 <= neighbor[1] < GRID_SIZE
                and obstacle_map[neighbor[1], neighbor[0]] == 0
            ):
                move_cost = sqrt(2) if dx != 0 and dy != 0 else 1.0  # 斜线移动代价更高
                tentative_g_score = float(
                    g_score[current] + move_cost
                )  # 计算到邻居的 tentative 代价
                # 如果邻居已在关闭列表且新代价不更优，跳过
                if neighbor in closed_set and tentative_g_score >= g_score.get(
                    neighbor, float("inf")
                ):
                    continue
                # 如果找到更优路径，更新邻居信息
                if tentative_g_score < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g_score  # 更新g值
                    f_score = tentative_g_score + heuristic_chebyshev(
                        neighbor, goal
                    )  # 计算f值
                    heappush(
                        open_set,
                        (
                            f_score,
                            Node(neighbor[0], neighbor[1], f_score, current_node),
                        ),
                    )  # 加入开放列表
    return None  # 开放列表为空且未找到路径，返回None


# 将像素坐标转换为网格坐标
def convert_to_grid_coordinates(pixel_x, pixel_y):
    return int(pixel_x // CELL_SIZE), int(pixel_y // CELL_SIZE)


# 释放所有方向按键的函数
def release_all_keys():
    """释放所有按键"""
    global key_status  # 使用全局按键状态变量
    for key in key_status:
        if key_status[key]:  # 如果该键处于按下状态
            release(key)  # 释放该键
            key_status[key] = False  # 更新状态为未按下


# 根据方向向量执行键盘移动指令
# 参数：dx,dy为目标方向向量，target_name为目标名称（用于日志），target_x,target_y为目标坐标（用于日志）
def move_direction(dx, dy, target_name=None, target_x=None, target_y=None):
    """
    使用键盘 WASD 移动
    dx, dy: 目标方向向量
    target_name, target_x, target_y: 目标信息（用于日志）
    """
    global last_move_time, move_direction_last_log_time  # 使用全局上次移动时间变量
    current_time = time.time()  # 获取当前时间戳

    # 检查是否满足移动间隔要求，避免过于频繁的按键操作
    if current_time - last_move_time < MOVE_INTERVAL:
        return

    abs_dx, abs_dy = abs(dx), abs(dy)  # 计算方向向量的绝对值

    # 如果偏移太小（在死区内），停止移动并释放所有按键
    if abs_dx <= MOVE_DEADZONE and abs_dy <= MOVE_DEADZONE:
        release_all_keys()
        return

    # 初始化新的按键状态字典，所有方向默认为False（未按下）
    new_keys = {
        KEY_MOVE_UP: False,
        KEY_MOVE_LEFT: False,
        KEY_MOVE_DOWN: False,
        KEY_MOVE_RIGHT: False,
    }

    # 当X和Y方向都有位移时，触发斜向移动
    if abs_dx > MOVE_DEADZONE and abs_dy > MOVE_DEADZONE:
        # 斜向移动：同时按两个方向键
        new_keys[KEY_MOVE_RIGHT] = dx > 0  # 向右
        new_keys[KEY_MOVE_LEFT] = dx < 0  # 向左
        new_keys[KEY_MOVE_DOWN] = dy > 0  # 向下
        new_keys[KEY_MOVE_UP] = dy < 0  # 向上
    elif abs_dx > abs_dy:
        # 主要X方向移动
        new_keys[KEY_MOVE_RIGHT] = dx > 0  # 向右
        new_keys[KEY_MOVE_LEFT] = dx < 0  # 向左
    else:
        # 主要Y方向移动
        new_keys[KEY_MOVE_DOWN] = dy > 0  # 向下
        new_keys[KEY_MOVE_UP] = dy < 0  # 向上

    # 应用按键变化（持续按压以确保跟随紧密）
    active_keys = []  # 记录当前激活的按键
    for key in new_keys:
        if new_keys[key]:
            press(key)  # 按下按键
            active_keys.append(key.upper())  # 记录大写的按键名
        else:
            release(key)  # 释放按键
        key_status[key] = new_keys[key]  # 更新按键状态

    # 每0.5秒输出一次移动日志（更及时看到效果）
    if active_keys and (current_time - move_direction_last_log_time) > 0.5:
        if target_name is not None and target_x is not None and target_y is not None:
            target_info = f" -> {target_name}({int(target_x)},{int(target_y)})"
        else:
            target_info = ""
        _ = target_info
        move_direction_last_log_time = current_time  # 更新上次日志时间

    last_move_time = current_time  # 更新上次移动时间


# 辅助函数：从检测到的友方英雄中找到优先跟随的目标
# 参数：b_centers是友方英雄列表，g_center是自身位置
# 返回：选中的目标英雄信息
def find_priority_target(b_centers, g_center):
    priority_targets = []  # 存储优先级高的目标列表
    closest_target = None  # 存储最近的普通目标
    min_distance = float("inf")  # 初始化最小距离为无穷大
    for b_center in b_centers:
        # 计算自身与该友方英雄的距离
        distance = sqrt(
            (g_center[0] - b_center[0]) ** 2 + (g_center[1] - b_center[1]) ** 2
        )
        class_id = b_center[2]  # 获取英雄的类别ID
        hero_name = class_names.get(class_id, "未知英雄")  # 根据ID获取英雄名称
        if hero_name in priority_heroes:
            # 如果是优先英雄，加入优先级列表
            priority_targets.append((b_center, distance))
        elif not priority_targets and (
            closest_target is None or distance < min_distance
        ):
            # 如果没有优先英雄且该目标更近，记录为最近目标
            closest_target = b_center
            min_distance = distance
    if priority_targets:
        # 如果有优先英雄，选择距离最近的优先英雄
        target, _ = min(priority_targets, key=lambda x: x[1])
    else:
        # 否则选择最近的普通目标
        target = closest_target
    return target


# 模态1移动逻辑主函数
# 参数：detection_result是检测结果字典，包含g_center（自身位置）和b_centers（友方英雄列表）
# 返回：包含移动状态的字典
def model1_movement_logic(detection_result):
    global g_center, g_center_cache, g_center_last_update_time  # 使用全局变量
    g_center = detection_result.get("g_center")  # 获取自身在小地图的位置
    b_centers = detection_result.get("b_centers", [])  # 获取友方英雄列表
    current_time = time.time()  # 获取当前时间戳

    # 状态更新逻辑：处理自身位置的缓存和丢失恢复
    if g_center:
        # 如果检测到自身位置，更新缓存和时间戳
        g_center_cache = g_center
        g_center_last_update_time = current_time
    elif (
        g_center_cache
        and (current_time - g_center_last_update_time) < G_CENTER_CACHE_DURATION
    ):
        # 如果未检测到但缓存未过期，使用缓存位置
        g_center = g_center_cache
    else:
        # 缓存过期，清空位置
        g_center = None

    # 如果既有自身位置又有友方英雄，执行跟随逻辑
    if g_center and b_centers:
        target = find_priority_target(b_centers, g_center)  # 找到要跟随的目标
        if target:
            # 计算小地图上的方向向量（目标位置 - 自身位置）
            dx = target[0] - g_center[0]
            dy = target[1] - g_center[1]

            # 将小地图坐标差转换为移动指令（乘以缩放因子）
            move_dx = dx * MINIMAP_SCALE_FACTOR
            move_dy = dy * MINIMAP_SCALE_FACTOR

            # 获取目标英雄的名称
            target_class_id = target[2] if len(target) > 2 else None
            target_name = class_names.get(target_class_id, "未知")

            # 执行移动指令
            move_direction(move_dx, move_dy, target_name, target[0], target[1])
            return {"g_center": g_center, "closest_b": target, "is_moving": True}

    # 没有目标时释放所有按键
    release_all_keys()
    return {"g_center": g_center, "closest_b": None, "is_moving": False}


# 程序入口点
if __name__ == "__main__":
    pass  # 此模块作为库导入使用，不直接运行
