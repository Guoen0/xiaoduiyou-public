# xiaoduiyou-public

Public Xiaoduiyou Agent integration repository for connected Agents.

Source of truth: `https://github.com/Guoen0/xiaoduiyou-public.git`. Clone or pull this repository directly; do not install generated zip files from the Xiaoduiyou app project.

## Contents

- Hermes platform plugin: `plugins/xiaoduiyou-hermes-platform/xiaoduiyou_hermes_platform/`
- OpenClaw connector: `plugins/xiaoduiyou-openclaw-connector/`
- Codex runtime skills plugin: `plugins/xiaoduiyou-runtime-skills/`
- Codex platform plugin: `plugins/xiaoduiyou-codex-platform/`
- Codex runner plugin: `plugins/xiaoduiyou-codex-runner/`
- IM skill: `skills/xiaoduiyou-im/`
- Document/content-package skill: `skills/xiaoduiyou-doc-content-package/`
- Growth Diary skill: `skills/xiaoduiyou-growth-diary/`
- Package manifest: `manifest.json`

## Runtime skill routing

Connected Agents should use these three skills directly:

| User/task shape | Load |
|---|---|
| Agent 对话页 / chat-only task / cards / product-source candidates / runtime messages | `xiaoduiyou-im` |
| 文档 / 内容包 / 发布稿 / 旅游规划 / process docs / `ui_templates` / `publish_notes` | `xiaoduiyou-doc-content-package` |
| 成长日记 / 宝宝记录 / diary photos / diary schema or views | `xiaoduiyou-growth-diary` |

There is no public `xiaoduiyou-usage-workflow` router. Cases live in the skill that owns the surface.

## Common Agent rules

- Use the Xiaoduiyou app-provided `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN` for the active connection.
- Do not modify Xiaoduiyou website code, UI, styles, API implementation, or deployment.
- Only one Agent should be connected at a time; starting a connection replaces the previous Agent.
- For Growth Diary writes, event time must come from the user's message. If the user gives an explicit time/date, use that. If the user says "now", "刚才", or gives no time, use the current Xiaoduiyou turn/user-message `created_at` timestamp as the basis for `occurred_at` and `date`. Do not invent a time, round to an arbitrary clock time, or use the Agent's local/system time unless it is the same turn timestamp provided by Xiaoduiyou.
- Product-link visual cards must use the product page/listing's actual first product image, uploaded through Xiaoduiyou assets/TOS, and the returned durable URL in `image_urls` and `image_attachments[].image_url`.
- Do not add maintainer-local paths, private repo URLs, deploy hosts, or credentials to this repository.

## Agent setup prompt: Hermes Agent

When a Xiaoduiyou user asks a Hermes Agent to connect, copy this prompt. The Xiaoduiyou app provides the current `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN`.

````text
你现在要连接到小队友，作为当前唯一启用的 Hermes Agent。

先读取并遵循 Xiaoduiyou public 仓库 README：
https://github.com/Guoen0/xiaoduiyou-public/blob/main/README.md

连接参数：
- XDY_BASE_URL=<由小队友设置页提供>
- XDY_CONNECTION_TOKEN=<由小队友设置页提供>

执行安装与配置：

```bash
XDY_PUBLIC_REPO="https://github.com/Guoen0/xiaoduiyou-public.git"
XDY_PUBLIC_DIR="$HOME/.xiaoduiyou/xiaoduiyou-public"
mkdir -p "$HOME/.xiaoduiyou"
if [ -d "$XDY_PUBLIC_DIR/.git" ]; then
  git -C "$XDY_PUBLIC_DIR" fetch origin main
  git -C "$XDY_PUBLIC_DIR" reset --hard origin/main
  git -C "$XDY_PUBLIC_DIR" clean -fd
else
  git clone "$XDY_PUBLIC_REPO" "$XDY_PUBLIC_DIR"
fi

XDY_BASE_URL="<由小队友设置页提供>" \
XDY_CONNECTION_TOKEN="<由小队友设置页提供>" \
"$XDY_PUBLIC_DIR/scripts/install-hermes.sh"
```

运行规则：
- Hermes 安装脚本会安装/更新小队友 platform 插件，以及 `xiaoduiyou-im`、`xiaoduiyou-doc-content-package`、`xiaoduiyou-growth-diary` 三个 runtime skills。
- 安装脚本会写入 `${HERMES_HOME:-~/.hermes}/config.yaml`，并把三个 runtime skills 安装到同一目录下的 `skills/productivity/`；如果你在 Hermes profile 下运行，先确保 `HERMES_HOME` 指向该 profile 目录。
- 安装脚本会禁用同一 `HERMES_HOME` 下 `.env` 里的旧 `XIAODUIYOU_BASE_URL` / `XIAODUIYOU_CONNECTION_TOKEN` 覆盖项，避免旧地址覆盖新配置。
- 不要把 `platform_toolsets.xiaoduiyou` 只配置成 `["xiaoduiyou"]`；要保留本地文件、终端、搜索、浏览器等 Hermes 工具。
- 按 README 的 Runtime skill routing 和 Common Agent rules 执行。
````

## Agent setup prompt: OpenClaw

When a Xiaoduiyou user asks an OpenClaw Agent to connect, copy this prompt. The Xiaoduiyou app provides the current `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN`.

````text
你现在要连接到小队友，作为当前唯一启用的 OpenClaw Agent。

先读取并遵循 Xiaoduiyou public 仓库 README：
https://github.com/Guoen0/xiaoduiyou-public/blob/main/README.md

