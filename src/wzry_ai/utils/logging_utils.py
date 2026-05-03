"""
日志工具模块 - 提供彩色日志格式化器和配置函数

功能说明：
    提供统一的日志管理功能，包括彩色输出、日志级别控制、文件输出等
    用于替代print语句，提供更专业的日志记录能力
"""

# 导入Python标准日志模块
import logging

# 导入日志处理器模块，支持日志文件轮转
import logging.handlers

# 导入sys模块，用于获取标准输出流
import sys

# 导入time模块，用于日志节流功能
import time

# 从typing导入Optional类型提示
from typing import Optional

# 全局日志配置标志
# 用于标记全局日志是否已配置，避免重复配置
_global_logging_configured = False


def _stream_is_tty(stream) -> bool:
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, TypeError, ValueError):
        return False


def _make_stream_safe_for_logging(stream):
    """Avoid logging crashes when a Windows console cannot encode a symbol."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, TypeError, ValueError):
            try:
                reconfigure(errors="replace")
            except (OSError, TypeError, ValueError):
                pass
    return stream


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器类

    功能说明：
        继承自logging.Formatter，根据日志级别使用不同颜色输出
        使不同级别的日志在终端中显示不同颜色，便于区分
    """

    # ANSI颜色代码字典
    # 这些代码是终端控制字符，用于改变文本颜色
    COLORS = {
        "DEBUG": "\033[36m",  # 青色 - 用于调试信息
        "INFO": "\033[97m",  # 白色 - 用于普通信息
        "WARNING": "\033[93m",  # 黄色 - 用于警告信息
        "ERROR": "\033[91m",  # 红色 - 用于错误信息
        "CRITICAL": "\033[95m",  # 紫色 - 用于严重错误
    }
    # 重置颜色代码，用于恢复默认颜色
    RESET = "\033[0m"

    def format(self, record):
        """
        格式化日志记录

        功能说明：
            重写父类的format方法，在日志消息前后添加颜色代码

        参数说明：
            record: 日志记录对象，包含日志级别、消息等信息
        """
        # 根据日志级别选择对应的颜色
        color = self.COLORS.get(record.levelname, self.COLORS["INFO"])
        # 在消息前后添加颜色代码和重置代码
        original_msg = record.msg
        record.msg = f"{color}{record.msg}{self.RESET}"
        # 调用父类的format方法完成格式化
        try:
            return super().format(record)
        finally:
            record.msg = original_msg


class ModuleFilter:
    """
    模块日志过滤器类

    功能说明：
        控制特定第三方模块的日志级别，过滤掉过于详细的日志
        用于减少第三方库（如ultralytics、scrcpy等）的日志输出
    """

    # 模块日志级别配置字典
    # 键是模块名前缀，值是对应的最低日志级别
    MODULE_LEVELS = {
        "ultralytics": logging.WARNING,  # ultralytics库只显示WARNING及以上级别
        "scrcpy": logging.ERROR,  # scrcpy库只显示ERROR及以上级别
        "adbutils": logging.WARNING,  # adbutils库只显示WARNING及以上级别
    }

    def filter(self, record):
        """
        过滤日志记录

        功能说明：
            实现logging.Filter的filter方法
            根据模块名决定是否允许该日志记录通过

        参数说明：
            record: 日志记录对象

        返回值：
            bool: True表示允许通过，False表示过滤掉
        """
        # 遍历模块级别配置
        for module, level in self.MODULE_LEVELS.items():
            # 检查日志记录是否来自该模块（通过名称前缀匹配）
            if record.name.startswith(module):
                # 只返回级别大于等于设定级别的日志
                return record.levelno >= level
        # 对于未配置的模块，允许所有日志通过
        return True


def setup_global_logging(
    level: int = logging.INFO,
    enable_color: bool = True,
    format_str: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """
    设置全局日志配置

    功能说明：
        配置全局日志系统，只需在程序入口调用一次
        支持控制台彩色输出和文件输出

    参数说明：
        level: 全局日志级别（如logging.INFO、logging.DEBUG）
        enable_color: 是否启用彩色输出，默认为True
        format_str: 日志格式字符串
        log_file: 日志文件路径，None表示不输出到文件
        max_bytes: 单个日志文件最大字节数，默认10MB
        backup_count: 保留的备份文件数量，默认3个
    """
    # 声明使用全局变量
    global _global_logging_configured

    # 检查是否已配置，避免重复配置
    if _global_logging_configured:
        return

    # 清除根日志记录器的现有处理器
    logging.root.handlers = []

    # 创建控制台输出处理器，输出到标准输出
    handler = logging.StreamHandler(_make_stream_safe_for_logging(sys.stdout))
    # 设置处理器的日志级别
    handler.setLevel(level)

    # 添加模块过滤器，控制第三方库的日志输出
    handler.addFilter(ModuleFilter())

    # 设置日志格式
    if enable_color and _stream_is_tty(sys.stdout):
        # 如果启用颜色且输出到终端，使用彩色格式化器
        formatter = ColoredFormatter(fmt=format_str, datefmt="%H:%M:%S")
    else:
        # 否则使用普通格式化器
        formatter = logging.Formatter(fmt=format_str, datefmt="%H:%M:%S")
    # 将格式化器应用到处理器
    handler.setFormatter(formatter)

    # 配置根日志记录器
    logging.root.setLevel(level)
    # 添加控制台处理器到根日志记录器
    logging.root.addHandler(handler)

    # 如果指定了日志文件，添加文件输出处理器
    if log_file:
        # 创建轮转文件处理器，当日志文件达到max_bytes时自动创建新文件
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,  # 日志文件路径
            maxBytes=max_bytes,  # 单个文件最大大小
            backupCount=backup_count,  # 保留的备份文件数
            encoding="utf-8",  # 文件编码
        )
        # 设置文件处理器的日志级别
        file_handler.setLevel(level)
        # 添加模块过滤器
        file_handler.addFilter(ModuleFilter())
        # 文件处理器不使用彩色格式（文件不需要颜色代码）
        file_formatter = logging.Formatter(fmt=format_str, datefmt="%H:%M:%S")
        file_handler.setFormatter(file_formatter)
        # 添加文件处理器到根日志记录器
        logging.root.addHandler(file_handler)

    # 标记全局日志已配置
    _global_logging_configured = True
    # 记录调试日志，表示配置完成
    logging.getLogger(__name__).debug("全局日志配置完成")


