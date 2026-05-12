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
from typing import Any, Dict, List, Optional
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

    async def get_commits(
        self,
        owner: str,
        repo: str,
        limit: int = 100,
        sha: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取仓库提交记录。sha 为分支名或提交 SHA，省略则使用 GitHub 默认分支。
        """
        from urllib.parse import quote

        url = f"{self.base_url}/repos/{owner}/{repo}/commits?per_page={limit}"
        if sha:
            url += "&sha=" + quote(sha, safe="")

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

    async def compare_commits(
        self, owner: str, repo: str, base: str, head: str
    ) -> Dict[str, Any]:
        """比较 base...head 两个引用之间的提交与文件 diff（含 patch）。"""
        expr = f"{base}...{head}"
        url = f"{self.base_url}/repos/{owner}/{repo}/compare/{expr}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    return await response.json()
                error_text = await response.text()
                raise Exception(f"GitHub API 错误 {response.status}: {error_text}")

    async def list_commit_pulls(
        self, owner: str, repo: str, commit_sha: str
    ) -> List[Dict[str, Any]]:
        """
        与某提交关联的 Pull Request（标题、正文等），用于对齐任务点。
        https://docs.github.com/en/rest/commits/commits#list-pull-requests-associated-with-a-commit
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}/pulls"
        headers = dict(self._get_headers())
        headers["Accept"] = "application/vnd.github+json"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                if response.status in (404, 422):
                    return []
                error_text = await response.text()
                raise Exception(f"GitHub API 错误 {response.status}: {error_text}")

    @staticmethod
    def truncate_patch(patch: Optional[str], max_chars: int = 1200) -> str:
        if not patch:
            return ""
        if len(patch) <= max_chars:
            return patch
        return patch[:max_chars] + "\n... [patch 已截断，节省 token]"