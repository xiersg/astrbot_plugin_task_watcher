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

import re
import aiohttp
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

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

    @staticmethod
    def _parse_link_next(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        for segment in link_header.split(","):
            if 'rel="next"' not in segment and "rel='next'" not in segment:
                continue
            m = re.search(r"<([^>]+)>", segment.strip())
            if m:
                return m.group(1)
        return None

    async def fetch_commits_since(
        self,
        owner: str,
        repo: str,
        since_iso: str,
        *,
        max_pages: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        列出 since_iso（含时区，建议 Z）之后的提交，分页直至无 next 或达到 max_pages。
        每项: sha, date, login, message, html_url
        """
        path = f"{self.base_url}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits"
        url = f"{path}?since={quote(since_iso, safe='')}&per_page=100"
        out: List[Dict[str, Any]] = []
        page = 0
        async with aiohttp.ClientSession() as session:
            while url and page < max_pages:
                page += 1
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"GitHub API 错误 {resp.status}: {err[:800]}")
                    batch = await resp.json()
                    if not isinstance(batch, list):
                        break
                    for c in batch:
                        if not isinstance(c, dict):
                            continue
                        commit = c.get("commit") or {}
                        auth = commit.get("author") or {}
                        cm = commit.get("committer") or {}
                        date = auth.get("date") or cm.get("date") or ""
                        msg = (commit.get("message") or "").split("\n", 1)[0].strip()
                        gh_author = c.get("author") or {}
                        login = (
                            gh_author.get("login")
                            if isinstance(gh_author, dict) and gh_author.get("login")
                            else None
                        )
                        if not login and isinstance(auth, dict):
                            login = (auth.get("name") or "").strip() or None
                        out.append(
                            {
                                "sha": str(c.get("sha") or "")[:40],
                                "date": date,
                                "login": login or "（无 GitHub 登录名）",
                                "message": msg[:200],
                                "html_url": str(c.get("html_url") or ""),
                            }
                        )
                    url = self._parse_link_next(resp.headers.get("Link"))
        return out

    async def fetch_commits_between(
        self,
        owner: str,
        repo: str,
        since_iso: str,
        until_iso: str,
        *,
        max_pages: int = 35,
    ) -> List[Dict[str, Any]]:
        """
        在 [since_iso, until_iso) 时间窗口内列提交（GitHub since/until 语义）。
        每项同 fetch_commits_since。
        """
        path = f"{self.base_url}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits"
        url = (
            f"{path}?since={quote(since_iso, safe='')}&until={quote(until_iso, safe='')}"
            f"&per_page=100"
        )
        out: List[Dict[str, Any]] = []
        page = 0
        async with aiohttp.ClientSession() as session:
            while url and page < max_pages:
                page += 1
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"GitHub API 错误 {resp.status}: {err[:800]}")
                    batch = await resp.json()
                    if not isinstance(batch, list):
                        break
                    for c in batch:
                        if not isinstance(c, dict):
                            continue
                        commit = c.get("commit") or {}
                        auth = commit.get("author") or {}
                        cm = commit.get("committer") or {}
                        date = auth.get("date") or cm.get("date") or ""
                        msg = (commit.get("message") or "").split("\n", 1)[0].strip()
                        gh_author = c.get("author") or {}
                        login = (
                            gh_author.get("login")
                            if isinstance(gh_author, dict) and gh_author.get("login")
                            else None
                        )
                        if not login and isinstance(auth, dict):
                            login = (auth.get("name") or "").strip() or None
                        out.append(
                            {
                                "sha": str(c.get("sha") or "")[:40],
                                "date": date,
                                "login": login or "（无 GitHub 登录名）",
                                "message": msg[:200],
                                "html_url": str(c.get("html_url") or ""),
                            }
                        )
                    url = self._parse_link_next(resp.headers.get("Link"))
        return out

    async def fetch_merged_pulls_search(
        self,
        owner: str,
        repo: str,
        merged_since_day: str,
        *,
        max_results: int = 1000,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        使用 search API 拉取 merged_since_day（YYYY-MM-DD）起合并的 PR。
        每项: number, title, login, merged_day, html_url
        返回 (列表, 是否因 GitHub search 1000 条上限而截断)。
        """
        q = f"repo:{owner}/{repo} is:pr is:merged merged:>={merged_since_day}"
        collected: List[Dict[str, Any]] = []
        per_page = 100
        max_page = max(1, (max_results + per_page - 1) // per_page)
        total_count = 0
        async with aiohttp.ClientSession() as session:
            for page in range(1, max_page + 1):
                url = (
                    f"{self.base_url}/search/issues?q={quote(q, safe='')}"
                    f"&per_page={per_page}&page={page}"
                )
                headers = dict(self._get_headers())
                headers["Accept"] = "application/vnd.github+json"
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"GitHub Search API 错误 {resp.status}: {err[:800]}")
                    data = await resp.json()
                if page == 1:
                    total_count = int(data.get("total_count") or 0)
                items = data.get("items") or []
                if not isinstance(items, list) or not items:
                    break
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if "pull_request" not in it:
                        continue
                    closed = it.get("closed_at") or ""
                    user = it.get("user") or {}
                    login = user.get("login") if isinstance(user, dict) else None
                    collected.append(
                        {
                            "number": it.get("number"),
                            "title": str(it.get("title") or "")[:240],
                            "login": login or "（无 GitHub 登录名）",
                            "merged_day": (
                                closed[:10]
                                if isinstance(closed, str) and len(closed) >= 10
                                else ""
                            ),
                            "html_url": str(it.get("html_url") or ""),
                        }
                    )
                    if len(collected) >= max_results:
                        truncated = total_count > len(collected)
                        return collected[:max_results], truncated
                if len(items) < per_page:
                    break
                if page * per_page >= total_count:
                    break
        truncated = total_count > len(collected)
        return collected, truncated

    async def fetch_merged_pulls_search_range(
        self,
        owner: str,
        repo: str,
        merged_start_day: str,
        merged_end_day: str,
        *,
        max_results: int = 500,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        已合并 PR，merged 日期在 [merged_start_day, merged_end_day]（闭区间，YYYY-MM-DD）。
        """
        q = (
            f"repo:{owner}/{repo} is:pr is:merged "
            f"merged:{merged_start_day}..{merged_end_day}"
        )
        collected: List[Dict[str, Any]] = []
        per_page = 100
        max_page = max(1, (max_results + per_page - 1) // per_page)
        total_count = 0
        async with aiohttp.ClientSession() as session:
            for page in range(1, max_page + 1):
                url = (
                    f"{self.base_url}/search/issues?q={quote(q, safe='')}"
                    f"&per_page={per_page}&page={page}"
                )
                headers = dict(self._get_headers())
                headers["Accept"] = "application/vnd.github+json"
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"GitHub Search API 错误 {resp.status}: {err[:800]}")
                    data = await resp.json()
                if page == 1:
                    total_count = int(data.get("total_count") or 0)
                items = data.get("items") or []
                if not isinstance(items, list) or not items:
                    break
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if "pull_request" not in it:
                        continue
                    closed = it.get("closed_at") or ""
                    user = it.get("user") or {}
                    login = user.get("login") if isinstance(user, dict) else None
                    collected.append(
                        {
                            "number": it.get("number"),
                            "title": str(it.get("title") or "")[:240],
                            "login": login or "（无 GitHub 登录名）",
                            "merged_day": (
                                closed[:10]
                                if isinstance(closed, str) and len(closed) >= 10
                                else ""
                            ),
                            "html_url": str(it.get("html_url") or ""),
                        }
                    )
                    if len(collected) >= max_results:
                        truncated = total_count > len(collected)
                        return collected[:max_results], truncated
                if len(items) < per_page:
                    break
                if page * per_page >= total_count:
                    break
        truncated = total_count > len(collected)
        return collected, truncated

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