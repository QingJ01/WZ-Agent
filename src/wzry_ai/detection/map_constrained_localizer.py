"""
地图约束定位器 - 用地图知识滤波原始 YOLO 定位结果

功能：
  1. 障碍拒绝：落在障碍内的观测 snap 到最近可走格
  2. 运动先验：根据按键预测位移，与观测混合
  3. 走廊吸附：如有活跃路径，向走廊偏移
  4. 置信度评分：异常跳跃/障碍附近/丢帧时降权
"""

import logging
from math import sqrt

from wzry_ai.config.base import CELL_SIZE
from wzry_ai.config.keys import (
    KEY_MOVE_UP,
    KEY_MOVE_DOWN,
    KEY_MOVE_LEFT,
    KEY_MOVE_RIGHT,
)
from wzry_ai.detection.map_preprocessor import MapLayers

logger = logging.getLogger(__name__)

# 英雄在小地图上的估计速度（像素/秒）
_HERO_MINIMAP_SPEED = 80.0 #存疑

# 按键到方向向量的映射（小地图像素坐标系，Y 向下为正）
_KEY_VELOCITY = {
    KEY_MOVE_UP: (0, -1),
    KEY_MOVE_DOWN: (0, 1),
    KEY_MOVE_LEFT: (-1, 0),
    KEY_MOVE_RIGHT: (1, 0),
}


