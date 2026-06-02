# xiaoduiyou-public

Public Xiaoduiyou Agent integration repository for connected Agents.

This repository is the source of truth for Xiaoduiyou Agent-facing packages. Do not download generated zip files from the Xiaoduiyou app project; clone or pull this repository and install the package directories directly.

Repository URL:

```text
https://github.com/Guoen0/xiaoduiyou-public.git
```

## Contents

| Package | Path | Purpose |
|---|---|---|
| Hermes platform plugin | `plugins/xiaoduiyou-hermes-platform/xiaoduiyou_hermes_platform/` | Hermes Gateway platform adapter: pending-turn polling, progress/final callbacks, document tools, outbound session messages. |
| OpenClaw connector | `plugins/xiaoduiyou-openclaw-connector/` | OpenClaw channel connector for Xiaoduiyou pending Agent turns. |
| Xiaoduiyou IM skill | `skills/xiaoduiyou-im/` | First entry for Xiaoduiyou Agent chat/IM intents: visual cards, product/source cards, Taobao/Xiaohongshu candidates, asset uploads, runtime messages, and chat-only delivery. |
| Xiaoduiyou document/content-package skill | `skills/xiaoduiyou-doc-content-package/` | Document artifacts, content packages, publish tabs, process docs, travel plans, and document create/update/delete operations. |
| Xiaoduiyou Growth Diary skill | `skills/xiaoduiyou-growth-diary/` | Growth Diary records, photos, summaries, schema-aware updates, and diary views. |

`manifest.json` describes the package paths in this public repository. It intentionally does not expose maintainer-local paths, deploy hosts, or secrets.

## Runtime skill routing

Connected Agents should use these three skills directly:

| User/task shape | Load |
|---|---|
| Agent 对话页 / chat-only task / cards / product-source candidates / runtime messages | `xiaoduiyou-im` |
| 文档 / 内容包 / 发布稿 / 旅游规划 / process docs / `ui_templates` / `publish_notes` | `xiaoduiyou-doc-content-package` |
| 成长日记 / 宝宝记录 / diary photos / diary schema or views | `xiaoduiyou-growth-diary` |

There is no public `xiaoduiyou-usage-workflow` router. Cases live in the skill that owns the surface.

## Agent setup prompt: Hermes Agent

When a Xiaoduiyou user asks a Hermes Agent to connect, the Agent should read this README first, then follow this section. The Xiaoduiyou app will provide the current `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN` in the copied setup message.

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

"$XDY_PUBLIC_DIR/scripts/install-hermes.sh"
```

运行规则：
- Hermes 只安装小队友 platform 插件；不要从这个仓库安装或覆盖 Hermes skills，skills 由 Hermes 自己整理和更新。
- Agent 对话页 / 卡片 / 商品候选 / runtime message：先加载 `xiaoduiyou-im`。
- 文档 / 内容包 / 发布稿 / 旅游规划 / publish tabs：加载 `xiaoduiyou-doc-content-package`。
- 成长日记 / 宝宝记录 / diary photos：加载 `xiaoduiyou-growth-diary`。
- 不要把 `platform_toolsets.xiaoduiyou` 只配置成 `["xiaoduiyou"]`；要保留本地文件、终端、搜索、浏览器等 Hermes 工具。
- 不要修改小队友网站代码、UI、样式、接口实现或部署。
- 同一时间只允许一个 Agent 接入；如果你开始连接，就视为替换掉其他 Agent。
````

## Agent setup prompt: OpenClaw

When a Xiaoduiyou user asks an OpenClaw Agent to connect, the Agent should read this README first, then follow this section. The Xiaoduiyou app will provide the current `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN` in the copied setup message.

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

"$XDY_PUBLIC_DIR/scripts/install-openclaw.sh"
```

运行规则：
- `XDY_PUBLIC_DIR` 必须是专用安装缓存目录；不要指向 `~/.openclaw/workspace`，也不要在 `~/.openclaw/workspace` 里 clone / pull 这个仓库。
- OpenClaw skill 只有进入当前 Agent 的 `agents.list[0].skills` allowlist 后才会进入模型上下文；仅安装到 `~/.openclaw/workspace/skills` 不够。
- OpenClaw tool policy 必须允许插件工具组；脚本会把 `tools.alsoAllow` 合并补上 `group:plugins`。如果 Connected tools 里看不到 `xiaoduiyou_growth_diary_get` / `xiaoduiyou_growth_diary_patch`，先重新执行 `scripts/install-openclaw.sh` 并重启 Gateway。
- Agent 对话页 / 卡片 / 商品候选 / runtime message：先加载 `xiaoduiyou-im`。
- 文档 / 内容包 / 发布稿 / 旅游规划 / publish tabs：加载 `xiaoduiyou-doc-content-package`。
- 成长日记 / 宝宝记录 / diary photos：加载 `xiaoduiyou-growth-diary`。
- 不要修改小队友网站代码、UI、样式、接口实现或部署。
- 同一时间只允许一个 Agent 接入；如果你开始连接，就视为替换掉其他 Agent。
````

## Third-party Agent guidance

Agents that are not Hermes or OpenClaw should still start from this repository:

1. Clone or update `https://github.com/Guoen0/xiaoduiyou-public.git` in a dedicated install/cache directory.
2. Read the matching skill under `skills/`:
   - `skills/xiaoduiyou-im/SKILL.md`
   - `skills/xiaoduiyou-doc-content-package/SKILL.md`
   - `skills/xiaoduiyou-growth-diary/SKILL.md`
3. Use the Xiaoduiyou app-provided base URL and connection token for polling/callbacks.
4. Do not reimplement product behavior from guesses; follow the bundled skill references.

## Important image/card rule

When an Agent renders product-link visual cards in Xiaoduiyou, it must use the product page/listing’s actual first product image, upload that image through Xiaoduiyou `/api/assets` / TOS, and use the returned durable URL in `image_urls` and `image_attachments[].image_url`. Do not use placeholders, local `MEDIA:` paths, screenshots, or raw third-party hotlinks as final card images.

## Maintenance

- This repository is consumed by Agents via `git clone` / `git fetch` in dedicated install/cache directories.
- OpenClaw Agents must not use `~/.openclaw/workspace` as the clone or update target; that directory is reserved for Agent work files.
- Generated `.zip` artifacts are intentionally not tracked here.
- Do not add maintainer-local paths, private repo URLs, Sealos devbox paths, or credentials to this README or package files.
