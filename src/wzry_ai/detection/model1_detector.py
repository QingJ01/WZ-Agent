"""
模态1（小地图）YOLO 目标检测模块

功能：识别小地图上的英雄位置（自身/友方/敌方）
检测类别：
  - 绿色：自身（瑶）
  - 蓝色：友方英雄
  - 红色：敌方英雄
核心逻辑：
  1. 从共享帧容器获取小地图帧
  2. YOLO GPU 推理检测目标
  3. 分类并返回坐标信息
  4. 生成带中文标注的可视化图像
"""

import time
from pathlib import Path
from typing import Any

# 第三方库
import cv2
import numpy as np
from ultralytics.models import YOLO

# 本地模块
from wzry_ai.config import (
    CLASS_NAMES_FILE,
    DEFAULT_REGIONS,
    ENEMY_CLASS_ID_MIN,
    FPS,
    MODEL1_CONFIDENCE_THRESHOLD,
    MODEL1_WEIGHTS,
    SELF_CLASS_ID_RANGE,
    TEAM_CLASS_ID_RANGE,
)
from wzry_ai.utils.frame_manager import get_minimap_frame
from wzry_ai.config.heroes.mapping import get_hero_chinese
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.utils.utils import get_cuda_device, cv2_add_chinese_text

# 获取模块日志记录器
logger = get_logger(__name__)

# 日志输出控制，用于限制日志输出频率
_last_log_time = 0
LOG_INTERVAL = 3.0

# 上一帧的瑶位置（用于头像重叠时的预测）
_last_yao_position = None
_yao_lost_frames = 0
MAX_YAO_LOST_FRAMES = 30

# ===== 附身代理跟踪 =====
# 当瑶附身队友时，小地图上绿色图标被蓝色队友图标遮挡
# 此时锁定最近的队友轨迹，用队友位置代替自身位置
_attached_proxy_track_id = None  # 附身时锁定的队友轨迹ID（在 _team_tracker 中）
_proxy_lock_time = None  # 代理锁定的时间戳
PROXY_MATCH_DISTANCE = 50  # 附身匹配距离阈值（小地图像素）
PROXY_MAX_DURATION = 120.0  # 代理最长持续时间（秒），超时自动释放

# ===== 跳帧缓存 =====
_skip_frame_counter = 0  # 帧计数器
_skip_frame_interval = 2  # 每N帧推理一次（2=每2帧推理1次，跳1帧）
_cached_detect_result = None  # 缓存的检测结果


