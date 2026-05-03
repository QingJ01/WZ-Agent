"""
优化的寻路算法模块 - 两层寻路系统

提供：
1. 骨架图全局路由（Dijkstra，<0.1ms）
2. Clearance 加权 A*（局部优化，<5ms）
3. Line-of-sight 路径平滑
4. 路径缓存机制
"""

import numpy as np
from heapq import heappop, heappush
from math import sqrt
from typing import List, Tuple, Optional
import time

from wzry_ai.config.base import (
    PATHFINDING_MAX_ITERATIONS,
    CLEARANCE_PENALTY_THRESHOLD,
    CLEARANCE_PENALTY_WEIGHT,
    TURN_PENALTY,
    PATH_CACHE_SIZE,
)


class OptimizedAStarPathfinder:
    """
    两层寻路器：骨架图全局路由 + clearance 加权 A* 局部优化。

    用法：
        from wzry_ai.detection.map_preprocessor import MapLayers
        pathfinder = OptimizedAStarPathfinder(MapLayers.get())
        path = pathfinder.find_path((start_gx, start_gy), (goal_gx, goal_gy))
    """

    def __init__(self, map_layers):
        self.map = map_layers
        self.inflated = map_layers.inflated_map
        self.clearance = map_layers.clearance_map
        self.grid_h, self.grid_w = self.inflated.shape

        # 骨架图数据
        self.skeleton_nodes = map_layers.skeleton_nodes
        self.skeleton_adj = map_layers.skeleton_adjacency

        # 节点位置数组，用于快速最近节点查找
        if self.skeleton_nodes:
            self._node_arr = np.array(self.skeleton_nodes, dtype=np.float32)
        else:
            self._node_arr = np.empty((0, 2), dtype=np.float32)

        # 路径缓存
        self._cache = {}
        self._cache_order = []

        # 8方向移动
        self._dirs = [
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (0, -1, 1.0),
            (0, 1, 1.0),
            (-1, -1, 1.414),
            (-1, 1, 1.414),
            (1, -1, 1.414),
            (1, 1, 1.414),
        ]

    # ==================== 主入口 ====================

    def find_path(
        self, start: Tuple[int, int], goal: Tuple[int, int]
    ) -> Optional[List[Tuple[int, int]]]:
        """
        寻路主入口。

        参数：
            start: (grid_x, grid_y) 起点网格坐标
            goal: (grid_x, grid_y) 目标网格坐标

        返回：
            [(gx, gy), ...] 路点列表，或 None
        """
        # 边界检查
        if not self._in_bounds(start[0], start[1]) or not self._in_bounds(
            goal[0], goal[1]
        ):
            return None

        # 起点/终点在障碍内时 snap
        if self.inflated[start[1], start[0]] == 1:
            start = self.map.snap_to_walkable(start[0], start[1])
        if self.inflated[goal[1], goal[0]] == 1:
            goal = self.map.snap_to_walkable(goal[0], goal[1])

        # 距离太近不需要寻路
        dx = abs(start[0] - goal[0])
        dy = abs(start[1] - goal[1])
        if dx + dy <= 3:
            return [start, goal]

        # 查缓存
        cache_key = self._cache_key(start, goal)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 尝试骨架图路由
        path = self._skeleton_route(start, goal)

        # 回退到 clearance A*
        if path is None or len(path) < 2:
            path = self._clearance_astar(start, goal)

        # 路径平滑
        if path and len(path) > 2:
            path = self._smooth_path(path)

        # 存缓存
        if path:
            self._put_cache(cache_key, path)

        return path

    def invalidate_cache(self):
        """清空路径缓存。"""
        self._cache.clear()
        self._cache_order.clear()

    # ==================== 骨架图路由 ====================

    def _skeleton_route(self, start: tuple, goal: tuple) -> Optional[List[tuple]]:
        """骨架图 Dijkstra 全局路由。"""
        if len(self.skeleton_nodes) < 2:
            return None

        start_node = self._nearest_skeleton_node(start)
        goal_node = self._nearest_skeleton_node(goal)

        if start_node is None or goal_node is None:
            return None
        if start_node == goal_node:
            return [start, goal]

        # Dijkstra
        dist = {start_node: 0.0}
        prev = {}
        heap = [(0.0, start_node)]

        while heap:
            d, u = heappop(heap)
            if u == goal_node:
                break
            if d > dist.get(u, float("inf")):
                continue
            for v, cost in self.skeleton_adj.get(u, []):
                nd = d + cost
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = u
                    heappush(heap, (nd, v))

        # 回溯路径
        if goal_node not in prev and start_node != goal_node:
            return None

        node_path = []
        cur = goal_node
        while cur != start_node:
            node_path.append(cur)
            cur = prev.get(cur)
            if cur is None:
                return None
        node_path.append(start_node)
        node_path.reverse()

        # 转为网格坐标路径：start → skeleton nodes → goal
        path = [start]
        for idx in node_path:
            path.append(self.skeleton_nodes[idx])
        path.append(goal)

        return path

    def _nearest_skeleton_node(self, pos: tuple) -> Optional[int]:
        """找最近的骨架节点索引。"""
        if len(self._node_arr) == 0:
            return None
        diffs = self._node_arr - np.array([pos[0], pos[1]], dtype=np.float32)
        dists = diffs[:, 0] ** 2 + diffs[:, 1] ** 2
        idx = int(np.argmin(dists))
        # 如果最近节点太远（>30格），不使用骨架路由
        if dists[idx] > 900:
            return None
        return idx

    # ==================== Clearance 加权 A* ====================

    def _clearance_astar(self, start: tuple, goal: tuple) -> Optional[List[tuple]]:
        """
        Clearance 加权 A*。

        代价 = 移动距离 + 靠近障碍惩罚 + 转向惩罚
        硬约束：inflated_map 为 1 的格子不可进入
        """
        # g_score: (x, y) -> cost
        g_score = {start: 0.0}
        # parent: (x, y) -> (px, py)
        parent = {}
        # parent direction for turn penalty
        parent_dir: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

        h = self._heuristic(start, goal)
        # heap: (f_score, x, y)
        heap = [(h, start[0], start[1])]
        closed = set()
        iterations = 0

        while heap and iterations < PATHFINDING_MAX_ITERATIONS:
            iterations += 1
            f, cx, cy = heappop(heap)
            current = (cx, cy)

            if current == goal:
                return self._reconstruct(parent, start, goal)

            if current in closed:
                continue
            closed.add(current)

            cur_g = g_score[current]
            cur_dir = parent_dir.get(current)

            for ddx, ddy, move_cost in self._dirs:
                nx, ny = cx + ddx, cy + ddy

                if not self._in_bounds(nx, ny):
                    continue
                if self.inflated[ny, nx] == 1:
                    continue

                neighbor = (nx, ny)
                if neighbor in closed:
                    continue

                # Clearance 惩罚
                cl = float(self.clearance[ny, nx])
                prox_penalty = 0.0
                if cl < CLEARANCE_PENALTY_THRESHOLD:
                    prox_penalty = (
                        CLEARANCE_PENALTY_THRESHOLD - cl
                    ) * CLEARANCE_PENALTY_WEIGHT

                # 转向惩罚
                new_dir = (ddx, ddy)
                turn_cost = 0.0
                if cur_dir is not None and new_dir != cur_dir:
                    turn_cost = TURN_PENALTY

                tentative_g = cur_g + move_cost + prox_penalty + turn_cost

                if tentative_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g
                    parent[neighbor] = current
                    parent_dir[neighbor] = new_dir
                    f_score = tentative_g + self._heuristic(neighbor, goal)
                    heappush(heap, (f_score, nx, ny))

        # 迭代上限到了，返回到目前为止最接近目标的路径
        if goal in parent or start == goal:
            return self._reconstruct(parent, start, goal)

        # 找已探索中离目标最近的点
        if closed:
            best = min(closed, key=lambda p: self._heuristic(p, goal))
            if best != start:
                return self._reconstruct(parent, start, best)

        return None

    # ==================== 路径平滑 ====================

    def _smooth_path(self, path: List[tuple]) -> List[tuple]:
        """Line-of-sight 路径压缩，消除锯齿。"""
        if len(path) <= 2:
            return path

        smoothed = [path[0]]
        i = 0
        while i < len(path) - 1:
            farthest = i + 1
            # 从远到近尝试跳跃
            for j in range(len(path) - 1, i + 1, -1):
                if self._line_of_sight(path[i], path[j]):
                    farthest = j
                    break
            smoothed.append(path[farthest])
            i = farthest

        return smoothed

    def _line_of_sight(self, p0: tuple, p1: tuple) -> bool:
        """Bresenham 检查两点间是否有障碍（用 inflated_map）。"""
        x0, y0 = p0
        x1, y1 = p1
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            if self.inflated[y0, x0] == 1:
                return False
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return True

    # ==================== 工具方法 ====================

    def _heuristic(self, a: tuple, b: tuple) -> float:
        """Chebyshev 启发函数（8方向）。"""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return max(dx, dy) + (1.414 - 1) * min(dx, dy)

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.grid_w and 0 <= y < self.grid_h

    def _reconstruct(self, parent: dict, start: tuple, end: tuple) -> List[tuple]:
        """从 parent 字典回溯路径。"""
        path = [end]
        cur = end
        while cur != start:
            cur = parent.get(cur)
            if cur is None:
                return [start, end]  # 回溯失败，返回直线
            path.append(cur)
        path.reverse()
        return path

    def _cache_key(self, start: tuple, goal: tuple) -> tuple:
        """量化到 3 格精度的缓存 key。"""
        return (start[0] // 3, start[1] // 3, goal[0] // 3, goal[1] // 3)

    def _put_cache(self, key: tuple, path: list):
        """存入缓存，超限时淘汰最旧的。"""
        if key in self._cache:
            return
        self._cache[key] = path
        self._cache_order.append(key)
        while len(self._cache_order) > PATH_CACHE_SIZE:
            old_key = self._cache_order.pop(0)
            self._cache.pop(old_key, None)
