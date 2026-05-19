"""
TaskWatcher - 智能任务监听插件

核心流程：
1. 用户设置 GitHub Token 和 Gist 任务书
2. AI 编排任务书为 YAML 嵌套结构
3. 全面检查项目，标记已完成任务
4. 后续触发监视时分析代码变更
"""

import json
import secrets
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .core.gist_manager import GistManager
from .core.github_client import GitHubAPIClient
from .core.change_digest import format_compare_for_prompt
from .core.taskbook_schema import count_tasks_in_tree, is_taskbook_yaml_v1_document
from .core import prompts
from .core.diagnostics import format_test_report, run_watcher_self_test
from .core.web_server import (
    read_web_listen_config,
    strip_fenced_markdown,
    TaskWatcherWebServer,
    web_user_link_and_hint,
)


def _parse_taskbook_yaml_v1(taskbook: str) -> Optional[dict]:
    """解析成功且为任务书 v1 时返回 dict，否则 None。"""
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


def _taskbook_task_count(taskbook: str) -> int:
    """YAML v1 中 kind==task 的节点数（含嵌套），无效时按 1 计以便分析仍可进行。"""
    doc = _parse_taskbook_yaml_v1(taskbook)
    if not doc:
        return 1
    n = count_tasks_in_tree(doc)
    return max(1, min(30, n or 1))


def _instruction_after_tasks_edit_command(event: AstrMessageEvent) -> str:
    """从整条消息中取出 tasks_edit 子命令后的说明文字（支持空格与多行）。"""
    s = (getattr(event, "message_str", None) or "").strip()
    if not s:
        return ""
    lower = s.lower()
    for marker in ("tasks_edit", "任务书编辑", "编辑任务"):
        i = lower.find(marker.lower())
        if i >= 0:
            return s[i + len(marker) :].strip()
    return ""


