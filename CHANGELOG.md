# Changelog

本文件供 AstrBot WebUI「更新日志」读取（`CHANGELOG.md`）。条目中的时间为对应 **commit 的提交时间（+0800）**，精确到分钟。

---

## v1.1.0 — 2026-05-15 17:22 +0800（发布）

### 发布与元数据

- 新增本 `CHANGELOG.md`，满足 AstrBot `/api/plugin/changelog` 对更新说明文件的检测。
- 插件版本号提升至 **v1.1.0**（`metadata.yaml` 与 `@register` 对齐）。

### 修复（与 aiohttp 3.13+ 兼容）

- **Web 路由**：移除与 `add_get` 重复的 `add_head` 注册，避免 `RuntimeError: Added route will never be executed, method HEAD is already registered`，确保 TaskWatcher 本地 HTTP 在 `web_server_port` 上可正常启动（问题与 **PR #8**、commit `2e72bc4` 一致；合并时间见下文）。

### 自 v1.0.0 以来仓库内主要变更（按时间倒序摘要）

以下依据 `git log` 与 GitHub **Merge pull request** 记录整理，便于从旧版一次性升级到 v1.1.0 时对照。

| 时间 (+0800) | 类型 | 说明 |
|--------------|------|------|
| 2026-05-15 15:05 | revert | `e39bc1a`：Revert「feat: 添加 GitHub API 超时处理」（经 **PR #9** `revert/github-api-timeout-handling` 合并）。 |
| 2026-05-14 16:09 | merge | **PR #8** `fix/head`：修复 Web 服务器在 aiohttp 3.13+ 下 `HEAD` 重复注册导致启动失败（`ac59e25`）。 |
| 2026-05-14 15:58 | fix | `2e72bc4`：修复 Web 服务器 HEAD 请求 / 路由注册问题。 |
| 2026-05-14 14:06 | merge | **PR #7** `feat/github-api-timeout-handling`：合并 GitHub API 超时相关改动（`f337755`）。 |
| 2026-05-14 14:03 | feat | `1e30cc1`：添加 GitHub API 超时处理（后续已被上表 revert 撤销，以当前默认分支为准）。 |
| 2026-05-13 15:33 | merge | **PR #6** `fix/web-panel-remote-access`：Web 只读面板远程访问相关修复（`712d94b`）。 |
| 2026-05-13 15:24 | fix | `05b3bdc`：修复任务书网络穿透问题。 |
| 2026-05-12 19:47 | merge | **PR #5** `feat/contrib-heatmap-tasks-edit-web`：贡献热力图、任务编辑与 Web 等（`be76bdc`）。 |
| 2026-05-12 19:43 | fix | `b4c0678`：贡献热力图约 90 天分页与图例色；完成情况/贡献圆角标签。 |
| 2026-05-12 19:32 | feat | `fdae4b8`：新增贡献热力图展示。 |
| 2026-05-12 19:04 | feat | `fe2e624`：新增任务节点编辑命令，并更新 Web 端头像展示。 |
| 2026-05-12 18:41 | merge | **PR #4** `fit/web-cache-static-ui`：Web 静态缓存、本地 js-yaml、UI 加固、`web_new` 等（`79398f6`）。 |
| 2026-05-12 18:37 | fix | `ff7c131`：web no-cache headers、local js-yaml、UI hardening、web_new。 |
| 2026-05-12 17:51 | merge | **PR #3** `feat/yaml-taskbook-gist-and-web`：YAML 任务书、Gist 自动编排、Web 侧栏与 compare 摘要等（`57680aa`）。 |
| 2026-05-12 17:45 | feat | `1e09d40`：YAML taskbook schema、Gist auto-organize、web sidebar and compare digest。 |

---

## v1.0.0 — 初始版本线

- 早期 TaskWatcher 能力：`feat!: 破坏性更改`（`2fccf5e`）及此前提交；本 CHANGELOG 自 **v1.1.0** 起维护，v1.0.0 仅作占位，细节以 `README.md` 与仓库历史为准。
