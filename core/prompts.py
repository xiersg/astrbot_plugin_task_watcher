"""
Prompt 模板模块

职责：
- 集中管理所有 AI 提示词模板
- 任务书编排、分析、更新的 prompt 定义

任务书 YAML 流水线（与 main.py 中 /watcher check 一致）：
1. TASKBOOK_ORGANIZE：把任意原始文字整理成合法 YAML（version:1 + tree，含 section/task、paths 等）。
2. TASK_ANALYSIS：模型只读「当前 YAML 片段 + PR + diff」，输出 JSON；每条任务含 task_id（对应 YAML 里
   task.id）、完成度、以及是否要把一行进展追加进 YAML 的 completion（completion_log_line）。
3. TASKBOOK_UPDATE：把上一步 JSON 合并进完整 YAML（按 task_id 定位节点，改 completion / contributors），
   不再让模型自由发挥成 Markdown。paths 用于把文件变更和任务节点对齐；contributors 对应 YAML 字段。
4. TASKBOOK_TASKS_EDIT（/watcher tasks_edit）：按用户自然语言增删任务点，输出完整新 YAML。
"""

from .taskbook_schema import TASKBOOK_YAML_SCHEMA_DOC


TASKBOOK_ORGANIZE_PROMPT = (
    """
你是一个项目管理专家。请将以下原始任务内容整理为 **YAML 任务书**（version: 1），供网页与插件解析。

## 原始任务内容
{content}

"""
    + TASKBOOK_YAML_SCHEMA_DOC
    + """

## 编排要求

1. 用 `kind: section` 表示「非任务」分组（如「AI端」「后台」），标题写在 `title`。
2. 具体可交付项一律用 `kind: task`，可放在 section 的 `children` 下，也可嵌套 `children` 表示子任务。
3. 为每个 task 生成全局唯一 `id`（英文/数字/下划线）。
4. `completion` / `description` / `contributors` / `paths` 尚无信息时用空字符串 `""`。
5. 第一行必须是 `version: 1`，随后 `tree:`，不要其它顶层键。

请直接输出完整 YAML 正文，不要 Markdown 代码围栏，不要附加说明。
"""
)


TASK_ANALYSIS_PROMPT = """你是一个代码任务分析专家。请根据代码变更分析任务完成情况。

## 分析基准时刻（任务书追加日志时必须使用）
{current_time_zh}
（向 YAML 中对应 `task` 的 `completion` 字段 **追加** 新进展时，每条必须以 `【{current_time_zh}】` 为前缀，精确到小时。）

## 仓库信息
名称: {repo_name}
描述: {repo_desc}

## 待分析任务书（YAML，约 {task_count} 个 task 节点；含嵌套）
{tasks_summary}

## 合并请求 PR（成员应在标题与描述中写明对应任务点；用于匹配任务书条目与贡献）
{pr_context}

## 代码变更 ({file_count}个文件，按路径列出；每文件附 unified diff 的 patch 片段，已截断以省 token)
{changes_summary}

## 贡献统计 ({member_count}人)
{members_summary}

## 关于「review」的常见层次（供你判断变更性质，不必在 JSON 中复述）
- **人工 Code Review**：人读 diff/PR，关注逻辑、边界、安全、可读性。
- **Diff / 提交粒度审阅**：按 commit 或 compare 视图看文件级、块级变更。
- **自动化审阅**：Lint、类型检查、单测、SAST 等规则驱动。
- **策略/噪声过滤**：区分「影响产品行为的实质变更」与「维护性、配置、文案微调」。

## 分析要求
根据文件变更分析每个任务的完成情况。

### 完成度计算规则
- 相关文件有修改/新增: +5-10% (根据变更数量)
- 相关文件有删除: -5% (可能重构)
- 无相关变更: 保持0%或当前值
- 完成度范围: 0-100%

### 状态判断
- 100%: "completed"
- 1-99%: "in_progress"
- 0%: "not_started"

### 匹配优先级
1. **PR 标题/描述** 中声明的任务点、条目编号或关键词（与成员约定一致时优先）。
2. 文件路径与任务 YAML 中 `paths` 字段（逗号分隔）匹配。
3. 文件路径包含 `paths` 中任一路径片段。
4. 考虑作者贡献活跃度；`main_contributor` 可优先采用 PR 作者或提交说明中的责任人。

### 任务书「完成情况」噪声控制（极其重要）
下列类型通常 **不应** 再写入任务书条目的长篇详情（`taskbook_detail_mode` 取 `skip`，且 `completion_log_line` 必须为空字符串 `""`）：
- 仅配置/常量微调：如改端口、改 `web_url`、开关默认值、环境变量名不变义等 **未改变业务语义** 的改动。
- 纯注释、排版、换行、无行为变化的格式化；仅 README/文档措辞微调且与条目目标无关。
- 与某条目 `paths` 明显无关的边角文件改动。

若变更 **确实推进** 了该条目对应能力（新逻辑、可测行为、接口契约、关键 bug 修复等），则 `taskbook_detail_mode` 取 `append`，并在 `completion_log_line` 写 **一条** 简洁中文记录，且 **必须以** `【{current_time_zh}】` **开头**，后接事实描述（可引用路径/行为），不要堆砌无关文件列表。若 PR 描述中已写明完成人/协作人，可写入 `contributors` 字段建议或并入 `completion_log_line`。

## 输出格式
必须且只能返回 JSON，不要其他文字：

```json
{{
  "tasks": [
    {{
      "task_id": "YAML 中对应 task 的 id；若无法确定可填空字符串",
      "name": "任务标题，与 YAML 中该 task 的 title 一致或为其父路径+标题便于人工核对",
      "completion_rate": 数字0-100,
      "status": "completed|in_progress|not_started",
      "main_contributor": "作者姓名或空字符串",
      "evidence": "简短技术判断依据",
      "taskbook_detail_mode": "skip 或 append",
      "completion_log_line": "若 append：必须以【{current_time_zh}】开头的单行追加文案；若 skip：必须为空字符串"
    }}
  ]
}}
```

## 重要
1. completion_rate 必须是纯数字，不要%
2. status 只能是: completed/in_progress/not_started
3. taskbook_detail_mode 只能是 skip 或 append
4. 优先用 `task_id` 定位 YAML 节点；若为空则用 `name` 与 `title` 匹配（允许「分组/子标题」形式）。
5. 只返回 JSON，不要任何说明文字
"""


