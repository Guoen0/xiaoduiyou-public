# Xiaoduiyou product-question workflow

Use this when the user asks Xiaoduiyou a concrete product question such as “这个安全座椅买哪个”, “帮我看下某个商品/App/品牌”, “有没有真实反馈”, “搜一下这个产品”, or “给我几个可买候选”. This is a usage-Agent workflow: gather evidence and return a richer Xiaoduiyou answer/document through runtime fields and message attachments. Do not change Xiaoduiyou source code or UI implementation from this skill.

## Default behavior

When the task is about a real product, prefer evidence collection over generic advice:

1. Identify the product/category, user constraints, and decision goal.
   - If the product/category is clear, start searching. Do not ask for clarification just to avoid work.
   - Ask only when the missing constraint changes the search target materially, e.g. car model, child age/height/weight, budget ceiling, city, or required platform.
2. Search Xiaohongshu for lived experience, installation/use cases, pitfalls, and scenario photos.
3. Search Taobao/Tmall for buyable candidates, exact SKUs/options, prices/promos when available, seller/store context, and product parameter pages.
4. Cross-check the claims: treat Xiaohongshu as experience/reference evidence and Taobao as purchase/parameter candidates.
5. Return a concise recommendation with clickable cards/images, not only a text paragraph.

## Recommendation grounding and novelty

Before searching or recommending gifts, style-sensitive products, or repeat purchases, build four short buckets:

- **Explicit preference:** the person directly said they like/want it.
- **Inferred signal:** an aesthetic or functional preference inferred from prior choices; label it as inference.
- **Already used / already purchased:** exclude by default. A successful past gift is evidence about taste, not permission to recommend the same gift again.
- **Unknown:** size, material, brand, budget, wearing habits, or other facts that cannot be recovered.

Do not force a recommendation when the evidence only supports a mood or aesthetic. Translate the signal into new categories, then verify real products. If an AI/search source returns precise-sounding product names without stable listing URLs, treat them as unverified leads and do not repeat them to the user. A recommendation must distinguish exact matches from partial matches, especially for material claims such as solid 18K gold versus gold vermeil, plated silver, brass, or generic “18K color.”

For follow-up requests like “换一些词再找”, vary search vocabulary by independent dimensions such as form, surface, material, and intended use instead of cycling through superficial synonyms. Choose terms from the user's current request rather than carrying preferences over from an unrelated purchase. Then filter out misleading material titles, imitation listings, implausible price/material combinations, poor return terms, and low-evidence sellers before presenting candidates.

### Jewelry and ring-size verification

- Treat price and material as separate axes. A high-priced designer ring may still use a base metal; explain whether the buyer is paying for design/craft or precious-metal value.
- Open the exact SKU page before stating material. A precious-metal color name in a variant label does not prove that the underlying material is that metal; verify the material field and seller description.
- Read the available size options from the live SKU panel. A numeric range may resemble a familiar sizing system, but do not assert the standard unless the page or seller confirms it.
- Use inner diameter in millimetres as the cross-system reference. Measure an existing ring from the intended finger, inner edge to inner edge; do not infer the intended size from another person's measurement or a remembered conversion shortcut.
- Wide, heavy, and multi-band rings fit tighter than thin bands. If between sizes, ask whether half sizes or resizing are available rather than blindly rounding down.
- When the system is unstated, give a concrete seller message such as: `请确认页面圈号采用什么标准；该尺码成品内径是多少毫米；现有戒指内径XXmm应选哪号，是否支持改圈？`
- If the user remembers only a vague historical ring number, recover the exact old order/SKU or measure a ring. Do not invent a conversion: mainstream regional sizing systems can assign very different numbers to the same inner diameter.

## Xiaohongshu sourcing

Use Xiaohongshu for real-user context and visual/installation references.

Capture for each useful note:

- `title`
- `author` when available
- `note_url`: clean browser-openable note URL
- `cover_image_url`: browser-fetchable HTTPS image URL if rendered in Xiaoduiyou; use the original external URL directly when stable/fetchable, or a Xiaoduiyou asset URL after upload when needed
- `raw_cover_url`: temporary source URL only in process notes if useful; never as final rendered image when it is login-bound, expiring, anti-hotlinking, or not directly fetchable
- `why_relevant`: one-line reason, e.g. “同车型后排安装参考”, “吐槽点集中在肩带/空间”, “真实使用半年反馈”
- `source_platform: "xiaohongshu"`

Clean note links before storing/displaying:

