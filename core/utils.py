"""
工具函数模块

职责：
- 提供通用的工具函数
- 文件操作
- 数据格式化
- 配置管理辅助功能

设计模式：
- 静态方法：无状态的纯函数
- 工具类：相关功能的集合
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from astrbot.api import logger


class FileUtils:
    """文件操作工具类"""

    @staticmethod
    def ensure_directory(path: str) -> Path:
        """
        确保目录存在，不存在则创建

        Args:
            path: 目录路径

        Returns:
            Path 对象
        """
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @staticmethod
    def backup_file(file_path: str) -> str:
        """
        备份文件

        Args:
            file_path: 要备份的文件路径

        Returns:
            备份文件路径

        Raises:
            FileNotFoundError: 原文件不存在
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{file_path}.backup_{timestamp}"

        shutil.copy(file_path, backup_path)
        logger.info(f"文件已备份: {backup_path}")
        return backup_path

    @staticmethod
    def safe_write_file(file_path: str, content: str) -> bool:
        """
        安全写入文件（原子性写入）

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            是否写入成功
        """
        try:
            # 先写入临时文件
            temp_path = f"{file_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # 原子性操作：重命名
            os.replace(temp_path, file_path)
            return True

        except Exception as e:
            logger.error(f"文件写入失败: {e}")
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    @staticmethod
    def get_file_extension(file_path: str) -> str:
        """
        获取文件扩展名

        Args:
            file_path: 文件路径

        Returns:
            文件扩展名（包含点），如 '.json'
        """
        return Path(file_path).suffix.lower()


class DataFormatter:
    """数据格式化工具类"""

    @staticmethod
    def format_timestamp(timestamp: str) -> str:
        """
        格式化时间戳为可读格式

        Args:
            timestamp: ISO 格式时间戳

        Returns:
            格式化后的时间字符串
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return timestamp

    @staticmethod
    def format_percentage(value: float) -> str:
        """
        格式化百分比

        Args:
            value: 百分比值

        Returns:
            格式化后的百分比字符串
        """
        return f"{value:.0f}%"

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        格式化文件大小

        Args:
            size_bytes: 文件大小（字节）

        Returns:
            可读的文件大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    @staticmethod
    def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
        """
        截断文本

        Args:
            text: 原始文本
            max_length: 最大长度
            suffix: 截断后缀

        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text

        # 为后缀预留空间
        available_length = max_length - len(suffix)
        return text[:available_length] + suffix

    @staticmethod
    def format_task_list(tasks: List[Dict], max_items: int = 5) -> str:
        """
        格式化任务列表

        Args:
            tasks: 任务列表
            max_items: 最大显示数量

        Returns:
            格式化后的任务列表字符串
        """
        if not tasks:
            return "没有任务"

        status_symbols = {
            'completed': '✅',
            'in_progress': '⏳',
            'not_started': '❌'
        }

        task_list = []
        for task in tasks[:max_items]:
            task_name = DataFormatter.truncate_text(task.get('name', ''), 50)
            status = task.get('status', 'not_started')
            symbol = status_symbols.get(status, '❌')
            completion = task.get('completion_rate', 0)
            contributor = task.get('main_contributor', '未分配')

            task_list.append(f"  • {symbol} {task_name} - {contributor} - {completion}%")

        return '\n'.join(task_list)


class ConfigUtils:
    """配置管理工具类"""

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        验证URL格式

        Args:
            url: 要验证的URL

        Returns:
            URL是否有效
        """
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain
            r'(?:[A-Z]{2,6}\.?)?'  # tld
            r'(?:\d+)?'  # port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return bool(url_pattern.match(url))

    @staticmethod
    def extract_github_info(url: str) -> Dict[str, str]:
        """
        从GitHub URL提取信息

        Args:
            url: GitHub仓库URL

        Returns:
            包含 owner 和 repo 的字典

        Raises:
            ValueError: URL格式无效时抛出异常
        """
        import re

        # 移除.git后缀
        url = url.replace('.git', '')

        # 匹配 GitHub URL 格式
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', url)
        if not match:
            raise ValueError(f"无效的GitHub URL格式: {url}")

        owner, repo = match.groups()
        return {
            'owner': owner,
            'repo': repo
        }

    @staticmethod
    def validate_positive_integer(value: str, default: int = 0, max_value: Optional[int] = None) -> int:
        """
        验证正整数

        Args:
            value: 要验证的字符串值
            default: 默认值
            max_value: 最大值（可选）

        Returns:
            验证后的整数值
        """
        try:
            result = int(value)
            if result < 0:
                logger.warning(f"值不能为负数，使用默认值: {default}")
                return default
            if max_value and result > max_value:
                logger.warning(f"值超过最大值 {max_value}，使用最大值")
                return max_value
            return result
        except ValueError:
            logger.warning(f"值不是有效的整数，使用默认值: {default}")
            return default


class Validator:
    """数据验证工具类"""

    @staticmethod
    def validate_task_data(tasks: List[Dict]) -> tuple[bool, List[str]]:
        """
        验证任务数据

        Args:
            tasks: 任务列表

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        if not tasks:
            errors.append("任务列表为空")
            return False, errors

        for i, task in enumerate(tasks):
            # 检查必需字段
            if 'name' not in task:
                errors.append(f"任务 {i+1} 缺少 'name' 字段")

            # 检查数据类型
            completion_rate = task.get('completion_rate', 0)
            if not isinstance(completion_rate, (int, float)):
                errors.append(f"任务 '{task.get('name', '')}' 的 completion_rate 不是数字")

            # 检查数值范围
            if isinstance(completion_rate, (int, float)):
                if completion_rate < 0 or completion_rate > 100:
                    errors.append(f"任务 '{task.get('name', '')}' 的 completion_rate 超出范围 (0-100)")

            # 检查状态值
            status = task.get('status', '')
            if status not in ['completed', 'in_progress', 'not_started']:
                errors.append(f"任务 '{task.get('name', '')}' 的 status 值无效")

        return len(errors) == 0, errors

    @staticmethod
    def validate_file_path(file_path: str) -> tuple[bool, str]:
        """
        验证文件路径

        Args:
            file_path: 文件路径

        Returns:
            (是否有效, 错误信息)
        """
        if not file_path:
            return False, "文件路径为空"

        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"

        if not os.path.isfile(file_path):
            return False, f"路径不是文件: {file_path}"

        return True, ""