"""
AI 智能分析器模块

职责：
- 利用大模型深度分析代码变更和任务关联
- 构造结构化的分析Prompt
- 解析和验证AI返回结果

设计模式：
- 策略模式：不同的AI分析策略
- 适配器模式：适配不同的AI模型
"""

import re
import json
from typing import Dict, List, Any
from astrbot.api import logger


class AIAnalyzer:
    """AI 智能分析器"""

    def __init__(self, context, use_detailed_analysis: bool = True):
        """
        初始化AI分析器

        Args:
            context: AstrBot 上下文对象
            use_detailed_analysis: 是否使用详细分析模式
        """
        self.context = context
        self.use_detailed_analysis = use_detailed_analysis

    async def analyze_tasks(self, tasks: List[Dict], file_changes: Dict,
                         member_contributions: Dict, repo_info: Dict) -> List[Dict]:
        """
        使用AI分析任务完成情况

        Args:
            tasks: 任务列表
            file_changes: 文件变更信息
            member_contributions: 成员贡献统计
            repo_info: 仓库信息

        Returns:
            分析后的任务列表

        Raises:
            Exception: AI分析失败时抛出异常
        """
        try:
            # 1. 获取当前会话的聊天模型ID
            umo = f"github:{repo_info.get('full_name', 'unknown')}"
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)

            if not provider_id:
                logger.warning("未找到聊天模型，AI分析失败")
                raise ValueError("未配置聊天模型")

            # 2. 构造分析Prompt
            prompt = self._construct_analysis_prompt(
                tasks, file_changes, member_contributions, repo_info
            )

            logger.info(f"调用AI分析任务完成情况，任务数: {len(tasks)}, 文件变更数: {len(file_changes)}")

            # 3. 调用LLM分析
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )

            # 4. 解析AI返回的结果
            ai_result_text = llm_resp.completion_text
            logger.debug(f"AI分析返回结果: {ai_result_text[:500]}...")

            # 5. 提取JSON部分
            validated_tasks = self._parse_ai_result(ai_result_text, tasks)

            logger.info(f"AI分析完成，处理了{len(validated_tasks)}个任务")
            return validated_tasks

        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            raise Exception(f"AI分析失败: {str(e)}")

    def _construct_analysis_prompt(self, tasks: List[Dict], file_changes: Dict,
                                member_contributions: Dict, repo_info: Dict) -> str:
        """
        构造AI分析Prompt

        Args:
            tasks: 任务列表
            file_changes: 文件变更信息
            member_contributions: 成员贡献统计
            repo_info: 仓库信息

        Returns:
            分析Prompt字符串
        """
        # 限制输出数量，避免token超限
        max_tasks = min(len(tasks), 10)
        max_files = min(len(file_changes), 15)
        max_members = min(len(member_contributions), 5)

        # 简化的任务摘要
        tasks_summary = "\n".join([
            f"{i+1}. {task.get('name', task.get('title', 'Unknown'))} "
            f"(进度: {task.get('completion_rate', 0)}%, "
            f"关联: {task.get('related_path', 'N/A')})"
            for i, task in enumerate(tasks[:max_tasks])
        ])

        # 简化的文件变更摘要
        changes_summary = "\n".join([
            f"- {file_path} ({change.get('status', 'unknown')}) "
            f"by {change.get('author', 'unknown')}, "
            f"{change.get('changes', 0)} changes"
            for file_path, change in list(file_changes.items())[:max_files]
        ])

        # 简化的成员贡献摘要
        members_summary = "\n".join([
            f"- {name}: {count} commits"
            for name, count in sorted(member_contributions.items(),
                                       key=lambda x: x[1], reverse=True)[:max_members]
        ])

        # 构造优化的Prompt
        prompt = f"""你是一个代码任务分析专家。请根据代码变更分析任务完成情况。

## 仓库信息
名称: {repo_info.get('name', 'Unknown')}
描述: {repo_info.get('description', 'No description')}

## 待分析任务 ({max_tasks}个)
{tasks_summary}

## 代码变更 ({max_files}个文件)
{changes_summary}

## 贡献统计 ({max_members}人)
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

        return prompt

    def _parse_ai_result(self, ai_result_text: str, original_tasks: List[Dict]) -> List[Dict]:
        """
        解析AI返回的结果

        Args:
            ai_result_text: AI返回的文本
            original_tasks: 原始任务列表

        Returns:
            验证后的任务列表

        Raises:
            ValueError: AI返回格式错误时抛出异常
        """
        # 尝试提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', ai_result_text)

        if not json_match:
            raise ValueError("AI返回结果中未找到有效的JSON格式")

        json_str = json_match.group(0)

        try:
            ai_result = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI返回的JSON格式错误: {str(e)}")

        # 验证和补充AI分析结果
        validated_tasks = []

        for ai_task in ai_result.get('tasks', []):
            task_name = ai_task.get('name', '')

            # 找到对应的原始任务
            original_task = None
            for task in original_tasks:
                if task['name'] == task_name:
                    original_task = task
                    break

            if not original_task:
                logger.warning(f"AI分析结果中的任务 '{task_name}' 在原始任务中未找到")
                continue

            # 验证AI返回的数据
            completion_rate = ai_task.get('completion_rate', original_task.get('completion_rate', 0))
            status = ai_task.get('status', 'not_started')
            main_contributor = ai_task.get('main_contributor', '未分配')
            evidence = ai_task.get('evidence', '')

            # 验证数据类型和范围
            if not isinstance(completion_rate, (int, float)):
                logger.warning(f"任务 '{task_name}' 的 completion_rate 不是数字: {completion_rate}，使用原值")
                completion_rate = original_task.get('completion_rate', 0)

            completion_rate = max(0, min(100, int(completion_rate)))

            if status not in ['completed', 'in_progress', 'not_started']:
                logger.warning(f"任务 '{task_name}' 的 status 值无效: {status}，使用默认值")
                status = 'not_started'

            # 合并AI分析结果和原始任务信息
            validated_task = {
                'name': original_task['name'],
                'completion_rate': completion_rate,
                'status': status,
                'main_contributor': main_contributor,
                'evidence': evidence,
                'related_path': original_task.get('related_path', None)
            }

            validated_tasks.append(validated_task)

        return validated_tasks

    async def update_task_book_with_ai(self, current_content: str, task_status: List[Dict]) -> str:
        """
        使用AI更新任务书内容

        Args:
            current_content: 当前任务书内容
            task_status: 任务状态列表

        Returns:
            更新后的任务书内容

        Raises:
            Exception: AI更新失败时抛出异常
        """
        try:
            # 简化的任务状态摘要
            status_summary = "\n".join([
                f"- {task['name']}: {task['completion_rate']}% "
                f"({task['status']}) by {task.get('main_contributor', 'N/A')}"
                for task in task_status[:10]  # 限制数量
            ])

            # 构造优化的更新Prompt
            prompt = f"""请更新任务书，标记已完成的任务。

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
**只返回更新后的任务书内容，不要任何说明文字。**
"""

            # 获取聊天模型ID
            provider_id = await self.context.get_current_chat_provider_id(umo="task_book_update")

            if not provider_id:
                logger.warning("未找到聊天模型，无法使用AI更新任务书")
                return current_content

            # 调用AI更新
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )

            updated_content = llm_resp.completion_text

            logger.info("AI更新任务书完成")
            return updated_content
        except Exception as e:
            logger.error(f"AI更新任务书失败: {e}")
            raise Exception(f"AI更新任务书失败: {str(e)}")