# 给同学 Codex 的接手提示词

打开 clone 的项目根目录，发送以下内容：

```text
请接手已有 PMO 项目，不要从零重建。主仓库：https://github.com/fuxiao-star/pmo-workspace 。
先读 README.md、AGENTS.md、docs/COLLABORATION.md，再检查源码。
定位 Python 3.10+，运行 python test_server.py，以仅本机模式运行 server.py，打开 http://127.0.0.1:8766 给我看。
本地空库属于开发环境，可用完整示例预览，不要冒充或覆盖正式数据库。
真实数据由负责人电脑的同一后端统一管理。我用负责人提供的 HTTPS /team 入口与独立团队访问码查看共享周报。不要把访问码写入 Git、日志或提示词文件，不索取负责人账号密码。
请协助我 fork 主仓库到自己的 GitHub，在 feature/... 分支开发，测试后 commit/push，最后向主仓库 main 发起 PR。不要向主仓库强推或自动覆盖他人修改。
当前有三语填报、SQLite 接收、提交码、总览/详情/历史、团队共享登录与项目分类。附件、证据审核、真实 Agent、OnePager 尚未实现。
先完成环境复现，再按我的下一步分工开发。我们通过源码、Git 提交、PR 和文档交接，不需要 AI 私有语言。
```

旧 `HANDOFF.md` 记录早期快照交接，若与 README 冲突，以 README 和本文件为准。
