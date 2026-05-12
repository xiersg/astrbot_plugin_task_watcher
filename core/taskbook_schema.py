"""
任务书稳定结构（YAML）说明与辅助函数。

根文档字段：
- version: 固定为 1
- tree: 根级节点列表，每项为 section（分组，非任务）或 task（任务点），可无限嵌套 children。
"""

from __future__ import annotations

from typing import Any, Dict, List

TASKBOOK_YAML_SCHEMA_DOC = """
## 任务书文件格式（必须严格遵守，整份文件即为有效 YAML，不要用 Markdown 替代）

顶层结构示例（缩进必须为 2 空格）：

    version: 1
    tree:
      - kind: section
        id: sec_ai
        title: "AI端"
        children:
          - kind: task
            id: task_login
            title: "任务点1"
            completion: "完成情况以及尚未完成的部分"
            description: "描述"
            contributors: "贡献（姓名或 @login）"
            paths: "可选，关联仓库路径，逗号分隔，如 src/a.py,src/b/"
            children: []
      - kind: section
        id: sec_api
        title: "后台"
        children:
          - kind: task
            id: t1
            title: "1"
            completion: ""
            description: ""
            contributors: ""
            children:
              - kind: task
                id: t1_a
                title: "子任务"
                completion: ""
                description: ""
                contributors: ""
                children: []

### 规则

1. version 必须为整数 1。
2. tree 为数组；元素 kind 只能是 section 或 task。
3. section 表示非任务分组，字段：id, title, children（数组，可空）。
4. task 字段：id, title, completion, description, contributors（无内容用空字符串 ""）, paths（可选，关联路径字符串）, children（嵌套子任务，可空数组）。
5. 所有 id 全文件唯一，仅使用字母、数字、下划线、连字符。
6. 不要添加未约定的顶层键。

请直接输出完整 YAML 正文，不要用 Markdown 围栏包裹，不要附加说明文字。
"""


def is_taskbook_yaml_v1_document(doc: Any) -> bool:
    """是否为可识别的任务书根文档（version 视为 1 即可，兼容 YAML 将 1 解析为字符串等）。"""
    if not isinstance(doc, dict) or not isinstance(doc.get("tree"), list):
        return False
    v = doc.get("version")
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v == 1
    if isinstance(v, float):
        return v == 1.0
    try:
        return int(float(str(v).strip())) == 1
    except (TypeError, ValueError):
        return False


def count_tasks_in_tree(doc: Any) -> int:
    """统计 kind==task 的节点数量（含任意深度嵌套）。"""
    if not is_taskbook_yaml_v1_document(doc):
        return 0

    def walk(nodes: List[Any]) -> int:
        n = 0
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            k = str(node.get("kind") or "").strip().lower()
            if k == "task":
                n += 1
            n += walk(node.get("children") or [])
        return n

    return walk(doc.get("tree") or [])