@register("astrbot_plugin_task_watcher", "xiersg", "检测Git仓库变化，分析任务完成情况", "1.1.1")
class TaskWatcherPlugin(Star):
    """任务监听插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path("data/task_watcher")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 用户配置: {user_id: {token, gist_id, repo, taskbook_content, ...}}
        self.user_configs: Dict[str, Dict] = {}
        self._web_server: Optional[TaskWatcherWebServer] = None
        self._load_configs()

    async def initialize(self):
        """AstrBot 加载插件后启动本地 Web（若配置了端口）。"""
        self._web_server = TaskWatcherWebServer(self)
        try:
            await self._web_server.start()
        except OSError as e:
            logger.error("TaskWatcher Web 启动失败: %s", e)
        except Exception:
            logger.exception("TaskWatcher Web 启动异常")

    def _load_configs(self):
        """加载用户配置"""
        config_file = self.data_dir / "configs.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.user_configs = json.load(f)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")

    def _save_configs(self):
        """保存用户配置"""
        config_file = self.data_dir / "configs.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _get_user_id(self, event: AstrMessageEvent) -> str:
        """获取用户ID"""
        return event.get_group_id() or event.message_obj.session_id

    @staticmethod
    def _parse_repo(repo: str) -> Tuple[str, str]:
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

    @staticmethod
    def _watch_branch(cfg: Dict[str, Any], repo_info: Optional[Dict[str, Any]] = None) -> str:
        """监视分支：配置 watch_branch 优先，否则用 GitHub 默认分支。"""
        explicit = str(cfg.get("watch_branch") or "").strip()
        if explicit:
            return explicit
        if repo_info:
            return str(repo_info.get("default_branch") or "main")
        return "main"

    # ============ 指令 ============

    @filter.command_group("watcher")
    async def watcher_group(self):
        """任务监听指令组"""
        pass

    @watcher_group.command("help", alias={"帮助"})
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助"""
        event.stop_event()
        help_text = """TaskWatcher 任务监听插件

【配置】
• /watcher set_token <token> - 设置 GitHub Token
  获取: https://github.com/settings/tokens
  权限: **gist**（写 Gist）+ 若仓库为**私有**还需 **repo**（读提交/compare，否则列表提交会 404）

• /watcher set_gist <gist_url> - 设置任务书 Gist；下载后会 **自动 AI 编排为 YAML** 并写回 Gist（失败则保留原文，可再发 /watcher organize）

• /watcher set_repo <repo> [分支] - 设置要监视的仓库（分支可选，省略则用 GitHub 默认分支）
  格式: owner/repo 或 owner/repo develop

• /watcher set_branch [分支] - 单独设置/清除监视分支（留空清除，恢复默认分支）

• /watcher config - 查看当前配置

【任务管理】
• /watcher organize - AI 将任务书重新编排为 YAML 嵌套结构
• /watcher tasks_edit <说明> - AI 按自然语言 **增删/调整任务点**（写回 Gist；说明写在子命令后）
• /watcher check    - 有新提交时：AI 根据 diff/PR 输出 JSON，再合并进 **YAML 任务书** 并同步 Gist

【监视】
• /watcher watch - 查看自上次 check 记录的提交起的增量 diff（hunk 截断预览）
• /watcher status - 查看当前任务完成状态统计

【网页只读面板】插件配置 web_server_port 为本机端口后：
• /watcher web - 返回任务书面板链接（**同一用户复用同一个只读 token**）
• /watcher web_new - **轮换**只读 token 并返回新链接（旧链接立即失效）
  部署在 Linux 服务器、需在飞书等外网打开时：插件配置里 **web_server_host** 填 **0.0.0.0**，**web_public_base_url** 填可从外网访问的完整前缀（如 http://公网IP:端口 或 https://反代域名），详见 README。"""
        yield event.plain_result(help_text)

    @watcher_group.command("set_token")
    async def cmd_set_token(self, event: AstrMessageEvent, token: str):
        """设置 GitHub Token: /watcher set_token <token>"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.user_configs:
            self.user_configs[user_id] = {}

        self.user_configs[user_id]['token'] = token
        self._save_configs()
        yield event.plain_result("✅ Token 已设置")

    @watcher_group.command("set_gist")
    async def cmd_set_gist(self, event: AstrMessageEvent, gist_url: str):
        """设置任务书 Gist: /watcher set_gist <gist_url>"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        gist_id = GistManager.extract_gist_id(gist_url)
        if not gist_id:
            yield event.plain_result("❌ Gist URL 格式错误")
            return

        token = self.user_configs.get(user_id, {}).get('token')
        if not token:
            yield event.plain_result("请先设置 Token: /watcher set_token <token>")
            return

        # 下载任务书
        gist_mgr = GistManager(token)
        content = await gist_mgr.get_gist_content(gist_id)
        if not content:
            yield event.plain_result("❌ 无法获取 Gist 内容，请检查 Token 和 URL")
            return

        if user_id not in self.user_configs:
            self.user_configs[user_id] = {}

        self.user_configs[user_id]["gist_id"] = gist_id
        self.user_configs[user_id]["gist_url"] = gist_url
        self.user_configs[user_id]["taskbook_content"] = content
        self._save_configs()

        cfg = self.user_configs[user_id]
        lines = ["✅ Gist 已设置并下载原文。"]
        try:
            await self._organize_and_sync_gist(cfg)
            lines.append(
                "✅ 首次 AI 编排完成。可设置仓库后使用 /watcher check；也可随时 /watcher organize 重新编排。"
            )
        except Exception as e:
            lines.append(
                f"⚠️ 自动编排失败（已保留 Gist 下载的原文）：{e}\n请配置好聊天模型后执行 /watcher organize"
            )
        yield event.plain_result("\n".join(lines))

    @watcher_group.command("set_repo")
    async def cmd_set_repo(self, event: AstrMessageEvent, repo: str, branch: str = ""):
        """设置监视仓库: /watcher set_repo <repo> [分支]"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        try:
            owner, name = self._parse_repo(repo)
            normalized = f"{owner}/{name}"
        except ValueError as e:
            yield event.plain_result(f"❌ {e}")
            return

        if user_id not in self.user_configs:
            self.user_configs[user_id] = {}

        self.user_configs[user_id]["repo"] = normalized
        br = (branch or "").strip()
        if br:
            self.user_configs[user_id]["watch_branch"] = br
        else:
            self.user_configs[user_id].pop("watch_branch", None)
        self._save_configs()
        branch_line = (
            f"监视分支: {br}" if br else "监视分支: GitHub 默认分支（未单独指定）"
        )
        yield event.plain_result(f"✅ 仓库已设置: {normalized}\n{branch_line}")

    @watcher_group.command("set_branch")
    async def cmd_set_branch(self, event: AstrMessageEvent, branch: str = ""):
        """设置监视分支；留空则恢复 GitHub 默认分支"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return
        if user_id not in self.user_configs:
            self.user_configs[user_id] = {}
        if not self.user_configs[user_id].get("repo"):
            yield event.plain_result("请先 /watcher set_repo <owner/repo>")
            return
        br = (branch or "").strip()
        if br:
            self.user_configs[user_id]["watch_branch"] = br
            msg = f"✅ 监视分支已设为: {br}"
        else:
            self.user_configs[user_id].pop("watch_branch", None)
            msg = "✅ 已清除自定义分支，将使用 GitHub 默认分支"
        self._save_configs()
        yield event.plain_result(msg)

    @watcher_group.command("config")
    async def cmd_config(self, event: AstrMessageEvent):
        """查看配置"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("未配置\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        sha = cfg.get("last_synced_commit")
        sync_line = (
            f"{sha[:12]}…（下次从该提交之后增量 compare）"
            if sha
            else "未记录（首次 /watcher check 成功后会记下当前 HEAD）"
        )
        watch_br = (cfg.get("watch_branch") or "").strip() or "（GitHub 默认分支）"
        text = f"""📋 配置信息
