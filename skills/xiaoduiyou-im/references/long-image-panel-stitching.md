# Long-image panel stitching for Xiaoduiyou chat

Use this when a Xiaoduiyou user asks to generate a long poster/长图 for WeChat, Xiaohongshu, family sharing, or similar chat delivery, especially when the image backend may not reliably generate very tall images.

## Pattern

1. Plan the long image as several short panels first.
   - Prefer 4–6 panels for a WeChat share poster.
   - Each panel should have one job: hook, pain point, product explanation, scenarios, CTA.
   - Keep copy short enough to remain readable after WeChat compression.
2. If prompt-based generation is uncertain for a very tall asset, render a deterministic draft locally with PIL/HTML/SVG.
   - Canvas example: 1080px wide, 1200–1400px per panel.
   - Use a known-good Simplified Chinese font. On macOS, `STHeiti Medium.ttc` / `STHeiti Light.ttc` have rendered Chinese reliably.
   - Draw each panel as its own visual section, then stitch vertically into one image.
3. QA the actual stitched output visually before delivery.
   - Check Chinese glyphs are not tofu boxes.
   - Check panel-specific elements use the correct y-offset; QR-code placeholders and decorative grids can accidentally draw at the top if the panel offset is missing.
   - Check bottom captions do not overlap cards or illustrations.
   - Check line wrapping, margins, and final CTA readability.
4. Upload the final approved local image to Xiaoduiyou TOS when a durable URL is useful, then HEAD-verify `200 image/*`.
5. Deliver inside the active Xiaoduiyou turn using `xiaoduiyou_im_send` with an `input_image` part. Do not return `MEDIA:` or a local path.

## WeChat friend-group poster structure

A working 5-panel structure for 小队友 friend-group acquisition:

1. **Hook panel** — family scene + one sharp line, e.g. “家里有娃以后，最累的其实是‘记不住’”.
2. **Scattered-info panel** — show 微信 / 备忘录 / 相册 / 脑子里 as separate fragments; emphasize information is scattered across the family.
3. **Product-explanation panel** — describe 小队友 as “家庭里的宝宝记录员”; show chat input → organized family record.
4. **Use-case panel** — three short cards: 喂养 / 生病时间线 / 家庭协作.
5. **CTA panel** — keep it soft, like a friend recommendation; include QR/small-program placeholder and a clear action.

## Copy tone

For Xiaoduiyou acquisition posters, avoid SaaS/AI feature language as the lead. Start from a concrete family burden, then introduce 小队友 as a helper. The poster should feel like a useful recommendation in a friends group, not a product landing page.

Good framing:

- “家里有娃以后，最累的其实是‘记不住’。”
- “很多家庭不是没人管孩子，是信息一直散着。”
- “小队友，就是一个家庭里的宝宝记录员。”
- “小队友不会替你当爸妈。它只是帮你把那些容易忘、容易漏、容易吵起来的小事，先接住。”

Avoid overly technical leads such as “AI 育儿助手”, “智能中枢”, “全流程闭环”, or homepage-style feature grids as the first screen.