class MapConstrainedLocalizer:
    """
    包裹 model1_detector 的原始 g_center，输出经过地图约束的滤波位置。

    用法：
        localizer = MapConstrainedLocalizer.get()
        localizer.update_keys(movement.key_status)
        filtered_x, filtered_y, confidence = localizer.filter(raw_g_center, time.time())
    """

    _instance = None

    def __init__(self):
        self.map = MapLayers.get()
        self.last_filtered_pos = None
        self.last_timestamp = None
        self.confidence = 1.0
        self.frames_since_detection = 0
        self._active_keys = {}  # {key: bool}
        self._active_path = None  # 当前活跃路径 [(gx, gy), ...]

    @classmethod
    def get(cls) -> "MapConstrainedLocalizer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def update_keys(self, key_status: dict):
        """跟踪当前按下的 WASD 键，用于运动预测。"""
        self._active_keys = dict(key_status)

    def set_active_path(self, path):
        """设置当前活跃路径，用于走廊吸附。"""
        self._active_path = path

    def filter(self, raw_g_center: tuple, timestamp: float) -> tuple:
        """
        主滤波管线。

        参数：
            raw_g_center: (x, y) 小地图像素坐标
            timestamp: 当前时间戳

        返回：
            (filtered_x, filtered_y, confidence)
        """
        if raw_g_center is None:
            self.frames_since_detection += 1
            if self.last_filtered_pos is not None and self.frames_since_detection < 10:
                # 用运动先验外推
                dt = timestamp - self.last_timestamp if self.last_timestamp else 0.033
                pred = self._predict_position(dt)
                if pred:
                    self.last_filtered_pos = pred
                    self.last_timestamp = timestamp
                    self.confidence = max(0.1, self.confidence * 0.85)
                    return (pred[0], pred[1], self.confidence)
            return (None, None, 0.0)

        self.frames_since_detection = 0
        obs_x, obs_y = float(raw_g_center[0]), float(raw_g_center[1])

        # 1. 障碍拒绝 + snap
        gx = int(obs_x / CELL_SIZE)
        gy = int(obs_y / CELL_SIZE)
        if not self.map.is_walkable(gx, gy):
            snapped = self.map.snap_to_walkable(gx, gy)
            obs_x = snapped[0] * CELL_SIZE + CELL_SIZE / 2
            obs_y = snapped[1] * CELL_SIZE + CELL_SIZE / 2

        # 2. 运动先验混合
        dt = timestamp - self.last_timestamp if self.last_timestamp else 0.033
        pred = self._predict_position(dt)

        if pred and self.last_filtered_pos:
            jump_dist = sqrt((obs_x - pred[0]) ** 2 + (obs_y - pred[1]) ** 2)

            # 根据跳跃距离决定混合权重
            if jump_dist < 8:
                alpha = 0.85  # 观测和预测接近，信任观测
            elif jump_dist < 20:
                alpha = 0.6  # 中等跳跃，混合
            else:
                alpha = 0.4  # 大跳跃，更信预测

            filtered_x = alpha * obs_x + (1 - alpha) * pred[0]
            filtered_y = alpha * obs_y + (1 - alpha) * pred[1]
        else:
            filtered_x, filtered_y = obs_x, obs_y

        # 3. 走廊吸附
        if self._active_path and len(self._active_path) >= 2:
            filtered_x, filtered_y = self._corridor_snap(
                filtered_x, filtered_y, weight=0.3
            )

        # 4. 最终障碍检查（确保滤波后仍在可走区）
        fgx = int(filtered_x / CELL_SIZE)
        fgy = int(filtered_y / CELL_SIZE)
        if not self.map.is_walkable(fgx, fgy):
            snapped = self.map.snap_to_walkable(fgx, fgy)
            filtered_x = snapped[0] * CELL_SIZE + CELL_SIZE / 2
            filtered_y = snapped[1] * CELL_SIZE + CELL_SIZE / 2

        # 5. 置信度评分
        self.confidence = self._compute_confidence(obs_x, obs_y, filtered_x, filtered_y)

        self.last_filtered_pos = (filtered_x, filtered_y)
        self.last_timestamp = timestamp
        return (filtered_x, filtered_y, self.confidence)

    def _predict_position(self, dt: float):
        """根据上一位置 + 按键方向预测当前位置。"""
        if self.last_filtered_pos is None:
            return None

        vx, vy = 0.0, 0.0
        for key, direction in _KEY_VELOCITY.items():
            if self._active_keys.get(key, False):
                vx += direction[0]
                vy += direction[1]

        # 归一化
        mag = sqrt(vx * vx + vy * vy)
        if mag > 0:
            vx = vx / mag * _HERO_MINIMAP_SPEED
            vy = vy / mag * _HERO_MINIMAP_SPEED

        pred_x = self.last_filtered_pos[0] + vx * dt
        pred_y = self.last_filtered_pos[1] + vy * dt
        return (pred_x, pred_y)

    def _corridor_snap(self, x: float, y: float, weight: float = 0.3) -> tuple:
        """向活跃路径最近点偏移。"""
        if not self._active_path:
            return (x, y)

        gx = x / CELL_SIZE
        gy = y / CELL_SIZE
        best_dist = float("inf")
        best_px, best_py = gx, gy

        # 只检查路径上附近的点（性能优化）
        for px, py in self._active_path:
            d = (gx - px) ** 2 + (gy - py) ** 2
            if d < best_dist:
                best_dist = d
                best_px, best_py = px, py

        if best_dist < 25:  # 5格以内才吸附
            snap_x = best_px * CELL_SIZE + CELL_SIZE / 2
            snap_y = best_py * CELL_SIZE + CELL_SIZE / 2
            return (
                x * (1 - weight) + snap_x * weight,
                y * (1 - weight) + snap_y * weight,
            )
        return (x, y)

    def _compute_confidence(self, obs_x, obs_y, filt_x, filt_y) -> float:
        """计算当前定位置信度。"""
        conf = 1.0

        # 观测与滤波结果的偏差
        deviation = sqrt((obs_x - filt_x) ** 2 + (obs_y - filt_y) ** 2)
        if deviation > 15:
            conf *= 0.5
        elif deviation > 8:
            conf *= 0.75

        # clearance 低 = 靠近障碍
        gx = int(filt_x / CELL_SIZE)
        gy = int(filt_y / CELL_SIZE)
        clearance = self.map.get_clearance(gx, gy)
        if clearance < 2:
            conf *= 0.6
        elif clearance < 4:
            conf *= 0.8

        # 连续丢帧惩罚
        if self.frames_since_detection > 0:
            conf *= max(0.3, 1.0 - self.frames_since_detection * 0.15)

        return max(0.1, conf)
