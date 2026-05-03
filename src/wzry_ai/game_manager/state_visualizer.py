# -*- coding: utf-8 -*-
"""
状态可视化模块 - 实时显示当前流程和状态

功能说明：
- 彩色控制台输出状态信息
- 显示流程进度百分比
- 记录状态转换历史
- 实时状态刷新

参数说明：
- history_size: 历史记录大小
- print_interval: 最小输出间隔（秒）

返回值说明：
- 各方法返回状态信息字典或进度对象
"""

import time  # 导入时间模块，用于记录时间戳和计算持续时间
from dataclasses import dataclass, field  # 导入数据类工具
from typing import Dict, List, Optional  # 导入类型提示工具
from collections import deque  # 导入双端队列，用于保存历史记录

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)  # 获取当前模块的日志记录器


@dataclass
class StateTransition:
    """
    状态转换记录数据类 - 保存一次状态转换的完整信息
    
    参数说明：
    - from_state: 转换前的状态名称
    - to_state: 转换后的状态名称
    - timestamp: 转换发生的时间戳
    - confidence: 状态检测的置信度
    - trigger: 触发转换的原因
    - flow: 所属流程名称
    
    功能描述：
    用于记录和追踪状态变化历史，便于调试和分析
    """
    from_state: str  # 源状态名称
    to_state: str  # 目标状态名称
    timestamp: float  # 转换时间戳
    confidence: float  # 检测置信度
    trigger: str  # 触发原因
    flow: str = ""  # 所属流程，默认为空


@dataclass
class FlowProgress:
    """
    流程进度信息数据类 - 记录当前流程的执行进度
    
    参数说明：
    - flow_name: 流程名称
    - current_state: 当前状态名称
    - total_states: 流程中总状态数
    - current_index: 当前状态在流程中的索引
    - percentage: 进度百分比
    
    功能描述：
    用于计算和显示当前流程的完成进度
    """
    flow_name: str  # 流程名称
    current_state: str  # 当前状态名称
    total_states: int  # 流程中总状态数
    current_index: int  # 当前状态索引（从1开始）
    percentage: float  # 进度百分比（0-100）


