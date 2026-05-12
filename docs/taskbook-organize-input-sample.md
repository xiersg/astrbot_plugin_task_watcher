# 项目任务书（原始稿 · 供编排验证）

以下内容为**人工草稿**，用于在机器人中执行 `/watcher organize`，验证是否能稳定整理为 **YAML `version: 1` + `tree`**（含 `section` 分组、`task` 嵌套、`completion` / `description` / `contributors` / `paths` 等）。

---

## 一、目标说明

- 任务书需要**多层嵌套**：每一层用标题区分；其中 **「分组」不是可勾选任务**，只作目录结构。
- **任务点**下需能写：完成情况（含尚未完成部分）、描述、贡献；可选 **关联仓库路径** 便于和 diff 对齐。
- 网页端：目录在侧边、搜索同时筛目录与正文卡片。

---

## 二、AI端（本组为「非任务」分组，仅归类）

### 任务点：对话与指令解析

- **完成情况：** 已完成基础指令路由；尚未接入部分平台的事件差异处理。
- **描述：** 统一 watcher 指令组入口，处理 help / set_* / organize / check / watch / status / web。
- **贡献：** @xiersg
- **关联路径：** `main.py`

### 任务点：任务书 YAML 与提示词

- **完成情况：** ORGANIZE / ANALYSIS / UPDATE 三段 prompt 已对齐 YAML；待观察长任务书下 token 与截断策略。
- **描述：** `core/prompts.py` 引用 `TASKBOOK_YAML_SCHEMA_DOC`；check 流程中先 JSON 分析再合并回 YAML。
- **贡献：** （待补充）
- **关联路径：** `core/prompts.py`，`core/taskbook_schema.py`

### 任务点：Gist 与首次接入自动编排

- **完成情况：** `set_gist` 下载原文后会尝试自动 AI 编排并写回 Gist；失败时保留原文并提示手动 `organize`。
- **描述：** 与 `GistManager`、本地 `taskbook_content` 同步；需有效 Token 与聊天模型。
- **贡献：** （待补充）
- **关联路径：** `main.py`，`core/gist_manager.py`

---

## 三、后台（本组为「非任务」分组，仅归类）

### 1. GitHub 提交与 compare

- **完成情况：** 支持从 `last_synced_commit` 到 HEAD 的 compare；私有库需 token `repo` 权限说明已写入帮助。
- **描述：** `GitHubAPIClient` 拉取 compare、提交列表、关联 PR 摘要供分析 prompt。
- **贡献：** （待补充）
- **关联路径：** `core/github_client.py`

### 2. 变更摘要（省 token）

- **完成情况：** 按文件与 hunk 截断生成 `summary_text`，供 TASK_ANALYSIS 使用。
- **描述：** `core/change_digest.py` 与 `format_compare_for_prompt`。
- **贡献：** （待补充）
- **关联路径：** `core/change_digest.py`

### 3. 本地只读 Web

- **完成情况：** `/api/taskbook` 返回 `taskbook` 字段；静态页侧边栏目录 + 搜索筛选；仅识别 YAML v1。
- **描述：** `core/web_server.py`，`web/static/index.html`，`web/static/app.js`，`web/static/style.css`；js-yaml CDN 解析。
- **贡献：** （待补充）
- **关联路径：** `web/static/`

---

## 四、子任务嵌套示例（父任务下再拆子任务）

### 任务点：前端任务书面板

- **完成情况：** 主流程已通；需持续验证 Gist 返回内容含 BOM、version 类型差异时的兼容性。
- **描述：** 递归渲染 `section` / `task`，TOC 与卡片 `data-search` 检索。
- **贡献：** （待补充）
- **关联路径：** `web/static/app.js`

#### 子项：解析与容错

- **完成情况：** 已增加 `version` 宽松匹配、`kind` 小写化、去 BOM；待真机多浏览器回归。
- **描述：** `tryParseYamlTaskbook`、`nodeKind`、`stripLeadingFence`。
- **贡献：** （待补充）

#### 子项：布局与窄屏

- **完成情况：** 侧栏 + 主栏 flex；小屏改为上下堆叠。
- **描述：** `style.css` 中 `@media` 与 `.shell`。
- **贡献：** （待补充）

---

## 五、文档与依赖

### 任务点：README 与运行说明

- **完成情况：** 已改为仅描述 YAML v1 与真实指令列表。
- **描述：** 与插件实际命令一致，避免虚构指令。
- **贡献：** （待补充）
- **关联路径：** `README.md`

### 任务点：Python 依赖

- **完成情况：** 已包含 `PyYAML`。
- **描述：** `requirements.txt` 供 AstrBot 环境安装。
- **贡献：** （待补充）
- **关联路径：** `requirements.txt`

---

## 六、验收清单（编排后可对照）

1. 根节点为 `version: 1` 与 `tree:`。
2. 「AI端」「后台」等应为 `kind: section`，不是 `task`。
3. 每个可交付项为 `kind: task`，有稳定 `id`，含 `completion`、`description`、`contributors`（可空字符串），`paths` 按需出现。
4. 父子层级用 `children` 表达；叶子任务 `children: []`。
5. 与本文 **关联路径** 尽量写入对应 `task.paths`（逗号分隔多路径）。

---

*（本文件不提交到 Gist 亦可：将全文复制到当前会话任务书或任意文本，再执行 organize 做对比。）*