class MinimapTracker:
    """小地图英雄多帧跟踪器：位置平滑 + 遮挡容忍 + 超时清除"""

    def __init__(self, buffer_size=5, timeout=1.5, match_distance=30):
        self.buffer_size = buffer_size  # 历史帧数
        self.timeout = timeout  # 消失超时（秒）
        self.match_distance = match_distance  # 匹配距离阈值（像素）
        self.tracks = {}  # track_id -> {positions: [(x,y,t),...], class_id, last_seen}
        self.next_id = 0

    def update(self, detections, current_time):
        """
        输入: detections = [(x, y, class_id), ...]
        输出: smoothed_detections = [(x, y, class_id), ...]
        """
        # 如果没有历史轨迹，直接返回当前检测
        if not self.tracks:
            for det in detections:
                x, y, class_id = det
                self._create_track(x, y, class_id, current_time)
            return [(x, y, class_id) for (x, y, class_id) in detections]

        # 1. 将新检测与现有轨迹匹配（欧氏距离 + 同class_id优先）
        matched_tracks = set()
        matched_dets = set()
        matches = []  # (track_id, det_idx, distance)

        for track_id, track in self.tracks.items():
            last_pos = track["positions"][-1]
            tx, ty = last_pos[0], last_pos[1]
            for det_idx, det in enumerate(detections):
                if det_idx in matched_dets:
                    continue
                x, y, class_id = det
                # 同class_id优先
                if class_id == track["class_id"]:
                    dist = np.sqrt((x - tx) ** 2 + (y - ty) ** 2)
                    if dist < self.match_distance:
                        matches.append((track_id, det_idx, dist))

        # 按距离排序，优先匹配最近的
        matches.sort(key=lambda x: x[2])

        final_matches = {}  # track_id -> det_idx
        for track_id, det_idx, dist in matches:
            if track_id not in matched_tracks and det_idx not in matched_dets:
                final_matches[track_id] = det_idx
                matched_tracks.add(track_id)
                matched_dets.add(det_idx)

        # 2. 匹配成功：更新轨迹
        for track_id, det_idx in final_matches.items():
            x, y, class_id = detections[det_idx]
            self.tracks[track_id]["positions"].append((x, y, current_time))
            self.tracks[track_id]["last_seen"] = current_time
            # 限制历史缓冲大小
            if len(self.tracks[track_id]["positions"]) > self.buffer_size:
                self.tracks[track_id]["positions"].pop(0)

        # 3. 未匹配的检测：创建新轨迹
        for det_idx, det in enumerate(detections):
            if det_idx not in matched_dets:
                x, y, class_id = det
                self._create_track(x, y, class_id, current_time)

        # 4. 未匹配的轨迹：检查超时，移除超时的轨迹
        tracks_to_remove = []
        for track_id, track in self.tracks.items():
            if track_id not in matched_tracks:
                if current_time - track["last_seen"] > self.timeout:
                    tracks_to_remove.append(track_id)

        for track_id in tracks_to_remove:
            del self.tracks[track_id]

        # 5. 返回所有活跃轨迹的平滑位置
        result = []
        for track_id, track in self.tracks.items():
            smoothed_pos = self._smooth_position(track["positions"])
            if smoothed_pos is not None:
                result.append(
                    (int(smoothed_pos[0]), int(smoothed_pos[1]), track["class_id"])
                )

        return result

    def _create_track(self, x, y, class_id, current_time):
        """创建新轨迹"""
        track_id = self.next_id
        self.next_id += 1
        self.tracks[track_id] = {
            "positions": [(x, y, current_time)],
            "class_id": class_id,
            "last_seen": current_time,
        }

    def _smooth_position(self, positions):
        """时间加权平均位置（最新帧权重最高）"""
        if not positions:
            return None

        # 使用线性权重：最新=1.0, 最旧=0.2
        n = len(positions)
        if n == 1:
            return positions[0][0], positions[0][1]

        # 计算权重：线性递增，最旧为0.2，最新为1.0
        weights = []
        for i in range(n):
            # i=0 是最旧的，i=n-1 是最新的
            weight = 0.2 + (0.8 * i / (n - 1)) if n > 1 else 1.0
            weights.append(weight)

        total_weight = sum(weights)
        weighted_x = (
            sum(pos[0] * w for pos, w in zip(positions, weights)) / total_weight
        )
        weighted_y = (
            sum(pos[1] * w for pos, w in zip(positions, weights)) / total_weight
        )

        return weighted_x, weighted_y


# 模块级跟踪器实例（分别用于队友和敌人）
_team_tracker = MinimapTracker(buffer_size=5, timeout=1.5, match_distance=30)
_enemy_tracker = MinimapTracker(buffer_size=5, timeout=1.5, match_distance=30)
# 自身位置简单缓冲（替代 _last_yao_position）
_self_position_buffer = []

# 加载YOLO模型，自动检测CUDA可用性
model = YOLO(MODEL1_WEIGHTS)
device = get_cuda_device()
if device == "cuda":
    logger.info("CUDA 可用，使用 GPU 推理")
else:
    logger.info("CUDA 不可用，使用 CPU 推理")
model.to(device)

# 小地图截图区域配置
monitor = DEFAULT_REGIONS["minimap"]

# 窗口截图器由调用方传入，不再创建全局实例
window_capture = None