class StateVisualizer:
    """
    状态可视化器类 - 实时显示当前流程和状态
    
    参数说明：
    - history_size: 历史记录大小，默认保存最近20条记录
    - print_interval: 最小输出间隔（秒），默认0.5秒
    
    功能描述：
    1. 彩色控制台输出状态信息
    2. 显示流程进度百分比
    3. 记录状态转换历史
    4. 实时状态刷新
    """
    
    # 流程分组颜色（ANSI转义码），用于控制台彩色输出
    FLOW_COLORS = {
        'startup': '\033[94m',       # 蓝色 - 启动流程
        'battle_flow': '\033[92m',   # 绿色 - 对战流程
        'ranking_flow': '\033[93m',  # 黄色 - 排位流程
        'matching': '\033[96m',      # 青色 - 匹配流程
        'game_core': '\033[91m',     # 红色 - 游戏核心
        'settlement': '\033[95m',    # 紫色 - 结算流程
        'special': '\033[90m',       # 灰色 - 特殊状态
        'unknown': '\033[90m',       # 灰色 - 未知
        'reset': '\033[0m'           # 重置
    }
    
    # 流程状态定义（用于计算进度），每个流程包含按顺序排列的状态列表
    FLOW_STATES = {
        'startup': [  # 启动流程
            'unknown', 'launcher', 'update_log',
            'select_zone', 'hall'
        ],
        'battle_flow': [  # 对战流程
            'hall', 'battle_mode_select', 'battle_5v5_sub', 
            'battle_5v5_type', 'battle_ai_mode', 'battle_ai_difficulty', 
            'battle_room'
        ],
        'ranking_flow': [  # 排位流程
            'hall', 'ranking_match_select', 'ranking_ban_pick', 
            'battle_room'
        ],
        'matching': [  # 匹配流程
            'battle_room', 'matching', 'match_confirmed'
        ],
        'game_core': [  # 游戏核心流程
            'hero_select', 'lane_select', 'game_loading_vs', 'in_game'
        ],
        'settlement': [  # 结算流程
            'in_game', 'game_end', 'mvp_display', 'post_match_stats', 
            'return_to_room'
        ],
    }
    
    def __init__(self, history_size: int = 20, print_interval: float = 0.5):
        """
        初始化可视化器
        
        参数说明：
        - history_size: 历史记录大小，控制保存多少条状态转换记录
        - print_interval: 最小输出间隔（秒），控制状态刷新的频率
        
        功能描述：
        初始化历史记录队列、当前状态、统计信息等
        """
        self.history: deque = deque(maxlen=history_size)  # 创建固定大小的双端队列保存历史
        self.current_flow = "unknown"  # 初始化当前流程为未知
        self.current_state = "unknown"  # 初始化当前状态为未知
        self.last_print_time = 0  # 初始化上次打印时间
        self.print_interval = print_interval  # 保存输出间隔设置
        self.frame_count = 0  # 初始化帧计数器
        
        # 统计信息字典
        self.stats = {
            'transitions': 0,  # 状态转换次数
            'state_durations': {},  # 各状态持续时间记录
            'last_state_time': time.time(),  # 上次状态变化时间
        }
    
    def update(self, state: str, flow: str, confidence: float, trigger: str = ""):
        """
        更新状态显示
        
        参数说明：
        - state: 当前状态名称
        - flow: 当前流程名称
        - confidence: 状态检测置信度（0-1之间）
        - trigger: 触发状态变化的原因描述
        
        功能描述：
        更新当前状态和流程，如果状态发生变化则记录转换并打印信息，
        否则定期刷新显示当前状态
        """
        self.frame_count += 1  # 帧计数器加1
        old_state = self.current_state  # 保存旧状态
        old_flow = self.current_flow  # 保存旧流程
        self.current_state = state  # 更新当前状态
        self.current_flow = flow  # 更新当前流程
        
        # 状态发生变化
        if old_state != state:  # 如果状态改变
            # 记录状态持续时间
            duration = time.time() - self.stats['last_state_time']  # 计算在旧状态的持续时间
            if old_state not in self.stats['state_durations']:  # 如果旧状态没有记录
                self.stats['state_durations'][old_state] = []  # 创建空列表
            self.stats['state_durations'][old_state].append(duration)  # 添加持续时间
            self.stats['last_state_time'] = time.time()  # 更新状态变化时间
            self.stats['transitions'] += 1  # 转换次数加1
            
            # 记录转换
            transition = StateTransition(  # 创建状态转换记录对象
                from_state=old_state,  # 源状态
                to_state=state,  # 目标状态
                timestamp=time.time(),  # 当前时间戳
                confidence=confidence,  # 置信度
                trigger=trigger,  # 触发原因
                flow=flow  # 所属流程
            )
            self.history.append(transition)  # 添加到历史记录
            
            # 打印转换信息
            self._print_transition(transition)  # 调用打印方法
            
            # 如果流程变化，打印流程信息
            if old_flow != flow:  # 如果流程改变
                self._print_flow_change(old_flow, flow)  # 打印流程变化信息
        else:  # 如果状态没有变化
            # 定期刷新显示
            self._refresh_display(confidence)  # 刷新当前状态显示
    
    def _print_transition(self, transition: StateTransition):
        """
        打印状态转换信息
        
        参数说明：
        - transition: 状态转换记录对象
        
        功能描述：
        在控制台打印格式化的状态切换信息，包括流程、置信度、触发原因和进度
        """
        flow_color = self.FLOW_COLORS.get(self.current_flow, self.FLOW_COLORS['unknown'])  # 获取流程对应的颜色
        reset = self.FLOW_COLORS['reset']  # 获取重置颜色代码
        
        logger.info(f"{'='*70}")  # 打印分隔线
        logger.info(f"【状态切换】 {transition.from_state} → {transition.to_state}")  # 打印状态变化
        logger.info(f"  流程: {self.current_flow.upper()}")  # 打印当前流程
        logger.info(f"  置信度: {transition.confidence:.2f}")  # 打印置信度
        logger.info(f"  触发: {transition.trigger}")  # 打印触发原因
        logger.info(f"  时间: {time.strftime('%H:%M:%S')}")  # 打印当前时间
        
        # 显示进度
        progress = self.get_flow_progress()  # 获取当前流程进度
        if progress.percentage > 0:  # 如果有进度信息
            bar = self._render_progress_bar(progress.percentage)  # 渲染进度条
            logger.info(f"  进度: {bar} {progress.percentage:.1f}%")  # 打印进度
        
        logger.info(f"{'='*70}")  # 打印分隔线
    
    def _print_flow_change(self, old_flow: str, new_flow: str):
        """
        打印流程变化信息
        
        参数说明：
        - old_flow: 之前的流程名称
        - new_flow: 新的流程名称
        
        功能描述：
        当流程发生变化时打印提示信息
        """
        logger.info(f">>> 进入新流程: {new_flow.upper()}")  # 打印流程变化信息
    
    def _refresh_display(self, confidence: float):
        """
        刷新当前状态显示（单行）
        
        参数说明：
        - confidence: 当前状态检测置信度
        
        功能描述：
        定期刷新显示当前状态信息，使用debug级别避免控制台刷屏
        """
        now = time.time()  # 获取当前时间
        if now - self.last_print_time < self.print_interval:  # 如果距离上次打印时间小于间隔
            return  # 直接返回，不打印
        
        self.last_print_time = now  # 更新上次打印时间
        
        # 获取进度
        progress = self.get_flow_progress()  # 获取当前流程进度
        progress_str = f"[{progress.percentage:5.1f}%]" if progress.percentage > 0 else "[---]"  # 格式化进度字符串
        
        # 使用debug级别记录状态刷新（避免控制台刷屏）
        logger.debug(
            f"[{self.current_flow.upper():12s}] "  # 流程名称（占12字符）
            f"{progress_str} "  # 进度百分比
            f"状态: {self.current_state:25s} "  # 状态名称（占25字符）
            f"置信: {confidence:.2f}"  # 置信度
        )
    
    def _render_progress_bar(self, percentage: float, width: int = 20) -> str:
        """
        渲染进度条
        
        参数说明：
        - percentage: 进度百分比（0-100）
        - width: 进度条总宽度（字符数）
        
        返回值：
        - str: 渲染后的进度条字符串
        
        功能描述：
        将百分比转换为可视化的进度条字符串，使用█表示已完成，░表示未完成
        """
        filled = int(width * percentage / 100)  # 计算已完成部分的长度
        bar = '█' * filled + '░' * (width - filled)  # 组合进度条字符串
        return bar  # 返回进度条
    
    def get_flow_progress(self) -> FlowProgress:
        """
        获取当前流程进度
        
        返回值：
        - FlowProgress: 包含流程名称、当前状态、总状态数、当前索引和百分比的对象
        
        功能描述：
        根据当前流程和状态，计算在流程中的进度百分比
        """
        if self.current_flow in self.FLOW_STATES:  # 如果当前流程在定义中
            states = self.FLOW_STATES[self.current_flow]  # 获取该流程的所有状态
            try:
                current_idx = states.index(self.current_state)  # 查找当前状态的索引
                percentage = (current_idx + 1) / len(states) * 100  # 计算进度百分比
                return FlowProgress(  # 返回进度对象
                    flow_name=self.current_flow,  # 流程名称
                    current_state=self.current_state,  # 当前状态
                    total_states=len(states),  # 总状态数
                    current_index=current_idx + 1,  # 当前索引（从1开始）
                    percentage=percentage  # 进度百分比
                )
            except ValueError:  # 如果当前状态不在流程中
                pass  # 跳过，返回空进度
        
        return FlowProgress(  # 返回空进度对象
            flow_name=self.current_flow,
            current_state=self.current_state,
            total_states=0,
            current_index=0,
            percentage=0
        )
    
    def print_history(self, count: int = 10):
        """
        打印最近的状态历史
        
        参数说明：
        - count: 要显示的记录数量，默认10条
        
        功能描述：
        打印最近的状态转换历史记录，便于查看状态变化轨迹
        """
        logger.info(f"{'='*70}")  # 打印分隔线
        logger.info("最近状态转换历史:")  # 打印标题
        logger.info(f"{'='*70}")  # 打印分隔线
        
        history_list = list(self.history)[-count:]  # 获取最近count条记录
        for i, trans in enumerate(history_list, 1):  # 遍历记录，从1开始计数
            time_str = time.strftime('%H:%M:%S', time.localtime(trans.timestamp))  # 格式化时间
            
            logger.info(f"{i:2d}. [{time_str}] "  # 打印序号和时间
                  f"{trans.from_state:20s} → "  # 打印源状态
                  f"{trans.to_state:20s} "  # 打印目标状态
                  f"({trans.confidence:.2f})")  # 打印置信度
        
        logger.info(f"{'='*70}")  # 打印分隔线
    
    def print_summary(self):
        """
        打印运行摘要
        
        功能描述：
        打印状态可视化器的运行统计摘要，包括帧数、转换次数和各状态持续时间
        """
        logger.info(f"{'='*70}")  # 打印分隔线
        logger.info("状态可视化器运行摘要")  # 打印标题
        logger.info(f"{'='*70}")  # 打印分隔线
        logger.info(f"总帧数: {self.frame_count}")  # 打印总帧数
        logger.info(f"状态转换次数: {self.stats['transitions']}")  # 打印转换次数
        logger.info(f"当前流程: {self.current_flow}")  # 打印当前流程
        logger.info(f"当前状态: {self.current_state}")  # 打印当前状态
        
        # 各状态平均持续时间
        logger.info("各状态平均持续时间:")  # 打印小标题
        for state, durations in self.stats['state_durations'].items():  # 遍历各状态
            if durations:  # 如果有持续时间记录
                avg_duration = sum(durations) / len(durations)  # 计算平均持续时间
                logger.info(f"  {state:25s}: {avg_duration:.2f}s (共{len(durations)}次)")  # 打印统计
        
        logger.info(f"{'='*70}")  # 打印分隔线
    
    def get_current_status(self) -> Dict:
        """
        获取当前状态信息
        
        返回值：
        - Dict: 包含当前状态、流程、进度、帧数和转换次数的字典
        
        功能描述：
        返回当前状态的完整信息，供外部调用使用
        """
        progress = self.get_flow_progress()  # 获取当前进度
        return {
            'state': self.current_state,  # 当前状态
            'flow': self.current_flow,  # 当前流程
            'progress_percentage': progress.percentage,  # 进度百分比
            'frame_count': self.frame_count,  # 总帧数
            'transitions': self.stats['transitions'],  # 转换次数
        }
    
    def reset(self):
        """
        重置可视化器
        
        功能描述：
        清空历史记录，重置所有状态和统计信息到初始值
        """
        self.history.clear()  # 清空历史记录
        self.current_flow = "unknown"  # 重置流程为未知
        self.current_state = "unknown"  # 重置状态为未知
        self.frame_count = 0  # 重置帧计数器
        self.stats = {  # 重置统计信息
            'transitions': 0,  # 转换次数清零
            'state_durations': {},  # 清空持续时间记录
            'last_state_time': time.time(),  # 重置状态时间
        }
        logger.info("已重置")  # 记录重置日志
