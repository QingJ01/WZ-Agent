"""
模态3检测器 - 游戏事件识别
检测击杀英雄、英雄助攻、击杀小兵、小兵助攻、被防御塔攻击等事件
使用 wzry.pt YOLO模型
"""

import logging
import time
from typing import Any
import cv2
import numpy as np
from collections import deque
from ultralytics.models import YOLO
from wzry_ai.config.base import MODEL3_WEIGHTS, MODEL3_CONFIDENCE_THRESHOLD, YOLO_IOU
from wzry_ai.utils.utils import get_cuda_device, cv2_add_chinese_text

logger = logging.getLogger(__name__)

# 模型3检测类别映射
MODEL3_CLASSES = {
    3: "kill_hero",  # 击杀英雄
    4: "kill_hero_assist",  # 英雄助攻
    5: "kill_unit",  # 击杀小兵
    6: "kill_unit_assist",  # 小兵助攻
    7: "tower_attack",  # 被防御塔攻击
}

# 事件颜色映射 (BGR格式)
EVENT_COLORS = {
    "kill_hero": (0, 255, 0),  # 绿色
    "kill_hero_assist": (0, 255, 255),  # 黄色
    "kill_unit": (255, 0, 255),  # 紫色
    "kill_unit_assist": (255, 165, 0),  # 橙色
    "tower_attack": (0, 0, 255),  # 红色
}

# 事件中文名称
EVENT_NAMES_CN = {
    "kill_hero": "击杀英雄",
    "kill_hero_assist": "英雄助攻",
    "kill_unit": "击杀小兵",
    "kill_unit_assist": "小兵助攻",
    "tower_attack": "防御塔攻击",
}

# 加载模型
model = None
# 事件历史记录（最近5秒）
_event_history = deque(maxlen=10)
_detect_count = 0
_event_total = 0


def _to_numpy_array(value: object) -> np.ndarray[Any, Any]:
    """将 YOLO 输出 truthfully 收窄为 numpy 数组。"""
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


def _init_model():
    global model
    if model is not None:
        return
    logger.info(f"加载模态3模型: {MODEL3_WEIGHTS}")
    model = YOLO(MODEL3_WEIGHTS)
    device = get_cuda_device()
    if device == "cuda":
        logger.info("模态3: CUDA 可用，使用 GPU 推理")
    else:
        logger.info("模态3: 使用 CPU 推理")
    model.to(device)


def detect(frame=None):
    """
    检测游戏事件（击杀、被塔攻击等）

    参数:
        frame: numpy数组，游戏截图（BGR格式）。如果为None则从共享帧获取

    返回:
        dict: {
            'kill_hero': bool,        # 是否击杀了英雄
            'kill_hero_assist': bool,  # 是否有英雄助攻
            'kill_unit': bool,         # 是否击杀了小兵
            'kill_unit_assist': bool,  # 是否有小兵助攻
            'tower_attack': bool,      # 是否被防御塔攻击
            'events': list,            # 所有检测到的事件详情 [{class_id, class_name, confidence, bbox}]
            'frame': numpy数组,        # 带标注的可视化图像（缩放50%）
        }
    """
    _init_model()
    predictor = model

    result = {
        "kill_hero": False,
        "kill_hero_assist": False,
        "kill_unit": False,
        "kill_unit_assist": False,
        "tower_attack": False,
        "events": [],
        "frame": None,
    }

    if frame is None:
        # 从共享帧容器获取（与model2类似）
        from wzry_ai.utils.frame_manager import get_full_frame

        frame = get_full_frame(copy=True)
        if frame is None:
            return result

    if predictor is None:
        logger.error("模态3模型初始化失败")
        return result

    # 保存原始帧副本用于绘制
    img = frame.copy()
    original_h, original_w = img.shape[:2]

    try:
        # 缩放到640x640进行推理
        img_for_yolo = cv2.resize(frame, (640, 640))
        results = predictor.predict(
            img_for_yolo, conf=MODEL3_CONFIDENCE_THRESHOLD, iou=YOLO_IOU, verbose=False
        )

        # 计算坐标映射比例
        scale_x = original_w / 640
        scale_y = original_h / 640

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if cls_id in MODEL3_CLASSES:
                    class_name = MODEL3_CLASSES[cls_id]
                    # 获取检测框坐标并映射回原始帧尺寸
                    coords = _to_numpy_array(box.xyxy[0]).reshape(-1)
                    if coords.size < 4:
                        continue
                    x1, y1, x2, y2 = coords[:4].tolist()
                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)
                    bbox = [x1, y1, x2, y2]

                    result[class_name] = True
                    result["events"].append(
                        {
                            "class_id": cls_id,
                            "class_name": class_name,
                            "confidence": conf,
                            "bbox": bbox,
                        }
                    )

                    # 绘制检测框
                    color = EVENT_COLORS.get(class_name, (128, 128, 128))
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                    # 绘制标签（类别名+置信度）
                    label = f"{EVENT_NAMES_CN.get(class_name, class_name)} {conf:.2f}"
                    label_size, _ = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                    )
                    label_y = (
                        y1 - 10 if y1 - 10 > label_size[1] else y1 + label_size[1] + 5
                    )
                    cv2.rectangle(
                        img,
                        (x1, label_y - label_size[1] - 5),
                        (x1 + label_size[0], label_y + 5),
                        color,
                        -1,
                    )
                    cv2.putText(
                        img,
                        label,
                        (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )

        if result["events"]:
            event_names = [e["class_name"] for e in result["events"]]
            logger.info(f"模态3检测到事件: {', '.join(event_names)}")
        else:
            # 没有检测到事件，在帧左上角显示 "No Events"
            cv2.putText(
                img,
                "No Events",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (128, 128, 128),
                2,
            )

        # 将帧缩放50%
        img_resized = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2))
        result["frame"] = img_resized

    except Exception as e:
        logger.error(f"模态3检测异常: {e}")

    return result
