"""
线程监控器模块 - 自动检测并重启崩溃的工作线程

功能说明：
    游戏运行时，技能线程和移动线程可能因异常崩溃
    ThreadSupervisor 定期检查线程存活状态，发现崩溃后自动重启
    避免因单个线程异常导致整个程序停止工作

使用方式：
    supervisor = ThreadSupervisor()
    supervisor.register("技能线程", target=yao_bot.run, args=(queue,), daemon=True)
    supervisor.register("移动线程", target=fusion_func, args=(...,), daemon=True)
    supervisor.start_all()       # 启动所有已注册的线程
    supervisor.check_and_restart()  # 在主循环中定期调用，检查并重启崩溃线程
"""

import threading
import time
from wzry_ai.utils.logging_utils import get_logger

# 获取模块日志记录器
logger = get_logger(__name__)


class ManagedThread:
    """
    被管理的线程信息容器
    
    功能说明：
        存储一个线程的全部创建参数，以便在崩溃后用相同参数重新创建
    
    属性说明：
        name: 字符串，线程显示名称（如 "技能线程"）
        target: 函数，线程的目标函数
        args: 元组，传给目标函数的位置参数
        kwargs: 字典，传给目标函数的关键字参数
        daemon: 布尔值，是否为守护线程
        thread: threading.Thread 实例，当前活跃的线程对象
        restart_count: 整数，已重启次数
        max_restarts: 整数，最大允许重启次数（防止无限重启）
        last_restart_time: 浮点数，上次重启的时间戳
        cooldown: 浮点数，两次重启之间的最小间隔（秒）
    """
    def __init__(self, name, target, args=(), kwargs=None, daemon=True,
                 max_restarts=10, cooldown=5.0):
        """
        初始化被管理的线程
        
        参数说明：
            name: 字符串，线程显示名称
            target: 函数，线程执行的目标函数
            args: 元组，目标函数的位置参数
            kwargs: 字典，目标函数的关键字参数（默认为空字典）
            daemon: 布尔值，是否为守护线程（默认True，主程序退出时自动结束）
            max_restarts: 整数，最大重启次数（默认10次，防止死循环崩溃）
            cooldown: 浮点数，两次重启之间的最小间隔秒数（默认5秒）
        """
        self.name = name
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon
        self.thread = None          # 当前线程实例（初始为空）
        self.restart_count = 0      # 已重启次数
        self.max_restarts = max_restarts
        self.last_restart_time = 0  # 上次重启时间
        self.cooldown = cooldown    # 重启冷却时间

    def create_thread(self):
        """
        创建新的线程实例
        
        功能说明：
            用保存的参数创建一个全新的 threading.Thread 对象
            每次重启都必须创建新线程（Python 不允许重启已结束的线程）
        
        返回值：
            threading.Thread 实例
        """
        self.thread = threading.Thread(
            target=self.target,
            args=self.args,
            kwargs=self.kwargs,
            daemon=self.daemon,
            name=self.name
        )
        return self.thread

    def is_alive(self):
        """
        检查线程是否存活
        
        返回值：
            布尔值，线程存活返回 True，未创建或已崩溃返回 False
        """
        return self.thread is not None and self.thread.is_alive()

    def can_restart(self):
        """
        判断是否允许重启
        
        功能说明：
            检查两个条件：
            1. 重启次数未超过上限
            2. 距上次重启已过冷却时间
        
        返回值：
            布尔值，允许重启返回 True
        """
        # 超过最大重启次数，拒绝重启
        if self.restart_count >= self.max_restarts:
            return False
        # 冷却时间未到，拒绝重启
        if time.time() - self.last_restart_time < self.cooldown:
            return False
        return True


