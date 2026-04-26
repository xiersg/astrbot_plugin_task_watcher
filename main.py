"""
TaskWatcher - 智能任务监听插件

核心流程：
1. 用户设置 GitHub Token 和 Gist 任务书
2. AI 编排任务书为 Markdown 格式
3. 全面检查项目，标记已完成任务
4. 后续触发监视时分析代码变更
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .core.gist_manager import GistManager
from .core.github_client import GitHubAPIClient
from .core import prompts


@register("astrbot_plugin_task_watcher", "xiersg", "检测Git仓库变化，分析任务完成情况", "1.0.0")
class TaskWatcherPlugin(Star):
    """任务监听插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path("data/task_watcher")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 用户配置: {user_id: {token, gist_id, repo, taskbook_content, ...}}
        self.user_configs: Dict[str, Dict] = {}
        self._load_configs()

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
  Token 获取: https://github.com/settings/tokens
  所需权限: gist

• /watcher set_gist <gist_url> - 设置任务书 Gist 链接
  格式: https://gist.github.com/用户名/gistID

• /watcher set_repo <repo> - 设置要监视的仓库
  格式: 用户名/仓库名 (如: owner/repo)

• /watcher config - 查看当前配置

【任务管理】
• /watcher organize - AI 将任务书重新编排为 Markdown 格式
• /watcher check    - 全面检查仓库代码，标记已完成的任务

【监视】
• /watcher watch - 触发代码变更监视（查看自上次检查后的变更）
• /watcher status - 查看当前任务完成状态统计"""
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

        self.user_configs[user_id]['gist_id'] = gist_id
        self.user_configs[user_id]['gist_url'] = gist_url
        self.user_configs[user_id]['taskbook_content'] = content
        self._save_configs()
        yield event.plain_result("✅ Gist 已设置并下载任务书")

    @watcher_group.command("set_repo")
    async def cmd_set_repo(self, event: AstrMessageEvent, repo: str):
        """设置监视仓库: /watcher set_repo <repo>"""
        event.stop_event()
        user_id = self._get_user_id(event)
        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.user_configs:
            self.user_configs[user_id] = {}

        self.user_configs[user_id]['repo'] = repo
        self._save_configs()
        yield event.plain_result(f"✅ 仓库已设置: {repo}")

    @watcher_group.command("config")
    async def cmd_config(self, event: AstrMessageEvent):
        """查看配置"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("未配置\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        text = f"""📋 配置信息
仓库: {cfg.get('repo')}
Gist: {cfg.get('gist_url')}
Token: {'✅ 已设置' if cfg.get('token') else '❌ 未设置'}
上次检查: {cfg.get('last_check', '从未')}"""
        yield event.plain_result(text)

    @watcher_group.command("organize")
    async def cmd_organize(self, event: AstrMessageEvent):
        """AI 编排任务书为 Markdown"""
        event.stop_event()
        user_id = self._get_user_id(event)
        cfg = self.user_configs.get(user_id)

        if not cfg:
            yield event.plain_result("请先配置:\n1. /watcher set_token <token>\n2. /watcher set_gist <url>\n3. /watcher set_repo <repo>")
            return

        yield event.plain_result("正在重新编排任务书...")

        try:
            organized = await self._call_ai(
                prompts.TASKBOOK_ORGANIZE_PROMPT.format(content=cfg['taskbook_content'])
            )

            # 更新 Gist
            gist_mgr = GistManager(cfg['token'])
            await gist_mgr.update_taskbook(cfg['gist_id'], organized)

            # 保存本地
            cfg['taskbook_content'] = organized
            cfg['organized_at'] = datetime.now().isoformat()
            self._save_configs()

            yield event.plain_result("✅ 任务书已编排完成并同步到 Gist")
            yield event.plain_result("下一步: /watcher check (全面检查)")

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

        yield event.plain_result("🔍 正在全面检查项目...")

        try:
            # 获取代码变更
            changes = await self._get_repo_changes(cfg)

            # AI 分析任务完成度
            prompt = prompts.TASK_ANALYSIS_PROMPT.format(
                repo_name=cfg['repo'],
                repo_desc="",
                task_count=10,
                tasks_summary=cfg['taskbook_content'][:2000],
                file_count=len(changes),
                changes_summary=str(changes)[:1500],
                member_count=0,
                members_summary=""
            )

            result = await self._call_ai(prompt)

            # 更新任务书
            updated = await self._call_ai(
                prompts.TASKBOOK_UPDATE_PROMPT.format(
                    current_content=cfg['taskbook_content'],
                    status_summary=result
                )
            )

            # 同步到 Gist
            gist_mgr = GistManager(cfg['token'])
            await gist_mgr.update_taskbook(cfg['gist_id'], updated)

            cfg['taskbook_content'] = updated
            cfg['last_check'] = datetime.now().isoformat()
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

        yield event.plain_result("👀 监视代码变更...")

        try:
            changes = await self._get_repo_changes(cfg)

            # 简化分析，后续扩展
            if changes:
                yield event.plain_result(f"检测到 {len(changes)} 个文件变更")
                yield event.plain_result("使用 /watcher check 更新任务进度")
            else:
                yield event.plain_result("暂无代码变更")

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

        content = cfg.get('taskbook_content', '无任务书内容')
        # 简单统计
        completed = content.count('[x]') + content.count('✅')
        total = content.count('- [')

        text = f"""📊 任务状态
已完成: {completed}/{total}
上次检查: {cfg.get('last_check', '从未')}
Gist: {cfg.get('gist_url')}"""
        yield event.plain_result(text)

    # ============ 辅助方法 ============

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

    async def _get_repo_changes(self, cfg: Dict) -> Dict:
        """获取仓库代码变更"""
        # TODO: 实现代码变更获取
        # 目前返回空，后续扩展
        return {}

    async def terminate(self):
        """插件销毁"""
        self._save_configs()
        logger.info("TaskWatcher 插件已卸载")
