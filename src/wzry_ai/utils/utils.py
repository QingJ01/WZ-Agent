"""工具函数模块 - 通用辅助函数

本模块提供一些通用的工具函数，用于设备检测、距离计算、队列操作等常见任务。
"""

# 从queue模块导入Queue类（队列）和Empty异常（队列为空时抛出）
from queue import Queue, Empty, Full
# 从typing模块导入类型提示，用于标注函数参数和返回值类型
from typing import List, Tuple, Optional

# 第三方库导入（用于中文文本绘制）
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 从config导入字体路径
from wzry_ai.config import FONT_PATH

# 加载中文字体用于图像标注
font = None
try:
    font = ImageFont.truetype(FONT_PATH, 20)
except FileNotFoundError:
    font = None
except OSError:
    font = None


def cv2_add_chinese_text(img, text, position, text_color=(255, 255, 255)):
    """
    在 OpenCV 图像上添加中文文字

    功能说明：
        使用 PIL 库在图像上绘制中文字符，因为 OpenCV 默认不支持中文显示

    参数说明：
        img: numpy 数组，输入图像（BGR格式）
        text: 字符串，要显示的中文文字
        position: 元组 (x, y)，文字左上角位置
        text_color: 元组 (B, G, R)，文字颜色，默认白色

    返回值说明：
        numpy 数组，添加了文字的图像
    """
    if font is None:
        cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1)
        return img
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    draw.text(position, text, font=font, fill=text_color)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def cv2_add_chinese_texts(img, texts):
    """
    批量在 OpenCV 图像上添加中文文字（只做一次 PIL↔cv2 转换）

    参数说明：
        img: numpy 数组，输入图像（BGR格式）
        texts: 列表，每个元素为 (text, position, text_color) 元组
            - text: 字符串，要显示的中文文字
            - position: 元组 (x, y)，文字左上角位置
            - text_color: 元组 (B, G, R)，文字颜色

    返回值说明：
        numpy 数组，添加了所有文字的图像
    """
    if not texts:
        return img
    if font is None:
        for text, position, text_color in texts:
            cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1)
        return img
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    for text, position, text_color in texts:
        draw.text(position, text, font=font, fill=text_color)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def get_cuda_device() -> str:
    """
    获取可用的计算设备（CUDA 或 CPU）
    
    功能说明：
        检测系统是否支持NVIDIA CUDA加速，如果支持则返回'cuda'，否则返回'cpu'
        这个函数用于AI模型运行时自动选择最优的计算设备
    
    参数说明：
        无参数
    
    返回值：
        str: 'cuda' 表示使用GPU加速，'cpu' 表示使用CPU计算
    """
    try:
        # 尝试导入torch模块（PyTorch深度学习框架）
        import torch
        # 检查CUDA是否可用（即是否有NVIDIA显卡且驱动正确安装）
        if torch.cuda.is_available():
            # CUDA可用，返回'cuda'表示使用GPU
            return 'cuda'
        else:
            # CUDA不可用，返回'cpu'表示使用CPU
            return 'cpu'
    except (ImportError, AttributeError):
        # 如果导入torch失败或发生任何异常，默认返回'cpu'
        return 'cpu'


def find_closest_target(self_pos: Tuple[float, float], targets: List[Tuple]) -> Optional[Tuple]:
    """
    找到距离自己最近的目标
    
    功能说明：
        计算自己位置与多个目标位置之间的欧几里得距离，返回距离最近的目标
        常用于游戏中寻找最近的敌人、队友或资源点
    
    参数说明：
        self_pos: 自己的位置坐标，格式为(x, y)的元组
        targets: 目标位置列表，每个元素是(x, y)格式的元组
    
    返回值：
        距离最近的目标坐标元组，如果没有有效目标则返回None
    """
    # 检查自己位置或目标列表是否为空，如果为空则无法计算
    if not self_pos or not targets:
        return None
    # 使用min函数配合lambda表达式找到最近的目标
    # lambda函数计算每个目标与当前位置的距离（欧几里得距离公式）
    # ((x1-x2)^2 + (y1-y2)^2)^0.5 就是两点之间的直线距离
    return min(targets, key=lambda t: ((self_pos[0] - t[0]) ** 2 + (self_pos[1] - t[1]) ** 2) ** 0.5)


def clear_queue(q: Queue) -> int:
    """
    清空队列中的所有元素
    
    功能说明：
        将队列中的所有元素逐个取出并丢弃，返回被清空的元素数量
        用于重置队列状态或释放内存
    
    参数说明：
        q: 要清空的队列对象
    
    返回值：
        int: 被清空的元素数量
    """
    # 初始化计数器，用于记录清空的元素数量
    count = 0
    # 使用无限循环持续取出队列元素
    while True:
        try:
            # 尝试立即从队列取出一个元素（不阻塞等待）
            q.get_nowait()
            # 成功取出，计数器加1
            count += 1
        except Empty:
            # 队列为空时抛出Empty异常，此时退出循环
            break
    # 返回清空的元素总数
    return count


def safe_queue_put(q: Queue, item, clear_first: bool = True) -> bool:
    """
    安全地向队列放入数据
    
    功能说明：
        将数据放入队列，可选择先清空队列再放入
        用于确保队列中只保留最新的数据，避免旧数据堆积
    
    参数说明：
        q: 目标队列对象
        item: 要放入队列的数据
        clear_first: 是否先清空队列再放入，默认为True
    
    返回值：
        bool: 放入成功返回True，失败返回False
    """
    try:
        # 如果设置了先清空队列，则调用clear_queue函数
        if clear_first:
            clear_queue(q)
        # 使用put_nowait立即放入数据（不阻塞等待队列有空位）
        q.put_nowait(item)
        # 放入成功，返回True
        return True
    except (Full, AttributeError):
        # 发生任何异常（如队列已满），返回False表示失败
        return False


def safe_queue_get(q: Queue, default=None):
    """
    安全地从队列获取数据
    
    功能说明：
        从队列中取出数据，如果队列为空则返回默认值
        用于非阻塞式地获取队列数据，避免程序等待
    
    参数说明：
        q: 源队列对象
        default: 队列为空时返回的默认值，默认为None
    
    返回值：
        队列中的数据，或队列为空时返回default参数指定的值
    """
    try:
        # 尝试立即从队列取出一个元素（不阻塞等待）
        return q.get_nowait()
    except Empty:
        # 队列为空时返回默认值
        return default