- Prefer canonical note URLs such as `https://www.xiaohongshu.com/explore/{note_id}` or the stable web note URL returned by the browser/tool.
- Strip tracking/session query params such as `xsec_token`, `xsec_source`, `share_from_user_hidden`, `appuid`, `apptime`, `timestamp`, `spm`, `utm_*` unless removing them breaks the link.
- Verify the cleaned link opens or redirects to the note.

Image handling:

- If a Xiaohongshu cover/image URL is public HTTPS and fetchable without cookies/login, it may be rendered directly in Xiaoduiyou.
- If the source URL is temporary, signed, anti-hotlinking, or only works in the current browser session, download it as a temporary staging file when allowed, upload through Xiaoduiyou `/api/assets`, and render the returned durable URL.
- The temporary staging file must stay local/ephemeral. Do not place source/replay/reference images under the app server's `public/`, `dist/`, `/official-replay`, `/replay-images`, or any repository/server static path.
- Keep the source link as `link_url`; do not hotlink temporary XHS image CDN URLs in final UI.
- If the image cannot be downloaded/uploaded, omit the image card and keep a text source link.

## Taobao/Tmall sourcing

Use Taobao/Tmall for buyable options and parameter/price cross-checks.

Capture for each candidate:

- `title`
- `item_url`: clean clickable item URL
- `image_url`: browser-fetchable HTTPS image URL if rendered in Xiaoduiyou; use the original external URL directly when stable/fetchable, or a Xiaoduiyou asset URL after upload when needed
- `price` / `price_note` when visible
- `shop` / `seller` when visible
- `option` / `sku_note` for the exact variant if the user constraint depends on it
- `why_candidate`: one-line reason, e.g. “可对照参数”, “适合某车型/年龄段”, “预算内候选”
- `risk_or_unknown`: what still needs manual confirmation, e.g. “需确认是否适配理想 L7 ISOFIX”
- `source_platform: "taobao"` or `"tmall"`

Clean item links before storing/displaying:

- Prefer canonical desktop links:
  - `https://item.taobao.com/item.htm?id={item_id}`
  - `https://detail.tmall.com/item.htm?id={item_id}`
- Preserve only parameters required to open the exact product/variant, usually `id` and occasionally `skuId` if variant-specific.
- Strip tracking params such as `spm`, `scm`, `abbucket`, `utparam`, `ns`, `xxc`, `pvid`, `ali_refid`, `ali_trackid`, `utm_*`.
- Expand share/short/redirect links first, then canonicalize.
- Verify the clean link is still browser-openable. If login is required, label it as “可能需要登录淘宝”.

### Taobao visual-card fallback

Taobao search output may provide title, price, shop, item ID, and URL but no stable main-image URL. When the user asks to see pictures:

1. Shortlist 2–6 candidates from search results before opening pages; do not screenshot every result.
2. Open each canonical item URL in the authenticated OpenCLI browser and verify that the product title, material claim, visible price, return terms, and main image agree with the search row.
3. Take a local screenshot, then crop to the main product-photo area. Do not use a giant full-page screenshot as the card thumbnail when a clean crop is possible.
4. QA the crop for the actual product and remove account-identifying chrome or unrelated UI.
5. Upload the crop through `xiaoduiyou_assets_upload`, use the durable HTTPS URL as `image_url`, keep the canonical Taobao URL as `display.link_url`, and send in the same turn through `xiaoduiyou_im_send`.
6. Verify `attachment_count` equals the number of promised cards before claiming delivery.

Card subtitles should state the actual material and visible price compactly, and call out critical uncertainty such as “镀金而非实金”, “开口可调”, “预售30天”, “不支持七天无理由”, or “价格以打开页面为准”.

## UI insertion: message cards first

For product questions, the Xiaoduiyou chat answer should include image attachment cards whenever reliable images are available. Send them through progress/final payload `image_attachments` so the UI can render clickable visual cards in the conversation.

If the user asks “用视觉卡片 / 换成卡片 / 点图能跳转” after a text-only source list, treat that as a formatting correction and send cards immediately; do not repeat the text list or explain the format first. Use 2–6 high-signal cards, with image + title + short subtitle + clean `link_url`.

Do **not** send visual cards to Xiaoduiyou as Markdown images or local `MEDIA:/...` attachments. Xiaoduiyou chat does not render generic Hermes `MEDIA:` attachments. Prefer `xiaoduiyou_im_send`; for old connectors without that tool, use the bundled script so every card is delivered through `/api/agent/im/send`:

```bash
HERMES_SKILL_HOME="${HERMES_HOME:-$HOME/.hermes}"
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --list-channels
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --channel default \
  --text '龙柳小红书参考卡片' \
  --cards-json '[{"image_path":"/tmp/card.png","title":"龙柳参考","link_url":"https://www.xiaohongshu.com/explore/...","badge":"参考帖"}]'
```

