"""
基础配置模块 - 核心路径、阈值、模型配置

功能说明：
    本模块包含最基础的配置常量，不依赖其他模块。
    包括游戏模式、ADB配置、模型检测参数、移动逻辑、状态机等核心配置。

参数说明：
    无直接参数，通过导入变量使用

返回值说明：
    无直接返回值，提供各类基础配置常量
"""

# 导入os模块用于路径拼接
import os

# 导入shutil模块用于自动查找可执行文件
import shutil
from importlib import import_module

get_runtime_path_resolver = import_module(
    "wzry_ai.utils.resource_resolver"
).get_runtime_path_resolver

# ========== 自动启动开关 ==========
# AUTO_LAUNCH控制程序是否自动启动游戏流程
AUTO_LAUNCH = True  # True表示自动启动，False表示手动启动

# ========== 游戏模式配置 ==========
# 定义游戏运行的模式和参数
GAME_MODE = "ai"  # 游戏模式：'ai'表示人机模式
BATTLE_MODE = "5v5"  # 对战模式：5对5对战
V5_MODE = "ai"  # 5V5具体模式：'ai'表示人机模式, 'match'表示匹配模式
AI_BATTLE_MODE = "quick"  # 人机对战模式：'quick'表示快速模式
AI_DIFFICULTY = "bronze"  # 人机难度：'bronze'表示青铜难度

# ========== 辅助英雄配置 ==========
# DEFAULT_SUPPORT_HERO定义默认使用的辅助英雄
DEFAULT_SUPPORT_HERO = "瑶"  # 默认选择瑶作为辅助英雄

# ========== 选英雄优先级配置 ==========
# HERO_SELECT_PRIORITY列表定义了选英雄时的优先级顺序
HERO_SELECT_PRIORITY = [
    "yao",  # 第一优先级：瑶
    "caiwenji",  # 第二优先级：蔡文姬
    "mingshiyin",  # 第三优先级：明世隐
]
HERO_SELECT_MAX_RETRY = 2  # 选英雄最大重试次数

# ========== scrcpy 配置 ==========
# scrcpy是用于屏幕镜像和控制的工具，以下为相关配置
SCRCPY_MAX_SIZE = 1920  # 最大画面尺寸（像素）
SCRCPY_BITRATE = 8000000  # 视频比特率（bps），影响画质和流畅度
SCRCPY_MAX_FPS = 60  # 最大帧率（帧/秒）

# ========== ADB 设备配置 ==========
# ADB（Android Debug Bridge）用于与安卓模拟器通信
ADB_DEVICE_IP = "127.0.0.1"  # ADB设备IP地址（本地）
ADB_DEVICE_PORT = 7555  # ADB设备端口号
ADB_DEVICE_SERIAL = os.environ.get(
    "WZRY_ADB_DEVICE", f"{ADB_DEVICE_IP}:{ADB_DEVICE_PORT}"
)  # 完整设备序列号
DEVICE_MODE = os.environ.get("WZRY_DEVICE_MODE", "auto").strip().lower()