def get_logger(name: str) -> logging.Logger:
    """
    获取模块日志记录器

    功能说明：
        获取指定名称的日志记录器，用于在模块中记录日志
        推荐使用__name__作为名称，自动按模块组织日志

    参数说明：
        name: 日志记录器名称，通常传入__name__

    返回值：
        logging.Logger: 配置好的日志记录器对象
    """
    return logging.getLogger(name)


def set_module_level(module_name: str, level: int) -> None:
    """
    设置特定模块的日志级别

    功能说明：
        为指定模块设置独立的日志级别
        支持前缀匹配，可以为一组模块统一设置级别

    参数说明：
        module_name: 模块名称（支持前缀匹配）
        level: 日志级别（如logging.DEBUG、logging.WARNING）
    """
    # 获取模块的日志记录器并设置级别
    logging.getLogger(module_name).setLevel(level)


# 保持向后兼容 - 旧版函数仍然可用
def setup_colored_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    创建带颜色输出的日志器（向后兼容）

    功能说明：
        旧版本的日志器创建函数，保留以兼容旧代码
        建议新代码使用get_logger(__name__)替代

    参数说明：
        name: 日志器名称
        level: 日志级别，默认为DEBUG

    返回值：
        logging.Logger: 配置好的日志记录器
    """
    # 获取或创建指定名称的日志记录器
    logger = logging.getLogger(name)
    # 设置日志级别
    logger.setLevel(level)

    # 避免重复添加处理器（如果已存在则不添加）
    if not logger.handlers:
        # 创建控制台处理器
        handler = logging.StreamHandler(_make_stream_safe_for_logging(sys.stderr))
        handler.setLevel(level)
        # 创建彩色格式化器
        if _stream_is_tty(sys.stderr):
            formatter = ColoredFormatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
            )
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
            )
        handler.setFormatter(formatter)
        # 添加处理器到日志记录器
        logger.addHandler(handler)
        # 设置不向父级传播，避免重复输出
        logger.propagate = False

    return logger


class ThrottledLogger:
    """
    日志节流工具类

    功能说明：
        防止在高频循环中产生大量重复日志，导致日志刷屏
        同一个key的消息在指定时间间隔内只输出一次
    """

    def __init__(self, logger, interval: float = 2.0):
        """
        初始化日志节流器

        参数说明：
            logger: 底层的日志记录器
            interval: 同一key的消息最小间隔时间（秒），默认2秒
        """
        # 保存底层日志记录器
        self._logger = logger
        # 保存时间间隔
        self._interval = interval
        # 字典，记录每个key上次日志的时间戳
        self._last_log_time = {}

    def _should_log(self, key: str) -> bool:
        """
        判断是否应该记录日志（内部方法）

        功能说明：
            检查指定key的日志是否已经超过时间间隔

        参数说明：
            key: 日志标识key

        返回值：
            bool: True表示应该记录，False表示需要节流
        """
        # 获取当前时间戳
        now = time.time()
        # 检查是否首次记录或已超过时间间隔
        if (
            key not in self._last_log_time
            or (now - self._last_log_time[key]) >= self._interval
        ):
            # 更新该key的最后记录时间
            self._last_log_time[key] = now
            return True
        # 时间间隔内，不记录
        return False

    def debug(self, msg, key="default"):
        """
        记录DEBUG级别日志（带节流）

        参数说明：
            msg: 日志消息
            key: 日志标识key，相同key的日志会受间隔限制
        """
        if self._should_log(key):
            self._logger.debug(msg)

    def info(self, msg, key="default"):
        """
        记录INFO级别日志（带节流）

        参数说明：
            msg: 日志消息
            key: 日志标识key，相同key的日志会受间隔限制
        """
        if self._should_log(key):
            self._logger.info(msg)

    def warning(self, msg, key="default"):
        """
        记录WARNING级别日志（带节流）

        参数说明：
            msg: 日志消息
            key: 日志标识key，相同key的日志会受间隔限制
        """
        if self._should_log(key):
            self._logger.warning(msg)

    def error(self, msg, key="default"):
        """
        记录ERROR级别日志（带节流）

        参数说明：
            msg: 日志消息
            key: 日志标识key，相同key的日志会受间隔限制
        """
        if self._should_log(key):
            self._logger.error(msg)
