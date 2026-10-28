---
name: github-resources
description: 检索和使用个人 GitHub 私有资源库中的供应商凭据、模型、数据库、Redis、邮件、服务器与部署信息。用户提到“我的百炼/服务/数据库/测试或正式环境”，或开发需要已有资源时，先查库并按项目适配；维护资源时按授权更新。
---

# GitHub 个人资源

这是跨项目云端供应商与远程服务入口，不绑定当前业务项目。本机服务、项目 Docker 与本地环境优先使用项目自身配置，默认不导入个人资源库。先查已维护的资源，再配置或开发；不要重复索取库里已有的凭据。资源库是普通私有 GitHub 仓库，当前存明文；公开 Skill 库只保存工具和虚构示例。

## 入口

本 Skill 仅依赖 Python 3.9+ 与 GitHub CLI。把下面 `<skill>` 替换为本 Skill 的绝对目录；不要依赖当前工作目录。

```sh
python3 <skill>/scripts/github_resources.py status
python3 <skill>/scripts/github_resources.py search 百炼
python3 <skill>/scripts/github_resources.py show <准确资源ID>
```

仓库优先级：`--repo owner/repo`、`GITHUB_RESOURCES_REPO`、本机绑定、当前账号的 `personal-resources`。不必每个项目重复指定。新设备先 `gh auth login --hostname github.com --git-protocol https --web`；账号授权由 gh 管理，不能把 Token 发到聊天或复制登录文件。需要自定义目标时运行 `bind owner/repo`。本机绑定位于 `~/.config/github-resources/config.json`，可由 `GITHUB_RESOURCES_CONFIG` 覆盖；绑定只存账号和仓库。

## 查找并使用

1. 根据需求搜索供应商、能力、环境或别名；必要时 `list`。`show` 返回非敏感配置、文档、模型、适用范围和脱敏的凭据字段名。搜索完整扫描当前目录的元数据，不扫描密钥值。
2. 区分账号、区域、环境、用途和地址可达范围。远程测试和生产资源分别使用，专用应用数据库不自动用作其他项目的数据库。本机服务直接按项目 Docker 或已有安装说明使用。查到多个候选时，用上下文选择；缺失的重要区别才问用户。
3. 阅读资源记录的官方文档，检查项目代码、SDK、协议和环境变量契约。模型列表是维护快照；供应商有模型发现接口时按已登记接口查询，但“返回模型”不等于当前 Key 对每个模型均有调用权限。缺少统一发现接口的 STT/TTS/Realtime 依照官方能力范围维护。不要捏造可用模型或声称配置导入等于接口验收。
4. 适配需求：实时语音优先登记的 Realtime 偏好，分段语音组合 STT/LLM/TTS；会议转写与纪要、OCR、数据库或邮件使用相应资源。按实际供应商协议接入，不强制经过统一 AI 网关。
5. 需要凭据时用 `export` 写本地文件，不先打印 catalog 或秘密原文。映射是一个 JSON 文件，例如 `{"LLM_API_KEY":"secrets.api_key","LLM_BASE_URL":"config.base_url","LLM_MODEL":"config.default_model"}`。

```sh
python3 <skill>/scripts/github_resources.py export <准确资源ID> \
  --map-file /absolute/path/mapping.json --output /absolute/path/.env.resources
```

输出默认拒绝覆盖、拒绝符号链接，POSIX 上以 0600 保存。生成的是字面量 dotenv，不能直接当 shell 脚本执行；Docker Compose、特殊 SDK 或引号密码需按其解析规则适配。先检查目标是否被 Git 忽略；不把凭据写入前端、公开仓库、日志、截图或聊天。更改既有环境文件前保留其他配置，不能用整文件覆盖代替合并。工具不会自动提交业务项目。

6. 用户要入口时返回工具提供的 GitHub 文件链接或记录中的服务/文档链接。`catalog.json` 的网页包含真实凭据，只有有仓库权限的账号可读；不要把这个链接描述为无凭据的公开说明页。不得将含密码的数据库连接串做成聊天链接。
7. 做与需求匹配的最小验证。现有开发授权可涵盖必要的测试调用；不要因查到密钥就发邮件、部署、改生产数据或运行无关请求。报告配置完成与真实调用通过的区别。

## 维护

查看 [资源格式与维护](references/catalog.md) 后创建资源 JSON，放本地受保护临时文件或从 stdin 传入，运行 `put --file`。修改已有记录需要当前 `catalog_sha`，通过 `--expected-sha` 提交，拒绝过期覆盖；服务超时或结果未知时先重新查询，不盲重试。维护请求才授权相应写入，查询请求不自动更新资源。不要从其他项目或设备无边界搜集凭据。

全部工具每次读取/写入都检查仓库私有权限；同一账号可以跨设备读取，不能因找不到资源降级到公开仓库。不自动改仓库可见性，不复制 gh 凭据。Skill 不提供密码加密、生产部署或后台同步。
