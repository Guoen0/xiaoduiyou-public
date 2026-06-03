# xiaoduiyou-public

Public Xiaoduiyou Agent integration repository for connected Agents.

Source of truth: `https://github.com/Guoen0/xiaoduiyou-public.git`. Clone or pull this repository directly; do not install generated zip files from the Xiaoduiyou app project.

## Contents

- Hermes platform plugin: `plugins/xiaoduiyou-hermes-platform/xiaoduiyou_hermes_platform/`
- OpenClaw connector: `plugins/xiaoduiyou-openclaw-connector/`
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
- Hermes 只安装小队友 platform 插件；不要从这个仓库安装或覆盖 Hermes skills，skills 由 Hermes 自己整理和更新。
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
- `XDY_PUBLIC_DIR` 必须是专用安装缓存目录；不要指向 `~/.openclaw/workspace`，也不要在 `~/.openclaw/workspace` 里 clone / pull 这个仓库。
- OpenClaw skill 只有进入当前 Agent 的 `agents.list[0].skills` allowlist 后才会进入模型上下文；仅安装到 `~/.openclaw/workspace/skills` 不够。
- OpenClaw tool policy 必须允许插件工具组；脚本会把 `tools.alsoAllow` 合并补上 `group:plugins`。如果 Connected tools 里看不到 `xiaoduiyou_growth_diary_get` / `xiaoduiyou_growth_diary_patch`，先重新执行 `scripts/install-openclaw.sh` 并重启 Gateway。
- 按 README 的 Runtime skill routing 和 Common Agent rules 执行。
````

## Third-party Agent guidance

Clone/update this repository in a dedicated install/cache directory, read the matching `skills/*/SKILL.md`, use Xiaoduiyou app-provided connection values, and follow the bundled skill references instead of guessing product behavior.

Notes: OpenClaw must not clone/update this repository under `~/.openclaw/workspace`; generated `.zip` artifacts and maintainer-local paths/secrets are intentionally not tracked here.
