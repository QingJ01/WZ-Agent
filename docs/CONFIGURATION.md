# 配置与环境变量

GUI 会自动为运行进程生成大部分环境变量。命令行运行时需要手动设置。

完整模板见项目根目录的 [.env.example](../.env.example)。

---

## 设备配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WZRY_DEVICE_MODE` | `auto` | 设备模式：`auto` / `android` / `mumu` |
| `WZRY_ADB_PATH` | `scrcpy/adb.exe`（存在时） | adb 可执行文件路径。未设置时优先使用项目根目录 `scrcpy/adb.exe`，再查找常见模拟器路径和系统 PATH |
| `WZRY_ADB_DEVICE` | — | ADB serial（真机序列号或 `127.0.0.1:7555`） |

如果项目根目录存在 `scrcpy/` 本地工具包，运行时会自动把该目录加入 `PATH`，让 ADB 和相关 DLL 全局可用。

---

## 运行控制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WZRY_AI_CONTROL_ENABLED` | `1` | 是否发送战斗操作到设备（GUI 默认关闭） |
| `WZRY_FRAME_SOURCE` | `scrcpy` | 视觉帧源模式：`scrcpy` 强制 scrcpy；`auto` 允许 scrcpy 失败后回退 ADB 截图；`adb` 直接使用 ADB 截图 |
| `WZRY_SCRCPY_FIRST_FRAME_TIMEOUT` | `10.0` | scrcpy 首帧等待秒数，范围 1 到 30 秒 |
| `WZRY_SCRCPY_SERVER_MODE` | `auto` | scrcpy server 来源：`auto` 优先使用项目 `scrcpy/scrcpy-server`；`local` 强制使用本地官方 server；`bundled` 使用 Python scrcpy-client 自带旧 server |
| `WZRY_INPUT_MODE` | GUI 自动设置 | Android 真机输入通道：`scrcpy` 使用 scrcpy control socket；`adb` 使用 ADB shell 输入 |
| `WZRY_DEBUG_WINDOWS` | `1` | 是否显示 OpenCV 调试窗口（GUI 默认关闭） |
| `WZRY_GUI_MINIMAP_PREVIEW` | `0` | 是否输出 GUI 小地图预览图片 |
| `WZRY_GUI_MINIMAP_PATH` | `logs/gui_preview/minimap.png` | 小地图预览图片路径 |

---

## 坐标与触摸

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WZRY_TOUCH_SIZE` | `2400x1080` | 游戏横屏坐标平面 |
| `WZRY_TOUCH_RAW_SIZE` | — | 真机原始触摸坐标范围（可自动检测） |
| `WZRY_TOUCH_RAW_TRANSFORM` | `identity` | 坐标变换：`identity` / `rotate_cw` / `rotate_ccw` / `flip_180` |
| `WZRY_SCRCPY_TOUCH_SIZE` | — | scrcpy 触控坐标平面。默认自动使用 scrcpy 首帧分辨率，例如 `1920x864` |
| `WZRY_SCRCPY_MOVE_HEARTBEAT_MS` | `80` | scrcpy 摇杆按住期间补发 MOVE 的间隔，避免长按被游戏侧判断为中断 |
| `WZRY_SCRCPY_MOVE_TOUCH_ID` | `1` | scrcpy 摇杆触点 ID |
| `WZRY_SCRCPY_TAP_TOUCH_ID` | `2` | scrcpy 技能/买装/升级点击触点 ID，需与摇杆触点不同 |
| `WZRY_ADB_MOVE_MODE` | `motion` | ADB 移动模式 |
| `WZRY_ADB_MOVE_SWIPE_MS` | `650` | ADB swipe 持续时间（毫秒） |

> 真机采集人工触摸时，如果 `WZRY_TOUCH_RAW_SIZE` 为空，运行时会尝试通过 `adb shell getevent -pl` 自动检测。

---

## 检测模型

| 变量 | 默认值 |
|------|--------|
| `WZRY_MODEL1_WEIGHTS` | `models/best_perfect.pt` |
| `WZRY_MODEL2_WEIGHTS` | `models/WZRY-health.pt` |
| `WZRY_MODEL3_WEIGHTS` | `models/wzry.pt` |

模型文件不随仓库发布，需要自行放置或通过环境变量指定路径。

---

## 学习与训练

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WZRY_DECISION_RECORDING` | `0` | 是否记录决策样本（GUI 默认开启） |
| `WZRY_DECISION_RECORD_DIR` | `logs/decision_records` | 自训练决策记录目录 |
| `WZRY_HUMAN_DEMO_ENABLED` | `0` | 是否采集人工示范 |
| `WZRY_HUMAN_DEMO_SOURCE` | 自动 | `adb_touch` 或 `windows_keyboard` |
| `WZRY_HUMAN_DEMO_DIR` | `logs/human_demos` | 人工示范目录 |
| `WZRY_HUMAN_POLICY_ENABLED` | `0` | 是否启用策略模型接管 |
| `WZRY_HUMAN_POLICY_PATH` | `models/human_policy.pt` | 策略模型路径 |
| `WZRY_HUMAN_POLICY_CONFIDENCE` | `0.80` | 策略接管置信度阈值 |

---

## 常用配置示例

### 真机只观察不操作

```powershell
$env:WZRY_DEVICE_MODE = "android"
$env:WZRY_ADB_DEVICE = "your-device-serial"
$env:WZRY_AI_CONTROL_ENABLED = "0"
$env:WZRY_DECISION_RECORDING = "1"
python Master_Auto.py
```

### 启用自训练策略模型

```powershell
$env:WZRY_HUMAN_POLICY_ENABLED = "1"
$env:WZRY_HUMAN_POLICY_PATH = "models/self_policy.pt"
$env:WZRY_HUMAN_POLICY_CONFIDENCE = "0.80"
python Master_Auto.py
```

### MuMu 模拟器调试模式

```powershell
$env:WZRY_DEVICE_MODE = "mumu"
$env:WZRY_AI_CONTROL_ENABLED = "0"
$env:WZRY_DEBUG_WINDOWS = "1"
$env:WZRY_GUI_MINIMAP_PREVIEW = "1"
python Master_Auto.py
```