Use this payload shape on `POST /api/agent/turns/{turn_id}/events`, final callback progress-equivalent payload, or `POST /api/agent/im/send` with `channel: "default"` when sending outside an active turn:

```json
{
  "label": "小队友",
  "detail": "我把小红书经验帖和淘宝候选都放在下面，点图片可以跳转原链接。",
  "image_attachments": [
    {
      "image_url": "https://xiaoduiyou-assets.example.com/xhs-cover.webp",
      "link_url": "https://www.xiaohongshu.com/explore/xxxx",
      "title": "同车型安装参考",
      "subtitle": "小红书 · 真实使用帖",
      "badge": "参考帖"
    },
    {
      "image_url": "https://xiaoduiyou-assets.example.com/taobao-item.webp",
      "link_url": "https://item.taobao.com/item.htm?id=123456",
      "title": "商品名 / 关键型号",
      "subtitle": "淘宝 · ¥价格/店铺/关键参数",
      "badge": "商品候选"
    }
  ]
}
```

Card rules:

- `image_url` must be a browser-fetchable HTTPS image URL verified with HTTP 200 and image content-type. It can be an external source image URL when stable/fetchable, or a Xiaoduiyou/TOS/asset URL after upload.
- `image_url` must not be a server-local/static URL such as `/official-replay/...`, `/replay-images/...`, `/public/...`, `/tmp/...`, or `/Users/...`.
- `link_url` must be the clean source/product link that the user can click.
- Use `badge: "参考帖"` for Xiaohongshu; use `badge: "商品候选"` for Taobao/Tmall.
- `title` should identify the note/product; `subtitle` should explain source and why it matters.
- Keep 2–6 cards. Prefer a small set of high-signal sources over dumping all results.
- If the final answer mentions “小红书是经验口径 / 淘宝是商品候选”, the cards should visually reflect that split.

## UI insertion: artifact/document fields

If the answer creates or updates a Xiaoduiyou document/content artifact, keep product evidence in process material and structured fields rather than only freeform Markdown.

Recommended fields under `fields` or `artifact.blocks`:

```json
{
  "source_markdown": "## 过程材料\n...",
  "product_research": {
    "query": "安全座椅 理想 L7 14个月",
    "decision_summary": "先看安装/适配风险，再从可买候选里挑...",
    "reference_posts": [
      {
        "source_platform": "xiaohongshu",
        "title": "...",
        "url": "https://www.xiaohongshu.com/explore/xxxx",
        "image_url": "https://durable-asset/cover.webp",
        "why_relevant": "同车型安装参考"
      }
    ],
    "product_candidates": [
      {
        "source_platform": "taobao",
        "title": "...",
        "url": "https://item.taobao.com/item.htm?id=123456",
        "image_url": "https://durable-asset/item.webp",
        "price_note": "¥...，以打开页面为准",
        "why_candidate": "参数可对照，适合...",
        "risk_or_unknown": "需确认..."
      }
    ]
  }
}
```

Current generic result templates (`xiaohongshu`, `moments`, `travel_plan`) should not be forced onto product QA unless the user is actually asking for a social post or travel plan. For normal product QA, use chat message `image_attachments` plus a process document/artifact link when the task needs persistent review.

## Answer composition

Use a compact structure:

1. `结论` — the actionable answer or shortlist.
2. `为什么` — 2–4 bullets tied to user constraints.
3. `小红书看到的经验口径` — summarize patterns, not every note.
4. `淘宝/天猫可买候选` — list candidates and remaining confirmations.
5. `我还不确定的点` — explicitly name missing checks such as exact vehicle fit, child size, return policy, or SKU variant.

Do not overstate scraped information. Prices, stock, promotions, and reviews change quickly; write “打开链接为准” when relevant.

## Validation checklist

- [ ] At least one Xiaohongshu source or a stated reason why none could be used.
- [ ] At least one Taobao/Tmall candidate or a stated reason why none could be used.
- [ ] Source links are clean and verified enough to click.
- [ ] Rendered images are browser-fetchable HTTPS URLs: stable external image URLs may be used directly; temporary/login-bound/anti-hotlinking source images are uploaded through `/api/assets` or omitted.
- [ ] Chat payload includes `image_attachments` for high-signal visual sources when images are available.
- [ ] Xiaohongshu cards are labeled `参考帖`; Taobao/Tmall cards are labeled `商品候选`.
- [ ] The final answer separates experience evidence from purchase candidates and names uncertainties.
