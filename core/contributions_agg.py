"""
贡献热力图：按 UTC 日从 GitHub 提交与已合并 PR 聚合（供 Web /api/contributions）。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .github_client import GitHubAPIClient


def parse_repo_slug(repo: str) -> Tuple[str, str]:
    """与 main._parse_repo 一致：得到 owner、仓库名。"""
    s = (repo or "").strip().rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    low = s.lower()
    if "github.com" in low:
        idx = low.find("github.com")
        tail = [p for p in s[idx + len("github.com") :].strip("/").split("/") if p]
        if len(tail) >= 2:
            return tail[0], tail[1]
    if "/" in s:
        a, b = s.split("/", 1)
        return a.strip(), b.split("/")[0].strip()
    raise ValueError("仓库格式应为 owner/repo 或 https://github.com/owner/repo")


def _iso_to_utc_day(iso: str) -> Optional[str]:
    if not iso or not isinstance(iso, str):
        return None
    try:
        s = iso.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


async def build_contributions_calendar(
    client: GitHubAPIClient,
    owner: str,
    repo: str,
    days: int,
) -> Dict[str, Any]:
    """
    返回前端热力图所需结构。日期键为 UTC 的 YYYY-MM-DD。
    """
    days_i = max(7, min(int(days), 800))
    end_d = datetime.now(timezone.utc).date()
    start_d = end_d - timedelta(days=days_i - 1)
    since_iso = (
        datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )
    since_day = start_d.isoformat()

    commits = await client.fetch_commits_since(owner, repo, since_iso, max_pages=50)
    prs, pr_truncated = await client.fetch_merged_pulls_search(
        owner, repo, since_day, max_results=1000
    )

    day_map: Dict[str, Dict[str, Any]] = {}

    def ensure_day(dk: str) -> Dict[str, Any]:
        if dk not in day_map:
            day_map[dk] = {
                "commit_count": 0,
                "pr_count": 0,
                "by_login": defaultdict(lambda: {"commits": 0, "prs": 0}),
                "commits": [],
                "prs": [],
            }
        return day_map[dk]

    max_commit_preview = 35
    max_pr_preview = 25

    for c in commits:
        dk = _iso_to_utc_day(c.get("date") or "")
        if not dk or dk < since_day or dk > end_d.isoformat():
            continue
        row = ensure_day(dk)
        row["commit_count"] += 1
        login = str(c.get("login") or "（无 GitHub 登录名）")
        row["by_login"][login]["commits"] += 1
        if len(row["commits"]) < max_commit_preview:
            row["commits"].append(
                {
                    "sha": c.get("sha"),
                    "login": login,
                    "message": c.get("message"),
                    "html_url": c.get("html_url"),
                }
            )

    for p in prs:
        dk = p.get("merged_day") or ""
        if not dk or dk < since_day or dk > end_d.isoformat():
            continue
        row = ensure_day(dk)
        row["pr_count"] += 1
        login = str(p.get("login") or "（无 GitHub 登录名）")
        row["by_login"][login]["prs"] += 1
        if len(row["prs"]) < max_pr_preview:
            row["prs"].append(
                {
                    "number": p.get("number"),
                    "title": p.get("title"),
                    "login": login,
                    "html_url": p.get("html_url"),
                }
            )

    max_activity = 0
    for row in day_map.values():
        t = int(row["commit_count"]) + int(row["pr_count"])
        if t > max_activity:
            max_activity = t
        bl = row["by_login"]
        row["by_login"] = {k: dict(v) for k, v in bl.items()}
        logins = sorted(
            bl.keys(),
            key=lambda u: (bl[u]["commits"] + bl[u]["prs"], bl[u]["prs"], bl[u]["commits"]),
            reverse=True,
        )
        row["contributors"] = logins

    return {
        "ok": True,
        "enabled": True,
        "repo": f"{owner}/{repo}",
        "range_start": since_day,
        "range_end": end_d.isoformat(),
        "utc_note": "按提交时间与 PR 合并时间的 UTC 日期聚合。",
        "pr_search_truncated": pr_truncated,
        "days": day_map,
        "max_activity": max_activity,
    }