# 加载真实类别名称，从文件中读取英雄ID和名称的映射关系
try:
    with open(CLASS_NAMES_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()
        class_names = {}
        for line in lines:
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                parts = line.split(":", 1)
                try:
                    key = int(parts[0])
                    # 格式: ID: 变量名 | 中文名 | 类型
                    value_parts = parts[1].split("|")
                    # 使用中文名（第二部分）作为显示名称
                    if len(value_parts) >= 2:
                        class_names[key] = value_parts[1].strip()
                    else:
                        class_names[key] = value_parts[0].strip()
                except (ValueError, IndexError):
                    continue
except FileNotFoundError:
    class_names = {}

# 使用配置的置信度阈值
confidence_threshold = MODEL1_CONFIDENCE_THRESHOLD


def _to_numpy_array(value: object) -> np.ndarray[Any, Any]:
    """将 YOLO 返回值统一收窄为 numpy 数组。"""
    if isinstance(value, np.ndarray):
        return value

    cpu_method = getattr(value, "cpu", None)
    if callable(cpu_method):
        value = cpu_method()

    numpy_method = getattr(value, "numpy", None)
    if callable(numpy_method):
        numpy_value = numpy_method()
        if isinstance(numpy_value, np.ndarray):
            return numpy_value
        return np.asarray(numpy_value)

    return np.asarray(value)


def _to_int_list(value: object) -> list[int]:
    """将 YOLO 类别结果统一收窄为 Python 整数列表。"""
    int_method = getattr(value, "int", None)
    if callable(int_method):
        value = int_method()
    array = _to_numpy_array(value)
    return np.asarray(array, dtype=np.int64).reshape(-1).tolist()


def get_color(class_id):
    """
    根据类别ID获取对应的颜色

    功能说明：
        根据 name_with_chinese.txt 的颜色规则返回对应的颜色：
        - 258-386: 绿色（自身）
        - 129-257: 蓝色（队友）
        - 0-128: 红色（敌人）

    参数说明：
        class_id: 整数，类别ID

    返回值说明：
        元组 (B, G, R)，OpenCV 格式的颜色值
    """
    if 258 <= class_id <= 386:
        return (0, 255, 0)
    elif 129 <= class_id <= 257:
        return (255, 0, 0)
    else:
        return (0, 0, 255)


def detect(sct=None, frame=None, visualize=True):
    """
    捕获屏幕指定区域并运行YOLO检测

    功能说明：
        对小地图区域进行 YOLO 目标检测，识别自身（瑶）、友方和敌方英雄的位置
        支持从共享帧容器读取或直接传入帧数据

    参数说明：
        sct: WindowCapture 实例（用于截图，如果 frame 为 None）
        frame: numpy 数组，直接传入的截图，如果提供则不再截图
        visualize: bool，是否生成可视化标注图像，默认True，设为False可提升性能

    返回值说明：
        dict: 检测结果字典，包含以下键：
            - g_center: 元组 (x, y) 或 None，自身（绿色瑶）的位置坐标
            - b_centers: 列表 [(x, y, class_id), ...]，友方英雄位置列表
            - r_centers: 列表 [(x, y, class_id), ...]，敌方英雄位置列表
            - annotated_frame: numpy 数组，带标注的可视化图像
            - class_names: 字典，类别ID到名称的映射
            - frame: numpy 数组，返回的图像供主线程显示
    """
    global \
        _last_yao_position, \
        _yao_lost_frames, \
        _team_tracker, \
        _enemy_tracker, \
        _self_position_buffer
    global _attached_proxy_track_id, _proxy_lock_time

    # 如果没有直接传入 frame，则从共享帧容器读取
    if frame is None:
        frame = get_minimap_frame(copy=True)
        if frame is None:
            capture = sct if sct is not None else window_capture
            if capture is None:
                logger.error("截图器未初始化")
                return {
                    "g_center": None,
                    "b_centers": [],
                    "r_centers": [],
                    "annotated_frame": np.zeros((300, 300, 3), dtype=np.uint8),
                    "class_names": class_names,
                }
            try:
                frame = capture.capture(monitor)
                frame = frame.copy()
            except (OSError, AttributeError, RuntimeError) as e:
                logger.error(f"截图失败: {e}")
                return {
                    "g_center": None,
                    "b_centers": [],
                    "r_centers": [],
                    "annotated_frame": np.zeros((300, 300, 3), dtype=np.uint8),
                    "class_names": class_names,
                }

    # 保存原始帧尺寸用于结果映射
    original_h, original_w = frame.shape[:2]

    # 跳帧机制：非推理帧直接复用上次结果，减少GPU开销
    global _skip_frame_counter, _cached_detect_result
    _skip_frame_counter += 1
    if (
        _cached_detect_result is not None
        and _skip_frame_counter % _skip_frame_interval != 0
    ):
        # 非推理帧：复用缓存结果，但更新可视化帧
        cached = _cached_detect_result.copy()
        cached["annotated_frame"] = frame.copy() if visualize else None
        cached["frame"] = frame
        return cached

    # 直接传原始帧给 YOLO，让 ultralytics 内部做 letterbox 保持宽高比
    results = model.predict(frame, conf=confidence_threshold, imgsz=384, verbose=False)

    # 坐标直接对应原始帧，scale 为 1
    scale_x = 1.0
    scale_y = 1.0

    g_center = None
    self_class_id = None  # 保存自身英雄的 class_id
    b_centers = []
    r_centers = []

    # 只在需要可视化时才复制帧进行绘制
    annotated_frame = frame.copy() if visualize else None

    current_time = time.time()
    global _last_log_time
    should_log = current_time - _last_log_time >= LOG_INTERVAL

    first_result = results[0] if results else None
    result_boxes = first_result.boxes if first_result is not None else None
    if result_boxes is not None and len(result_boxes) > 0:
        boxes = _to_numpy_array(result_boxes.xywh)
        class_ids = _to_int_list(result_boxes.cls)
        confidences = _to_numpy_array(result_boxes.conf).reshape(-1)

        detected_info = []

        # 第一遍：收集所有检测结果
        detections = []
        for i, box in enumerate(boxes):
            class_id = class_ids[i]
            confidence = confidences[i]
            # 将坐标从缩小后的图像映射回原始图像尺寸
            x, y, w, h = box
            x = x * scale_x
            y = y * scale_y
            w = w * scale_x
            h = h * scale_y

            # 获取类别名称
            class_name = class_names.get(class_id, f"{class_id}")

            # 只在需要可视化时才绘制检测框和标签
            if visualize and annotated_frame is not None:
                box_color = get_color(class_id)
                cv2.rectangle(
                    annotated_frame,
                    (int(x - w / 2), int(y - h / 2)),
                    (int(x + w / 2), int(y + h / 2)),
                    box_color,
                    2,
                )
                label = f"{class_name} {confidence:.2f}"
                annotated_frame = cv2_add_chinese_text(
                    annotated_frame, label, (int(x - w / 2), int(y - h / 2 - 30))
                )

            # 收集检测信息用于后续分类
            if confidence > confidence_threshold:
                detected_info.append(
                    {
                        "name": class_name,
                        "class_id": class_id,
                        "x": int(x),
                        "y": int(y),
                        "conf": confidence,
                    }
                )

                # 保存用于分类的标记
                class_name_lower = class_name.lower()
                is_yao = "yao" in class_name_lower or "瑶" in class_name
                is_green = SELF_CLASS_ID_RANGE[0] <= class_id <= SELF_CLASS_ID_RANGE[1]
                detections.append(
                    {
                        "x": x,
                        "y": y,
                        "class_id": class_id,
                        "class_name": class_name,
                        "is_yao": is_yao,
                        "is_green": is_green,
                    }
                )

        # 第二遍：优先处理瑶的检测（绿色瑶优先）
        for d in detections:
            if d["is_yao"] and d["is_green"]:
                # 绿色瑶 = 自己（最高优先级）
                g_center = (d["x"], d["y"])
                self_class_id = d["class_id"]  # 保存自身的 class_id
                break

        # 第三遍：处理其他检测
        for d in detections:
            if d["is_yao"] and d["is_green"]:
                continue
            elif d["is_yao"]:
                # 瑶但不是绿色 = 敌人（对面的瑶）
                r_centers.append((d["x"], d["y"], d["class_id"]))
            elif d["is_green"]:
                # 绿色但不是瑶 = 其他英雄的绿色标记（不应该出现）
                if g_center is None:
                    g_center = (d["x"], d["y"])
                    self_class_id = d["class_id"]  # 保存自身的 class_id
            elif TEAM_CLASS_ID_RANGE[0] <= d["class_id"] <= TEAM_CLASS_ID_RANGE[1]:
                b_centers.append((d["x"], d["y"], d["class_id"]))
            elif d["class_id"] >= ENEMY_CLASS_ID_MIN:
                r_centers.append((d["x"], d["y"], d["class_id"]))

        # 如果还是没找到瑶，尝试使用上一帧的位置（头像重叠时）
        if (
            g_center is None
            and _last_yao_position is not None
            and _yao_lost_frames < MAX_YAO_LOST_FRAMES
        ):
            g_center = _last_yao_position
            _yao_lost_frames += 1

        # [已删除] 原兜底逻辑：随便选第一个高置信度目标
        # 该逻辑可能把敌人或队友位置当作自身位置，导致严重错误

        # 更新瑶的位置记录
        if g_center is not None:
            _last_yao_position = g_center
            _yao_lost_frames = 0

        # 每秒输出一次检测日志
        if should_log and detected_info:
            _last_log_time = current_time
            log_msg = f"检测到 {len(detected_info)} 个目标:"
            for info in detected_info:
                # 将拼音名称转换为中文
                display_name = get_hero_chinese(info["name"])
                log_msg += (
                    f" [{display_name}]({info['x']},{info['y']})置信{info['conf']:.2f}"
                )
            logger.info(log_msg)

    # === 多帧时序平滑处理 ===
    current_time = time.time()

    # 1. 自身位置平滑（使用简单缓冲）
    if g_center is not None:
        _self_position_buffer.append((g_center[0], g_center[1], current_time))
        # 限制缓冲大小为5帧
        if len(_self_position_buffer) > 5:
            _self_position_buffer.pop(0)
        # 计算平滑位置（时间加权平均）
        if len(_self_position_buffer) > 0:
            n = len(_self_position_buffer)
            weights = [0.2 + (0.8 * i / (n - 1)) if n > 1 else 1.0 for i in range(n)]
            total_weight = sum(weights)
            smoothed_x = (
                sum(pos[0] * w for pos, w in zip(_self_position_buffer, weights))
                / total_weight
            )
            smoothed_y = (
                sum(pos[1] * w for pos, w in zip(_self_position_buffer, weights))
                / total_weight
            )
            g_center = (int(smoothed_x), int(smoothed_y))
    else:
        # 如果当前未检测到自身，检查缓冲中是否有未超时的位置
        if _self_position_buffer:
            last_time = _self_position_buffer[-1][2]
            if current_time - last_time <= 1.5:  # 1.5秒超时
                last_pos = _self_position_buffer[-1]
                g_center = (int(last_pos[0]), int(last_pos[1]))
            else:
                # 超时清空缓冲
                _self_position_buffer.clear()

    # 2. 队友位置平滑
    b_centers_smoothed = _team_tracker.update(b_centers, current_time)

    # 3. 敌人位置平滑
    r_centers_smoothed = _enemy_tracker.update(r_centers, current_time)

    # 合并输出跟踪日志（只在 should_log 为 True 时输出）
    if should_log and (
        len(b_centers_smoothed) != len(b_centers)
        or len(r_centers_smoothed) != len(r_centers)
    ):
        logger.debug(
            f"多帧平滑: 队友 {len(b_centers)}->{len(b_centers_smoothed)}, 敌人 {len(r_centers)}->{len(r_centers_smoothed)}"
        )

    b_centers = b_centers_smoothed
    r_centers = r_centers_smoothed

    # ===== 4. 附身代理跟踪 =====
    # 当瑶附身队友时，绿色图标被蓝色图标遮挡，g_center 持续为 None
    # 此时锁定消失点附近的队友轨迹，用队友位置代替自身位置
    if g_center is None and _last_yao_position is not None:
        # --- 尝试锁定附身队友 ---
        if _attached_proxy_track_id is None:
            # 首次丢失 g_center，在队友轨迹中寻找最近的
            min_dist = float("inf")
            best_track_id = None
            for track_id, track in _team_tracker.tracks.items():
                # 取该队友最新位置
                last_pos = track["positions"][-1]
                tx, ty = last_pos[0], last_pos[1]
                dist = np.sqrt(
                    (tx - _last_yao_position[0]) ** 2
                    + (ty - _last_yao_position[1]) ** 2
                )
                if dist < min_dist and dist < PROXY_MATCH_DISTANCE:
                    min_dist = dist
                    best_track_id = track_id

            if best_track_id is not None:
                _attached_proxy_track_id = best_track_id
                _proxy_lock_time = current_time
                logger.info(
                    f"[附身代理] 锁定队友轨迹 {best_track_id}，"
                    f"距消失点 {min_dist:.0f}px"
                )

        # --- 使用已锁定队友的位置作为 g_center ---
        if _attached_proxy_track_id is not None:
            if _attached_proxy_track_id in _team_tracker.tracks:
                track = _team_tracker.tracks[_attached_proxy_track_id]
                smoothed = _team_tracker._smooth_position(track["positions"])
                if smoothed is not None:
                    g_center = (int(smoothed[0]), int(smoothed[1]))
                    # 不更新 _last_yao_position，避免代理位置漂移影响重新检测
                    if should_log:
                        logger.debug(
                            f"[附身代理] 使用队友位置 ({g_center[0]},{g_center[1]})"
                        )
            else:
                # 队友轨迹已超时消失，释放代理
                logger.info(
                    f"[附身代理] 队友轨迹 {_attached_proxy_track_id} 已消失，释放代理"
                )
                _attached_proxy_track_id = None
                _proxy_lock_time = None

            # 超时保护：代理持续时间过长则释放（防止跟错人）
            if (
                _proxy_lock_time is not None
                and current_time - _proxy_lock_time > PROXY_MAX_DURATION
            ):
                logger.info(f"[附身代理] 超时 {PROXY_MAX_DURATION}秒，释放代理")
                _attached_proxy_track_id = None
                _proxy_lock_time = None

    elif g_center is not None and _attached_proxy_track_id is not None:
        # YOLO 重新检测到自身绿色图标 → 释放附身代理
        logger.info(f"[附身代理] 自身重新出现，释放队友轨迹锁定")
        _attached_proxy_track_id = None
        _proxy_lock_time = None

    # 如果不需要可视化，annotated_frame 为 None，返回原始帧作为占位
    display_frame = annotated_frame if annotated_frame is not None else frame

    result = {
        "g_center": g_center,
        "self_class_id": self_class_id,  # 返回自身 class_id
        "b_centers": b_centers,
        "r_centers": r_centers,
        "annotated_frame": display_frame,
        "class_names": class_names,
        "frame": display_frame,
    }
    _cached_detect_result = result
    return result


if __name__ == "__main__":
    """
    独立测试模式：使用 scrcpy 获取画面进行实时检测
    
    功能说明：
        当直接运行此文件时，启动独立测试模式
        通过 scrcpy 连接手机，实时显示小地图检测结果
    """
    logger.info("独立测试模式 - 使用 scrcpy")
    import scrcpy
    from wzry_ai.device.ScrcpyTool import ScrcpyTool

    scrcpy_tool = ScrcpyTool()
    latest_frame: list[np.ndarray[Any, Any] | None] = [None]

    def on_frame(frame):
        """
        帧回调函数 - 接收 scrcpy 传来的每一帧画面

        参数说明：
            frame: numpy 数组，表示一帧图像数据
        """
        if frame is not None:
            latest_frame[0] = frame

    scrcpy_tool.client.add_listener(scrcpy.EVENT_FRAME, on_frame)
    scrcpy_tool.client.start(threaded=True)
    time.sleep(2)

    logger.info("开始检测，按 'q' 退出")
    try:
        while True:
            if latest_frame[0] is not None:
                # 裁剪小地图区域
                mm = DEFAULT_REGIONS["minimap"]
                h, w = latest_frame[0].shape[:2]
                base_w, base_h = (
                    DEFAULT_REGIONS["full"]["width"],
                    DEFAULT_REGIONS["full"]["height"],
                )
                sx, sy = w / base_w, h / base_h
                mx, my = int(mm["left"] * sx), int(mm["top"] * sy)
                mw, mh = int(mm["width"] * sx), int(mm["height"] * sy)
                minimap = latest_frame[0][my : my + mh, mx : mx + mw]

                result = detect(frame=minimap)
                if result["annotated_frame"] is not None:
                    cv2.imshow("Model1 Detection", result["annotated_frame"])

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        logger.info("测试结束")
