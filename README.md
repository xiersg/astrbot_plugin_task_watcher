# TaskWatcher - 智能任务监听插件

检测 Git 仓库代码变更，自动分析任务完成进度并生成汇报。

![插件截图](http://xitm.xyz/markdown/readme%E7%94%A8%E5%9B%BE%E7%89%87/astrbot_plugin_task_watcher/2026-04-27-20-35-52_55ca1bde.png)

## 快速开始

### 第一步：准备任务书

在 GitHub [Gist](https://gist.github.com/) 创建任务书：

[内容示例](https://gist.github.com/xiersg/5af0f41f97a896bd2d8a85c52a5b2871)

### 第二步：配置插件

```bash
# 1. 设置 GitHub Token（用于访问 Gist）
/watcher set_token ghp_xxxxxxxx
# Token 获取: https://github.com/settings/tokens（需 gist 权限）

# 2. 设置任务书 Gist 链接（会自动下载内容）
/watcher set_gist https://gist.github.com/用户名/gistID

# 3. 设置要监视的仓库
/watcher set_repo owner/repo
```

### 第三步：使用

```bash
/watcher check      # AI 检查代码，标记已完成任务
/watcher organize   # AI 编排任务书格式
/watcher watch      # 查看代码变更
/watcher status     # 查看进度统计
```

---

## 功能

- 监听 GitHub 仓库代码变更
- AI 智能分析任务完成度
- 任务书同步 Gist 版本管理

## 指令

| 指令 | 说明 |
|------|------|
| `/watcher help` | 显示帮助 |
| `/watcher config` | 查看当前配置 |
| `/watcher set_token <token>` | 设置 GitHub Token |
| `/watcher set_gist <url>` | 设置任务书 Gist 链接 |
| `/watcher set_repo <repo>` | 设置监视的仓库 |
| `/watcher check` | 检查任务完成情况 |
| `/watcher organize` | AI 编排任务书格式 |
| `/watcher watch` | 触发代码变更监视 |
| `/watcher status` | 查看任务状态统计 |

## 许可证

查看 [LICENSE](LICENSE) 文件。