class ThreadSupervisor:
    """
    线程监控器 - 管理多个工作线程的生命周期
    
    功能说明：
        1. 注册需要监控的线程（保存创建参数）
        2. 统一启动所有线程
        3. 定期检查线程状态，发现崩溃自动重启
        4. 提供状态查询接口
    
    使用流程：
        register() → start_all() → 在主循环中调用 check_and_restart()
    """

    def __init__(self):
        """初始化线程监控器，创建空的线程注册表"""
        # 已注册的线程列表（ManagedThread 实例）
        self._threads = []
        # 监控器是否已启动
        self._started = False

    def register(self, name, target, args=(), kwargs=None, daemon=True,
                 max_restarts=10, cooldown=5.0):
        """
        注册一个需要监控的线程
        
        功能说明：
            将线程的创建参数保存到注册表中，但不立即启动
            调用 start_all() 或 start_thread() 时才会创建并启动线程
        
        参数说明：
            name: 字符串，线程显示名称（用于日志输出）
            target: 函数，线程的目标函数
            args: 元组，传给目标函数的位置参数
            kwargs: 字典，传给目标函数的关键字参数
            daemon: 布尔值，是否为守护线程
            max_restarts: 整数，最大允许重启次数
            cooldown: 浮点数，重启冷却时间（秒）
        
        返回值：
            ManagedThread 实例，可用于后续直接操作该线程
        """
        managed = ManagedThread(
            name=name, target=target, args=args, kwargs=kwargs,
            daemon=daemon, max_restarts=max_restarts, cooldown=cooldown
        )
        self._threads.append(managed)
        logger.info(f"[线程监控] 已注册线程: {name}")
        return managed

    def start_all(self):
        """
        启动所有已注册的线程
        
        功能说明：
            遍历注册表，为每个线程创建实例并启动
            启动后标记监控器为已启动状态
        """
        for managed in self._threads:
            managed.create_thread()
            managed.thread.start()
            logger.info(f"[线程监控] 线程已启动: {managed.name}")
        self._started = True

    def check_and_restart(self):
        """
        检查所有线程状态，重启已崩溃的线程
        
        功能说明：
            在主循环中定期调用此方法（建议每1-2秒调用一次）
            检查每个注册的线程是否还活着：
            - 活着 → 跳过
            - 崩溃且允许重启 → 创建新线程并启动
            - 崩溃但已达重启上限 → 记录警告日志
        
        返回值：
            列表，包含本次成功重启的线程名称
        """
        if not self._started:
            return []

        restarted = []
        for managed in self._threads:
            # 线程还活着，无需处理
            if managed.is_alive():
                continue

            # 线程未创建过（不应发生，但做防御）
            if managed.thread is None:
                continue

            # 线程已崩溃，检查是否可以重启
            if managed.can_restart():
                managed.restart_count += 1
                managed.last_restart_time = time.time()

                # 创建新线程并启动（Python 线程不可复用）
                managed.create_thread()
                managed.thread.start()

                logger.warning(
                    f"[线程监控] 线程 [{managed.name}] 已崩溃，"
                    f"第 {managed.restart_count}/{managed.max_restarts} 次重启"
                )
                restarted.append(managed.name)
            else:
                # 无法重启（超过上限或冷却中）
                if managed.restart_count >= managed.max_restarts:
                    logger.error(
                        f"[线程监控] 线程 [{managed.name}] 已崩溃，"
                        f"已达最大重启次数 {managed.max_restarts}，停止重试"
                    )

        return restarted

    def get_status(self):
        """
        获取所有线程的状态信息
        
        功能说明：
            返回每个注册线程的当前状态，用于调试和状态监控
        
        返回值：
            列表，每个元素是一个字典：
            {
                'name': 线程名,
                'alive': 是否存活,
                'restart_count': 已重启次数,
                'max_restarts': 最大允许重启次数
            }
        """
        status_list = []
        for managed in self._threads:
            status_list.append({
                'name': managed.name,
                'alive': managed.is_alive(),
                'restart_count': managed.restart_count,
                'max_restarts': managed.max_restarts
            })
        return status_list

    def stop_all(self):
        """
        停止监控（标记为未启动状态）
        
        功能说明：
            将监控器标记为未启动，check_and_restart() 将不再执行重启
            注意：守护线程会在主程序退出时自动结束，此方法不强制杀线程
        """
        self._started = False
        logger.info("[线程监控] 监控已停止")

    def reset(self):
        """
        重置监控器，清除所有注册的线程
        
        功能说明：
            清空注册表，恢复到初始状态
            用于游戏状态切换（如从对局结束回到大厅）时清理旧线程
        """
        self._threads.clear()
        self._started = False
        logger.info("[线程监控] 监控器已重置")
