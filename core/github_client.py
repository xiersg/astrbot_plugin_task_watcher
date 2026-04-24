"""
GitHub API 客户端模块

职责：
- 封装 GitHub API 调用
- 处理 HTTP 请求和响应
- 管理 API 认证

设计模式：
- 单例模式：一个客户端实例
- 策略模式：不同的 API 调用策略
"""

import aiohttp
from typing import Dict, List
from astrbot.api import logger


class GitHubAPIClient:
    """GitHub API 客户端类"""

    def __init__(self, token: str = None):
        """
        初始化 GitHub API 客户端

        Args:
            token: GitHub Personal Access Token (可选)
        """
        self.token = token
        self.base_url = "https://api.github.com"

    def _get_headers(self) -> Dict[str, str]:
        """获取 API 请求头"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TaskWatcher-AstrBot-Plugin"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def get_commits(self, owner: str, repo: str, limit: int = 100) -> List[Dict]:
        """
        获取仓库的提交记录

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            limit: 获取的提交数量限制

        Returns:
            提交记录列表

        Raises:
            Exception: API 请求失败时抛出异常
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits?per_page={limit}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    commits = await response.json()
                    logger.debug(f"成功获取 {len(commits)} 次提交记录")
                    return commits
                else:
                    error_text = await response.text()
                    raise Exception(f"GitHub API 错误 {response.status}: {error_text}")

    async def get_commit_detail(self, owner: str, repo: str, sha: str) -> Dict:
        """
        获取指定提交的详细信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            sha: 提交的 SHA 值

        Returns:
            提交详细信息，包含文件变更

        Raises:
            Exception: API 请求失败时抛出异常
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    detail = await response.json()
                    return detail
                else:
                    error_text = await response.text()
                    raise Exception(f"GitHub API 错误 {response.status}: {error_text}")

    async def get_repository_info(self, owner: str, repo: str) -> Dict:
        """
        获取仓库的基本信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            仓库信息字典

        Raises:
            Exception: API 请求失败时抛出异常
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    repo_info = await response.json()
                    logger.debug(f"成功获取仓库信息: {repo_info.get('name', 'unknown')}")
                    return repo_info
                else:
                    error_text = await response.text()
                    raise Exception(f"GitHub API 错误 {response.status}: {error_text}")

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str:
        """
        获取指定文件的内容

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            ref: 分支或标签（默认为 main）

        Returns:
            文件内容

        Raises:
            Exception: API 请求失败时抛出异常
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}?ref={ref}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    # GitHub API 返回的是 base64 编码的内容
                    import base64
                    content = base64.b64decode(data['content']).decode('utf-8')
                    return content
                else:
                    error_text = await response.text()
                    raise Exception(f"GitHub API 错误 {response.status}: {error_text}")