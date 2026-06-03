# Travel-plan reference-image workflow: Xiaohongshu sources

Use this when a Xiaoduiyou travel-plan case needs realistic destination/reference visuals from Xiaohongshu rather than generic placeholders.

## Workflow

1. Search Xiaohongshu for the selected destination plus the actual intent, e.g. `苏州金鸡湖 亲子游 宝宝`, `苏州 月光码头 亲子 金鸡湖`, `苏州 诚品书店 亲子 金鸡湖`.
2. Select notes whose title/cover directly support the final route: stroller-friendly route, low-age baby, hotel/activity proximity, food/supply fallback, named POIs in the itinerary.
3. Keep clean provenance:
   - Clean note URL: `https://www.xiaohongshu.com/explore/<note_id>` or an official share link.
   - Clean image URL: stripped of `xsec_token`, `xsec_source`, search/session query strings, and other tracking params.
4. Download selected images only as temporary staging files.
5. Upload every image to Xiaoduiyou asset storage / TOS before using it in the artifact, process doc, or result UI.
6. Store rendered URLs in:
   - `generated_images`
   - `publish_notes.travel_plan.images`
   - `publish_notes.travel_plan.travel_plan.destination.images`
   - Markdown image blocks in `source_markdown`
7. Store matching note/source links in `publish_notes.travel_plan.travel_plan.destination.image_links`, one-to-one with `destination.images`.
8. In the visible gallery, the UI can expose each source as a bottom-right CTA such as `小红书 ↗`.
9. Verify every uploaded image URL with `HEAD` or `GET`: status `200`, `content-type` starts with `image/`, and the URL is not local/server-only.

## Hard rules

- Do not use Xiaohongshu CDN hotlinks as rendered image URLs in the result. Upload copies first.
- Do not add downloaded reference images to the app server or serve them through repository `public/`, `/official`, `/replay-images`, or similar paths.
- Do not use generic lake/hotel/Unsplash/Wikimedia photos when the plan claims to be based on Xiaohongshu references.
- Do not paste search URLs or links with `xsec_token` into user-facing documents.
- If the itinerary names a concrete POI such as `月光码头` or `诚品书店`, include reference images for those named stops or explicitly state that you could not obtain them.

## Provenance row template

```md
![小红书参考图 1](https://durable-tos-or-asset-url/image-1.webp)

- 小红书笔记：<title>
- 清洁笔记链接：https://www.xiaohongshu.com/explore/<note_id>
- 清洁图片链接：https://sns-webpic.../...
- 上传后的图片：https://durable-tos-or-asset-url/image-1.webp
- 可见互动：<likes/favorites if available>
- 这张图证明什么：<one sentence tied to the final route>
- 对规划有用的信息：<signals separated by semicolon>
```

## Verification checklist

- [ ] `destination.images.length === destination.image_links.length` when source CTAs are expected.
- [ ] Every `destination.images[]` URL is a durable asset/TOS URL and returns an image.
- [ ] Every `destination.image_links[]` is a clean note/share URL.
- [ ] Process doc includes note title, note URL, clean source image URL, uploaded image URL, and planning signal.
- [ ] No local/server-only paths appear in rendered image fields.
