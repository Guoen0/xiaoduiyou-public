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

## Xiaohongshu sourcing

Use Xiaohongshu for real-user context and visual/installation references.

Capture for each useful note:

- `title`
- `author` when available
- `note_url`: clean browser-openable note URL
- `cover_image_url`: durable Xiaoduiyou asset URL if rendered in Xiaoduiyou
- `raw_cover_url`: temporary source URL only in process notes if useful; never as final rendered image
- `why_relevant`: one-line reason, e.g. “同车型后排安装参考”, “吐槽点集中在肩带/空间”, “真实使用半年反馈”
- `source_platform: "xiaohongshu"`

Clean note links before storing/displaying:

- Prefer canonical note URLs such as `https://www.xiaohongshu.com/explore/{note_id}` or the stable web note URL returned by the browser/tool.
- Strip tracking/session query params such as `xsec_token`, `xsec_source`, `share_from_user_hidden`, `appuid`, `apptime`, `timestamp`, `spm`, `utm_*` unless removing them breaks the link.
- Verify the cleaned link opens or redirects to the note.

Image handling:

- If a Xiaohongshu cover/image is shown in Xiaoduiyou, download it as a temporary staging file, upload through Xiaoduiyou `/api/assets`, and render the returned durable URL.
- The temporary staging file must stay local/ephemeral. Do not place source/replay/reference images under the app server's `public/`, `dist/`, `/official-replay`, `/replay-images`, or any repository/server static path.
- Keep the source link as `link_url`; do not hotlink temporary XHS image CDN URLs in final UI.
- If the image cannot be downloaded/uploaded, omit the image card and keep a text source link.

## Taobao/Tmall sourcing

Use Taobao/Tmall for buyable options and parameter/price cross-checks.

Capture for each candidate:

- `title`
- `item_url`: clean clickable item URL
- `image_url`: durable Xiaoduiyou asset URL if rendered in Xiaoduiyou
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

## UI insertion: message cards first

For product questions, the Xiaoduiyou chat answer should include image attachment cards whenever reliable images are available. Send them through progress/final payload `image_attachments` so the UI can render clickable visual cards in the conversation.

If the user asks “用视觉卡片 / 换成卡片 / 点图能跳转” after a text-only source list, treat that as a formatting correction and send cards immediately; do not repeat the text list or explain the format first. Use 2–6 high-signal cards, with image + title + short subtitle + clean `link_url`.

Do **not** send visual cards to Xiaoduiyou as Markdown images or local `MEDIA:/...` attachments. Xiaoduiyou chat does not render generic Hermes `MEDIA:` attachments. Use the bundled script so every card is uploaded to Xiaoduiyou assets and delivered as structured `image_attachments`:

```bash
HERMES_SKILL_HOME="${HERMES_HOME:-$HOME/.hermes}"
python "$HERMES_SKILL_HOME/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --list-sessions
python "$HERMES_SKILL_HOME/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --session-id sess_0005 \
  --text '龙柳小红书参考卡片' \
  --card '{"image_path":"/tmp/card.png","title":"龙柳参考","link_url":"https://www.xiaohongshu.com/explore/...","badge":"参考帖"}'
```

Use this payload shape on `POST /api/hermes/turns/{turn_id}/events`, final callback progress-equivalent payload, or `POST /api/agent/sessions/{session_id}/messages` when sending outside an active turn:

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

- `image_url` must be a durable Xiaoduiyou/TOS/asset URL verified with HTTP 200 and image content-type.
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
- [ ] Rendered images are uploaded through `/api/assets`, not hotlinked from temporary XHS/Taobao CDNs.
- [ ] Chat payload includes `image_attachments` for high-signal visual sources when images are available.
- [ ] Xiaohongshu cards are labeled `参考帖`; Taobao/Tmall cards are labeled `商品候选`.
- [ ] The final answer separates experience evidence from purchase candidates and names uncertainties.
