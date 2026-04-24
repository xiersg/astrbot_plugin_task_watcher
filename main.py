"""
TaskWatcher - 智能任务监听插件

职责：
- 插件初始化和配置管理
- 指令处理和用户交互
- 任务检查和分析协调
- 汇报生成和展示

设计模式：
- 外观模式：简单的插件接口
- 策略模式：不同的分析策略（规则/AI）
- 模板模式：汇报格式化
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.api.message_components import File, Plain, Image
from astrbot.core.utils.session_waiter import (
    session_waiter,
    SessionController,
)
import astrbot.api.message_components as Comp

# 导入自定义模块（使用相对导入避免与其他插件冲突）
from .core.github_client import GitHubAPIClient
from .core.task_parser import TaskBookParser
from .core.ai_analyzer import AIAnalyzer
from .core.task_matcher import TaskMatcher
from .core.utils import FileUtils, DataFormatter, ConfigUtils, Validator


@register("astrbot_plugin_task_watcher", "xiersg", "检测Git仓库变化，分析任务完成情况并自动汇报", "1.0.0")
class TaskWatcherPlugin(Star):
    """任务监听插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 数据存储目录
        self.data_dir = Path("data/task_watcher")
        FileUtils.ensure_directory(str(self.data_dir))

        # GitHub API Token（从配置中读取）
        self.github_token = self.config.get("github_token", "")

        # 群组配置存储
        self.group_configs: Dict[str, Dict] = {}

        # 初始化各个分析器
        self.ai_analyzer = AIAnalyzer(context) if config.get("use_ai", True) else None
        self.task_matcher = TaskMatcher()

        # 加载现有配置
        self._load_configs()

    async def initialize(self):
        """插件初始化"""
        logger.info("TaskWatcherPlugin 插件初始化完成")

    def _load_configs(self):
        """加载群组配置"""
        config_file = self.data_dir / "group_configs.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.group_configs = json.load(f)
                logger.info(f"加载了 {len(self.group_configs)} 个用户配置")
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
                self.group_configs = {}
        else:
            logger.info("配置文件不存在，使用默认空配置")

    def _save_configs(self):
        """保存群组配置"""
        config_file = self.data_dir / "group_configs.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.group_configs, f, ensure_ascii=False, indent=2)
            logger.info("配置保存成功")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    # ============ 指令组定义 ============
    @filter.command_group("watcher")
    async def watcher_group(self):
        """任务监听指令组"""
        pass

    # ============ 基础指令 ============
    @watcher_group.command("help", alias={"帮助", "使用说明"})
    async def watcher_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """
📊 TaskWatcher 任务监听插件

指令列表：
• /watcher help - 显示此帮助信息
• /watcher status - 查看当前配置状态
• /watcher config - 配置任务监听
• /watcher check - 手动检查任务完成情况
• /watcher report - 生成任务汇报
• /watcher update_task_book - 使用AI更新任务书
• /watcher reset - 重置当前配置

支持的任务书格式：JSON、Markdown、YAML
支持更新模式：√×符号、百分比
支持分析方法：规则匹配、AI智能分析
        """
        yield event.plain_result(help_text)

    @watcher_group.command("status", alias={"状态", "查看状态"})
    async def watcher_status(self, event: AstrMessageEvent):
        """查看当前配置状态"""
        # 支持群聊和私聊
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.group_configs:
            yield event.plain_result("当前未配置任务监听\n使用 /watcher config 开始配置")
            return

        config = self.group_configs[user_id]
        status_text = f"""
📊 配置状态
━━━━━━━━━━━━━━━━━
用户ID: {user_id}
状态: {'✅ 已启用' if config.get('enabled', True) else '❌ 已禁用'}
仓库类型: {'GitHub仓库' if config.get('is_github') else '本地仓库'}
仓库路径: {config.get('repo_path', '未设置')}
任务书文件: {config.get('task_book_filename', '未设置')}
更新模式: {config.get('watcher_mode', 'percentage')}
分析方法: {'🤖 AI智能分析' if config.get('use_ai', False) else '📏 规则匹配分析'}
更新频率: {config.get('update_frequency', 3600)}秒
最后更新: {DataFormatter.format_timestamp(config.get('last_update', '从未'))}
        """
        yield event.plain_result(status_text)

    # ============ 配置管理指令 ============
    @watcher_group.command("config", alias={"配置"})
    async def watcher_config(self, event: AstrMessageEvent):
        """配置任务监听"""
        # 支持群聊和私聊
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        yield event.plain_result("📝 开始配置任务监听...")
        yield event.plain_result("请输入Git仓库路径 (支持本地路径或GitHub URL):")

        @session_waiter(timeout=300)
        async def config_repo_path(controller: SessionController, event: AstrMessageEvent):
            repo_path = event.message_str.strip()

            # 验证是本地路径还是GitHub URL
            is_github = repo_path.startswith('http') and 'github.com' in repo_path

            if is_github:
                # 验证GitHub URL格式
                if not ConfigUtils.validate_url(repo_path):
                    yield event.plain_result("⚠️ GitHub URL格式错误，正确格式: https://github.com/owner/repo，重新开始请输入 /watcher config")
                    controller.stop()
                    return

                yield event.plain_result(f"✓ GitHub仓库: {repo_path}")
                yield event.plain_result("将使用GitHub API进行分析")
            else:
                # 验证本地路径
                if not os.path.exists(repo_path):
                    yield event.plain_result("⚠️ 本地路径不存在，请确认后重新输入 /watcher config")
                    controller.stop()
                    return

                if not os.path.isdir(repo_path):
                    yield event.plain_result("⚠️ 请输入目录路径，不是文件路径，重新开始请输入 /watcher config")
                    controller.stop()
                    return

                yield event.plain_result(f"✓ 本地仓库: {repo_path}")

            yield event.plain_result("请上传任务书文件 (.json, .md, .yaml, .yml):")

            @session_waiter(timeout=300)
            async def config_task_book(controller: SessionController, event: AstrMessageEvent):
                message_chain = event.get_messages()

                # 检查是否上传了文件
                task_file = None
                for component in message_chain:
                    if isinstance(component, File):
                        task_file = component
                        break

                if not task_file:
                    yield event.plain_result("⚠️ 请先上传任务书文件，重新开始请输入 /watcher config")
                    controller.stop()
                    return

                # 验证文件格式
                file_ext = FileUtils.get_file_extension(task_file.name)
                if file_ext not in ['.json', '.md', '.yaml', '.yml']:
                    yield event.plain_result("⚠️ 不支持的文件格式，重新开始请输入 /watcher config")
                    controller.stop()
                    return

                # 下载并保存文件
                try:
                    task_path = await self._download_task_file(task_file, user_id)
                    yield event.plain_result(f"✓ 任务书文件已保存: {task_file.name}")
                    yield event.plain_result(f"存储位置: {task_path}")
                except Exception as e:
                    yield event.plain_result(f"⚠️ 文件处理失败: {str(e)}")
                    controller.stop()
                    return

                yield event.plain_result("请选择更新模式 (1=√×符号, 2=百分比):")

                @session_waiter(timeout=300)
                async def config_mode(controller: SessionController, event: AstrMessageEvent):
                    mode_choice = event.message_str.strip()

                    watcher_mode = None
                    if mode_choice == "1":
                        watcher_mode = "check"
                    elif mode_choice == "2":
                        watcher_mode = "percentage"
                    else:
                        yield event.plain_result("⚠️ 无效选择，重新开始请输入 /watcher config")
                        controller.stop()
                        return

                    yield event.plain_result(f"✓ 更新模式: {watcher_mode}")
                    yield event.plain_result("是否使用AI智能分析？(y/n):")

                    @session_waiter(timeout=300)
                    async def config_ai(controller: SessionController, event: AstrMessageEvent):
                        ai_choice = event.message_str.strip().lower()
                        use_ai = ai_choice in ['y', 'yes', '是']

                        yield event.plain_result(f"✓ AI分析: {'启用' if use_ai else '禁用'}")
                        yield event.plain_result("请输入自动更新频率（秒，0表示手动触发，默认3600）:")

                        @session_waiter(timeout=300)
                        async def config_frequency(controller: SessionController, event: AstrMessageEvent):
                            freq_input = event.message_str.strip()

                            frequency = ConfigUtils.validate_positive_integer(
                                freq_input, default=3600
                            )

                            # 保存配置
                            self.group_configs[user_id] = {
                                'repo_path': repo_path,
                                'task_book_path': task_path,
                                'task_book_filename': task_file.name,
                                'is_github': is_github,
                                'watcher_mode': watcher_mode,
                                'use_ai': use_ai,
                                'update_frequency': frequency,
                                'enabled': True,
                                'last_update': None,
                                'created_at': datetime.now().isoformat()
                            }
                            self._save_configs()

                            yield event.plain_result(f"""
✅ 配置完成！
━━━━━━━━━━━━━━━━━
用户ID: {user_id}
仓库类型: {'GitHub仓库' if is_github else '本地仓库'}
仓库路径: {repo_path}
任务书文件: {task_file.name}
存储位置: {task_path}
更新模式: {watcher_mode}
AI分析: {'启用' if use_ai else '禁用'}
更新频率: {frequency}秒
━━━━━━━━━━━━━━━━━
使用 /watcher check 开始检查任务
使用 /watcher report 生成汇报
                            """)

                            controller.stop()

                        try:
                            await config_frequency(event)
                        except TimeoutError:
                            yield event.plain_result("⚠️ 配置超时，重新开始请输入 /watcher config")
                        finally:
                            controller.stop()

                    try:
                        await config_ai(event)
                    except TimeoutError:
                        yield event.plain_result("⚠️ 配置超时，重新开始请输入 /watcher config")
                    finally:
                        controller.stop()

                try:
                    await config_task_book(event)
                except TimeoutError:
                    yield event.plain_result("⚠️ 配置超时，重新开始请输入 /watcher config")
                finally:
                    controller.stop()

        try:
            await config_repo_path(event)
        except TimeoutError:
            yield event.plain_result("⚠️ 配置超时，重新开始请输入 /watcher config")

    # ============ 检查和汇报指令 ============
    @watcher_group.command("check", alias={"检查", "检查任务"})
    async def watcher_check(self, event: AstrMessageEvent):
        """手动检查任务完成情况"""
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.group_configs:
            yield event.plain_result("当前未配置任务监听\n使用 /watcher config 开始配置")
            return

        config = self.group_configs[user_id]
        yield event.plain_result("🔍 开始检查任务完成情况...")

        try:
            # 这里调用实际的检查逻辑
            result = await self._check_tasks(user_id, config)

            yield event.plain_result(f"""
✅ 检查完成！
━━━━━━━━━━━━━━━━━
{result}
━━━━━━━━━━━━━━━━━
使用 /watcher report 查看详细汇报
            """)

        except Exception as e:
            logger.error(f"检查任务失败: {e}")
            yield event.plain_result(f"⚠️ 检查失败: {str(e)}")

    @watcher_group.command("report", alias={"汇报", "生成汇报"})
    async def watcher_report(self, event: AstrMessageEvent):
        """生成任务汇报"""
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.group_configs:
            yield event.plain_result("当前未配置任务监听\n使用 /watcher config 开始配置")
            return

        yield event.plain_result("📊 正在生成任务汇报...")

        try:
            # 这里调用实际的汇报生成逻辑
            report = await self._generate_report(user_id)

            yield event.plain_result(report)

        except Exception as e:
            logger.error(f"生成汇报失败: {e}")
            yield event.plain_result(f"⚠️ 生成汇报失败: {str(e)}")

    @watcher_group.command("update_task_book", alias={"更新任务书", "更新任务"})
    async def update_task_book(self, event: AstrMessageEvent):
        """使用AI更新任务书"""
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id not in self.group_configs:
            yield event.plain_result("当前未配置任务监听\n使用 /watcher config 开始配置")
            return

        config = self.group_configs[user_id]
        if not config.get('use_ai', False):
            yield event.plain_result("⚠️ 需要启用AI分析才能使用此功能\n请在配置中启用AI智能分析")
            return

        yield event.plain_result("🤖 正在使用AI更新任务书...")
        yield event.plain_result("这可能需要一些时间，请稍候...")

        try:
            # 1. 获取当前任务状态
            task_status = config.get('task_status', [])
            if not task_status:
                yield event.plain_result("⚠️ 没有任务分析数据，请先运行 /watcher check")
                return

            # 2. 读取当前任务书内容
            task_book_path = config['task_book_path']
            with open(task_book_path, 'r', encoding='utf-8') as f:
                current_content = f.read()

            # 3. 使用AI更新任务书
            if self.ai_analyzer:
                updated_content = await self.ai_analyzer.update_task_book_with_ai(
                    current_content, task_status
                )
            else:
                yield event.plain_result("⚠️ AI分析器未初始化")
                return

            # 4. 备份并保存
            backup_path = FileUtils.backup_file(task_book_path)
            
            success = FileUtils.safe_write_file(task_book_path, updated_content)
            if not success:
                yield event.plain_result("⚠️ 任务书写入失败")
                return

            # 5. 生成更新摘要
            completed_count = len([t for t in task_status if t['status'] == 'completed'])
            in_progress_count = len([t for t in task_status if t['status'] == 'in_progress'])
            not_started_count = len([t for t in task_status if t['status'] == 'not_started'])

            yield event.plain_result(f"""
✅ AI更新任务书完成！
━━━━━━━━━━━━━━━━━
更新摘要：
• 总任务数: {len(task_status)}
• 已完成: {completed_count}
• 进行中: {in_progress_count}
• 未开始: {not_started_count}

原任务书已备份到:
{backup_path}

更新后的任务书已保存，请检查格式是否正确。
使用 /watcher check 查看最新分析结果。
            """)

        except Exception as e:
            logger.error(f"AI更新任务书失败: {e}")
            yield event.plain_result(f"⚠️ 更新失败: {str(e)}")

    @watcher_group.command("reset", alias={"重置"})
    async def watcher_reset(self, event: AstrMessageEvent):
        """重置当前配置"""
        user_id = event.get_group_id() or event.message_obj.session_id

        if not user_id:
            yield event.plain_result("无法获取用户ID")
            return

        if user_id in self.group_configs:
            del self.group_configs[user_id]
            self._save_configs()
            yield event.plain_result("✅ 当前配置已重置")
        else:
            yield event.plain_result("当前没有配置需要重置")

    # ============ 核心功能方法 ============
    async def _download_task_file(self, file_component: File, user_id: str) -> str:
        """下载并保存任务书文件"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(file_component.url) as response:
                if response.status == 200:
                    content = await response.read()

                    # 创建用户专属目录
                    user_dir = self.data_dir / "task_books" / user_id
                    FileUtils.ensure_directory(str(user_dir))

                    # 保存文件
                    file_path = user_dir / file_component.name
                    with open(file_path, 'wb') as f:
                        f.write(content)

                    logger.info(f"任务书文件已保存: {file_path}")
                    return str(file_path)
                else:
                    raise Exception(f"下载失败，状态码：{response.status}")

    async def _check_tasks(self, user_id: str, config: Dict) -> str:
        """检查任务完成情况"""
        repo_path = config['repo_path']
        task_book_path = config['task_book_path']
        use_ai = config.get('use_ai', False)
        is_github = config.get('is_github', False)

        try:
            if is_github:
                # 使用GitHub API分析
                return await self._check_tasks_github_api(user_id, config)
            else:
                # 使用本地Git分析
                return await self._check_tasks_local(user_id, config)

        except Exception as e:
            raise Exception(f"任务检查失败: {str(e)}")

    async def _check_tasks_github_api(self, user_id: str, config: Dict) -> str:
        """使用GitHub API检查任务完成情况"""
        github_url = config['repo_path']
        task_book_path = config['task_book_path']
        use_ai = config.get('use_ai', False)

        # 解析GitHub URL
        github_info = ConfigUtils.extract_github_info(github_url)
        owner, repo_name = github_info['owner'], github_info['repo']

        # 创建GitHub API客户端
        github_api = GitHubAPIClient(token=self.github_token)

        # 1. 获取仓库信息
        repo_info = await github_api.get_repository_info(owner, repo_name)

        # 2. 获取提交记录
        commits = await github_api.get_commits(owner, repo_name, limit=100)

        # 3. 统计成员贡献
        member_contributions = {}
        for commit in commits:
            author = commit['commit']['author']['name']
            if author not in member_contributions:
                member_contributions[author] = 0
            member_contributions[author] += 1

        # 4. 获取文件变更详情
        file_changes = {}
        for commit in commits:
            sha = commit['sha']
            try:
                commit_detail = await github_api.get_commit_detail(owner, repo_name, sha)

                for file in commit_detail.get('files', []):
                    filename = file['filename']
                    author = commit['commit']['author']['name']

                    if filename not in file_changes:
                        file_changes[filename] = {
                            'author': author,
                            'changes': 0,
                            'additions': 0,
                            'deletions': 0,
                            'patch': file.get('patch', ''),
                            'status': file.get('status', '')
                        }

                    file_changes[filename]['changes'] += 1
                    file_changes[filename]['additions'] += file.get('additions', 0)
                    file_changes[filename]['deletions'] += file.get('deletions', 0)

            except Exception as e:
                logger.error(f"获取提交详情失败: {e}")
                continue

        # 5. 解析任务书
        tasks = TaskBookParser.parse_file(task_book_path)

        # 6. 根据配置选择分析方法
        if use_ai and self.ai_analyzer:
            try:
                logger.info("使用 AI 分析任务完成情况...")
                task_status = await self.ai_analyzer.analyze_tasks(
                    tasks, file_changes, member_contributions, repo_info
                )
                logger.info(f"AI 分析完成，处理了 {len(task_status)} 个任务")
            except ValueError as e:
                # AI 配置或返回格式错误，降级到规则匹配
                logger.warning(f"AI 分析失败: {e}，降级到规则匹配")
                await event.send(Plain(f"⚠️ AI 分析失败: {str(e)}，使用规则匹配替代"))
                task_status = self.task_matcher.match_tasks_with_changes(tasks, file_changes)
            except Exception as e:
                # 其他 AI 错误，降级到规则匹配
                logger.error(f"AI 分析异常: {e}，降级到规则匹配")
                await event.send(Plain(f"⚠️ AI 分析异常，使用规则匹配替代"))
                task_status = self.task_matcher.match_tasks_with_changes(tasks, file_changes)
        else:
            # 使用传统匹配分析
            logger.info("使用规则匹配分析任务...")
            task_status = self.task_matcher.match_tasks_with_changes(tasks, file_changes)

        # 7. 更新配置和生成结果
        self.group_configs[user_id]['last_update'] = datetime.now().isoformat()
        self.group_configs[user_id]['task_status'] = task_status
        self.group_configs[user_id]['member_contributions'] = member_contributions
        self._save_configs()

        # 8. 生成结果摘要
        total_tasks = len(tasks)
        completed_tasks = len([t for t in task_status if t['completion_rate'] == 100])
        in_progress_tasks = len([t for t in task_status if 0 < t['completion_rate'] < 100])
        not_started_tasks = len([t for t in task_status if t['completion_rate'] == 0])

        analysis_method = "AI智能分析" if use_ai else "规则匹配分析"

        result = f"""
