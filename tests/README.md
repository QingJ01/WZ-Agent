# 测试说明

测试覆盖项目的核心纯逻辑和可离线验证的运行路径。默认测试不要求连接真实设备或准备完整模型权重。

---

## 运行全部测试

```powershell
python -m pytest -q
```

---

## 定向测试

| 测试范围 | 命令 |
|----------|------|
| GUI 和环境变量 | `python -m pytest tests/test_gui_launcher.py -q` |
| 训练逻辑 | `python -m pytest tests/test_human_policy_training.py tests/test_self_policy_training.py -q` |
| 人工示范和触摸坐标 | `python -m pytest tests/test_human_demo.py -q` |
| 瑶技能运行时 | `python -m pytest tests/test_yao_skill_runtime.py tests/test_yao_decision_brain.py -q` |

---

## 编写规范

- 单元测试优先覆盖**纯函数和边界条件**
- 真实设备相关测试**必须** mock 或 skip
- 新增训练逻辑必须覆盖数据读取、过滤、报告和质量门
- 新增 GUI 行为优先测试 helper，不直接依赖 Tk 主循环
- 修改坐标、分辨率或 ADB 输入逻辑时，必须补充回归测试

---

## 跳过项

部分 `services` 测试需要真实设备连接，会在无设备环境中自动跳过，避免 CI 阻塞。