连接参数：
- XDY_BASE_URL=<由小队友设置页提供>
- XDY_CONNECTION_TOKEN=<由小队友设置页提供>

执行安装与配置：

```bash
XDY_PUBLIC_REPO="https://github.com/Guoen0/xiaoduiyou-public.git"
XDY_PUBLIC_DIR="$HOME/.openclaw/vendor/xiaoduiyou-public"
mkdir -p "$(dirname "$XDY_PUBLIC_DIR")"
if [ ! -d "$XDY_PUBLIC_DIR/.git" ]; then
  rm -rf "$XDY_PUBLIC_DIR"
  git clone "$XDY_PUBLIC_REPO" "$XDY_PUBLIC_DIR"
else
  git -C "$XDY_PUBLIC_DIR" fetch origin main
  git -C "$XDY_PUBLIC_DIR" reset --hard origin/main
  git -C "$XDY_PUBLIC_DIR" clean -fd
fi

XDY_BASE_URL="<由小队友设置页提供>" \
XDY_CONNECTION_TOKEN="<由小队友设置页提供>" \
"$XDY_PUBLIC_DIR/scripts/install-openclaw.sh"
```

运行规则：
- `XDY_PUBLIC_DIR` 必须是专用安装缓存目录；不要指向 `${OPENCLAW_HOME:-~/.openclaw}/workspace`，也不要在 OpenClaw workspace 里 clone / pull 这个仓库。
- 安装脚本会写入 `${OPENCLAW_HOME:-~/.openclaw}`；如果你在 OpenClaw profile 下运行，先确保 `OPENCLAW_HOME` 指向该 profile 目录。
- OpenClaw skill 只有进入当前 Agent 的 `agents.list[0].skills` allowlist 后才会进入模型上下文；仅安装到 `${OPENCLAW_HOME:-~/.openclaw}/workspace/skills` 不够。
- OpenClaw tool policy 必须允许插件工具组；脚本会把 `tools.alsoAllow` 合并补上 `group:plugins`。如果 Connected tools 里看不到 `xiaoduiyou_growth_diary_get` / `xiaoduiyou_growth_diary_patch`，先重新执行 `scripts/install-openclaw.sh` 并重启 Gateway。
- 按 README 的 Runtime skill routing 和 Common Agent rules 执行。
````

## Agent setup prompt: Codex

When a Xiaoduiyou user asks Codex to connect, copy this prompt. The Xiaoduiyou app provides the current `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN`. Codex should install the public runtime skills plugin, platform plugin, and runner plugin, then start the local runner; the user should not need to understand or run a polling loop manually.

````text
你现在要连接到小队友，作为当前唯一启用的 Codex。

先读取并遵循 Xiaoduiyou public 仓库 README：
https://github.com/Guoen0/xiaoduiyou-public/blob/main/README.md

连接参数：
- XDY_BASE_URL=<由小队友设置页提供>
- XDY_CONNECTION_TOKEN=<由小队友设置页提供>

执行安装与配置：

```bash
XDY_PUBLIC_REPO="https://github.com/Guoen0/xiaoduiyou-public.git"
XDY_PUBLIC_DIR="$HOME/.codex/vendor/xiaoduiyou-public"
mkdir -p "$(dirname "$XDY_PUBLIC_DIR")"
if [ ! -d "$XDY_PUBLIC_DIR/.git" ]; then
  rm -rf "$XDY_PUBLIC_DIR"
  git clone "$XDY_PUBLIC_REPO" "$XDY_PUBLIC_DIR"
else
  git -C "$XDY_PUBLIC_DIR" fetch origin main
  git -C "$XDY_PUBLIC_DIR" reset --hard origin/main
  git -C "$XDY_PUBLIC_DIR" clean -fd
fi

export XDY_BASE_URL="<由小队友设置页提供>"
export XDY_CONNECTION_TOKEN="<由小队友设置页提供>"
"$XDY_PUBLIC_DIR/scripts/install-codex-runner.sh"
```

- 安装脚本会安装/更新三个 Codex 插件：`xiaoduiyou-runtime-skills`、`xiaoduiyou-codex-platform`、`xiaoduiyou-codex-runner`。
- `xiaoduiyou-runtime-skills` 会把 `xiaoduiyou-im`、`xiaoduiyou-doc-content-package`、`xiaoduiyou-growth-diary` 装进 Codex；这些 runtime skills 是 IM、内容包、成长日记行为的来源。
- 安装脚本会写入本地连接配置，启动后台 runner，并验证平台连接。
- 安装后使用 `xiaoduiyou-codex-runner` skill 检查 runner 状态；使用 `xiaoduiyou-codex-platform` skill 处理需要平台 MCP 工具的任务；按 `xiaoduiyou-im` / `xiaoduiyou-doc-content-package` / `xiaoduiyou-growth-diary` 执行用户消息。
- 不要把连接 token 打印回聊天；只汇报是否安装成功、runner 是否在线、失败时的明确原因。
- 按 README 的 Runtime skill routing 和 Common Agent rules 执行。
````

## Third-party Agent guidance

Clone/update this repository in a dedicated install/cache directory, read the matching `skills/*/SKILL.md`, use Xiaoduiyou app-provided connection values, and follow the bundled skill references instead of guessing product behavior.

Notes: OpenClaw must not clone/update this repository under `${OPENCLAW_HOME:-~/.openclaw}/workspace`; generated `.zip` artifacts and maintainer-local paths/secrets are intentionally not tracked here.
