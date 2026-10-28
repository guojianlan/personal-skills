# Personal GitHub Skills

仓库由 `github-notes-skill` 更名为 `personal-skills`，统一维护个人 Skill；笔记 Skill 的既有路径和 MCP 名称保持不变。

| Skill | 用途 | 私有数据位置 |
| --- | --- | --- |
| [github-notes](skills/github-notes/SKILL.md) | 分类保存和检索笔记，支持本机 MCP | 用户独立选择的私有笔记仓库 |
| [github-resources](skills/github-resources/SKILL.md) | 检索、维护并使用供应商、模型、数据库、Redis、邮件和服务器配置 | 用户的私有资源仓库，默认 `当前账号/personal-resources` |

本仓库公开，只包含通用代码与虚构示例。真实资源、密钥、个人仓库绑定和 gh 授权不进入本仓库。

默认 `python3 install.py` 安装两个 Skill，并注册原笔记 MCP。仅安装资源 Skill 不需要 Codex CLI，也不改 MCP，因此不必额外添加 `--skip-mcp`：

```sh
python3 install.py --skill github-resources
gh auth login --hostname github.com --git-protocol https --web
```

新开聊天后可以说“查一下我的百炼配置”或“使用 $github-resources 查找测试数据库”。默认仓库只需按账号约定存在；自定义仓库用资源 CLI 的 `bind owner/repo`。资源 CLI 会拒绝公开仓库，查询默认脱敏；真实凭据按需导出到受保护的本地文件。每台设备独立授权，资源不做后台同步，不运行 Actions，不部署网站。

首次建库、配置格式与命令见 [资源格式与维护](skills/github-resources/references/catalog.md)。资源工具需要私有仓库根目录已有 `catalog.json`，格式为 `{"version":1,"resources":[]}`。当前不提供自动建库命令；可由授权的 `gh repo create --private` 建立并提交初始文件。

下面保留原笔记功能与安装说明。

## GitHub Notes Skill and MCP

用独立 GitHub 仓库保存调研和开发笔记。包含一个可全局安装的 Codex Skill，以及一个复用 GitHub CLI 授权的轻量笔记 MCP。

首次使用检查授权、分析候选仓库、选择并绑定笔记目录；没有合适仓库时按用户要求创建私有仓库。后续由助手自动选择分类与标签，按内容补充流程图、表格或图片，再保存、检索和更新笔记。通用源码可公开分享，每个用户独立授权并使用自己的笔记库。

笔记 Skill 当前版本：**1.1.0**。个人资源 Skill 的验收记录见 [VALIDATION.md](VALIDATION.md)。

## 快速安装

准备 Python 3.9+、GitHub CLI 和 Codex CLI：

```sh
git clone https://github.com/guojianlan/personal-skills.git
cd personal-skills
python3 install.py
gh auth login --hostname github.com --git-protocol https --web
```

Windows 可以用 `py -3 install.py`。授权已有效时不必重新登录。新开聊天或重启客户端加载 Skill/MCP，然后说：

> 使用 $github-notes 初始化我的笔记库，先看看是否已有合适的私有仓库。

> 使用 $github-notes 把这次调研保存到我的笔记库，保留来源和待验证步骤。

> 使用 $github-notes 查找我以前关于作业批改的调研。

> 使用 $github-notes 把这次验证结果补充到指定笔记。

## 分类与图文笔记

用户说明要保存的内容，助手负责检索已有主题、选择主分类、添加标签与关联笔记，并维护相关索引。优先复用仓库现有目录，按需要增加领域或主题；同一篇文章只保存一份，交叉主题通过标签和链接表达。分类工具从目录实时统计，不依赖固定分类清单。

流程、调用、状态转换和实体关系优先用可编辑的 Mermaid，方案比较使用表格，数据图表保留来源；需要插画或视觉概念时调用客户端可用的图片生成能力。MCP 本身不内置图片生成模型。短记录无需为了形式强加配图。

PNG、JPEG、WebP 图片可从本机保存到绑定笔记目录的 `assets/`，单张最多 8 MiB，随后由正文相对引用。上传后从提交版本逐字节读回；相同文件可以安全重试，不同图片拒绝覆盖，需另取版本文件名。图片签名检查不能替代实际解码和人工阅读检查。图片和正文分步提交，失败时分别报告状态。

