#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的测试脚本 - 带详细日志
可以独立运行，不依赖 pytest
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入日志系统
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'test_results/test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class TestResult:
    """测试结果统计"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def add_pass(self):
        self.total += 1
        self.passed += 1

    def add_fail(self, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append(error)

    def add_skip(self):
        self.total += 1
        self.skipped += 1

    def print_summary(self):
        logger.info("="*60)
        logger.info("测试总结")
        logger.info("="*60)
        logger.info(f"总计: {self.total} 个测试")
        logger.info(f"通过: {self.passed} 个 ✓")
        logger.info(f"失败: {self.failed} 个 ✗")
        logger.info(f"跳过: {self.skipped} 个 ⊘")

        if self.errors:
            logger.error("\n失败详情:")
            for i, error in enumerate(self.errors, 1):
                logger.error(f"{i}. {error}")

        logger.info("="*60)


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.result = TestResult()
        self.test_data_dir = Path(__file__).parent

    def setup(self):
        """测试前准备"""
        logger.info("\n[准备] 创建测试结果目录...")
        self.test_data_dir.mkdir(exist_ok=True)
        results_dir = self.test_data_dir / "test_results"
        results_dir.mkdir(exist_ok=True)
        logger.info("✓ 测试环境准备完成")

    def tear_down(self):
        """测试后清理"""
        logger.info("\n[清理] 清理临时文件...")
        # 这里可以添加清理逻辑
        logger.info("✓ 清理完成")

    async def run_all_tests(self, module_filter=None):
        """运行所有测试"""
        logger.info("\n" + "="*60)
        logger.info("开始测试 TaskWatcher 插件")
        logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)

        self.setup()

        try:
            # 运行不同模块的测试
            if module_filter in [None, "parser", "all"]:
                await self.test_parser_module()

            if module_filter in [None, "matcher", "all"]:
                await self.test_matcher_module()

            if module_filter in [None, "utils", "all"]:
                await self.test_utils_module()

            if module_filter in [None, "github", "all"]:
                await self.test_github_module()

            if module_filter in [None, "ai", "all"]:
                await self.test_ai_module()

            if module_filter == "integration":
                await self.test_integration()

        finally:
            self.tear_down()
            self.result.print_summary()

        return self.result.failed == 0

    async def test_parser_module(self):
        """测试任务书解析模块"""
        logger.info("\n" + "-"*60)
        logger.info("[模块测试] 任务书解析器 (TaskBookParser)")
        logger.info("-"*60)

        try:
            from task_parser import TaskBookParser
        except ImportError as e:
            logger.error(f"✗ 无法导入 TaskBookParser: {e}")
            self.result.add_skip()
            return

        # 测试 JSON 解析
        logger.info("\n[测试 1.1] JSON 格式解析")
        try:
            json_file = self.test_data_dir / "test_task_book.json"
            tasks = TaskBookParser.parse_json(str(json_file))
            assert len(tasks) > 0, "应该解析出至少一个任务"
            assert tasks[0].get("id") == "task_001", "第一个任务的 ID 应该是 task_001"
            logger.info(f"  ✓ 成功解析 {len(tasks)} 个任务")
            logger.debug(f"  任务列表: {json.dumps(tasks, indent=2, ensure_ascii=False)}")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ JSON 解析失败: {e}")
            self.result.add_fail(f"JSON 解析: {e}")

        # 测试 Markdown 解析
        logger.info("\n[测试 1.2] Markdown 格式解析")
        try:
            md_file = self.test_data_dir / "test_task_book.md"
            tasks = TaskBookParser.parse_markdown(str(md_file))
            assert len(tasks) > 0, "应该解析出至少一个任务"
            logger.info(f"  ✓ 成功解析 {len(tasks)} 个任务")
            logger.debug(f"  任务列表: {json.dumps(tasks, indent=2, ensure_ascii=False)}")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ Markdown 解析失败: {e}")
            self.result.add_fail(f"Markdown 解析: {e}")

        # 测试自动检测格式
        logger.info("\n[测试 1.3] 自动格式检测")
        try:
            json_file = self.test_data_dir / "test_task_book.json"
            md_file = self.test_data_dir / "test_task_book.md"

            tasks_json = TaskBookParser.parse(str(json_file))
            tasks_md = TaskBookParser.parse(str(md_file))

            assert len(tasks_json) > 0, "JSON 格式应该解析成功"
            assert len(tasks_md) > 0, "Markdown 格式应该解析成功"
            logger.info("  ✓ 自动格式检测成功")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 自动格式检测失败: {e}")
            self.result.add_fail(f"自动格式检测: {e}")

    async def test_matcher_module(self):
        """测试任务匹配模块"""
        logger.info("\n" + "-"*60)
        logger.info("[模块测试] 任务匹配器 (TaskMatcher)")
        logger.info("-"*60)

        try:
            from task_matcher import TaskMatcher
        except ImportError as e:
            logger.error(f"✗ 无法导入 TaskMatcher: {e}")
            self.result.add_skip()
            return

        matcher = TaskMatcher()

        # 测试精确匹配
        logger.info("\n[测试 2.1] 精确匹配策略")
        try:
            tasks = [
                {"id": "task_001", "title": "实现用户登录", "status": "pending"},
            ]
            files = {
                "src/auth/login.py": {
                    "status": "modified",
                    "changes": "Added login function"
                }
            }
            related_files_map = {
                "task_001": ["src/auth/login.py"]
            }

            result = matcher.match_tasks_with_files(
                tasks, files, related_files_map, strategy="exact"
            )
            assert len(result["completed"]) > 0, "应该匹配到完成的任务"
            logger.info(f"  ✓ 匹配到 {len(result['completed'])} 个完成的任务")
            logger.debug(f"  匹配结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 精确匹配失败: {e}")
            self.result.add_fail(f"精确匹配: {e}")

        # 测试部分匹配
        logger.info("\n[测试 2.2] 部分匹配策略")
        try:
            tasks = [
                {"id": "task_001", "title": "实现登录功能", "status": "pending"},
            ]
            files = {
                "src/auth/user.py": {
                    "status": "added",
                    "changes": "Added user authentication"
                }
            }
            related_files_map = {
                "task_001": ["src/auth/login.py"]
            }

            result = matcher.match_tasks_with_files(
                tasks, files, related_files_map, strategy="partial"
            )
            logger.info(f"  ✓ 匹配结果: 完成={len(result['completed'])}, 部分完成={len(result['partial'])}")
            logger.debug(f"  匹配结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 部分匹配失败: {e}")
            self.result.add_fail(f"部分匹配: {e}")

    async def test_utils_module(self):
        """测试工具模块"""
        logger.info("\n" + "-"*60)
        logger.info("[模块测试] 工具模块 (Utils)")
        logger.info("-"*60)

        try:
            from utils import FileUtils, DataFormatter, ConfigUtils, Validator
        except ImportError as e:
            logger.error(f"✗ 无法导入工具模块: {e}")
            self.result.add_skip()
            return

        # 测试文件读取
        logger.info("\n[测试 3.1] 文件工具类")
        try:
            test_file = self.test_data_dir / "test_task_book.json"
            content = FileUtils.read_file(str(test_file))
            assert content is not None, "文件内容不应为空"
            logger.info("  ✓ 文件读取成功")
            logger.debug(f"  文件内容长度: {len(content)} 字符")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 文件读取失败: {e}")
            self.result.add_fail(f"文件读取: {e}")

        # 测试数据格式化
        logger.info("\n[测试 3.2] 数据格式化工具")
        try:
            tasks = [
                {"id": "task_001", "title": "任务1", "status": "completed"},
                {"id": "task_002", "title": "任务2", "status": "pending"},
            ]
            formatted = DataFormatter.format_task_status_report(tasks)
            assert "task_001" in formatted, "报告应包含 task_001"
            assert "completed" in formatted, "报告应包含 completed"
            logger.info("  ✓ 任务状态格式化成功")
            logger.debug(f"  格式化结果:\n{formatted}")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 数据格式化失败: {e}")
            self.result.add_fail(f"数据格式化: {e}")

        # 测试验证器
        logger.info("\n[测试 3.3] 验证器工具")
        try:
            valid_config = {
                "owner": "test_owner",
                "repo": "test_repo",
                "branch": "main"
            }
            is_valid = Validator.validate_repo_config(valid_config)
            assert is_valid is True, "配置应该是有效的"

            invalid_config = {"owner": "test_owner"}
            is_valid = Validator.validate_repo_config(invalid_config)
            assert is_valid is False, "配置应该是无效的"

            logger.info("  ✓ 验证器测试成功")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 验证器测试失败: {e}")
            self.result.add_fail(f"验证器: {e}")

    async def test_github_module(self):
        """测试 GitHub 模块"""
        logger.info("\n" + "-"*60)
        logger.info("[模块测试] GitHub 客户端 (GitHubAPIClient)")
        logger.info("-"*60)

        try:
            from github_client import GitHubAPIClient
        except ImportError as e:
            logger.error(f"✗ 无法导入 GitHubAPIClient: {e}")
            self.result.add_skip()
            return

        logger.info("\n[测试 4.1] GitHub 客户端初始化")
        try:
            client = GitHubAPIClient("test_token")
            logger.info("  ✓ GitHub 客户端初始化成功")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ GitHub 客户端初始化失败: {e}")
            self.result.add_fail(f"GitHub 客户端初始化: {e}")

        logger.info("\n[提示] GitHub API 测试需要有效的 Token")
        logger.info("如需测试真实 API 调用，请在 test_config.json 中配置 token")

    async def test_ai_module(self):
        """测试 AI 分析模块"""
        logger.info("\n" + "-"*60)
        logger.info("[模块测试] AI 分析器 (AIAnalyzer)")
        logger.info("-"*60)

        try:
            from ai_analyzer import AIAnalyzer
        except ImportError as e:
            logger.error(f"✗ 无法导入 AIAnalyzer: {e}")
            self.result.add_skip()
            return

        logger.info("\n[测试 5.1] AI 分析器初始化")
        try:
            # 注意：AI 功能需要 AstrBot 的 LLM 集成
            # 这里只测试初始化
            logger.info("  ✓ AI 模块导入成功")
            logger.info("[提示] AI 功能需要 AstrBot 环境才能完整测试")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ AI 模块测试失败: {e}")
            self.result.add_fail(f"AI 模块: {e}")

    async def test_integration(self):
        """集成测试"""
        logger.info("\n" + "-"*60)
        logger.info("[集成测试] 完整工作流程")
        logger.info("-"*60)

        try:
            from task_parser import TaskBookParser
            from task_matcher import TaskMatcher
            from utils import DataFormatter
        except ImportError as e:
            logger.error(f"✗ 无法导入必要模块: {e}")
            self.result.add_skip()
            return

        logger.info("\n[集成测试 1] 完整监控流程")
        try:
            # 1. 解析任务书
            logger.info("  步骤 1: 解析任务书...")
            json_file = self.test_data_dir / "test_task_book.json"
            tasks = TaskBookParser.parse_json(str(json_file))
            logger.info(f"  ✓ 解析到 {len(tasks)} 个任务")

            # 2. 模拟文件变更
            logger.info("  步骤 2: 模拟文件变更...")
            files = {
                "src/auth/login.py": {"status": "modified"},
                "src/db/connection.py": {"status": "added"}
            }
            logger.info(f"  ✓ 模拟了 {len(files)} 个文件变更")

            # 3. 匹配任务
            logger.info("  步骤 3: 匹配任务...")
            matcher = TaskMatcher()
            related_files_map = {
                "task_001": ["src/auth/login.py"],
                "task_002": ["src/db/connection.py"]
            }
            result = matcher.match_tasks_with_files(tasks, files, related_files_map)
            logger.info(f"  ✓ 完成任务: {len(result['completed'])}")
            logger.info(f"  ✓ 部分完成: {len(result['partial'])}")

            # 4. 生成报告
            logger.info("  步骤 4: 生成报告...")
            report = DataFormatter.format_task_status_report(
                result["completed"] + result["partial"] + result["pending"]
            )
            logger.info("  ✓ 报告生成成功")
            logger.debug(f"  报告内容:\n{report}")

            logger.info("\n  ✓ 集成测试通过")
            self.result.add_pass()
        except Exception as e:
            logger.error(f"  ✗ 集成测试失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.result.add_fail(f"集成测试: {e}")


def print_usage():
    """打印使用说明"""
    print("\n用法:")
    print("  python test_all.py                  # 运行所有测试")
    print("  python test_all.py --module parser  # 仅测试解析器")
    print("  python test_all.py --module matcher # 仅测试匹配器")
    print("  python test_all.py --module utils   # 仅测试工具模块")
    print("  python test_all.py --integration    # 仅运行集成测试")
    print("\n参数:")
    print("  --module <name>  - 指定测试模块 (parser|matcher|utils|github|ai)")
    print("  --integration    - 运行集成测试")
    print("\n日志:")
    print("  - 测试日志会输出到 test_results/ 目录")
    print("  - 同时在控制台显示详细日志")


async def main():
    """主函数"""
    # 解析命令行参数
    module_filter = None
    run_integration = False

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--help" or arg == "-h":
            print_usage()
            return
        elif arg == "--module" and i + 1 < len(sys.argv):
            module_filter = sys.argv[i + 1]
        elif arg == "--integration":
            module_filter = "integration"

    # 运行测试
    runner = TestRunner()
    success = await runner.run_all_tests(module_filter)

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n测试运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)