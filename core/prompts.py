"""
Prompt 模板模块

职责：
- 集中管理所有 AI 提示词模板
- 任务书编排、分析、更新的 prompt 定义
"""


TASKBOOK_ORGANIZE_PROMPT = """
你是一个项目管理专家。请将以下任务内容整理成结构清晰的 Markdown 格式任务书。

## 原始任务内容
{content}

## 输出要求
请生成标准 Markdown 格式的任务书，包含以下结构：

```markdown
# 项目任务书

## 任务清单

### 功能模块1
- [ ] 任务1名称 (关联文件路径) - 0%
- [ ] 任务2名称 (关联文件路径) - 0%

### 功能模块2
- [ ] 任务3名称 (关联文件路径) - 0%

## 说明
- 优先级：高/中/低
- 截止日期：YYYY-MM-DD（如已知）
- 负责人：（如已知）
```

## 格式规范
1. 使用 `- [ ]` 标记未开始任务，`- [x]` 标记已完成任务
2. 每个任务后括号内标注关联的文件路径
3. 任务后标注当前进度百分比（初始为 0%）
4. 按功能模块分组任务
5. 保持简洁，不要冗余描述

请直接输出整理后的 Markdown 任务书内容，不要添加任何说明文字。
"""


TASK_ANALYSIS_PROMPT = """你是一个代码任务分析专家。请根据代码变更分析任务完成情况。

## 仓库信息
名称: {repo_name}
描述: {repo_desc}

## 待分析任务 ({task_count}个)
{tasks_summary}

## 代码变更 ({file_count}个文件)
{changes_summary}

## 贡献统计 ({member_count}人)
{members_summary}

## 分析要求
根据文件变更分析每个任务的完成情况：

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
1. 文件路径完全匹配
2. 文件路径包含任务相关路径
3. 考虑作者贡献活跃度

## 输出格式
必须且只能返回JSON，不要其他文字：

```json
{{
  "tasks": [
    {{
      "name": "任务名称",
      "completion_rate": 数字0-100,
      "status": "completed|in_progress|not_started",
      "main_contributor": "作者姓名",
      "evidence": "简短的判断依据"
    }}
  ]
}}
```

## 重要
1. completion_rate 必须是纯数字，不要%
2. status 只能是: completed/in_progress/not_started
3. 只返回JSON，不要任何说明文字
"""


TASKBOOK_UPDATE_PROMPT = """请更新任务书，标记已完成的任务。

## 当前任务书
{current_content}

## 任务状态更新
{status_summary}

## 更新规则

### 格式保持
- Markdown格式: 保持原有的Markdown结构
- JSON格式: 保持原有的JSON结构

### 状态标记
- 100% completed: 使用 ✅ 或 [x]
- 1-99% in_progress: 使用 ⏳ 或 [ ] (百分比)
- 0% not_started: 使用 ❌ 或 [ ]

### 完成度显示
百分比模式: 直接显示数字 (如: "75%")

## 输出要求
**只返回更新后的任务书内容，不要任何说明文字。输出要求简洁，不要加入新的文本**
"""