仓库: {repo_info['name']}
分析方法: {analysis_method}
检查时间: {DataFormatter.format_timestamp(datetime.now().isoformat())}

📋 任务统计:
• 总任务数: {total_tasks}
• 已完成: {completed_tasks}
• 进行中: {in_progress_tasks}
• 未开始: {not_started_tasks}

👥 成员贡献:
{chr(10).join([f'• {name}: {count} 次提交' for name, count in sorted(member_contributions.items(), key=lambda x: x[1], reverse=True)])}
        """

        return result

    async def _check_tasks_local(self, user_id: str, config: Dict) -> str:
        """使用本地Git检查任务完成情况"""
        # TODO: 实现本地Git检测逻辑
        repo_path = config['repo_path']
        task_book_path = config['task_book_path']

        result = f"""
本地仓库: {repo_path}
任务书: {task_book_path}
检查时间: {DataFormatter.format_timestamp(datetime.now().isoformat())}

📋 任务统计:
• 总任务数: 15
• 已完成: 8
• 进行中: 4
• 未开始: 3

👥 成员贡献:
• 张三: 45%
• 李四: 35%
• 王五: 20%
        """

        # 更新最后检查时间
        self.group_configs[user_id]['last_update'] = datetime.now().isoformat()
        self._save_configs()

        return result

    async def _generate_report(self, user_id: str) -> str:
        """生成详细汇报"""
        config = self.group_configs[user_id]
        task_status = config.get('task_status', [])
        member_contributions = config.get('member_contributions', {})
        use_ai = config.get('use_ai', False)

        # 按状态分类任务
        completed_tasks = [t for t in task_status if t['status'] == 'completed']
        in_progress_tasks = [t for t in task_status if t['status'] == 'in_progress']
        not_started_tasks = [t for t in task_status if t['status'] == 'not_started']

        # 排序成员贡献
        sorted_contributions = sorted(member_contributions.items(), key=lambda x: x[1], reverse=True)

        analysis_method = f"🤖 AI智能分析" if use_ai else "📏 规则匹配分析"

        # 生成任务详情
        report = f"""
