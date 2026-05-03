# 排错指南

---

## GUI 启动失败

**检查依赖安装**：

```powershell
pip install -r requirements.txt
python GUI.py
```

如果提示找不到 `wzry_ai`，确认命令在仓库根目录执行。

---

## ADB 设备为空

运行 `adb devices -l` 检查设备列表。

**真机**：
- 确认 USB 调试已开启
- 手机上已确认调试授权弹窗
- 优先使用项目根目录 `scrcpy/adb.exe`；运行时会自动把 `scrcpy/` 加入 `PATH`，避免多版本 ADB 混用

**MuMu**：
- 确认模拟器已启动
- ADB 端口可连接（通常 `127.0.0.1:7555`）
- GUI 中选择 MuMu ADB 模式或手动填写 serial

---

## 找不到 MuMu 窗口

- 如果使用真机，不需要 MuMu 窗口 — 选择「真机 ADB」模式
- 确认模拟器窗口可见且标题包含 MuMu
- 确认分辨率和模板资源匹配

---

## scrcpy 黑屏或首帧失败

默认 `WZRY_FRAME_SOURCE=scrcpy`，首帧失败时不会再静默回退到 ADB 截图，日志中会出现：

```
scrcpy 在 10.0 秒内未收到有效首帧，已禁止回退 ADB 截图
```

优先检查：

```powershell
pip install av==17.0.1
pip install scrcpy-client==0.4.1 --no-deps
```

同时确认手机已授权 USB 调试、屏幕已解锁、项目根目录存在 `scrcpy/adb.exe` 和 `scrcpy/scrcpy-server`。Android 16 等新系统需要本地官方 `scrcpy-server`，否则 Python scrcpy-client 自带的旧 server 可能连上但不出首帧。如果只是临时验证流程，可在 GUI 中把“视觉帧源模式”切换为 `scrcpy 优先，失败后 ADB 截图`，或设置：

```powershell
$env:WZRY_FRAME_SOURCE = "auto"
$env:WZRY_INPUT_MODE = "adb"
```

---

## 日志乱码

在 PowerShell 中设置编码：

```powershell
$env:PYTHONIOENCODING = "utf-8:replace"
$env:PYTHONUTF8 = "1"
```

GUI 启动的子进程已默认设置这两个变量。

---

## EVE / EVE Check 弹窗

这是 OpenCV 调试窗口，用于观察检测画面。普通运行不需要，GUI 中默认关闭「显示 EVE / EVE Check 调试窗口」。

---

## 训练成功但模型不可启用

查看训练报告最后几行，常见原因：

| 原因 | 解决方法 |
|------|----------|
| `no_op` 占比过高 | 数据中大部分是不操作，重点采集技能/攻击动作 |
| 可执行动作样本过少 | 数据主要是 `move`/`touch`，需要采集更多技能动作 |
| 触摸坐标越界 | 人工示范时坐标映射错误，清理旧数据重新录制 |
| 某些动作只有几条 | 继续采集缺失动作的样本 |

---

## 人工示范没有生成 JSONL

逐项检查：

1. GUI 中是否勾选「启用示范数据采集」
2. 运行时是否已进入对局并产生战斗状态
3. 真机模式：`adb shell getevent -lt` 是否能读到数据
4. MuMu 模式：是否安装 `pywin32` 且能读取键盘状态

---

## 真机触摸坐标不对

默认配置：

```
WZRY_TOUCH_SIZE=2400x1080
WZRY_TOUCH_RAW_TRANSFORM=identity
```

如果训练报告提示大量坐标越界，说明原始触摸坐标未正确转换。解决方法：

- 在 GUI 中填写原始触摸分辨率（如 `10800x24000`）
- 或清空 `WZRY_TOUCH_RAW_SIZE` 让运行时自动检测

---

## AI 不操作

按优先级逐项排查：

1. GUI 中「AI 自动操作」是否已启用
2. 当前是否在对局中，检测系统能否识别血条和小地图
3. 策略模型是否被质量门拒绝
4. 规则策略是否选择了 `no_op` 或 `stay_attached`
5. 日志是否显示设备输入失败

> 如果只是想录数据，AI 不操作是正常的 — 保持 `WZRY_AI_CONTROL_ENABLED=0` 即可。
