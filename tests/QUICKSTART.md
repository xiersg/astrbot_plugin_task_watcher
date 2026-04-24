# 快速测试指南

## 🚀 一键运行测试

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行测试
```bash
# 进入测试目录
cd tests

# 运行所有测试
python run_tests.py

# 运行特定类型
python run_tests.py unit         # 仅单元测试
python run_tests.py integration  # 仅集成测试
python run_tests.py parser       # 仅任务书解析
python run_tests.py matcher      # 仅任务匹配
```

## 📊 查看测试报告

测试完成后，用浏览器打开：
```
tests/test_results/test_report.html
```

## 🔧 直接使用 pytest

```bash
cd tests

# 运行所有测试
pytest test_pytest.py -v

# 运行特定测试类
pytest test_pytest.py::TestTaskBookParser -v

# 运行特定测试方法
pytest test_pytest.py::TestTaskBookParser::test_parse_json -v
```

## 📝 详细文档

- **TESTING.md** - 完整测试文档
- **TEST_GUIDE.md** - 测试指南

## ✨ 特点

- ✅ 跨平台支持（Windows/Linux/Mac）
- ✅ 自动检查依赖
- ✅ 生成 HTML 报告
- ✅ 详细日志输出
- ✅ 支持按类型运行测试