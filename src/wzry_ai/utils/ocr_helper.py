"""
OCR 辅助识别模块 - 使用 PaddleOCR 或 EasyOCR 识别游戏界面文字
用于辅助模板匹配，提高界面状态识别准确性
"""

# 在导入 paddle 之前，将 NVIDIA CUDA DLL 路径添加到搜索路径
# 解决 GPU 版 PaddlePaddle 在 Windows 上的 DLL 加载失败问题
import os as _os

_nvidia_base = _os.path.join(
    _os.path.dirname(_os.__file__), "..", "Lib", "site-packages", "nvidia"
)
if _os.path.isdir(_nvidia_base):
    _current_path = _os.environ.get("PATH", "")
    for _d in _os.listdir(_nvidia_base):
        _bin_dir = _os.path.join(_nvidia_base, _d, "bin")
        if _os.path.isdir(_bin_dir):
            # 添加到 PATH 环境变量（影响子进程）
            if _bin_dir not in _current_path:
                _os.environ["PATH"] = _bin_dir + _os.pathsep + _os.environ["PATH"]
            # 使用 os.add_dll_directory 添加 DLL 搜索路径（Python 3.8+ Windows）
            if hasattr(_os, "add_dll_directory"):
                try:
                    _os.add_dll_directory(_bin_dir)
                except OSError:
                    pass

# 预加载 torch 以确保 CUDA DLL 在主线程完成加载，避免后台线程加载失败
import torch as _torch
from importlib import import_module

# 尝试导入 PaddleOCR，如果失败则使用 EasyOCR 作为备选
_OCR_BACKEND = None  # 'paddle' 或 'easyocr'
_PaddleOCR_cls = None
_EasyOCR_cls = None

import cv2
import numpy as np
from typing import (
    Any,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    TypeAlias,
    cast,
)
import threading
import time


class PaddleOCREngine(Protocol):
    def predict(self, image: np.ndarray) -> Iterable[object]: ...


class EasyOCREngine(Protocol):
    def readtext(self, image: np.ndarray) -> list[object]: ...


class PaddleOCRFactory(Protocol):
    def __call__(
        self, *, use_textline_orientation: bool, lang: str, device: str
    ) -> PaddleOCREngine: ...


class EasyOCRFactory(Protocol):
    def __call__(self, lang_list: list[str], gpu: bool) -> EasyOCREngine: ...


OCRBackend: TypeAlias = Literal["paddle", "easyocr"]
OCREngine: TypeAlias = PaddleOCREngine | EasyOCREngine


def _import_optional_module(module_name: str) -> Any | None:
    """按需导入可选模块，缺失时返回 None。"""
    try:
        return import_module(module_name)
    except (ImportError, ModuleNotFoundError):
        return None


def _check_paddle_available():
    """检查 PaddleOCR 是否可用（包括 paddle 模块）"""
    paddle_module = _import_optional_module("paddle")
    paddleocr_module = _import_optional_module("paddleocr")
    return (
        paddle_module is not None
        and paddleocr_module is not None
        and hasattr(paddleocr_module, "PaddleOCR")
    )


try:
    if _check_paddle_available():
        paddleocr_module = _import_optional_module("paddleocr")
        paddle_cls = (
            getattr(paddleocr_module, "PaddleOCR", None)
            if paddleocr_module is not None
            else None
        )
        if callable(paddle_cls):
            _PaddleOCR_cls = cast(PaddleOCRFactory, paddle_cls)
            _OCR_BACKEND = "paddle"
            print("[OCR] PaddleOCR 导入成功")  # 模块加载期日志，logger可能未初始化
except (ImportError, ModuleNotFoundError) as e:
    print(f"[OCR] PaddleOCR 导入失败: {e}")  # 模块加载期日志

try:
    _easyocr_module = _import_optional_module("easyocr")
    easyocr_cls = (
        getattr(_easyocr_module, "Reader", None)
        if _easyocr_module is not None
        else None
    )
    if callable(easyocr_cls):
        _EasyOCR_cls = cast(EasyOCRFactory, easyocr_cls)
        if _OCR_BACKEND is None:
            _OCR_BACKEND = "easyocr"
            print("[OCR] EasyOCR 导入成功，将作为备选")  # 模块加载期日志
except (ImportError, ModuleNotFoundError) as e:
    print(f"[OCR] EasyOCR 导入失败: {e}")  # 模块加载期日志

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)

# 延迟导入 OCR 引擎，避免启动时加载
_ocr_engine: OCREngine | Literal[False] | None = None
_ocr_lock = threading.Lock()
_ocr_initializing = False


