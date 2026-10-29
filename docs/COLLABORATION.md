# Git 分支协作

主仓库：https://github.com/fuxiao-star/pmo-workspace

公开的是源码，不是数据库或凭证。同学无需邀请即可 clone。要贡献修改，请 fork 到自己的 GitHub，再从功能分支提交 PR；公开可读不等于能直接 push 主仓库。

```sh
git clone https://github.com/YOUR-USERNAME/pmo-workspace.git
cd pmo-workspace
git remote add upstream https://github.com/fuxiao-star/pmo-workspace.git
git switch -c feature/your-task
# 修改代码并运行 python test_server.py
git add server.py  # 示例，只添加本次相关源码
git commit -m "Describe the change"
git push -u origin feature/your-task
```

随后在 GitHub 发起 PR：自己的功能分支 → `fuxiao-star/pmo-workspace:main`。负责人审核、运行测试、处理冲突后合并。

下次开发前先 `git fetch upstream`，切回 main 后 `git merge --ff-only upstream/main`，再新建功能分支。不要覆盖未提交工作或用强推代替冲突处理。

建议一人界面与报告呈现，一人接口、数据库及证据/Agent；接口变更先约定，再分别开发。每项完成的修改测试后 commit/push，不做每次键盘输入的自动同步。

正式数据只在负责人后端，团队用 HTTPS `/team` 登录入口共用。开发 clone 产生本地空库，不要覆盖正式库，不通过 Git 合并 SQLite。访问码须私下分发，不能放进 Git 或 PR。

正式部署由负责人完成。Git push 与服务部署是不同操作，后端改动需备份和重启。`frontend/` 是唯一网站源码；Sites 的原托管仓库只是发布暂存区。