TASKBOOK_UPDATE_PROMPT = (
    """请根据「任务状态更新」改写任务书，并 **严格保持** YAML 结构与既有 `id`（除非条目被合并/删除且需整体重排时，仍须尽量保留原 id）。

## 当前任务书（YAML）
{current_content}

## 任务状态更新（JSON，含 taskbook_detail_mode / completion_log_line）
{status_summary}

## 本次分析基准时刻（写入详情时必须一致）
{current_time_zh}
凡向某 `task` 的 `completion` 字段 **追加** 新进展，每条必须以 `【{current_time_zh}】` 开头（精确到小时，与 JSON 中 completion_log_line 前缀一致）。禁止省略时间戳。

"""
    + TASKBOOK_YAML_SCHEMA_DOC
    + """

## 与 JSON 对齐的更新规则（极其重要）

0. 若 JSON 的推理依据中包含 **PR 标题/描述**，更新时 **优先** 将 `completion_log_line` / `main_contributor` 与 PR 中声明的任务点、贡献者对齐；仍须遵守每条 `completion_log_line` 的时间戳前缀规则。

1. 对上表 JSON 中 **每一条** `tasks[]`：
   - 用 `task_id` 在 YAML `tree` 中定位 `kind: task` 节点；若 `task_id` 为空，则用 `name` 与节点的 `title` 匹配（允许路径式名称）。
   - 若 `taskbook_detail_mode` 为 **skip**：**不要**因本次微调去改写或拉长该节点的 `completion`；保持原文。
   - 若 `taskbook_detail_mode` 为 **append** 且 `completion_log_line` 非空：将该字符串 **追加**到对应节点的 `completion`（已是 `【{current_time_zh}】` 开头）；若已有内容，用换行分隔多条，**每条各自带时间戳**。
   - 若 `main_contributor` 非空且与现有 `contributors` 明显相关，可 **追加或合并**到 `contributors`（换行或顿号分隔），不要删除既有贡献记录。
2. 不得把 `skip` 条目的 evidence 抄进 `completion`。
3. `kind: section` 节点仅作分组，不要为其写 `completion` 等业务字段（除非原稿已有且需保留）。

## 输出要求

**只返回更新后的完整 YAML 正文**（第一行 `version: 1`），不要 Markdown 代码围栏，不要任何说明文字。
"""
)


TASKBOOK_TASKS_EDIT_PROMPT = (
    """你是任务书维护助手，仅根据「编辑说明」修改 YAML 任务书（version: 1）。

## 当前任务书（YAML）
{current_content}

## 用户编辑说明（用自然语言描述：要新增/删除哪些任务点、挂到哪个分组下、id/title/paths 等）
{instruction}

## 必须遵守
1. 输出 **完整** YAML 正文（第一行 `version: 1`，随后 `tree:`），不要用 Markdown 代码围栏，不要附加说明。
2. **仅**按说明增删或调整 `kind: task` 与必要的 `kind: section` 结构；不要无故清空与说明无关节点的 `completion` / `description`。
3. 所有 `task`/`section` 的 `id` 全文唯一；新建 `task` 时 `completion`/`description`/`contributors`/`paths` 若无信息用 `""`；无子节点时 `children: []`。
4. 删除任务时移除该 `task` 节点整棵（含其 `children`）。
5. 不要添加未约定的顶层键。

"""
    + TASKBOOK_YAML_SCHEMA_DOC
    + """

请直接输出修改后的 YAML。
"""
)
