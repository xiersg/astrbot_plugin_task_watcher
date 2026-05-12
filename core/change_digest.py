"""
将 GitHub compare / commit detail 的 JSON 压成「按文件 + hunk(patch) 截断」的短文本，供 LLM 省 token。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _trunc_patch(patch: Optional[str], max_chars: int) -> str:
    if not patch:
        return ""
    if len(patch) <= max_chars:
        return patch
    return patch[:max_chars] + "\n... [patch 已截断]"


def format_compare_for_prompt(
    data: Dict[str, Any],
    *,
    max_files: int = 25,
    patch_chars_per_file: int = 900,
) -> Tuple[str, int]:
    """
    将 compare API（或结构相近的单提交详情）格式化为可读摘要。

    Returns:
        (summary_text, file_count)
    """
    lines: List[str] = []
    lines.append(
        "compare: "
        f"status={data.get('status')} "
        f"total_commits={data.get('total_commits', 0)} "
        f"ahead_by={data.get('ahead_by', 0)}"
    )

    for c in (data.get("commits") or [])[:18]:
        sha = (c.get("sha") or "")[:7]
        cmt = c.get("commit") or {}
        msg = (cmt.get("message") or "").split("\n")[0].strip()[:200]
        author = (cmt.get("author") or {}).get("name") or ""
        lines.append(f"commit {sha}  {author}: {msg}")

    files: List[Dict[str, Any]] = list(data.get("files") or [])
    lines.append(f"files_changed: {len(files)}")

    for f in files[:max_files]:
        path = f.get("filename") or "?"
        st = f.get("status") or "?"
        ad = f.get("additions", 0)
        de = f.get("deletions", 0)
        patch = _trunc_patch(f.get("patch"), patch_chars_per_file)
        lines.append(f">>> {path}  ({st}) +{ad}/-{de}")
        if patch:
            lines.append(patch)
        else:
            lines.append("(无 patch 或过大已省略，仅路径与行数)")

    if len(files) > max_files:
        lines.append(f"... 另有 {len(files) - max_files} 个文件未展开")

    return "\n".join(lines), len(files)