def _init_ocr_in_background():
    """
    在后台线程中初始化 OCR 引擎

    功能说明：
        在独立的后台线程中初始化 OCR 引擎（PaddleOCR 或 EasyOCR），避免阻塞主程序启动
        设置必要的环境变量以优化性能和兼容性

    参数说明：
        无参数

    返回值说明：
        无返回值，初始化结果存储在全局变量 _ocr_engine 中
    """
    global _ocr_engine, _ocr_initializing
    with _ocr_lock:
        if _ocr_initializing or _ocr_engine is not None:
            return
        _ocr_initializing = True

    def _do_init():
        """
        实际执行 OCR 引擎初始化的内部函数

        功能说明：
            配置环境变量并创建 OCR 实例（优先使用 PaddleOCR，失败则使用 EasyOCR）
        """
        global _ocr_engine, _ocr_initializing
        try:
            import os

            # 设置4线程，平衡性能和兼容性
            os.environ["OMP_NUM_THREADS"] = "4"
            os.environ["MKL_NUM_THREADS"] = "4"

            # 优先尝试 PaddleOCR
            if _OCR_BACKEND == "paddle" and _PaddleOCR_cls is not None:
                # 禁用 oneDNN 以避免兼容性问题
                os.environ["FLAGS_use_mkldnn"] = "0"
                # 跳过模型源检查，避免每次启动时的网络连接延迟
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

                paddle = _import_optional_module("paddle")
                if paddle is None:
                    raise RuntimeError("paddle 模块不可用")
                logger.info(
                    f"PaddlePaddle {paddle.__version__} (CUDA={paddle.is_compiled_with_cuda()}, GPU={paddle.device.cuda.device_count()})"
                )
                logger.info("正在后台初始化 PaddleOCR 引擎...")
                # PaddleOCR 3.x 参数变更：use_gpu -> device='gpu'，use_angle_cls -> use_textline_orientation
                # 如果 GPU 不可用则自动降级为 CPU
                _device = (
                    "gpu"
                    if paddle.is_compiled_with_cuda()
                    and paddle.device.cuda.device_count() > 0
                    else "cpu"
                )
                _ocr_engine = _PaddleOCR_cls(
                    use_textline_orientation=False, lang="ch", device=_device
                )
                logger.info("PaddleOCR 引擎初始化完成")
            # 备选：使用 EasyOCR
            elif _OCR_BACKEND == "easyocr" and _EasyOCR_cls is not None:
                logger.info(
                    f"PyTorch {_torch.__version__} (CUDA={_torch.cuda.is_available()})"
                )
                logger.info("正在后台初始化 EasyOCR 引擎...")
                # EasyOCR 使用 GPU 如果可用
                _ocr_engine = _EasyOCR_cls(
                    lang_list=["ch_sim", "en"], gpu=_torch.cuda.is_available()
                )
                logger.info("EasyOCR 引擎初始化完成")
            else:
                raise RuntimeError(
                    "没有可用的 OCR 引擎（PaddleOCR 和 EasyOCR 都未能导入）"
                )
        except (RuntimeError, ImportError, OSError) as e:
            logger.error(f"OCR 初始化失败: {e}", exc_info=True)
            _ocr_engine = False
        finally:
            _ocr_initializing = False

    # 启动后台线程初始化，daemon=True 表示主程序退出时线程自动结束
    t = threading.Thread(target=_do_init, daemon=True)
    t.start()


def is_ocr_ready() -> bool:
    """
    检查 OCR 是否已初始化完成

    功能说明：
        判断 PaddleOCR 引擎是否已完成初始化且可用

    参数说明：
        无参数

    返回值说明：
        bool: True 表示初始化完成且可用，False 表示未初始化或初始化失败
    """
    global _ocr_engine
    return _ocr_engine is not None and _ocr_engine is not False


def _get_ocr_engine():
    """
    获取或创建 OCR 引擎（延迟加载）

    功能说明：
        如果 OCR 引擎尚未初始化，则在后台启动初始化过程
        返回当前引擎状态（可能是 None、False 或已初始化的引擎对象）

    参数说明：
        无参数

    返回值说明：
        返回 OCR 引擎对象，或 None（未初始化），或 False（初始化失败）
    """
    global _ocr_engine
    if _ocr_engine is None and not _ocr_initializing:
        _init_ocr_in_background()
    return _ocr_engine


def _recognize_with_paddle(
    engine: PaddleOCREngine, rgb_frame: np.ndarray
) -> List[Tuple[str, float]]:
    """调用 PaddleOCR 并标准化返回结果。"""
    texts: List[Tuple[str, float]] = []
    result_list = list(engine.predict(rgb_frame))

    for item in result_list:
        if isinstance(item, dict):
            rec_texts = item.get("rec_texts", [])
            rec_scores = item.get("rec_scores", [])
            for text, score in zip(rec_texts, rec_scores):
                texts.append((str(text), float(score)))

    return texts


