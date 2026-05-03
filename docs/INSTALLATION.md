# 安装与运行

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | 3.11+ |
| ADB | 系统 PATH 中或在 GUI 中指定路径 |
| 设备 | Android 真机（USB 调试）或 MuMu 模拟器（ADB 开启） |

---

## 第一步：安装 Python 依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

开发者额外安装：

```powershell
pip install -r requirements-dev.txt
```

---

## 第二步：安装 scrcpy 帧源（默认）

WZ-Agent 默认使用 `scrcpy` 强制帧源，不再静默回退到 ADB 截图。这样首帧失败时会直接暴露问题，避免看似在运行但实际帧率很低。

如果你把官方 scrcpy Windows 工具包解压到项目根目录的 `scrcpy/` 目录，WZ-Agent 会优先使用其中的 `adb.exe`，并在运行时自动把 `scrcpy/` 加入 `PATH`。该目录只在本地使用，不提交到 GitHub。

```powershell
pip install av==17.0.1
pip install scrcpy-client==0.4.1 --no-deps
```

> 如果遇到依赖冲突，可以在 GUI 的“视觉帧源模式”里临时切换到 `ADB 截图兼容模式`，或设置 `WZRY_FRAME_SOURCE=adb` 验证流程。

---

## 第三步：准备模型权重

将 YOLO 权重放入 `models/` 目录：

| 文件 | 用途 |
|------|------|
| `models/best_perfect.pt` | 小地图英雄检测 |
| `models/WZRY-health.pt` | 血条检测 |
| `models/wzry.pt` | 事件检测 |

也可通过环境变量指定自定义路径：

```powershell
$env:WZRY_MODEL1_WEIGHTS = "D:\models\best_perfect.pt"
$env:WZRY_MODEL2_WEIGHTS = "D:\models\WZRY-health.pt"
$env:WZRY_MODEL3_WEIGHTS = "D:\models\wzry.pt"
```

> 策略模型（`self_policy.pt`、`human_policy.pt`）由本项目训练生成。不建议使用来源不明的 `.pt` 文件。

---

## 第四步：启动

### GUI 方式（推荐）

```powershell
python GUI.py
```

**首次使用建议流程**：

1. 刷新 ADB 设备列表
2. 关闭「AI 自动操作」
3. 开启「小地图预览」和「决策记录」
4. 进入游戏，观察日志和小地图预览
5. 确认检测正常后再开启自动操作

### 命令行方式

```powershell
python Master_Auto.py
```

常用环境变量配置示例：

```powershell
$env:WZRY_DEVICE_MODE = "android"
$env:WZRY_ADB_PATH = "D:\tools\adb.exe"
$env:WZRY_ADB_DEVICE = "your-device-serial"
$env:WZRY_FRAME_SOURCE = "scrcpy"
$env:WZRY_SCRCPY_FIRST_FRAME_TIMEOUT = "10.0"
$env:WZRY_INPUT_MODE = "scrcpy"
$env:WZRY_AI_CONTROL_ENABLED = "0"
python Master_Auto.py
```

---

## 验证安装

```powershell
python -m pytest -q
```

> 测试通过只代表代码逻辑正确。真实运行还需要 ADB 连接、模型权重和游戏状态都正常。

---

## 下一步

- [GUI 使用说明](GUI.md) — 了解控制台各功能
- [配置与环境变量](CONFIGURATION.md) — 完整配置参考
- [排错指南](TROUBLESHOOTING.md) — 遇到问题时查阅