Mermaid 可在 GitHub 阅读；其他站点或阅读器的渲染支持需独立确认，工具不自动修改站点构建。具体分类、图表选择与归档规则见[分类与可视化](skills/github-notes/references/organization-and-visuals.md)。

## 架构

Skill 负责授权和仓库选择流程、笔记组织与回复；MCP 负责身份与权限检查、目录范围、GitHub API 读写、并发校验和提交后读回。

MCP 是本机 stdio 进程，GitHub 是远程存储和版本来源。每台电脑分别安装授权，共享同一个 GitHub 仓库。当前不提供托管 HTTP MCP，也不包含后台自动归档和离线同步队列。

代码只依赖 Python 标准库，通过 `gh api` 调用 github.com。Token 由 GitHub CLI 管理，不写入共享代码、笔记或绑定配置。

## 工具

| 工具 | 用途 |
| --- | --- |
| `notes_status` | 检查当前 GitHub 身份和笔记库绑定 |
| `notes_discover` | 按名称和描述发现候选，检查远程笔记目录标记 |
| `notes_inspect_repository` | 分析权限、可见性、默认分支、目录和约定文件 |
| `notes_read_repository_file` | 读取首次设置需要的 README、AGENTS 等约定 |
| `notes_bind_repository` | 在本机记住用户选择的仓库与目录 |
| `notes_create_repository` | 按需创建仓库，默认私有 |
| `notes_initialize` | 新增 `.github-notes.json`，帮助其他电脑识别笔记目录 |
| `notes_categories` | 查询已有分类、子分类及 Markdown 数量 |
| `notes_list` / `notes_search` / `notes_get` | 分页列表、检索正文、读取笔记及 SHA；列表和搜索可按 `category` 筛选 |
| `notes_asset_create` | 保存本机 PNG/JPEG/WebP，核对提交字节，拒绝覆盖不同图片 |
| `notes_asset_info` | 读取已保存图片的类型、大小与 SHA-256，帮助恢复结果未知的上传 |
| `notes_create` | 新增 Markdown，拒绝覆盖已有文件 |
| `notes_update` / `notes_append` | 带预期 SHA 编辑或追加，拒绝过期版本 |

每次写入直接提交并读回校验。工具无删除、修改仓库可见性或执行笔记内命令的功能。搜索结果明确返回范围和游标；自动发现采用名称启发式，找不到时可以直接指定仓库。

列表、分类与搜索只覆盖绑定目录，不自动纳入仓库其他历史目录。分类统计包含 README 等索引文件；它不是语义分类审核结果。

## 更新到新版

在原安装源码目录执行：

```sh
git pull --ff-only
python3 install.py
```

原先使用 `--skip-mcp` 安装的客户端，更新时继续使用 `python3 install.py --skip-mcp`。已有有效授权和仓库绑定可继续使用。安装器会备份同名 Skill；更新后重启对应 MCP 或客户端，使运行中的进程加载新代码和工具列表。当前聊天也可先使用 Skill 附带 CLI 调用新工具。

## 安装位置与其他客户端

Skill 默认安装到 `${CODEX_HOME:-~/.codex}/skills/github-notes`；MCP 使用 `codex mcp add` 写入用户配置，保留已有服务。更新前备份同名 Skill；发现同名但不同配置的 MCP 时拒绝覆盖。

`python3 install.py --skip-mcp` 仅安装 Skill，并打印其他 MCP 客户端可用的配置。运行入口为：

```sh
python3 /absolute/path/to/github-notes/scripts/github_notes.py stdio
```

CLI 也可直接调用相同工具：

```sh
python3 skills/github-notes/scripts/github_notes.py status
python3 skills/github-notes/scripts/github_notes.py tools
python3 skills/github-notes/scripts/github_notes.py call notes_discover
```

对有参数的调用，将 JSON 写入临时文件，使用 `--json-file /path/to/arguments.json`；不要把笔记正文拼入 shell。

详细授权、跨电脑流程与限制见 [setup.md](skills/github-notes/references/setup.md)。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

单元测试使用内存中的模拟 GitHub，不创建真实仓库。真实 GitHub 验收记录见 [VALIDATION.md](VALIDATION.md)。

项目为 MIT。个人笔记及其引用资源的许可不由本项目许可证授予。
