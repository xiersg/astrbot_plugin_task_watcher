"""
本地只读 Web：用插件内保存的 GitHub Token 拉取 Gist，供静态页展示。

监听插件配置中的 web_server_port（>0 时启用），默认仅绑定 127.0.0.1。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from aiohttp import web
from astrbot.api import logger

from .gist_manager import GistManager
from .github_client import GitHubAPIClient
from .contributions_agg import build_contributions_calendar, parse_repo_slug


def read_web_listen_config(config_obj: Any) -> tuple[str, int]:
    """从 AstrBot 插件配置读取 Web 监听地址与端口（端口<=0 表示不启用）。"""
    if isinstance(config_obj, dict):
        cfg = config_obj
    else:
        try:
            cfg = dict(config_obj.items())  # type: ignore[union-attr]
        except (AttributeError, TypeError):
            cfg = {}
    host = str(cfg.get("web_server_host") or "127.0.0.1")
    try:
        port = int(cfg.get("web_server_port") or 0)
    except (TypeError, ValueError):
        port = 0
    return host, port


def strip_fenced_markdown(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("\ufeff"):
        t = t.lstrip("\ufeff").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _no_store_headers() -> dict[str, str]:
    """避免浏览器强缓存旧版前端（插件更新后仍用缓存的 app.js）。"""
    h = dict(_cors_headers())
    h["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    h["Pragma"] = "no-cache"
    return h


class TaskWatcherWebServer:
    def __init__(self, plugin: Any):
        self._plugin = plugin
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._started = False

    @property
    def static_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "web" / "static"

    def _web_conf(self) -> tuple[str, int]:
        return read_web_listen_config(self._plugin.config)

    def _find_session(self, token: str) -> Optional[dict[str, Any]]:
        if not token:
            return None
        for _uid, c in self._plugin.user_configs.items():
            if c.get("web_read_token") == token:
                return c
        return None

    async def _handle_options(self, _request: web.Request) -> web.Response:
        return web.Response(status=204, headers=_cors_headers())

    async def _handle_api_taskbook(self, request: web.Request) -> web.Response:
        token = request.query.get("token") or ""
        cfg = self._find_session(token)
        if not cfg:
            return web.json_response(
                {"ok": False, "error": "invalid_token"},
                status=401,
                headers=_no_store_headers(),
            )
        gist_id = cfg.get("gist_id")
        gh_token = cfg.get("token")
        taskbook = ""
        source = "local"
        try:
            if gist_id and gh_token:
                mgr = GistManager(gh_token)
                fetched = await mgr.get_gist_content(gist_id)
                if fetched is not None:
                    taskbook = strip_fenced_markdown(fetched)
                    source = "gist"
            if not taskbook:
                taskbook = strip_fenced_markdown(
                    str(cfg.get("taskbook_content") or "")
                )
                source = "local"
        except Exception as e:
            logger.exception("web /api/taskbook: %s", e)
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=500,
                headers=_no_store_headers(),
            )
        return web.json_response(
            {
                "ok": True,
                "taskbook": taskbook,
                "source": source,
                "gist_url": cfg.get("gist_url"),
            },
            headers=_no_store_headers(),
        )

    async def _handle_api_contributions(self, request: web.Request) -> web.Response:
        token = request.query.get("token") or ""
        cfg = self._find_session(token)
        if not cfg:
            return web.json_response(
                {"ok": False, "error": "invalid_token"},
                status=401,
                headers=_no_store_headers(),
            )
        gh_token = str(cfg.get("token") or "").strip()
        if not gh_token:
            return web.json_response(
                {"ok": False, "error": "no_github_token", "message": "未配置 GitHub Token"},
                status=401,
                headers=_no_store_headers(),
            )
        repo_s = str(cfg.get("repo") or "").strip()
        if not repo_s:
            return web.json_response(
                {
                    "ok": True,
                    "enabled": False,
                    "reason": "no_repo",
                    "message": "未设置监视仓库，无法拉取贡献数据（/watcher set_repo）",
                },
                headers=_no_store_headers(),
            )
        range_end_q = (request.query.get("range_end") or "").strip() or None
        raw_rd = request.query.get("range_days") or "90"
        try:
            range_days = int(raw_rd)
        except (TypeError, ValueError):
            range_days = 90
        try:
            owner, name = parse_repo_slug(repo_s)
        except ValueError as e:
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=400,
                headers=_no_store_headers(),
            )
        try:
            client = GitHubAPIClient(gh_token)
            payload = await build_contributions_calendar(
                client,
                owner,
                name,
                range_end=range_end_q,
                range_days=range_days,
            )
            return web.json_response(payload, headers=_no_store_headers())
        except Exception as e:
            logger.exception("web /api/contributions: %s", e)
            return web.json_response(
                {"ok": False, "error": str(e)},
                status=502,
                headers=_no_store_headers(),
            )

    async def _handle_static(self, request: web.Request) -> web.StreamResponse:
        rel = request.match_info.get("path", "index.html")
        if ".." in rel or rel.startswith("/"):
            raise web.HTTPNotFound()
        path = self.static_dir / rel
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers=_no_store_headers())

    async def _handle_index(self, _request: web.Request) -> web.StreamResponse:
        index = self.static_dir / "index.html"
        if not index.is_file():
            return web.Response(
                text="静态文件缺失：请检查插件 web/static/index.html",
                content_type="text/plain; charset=utf-8",
                headers=_no_store_headers(),
            )
        return web.FileResponse(index, headers=_no_store_headers())

    def build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/api/taskbook", self._handle_api_taskbook)
        app.router.add_options("/api/taskbook", self._handle_options)
        app.router.add_get("/api/contributions", self._handle_api_contributions)
        app.router.add_options("/api/contributions", self._handle_options)
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/static/{path:.*}", self._handle_static)
        return app

    async def start(self) -> None:
        if self._started:
            return
        host, port = self._web_conf()
        if port <= 0:
            logger.info("TaskWatcher Web：未启用（web_server_port<=0）")
            return
        if not self.static_dir.is_dir():
            logger.warning("TaskWatcher Web：缺少目录 %s", self.static_dir)
        app = self.build_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()
        self._started = True
        logger.info("TaskWatcher Web 已启动：http://%s:%s/", host, port)

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self._site:
            await self._site.stop()
            self._site = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("TaskWatcher Web 已停止")