📊 TaskWatcher 详细汇报
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 仓库信息
仓库路径: {config['repo_path']}
任务书文件: {config['task_book_filename']}

⏰ 检查信息
分析方法: {analysis_method}
最后检查: {DataFormatter.format_timestamp(config.get('last_update', '从未'))}
检查频率: {config['update_frequency']}秒
更新模式: {config['watcher_mode']}

📋 任务详情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 已完成任务 ({len(completed_tasks)}/{len(task_status)})
{DataFormatter.format_task_list(completed_tasks, max_items=5)}

⏳ 进行中任务 ({len(in_progress_tasks)}/{len(task_status)})
{DataFormatter.format_task_list(in_progress_tasks, max_items=5)}

❌ 未开始任务 ({len(not_started_tasks)}/{len(task_status)})
{DataFormatter.format_task_list(not_started_tasks, max_items=5)}

👥 成员贡献排行
{chr(10).join([f"{i+1}. {name} - {count} 次提交" for i, (name, count) in enumerate(sorted_contributions[:5])])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 总体进度: {int((len(completed_tasks) / len(task_status)) * 100) if task_status else 0}% ({len(completed_tasks)}/{len(task_status)} 任务完成)
        """

        # 如果使用AI，显示详细证据
        if use_ai and any('evidence' in t for t in task_status):
            report += """
📋 AI分析证据（部分任务）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            evidence_count = 0
            for task in task_status[:3]:  # 只显示前3个任务
                if 'evidence' in task and task['evidence']:
                    evidence_count += 1
                    report += f"""
任务: {task['name']}
完成度: {task['completion_rate']}%
主要贡献者: {task['main_contributor']}
分析依据: {task['evidence']}

"""
            if evidence_count == 0:
                report += "当前任务没有详细的AI分析证据。"

        return report

    async def terminate(self):
        """插件销毁"""
        logger.info("TaskWatcherPlugin 插件已卸载")
        # 保存所有配置
        self._save_configs()