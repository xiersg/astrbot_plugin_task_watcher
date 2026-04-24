#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskWatcher 测试运行脚本
跨平台支持，避免批处理文件编码问题
"""
import sys
import os
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """运行命令并输出结果"""
    print(f"\n{'='*60}")
    print(f"[执行] {description}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.stdout:
            print(result.stdout)
        return True, 0
    except subprocess.CalledProcessError as e:
        print(f"[错误] 命令执行失败，返回码: {e.returncode}")
        if e.stdout:
            print("标准输出:")
            print(e.stdout)
        if e.stderr:
            print("错误输出:")
            print(e.stderr)
        return False, e.returncode


def check_python():
    """检查 Python 环境"""
    success, code = run_command(
        [sys.executable, '--version'],
        '检查 Python 版本'
    )
    return success


def check_dependencies():
    """检查并安装依赖"""
    success, code = run_command(
        [sys.executable, '-m', 'pip', 'show', 'pytest'],
        '检查 pytest 是否已安装'
    )

    if not success:
        print("\npytest 未安装，正在安装依赖...")
        success, code = run_command(
            [sys.executable, '-m', 'pip', 'install', '-r', '../requirements.txt'],
            '安装依赖'
        )
        if not success:
            print("[错误] 依赖安装失败")
            return False

    print("[成功] 依赖检查完成")
    return True


def create_test_results_dir():
    """创建测试结果目录"""
    test_results = Path('test_results')
    test_results.mkdir(exist_ok=True)
    print(f"[成功] 测试结果目录: {test_results.absolute()}")
    return True


def run_tests(test_type='all'):
    """运行测试"""
    # 切换到 tests 目录
    tests_dir = Path(__file__).parent
    os.chdir(tests_dir)

    test_commands = {
        'all': [
            '运行所有测试...',
            [sys.executable, '-m', 'pytest', 'test_pytest.py', '-v',
             '--html=test_results/test_report.html', '--self-contained-html']
        ],
        'unit': [
            '运行单元测试...',
            [sys.executable, '-m', 'pytest', 'test_pytest.py', '-v',
             '-m', 'not integration', '--html=test_results/test_report.html']
        ],
        'integration': [
            '运行集成测试...',
            [sys.executable, '-m', 'pytest', 'test_pytest.py', '-v',
             '-m', 'integration', '--html=test_results/test_report.html']
        ],
        'parser': [
            '运行任务书解析测试...',
            [sys.executable, '-m', 'pytest', 'test_pytest.py::TestTaskBookParser', '-v']
        ],
        'matcher': [
            '运行任务匹配测试...',
            [sys.executable, '-m', 'pytest', 'test_pytest.py::TestTaskMatcher', '-v']
        ],
    }

    if test_type not in test_commands:
        print(f"[错误] 未知的测试类型: {test_type}")
        print(f"可用选项: {', '.join(test_commands.keys())}")
        return False

    description, command = test_commands[test_type]
    print(f"\n{description}")
    success, code = run_command(command, description)

    return success


def main():
    """主函数"""
    print("="*60)
    print("TaskWatcher 插件测试脚本")
    print("="*60)

    # 获取测试类型
    test_type = sys.argv[1] if len(sys.argv) > 1 else 'all'

    # 步骤 1: 检查 Python 环境
    print("\n[1/4] 检查 Python 环境...")
    if not check_python():
        print("[错误] Python 环境检查失败")
        sys.exit(1)

    # 步骤 2: 检查依赖
    print("\n[2/4] 检查依赖...")
    if not check_dependencies():
        print("[错误] 依赖检查失败")
        sys.exit(1)

    # 步骤 3: 创建测试结果目录
    print("\n[3/4] 准备测试环境...")
    if not create_test_results_dir():
        print("[错误] 测试环境准备失败")
        sys.exit(1)

    # 步骤 4: 运行测试
    print("\n[4/4] 运行测试...")
    success = run_tests(test_type)

    # 显示结果
    print("\n" + "="*60)
    if success:
        print("[成功] 所有测试通过")
    else:
        print("[失败] 部分测试失败")
    print("="*60)
    print("\n测试报告已生成: test_results/test_report.html")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()