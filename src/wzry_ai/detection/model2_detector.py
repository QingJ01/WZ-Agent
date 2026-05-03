"""
模态2（全屏）YOLO 血条检测模块

功能：识别游戏画面中的血条位置和血量
检测类别：
  - 绿色血条：自身
  - 蓝色血条：友方英雄
  - 红色血条：敌方英雄
核心逻辑：
  1. YOLO 检测血条位置
  2. OpenCV HSV 颜色空间计算血量百分比
  3. 生成带标注的可视化图像
"""

import time
from dataclasses import dataclass, field
from typing import Any

# 第三方库
import cv2
import numpy as np
from ultralytics.models import YOLO

# 本地模块
from wzry_ai.config import (
    DEFAULT_REGIONS,
    FPS,
    FRAME_TIME,
    MODEL2_CLASS_NAMES,
    MODEL2_CONFIDENCE_THRESHOLD,
    MODEL2_DISPLAY_SCALE,
    MODEL2_WEIGHTS,
    YOLO_CONF,
    YOLO_IOU,
)
from wzry_ai.utils.frame_manager import get_full_frame
from wzry_ai.utils.logging_utils import get_logger
from wzry_ai.utils.utils import get_cuda_device

# 获取模块日志记录器
logger = get_logger(__name__)

# 窗口缩放比例
scale = MODEL2_DISPLAY_SCALE


@dataclass
class _DetectorState:
    """模块级运行时状态，替代函数/类动态属性。"""

    last_health_cleanup_time: float = 0.0
    last_log_time: float = 0.0
    health_history: dict[str, int] = field(default_factory=dict)


_DETECTOR_STATE = _DetectorState()


def clear_entity_cache():
    """
    清除实体跟踪器缓存（在状态切换时调用）

    功能说明：
        在游戏状态切换时调用，清除历史跟踪数据，避免状态混淆
        注意：ByteTrack 跟踪状态由 ultralytics 自动管理，
        此函数现在主要用于清理血量历史记录

    参数说明：
        无参数

    返回值说明：
        无返回值
    """
    _DETECTOR_STATE.health_history.clear()
    logger.info("实体跟踪器缓存已清除")


# 加载 YOLOv8 模型，自动检测CUDA可用性
model = YOLO(MODEL2_WEIGHTS)
device = get_cuda_device()
if device == "cuda":
    logger.info("CUDA 可用，使用 GPU 推理")
else:
    logger.info("CUDA 不可用，使用 CPU 推理")
model.to(device)

# 定义常量
CONFIDENCE_THRESHOLD = MODEL2_CONFIDENCE_THRESHOLD

# 定义类别名称
class_names = MODEL2_CLASS_NAMES


# ByteTrack 已由 ultralytics 内置，无需自定义 EntityTracker
# 保留 clear_entity_cache 函数以兼容现有调用，但功能已简化


