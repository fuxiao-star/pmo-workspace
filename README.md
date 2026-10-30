# PMO Workspace

七个学期项目的周报管理，另管理第八组 PMO 自身项目。

## 云端正式版

正式版已迁移至 Cloudflare Workers + D1，固定入口 https://pmo-workspace.pmo-cloud.workers.dev/ ，管理入口为 /team。部署、迁移、权限和备份见 [docs/CLOUD.md](docs/CLOUD.md)。下方本机服务和临时隧道保留作为开发/历史运行方式；迁移完成后以云端 D1 为正式数据源，本机 SQLite 保留备份，不自动双向同步。

## 两人协作

- 代码：此 GitHub 仓库是统一来源；同学 fork 后在 feature/... 分支开发，通过 PR 合并。
- 正式数据：云端迁移后以 D1 为准；团队登录同一个 HTTPS /team 工作台查看相同周报和分类，不直接跨网络打开 SQLite 文件。
- 开发数据：clone 后首次启动建立本地空库，可用完整示例预览。不要用开发库覆盖正式库。
- 每项完成修改测试后 commit/push，Git 不会自动同步每次键盘输入；数据库不进入 Git。

## 本机运行

需要 Python 3.10+，仅使用标准库，无 pip 依赖。运行 `python server.py`，Windows 可用 `start-local.cmd`。

- 填报：http://127.0.0.1:8765
- 负责人管理：http://127.0.0.1:8766

## 外网与团队共享数据库

负责人电脑安装 Cloudflare 官方工具后运行 `python start.py` 或 `start-pmo.cmd`。
Windows x64 可用 `python tools/download_cloudflared.py` 下载官方程序（不进 Git）。

- 程序显示的 HTTPS 临时网址 `/` 供各组填报，`/team` 供团队登录。
- 本机管理页“接收与小组设置”创建独立团队访问码，私下发给同学。团队码可以查看真实报告、管理小组提交码和分类，不能当作公开提交码分享。
- 只有本机负责人可以创建、停用或重置团队访问码。
- 使用 HttpOnly、Secure、SameSite Cookie，登录会话为 8 小时，停用成员会撤销现有会话。
- 电脑和服务需保持在线；临时隧道重启地址会改变。固定入口需配置命名隧道/域名或部署到长期在线服务器。

## 已完成与未完成

已实现：德中英填报、草稿、直接提交、回执、去重、提交码生命周期、项目总览/详情/历史、分区报告、打印 PDF、共享项目分类、受保护的团队访问。

未实现：附件上传与证据审核、真实 AI Agent、报告审核/OnePager、教师和项目组的细分阅读权限。不要将计划当作已实现功能。

## 文件

- frontend/：网站源码（index.html、样式、翻译与提交脚本）。
- server.py：API、SQLite、管理员和团队会话。
- admin.html、team-login.html：PMO 管理页与团队登录。
- start.py：服务与临时 HTTPS 隧道。
- test_server.py：隔离集成测试。
- docs/：分支协作与同学 Codex 接手说明。
- tools/：工具下载和托管前端准备。
- data/、bin/：运行时数据库与下载工具，不进 Git。

## 测试

运行 `python test_server.py`。测试使用临时数据库和随机本机端口，不改正式数据。

## 托管发布

当前已发布表单：https://pmo-team-report-template.palevenus33.chatgpt.site

GitHub 与 Sites 的托管仓库不同。frontend/ 是唯一网站源代码；由负责人通过 Sites 正式发布流程更新托管站点。tools/sync_hosted_frontend.py 只准备发布文件，不自动部署。

## 交接

请读 docs/TEAM_HANDOFF.md、docs/COLLABORATION.md 和 AGENTS.md。
旧 HANDOFF.md 只作为早期快照的历史记录，以本 README 为准。
不要把包含真实数据库的旧交接包上传到公开仓库。

参考：https://www.sqlite.org/useovernet.html
