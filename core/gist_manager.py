"""
Gist 管理模块

职责：
- 上传任务书到 GitHub Gist
- 管理 Gist 版本历史
- 获取 Gist 内容
"""

import aiohttp
from typing import Optional, Dict
from astrbot.api import logger


class GistManager:
    """Gist 管理器"""

    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}",
            "User-Agent": "TaskWatcher-AstrBot-Plugin"
        }

    async def upload_taskbook(self, content: str, filename: str = "taskbook.md",
                              description: str = "TaskWatcher 任务书") -> Optional[str]:
        """上传任务书到 Gist，返回 Gist URL"""
        url = f"{self.base_url}/gists"

        payload = {
            "description": description,
            "public": False,
            "files": {
                filename: {
                    "content": content
                }
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._get_headers(), json=payload) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    return data.get("html_url")
                logger.error(f"上传 Gist 失败: {resp.status}")
                return None

    async def update_taskbook(self, gist_id: str, content: str,
                              filename: str = None) -> bool:
        """更新已存在的 Gist，如果不指定文件名则更新第一个文件"""
        url = f"{self.base_url}/gists/{gist_id}"

        # 如果没有指定文件名，先获取 Gist 信息
        if not filename:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        files = data.get("files", {})
                        if files:
                            filename = list(files.keys())[0]
                        else:
                            filename = "taskbook.md"
                    else:
                        filename = "taskbook.md"

        payload = {
            "files": {
                filename: {
                    "content": content
                }
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=self._get_headers(), json=payload) as resp:
                return resp.status == 200

    async def get_gist_content(self, gist_id: str, filename: str = None) -> Optional[str]:
        """获取 Gist 内容，如果不指定文件名则返回第一个文件的内容"""
        url = f"{self.base_url}/gists/{gist_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    files = data.get("files", {})
                    if not files:
                        return None
                    # 如果指定了文件名，查找对应文件
                    if filename and filename in files:
                        return files[filename].get("content")
                    # 否则返回第一个文件的内容
                    first_file = list(files.values())[0]
                    return first_file.get("content")
                return None

    @staticmethod
    def extract_gist_id(gist_url: str) -> Optional[str]:
        """从 Gist URL 中提取 Gist ID"""
        # 支持格式: https://gist.github.com/username/gist_id
        # 或: https://gist.githubusercontent.com/username/gist_id/raw/...
        parts = gist_url.replace("https://", "").replace("http://", "").split("/")
        if "gist.github.com" in gist_url or "gist.githubusercontent.com" in gist_url:
            for part in parts:
                if len(part) == 32:  # Gist ID 是 32 位十六进制
                    return part
        return None
