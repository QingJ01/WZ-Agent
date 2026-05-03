"""
地图预处理模块 - 从手绘地图生成多层导航数据

功能：
  1. 二值占据图 - 障碍/可走区域
  2. 膨胀障碍图 - 按英雄半径膨胀
  3. 距离场(Clearance Map) - 每格到最近障碍的距离
  4. 骨架/走廊图 - 稀疏导航图

用法：
  python -m wzry_ai.detection.map_preprocessor
"""

import numpy as np
import cv2
import logging
import os
from math import sqrt
from collections import deque

logger = logging.getLogger(__name__)

# ==================== 地图生成函数 ====================


def generate_binary_grid(image_path: str, grid_size: int = 210) -> np.ndarray:
    """
    从手绘地图 PNG 生成二值占据图。

    参数：
        image_path: 手绘地图图片路径
        grid_size: 输出网格大小（默认210x210）

    返回：
        (grid_size, grid_size) uint8 数组，1=障碍，0=可走
    """
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"无法加载地图图片: {image_path}")

    # 转灰度
    if len(img.shape) == 3:
        if img.shape[2] == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # 缩放到目标尺寸
    resized = cv2.resize(gray, (grid_size, grid_size), interpolation=cv2.INTER_AREA)

    # 阈值化：暗像素 = 障碍(1)，亮像素 = 可走(0)
    _, binary = cv2.threshold(resized, 128, 1, cv2.THRESH_BINARY_INV)
    binary = binary.astype(np.uint8)

    # 强制边界为障碍（匹配现有 map_grid.txt 惯例：前6行/列和后6行/列）
    border = 6
    binary[:border, :] = 1
    binary[-border:, :] = 1
    binary[:, :border] = 1
    binary[:, -border:] = 1

    return binary


def generate_inflated_map(
    binary_grid: np.ndarray, inflation_radius: int = 4
) -> np.ndarray:
    """
    膨胀障碍图 - 按英雄半径+安全边距膨胀障碍物。

    参数：
        binary_grid: (N,N) 二值占据图
        inflation_radius: 膨胀半径（网格单元），4格 ≈ 6.7小地图像素

    返回：
        (N,N) uint8，1=膨胀后障碍，0=安全可走
    """
    kernel_size = 2 * inflation_radius + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    inflated = cv2.dilate(binary_grid, kernel, iterations=1)
    return inflated.astype(np.uint8)


def generate_clearance_map(binary_grid: np.ndarray) -> np.ndarray:
    """
    距离场 - 每个可走格到最近障碍的欧氏距离。

    参数：
        binary_grid: (N,N) 二值占据图，1=障碍，0=可走

    返回：
        (N,N) float32，障碍格=0，可走格=到最近障碍的距离
    """
    walkable = (1 - binary_grid).astype(np.uint8)
    clearance = cv2.distanceTransform(walkable, cv2.DIST_L2, 5)
    return clearance.astype(np.float32)


# ==================== 骨架提取 ====================


def _zhang_suen_thinning(binary_mask: np.ndarray) -> np.ndarray:
    """
    Zhang-Suen 形态学细化算法（纯 numpy 实现）。
    输入：uint8 二值图，前景=1，背景=0
    输出：细化后的骨架，前景=1，背景=0
    """
    skeleton = binary_mask.copy()
    rows, cols = skeleton.shape

    def _neighbors(img, r, c):
        """按 Zhang-Suen 顺序返回 8 邻域: P2,P3,...,P9"""
        return [
            img[r - 1, c],
            img[r - 1, c + 1],
            img[r, c + 1],
            img[r + 1, c + 1],
            img[r + 1, c],
            img[r + 1, c - 1],
            img[r, c - 1],
            img[r - 1, c - 1],
        ]

    def _transitions(neighbors):
        """计算 0→1 跳变次数"""
        n = neighbors + [neighbors[0]]
        return sum(1 for i in range(len(neighbors)) if n[i] == 0 and n[i + 1] == 1)

    changed = True
    while changed:
        changed = False
        for step in (1, 2):
            markers = []
            for r in range(1, rows - 1):
                for c in range(1, cols - 1):
                    if skeleton[r, c] != 1:
                        continue
                    nb = _neighbors(skeleton, r, c)
                    s = sum(nb)
                    t = _transitions(nb)
                    if s < 2 or s > 6:
                        continue
                    if t != 1:
                        continue
                    if step == 1:
                        if nb[0] * nb[2] * nb[4] != 0:
                            continue
                        if nb[2] * nb[4] * nb[6] != 0:
                            continue
                    else:
                        if nb[0] * nb[2] * nb[6] != 0:
                            continue
                        if nb[0] * nb[4] * nb[6] != 0:
                            continue
                    markers.append((r, c))
            for r, c in markers:
                skeleton[r, c] = 0
                changed = True

    return skeleton


