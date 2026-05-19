"""
/watcher test 自检：只读探测，不调用 LLM，不写 Gist/任务书。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
import yaml

from .gist_manager import GistManager
from .github_client import GitHubAPIClient
from .taskbook_schema import count_tasks_in_tree, is_taskbook_yaml_v1_document
from .web_server import read_web_listen_config, strip_fenced_markdown, web_user_link_and_hint

_HTTP_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=4, connect=2)


@dataclass
class TestStep:
    index: int
    total: int
    name: str
    ok: bool
    detail: str
    elapsed_ms: int = 0

    def line(self) -> str:
        mark = "✅" if self.ok else "❌"
        ms = f" ({self.elapsed_ms}ms)" if self.elapsed_ms else ""
        return f"[{self.index}/{self.total}] {self.name} … {mark} {self.detail}{ms}"


def _parse_taskbook_yaml_v1(taskbook: str) -> Optional[dict]:
    tb = strip_fenced_markdown(taskbook or "")
    if tb.startswith("\ufeff"):
        tb = tb.lstrip("\ufeff")
    try:
        doc = yaml.safe_load(tb)
    except Exception:
        return None
    if isinstance(doc, dict) and is_taskbook_yaml_v1_document(doc):
        return doc
    return None


async def _http_get(url: str) -> tuple[int, str]:
    async with aiohttp.ClientSession(timeout=_HTTP_PROBE_TIMEOUT) as session:
        async with session.get(url) as resp:
            return resp.status, (await resp.text())[:300]


async def _http_get_json(url: str) -> tuple[int, Optional[dict]]:
    async with aiohttp.ClientSession(timeout=_HTTP_PROBE_TIMEOUT) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return resp.status, None
            try:
                data = await resp.json(content_type=None)
            except (json.JSONDecodeError, aiohttp.ContentTypeError, ValueError):
                return resp.status, None
            return resp.status, data if isinstance(data, dict) else None


async def run_watcher_self_test(plugin: Any, user_id: str) -> List[TestStep]:
    total = 9
    steps: List[TestStep] = []
    cfg: Optional[Dict[str, Any]] = None
    config_path = plugin.data_dir / "configs.json"

    def add(name: str, ok: bool, detail: str, elapsed_ms: int = 0) -> None:
        steps.append(
            TestStep(
                index=len(steps) + 1,
                total=total,
                name=name,
                ok=ok,
                detail=detail,
                elapsed_ms=elapsed_ms,
            )
        )

    # 1 会话与本地配置
    t0 = time.perf_counter()
    if not user_id:
        add("会话 ID", False, "无法识别，请在与 set_token 相同会话重试")
    else:
        cfg = plugin.user_configs.get(user_id)
        if not cfg:
            add(
                "本地配置",
                False,
                f"user_id={user_id[:32]} 无条目；{config_path.name} 存在={config_path.is_file()}",
            )
        else:
            parts = [
                "token✓" if cfg.get("token") else "无token",
                "gist✓" if cfg.get("gist_id") else "无gist",
                "repo✓" if (cfg.get("repo") or "").strip() else "无repo",
                f"书{(len(cfg.get('taskbook_content') or ''))}字",
                "web_token✓" if cfg.get("web_read_token") else "无web_token",
            ]
            add("本地配置", True, " ".join(parts))
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not cfg:
        add("任务书 YAML", False, "跳过（无配置）")
        add("GitHub", False, "跳过（无配置）")
        add("Gist", False, "跳过（无配置）")
        add("增量 compare", False, "跳过（无配置）")
        add("Web 服务", False, "跳过（无配置）")
        add("HTTP 首页", False, "跳过（无配置）")
        add("HTTP taskbook API", False, "跳过（无配置）")
        add("LLM", True, "test 不调用 AI（设计如此）")
        return steps

    # 2 任务书 YAML
    t0 = time.perf_counter()
    doc = _parse_taskbook_yaml_v1(cfg.get("taskbook_content") or "")
    if doc is None:
        add("任务书 YAML", False, "非 v1（需 version:1 与 tree）；请 organize 或 set_gist")
    else:
        n = count_tasks_in_tree(doc)
        add("任务书 YAML", True, f"version=1，task 节点 {n} 个")
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 3 GitHub
    t0 = time.perf_counter()
    token = cfg.get("token")
    repo_s = (cfg.get("repo") or "").strip()
    gh_ok = False
    gh_detail = ""
    owner, repo_name = "", ""
    if not token or not repo_s:
        gh_detail = "缺少 token 或 repo"
    else:
        try:
            owner, repo_name = plugin._parse_repo(repo_s)
            client = GitHubAPIClient(token)
            info = await client.get_repository_info(owner, repo_name)
            branch = info.get("default_branch") or "main"
            commits = await client.get_commits(owner, repo_name, limit=1, sha=branch)
            head = (commits[0].get("sha") or "")[:7] if commits else "?"
            gh_ok = True
            gh_detail = f"{owner}/{repo_name} @{branch} HEAD {head}"
        except Exception as e:
            gh_detail = str(e)[:240]
            if owner and repo_name:
                gh_detail = plugin._fmt_github_err(gh_detail, owner, repo_name)[:280]
    add("GitHub", gh_ok, gh_detail)
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 4 Gist
    t0 = time.perf_counter()
    gist_id = cfg.get("gist_id")
    if not gist_id or not token:
        add("Gist", False, "缺少 gist_id 或 token")
    else:
        try:
            content = await GistManager(token).get_gist_content(gist_id)
            if content:
                add("Gist", True, f"可读，约 {len(content)} 字符")
            else:
                add("Gist", False, "返回空（检查 URL/权限）")
        except Exception as e:
            add("Gist", False, str(e)[:200])
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 5 增量 compare（摘要）
    t0 = time.perf_counter()
    try:
        changes = await plugin._get_repo_changes(cfg)
        if changes.get("error"):
            add("增量 compare", False, str(changes["error"])[:220])
        elif changes.get("no_new_commits"):
            add("增量 compare", True, "无新提交（与 last_synced 一致）")
        else:
            fc = int(changes.get("file_count") or 0)
            rng = changes.get("commits_range") or ""
            add("增量 compare", True, f"{rng} · 约 {fc} 个文件有 diff")
    except Exception as e:
        add("增量 compare", False, str(e)[:200])
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 6 Web 服务状态
    t0 = time.perf_counter()
    host, port = read_web_listen_config(plugin.config)
    ws = getattr(plugin, "_web_server", None)
    started = bool(ws and getattr(ws, "is_started", False))
    if port <= 0:
        add("Web 服务", False, "web_server_port 未启用（≤0）")
    elif not started:
        add(
            "Web 服务",
            False,
            f"未启动（应监听 {host}:{port}）；查日志 TaskWatcher Web 启动异常",
        )
    else:
        add("Web 服务", True, f"已启动，配置监听 {host}:{port}")
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 7 HTTP 首页
    t0 = time.perf_counter()
    if port <= 0 or not started:
        add("HTTP 首页", False, "跳过（Web 未运行）")
    else:
        try:
            status, body = await _http_get(f"http://127.0.0.1:{port}/")
            if status == 200 and "TaskWatcher" in body:
                add("HTTP 首页", True, f"GET / → {status}")
            else:
                add("HTTP 首页", False, f"GET / → {status}")
        except Exception as e:
            add("HTTP 首页", False, str(e)[:160])
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 8 HTTP /api/taskbook
    t0 = time.perf_counter()
    web_tok = cfg.get("web_read_token")
    if port <= 0 or not started:
        add("HTTP taskbook API", False, "跳过（Web 未运行）")
    elif not web_tok:
        add("HTTP taskbook API", False, "无 web_read_token，请先 /watcher web")
    else:
        try:
            url = f"http://127.0.0.1:{port}/api/taskbook?token={web_tok}"
            status, data = await _http_get_json(url)
            if status == 401:
                add("HTTP taskbook API", False, "invalid_token（会话与发 web 时不一致？）")
            elif status == 200 and data and data.get("ok") is True:
                src = data.get("source") or "?"
                n = len(str(data.get("taskbook") or ""))
                add("HTTP taskbook API", True, f"ok=true，source={src}，约 {n} 字")
            elif status == 200:
                add("HTTP taskbook API", False, f"JSON ok≠true: {str(data)[:80]}")
            else:
                add("HTTP taskbook API", False, f"HTTP {status}")
        except Exception as e:
            add("HTTP taskbook API", False, str(e)[:160])
    steps[-1].elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 9 LLM 跳过说明 + 外链提示
    pub = str(_plugin_cfg_dict(plugin.config).get("web_public_base_url") or "").strip()
    hint = ""
    if pub:
        try:
            p = urlparse(pub)
            if p.port and p.port != port:
                hint = f"；注意 public_url 端口 {p.port} 与监听 {port} 不一致"
        except Exception:
            pass
        base, _ = web_user_link_and_hint(plugin.config)
        hint = f"面板前缀 {base}{hint}"
    add("LLM", True, f"未调用 AI。{hint}".strip() or "未调用 AI")

    return steps


def _plugin_cfg_dict(config_obj: Any) -> dict:
    if isinstance(config_obj, dict):
        return config_obj
    try:
        return dict(config_obj.items())
    except (AttributeError, TypeError):
        return {}


def format_test_report(user_id: str, steps: List[TestStep]) -> List[str]:
    """返回 1～2 条消息文本。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    passed = sum(1 for s in steps if s.ok)
    failed = [s for s in steps if not s.ok and s.name != "LLM"]
    header = [
        f"🧪 TaskWatcher 自检 · {now}",
        f"user_id={user_id or '（空）'}",
        "",
    ]
    body_lines = [s.line() for s in steps]
    footer = [f"结果：{passed}/{len(steps)} 项通过"]
    if failed:
        footer.append("失败项：" + "、".join(s.name for s in failed))
        footer.append("建议：对照失败项检查配置/日志；Web 异常时查「TaskWatcher Web 已启动」。")
    text = "\n".join(header + body_lines + footer)
    if len(text) <= 4000:
        return [text]
    half = len(body_lines) // 2
    return [
        "\n".join(header + body_lines[:half]),
        "\n".join(body_lines[half:] + footer),
    ]