def _recognize_with_easyocr(
    engine: EasyOCREngine, rgb_frame: np.ndarray
) -> List[Tuple[str, float]]:
    """调用 EasyOCR 并标准化返回结果。"""
    texts: List[Tuple[str, float]] = []

    for item in engine.readtext(rgb_frame):
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            text = item[1]
            confidence = item[2]
            texts.append((str(text), float(confidence)))

    return texts


def recognize_text(
    frame: np.ndarray, region: Optional[Tuple[int, int, int, int]] = None
) -> List[Tuple[str, float]]:
    """
    识别图像中的文字

    功能说明：
        使用 OCR 引擎（PaddleOCR 或 EasyOCR）识别图像中的文字内容
        支持指定区域裁剪和自适应缩放以提高识别准确率

    参数说明：
        frame: numpy 数组，输入图像（BGR格式）
        region: 可选，指定裁剪区域 (x, y, width, height)，None 表示识别全图

    返回值说明：
        List[Tuple[str, float]]: 识别结果列表，每个元素为 (文字内容, 置信度分数)
    """
    engine = _get_ocr_engine()
    if engine is False or engine is None:
        return []

    # 如果指定了区域，先裁剪区域以减少后续处理的像素数量
    if region:
        x, y, w, h = region
        frame = frame[y : y + h, x : x + w]

    # 自适应缩放：小图放大提高识别率，大图保持原样
    h, w = frame.shape[:2]
    max_dim = max(h, w)
    if max_dim < 400:
        scale = min(2.0, 800 / max_dim)
        frame = cv2.resize(
            frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
        )

    # 直接转换为灰度再转RGB（减少一次颜色转换）
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rgb_frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    try:
        # 根据后端类型调用不同的识别方法
        if _OCR_BACKEND == "paddle":
            return _recognize_with_paddle(cast(PaddleOCREngine, engine), rgb_frame)

        elif _OCR_BACKEND == "easyocr":
            return _recognize_with_easyocr(cast(EasyOCREngine, engine), rgb_frame)

        return []
    except (RuntimeError, ValueError, AttributeError, OSError) as e:
        logger.error(f"识别失败: {e}", exc_info=True)
        return []


def find_text(
    frame: np.ndarray,
    keywords: List[str],
    region: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[str, float]]:
    """
    查找指定关键词，返回第一个匹配

    功能说明：
        在图像中识别文字，并查找是否包含指定的关键词列表中的任意一个

    参数说明：
        frame: numpy 数组，输入图像
        keywords: 字符串列表，要查找的关键词
        region: 可选，指定裁剪区域

    返回值说明：
        Optional[Tuple[str, float]]: 返回第一个匹配的关键词所在的 (文字内容, 置信度)，未找到返回 None
    """
    texts = recognize_text(frame, region)

    for text, conf in texts:
        for keyword in keywords:
            if keyword in text:
                return (text, conf)
    return None


def check_match_confirm(frame: np.ndarray) -> float:
    """
    检查匹配确认界面，返回置信度分数

    功能说明：
        检测游戏界面是否显示"匹配成功"等确认按钮文字
        用于判断是否需要点击确认进入游戏

    参数说明：
        frame: numpy 数组，输入图像

    返回值说明：
        float: 置信度分数，0.0 表示未检测到，大于 0 表示检测到的置信度
    """
    h, w = frame.shape[:2]
    # 缩小检测区域到中心按钮区域，提高检测效率和准确率
    center_region = (int(w * 0.35), int(h * 0.4), int(w * 0.3), int(h * 0.2))

    result = find_text(frame, ["匹配成功", "确认", "接受"], center_region)
    if result:
        text, conf = result
        logger.debug(f"检测到匹配确认文字: '{text}' (置信度: {conf:.2f})")
        return conf
    return 0.0


def check_battle_start(frame: np.ndarray) -> float:
    """
    检查是否进入战斗，返回置信度分数

    功能说明：
        检测游戏界面是否显示战斗相关的文字（如"回车"、"恢复"等）
        用于判断游戏是否已进入战斗状态

    参数说明：
        frame: numpy 数组，输入图像

    返回值说明：
        float: 置信度分数，0.0 表示未检测到战斗状态
    """
    h, w = frame.shape[:2]
    # 缩小检测区域到中心区域
    center_region = (int(w * 0.35), int(h * 0.4), int(w * 0.3), int(h * 0.2))

    result = find_text(frame, ["回车", "恢复"], center_region)
    if result:
        text, conf = result
        logger.debug(f"检测到战斗开始文字: '{text}' (置信度: {conf:.2f})")
        return conf
    return 0.0


