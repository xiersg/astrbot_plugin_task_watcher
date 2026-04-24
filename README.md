# TaskWatcher - 智能任务监听插件

## 功能概述

TaskWatcher 是一个智能的 Git 仓库任务监听插件，能够：
- 检测 GitHub 仓库或本地 Git 仓库的代码变化
- 分析代码变更与任务书的关联关系
- 计算任务完成进度
- 支持多种分析方法：规则匹配和 AI 智能分析

## 主要特性

### ✨ 智能分析
- **规则匹配分析**：基于文件路径和变更次数的快速分析
- **AI 智能分析**：利用大模型深度分析代码变更，判断任务完成情况

### 📊 多维度汇报
- 按任务状态分类（已完成、进行中、未开始）
- 按成员贡献排行
- AI 分析证据详情

### 📁 灵活配置
- 支持多用户/群组独立配置
- 支持多种任务书格式（JSON、Markdown、YAML）
- 支持多种更新模式（√×符号、百分比）

## 快速开始

### 1. 基础配置

```bash
# 配置插件
/watcher config

# 按提示输入：
# 1. Git 仓库路径（支持 GitHub URL 或本地路径）
# 2. 上传任务书文件
# 3. 选择更新模式
# 4. 选择分析方法（AI 或规则匹配）
# 5. 设置更新频率
```

### 2. 任务书格式示例

#### Markdown 格式
```markdown
## 项目任务清单

- [ ] 用户注册功能 (src/auth/register.py) - 0%
- [x] 登录功能 (src/auth/login.py) - 100%
- [ ] API接口开发 (src/api/) - 30%
```

#### JSON 格式
```json
{
  "tasks": [
    {
      "name": "用户注册功能",
      "related_path": "src/auth/register.py",
      "status": "pending",
      "completion_rate": 0
    },
    {
      "name": "登录功能",
      "related_path": "src/auth/login.py",
      "status": "completed",
      "completion_rate": 100
    }
  ]
}
```

### 3. 使用指令

```bash
# 查看配置状态
/watcher status

# 手动检查任务完成情况
/watcher check

# 生成详细汇报
/watcher report

# 使用 AI 更新任务书（需要启用 AI 分析）
/watcher update_task_book

# 重置配置
/watcher reset
```

## AI 智能分析功能

### 工作原理

1. **获取代码变更信息**
   - 文件路径和变更类型（新增/修改/删除）
   - 代码变更的 patch 信息
   - 变更次数和代码行数统计

2. **构造分析 Prompt**
   - 项目信息和任务列表
   - 代码变更详情
   - 成员贡献统计
   - 分析规则和要求

3. **AI 深度分析**
   - 理解任务需求和代码变更的关联
   - 判断任务完成情况
   - 提供分析依据

4. **生成结构化结果**
   - 任务完成度（0-100%）
   - 任务状态（已完成/进行中/未开始）
   - 主要贡献者
   - 分析证据

### 配置要求

#### AstrBot 配置
- 在 WebUI 配置聊天模型（OpenAI、Claude、或其他支持的模型）
- 确保模型能提供 JSON 格式输出

#### 插件配置
- 启用 AI 分析功能（在配置时选择）
- 建议配置 GitHub Token 以提高 API 限制

### 优势

- **准确性更高**：基于代码语义理解，不只是简单的文件匹配
- **上下文感知**：考虑项目整体结构和业务逻辑
- **灵活适应**：能够处理各种代码风格和项目结构
- **详细证据**：提供分析依据，便于审核和调整

### 使用建议

1. **首次使用**
   - 建议先用规则匹配分析测试
   - 确认基础功能正常后再启用 AI 分析

2. **Token 限制**
   - AI 分析会消耗较多 tokens
   - 建议监控 API 使用情况

3. **结果验证**
   - 初期建议人工审核 AI 分析结果
   - 根据实际情况调整分析规则

## 配置文件说明

### 全局配置 (`_conf_schema.json`)
- `github_token`: GitHub API Token（提高请求限制）
- `data_directory`: 数据存储目录

### 用户配置 (`group_configs.json`)
- `repo_path`: Git 仓库路径
- `task_book_path`: 任务书文件路径
- `watcher_mode`: 更新模式（check/percentage）
- `use_ai`: 是否使用 AI 分析
- `update_frequency`: 自动更新频率（秒）

## 支持的平台

- GitHub 仓库（公开和私有）
- 本地 Git 仓库
- 群聊和私聊

## 依赖项

- `aiohttp>=3.8.0` - 异步 HTTP 客户端
- `PyYAML>=6.0` - YAML 文件解析

## 注意事项

1. **GitHub API 限制**
   - 无 Token: 每小时 60 次请求
   - 有 Token: 每小时 5000 次请求

2. **AI 分析成本**
   - 会消耗聊天模型的 tokens
   - 大项目可能需要较长的处理时间

3. **任务书更新**
   - AI 更新前会自动备份原文件
   - 建议人工审核更新内容

4. **网络连接**
   - 需要 GitHub 网络访问权限
   - AI 分析需要稳定的网络连接

## 常见问题

### Q: AI 分析很慢怎么办？
A: AI 分析需要调用大模型，处理时间取决于模型响应速度。建议：
- 使用响应较快的模型
- 减少分析的任务数量
- 首次分析后可以只分析增量变化

### Q: AI 分析结果不准确？
A: 可以通过以下方式改进：
- 在任务书中提供更详细的描述
- 确保文件路径关联准确
- 使用更强大的模型
- 人工审核并反馈问题

### Q: 如何监控私有仓库？
A: 需要在插件配置中设置 GitHub Token：
1. 生成 GitHub Personal Access Token
2. 权限选择 `repo` 或 `public_repo`
3. 在 WebUI 插件配置中输入 Token

## 开发者信息

- 作者: xiersg
- 版本: v1.0.0
- 仓库: https://github.com/xiersg/astrbot_plugin_task_watcher.git

## 许可证

请查看项目根目录的 LICENSE 文件了解具体许可信息。