仓库: {cfg.get('repo')}
监视分支: {watch_br}
Gist: {cfg.get('gist_url')}
Token: {'✅ 已设置' if cfg.get('token') else '❌ 未设置'}
上次检查: {cfg.get('last_check', '从未')}
Git 同步进度: {sync_line}"""
        yield event.plain_result(text)

    @watcher_group.command("organize")
    async def cmd_organize(self, event: AstrMessageEvent):
        """AI 编排任务书为 YAML"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("请先配置:\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        if not cfg.get("gist_id"):
            yield event.plain_result("❌ 请先设置 Gist: /watcher set_gist <url>")
            return

        try:
            await self._organize_and_sync_gist(cfg)
            yield event.plain_result(
                "✅ 任务书已编排完成并同步到 Gist\n下一步: /watcher check (全面检查)"
            )
        except Exception as e:
            yield event.plain_result(f"❌ 编排失败: {e}")

    @watcher_group.command("check")
    async def cmd_check(self, event: AstrMessageEvent):
        """全面检查项目，标记已完成任务"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("请先配置:\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        try:
            if not cfg.get("token") or not (cfg.get("repo") or "").strip():
                yield event.plain_result("❌ 需要已设置 token 与仓库（/watcher set_repo）才能拉取 GitHub 提交。")
                return

            if _parse_taskbook_yaml_v1(cfg.get("taskbook_content") or "") is None:
                yield event.plain_result(
                    "❌ 当前任务书不是有效的 YAML v1（需含 version: 1 与 tree）。\n"
                    "请先 /watcher organize，或重新执行 /watcher set_gist 以触发自动编排。"
                )
                return

            changes = await self._get_repo_changes(cfg)

            if changes.get("reset_last_sync"):
                cfg.pop("last_synced_commit", None)
                self._save_configs()

            if changes.get("error"):
                yield event.plain_result(f"❌ GitHub: {changes['error']}")
                return

            if changes.get("no_new_commits"):
                cfg["last_check"] = datetime.now().isoformat()
                self._save_configs()
                yield event.plain_result("无新的 Git 提交，已跳过 AI 与任务书写回。")
                return

            now_zh = datetime.now().strftime("%Y-%m-%d %H时")
            tb = cfg.get("taskbook_content") or ""
            task_count = _taskbook_task_count(tb)
            file_count = int(changes.get("file_count") or 0)
            summary = (changes.get("summary_text") or "")[:12000]
            pr_ctx = (changes.get("pr_hints") or "").strip()
            if not pr_ctx:
                pr_ctx = "（本期变更未关联到合并 PR；可能为直接 push，或提交未出现在 GitHub 的 PR 关联接口中。）"
            pr_ctx = pr_ctx[:6000]

            # AI 分析任务完成度（变更摘要为按文件截断的 hunk）
            prompt = prompts.TASK_ANALYSIS_PROMPT.format(
                repo_name=cfg["repo"],
                repo_desc="",
                task_count=task_count,
                tasks_summary=cfg["taskbook_content"][:8000],
                file_count=file_count,
                changes_summary=summary,
                pr_context=pr_ctx,
                member_count=0,
                members_summary="",
                current_time_zh=now_zh,
            )

            result = await self._call_ai(prompt)

            # 更新任务书
            updated = strip_fenced_markdown(
                await self._call_ai(
                    prompts.TASKBOOK_UPDATE_PROMPT.format(
                        current_content=cfg["taskbook_content"],
                        status_summary=result,
                        current_time_zh=now_zh,
                    )
                )
            )

            # 同步到 Gist
            gist_mgr = GistManager(cfg["token"])
            await gist_mgr.update_taskbook(cfg["gist_id"], updated)

            cfg["taskbook_content"] = updated
            cfg["last_check"] = datetime.now().isoformat()
            head = changes.get("head_sha")
            if head:
                cfg["last_synced_commit"] = head
            self._save_configs()

            yield event.plain_result("✅ 检查完成，任务书已更新")

        except Exception as e:
            yield event.plain_result(f"❌ 检查失败: {e}")

    @watcher_group.command("watch")
    async def cmd_watch(self, event: AstrMessageEvent):
        """触发代码变更监视"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("请先配置:\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        try:
            if not cfg.get("token") or not (cfg.get("repo") or "").strip():
                yield event.plain_result("需要 token 与 set_repo 后才能拉取变更。")
                return

            changes = await self._get_repo_changes(cfg)

            if changes.get("error"):
                yield event.plain_result(f"❌ {changes['error']}")
                return

            if changes.get("no_new_commits"):
                yield event.plain_result("无新提交（与上次 check 记录的进度一致）。")
                return

            fc = int(changes.get("file_count") or 0)
            preview = (changes.get("summary_text") or "")[:3500]
            yield event.plain_result(
                f"👀 自上次记录起的增量：约 {fc} 个文件有 diff（hunk 已截断展示）。\n\n{preview}"
                "\n\n使用 /watcher check 写入任务书并推进同步进度。"
            )

        except Exception as e:
            yield event.plain_result(f"❌ 监视失败: {e}")

    @watcher_group.command("status")
    async def cmd_status(self, event: AstrMessageEvent):
        """查看任务状态"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("未配置")
            return

        content = cfg.get("taskbook_content", "无任务书内容")
        doc = _parse_taskbook_yaml_v1(content)
        if doc is not None:
            yaml_tasks = count_tasks_in_tree(doc)
            text = f"""📊 任务状态（YAML v1）
