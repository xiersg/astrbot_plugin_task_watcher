"""
规则匹配器模块

职责：
- 基于规则的快速任务匹配分析
- 文件路径匹配和关联度计算
- 完成度计算逻辑

设计模式：
- 策略模式：不同的匹配策略
- 规则引擎：可配置的匹配规则
"""

from typing import Dict, List
from astrbot.api import logger


class TaskMatcher:
    """规则匹配器"""

    def __init__(self, matching_strategy: str = "hybrid"):
        """
        初始化规则匹配器

        Args:
            matching_strategy: 匹配策略
                - "exact": 精确匹配
                - "partial": 部分匹配
                - "hybrid": 混合匹配（默认）
        """
        self.matching_strategy = matching_strategy

    def match_tasks_with_changes(self, tasks: List[Dict], file_changes: Dict) -> List[Dict]:
        """
        匹配任务和文件变更，计算完成度

        Args:
            tasks: 任务列表
            file_changes: 文件变更信息字典

        Returns:
            分析后的任务列表
        """
        task_status = []

        for task in tasks:
            task_name = task['name']
            related_path = task.get('related_path', '').lower()

            # 查找相关文件变更
            matching_changes = self._find_matching_files(related_path, file_changes)

            # 计算完成度
            if matching_changes:
                completion_data = self._calculate_completion(task, matching_changes)
            else:
                completion_data = {
                    'completion_rate': task.get('completion_rate', 0),
                    'main_contributor': '未分配',
                    'matching_files': []
                }

            # 确定任务状态
            status = self._determine_status(completion_data['completion_rate'])

            task_status.append({
                'name': task_name,
                'status': status,
                'completion_rate': completion_data['completion_rate'],
                'main_contributor': completion_data['main_contributor'],
                'related_files': completion_data.get('matching_files', []),
                'evidence': self._generate_evidence(completion_data)
            })

        return task_status

    def _find_matching_files(self, related_path: str, file_changes: Dict) -> Dict:
        """
        查找与任务相关的文件变更

        Args:
            related_path: 任务相关的路径
            file_changes: 所有文件变更

        Returns:
            匹配的文件变更字典
        """
        if not related_path:
            return {}

        matching_changes = {}

        for filename, changes in file_changes.items():
            filename_lower = filename.lower()

            # 根据匹配策略进行匹配
            if self.matching_strategy == "exact":
                # 精确匹配
                if related_path == filename_lower:
                    matching_changes[filename] = changes

            elif self.matching_strategy == "partial":
                # 部分匹配（包含关系）
                if related_path in filename_lower or filename_lower in related_path:
                    matching_changes[filename] = changes

            else:  # hybrid
                # 混合匹配：精确匹配优先，部分匹配次之
                if related_path == filename_lower:
                    matching_changes[filename] = changes
                elif related_path in filename_lower or filename_lower in related_path:
                    matching_changes[filename] = changes

        return matching_changes

    def _calculate_completion(self, task: Dict, matching_changes: Dict) -> Dict:
        """
        计算任务完成度

        Args:
            task: 任务信息
            matching_changes: 匹配的文件变更

        Returns:
            包含完成度和贡献者的字典
        """
        total_additions = sum(c['additions'] for c in matching_changes.values())
        total_deletions = sum(c['deletions'] for c in matching_changes.values())
        total_changes = sum(c['changes'] for c in matching_changes.values())

        # 基础完成度
        base_completion = task.get('completion_rate', 0)

        # 计算增量完成度
        # 规则：每次变更增加5%，但考虑代码量的影响
        code_weight = min(total_additions / 100, 1.0)  # 代码量权重，最大为1
        increment = min(total_changes * 5, 30)  # 每次变更+5%，最多+30%

        # 删除操作可能表示重构，谨慎处理
        deletion_penalty = min(total_deletions / 50, 10)  # 删除惩罚，最多-10%

        # 计算最终完成度
        completion_rate = min(100, max(0, base_completion + increment * code_weight - deletion_penalty))

        # 计算主要贡献者
        contributors = {}
        for changes in matching_changes.values():
            author = changes['author']
            if author not in contributors:
                contributors[author] = 0
            contributors[author] += changes['changes']

        if contributors:
            main_contributor = max(contributors.items(), key=lambda x: x[1])[0]
        else:
            main_contributor = "未分配"

        return {
            'completion_rate': int(completion_rate),
            'main_contributor': main_contributor,
            'matching_files': list(matching_changes.keys()),
            'total_changes': total_changes,
            'total_additions': total_additions,
            'total_deletions': total_deletions
        }

    def _determine_status(self, completion_rate: int) -> str:
        """
        根据完成度确定任务状态

        Args:
            completion_rate: 完成度（0-100）

        Returns:
            任务状态：'completed', 'in_progress', 'not_started'
        """
        if completion_rate >= 100:
            return 'completed'
        elif completion_rate > 0:
            return 'in_progress'
        else:
            return 'not_started'

    def _generate_evidence(self, completion_data: Dict) -> str:
        """
        生成分析证据

        Args:
            completion_data: 完成度计算数据

        Returns:
            分析证据字符串
        """
        if not completion_data.get('matching_files'):
            return "未找到相关文件变更"

        evidence_parts = []

        # 文件变更信息
        files = completion_data['matching_files']
        if files:
            evidence_parts.append(f"相关文件: {', '.join(files)}")

        # 代码变更统计
        if completion_data.get('total_changes', 0) > 0:
            total_changes = completion_data['total_changes']
            total_additions = completion_data.get('total_additions', 0)
            total_deletions = completion_data.get('total_deletions', 0)

            change_info = f"代码变更: {total_changes}次提交"
            if total_additions > 0 or total_deletions > 0:
                change_info += f", 新增{total_additions}行, 删除{total_deletions}行"
            evidence_parts.append(change_info)

        return "; ".join(evidence_parts)

    def update_matching_strategy(self, strategy: str):
        """
        更新匹配策略

        Args:
            strategy: 新的匹配策略 ('exact', 'partial', 'hybrid')

        Raises:
            ValueError: 策略无效时抛出异常
        """
        if strategy not in ['exact', 'partial', 'hybrid']:
            raise ValueError(f"无效的匹配策略: {strategy}")

        self.matching_strategy = strategy
        logger.info(f"匹配策略已更新为: {strategy}")