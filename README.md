# TaskWatcher - 智能任务监听插件

检测 Git 仓库代码变更，结合任务书分析进度并写回 Gist。

## 功能

- 对比 GitHub 提交（compare）并生成截断 diff 供 AI 分析
- **YAML v1 嵌套任务书**（`section` 分组 + `task` 可嵌套，`completion` / `contributors` / `paths` 等）
- 任务书存 **Gist**；本机可开 **只读 Web 面板** 浏览；在已配置 `set_repo` 与 GitHub Token 时，面板顶部展示 **仓库贡献热力图**（默认每次约 **90 天（约 3 个月）** UTC 数据，左右箭头切换时段并重新请求；悬停看贡献者，点击格子看排行榜与链接）

## 指令

| 指令 | 说明 |
|------|------|
| `/watcher help` | 帮助 |
| `/watcher set_token <token>` | GitHub Token（gist + 私有库需 repo） |
| `/watcher set_gist <url>` | 绑定 Gist；下载后 **自动 AI 编排为 YAML** 并写回 |
| `/watcher set_repo <repo>` | 监视仓库 `owner/repo` |
| `/watcher organize` | 手动再次 AI 编排任务书并同步 Gist |
| `/watcher tasks_edit <说明>` | AI 按自然语言增删/调整任务点（别名：`任务书编辑`、`编辑任务`） |
| `/watcher check` | 拉取新提交 → 分析 → 更新任务书 YAML |
| `/watcher watch` | 仅预览增量 diff（不写任务书） |
| `/watcher status` | 任务书统计（YAML task 数） |
| `/watcher config` | 当前配置摘要 |
| `/watcher web` | 只读面板链接（需 `web_server_port`）；外网部署需配 `web_public_base_url`，见下文 |
| `/watcher web_new` | **轮换**只读 token 并返回新链接（旧链接失效） |

## 只读网页（Ubuntu / 飞书打不开的常见原因）

默认 **`web_server_host` = `127.0.0.1`** 时，服务只监听本机回环；`/watcher web` 返回的 `http://127.0.0.1:端口/` 在飞书里点，会连到你**手机/电脑自己**，连不到服务器。

**推荐做法：**

1. 插件配置 **`web_server_host`** 改为 **`0.0.0.0`**（对所有网卡监听）。
2. 插件配置 **`web_public_base_url`** 填外网能访问的**完整前缀**（不要末尾 `/`），例如：
   - `http://你的公网IP:1379`
   - 或经 Nginx/Caddy 反代后的 `https://taskbook.example.com`
3. 系统防火墙 / 云安全组 **放行** `web_server_port`（如 1379）。
4. 重载插件后再发 **`/watcher web`**，应得到以 `web_public_base_url` 开头的链接。

隧道（frp、cloudflared 等）时，**`web_public_base_url` 应填隧道暴露给浏览器的那个地址**，与隧道入口一致。

## 配置步骤

1. `/watcher set_token <token>`
2. `/watcher set_gist <gist_url>`（首次会自动编排为 YAML）
3. `/watcher set_repo owner/repo`
4. 需要时 `/watcher check` 写入任务书并推进同步提交记录

## 任务书格式（唯一）

整份 Gist 文件为 **YAML**，顶层为 `version: 1` 与 `tree:`；节点 `kind` 为 `section`（非任务分组）或 `task`（可含 `children`）。字段约定见仓库内 `core/taskbook_schema.py` 中的 `TASKBOOK_YAML_SCHEMA_DOC`。`contributors` 中若写 GitHub 登录名，建议用 **`@login`** 形式，只读网页「贡献」区会尝试显示对应头像。

示例（结构示意）：

```yaml
version: 1
tree:
  - kind: section
    id: sec_ai
    title: "AI端"
    children:
      - kind: task
        id: task_login
        title: "登录"
        completion: ""
        description: ""
        contributors: ""
        paths: "src/auth/login.py"
        children: []
```

## 依赖

- `aiohttp>=3.8.0`
- `PyYAML>=6.0`

## 许可证

查看 [LICENSE](LICENSE) 文件。
