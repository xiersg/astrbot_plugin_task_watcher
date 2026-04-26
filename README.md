# TaskWatcher - 智能任务监听插件

检测 Git 仓库代码变更，自动分析任务完成进度并生成汇报。

![插件截图-任务汇报](docs/images/report.png)

## 功能

- 监听 GitHub/本地 Git 仓库变更
- AI 智能分析任务完成度
- 自动生成 Markdown 任务书
- 任务书版本管理（Gist）

## 指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/watcher help` | 帮助 | 显示帮助信息 |
| `/watcher status` | 状态 | 查看配置状态 |
| `/watcher check` | 检查/查看 | 检查任务完成情况 |
| `/watcher report` | 汇报/报告 | 生成详细汇报 |
| `/watcher organize` | 编排 | AI 编排任务书为 Markdown |
| `/watcher upload_gist` | 上传 | 上传任务书到 Gist |
| `/watcher set_token <token>` | - | 设置 GitHub Token |
| `/watcher reset` | 重置 | 重置配置 |

![指令演示](docs/images/commands.png)

## 配置步骤

### 1. 基础配置

```bash
# 设置仓库
/watcher set_repo https://github.com/owner/repo

# 上传任务书文件（支持 .json/.md/.yaml）
/watcher set_taskbook

# 或使用文本直接设置
/watcher set_taskbook_text
[粘贴任务书内容]

# 启用 AI 分析
/watcher set_ai y

# 设置检查频率（秒，0 为手动）
/watcher set_freq 3600
```

### 2. Gist 同步（可选）

```bash
# 设置 GitHub Token（用于上传 Gist）
/watcher set_token ghp_xxxxxxxx

# 上传任务书到 Gist
/watcher upload_gist

# 使用 AI 编排任务书格式
/watcher organize
```

设置后，每次 `/watcher check` 会自动同步最新版本到 Gist。

![配置流程](docs/images/setup.png)

## 任务书格式

### Markdown 格式

```markdown
# 项目任务书

## 任务清单

### 用户模块
- [ ] 注册功能 (src/auth/register.py) - 0%
- [x] 登录功能 (src/auth/login.py) - 100%

### API 模块
- [ ] 接口开发 (src/api/) - 30%
```

### JSON 格式

```json
{
  "tasks": [
    {"name": "注册功能", "related_path": "src/auth/register.py", "completion_rate": 0},
    {"name": "登录功能", "related_path": "src/auth/login.py", "completion_rate": 100}
  ]
}
```

![任务书示例](docs/images/taskbook.png)

## 依赖

- `aiohttp>=3.8.0`
- `PyYAML>=6.0`

## 许可证

查看 [LICENSE](LICENSE) 文件。