def _thin_skeleton(binary_mask: np.ndarray) -> np.ndarray:
    """提取骨架，优先用 cv2.ximgproc，回退到 Zhang-Suen。"""
    ximgproc = getattr(cv2, "ximgproc", None)
    if ximgproc is not None:
        thinning = getattr(ximgproc, "thinning", None)
        thinning_type = getattr(ximgproc, "THINNING_ZHANGSUEN", None)
        if thinning is not None and thinning_type is not None:
            return thinning(binary_mask * 255, thinningType=thinning_type) // 255
    return _zhang_suen_thinning(binary_mask)


def generate_skeleton_graph(
    clearance_map: np.ndarray, min_clearance: float = 3.0
) -> dict:
    """
    从 clearance map 提取骨架走廊图。

    参数：
        clearance_map: (N,N) float32 距离场
        min_clearance: 最小间距阈值，低于此值的区域不参与骨架

    返回：
        dict:
            'skeleton_mask': (N,N) uint8, 1=骨架像素
            'nodes': [(x,y), ...] 节点列表（交叉点和端点）
            'edges': [(i, j, cost), ...] 边列表
            'adjacency': {node_idx: [(neighbor_idx, cost), ...]}
    """
    # 阈值化：只保留 clearance 足够大的区域
    wide_area = (clearance_map >= min_clearance).astype(np.uint8)

    # 如果宽区域太少，降低阈值重试
    if np.sum(wide_area) < 100:
        wide_area = (clearance_map >= 1.5).astype(np.uint8)

    # 形态学细化提取骨架
    skeleton = _thin_skeleton(wide_area)
    rows, cols = skeleton.shape

    # 识别节点：交叉点（>=3 骨架邻居）和端点（==1 骨架邻居）
    nodes = []
    node_map = {}  # (y, x) -> node_index

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if skeleton[r, c] != 1:
                continue
            # 计算 8 邻域中骨架像素数
            nb_count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    if skeleton[r + dr, c + dc] == 1:
                        nb_count += 1
            # 交叉点或端点
            if nb_count >= 3 or nb_count == 1:
                node_idx = len(nodes)
                nodes.append((c, r))  # (x, y) 格式
                node_map[(r, c)] = node_idx

    # 如果节点太少，把骨架上每隔 N 像素的点也加为节点
    if len(nodes) < 5:
        spacing = 15
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                if skeleton[r, c] == 1 and (r, c) not in node_map:
                    if r % spacing == 0 or c % spacing == 0:
                        node_idx = len(nodes)
                        nodes.append((c, r))
                        node_map[(r, c)] = node_idx

    # BFS 沿骨架追踪边：从每个节点出发，沿骨架走到下一个节点
    edges = []
    edge_set = set()  # 避免重复边
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for start_idx, (sx, sy) in enumerate(nodes):
        sr, sc = sy, sx  # 转回 (row, col)
        for dr, dc in directions:
            nr, nc = sr + dr, sc + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if skeleton[nr, nc] != 1:
                continue
            if (nr, nc) in node_map and node_map[(nr, nc)] != start_idx:
                # 直接相邻的节点
                end_idx = node_map[(nr, nc)]
                edge_key = (min(start_idx, end_idx), max(start_idx, end_idx))
                if edge_key not in edge_set:
                    cost = sqrt(
                        (sx - nodes[end_idx][0]) ** 2 + (sy - nodes[end_idx][1]) ** 2
                    )
                    edges.append((start_idx, end_idx, cost))
                    edge_set.add(edge_key)
                continue

            # BFS 沿骨架追踪
            visited = {(sr, sc)}
            queue = deque([(nr, nc, 1.414 if (dr != 0 and dc != 0) else 1.0)])
            visited.add((nr, nc))
            found_end = None

            while queue:
                cr, cc, dist = queue.popleft()
                if (cr, cc) in node_map and node_map[(cr, cc)] != start_idx:
                    found_end = (node_map[(cr, cc)], dist)
                    break
                if dist > 100:  # 防止无限追踪
                    break
                for ddr, ddc in directions:
                    nnr, nnc = cr + ddr, cc + ddc
                    if nnr < 0 or nnr >= rows or nnc < 0 or nnc >= cols:
                        continue
                    if (nnr, nnc) in visited:
                        continue
                    if skeleton[nnr, nnc] != 1:
                        continue
                    step = 1.414 if (ddr != 0 and ddc != 0) else 1.0
                    visited.add((nnr, nnc))
                    queue.append((nnr, nnc, dist + step))

            if found_end:
                end_idx, cost = found_end
                edge_key = (min(start_idx, end_idx), max(start_idx, end_idx))
                if edge_key not in edge_set:
                    edges.append((start_idx, end_idx, cost))
                    edge_set.add(edge_key)

    # 构建邻接表
    adjacency = {i: [] for i in range(len(nodes))}
    for i, j, cost in edges:
        adjacency[i].append((j, cost))
        adjacency[j].append((i, cost))

    logger.info(f"骨架图: {len(nodes)} 节点, {len(edges)} 边")
    return {
        "skeleton_mask": skeleton,
        "nodes": nodes,
        "edges": edges,
        "adjacency": adjacency,
    }


