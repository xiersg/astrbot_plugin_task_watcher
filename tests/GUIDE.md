# 测试指南

## 测试环境准备

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置测试数据
- 确保 `test_task_book.json` 和 `test_task_book.md` 文件存在
- 确保 `test_config.json` 文件存在
- (可选) 如果要测试 GitHub API，请在 `test_config.json` 中配置真实的 GitHub Token

### 3. 运行测试

#### 方法 1: 使用测试脚本（推荐，跨平台）

```bash
# 运行所有测试
python run_tests.py

# 运行特定类型的测试
python run_tests.py unit        # 仅单元测试
python run_tests.py integration # 仅集成测试
python run_tests.py parser      # 仅任务书解析测试
python run_tests.py matcher     # 仅任务匹配测试
```

#### 方法 2: 使用 pytest

```bash
# 进入 tests 目录
cd tests

# 运行所有测试
pytest test_pytest.py -v

# 运行特定模块测试
# 仅测试 GitHub 客户端
pytest test_pytest.py::TestGitHubClient -v

# 仅测试任务书解析
pytest test_pytest.py::TestTaskBookParser -v

# 仅测试任务匹配
pytest test_pytest.py::TestTaskMatcher -v
```

## 测试覆盖范围

### 单元测试
1. **GitHub 客户端测试**
   - 获取提交历史
   - 获取提交详情
   - 获取仓库信息

2. **任务书解析测试**
   - JSON 格式解析
   - Markdown 格式解析
   - YAML 格式解析

3. **任务匹配测试**
   - 精确匹配
   - 部分匹配
   - 混合匹配

4. **AI 分析测试**
   - 任务状态分析
   - 任务书更新

### 集成测试
1. 完整的监控流程测试
2. 多任务书格式测试
3. 多仓库监控测试

## 测试输出

测试脚本会输出详细的日志信息，包括：
- 测试开始/结束时间
- 每个测试模块的执行状态
- 测试通过/失败的结果
- 错误堆栈信息（如果失败）
- 性能统计信息

## 注意事项

1. **GitHub API 限制**
   - 如果没有配置真实的 GitHub Token，GitHub 相关测试会使用模拟数据
   - 真实测试时请注意 API 调用频率限制

2. **AI 功能测试**
   - AI 分析测试需要 AstrBot 的 LLM 集成
   - 如果未配置 LLM，AI 测试会跳过

3. **日志文件**
   - 所有测试日志会输出到 `test_results/` 目录
   - 日志文件名格式: `test_{timestamp}.log`
   - HTML 报告: `test_report_{timestamp}.html`

## 故障排查

### 测试失败
查看日志文件中的详细错误信息，常见问题：
- 依赖未安装：运行 `pip install -r requirements.txt`
- 测试文件缺失：检查测试数据文件是否存在
- GitHub Token 无效：更新 `test_config.json` 中的 token

### 性能问题
- 某些测试可能需要较长时间（如 GitHub API 调用）
- 可以使用 `--timeout` 参数设置超时时间