task 节点数: {yaml_tasks}
上次检查: {cfg.get("last_check", "从未")}
Git 进度: {(cfg.get("last_synced_commit") or "未记录")[:12]}…
Gist: {cfg.get("gist_url")}"""
        else:
            text = f"""📊 任务状态
任务书不是有效的 YAML v1（需 version: 1 与 tree）。
请先 /watcher organize，或重新 /watcher set_gist 触发自动编排。
上次检查: {cfg.get("last_check", "从未")}
Gist: {cfg.get("gist_url")}"""
        yield event.plain_result(text)

    @watcher_group.command("web", alias={"网页", "web_token"})
    async def cmd_web(self, event: AstrMessageEvent):
        """返回本机任务书面板链接；只读 token 首次生成后写入配置并复用（链接稳定）。"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return
        cfg = self.user_configs.get(user_id)
        if not cfg:
            yield event.plain_result("未配置")
            return
        _, port = read_web_listen_config(self.config)
        if port <= 0:
            yield event.plain_result(
                "web_server_port 是插件在本机开的 HTTP 端口（数字，如 8765），"
                "不是完整网址；在 AstrBot 插件配置里把它改成大于 0 并重启后，"
                "再发 /watcher web。"
            )
            return
        token = cfg.get("web_read_token")
        if not token:
            token = secrets.token_urlsafe(24)
            cfg["web_read_token"] = token
            self._save_configs()
        base, hint = web_user_link_and_hint(self.config)
        url = f"{base}/?token={token}"
        yield event.plain_result(url + (f"\n\n{hint}" if hint else ""))

    @watcher_group.command("web_new", alias={"网页新链接", "刷新网页令牌"})
    async def cmd_web_new(self, event: AstrMessageEvent):
        """重新生成只读 token 并返回新链接（旧链接失效）。"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return
        cfg = self.user_configs.get(user_id)
        if not cfg:
            yield event.plain_result("未配置")
            return
        _, port = read_web_listen_config(self.config)
        if port <= 0:
            yield event.plain_result(
                "web_server_port 未启用（需在插件配置中设为大于 0 并重启）。"
            )
            return
        token = secrets.token_urlsafe(24)
        cfg["web_read_token"] = token
        self._save_configs()
        base, hint = web_user_link_and_hint(self.config)
        url = f"{base}/?token={token}"
        yield event.plain_result(
            url + "\n（已轮换 token，旧书签失效）" + (f"\n\n{hint}" if hint else "")
        )

    @watcher_group.command("test")
    async def cmd_test(self, event: AstrMessageEvent):
        """隐藏自检：只读探测配置/GitHub/Gist/Web，不调用 AI（不出现在 help）。"""
        event.stop_event()
        user_id = self._get_user_id(event)
        try:
            # 勿在 await 前 yield：AstrBot 首条回复后会 after_message_sent 终止管道（QQ 等仅见半句）
            steps = await run_watcher_self_test(self, user_id)
            chunks = format_test_report(user_id, steps)
            yield event.plain_result("\n\n".join(chunks))
        except Exception as e:
            logger.exception("watcher test")
            yield event.plain_result(f"❌ 自检异常: {e}")

    @watcher_group.command("tasks_edit", alias={"任务书编辑", "编辑任务"})
    async def cmd_tasks_edit(self, event: AstrMessageEvent):
        """AI 按自然语言增删 YAML 任务点并写回 Gist"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return
        cfg = self.user_configs.get(user_id)
        if not cfg:
            yield event.plain_result(
                "请先配置:\n1. /watcher set_token <token>\n2. /watcher set_gist <url>"
            )
            return
        if not cfg.get("gist_id"):
            yield event.plain_result("❌ 请先设置 Gist: /watcher set_gist <url>")
            return

        instruction = _instruction_after_tasks_edit_command(event)
        if not instruction:
            yield event.plain_result(
                "请在子命令后写明要如何改任务书，例如：\n"
                "/watcher tasks_edit 删除 id 为 task_old 的任务；在「后台」分组下新增标题为「限流」的任务，id 用 task_rl，paths 填 src/limit.py\n"
                "（也支持别名：/任务书编辑 …、/编辑任务 …）"
            )
            return

        if _parse_taskbook_yaml_v1(cfg.get("taskbook_content") or "") is None:
            yield event.plain_result(
                "❌ 当前任务书不是有效 YAML v1。请先 /watcher organize 或 /watcher set_gist。"
            )
            return

        try:
            raw_out = strip_fenced_markdown(
                await self._call_ai(
                    prompts.TASKBOOK_TASKS_EDIT_PROMPT.format(
                        current_content=cfg.get("taskbook_content") or "",
                        instruction=instruction,
                    )
                )
            )
            try:
                doc = yaml.safe_load(raw_out)
            except Exception as e:
                yield event.plain_result(f"❌ AI 输出不是合法 YAML：{e}")
                return
            if not is_taskbook_yaml_v1_document(doc):
                yield event.plain_result(
                    "❌ AI 输出不符合任务书 v1（version + tree）。未写入 Gist，请重试或改写说明。"
                )
                return

            gist_mgr = GistManager(cfg["token"])
            await gist_mgr.update_taskbook(cfg["gist_id"], raw_out)
            cfg["taskbook_content"] = raw_out
            cfg["tasks_edited_at"] = datetime.now().isoformat()
            self._save_configs()
            n = count_tasks_in_tree(doc)
            yield event.plain_result(f"✅ 已更新任务书并同步 Gist（当前共 {n} 个 task 节点）")
        except Exception as e:
            yield event.plain_result(f"❌ 编辑失败: {e}")

    # ============ 辅助方法 ============

    async def _ai_organize_taskbook(self, cfg: Dict[str, Any]) -> str:
        """调用 AI 将 taskbook_content 编排为 YAML 正文（不含写盘）。"""
        return strip_fenced_markdown(
            await self._call_ai(
                prompts.TASKBOOK_ORGANIZE_PROMPT.format(
                    content=cfg.get("taskbook_content") or ""
                )
            )
        )

    async def _organize_and_sync_gist(self, cfg: Dict[str, Any]) -> str:
        """编排后写 Gist 与本地 taskbook_content，并记下 organized_at。"""
        organized = await self._ai_organize_taskbook(cfg)
        gist_mgr = GistManager(cfg["token"])
        await gist_mgr.update_taskbook(cfg["gist_id"], organized)
        cfg["taskbook_content"] = organized
        cfg["organized_at"] = datetime.now().isoformat()
        self._save_configs()
        return organized

    async def _call_ai(self, prompt: str) -> str:
        """调用 AI 生成"""
        provider_id = await self.context.get_current_chat_provider_id(umo="taskwatcher")
        if not provider_id:
            raise ValueError("未配置聊天模型")

        resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        return resp.completion_text.strip()

    @staticmethod
    def _fmt_github_err(message: str, owner: str, repo: str) -> str:
        if "404" not in message and "Not Found" not in message:
            return message
        slug = f"{owner}/{repo}"
        return (
            f"{message}\n\n"
            f"请求 `{slug}` 失败时常见原因：\n"
            "• owner/repo 与 GitHub 不一致，或仓库不存在。\n"
            "• **私有仓库**：Token 需在 https://github.com/settings/tokens 勾选 **repo**（读代码）；"
            "仅有 **gist** 权限时访问私有库常被误报为 **404**。\n"
            "• 仓库已删除、迁移或无权访问。"
        )

    async def _collect_pr_hints(
        self,
        client: GitHubAPIClient,
        owner: str,
        repo: str,
        compare_data: Dict[str, Any],
        max_commits: int = 12,
    ) -> str:
        """从 compare 范围内的提交拉取关联 PR 的标题与正文（成员用于写明任务点）。"""
        seen_pr_nums = set()
        lines: List[str] = []
        for c in (compare_data.get("commits") or [])[:max_commits]:
            sha = c.get("sha")
            if not sha:
                continue
            try:
                prs = await client.list_commit_pulls(owner, repo, sha)
            except Exception:
                logger.debug("list_commit_pulls 跳过 %s", sha[:7])
                continue
            for pr in prs:
                num = pr.get("number")
                if num is None or num in seen_pr_nums:
                    continue
                seen_pr_nums.add(int(num))
                title = (pr.get("title") or "").strip()
                body = (pr.get("body") or "").strip()[:2800]
                login = (pr.get("user") or {}).get("login") or ""
                merged = pr.get("merged_at") or ""
                lines.append(
                    f"PR #{num} @{login} merged_at={merged}\n标题: {title}\n描述:\n{body}\n---"
                )
        return "\n".join(lines)

    async def _get_repo_changes(self, cfg: Dict) -> Dict[str, Any]:
        """
        从上次记录的 last_synced_commit 到当前监视分支 HEAD 做 compare，
        分支见 watch_branch，未设置则用 GitHub 默认分支。
        摘要为按文件截断的 patch（hunk），节省 token。
        """
        out: Dict[str, Any] = {
            "head_sha": None,
            "file_count": 0,
            "summary_text": "",
            "commits_range": "",
        }
        token = cfg.get("token")
        repo_s = (cfg.get("repo") or "").strip()
        if not token or not repo_s:
            out["summary_text"] = "(未设置 token 或 repo)"
            return out

        try:
            owner, repo = self._parse_repo(repo_s)
        except ValueError as e:
            out["error"] = str(e)
            return out

        client = GitHubAPIClient(token)
        try:
            repo_info = await client.get_repository_info(owner, repo)
        except Exception as e:
            out["error"] = self._fmt_github_err(str(e), owner, repo)
            return out

        branch = self._watch_branch(cfg, repo_info)

        try:
            commits = await client.get_commits(
                owner, repo, limit=100, sha=branch
            )
        except Exception as e:
            out["error"] = self._fmt_github_err(str(e), owner, repo)
            return out

        if not commits:
            out["summary_text"] = "仓库无提交记录"
            return out

        head_sha = commits[0]["sha"]
        out["head_sha"] = head_sha
        last = (cfg.get("last_synced_commit") or "").strip()

        if last == head_sha:
            out["no_new_commits"] = True
            out["summary_text"] = "自上次记录以来无新提交。"
            return out

        try:
            if last:
                data = await client.compare_commits(owner, repo, last, head_sha)
                out["commits_range"] = f"{last[:7]}..{head_sha[:7]}"
            else:
                depth = min(10, len(commits))
                if len(commits) >= 2:
                    base_sha = commits[depth - 1]["sha"]
                    data = await client.compare_commits(owner, repo, base_sha, head_sha)
                    out["commits_range"] = f"bootstrap:{base_sha[:7]}..{head_sha[:7]}"
                else:
                    detail = await client.get_commit_detail(owner, repo, head_sha)
                    data = {
                        "status": "bootstrap_single",
                        "total_commits": 1,
                        "ahead_by": 1,
                        "commits": [
                            {"sha": head_sha, "commit": detail.get("commit") or {}}
                        ],
                        "files": detail.get("files") or [],
                    }
                    out["commits_range"] = f"bootstrap:single:{head_sha[:7]}"

            pr_raw = await self._collect_pr_hints(client, owner, repo, data)
            out["pr_hints"] = (pr_raw or "")[:8000]

            text, fc = format_compare_for_prompt(data)
            out["summary_text"] = text
            out["file_count"] = fc
        except Exception as e:
            err = self._fmt_github_err(str(e), owner, repo)
            out["error"] = err
            if "404" in err or "422" in err:
                out["reset_last_sync"] = True
            return out

        return out

    async def terminate(self):
        """插件销毁"""
        ws = getattr(self, "_web_server", None)
        if ws is not None:
            try:
                await ws.stop()
            except Exception as e:
                logger.warning("TaskWatcher Web 停止时异常: %s", e)
        self._save_configs()
        logger.info("TaskWatcher 插件已卸载")