# ==================== 运行时加载器 ====================


class MapLayers:
    """
    单例，首次访问时从 data/ 加载所有预处理地图层。
    如果 .npy 文件不存在，回退到 map_grid.txt 并实时生成其余层。
    """

    _instance = None

    def __init__(self):
        self.binary_grid: np.ndarray | None = None  # (210,210) uint8
        self.inflated_map: np.ndarray | None = None  # (210,210) uint8
        self.clearance_map: np.ndarray | None = None  # (210,210) float32
        self.skeleton_mask: np.ndarray | None = None  # (210,210) uint8
        self.skeleton_nodes: list[tuple[int, int]] = []  # [(x,y), ...]
        self.skeleton_edges: list[tuple[int, int, float]] = []  # [(i, j, cost), ...]
        self.skeleton_adjacency: dict[
            int, list[tuple[int, float]]
        ] = {}  # {node_idx: [(neighbor_idx, cost), ...]}

    @classmethod
    def get(cls) -> "MapLayers":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        """从 data/ 加载预处理层，缺失时回退生成。"""
        from wzry_ai.utils.resource_resolver import resolve_data_path
        from wzry_ai.config.base import GRID_SIZE

        data_dir = os.path.dirname(str(resolve_data_path("map_grid.txt")))

        binary_path = os.path.join(data_dir, "map_binary_grid.npy")
        inflated_path = os.path.join(data_dir, "map_inflated.npy")
        clearance_path = os.path.join(data_dir, "map_clearance.npy")
        skeleton_path = os.path.join(data_dir, "map_skeleton_graph.npz")

        # 尝试加载预处理文件
        if os.path.exists(binary_path):
            self.binary_grid = np.load(binary_path)
            logger.info("已加载 map_binary_grid.npy")
        else:
            # 回退：从 map_grid.txt 加载
            grid_path = str(resolve_data_path("map_grid.txt"))
            if os.path.exists(grid_path):
                self.binary_grid = np.loadtxt(grid_path, dtype=np.uint8)
                logger.info("从 map_grid.txt 回退加载二值网格")
            else:
                self.binary_grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.uint8)
                logger.warning("无地图数据，使用空白网格")

        binary_grid = self.binary_grid
        if binary_grid is None:
            raise RuntimeError("二值网格加载失败")

        # 膨胀图
        if os.path.exists(inflated_path):
            self.inflated_map = np.load(inflated_path)
        else:
            from wzry_ai.config.base import HERO_INFLATION_RADIUS

            self.inflated_map = generate_inflated_map(
                binary_grid, HERO_INFLATION_RADIUS
            )
            logger.info("实时生成膨胀障碍图")

        # 距离场
        if os.path.exists(clearance_path):
            self.clearance_map = np.load(clearance_path)
        else:
            self.clearance_map = generate_clearance_map(binary_grid)
            logger.info("实时生成距离场")

        clearance_map = self.clearance_map
        if clearance_map is None:
            raise RuntimeError("距离场加载失败")

        # 骨架图
        if os.path.exists(skeleton_path):
            data = np.load(skeleton_path, allow_pickle=True)
            self.skeleton_mask = data["skeleton_mask"]
            self.skeleton_nodes = data["nodes"].tolist()
            self.skeleton_edges = data["edges"].tolist()
            self.skeleton_adjacency = data["adjacency"].item()
        else:
            from wzry_ai.config.base import SKELETON_MIN_CLEARANCE

            result = generate_skeleton_graph(clearance_map, SKELETON_MIN_CLEARANCE)
            self.skeleton_mask = result["skeleton_mask"]
            self.skeleton_nodes = result["nodes"]
            self.skeleton_edges = result["edges"]
            self.skeleton_adjacency = result["adjacency"]
            logger.info("实时生成骨架走廊图")

    def _require_navigation_maps(self) -> tuple[np.ndarray, np.ndarray]:
        """返回已加载的膨胀图和距离场。"""
        if self.inflated_map is None or self.clearance_map is None:
            raise RuntimeError("地图预处理层尚未加载完成")
        return self.inflated_map, self.clearance_map

    def is_walkable(self, gx: int, gy: int) -> bool:
        """检查膨胀图上该格是否可走。"""
        inflated_map, _ = self._require_navigation_maps()
        if 0 <= gy < inflated_map.shape[0] and 0 <= gx < inflated_map.shape[1]:
            return inflated_map[gy, gx] == 0
        return False

    def get_clearance(self, gx: int, gy: int) -> float:
        """获取该格到最近障碍的距离。"""
        _, clearance_map = self._require_navigation_maps()
        if 0 <= gy < clearance_map.shape[0] and 0 <= gx < clearance_map.shape[1]:
            return float(clearance_map[gy, gx])
        return 0.0

    def snap_to_walkable(self, gx: int, gy: int, max_radius: int = 10) -> tuple:
        """
        如果当前格在膨胀障碍内，BFS 找最近可走格。
        返回 (gx, gy)，找不到则返回原坐标。
        """
        if self.is_walkable(gx, gy):
            return (gx, gy)

        inflated_map, _ = self._require_navigation_maps()
        rows, cols = inflated_map.shape
        visited = set()
        queue = deque([(gx, gy, 0)])
        visited.add((gx, gy))

        while queue:
            cx, cy, dist = queue.popleft()
            if dist > max_radius:
                break
            if self.is_walkable(cx, cy):
                return (cx, cy)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= ny < rows and 0 <= nx < cols and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny, dist + 1))

        return (gx, gy)


