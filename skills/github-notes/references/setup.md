# 安装与跨电脑使用

需要 Python 3.9+、[GitHub CLI](https://cli.github.com/)；自动注册 Codex MCP 还需要 Codex CLI。Python 代码不依赖第三方包。当前仅支持 github.com。

## 安装

```sh
git clone https://github.com/guojianlan/personal-skills.git
cd personal-skills
python3 install.py
```

Windows 若使用 `py` 启动 Python，可运行 `py -3 install.py`。安装器把 Skill 复制到个人全局目录，用 `codex mcp add` 注册 stdio MCP；不改业务仓库，不读取或复制 Token。安装器可用 `--skip-mcp` 仅安装 Skill，并输出其他 MCP 客户端可用的本机绝对路径配置。

新开 Codex 聊天或重启客户端以加载新 Skill 和 MCP。单个现有聊天不保证动态发现刚注册的工具，可以先使用 Skill 附带 CLI。

## 首次授权

```sh
gh auth login --hostname github.com --git-protocol https --web
```

浏览器或设备授权由 GitHub CLI 处理，凭据使用 CLI 自己的凭据存储方式。本项目不持有独立 OAuth 客户端、不复制登录文件，也不要求把 Token 发送到聊天。用户必须在每台电脑分别授权；权限不足、组织 SSO 或授权失效时按实际提示恢复。

授权不等于选定笔记库。调用状态、发现、检查和绑定工具，明确仓库和笔记目录后再保存。

## 本机配置与远程标记

本机绑定默认位于 `~/.config/github-notes/config.json`；`XDG_CONFIG_HOME` 可改变父目录，`GITHUB_NOTES_CONFIG` 可指定独立配置文件。配置包含账号、仓库、分支、笔记目录和是否允许公开笔记，不含凭据。切换 GitHub 账号后必须重新绑定。

远程 `.github-notes.json` 只记录版本、笔记目录与 Markdown 格式。同一账号在另一台电脑授权后，可以发现带标记的候选并选择已有库。自动发现按仓库名称和描述筛选，每页最多检查 12 个候选；名称不明显或候选过多时直接指定 `owner/repo` 检查，不能宣称发现结果覆盖了全部仓库。

## 同步和冲突

每次读取直接请求 GitHub，每次写入直接创建 GitHub 提交，并从该提交读回校验。没有后台监听或离线同步队列，也不自动修改聊天内容。

更新和追加要求刚读取的文件 SHA，远程变化后拒绝覆盖。网络中断或写入结果未知时，先检查远程文件和提交再决定重试。单篇上限为 240 KiB，搜索按页扫描正文，必须查看 `next_cursor`、`skipped` 和扫描数量。

1.1 起支持 `notes_categories` 分类清单，`notes_list/search` 可按 `category` 路径前缀筛选；`notes_asset_create` 保存本机 PNG/JPEG/WebP 到笔记目录的 `assets/`，单张上限 8 MiB，创建后逐字节读回校验，不覆盖不同图片。图片生成使用客户端自身可用工具，MCP 不内置图像模型。Mermaid 直接保留在 Markdown，GitHub 可显示流程图；原有 VuePress 站点是否支持 Mermaid 需独立检查，技能不自动改站点构建。

更新脚本后，已经运行的 stdio MCP 可能仍提供旧工具列表；重启该 MCP/客户端后加载。当前聊天可先通过 Skill CLI 使用新工具。更新本机安装不等于已经发布上游代码或更新其他电脑。

默认使用私有笔记库。若用户明确要保存到公开库，绑定时设置 `allow_public: true`。通用源码公开不代表允许把其他内容公开。

## MCP 的运行位置

此 MCP 在客户端电脑以 stdio 运行，远程数据通过 GitHub REST API 保存。另一台电脑安装后可读取同一仓库；没有单独部署公共 HTTP MCP 服务器。云端或网页客户端若不能运行本地 stdio 进程，需要另行接入其支持的 GitHub 服务或部署 HTTP 适配。

GitHub 另有[官方远程 MCP](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-codex.md)。它提供更通用的 GitHub 工具，认证与客户端支持以官方文档为准；本项目提供的是限制在笔记目录的工作流和工具。
