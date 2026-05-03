# 测试报告

最后验证日期：2026-05-03

## 命令

```powershell
python -m pytest -q
python -m py_compile scripts\train_human_policy.py scripts\train_self_policy.py src\wzry_ai\app\gui_launcher.py src\wzry_ai\learning\human_demo.py src\wzry_ai\learning\human_policy.py
```

## 结果

- `pytest`：284 passed, 1 skipped
- `py_compile`：通过

## 覆盖重点

- Android ADB 输入控制
- GUI 默认值、训练目录切换、运行环境构建
- 人工示范采集和触摸坐标转换
- 自训练与人工策略训练报告
- 策略模型运行前质量门
- 决策记录
- 资源路径解析
- 小地图寻路与移动运行时
- 瑶技能决策和运行时执行
- 模板匹配和状态检测辅助逻辑

## 已知限制

- 自动测试不启动真实游戏。
- 自动测试不依赖真实 Android 设备或 MuMu 窗口。
- 检测模型权重不随测试提供，相关行为以 mock 或纯逻辑方式验证。