def check_text_score(
    frame: np.ndarray,
    keywords: List[str],
    region: Optional[Tuple[int, int, int, int]] = None,
) -> float:
    """
    检查指定文字的综合置信度分数

    功能说明：
        识别图像中的文字，计算包含指定关键词的最高置信度

    参数说明：
        frame: numpy 数组，输入图像
        keywords: 字符串列表，要检查的关键词
        region: 可选，指定裁剪区域

    返回值说明：
        float: 最高置信度分数，0.0 表示未检测到任何关键词
    """
    texts = recognize_text(frame, region)

    max_score = 0.0
    for text, conf in texts:
        for keyword in keywords:
            if keyword in text and conf > max_score:
                max_score = conf
                logger.debug(
                    f"检测到文字: '{text}' 包含 '{keyword}' (置信度: {conf:.2f})"
                )

    return max_score


def check_victory_defeat(frame: np.ndarray) -> Optional[str]:
    """
    检查结算界面（胜利/失败）

    功能说明：
        检测游戏结算界面，判断是否显示胜利或失败
        支持中英文关键词匹配

    参数说明：
        frame: numpy 数组，输入图像

    返回值说明：
        Optional[str]: "victory" 表示胜利，"defeat" 表示失败，None 表示未检测到
    """
    # 只检测顶部小区域（胜利/失败标志位置固定）
    h, w = frame.shape[:2]
    top_region = (int(w * 0.3), 0, int(w * 0.4), int(h * 0.25))

    texts = recognize_text(frame, top_region)

    for text, conf in texts:
        if "胜利" in text or "VICTORY" in text.upper():
            logger.debug(f"检测到胜利: '{text}' (置信度: {conf:.2f})")
            return "victory"
        if "失败" in text or "DEFEAT" in text.upper():
            logger.debug(f"检测到失败: '{text}' (置信度: {conf:.2f})")
            return "defeat"
    return None


def check_game_state(frame: np.ndarray) -> dict:
    """
    综合检查游戏状态

    功能说明：
        综合分析图像中的文字信息，判断当前游戏状态
        包括匹配确认、胜利、失败等状态的检测

    参数说明：
        frame: numpy 数组，输入图像

    返回值说明：
        dict: 包含以下键的字典
            - match_confirm: bool，是否检测到匹配确认
            - victory: bool，是否检测到胜利
            - defeat: bool，是否检测到失败
            - texts: List[Tuple[str, float]]，所有识别到的文字列表
    """
    result = {"match_confirm": False, "victory": False, "defeat": False, "texts": []}

    # 识别全图文字
    texts = recognize_text(frame)
    result["texts"] = texts

    # 检查各种状态
    for text, conf in texts:
        if conf < 0.6:
            continue

        if "匹配成功" in text or ("确认" in text and "匹配" in text):
            result["match_confirm"] = True
        if "胜利" in text or "VICTORY" in text.upper():
            result["victory"] = True
        if "失败" in text or "DEFEAT" in text.upper():
            result["defeat"] = True

    return result


# 测试代码
if __name__ == "__main__":
    import time

    # 测试 OCR 功能
    logger.info("=== OCR 辅助识别模块测试 ===")

    # 先触发 OCR 初始化
    logger.info("触发 OCR 初始化...")
    _get_ocr_engine()

    # 等待 OCR 初始化完成
    logger.info("等待 OCR 初始化完成...")
    wait_count = 0
    while _ocr_engine is None and _ocr_initializing and wait_count < 60:
        time.sleep(0.5)
        wait_count += 1
        logger.info(f"等待中... {wait_count * 0.5:.0f}s")

    if _ocr_engine is None:
        logger.error("OCR 初始化失败或超时")
    else:
        logger.info("OCR 初始化完成")

    # 使用 PIL 创建测试图像（支持中文）
    from PIL import Image, ImageDraw, ImageFont

    # 创建白色背景图像
    test_img_pil = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(test_img_pil)

    # 尝试加载系统字体
    try:
        # Windows 系统字体路径，优先使用黑体
        font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 60)
    except OSError:
        try:
            # 黑体加载失败则尝试宋体
            font = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", 60)
        except OSError:
            # 如果都失败则使用默认字体
            font = ImageFont.load_default()
            logger.warning("无法加载中文字体，使用默认字体")

    # 在图像上绘制测试文字
    draw.text((150, 150), "返回房间", fill=(0, 0, 0), font=font)

    # 将 PIL 图像转换为 OpenCV 格式 (BGR)
    test_img = cv2.cvtColor(np.array(test_img_pil), cv2.COLOR_RGB2BGR)

    logger.info("测试文字识别...")
    start = time.time()
    texts = recognize_text(test_img)
    elapsed = time.time() - start
    logger.info(f"识别耗时: {elapsed * 1000:.1f}ms")
    logger.info(f"识别结果: {texts}")

    logger.info("测试匹配确认检测...")
    is_match = check_match_confirm(test_img)
    logger.info(f"是否匹配确认: {is_match}")

    logger.info("=== 测试完成 ===")