# ADB工具路径：按优先级自动查找，支持MuMu模拟器
# 查找顺序：常见模拟器安装路径 → 系统PATH → 回退到 "adb"
def _find_adb_path():
    """
    自动查找ADB可执行文件路径

    查找顺序：
        1. WZRY_ADB_PATH 环境变量
        2. 常见MuMu模拟器安装路径
        3. 系统PATH环境变量中的adb
        4. 都找不到则返回 "adb"（假设已加入PATH）
    """
    env_adb_path = os.environ.get("WZRY_ADB_PATH")
    if env_adb_path:
        return os.path.expanduser(os.path.expandvars(env_adb_path))

    _COMMON_ADB_PATHS = [
        # MuMu模拟器
        r"D:\MuMuPlayer\nx_main\adb.exe",
        r"C:\Program Files\MuMu\emulator\nemu\EmulatorShell\adb.exe",
        r"C:\Program Files (x86)\MuMu\emulator\nemu\EmulatorShell\adb.exe",
        os.path.join(os.path.expanduser("~"), "Desktop", "手机投屏", "adb.exe"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
    ]
    for path in _COMMON_ADB_PATHS:
        if os.path.isfile(path):
            return path
    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb
    return "adb"


ADB_PATH = _find_adb_path()  # 自动检测的ADB工具路径

# ========== 全局截图区域配置 ==========
# DEFAULT_REGIONS定义不同场景下的截图区域坐标和尺寸
DEFAULT_REGIONS = {
    "full": {"top": 0, "left": 0, "width": 1920, "height": 1080},  # 全屏截图
    "minimap": {"top": 0, "left": 0, "width": 360, "height": 380},  # 小地图区域
    "game": {"top": 0, "left": 0, "width": 1920, "height": 1080},  # 游戏画面区域
}

# ========== 模型检测配置 ==========
# YOLO模型检测的置信度阈值配置
MODEL1_CONFIDENCE_THRESHOLD = 0.80  # 模型1置信度阈值（英雄检测）
MODEL2_CONFIDENCE_THRESHOLD = 0.90  # 模型2置信度阈值（血条检测）
MODEL3_CONFIDENCE_THRESHOLD = 0.75  # 模型3置信度阈值（游戏事件检测）
YOLO_CONF = 0.5  # YOLO基础置信度
YOLO_IOU = 0.5  # IOU（交并比）阈值，用于NMS非极大值抑制

# ========== 帧率配置 ==========
# 控制程序运行帧率和相关时间参数
FPS = 60  # 目标帧率（帧/秒）
FRAME_TIME = 1 / FPS  # 每帧理论耗时（秒）
MODEL2_DISPLAY_SCALE = 0.35  # 模型2显示缩放比例

# ========== 模态2关键帧策略配置 ==========
# 模态2（血条检测）耗时较高（50-150ms），但血条变化相对缓慢，可以隔帧检测
M2_DETECT_INTERVAL = 2  # 模态2检测间隔（每N帧执行一次完整检测）
M3_DETECT_INTERVAL = 2  # 模态3检测间隔（每N帧检测一次）

# ========== 移动逻辑配置 ==========
# 控制AI移动行为的核心参数
FOLLOW_THRESHOLD = 50  # 跟随阈值：与目标距离小于此值时停止移动
SAFE_ENEMY_DISTANCE = 200  # 安全距离：与敌人保持的最小距离
AVOID_ENEMY_WEIGHT = 0.5  # 避敌权重：躲避敌人的影响系数
MINIMAP_SCALE_FACTOR = 12  # 小地图缩放因子
MOVE_INTERVAL = 0.03  # 移动指令发送间隔（秒）
MOVE_DEADZONE = 8  # 移动死区：小于此值的移动不处理
DIAGONAL_THRESHOLD = 20  # 对角线移动阈值
MOVE_SCALE_FACTOR = 10  # 移动缩放因子

# ========== 状态机配置 ==========
# 游戏状态检测和切换的相关参数
MENU_CHECK_INTERVAL = 0.033  # 菜单检测间隔（秒）
GAME_DETECTION_THRESHOLD = 1  # 游戏检测阈值
MENU_GONE_THRESHOLD = 5.0  # 菜单消失判定时间（秒）
STATE_STUCK_THRESHOLD = 6.0  # 状态卡住判定时间（秒）
STATE_STUCK_VERIFY_COUNT = 3  # 状态卡住验证次数
STATE_STUCK_VERIFY_INTERVAL = 2.0  # 状态卡住验证间隔（秒）

# ========== 字体配置 ==========
# 动态查找系统字体路径，支持不同Windows安装位置
FONT_PATH = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf")

# ========== 模型文件路径 ==========
# 定义YOLO模型权重文件和类别名称文件的路径
_PATH_RESOLVER = get_runtime_path_resolver()
PROJECT_ROOT = os.fspath(_PATH_RESOLVER.repo_root)
MODELS_DIR = os.fspath(_PATH_RESOLVER.models_dir())  # 模型文件目录
DATA_DIR = os.fspath(_PATH_RESOLVER.data_dir())  # 数据文件目录

MODEL1_WEIGHTS = os.fspath(
    os.environ.get("WZRY_MODEL1_WEIGHTS", "").strip()
    or _PATH_RESOLVER.resolve_model("best_perfect.pt")
)  # 模型1权重文件（英雄检测）
MODEL2_WEIGHTS = os.fspath(
    os.environ.get("WZRY_MODEL2_WEIGHTS", "").strip()
    or _PATH_RESOLVER.resolve_model("WZRY-health.pt")
)  # 模型2权重文件（血条检测）
MODEL3_WEIGHTS = os.fspath(
    os.environ.get("WZRY_MODEL3_WEIGHTS", "").strip()
    or _PATH_RESOLVER.resolve_model("wzry.pt")
)  # 模型3权重文件（游戏事件检测：击杀、被塔攻击等）
CLASS_NAMES_FILE = os.fspath(
    _PATH_RESOLVER.resolve_data("name_with_chinese.txt")
)  # 类别名称文件

# ========== 类别 ID 范围定义 ==========
# 定义不同阵营的类别ID范围，用于区分自己、队友和敌人
SELF_CLASS_ID_RANGE = (258, 386)  # 自己（绿色血条）的类别ID范围
TEAM_CLASS_ID_RANGE = (129, 257)  # 队友（蓝色血条）的类别ID范围
ENEMY_CLASS_ID_MIN = 0  # 敌人（红色血条）的最小类别ID

# ========== Model2: 血条类别 ==========
# MODEL2_CLASS_NAMES列表定义模型2检测的血条类别名称
MODEL2_CLASS_NAMES = [
    "g_self_health_health",  # 自己满血
    "b_team_health",  # 队友满血
    "b_low_health",  # 低血量
    "g_in_head_health",  # 头顶血条
    "g_in_head_low_health",  # 头顶低血条
    "r_enemy_health",  # 敌人血条
]

# ========== 网格地图配置 ==========
# 用于路径规划和移动控制的网格系统参数
GRID_SIZE = 210  # 网格大小（3倍精度：70×3）
CELL_SIZE = 5 / 3  # 单元格大小（像素），约1.667像素/格，3倍精度
G_CENTER_CACHE_DURATION = 0.5  # G点中心缓存持续时间（秒）
G_CENTER_MISS_THRESHOLD = 5  # G点中心丢失阈值

# ========== 召唤师技能配置 ==========
# F键绑定的召唤师技能类型："confluence"（汇流为兵）或 "heal"（治疗术）
ACTIVE_SUMMONER_F = "confluence"

# ========== 救赎/治疗术技能范围配置 ==========
# 定义救赎和治疗术技能的有效范围（与E技能范围保持一致）
REDEMPTION_RANGE = (599, 316, 496)  # 救赎技能范围（x, y, radius）
HEAL_RANGE = (599, 316, 496)  # 治疗术范围（x, y, radius）

# ========== 英雄身高偏移配置 ==========
# HERO_HEIGHT_OFFSET定义特定英雄的身高偏移量（用于技能瞄准）
# 格式：{"英雄名": (x_offset, y_offset)}
HERO_HEIGHT_OFFSET = {
    "瑶": (-11, 188),  # 瑶的身高偏移
    "明世隐": (0, 180),  # 明世隐的身高偏移
    "蔡文姬": (0, 188),  # 蔡文姬的身高偏移
}

# ========== 模态2血条坐标偏移配置 ==========
# 用于将血条中心（头顶位置）转换为脚下坐标（攻击/技能中心）
# 所有基于模态2血条坐标的逻辑都需要先应用此偏移
HEAD_TO_FEET_OFFSET = {
    "x": -10,  # X轴偏移：向左偏移10像素
    "y": 200,  # Y轴偏移：从头顶到脚下的垂直距离
}

# 通用偏移（用于敌人/队友，因为不知道具体英雄类型）
HEAD_TO_FEET_OFFSET_GENERIC = (-10, 188)  # 格式：(x偏移, y偏移)

# === 战斗系统配置 ===
THREAT_DISTANCE_WEIGHT = 0.6  # 威胁评估中距离权重
THREAT_COUNT_WEIGHT = 0.4  # 威胁评估中人数权重
THREAT_HIGH_THRESHOLD = 0.7  # 高威胁等级阈值
THREAT_MEDIUM_THRESHOLD = 0.25  # 中威胁等级阈值（降低以使单个近距离敌人触发MEDIUM）
FOCUS_FIRE_HP_DROP_RATE = 8.0  # 集火判定血量下降速率阈值（%/秒）
FOCUS_FIRE_TIME_WINDOW = 0.5  # 集火判定时间窗口（秒）
RETREAT_HP_THRESHOLD = 30  # 撤退血量阈值（%）
FIGHT_ENEMY_DISTANCE = 800  # 交战判定距离（像素）
SAFE_DISTANCE_FOR_RECALL = 1000  # 安全回城距离（像素，无敌人）

# ========== 小地图到全屏坐标转换配置 ==========
# 用于将小地图坐标距离转换为全屏像素距离
# 全屏 1920×1080 对应小地图摄像机视野约 101×57 像素
MINIMAP_TO_SCREEN = {
    "fov_w": 101,  # 摄像机视野宽度（小地图像素）
    "fov_h": 57,  # 摄像机视野高度（小地图像素）
    "screen_w": 1920,  # 全屏宽度
    "screen_h": 1080,  # 全屏高度
}
# 自动计算缩放比（避免硬编码）
MINIMAP_SCALE_X = MINIMAP_TO_SCREEN["screen_w"] / MINIMAP_TO_SCREEN["fov_w"]  # ≈19.0
MINIMAP_SCALE_Y = MINIMAP_TO_SCREEN["screen_h"] / MINIMAP_TO_SCREEN["fov_h"]  # ≈18.9

# ========== 地图预处理与寻路系统配置 ==========
HERO_INFLATION_RADIUS = 3          # 障碍物膨胀半径（网格单元，≈5 小地图像素）
PATHFINDING_MAX_ITERATIONS = 2000  # A* 最大迭代次数
CLEARANCE_PENALTY_THRESHOLD = 5.0  # 开始惩罚的间距阈值（网格单元）
CLEARANCE_PENALTY_WEIGHT = 0.5     # 间距惩罚权重
TURN_PENALTY = 0.3                 # 转向惩罚
PATH_CACHE_SIZE = 50               # 路径缓存大小
PATH_REPLAN_DISTANCE = 10          # 目标移动多少格触发重规划
SKELETON_MIN_CLEARANCE = 3.0       # 骨架提取最小间距
LOOKAHEAD_DISTANCE = 8             # 前瞻距离（网格单元，≈13 小地图像素）
CORRIDOR_TOLERANCE = 5             # 走廊容差（网格单元）
