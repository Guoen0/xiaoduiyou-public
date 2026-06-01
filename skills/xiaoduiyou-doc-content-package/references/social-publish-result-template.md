# Xiaoduiyou Xiaohongshu / Moments result templates

Use this reference when a connected Agent needs Xiaoduiyou to render social-publishing result tabs: 小红书发布稿 and/or 朋友圈发布稿.

The visible publish tabs render from structured fields. Do not rely on the process document being parsed into final publish content.

## Template selection

Select one or both templates with `ui_templates`:

```json
{
  "ui_templates": ["xiaohongshu", "moments"]
}
```

Supported social keys:

- `xiaohongshu`: 小红书发布稿 UI
- `moments`: 朋友圈发布稿 UI

If `ui_templates` is omitted, the UI may fall back to available `publish_notes` keys or legacy defaults. New Agents should always set `ui_templates` explicitly.

## Data locations

Preferred structured fields:

```json
{
  "fields": {
    "publish_notes": {
      "xiaohongshu": {
        "platform": "xiaohongshu",
        "label": "小红书发布稿",
        "title": "标题",
        "body": "正文，不含过程说明",
        "images": ["https://durable-asset-url/cover.webp"],
        "hashtags": ["#这个App应该消失", "#AI产品观察"]
      },
      "moments": {
        "platform": "moments",
        "label": "朋友圈发布稿",
        "body": "朋友圈正文",
        "images": ["https://durable-asset-url/cover.webp"]
      }
    }
  }
}
```

When completing a turn directly with an artifact, put the same object under `artifact.blocks.publish_notes`.

## Type shape

```ts
type PlatformPublishNote = {
  platform: 'xiaohongshu' | 'moments' | string;
  label: string;
  body: string;
  title?: string;      // required for xiaohongshu; optional/unused for moments
  images?: string[];   // durable browser-accessible URLs only
  hashtags?: string[]; // xiaohongshu only; UI appends them to body for copying
};
```

## Xiaohongshu contract

Required:

- `platform: "xiaohongshu"`
- `label: "小红书发布稿"`
- `title`: final note title only, not a process heading.
- `body`: ready-to-copy note body. Do not include prompt, visual-direction notes, source research, or process headings.
- `images`: final images in publishing order. First image is the feed cover.
- `hashtags`: evidence-based hashtags. Preserve project/series tags when required by the user.

Rendering behavior:

- The UI shows a carousel of `images`.
- The first image is used as the waterfall/cover preview.
- Copying body uses `body + hashtags.join(' ')`.

Good example:

```json
{
  "platform": "xiaohongshu",
  "label": "小红书发布稿",
  "title": "这个 App 应该消失：某某工具",
  "body": "我不想再打开一个只会制造中间步骤的工具了。\n\n它的问题不是功能少，而是把本来可以自动结束的事，又拆成了十几个按钮。",
  "images": [
    "https://<xiaoduiyou-asset-host>/cases/app-xhs-01.webp",
    "https://<xiaoduiyou-asset-host>/cases/app-xhs-02.webp"
  ],
  "hashtags": ["#这个App应该消失", "#AI产品观察"]
}
```

## Moments contract

Required:

- `platform: "moments"`
- `label: "朋友圈发布稿"`
- `body`: ready-to-copy朋友圈正文.
- `images`: optional; use the same final images or a smaller platform-specific subset.

Rendering behavior:

- The UI shows a WeChat Moments-like card.
- Long body may be collapsed in preview, with an expand control.
- Image grid uses WeChat-like layouts: 1 image large, 2/4 as 2 columns, 3+ as 3 columns.
- If `publish_notes.moments.images` is missing or empty, the UI falls back to Xiaohongshu images.
- If `publish_notes.moments` is missing but `moments` template is selected, the UI falls back to Xiaohongshu body/images. New Agents should still provide explicit Moments copy when the user expects it.

Good example:

```json
{
  "platform": "moments",
  "label": "朋友圈发布稿",
  "body": "今天做了一个小队友旅行规划示例：一岁宝宝旅行规划。\n\n重点不是列景点，而是把午睡、吃饭、撤退路线和酒店位置一起算进去。",
  "images": [
    "https://<xiaoduiyou-asset-host>/cases/travel-cover.webp"
  ]
}
```

## Legacy fallback

`blocks.publish_note` is a Xiaohongshu compatibility alias only:

```json
{
  "publish_note": {
    "title": "标题",
    "body": "正文",
    "images": ["https://..."],
    "hashtags": ["#... "]
  }
}
```

Do not use it for new integrations. Use `publish_notes.xiaohongshu` and `publish_notes.moments` instead.

## Image rules

- Local paths are invalid: `/tmp`, `/Users`, `~/.hermes/cache`, `file://`, `MEDIA:`.
- Repository/server static paths are invalid for durable Agent output: `/official`, `/public`, `/replay-images`.
- Upload generated/local images through Xiaoduiyou `/api/assets`, then write the returned public URL.
- Verify every image URL with `GET`/`HEAD`: HTTP `200`, `content-type` starts with `image/`.

## Process/result separation

The process document may include:

- source evidence;
- image prompts;
- alternative titles;
- rejected drafts;
- compliance notes;
- visual direction.

The publish tabs should contain only final user-facing copy and final images. Do not place process sections such as `图片结构`, `参考资料`, `prompt`, `修改记录`, or `过程材料` in `publish_notes.*.body`.

## Verification checklist

- [ ] `ui_templates` contains `xiaohongshu` and/or `moments` as intended.
- [ ] Every selected template has matching `publish_notes.<template>` data.
- [ ] Xiaohongshu has `title`, `body`, ordered `images`, and `hashtags` when hashtags are needed.
- [ ] Moments has platform-specific `body`; image fallback to Xiaohongshu is intentional if used.
- [ ] First Xiaohongshu image is the feed cover.
- [ ] All images are durable public URLs and verified.
- [ ] No process headings or internal notes appear in final copy.
