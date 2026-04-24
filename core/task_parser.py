"""
任务书解析器模块

职责：
- 解析不同格式的任务书文件
- 统一任务数据结构
- 提供任务书验证功能

设计模式：
- 工厂模式：根据文件类型选择解析器
- 策略模式：不同的解析策略
"""

import json
import re
from typing import Dict, List
from astrbot.api import logger


class TaskBookParser:
    """任务书解析器"""

    @staticmethod
    def parse_json(file_path: str) -> List[Dict]:
        """
        解析 JSON 格式的任务书

        Args:
            file_path: JSON 文件路径

        Returns:
            任务列表

        Raises:
            ValueError: JSON 格式错误时抛出异常
            FileNotFoundError: 文件不存在时抛出异常
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 支持两种 JSON 格式
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'tasks' in data:
                return data['tasks']
            else:
                raise ValueError("JSON 格式错误，期望包含 tasks 数组")

        except FileNotFoundError:
            raise FileNotFoundError(f"任务书文件不存在: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析错误: {str(e)}")

    @staticmethod
    def parse_markdown(file_path: str) -> List[Dict]:
        """
        解析 Markdown 格式的任务书

        Args:
            file_path: Markdown 文件路径

        Returns:
            任务列表

        Raises:
            ValueError: Markdown 格式错误时抛出异常
            FileNotFoundError: 文件不存在时抛出异常
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tasks = []
            lines = content.split('\n')

            for line in lines:
                line = line.strip()

                # 匹配任务项格式：
                # - [ ] 任务名称 (相关路径) - 百分比%
                # - [x] 任务名称 (相关路径)
                match = re.match(r'^-\s*\[([ xX])\]\s*(.+?)(?:\s*-\s*(\d+)%?)?$', line)
                if match:
                    status, task_name, progress = match.groups()
                    is_completed = status.lower() == 'x'

                    # 处理百分比
                    completion_rate = int(progress) if progress else (100 if is_completed else 0)

                    # 提取相关路径（括号中的内容）
                    path_match = re.search(r'\(([^)]+)\)', task_name)
                    related_path = path_match.group(1) if path_match else None

                    # 清理任务名称（移除路径信息）
                    clean_name = re.sub(r'\([^)]+\)', '', task_name).strip()

                    tasks.append({
                        'name': clean_name,
                        'status': 'completed' if is_completed else 'pending',
                        'completion_rate': completion_rate,
                        'related_path': related_path
                    })

            if not tasks:
                logger.warning(f"Markdown 任务书中没有找到有效的任务项: {file_path}")

            return tasks

        except FileNotFoundError:
            raise FileNotFoundError(f"任务书文件不存在: {file_path}")
        except Exception as e:
            raise ValueError(f"Markdown 解析错误: {str(e)}")

    @staticmethod
    def parse_yaml(file_path: str) -> List[Dict]:
        """
        解析 YAML 格式的任务书

        Args:
            file_path: YAML 文件路径

        Returns:
            任务列表

        Raises:
            ValueError: YAML 格式错误时抛出异常
            ImportError: 缺少 PyYAML 库时抛出异常
            FileNotFoundError: 文件不存在时抛出异常
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("需要安装 PyYAML 库来解析 YAML 文件")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # 支持两种 YAML 格式
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'tasks' in data:
                return data['tasks']
            else:
                raise ValueError("YAML 格式错误，期望包含 tasks 数组")

        except FileNotFoundError:
            raise FileNotFoundError(f"任务书文件不存在: {file_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误: {str(e)}")

    @classmethod
    def parse_file(cls, file_path: str) -> List[Dict]:
        """
        自动识别并解析任务书文件

        Args:
            file_path: 任务书文件路径

        Returns:
            任务列表

        Raises:
            ValueError: 不支持的文件格式时抛出异常
        """
        if file_path.endswith('.json'):
            return cls.parse_json(file_path)
        elif file_path.endswith('.md'):
            return cls.parse_markdown(file_path)
        elif file_path.endswith(('.yaml', '.yml')):
            return cls.parse_yaml(file_path)
        else:
            raise ValueError(f"不支持的任务书格式: {file_path}。支持的格式: .json, .md, .yaml, .yml")

    @staticmethod
    def validate_tasks(tasks: List[Dict]) -> bool:
        """
        验证任务列表的有效性

        Args:
            tasks: 任务列表

        Returns:
            是否有效

        检查项目：
        - 任务列表不为空
        - 每个任务都有 name 字段
        - completion_rate 在 0-100 范围内
        """
        if not tasks:
            return False

        for task in tasks:
            if 'name' not in task:
                return False

            completion_rate = task.get('completion_rate', 0)
            if not isinstance(completion_rate, (int, float)):
                return False

            if completion_rate < 0 or completion_rate > 100:
                return False

        return True