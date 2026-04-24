#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件诊断脚本
用于检查插件依赖和配置是否正确
"""
import sys
import traceback
from pathlib import Path

print("="*60)
print("TaskWatcher 插件诊断工具")
print("="*60)

# 检查 Python 版本
print(f"\n[1] Python 版本检查")
print(f"Python 版本: {sys.version}")

# 检查依赖
print(f"\n[2] 依赖检查")

dependencies = [
    ('aiohttp', 'GitHub API 客户端需要'),
    ('PyYAML', '任务书解析需要'),
]

missing_deps = []

for dep, description in dependencies:
    try:
        __import__(dep)
        print(f"✅ {dep} - 已安装 ({description})")
    except ImportError:
        print(f"❌ {dep} - 未安装 ({description})")
        missing_deps.append(dep)

if missing_deps:
    print(f"\n[错误] 缺少依赖: {', '.join(missing_deps)}")
    print(f"[提示] 请运行: pip install {' '.join(missing_deps)}")
    sys.exit(1)

# 检查核心模块
print(f"\n[3] 核心模块检查")

modules = [
    ('core.github_client', 'GitHubAPIClient'),
    ('core.task_parser', 'TaskBookParser'),
    ('core.task_matcher', 'TaskMatcher'),
    ('core.ai_analyzer', 'AIAnalyzer'),
    ('core.utils', 'FileUtils'),
]

module_errors = []

for module_path, class_name in modules:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name, None)
        if cls is not None:
            print(f"✅ {module_path}.{class_name} - 可用")
        else:
            print(f"❌ {module_path}.{class_name} - 未找到类")
            module_errors.append(f"{module_path}.{class_name}")
    except Exception as e:
        print(f"❌ {module_path}.{class_name} - 导入失败: {e}")
        module_errors.append(f"{module_path}.{class_name}")

if module_errors:
    print(f"\n[错误] 模块导入失败:")
    for error in module_errors:
        print(f"  - {error}")

    print(f"\n详细错误信息:")
    for module_path, _ in modules:
        try:
            __import__(module_path)
        except Exception as e:
            print(f"\n{module_path}:")
            traceback.print_exc()

    sys.exit(1)

# 检查文件结构
print(f"\n[4] 文件结构检查")

current_dir = Path(__file__).parent

required_files = [
    'main.py',
    'metadata.yaml',
    '_conf_schema.json',
    'requirements.txt',
    'README.md',
    'core/__init__.py',
    'core/github_client.py',
    'core/task_parser.py',
    'core/task_matcher.py',
    'core/ai_analyzer.py',
    'core/utils.py',
]

missing_files = []

for file_path in required_files:
    full_path = current_dir / file_path
    if full_path.exists():
        print(f"✅ {file_path} - 存在")
    else:
        print(f"❌ {file_path} - 不存在")
        missing_files.append(file_path)

if missing_files:
    print(f"\n[错误] 缺少文件: {', '.join(missing_files)}")
    sys.exit(1)

# 检查 metadata.yaml
print(f"\n[5] metadata.yaml 检查")

metadata_file = current_dir / 'metadata.yaml'
if metadata_file.exists():
    import yaml
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)

        required_fields = ['name', 'author', 'description', 'version']
        for field in required_fields:
            if field in metadata:
                print(f"✅ {field}: {metadata[field]}")
            else:
                print(f"❌ {field} - 缺失")
                missing_files.append(f"metadata.{field}")
    except Exception as e:
        print(f"❌ metadata.yaml 解析失败: {e}")

# 最终结果
print(f"\n{'='*60}")
if missing_deps or module_errors or missing_files:
    print("[结果] 诊断失败，请修复上述问题")
    print(f"{'='*60}")
    sys.exit(1)
else:
    print("[结果] ✅ 所有检查通过，插件可以正常加载")
    print(f"{'='*60}")
    sys.exit(0)