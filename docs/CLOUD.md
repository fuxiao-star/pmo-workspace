# 免费云端部署与协作

正式系统使用 Cloudflare Workers + D1 免费套餐，固定入口：

- 表单：https://pmo-workspace.pmo-cloud.workers.dev/
- 团队管理：https://pmo-workspace.pmo-cloud.workers.dev/team
- 原 Sites 表单地址继续保留，接收地址切换到上述云端后台。

电脑关机不会停止云端服务。免费套餐有请求、数据库读取/写入及存储额度；不要启用付费套餐或承诺无限容量。AI 模型调用及未来附件存储不包含在本次改造内。

## 数据与权限

正式数据迁移后以云端 D1 为准。本机 data/pmo.sqlite3 及 data/backups 是迁移前备份，不会自动双向同步。开发者本机数据库仍用于开发，不要覆盖正式数据。

小组提交码只允许提交。团队成员登录可查看周报、管理小组提交码和分类。负责人登录另可创建、停用和重置团队成员访问码。负责人账号受到保护，不能从团队界面停用或重置；丢失访问码时由 Cloudflare 账号负责人离线恢复。

会话 8 小时，Cookie 设置 HttpOnly、Secure 和 SameSite=Strict；管理接口另验证 CSRF 和来源。停用或重置团队成员访问码会撤销该成员全部会话。迁移不复制本机会话。

负责人访问码仅保存在本机忽略目录 data/cloud-migration/owner-access.txt，请私下保管。旧团队成员码和小组提交码保留。任何访问码、真实 SQL、SQLite、会话和 OAuth 授权均不得提交 Git。

## 开发和部署

1. 在 cloud/ 运行 npm ci 安装固定版本 Wrangler。
2. 运行 python cloud/prepare.py（项目根目录）准备忽略的 public/ 构建产物。frontend/ 仍为表单唯一源代码。
3. 运行 python cloud/test_cloud.py 验证隔离的本机 Workers/D1 数据库；运行 python test_server.py 验证旧本机后端。
4. 生产配置是忽略的 cloud/wrangler.local.json。复制 wrangler.jsonc 后填入自己的 account_id 和 database_id；不要使用他人正式数据库开发。
5. 负责人授权后运行 node node_modules/wrangler/bin/wrangler.js d1 migrations apply DB --remote --config wrangler.local.json，然后 deploy --config wrangler.local.json。

cloud/prepare.py --export 仅用于首次迁移：先停止旧接收服务，生成一致性快照与私密 import.sql，并创建独立负责人码。不要重复导入、重复执行导出后覆盖已启用的负责人凭证。

schema 迁移必须追加，不能修改已应用版本。生产导入前检查库为空。import.sql 通过 Wrangler d1 execute --remote --file 上传，不能放入公开资源或 Git。会话和失败计数不迁移。

## 备份与恢复

负责人可在 cloud/ 执行：

    node node_modules/wrangler/bin/wrangler.js d1 export DB --remote --config wrangler.local.json --output ../data/backups/cloud-backup.sql

备份保存在忽略的 data/ 下。不要将备份发到 GitHub。恢复前先验证备份和目标库，在维护窗口操作；不要用旧本机快照直接覆盖正在使用的云端库。

代码仍通过 GitHub 功能分支、PR 审核合并。Git push 不等于部署，正式库不会随 Git 分支切换。只有负责人 Cloudflare 账号可以发布正式服务；不需要把账号密码发给同学。
