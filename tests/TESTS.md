# TaskWatcher 测试文档

## 概述

本插件提供了完整的测试套件，包括单元测试和集成测试。测试使用 pytest 框架，支持详细的日志输出和 HTML 测试报告。

## 测试文件说明

### 核心测试文件

| 文件名 | 说明 |
|--------|------|
| `test_pytest.py` | pytest 格式的单元测试和集成测试 |
| `test_all.py` | 独立运行的测试脚本（带详细日志） |
| `pytest.ini` | pytest 配置文件 |
| `run_tests.py` | Python 测试运行脚本（跨平台） |

### 测试数据文件

| 文件名 | 说明 |
|--------|------|
| `test_task_book.json` | JSON 格式测试任务书 |
| `test_task_book.md` | Markdown 格式测试任务书 |
| `test_config.json` | 测试配置文件 |

## 快速开始

### 1. 安装测试依赖

```bash
pip install -r requirements.txt
```

这将安装以下测试相关的包：
- `pytest>=7.0.0` - 测试框架
- `pytest-asyncio>=0.21.0` - 异步测试支持
- `pytest-html>=3.0.0` - HTML 报告生成

### 2. 运行测试

#### 使用测试脚本（推荐，跨平台）

```bash
# 运行所有测试
python run_tests.py

# 运行特定类型的测试
python run_tests.py unit        # 仅单元测试
python run_tests.py integration # 仅集成测试
python run_tests.py parser      # 仅任务书解析测试
python run_tests.py matcher     # 仅任务匹配测试
```

#### 直接使用 pytest
```bash
# 运行所有测试
pytest test_pytest.py -v

# 运行特定测试类
pytest test_pytest.py::TestTaskBookParser -v

# 运行特定测试方法
pytest test_pytest.py::TestTaskBookParser::test_parse_json -v

# 运行集成测试
pytest test_pytest.py -m integration -v

# 运行单元测试（排除集成测试）
pytest test_pytest.py -m "not integration" -v
```

### 3. 查看测试报告

测试完成后，HTML 报告会生成在 `test_results/test_report.html`。用浏览器打开此文件查看详细的测试结果。

## 测试覆盖范围

### 单元测试

#### 1. TaskBookParser 测试
- ✓ JSON 格式任务书解析
- ✓ Markdown 格式任务书解析
- ✓ YAML 格式任务书解析
- ✓ 自动格式检测

#### 2. TaskMatcher 测试
- ✓ 精确匹配策略
- ✓ 部分匹配策略
- ✓ 混合匹配策略

#### 3. FileUtils 测试
- ✓ 文件读取
- ✓ 文件写入
- ✓ JSON 文件操作

#### 4. DataFormatter 测试
- ✓ 任务状态报告格式化
- ✓ 成员贡献统计格式化

#### 5. Validator 测试
- ✓ 仓库配置验证
- ✓ 任务书配置验证

### 集成测试

#### 1. 完整工作流程测试
- 解析任务书 → 模拟文件变更 → 任务匹配 → 生成报告

#### 2. 多格式任务书测试
- 同时处理不同格式的任务书文件

#### 3. 错误处理测试
- 测试各种错误场景的处理

## 测试标记 (Markers)

pytest 使用标记来分类测试：

| 标记 | 说明 | 用法 |
|------|------|------|
| `unit` | 单元测试 | `pytest -m unit` |
| `integration` | 集成测试 | `pytest -m integration` |
| `slow` | 慢速测试 | `pytest -m "not slow"` |
| `github` | 需要 GitHub API | `pytest -m "not github"` |
| `ai` | 需要 AI 功能 | `pytest -m "not ai"` |

## 日志说明

### 控制台日志

测试运行时会在控制台输出详细日志：

```
2024-01-01 10:00:00 [INFO] 开始测试...
2024-01-01 10:00:01 [INFO] [测试] 解析 JSON 格式任务书
2024-01-01 10:00:02 [INFO] ✓ 成功解析 3 个任务
```

### 日志级别

- `DEBUG` - 详细的调试信息
- `INFO` - 一般信息
- `WARNING` - 警告信息
- `ERROR` - 错误信息
- `CRITICAL` - 严重错误

### 查看更多日志

```bash
# 显示详细输出（包括 print 语句）
pytest test_pytest.py -v -s

# 设置日志级别为 DEBUG
pytest test_pytest.py -v --log-cli-level=DEBUG
```

## 测试结果解读

### 成功的测试

```
test_pytest.py::TestTaskBookParser::test_parse_json PASSED
```

### 失败的测试

```
test_pytest.py::TestTaskBookParser::test_parse_json FAILED
test_pytest.py::TestTaskBookParser::test_parse_json
    assert len(tasks) > 0
    AssertionError: 应该解析出至少一个任务
```

### 跳过的测试

```
test_pytest.py::TestTaskBookParser::test_parse_yaml SKIPPED (未安装 PyYAML)
```

## 常见问题

### Q1: 测试失败，提示模块未导入

**问题**: `ImportError: No module named 'github_client'`

**解决方案**:
- 确保所有模块文件（github_client.py, task_parser.py 等）在当前目录
- 检查 Python 路径是否正确

### Q2: GitHub API 测试失败

**问题**: 测试无法连接到 GitHub API

**解决方案**:
- 在 `test_config.json` 中配置有效的 GitHub Token
- 或者跳过 GitHub 相关测试：`pytest -m "not github"`

### Q3: AI 测试被跳过

**问题**: AI 相关的测试显示为 SKIPPED

**解决方案**:
- 这是正常的，AI 功能需要 AstrBot 的 LLM 集成
- 可以在 AstrBot 环境中测试 AI 功能

### Q4: 测试运行很慢

**问题**: 测试执行时间过长

**解决方案**:
- 跳过慢速测试：`pytest -m "not slow"`
- 跳过网络测试：`pytest -m "not github and not ai"`
- 只运行单元测试：`pytest -m "not integration"`

## 持续集成

如果要在 CI/CD 管道中运行测试：

```yaml
# GitHub Actions 示例
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest test_pytest.py -v --html=test_results/report.html
```

## 性能基准

在普通开发机器上的预期测试时间：

| 测试类型 | 预期时间 |
|----------|----------|
| 单元测试 | 1-2 秒 |
| 集成测试（无网络） | 2-3 秒 |
| 集成测试（含网络） | 5-10 秒 |
| 完整测试套件 | 5-15 秒 |

## 贡献指南

### 添加新测试

1. 在 `test_pytest.py` 中添加测试方法
2. 使用 `@pytest.mark.asyncio` 装饰异步测试
3. 添加适当的标记（如 `unit`, `integration`）
4. 编写清晰的测试名称和文档字符串

### 示例

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_feature(self):
    """测试新功能"""
    # 准备测试数据
    data = {...}

    # 执行测试
    result = await function_under_test(data)

    # 断言结果
    assert result is not None
    assert result.status == "success"
```

## 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [项目主 README](README.md)