class HealthBar:
    """
    血条类 - 封装血条检测和血量计算的相关功能

    功能说明：
        用于检测不同类型血条（自身绿色、队友蓝色、敌人红色）
        通过 HSV 颜色空间分析计算血量百分比
    """

    def __init__(
        self,
        name,
        lower_hsv,
        upper_hsv,
        target_height,
        width_tolerance,
        height_tolerance,
        color,
        label,
    ):
        """
        初始化血条检测器

        功能说明：
            创建血条检测器实例，配置 HSV 颜色范围和检测参数

        参数说明：
            name: 字符串，血条名称
            lower_hsv: numpy 数组，HSV 颜色下限
            upper_hsv: numpy 数组，HSV 颜色上限
            target_height: 整数，目标血条高度
            width_tolerance: 整数，宽度容差
            height_tolerance: 整数，高度容差
            color: 元组 (B, G, R)，显示颜色
            label: 字符串，显示标签

        返回值说明：
            无返回值
        """
        self.name = name
        self.lower_hsv = lower_hsv
        self.upper_hsv = upper_hsv
        self.target_height = target_height
        self.width_tolerance = width_tolerance
        self.height_tolerance = height_tolerance
        self.color = color
        self.label = label

    def calculate_health_percentage(self, roi_hsv, detected_width, debug=False):
        """
        计算血量百分比

        功能说明：
            通过 HSV 颜色空间分析 ROI 区域，计算血条填充比例
            支持多个 HSV 范围（用于红色等跨越 hue 边界的颜色）

        参数说明：
            roi_hsv: numpy 数组，血条区域的 HSV 图像（由调用方预转换）
            detected_width: 整数，检测到的血条总宽度
            debug: 布尔值，是否输出调试信息

        返回值说明：
            整数，血量百分比（0-100），未检测到返回100
        """
        # 检查 ROI 是否有效（宽高必须大于0）
        if (
            roi_hsv is None
            or roi_hsv.size == 0
            or roi_hsv.shape[0] < 1
            or roi_hsv.shape[1] < 1
        ):
            if debug:
                logger.debug("[血量计算] ROI 无效，跳过")
            return 100

        hsv_img = roi_hsv

        # 生成颜色掩码（支持多 HSV 范围，用于红色 hue 跨越 0/180 的情况）
        if isinstance(self.lower_hsv, list):
            # 多范围模式：将多个范围的掩码合并（OR 操作）
            mask = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
            for lower, upper in zip(self.lower_hsv, self.upper_hsv):
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv_img, lower, upper))
        else:
            # 单范围模式：直接生成掩码
            mask = cv2.inRange(hsv_img, self.lower_hsv, self.upper_hsv)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 从所有符合高度条件的轮廓中，选择宽度最大的（最可靠）
        best_w = 0
        best_health = None
        for contour in contours:
            _, _, w, h = cv2.boundingRect(contour)
            if (
                self.target_height - self.height_tolerance
                <= h
                <= self.target_height + self.height_tolerance
            ):
                if w > best_w:
                    best_w = w
                    best_health = min(100, int((w / detected_width) * 100))

        if best_health is not None:
            if debug:
                logger.debug(
                    f"[血量计算] 最大匹配轮廓宽度:{best_w}px, 总宽度:{detected_width}px, 血量:{best_health}%"
                )
            # 95%~100% 视为满血，消除微小误差
            if 95 <= best_health <= 100:
                return 100
            return best_health

        if debug:
            logger.debug("[血量计算] 未找到符合条件的轮廓，返回100%")
        return 100

    def draw_health_bar(self, image, bbox, health_percentage, yolo_color, opencv_color):
        """
        在图像上绘制血条和血量信息

        功能说明：
            绘制 YOLO 检测框、血条填充情况和血量百分比文字

        参数说明：
            image: numpy 数组，要绘制的图像
            bbox: 元组 (x1, y1, x2, y2)，血条边界框坐标
            health_percentage: 整数，血量百分比
            yolo_color: 元组 (B, G, R)，YOLO 检测框颜色
            opencv_color: 元组 (B, G, R)，血量条颜色

        返回值说明：
            无返回值，直接修改输入图像
        """
        x1, y1, x2, y2 = bbox
        cv2.rectangle(image, (x1, y1), (x2, y2), yolo_color, 2)
        text = f"{self.label} (YOLOv8)"
        cv2.putText(
            image, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, yolo_color, 2
        )
        filled_width = int((x2 - x1) * health_percentage / 100)
        cv2.rectangle(image, (x1, y1), (x1 + filled_width, y2), opencv_color, 2)
        text = f"Health: {health_percentage}%"
        cv2.putText(
            image, text, (x1, y2 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, opencv_color, 2
        )


# 窗口截图器由调用方传入，不再创建全局实例
window_capture = None

# ================= 预定义血条检测器（模块级单例，避免每帧重建） =================
# 绿色血条：自身英雄
green_health_bar = HealthBar(
    name="Green Health Bar",
    lower_hsv=np.array([50, 120, 80]),  # 放宽饱和度和亮度下限，兼容暗场景
    upper_hsv=np.array([75, 255, 255]),  # 放宽色相上限，覆盖更多绿色调
    target_height=10,
    width_tolerance=5,
    height_tolerance=5,
    color=(0, 255, 0),
    label="Self",
)

# 蓝色血条：队友英雄
blue_health_bar = HealthBar(
    name="Blue Health Bar",
    lower_hsv=np.array([90, 80, 120]),  # 放宽饱和度和亮度下限
    upper_hsv=np.array([130, 255, 255]),  # 放宽色相上限
    target_height=13,
    width_tolerance=15,
    height_tolerance=8,
    color=(255, 0, 0),
    label="Team",
)

# 红色血条：敌方英雄
# 红色在 HSV 中 hue 值会绕过 0/180 边界，需要两段范围
red_health_bar = HealthBar(
    name="Red Health Bar",
    lower_hsv=[
        np.array([0, 40, 120]),
        np.array([170, 40, 120]),
    ],  # 两段：0~8 和 170~180
    upper_hsv=[
        np.array([8, 255, 255]),
        np.array([180, 255, 255]),
    ],  # 覆盖红色完整 hue 范围
    target_height=13,
    width_tolerance=5,
    height_tolerance=4,
    color=(0, 0, 255),
    label="Enemy",
)


def detect(sct=None, frame=None):
    """
    检测血条位置和血量

    功能说明：
        对游戏画面进行血条检测，识别自身、队友和敌人的血条位置和血量
        支持从共享帧容器读取或直接传入帧数据

    参数说明：
        sct: WindowCapture 实例（用于截图，如果 frame 为 None）
        frame: numpy 数组，直接传入的截图，如果提供则不再截图

    返回值说明：
        dict: 检测结果字典，包含以下键：
            - self_pos: 元组 (x, y) 或 None，自身位置坐标
            - self_health: 整数或 None，自身血量百分比
            - team_targets: 列表 [(x, y, health), ...]，队友位置和血量
            - enemies: 列表 [(x, y, health), ...]，敌人位置和血量
            - frame: numpy 数组，带标注的可视化图像
    """
    # 如果没有直接传入 frame，则从共享帧容器读取
    if frame is None:
        frame = get_full_frame(copy=True)
        if frame is None:
            capture = sct if sct is not None else window_capture
            if capture is None:
                logger.error("截图器未初始化")
                return {
                    "self_pos": None,
                    "self_health": None,
                    "team_targets": [],
                    "enemies": [],
                    "frame": None,
                }
            region = DEFAULT_REGIONS["full"]
            try:
                frame = capture.capture(region)
                frame = frame.copy()
            except (OSError, AttributeError, RuntimeError) as e:
                logger.error(f"截图失败: {e}")
                return {
                    "self_pos": None,
                    "self_health": None,
                    "team_targets": [],
                    "enemies": [],
                    "frame": None,
                }
    else:
        # 使用传入的 frame，但需要复制一份避免修改原图
        frame = frame.copy()

    # 使用模块级预定义的血条检测器（green_health_bar, blue_health_bar, red_health_bar）
    yolo_color = (255, 0, 0)
    opencv_color = (0, 255, 0)

    img = frame

    # 保存原始图像尺寸
    original_h, original_w = img.shape[:2]

    # 使用缩放后的图像进行YOLO检测（使用 ByteTrack 跟踪）
    img_for_yolo = cv2.resize(img, (640, 640))
    results = model.track(
        img_for_yolo, conf=YOLO_CONF, iou=YOLO_IOU, persist=True, verbose=False
    )

    # 将检测结果映射回原始图像尺寸
    scale_x = original_w / 640
    scale_y = original_h / 640

    self_pos = None
    self_health = None
    team_targets = []
    enemies = []

    # 日志计数器
    detection_count = {"self": 0, "team": 0, "enemy": 0}

    # 用于汇总日志的详细信息
    log_details = {"self": None, "team": [], "enemy": []}

    # 收集当前帧所有检测到的实体（使用 ByteTrack 的跟踪ID）
    current_detections = []

    # 预计算整帧 HSV，避免每个血条 ROI 重复转换
    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    active_track_ids = set()

    # 临时存储队友检测信息（用于数据融合匹配）
    team_detections = []

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            x1 = int(x1 * scale_x)
            y1 = int(y1 * scale_y)
            x2 = int(x2 * scale_x)
            y2 = int(y2 * scale_y)

            class_id = int(box.cls[0])

            # 提取 ByteTrack 跟踪ID
            track_id = int(box.id[0]) if box.id is not None else -1
            if track_id >= 0:
                active_track_ids.add(track_id)

            # 根据类别选择对应的 HealthBar 实例
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            if class_id == 0:
                health_bar = green_health_bar
                entity_type = "self"
            elif class_id == 1:
                health_bar = blue_health_bar
                entity_type = "team"
                team_detections.append(
                    {"bbox": (x1, y1, x2, y2), "center": (center_x, center_y)}
                )
            elif class_id == 2:
                health_bar = red_health_bar
                entity_type = "enemy"
            else:
                continue

            # 动态更新 target_width 为检测到的边界框宽度
            detected_width = x2 - x1

            # 截取检测到的 ROI 区域（HSV 预转换帧，避免重复 cvtColor）
            roi_hsv = img_hsv[y1:y2, x1:x2]

            # 计算血条的健康百分比
            debug_mode = class_id == 1
            raw_health_percentage = health_bar.calculate_health_percentage(
                roi_hsv, detected_width, debug=debug_mode
            )

            # ===== 血量 EMA 平滑（所有实体类型共用，基于 track_id） =====
            # 目的：消除 HSV 检测的帧间抖动，让血量变化更平滑
            health_percentage = raw_health_percentage
            if track_id >= 0:
                # 使用 track_id 作为键（比坐标更稳定）
                pos_key = f"track_{track_id}"
                last_health = _DETECTOR_STATE.health_history.get(
                    pos_key, raw_health_percentage
                )

                # 区分"掉血"和"噪声跳变"
                delta = raw_health_percentage - last_health  # 正值=回血, 负值=掉血

                if delta < -40:
                    # 血量大幅下降（被打了）：允许快速更新，但稍加平滑以防单帧误检
                    health_percentage = int(
                        last_health * 0.3 + raw_health_percentage * 0.7
                    )
                elif delta > 30:
                    # 血量突然大幅上升（可能是误检/切换目标）：保守更新
                    health_percentage = int(
                        last_health * 0.8 + raw_health_percentage * 0.2
                    )
                else:
                    # 正常波动范围：标准 EMA 平滑
                    health_percentage = int(
                        last_health * 0.6 + raw_health_percentage * 0.4
                    )

                # 始终更新历史值（旧版 bug：大幅变化时不更新导致血量卡住）
                _DETECTOR_STATE.health_history[pos_key] = health_percentage

            # 添加到当前帧检测列表（包含 track_id）
            current_detections.append(
                (center_x, center_y, health_percentage, entity_type, track_id)
            )

            # 绘制 YOLOv8 检测框和 OpenCV 血量框
            health_bar.draw_health_bar(
                img, (x1, y1, x2, y2), health_percentage, yolo_color, opencv_color
            )

    # 获取当前时间用于后续逻辑
    current_time = time.time()

    # 定期清理血量历史记录（每10秒）
    if current_time - _DETECTOR_STATE.last_health_cleanup_time >= 10.0:
        _DETECTOR_STATE.last_health_cleanup_time = current_time
        # 只保留当前活跃的 track_id 对应的历史记录
        keys_to_remove: list[str] = []
        for key in _DETECTOR_STATE.health_history:
            # 提取 track_id，格式为 "track_{id}"
            try:
                track_id_from_key = int(key.split("_")[1])
                if track_id_from_key not in active_track_ids:
                    keys_to_remove.append(key)
            except (IndexError, ValueError):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del _DETECTOR_STATE.health_history[key]

        if keys_to_remove:
            logger.debug(f"[血量平滑] 清理 {len(keys_to_remove)} 条过期历史记录")

    # ByteTrack 已处理跨帧跟踪，直接从当前检测结果构建跟踪实体
    # 格式：(x, y, health, entity_type, is_estimated) - is_estimated 始终为 False
    # 因为 ByteTrack 已经处理了遮挡和预测
    tracked_entities = []
    for x, y, health, entity_type, track_id in current_detections:
        # ByteTrack 提供的是实际检测结果，is_estimated 设为 False
        tracked_entities.append((x, y, health, entity_type, False))

    # 根据跟踪结果分类
    # 先收集所有 self 候选，避免多个绿色血条被误识别为自身
    self_candidates = []
    team_idx = 0
    for x, y, health, entity_type, is_estimated in tracked_entities:
        if entity_type == "self":
            self_candidates.append((x, y, health, is_estimated))
        elif entity_type == "team":
            team_targets.append((x, y, health))
            detection_count["team"] += 1
            log_details["team"].append((x, y, health, is_estimated))
            team_idx += 1
        elif entity_type == "enemy":
            enemies.append((x, y, health))
            detection_count["enemy"] += 1
            log_details["enemy"].append((x, y, health, is_estimated))

    # 处理 self 候选：选择离屏幕中心最近的作为自己，其余降级为队友
    if len(self_candidates) == 1:
        x, y, health, is_estimated = self_candidates[0]
        self_pos = (x, y)
        self_health = health
        detection_count["self"] += 1
        log_details["self"] = (x, y, health, is_estimated)
    elif len(self_candidates) > 1:
        # 计算屏幕中心
        screen_center_x = original_w / 2
        screen_center_y = original_h / 2
        # 找到离中心最近的 self 候选
        best_candidate = None
        min_dist = float("inf")
        for candidate in self_candidates:
            x, y, health, is_estimated = candidate
            dist = ((x - screen_center_x) ** 2 + (y - screen_center_y) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_candidate = candidate
        # 设置最终的 self
        if best_candidate is not None:
            x, y, health, is_estimated = best_candidate
            self_pos = (x, y)
            self_health = health
            detection_count["self"] += 1
            log_details["self"] = (x, y, health, is_estimated)
            # 其余降级为队友
            for candidate in self_candidates:
                if candidate != best_candidate:
                    x, y, health, is_estimated = candidate
                    team_targets.append((x, y, health))
                    detection_count["team"] += 1
                    log_details["team"].append((x, y, health, is_estimated))
                    team_idx += 1
            logger.debug(
                f"多 self 筛选: 从 {len(self_candidates)} 个候选中选择了最近的作为自身，其余 {len(self_candidates) - 1} 个降级为队友"
            )

    # 缩放为50%以提高显示性能
    img_resized = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2))

    # 控制日志输出频率（每1秒一次）
    should_log = current_time - _DETECTOR_STATE.last_log_time >= 1.0

    if should_log:
        _DETECTOR_STATE.last_log_time = current_time
        # 输出检测汇总日志
        total = (
            detection_count["self"] + detection_count["team"] + detection_count["enemy"]
        )
        if total > 0:
            estimated_count = sum(1 for e in tracked_entities if e[4])
            logger.info(
                f"检测汇总: 总计{total}个血条 (自身:{detection_count['self']}, 队友:{detection_count['team']}, 敌人:{detection_count['enemy']}), 估计位置:{estimated_count}"
            )
        else:
            logger.debug("未检测到任何血条")

    # 瑶附身状态处理：使用最靠近屏幕中心的队友位置作为自身位置
    if self_pos is None and team_targets:
        # 计算屏幕中心
        screen_center_x = original_w / 2
        screen_center_y = original_h / 2

        # 找到最靠近屏幕中心的队友
        closest_to_center = None
        min_distance = float("inf")

        for target in team_targets:
            tx, ty, _ = target
            dist = ((tx - screen_center_x) ** 2 + (ty - screen_center_y) ** 2) ** 0.5
            if dist < min_distance:
                min_distance = dist
                closest_to_center = target

        if closest_to_center:
            # 使用最靠近中心的队友位置作为自身位置
            self_pos = (closest_to_center[0], closest_to_center[1])
            # 瑶附身时自身血量显示为None
            self_health = None
            if should_log:
                logger.debug(
                    f"瑶附身推断: 使用队友位置作为自身位置 ({self_pos[0]:.1f}, {self_pos[1]:.1f})"
                )

    # 返回检测结果
    return {
        "self_pos": self_pos,
        "self_health": self_health,
        "team_targets": team_targets,
        "enemies": enemies,
        "frame": img_resized,
    }


if __name__ == "__main__":
    """
    独立测试模式：使用 scrcpy 获取画面进行实时检测
    
    功能说明：
        当直接运行此文件时，启动独立测试模式
        通过 scrcpy 连接手机，实时显示血条检测结果
    """
    print("[Model2] 独立测试模式 - 使用 scrcpy")
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

    print("[Model2] 开始检测，按 'q' 退出")
    try:
        while True:
            if latest_frame[0] is not None:
                result = detect(frame=latest_frame[0])
                if result and result.get("frame") is not None:
                    cv2.imshow("Model2 Detection", result["frame"])

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        print("[Model2] 测试结束")