# ==================== 预处理主入口 ====================


def preprocess_and_save(
    data_dir: str,
    image_path: str,
    grid_size: int = 210,
    inflation_radius: int | None = None,
    min_clearance: float | None = None,
):
    """运行完整预处理管线并保存到 data/ 目录。"""
    from wzry_ai.config.base import HERO_INFLATION_RADIUS, SKELETON_MIN_CLEARANCE

    if inflation_radius is None:
        inflation_radius = HERO_INFLATION_RADIUS
    if min_clearance is None:
        min_clearance = SKELETON_MIN_CLEARANCE

    logger.info(f"开始地图预处理: {image_path} (膨胀半径={inflation_radius})")

    # 1. 二值占据图
    binary = generate_binary_grid(image_path, grid_size)
    np.save(os.path.join(data_dir, "map_binary_grid.npy"), binary)
    logger.info(f"  二值图: 障碍率 {np.mean(binary) * 100:.1f}%")

    # 对比现有 map_grid.txt
    old_grid_path = os.path.join(data_dir, "map_grid.txt")
    if os.path.exists(old_grid_path):
        old_grid = np.loadtxt(old_grid_path, dtype=np.uint8)
        if old_grid.shape == binary.shape:
            match = np.sum(old_grid == binary)
            total = binary.size
            iou = match / total
            logger.info(f"  与 map_grid.txt 一致率: {iou * 100:.1f}%")

    # 2. 膨胀障碍图
    inflated = generate_inflated_map(binary, inflation_radius)
    np.save(os.path.join(data_dir, "map_inflated.npy"), inflated)
    logger.info(f"  膨胀图: 障碍率 {np.mean(inflated) * 100:.1f}%")

    # 3. 距离场
    clearance = generate_clearance_map(binary)
    np.save(os.path.join(data_dir, "map_clearance.npy"), clearance)
    logger.info(f"  距离场: 最大clearance {np.max(clearance):.1f}")

    # 4. 骨架走廊图
    skel = generate_skeleton_graph(clearance, min_clearance)
    np.savez(
        os.path.join(data_dir, "map_skeleton_graph.npz"),
        skeleton_mask=skel["skeleton_mask"],
        nodes=np.array(skel["nodes"], dtype=object),
        edges=np.array(skel["edges"], dtype=object),
        adjacency=skel["adjacency"],
    )

    logger.info("地图预处理完成，文件已保存到 data/")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from wzry_ai.utils.resource_resolver import resolve_data_path

    data_dir = os.path.dirname(str(resolve_data_path("map_grid.txt")))
    image_path = os.path.join(data_dir, "手绘地图.png")

    if not os.path.exists(image_path):
        logger.error(f"找不到手绘地图: {image_path}")
    else:
        preprocess_and_save(data_dir, image_path)
