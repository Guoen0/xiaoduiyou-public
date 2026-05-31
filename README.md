# xiaoduiyou-public

Public Xiaoduiyou Agent integration packages for connected Agents.

This repository replaces the old “download a generated zip from Xiaoduiyou” flow. Agents should clone or pull this repository, then install the package directories directly.

## Contents

| Package | Path | Purpose |
|---|---|---|
| Hermes platform plugin | `plugins/xiaoduiyou-platform/xiaoduiyou_platform/` | Hermes Gateway platform adapter, pending-turn polling, progress/final callbacks, document tools, outbound session messages. |
| OpenClaw connector | `plugins/xiaoduiyou-openclaw-connector/` | OpenClaw channel connector for Xiaoduiyou pending Agent turns. |
| Public usage skill | `skills/xiaoduiyou-usage-workflow/` | Runtime/product-surface usage rules: content packages, product Q&A, image uploads, Growth Diary, travel/social templates. |

`manifest.json` records the upstream Xiaoduiyou app commit that these public packages were synced from.

## Quick install: Hermes Agent

```bash
# 1. Clone or update this repo
mkdir -p ~/.xiaoduiyou
if [ -d ~/.xiaoduiyou/xiaoduiyou-public/.git ]; then
  git -C ~/.xiaoduiyou/xiaoduiyou-public pull --ff-only
else
  git clone https://github.com/Guoen0/xiaoduiyou-public.git ~/.xiaoduiyou/xiaoduiyou-public
fi

cd ~/.xiaoduiyou/xiaoduiyou-public

# 2. Install/update the Hermes platform plugin
mkdir -p ~/.hermes/plugins/xiaoduiyou_platform
rsync -a --delete plugins/xiaoduiyou-platform/xiaoduiyou_platform/ ~/.hermes/plugins/xiaoduiyou_platform/

# 3. Install/update the public Xiaoduiyou usage skill
mkdir -p ~/.hermes/skills/productivity/xiaoduiyou-usage-workflow
rsync -a --delete skills/xiaoduiyou-usage-workflow/ ~/.hermes/skills/productivity/xiaoduiyou-usage-workflow/

# 4. Restart Hermes Gateway after plugin updates
hermes gateway restart
```

Hermes config still needs a Xiaoduiyou platform entry and token issued by Xiaoduiyou. Do not commit tokens or credentials into this repo.

## Quick install: OpenClaw

```bash
# 1. Clone or update this repo
mkdir -p ~/.xiaoduiyou
if [ -d ~/.xiaoduiyou/xiaoduiyou-public/.git ]; then
  git -C ~/.xiaoduiyou/xiaoduiyou-public pull --ff-only
else
  git clone https://github.com/Guoen0/xiaoduiyou-public.git ~/.xiaoduiyou/xiaoduiyou-public
fi

cd ~/.xiaoduiyou/xiaoduiyou-public

# 2. Install/update the OpenClaw connector
mkdir -p ~/.openclaw/extensions/xiaoduiyou
rsync -a --delete plugins/xiaoduiyou-openclaw-connector/ ~/.openclaw/extensions/xiaoduiyou/
```

Restart the OpenClaw gateway/runtime after updating the connector.

## Update workflow for package maintainers

From the Xiaoduiyou app repository, sync the current public package source into this repository:

```bash
cd /path/to/xiaoduiyou-public
./scripts/sync-from-xiaolanbi.sh /path/to/xiaolanbi

git diff --stat
git add plugins skills manifest.json
git commit -m "Sync Xiaoduiyou public packages"
git push origin main
```

Do not add generated `.zip` artifacts here. This repository is meant to be consumed by `git clone` / `git pull`.

## Important image/card rule

When an Agent renders product-link visual cards in Xiaoduiyou, it must use the product page/listing’s actual first product image, upload that image through Xiaoduiyou `/api/assets` / TOS, and use the returned durable URL in `image_urls` and `image_attachments[].image_url`. Do not use placeholders, local `MEDIA:` paths, screenshots, or raw third-party hotlinks as final card images.
