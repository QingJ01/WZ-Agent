# 贡献指南

感谢你愿意改进这个项目。提交代码前请确认改动范围清晰、测试可运行、不引入本地隐私数据。

---

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements-dev.txt
```

---

## 分支与提交

- 一个分支只做一类改动
- 不要混入日志、模型、训练数据、截图和本地配置
- 修改运行逻辑时同步更新文档和测试
- 修改 GUI 文案时确认中文正常显示

---

## 测试要求

提交前必须通过：

```powershell
python -m pytest -q
```

涉及训练、GUI、坐标或策略模型质量门的改动，额外运行：

```powershell
python -m pytest tests/test_gui_launcher.py tests/test_human_demo.py tests/test_human_policy_training.py tests/test_self_policy_training.py tests/test_human_policy_runtime.py -q
```

---

## 代码规范

- 业务逻辑放在 `src/wzry_ai/` 内，根目录入口保持薄封装
- 不在运行时代码中写死个人绝对路径
- 坐标、分辨率、触摸变换相关改动**必须**有测试
- 训练脚本**必须**输出训练报告
- 新增环境变量时更新 [docs/CONFIGURATION.md](docs/CONFIGURATION.md) 和 [.env.example](.env.example)

---

## 文档规范

- 用户文档放在 `README.md` 或 `docs/`
- 内部计划、个人设备信息和调试记录不提交
- 保持文档与代码同步

---

## 合规要求

- 不提交无权公开分发的模型、游戏截图、素材、账号信息或第三方二进制文件
- 提交贡献即表示同意将贡献内容按本项目的 GPL-3.0-only 许可证发布
