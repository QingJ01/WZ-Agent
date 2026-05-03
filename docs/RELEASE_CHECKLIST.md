# 发布检查清单

发布前按顺序逐项检查。

---

## 本地文件清理

- [ ] `logs/` 目录未提交
- [ ] `models/*.pt`、`*.onnx`、`*.engine` 未提交
- [ ] `scrcpy.zip` 未提交
- [ ] `.env` 未提交
- [ ] 无个人 ADB 路径、设备序列号、真实日志
- [ ] 内部计划文档（如 `docs/superpowers/`）已被 `.gitignore` 排除

---

## 文档完整性

- [ ] `README.md` 覆盖项目定位、安装、运行、训练和声明
- [ ] `ARCHITECTURE.md` 覆盖模块划分和扩展边界
- [ ] `docs/INSTALLATION.md` 可从零安装
- [ ] `docs/GUI.md` 可指导普通用户启动
- [ ] `docs/LEARNING.md` 准确描述当前模型能力和限制
- [ ] `docs/TROUBLESHOOTING.md` 覆盖常见错误
- [ ] `tests/README.md` 包含测试运行说明

---

## 测试通过

```powershell
python -m pytest -q
python -m py_compile scripts/train_human_policy.py scripts/train_self_policy.py src/wzry_ai/app/gui_launcher.py src/wzry_ai/learning/human_demo.py src/wzry_ai/learning/human_policy.py
```

---

## 法务与合规

- [ ] `LICENSE` 为 GPL-3.0-only 且随仓库发布
- [ ] 项目明确声明仅用于研究和学习
- [ ] 未上传无权分发的模型权重、截图或素材
- [ ] 未声称与游戏官方存在关系

---

## GitHub 仓库配置

| 项目 | 建议值 |
|------|--------|
| Description | `Computer vision and policy-learning automation research for Honor of Kings on Windows/ADB` |
| Topics | `computer-vision`, `adb`, `game-ai`, `pytorch`, `tkinter` |
| Release 附件 | 不附带个人日志和模型权重 |
