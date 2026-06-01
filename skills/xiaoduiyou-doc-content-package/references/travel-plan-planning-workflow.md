# Travel-plan planning workflow

Use this when a connected Agent needs to produce a Xiaoduiyou travel-planning artifact. This is the planning workflow itself: identify constraints, research options, make one executable recommendation, and write the process document that proves the decision.

The visible result UI is not parsed from this process document. Rendered UI data belongs in `publish_notes.travel_plan.travel_plan`; see `references/travel-plan-result-template.md`.

## Output bar

A good travel plan should:

- make one decisive recommendation when the research supports it, rather than a vague activity menu;
- respect hard constraints such as no self-driving, toddler nap/food/exit needs, travel dates, weather/heat/crowds, and return logistics;
- use current evidence: map facts, train/ticket links, hotel/booking links, Xiaohongshu notes/images when useful;
- keep the visible result concise and executable: travel chain, hotel area, short itinerary, baby rhythm, food/supply fallback;
- avoid internal labels in user-visible copy, such as `模拟对话`, `官方案例`, `demo data`, `debug`, `UI模型`, `数据接口`, `关键利益点`, or `按要求`.

For toddler travel, the itinerary must have nap, food, and exit anchors. The plan should be easy to abandon or shorten without breaking the day.

## Planning steps

1. Restate the user's goal and hard constraints.
2. Screen candidate destinations/options. Reject options that violate constraints, especially return-risk, long transfer chains, car-only logistics, or weak toddler fallback.
3. Pick the strongest route and explain why it wins.
4. Gather evidence for the final route:
   - map facts and real coordinates;
   - station/transport time and ticket/search links;
   - hotel names, area logic, facilities, and booking/detail links;
   - POI images/reference notes when useful.
5. Build the structured result data in `publish_notes.travel_plan.travel_plan` using `references/travel-plan-result-template.md`.
6. Write `source_markdown` / process document using the chapter structure below.
7. Validate that process document, structured result data, and final visible copy agree.

## Process document purpose

The process document is a QA/evidence/editing surface. It should let a reviewer answer:

1. What did the user ask for?
2. What hard constraints were recognized?
3. Which destinations/options were screened in or out, and why?
4. What current evidence was used: Xiaohongshu notes, map facts, FlyAI/Fliggy hotel/train links, etc.?
5. What final itinerary and hotel stack came out of the research?
6. Which exact structured fields were migrated into the `travel_plan` UI data?

Keep this material in `source_markdown` and/or `block_json`. Do not put process headings inside visible result tabs.

## Recommended process document structure

```md
<title>一岁宝宝旅行规划</title>

# 一、需求对话
用户：端午节想带一岁宝宝去附近玩，不想开车，轻松一点。

# 二、识别出的关键约束
| 约束 | 识别结果 | 信息来源 |
| --- | --- | --- |
| 宝宝年龄 | 1 岁，午睡和撤退优先 | 用户/记忆/对话 |
| 交通 | 不自驾，优先高铁 + 短打车 | 对话 |
| 天数 | 两天一晚 | 对话/假期长度 |

# 三、方案筛选
| 方向 | 判断 | 原因 |
| --- | --- | --- |
| 苏州金鸡湖 | 推荐 | 短高铁、城市配套强、酒店和活动点距离近 |
| 崇明/横沙岛 | 不推荐 | 不自驾时返程风险高 |

# 四、参考图、来源与规划信号
![小红书参考图 1](https://durable-tos-or-asset-url/image-1.webp)

- 小红书笔记：苏州金鸡湖遛娃路线
- 清洁笔记链接：https://www.xiaohongshu.com/explore/<note_id>
- 清洁图片链接：https://sns-webpic.../...
- 上传后的图片：https://durable-tos-or-asset-url/image-1.webp
- 这张图证明什么：湖边短走和商场切换可行
- 对规划有用的信息：母婴室、厕所、补给、路线长度、排队/天气风险

# 五、日程安排
| 天数 | 时间 | 动作 | 执行说明 |
| --- | --- | --- | --- |
| D1 | 09:00 | 从家出门 | 先处理早饭、奶、尿布和备用衣物 |
| D1 | 15:30 | 月光码头—诚品—苏州中心短线 | 热、人多、风大就进商场 |

# 六、与规划匹配的酒店
| 酒店 | 定位 | 距离/位置 | 为什么匹配这条路线 | 飞猪链接 |
| --- | --- | --- | --- | --- |
| 苏州洲际酒店 | 路线首选 | 旺墩路288号，近诚品/月光码头 | 体量和亲子设施更稳 | https://a.feizhu.com/... |

# 七、迁移到旅行规划 UI 的字段
| UI 模块 | 数据字段 | 说明 |
| --- | --- | --- |
| 顶部图片 | destination.images + destination.image_links | 图片必须是 TOS/asset URL；链接必须一一对应 |
| 旅程时间 | main_map.points/routes/ticket_links | 使用真实坐标和飞猪车票链接 |
| 酒店选择 | hotel_map.hotels/scenic_point/scenic_points | 酒店与 POI 坐标已检查；酒店卡可点击 |
| 日程安排 | itinerary | 短、明确、能执行 |
```

## Writing rules

- Process text can be more detailed than the visible result, but still avoid dumping raw search noise.
- Use native Markdown headings/tables/images so Xiaoduiyou can preserve structure in BlockNote.
- Put uncertainty in the process doc, e.g. `FlyAI 当前只返回酒店级卡片/价位段，未返回具体房型库存。`
- Keep source URLs clean: Xiaohongshu note links should be `https://www.xiaohongshu.com/explore/<note_id>` or official share links; do not include `xsec_token`, `xsec_source`, search-session params, or login/risk URLs.
- Every image shown in the process doc must use a durable uploaded asset/TOS URL, not the original temporary CDN URL as the rendered image. Keep the original clean image URL as provenance text only.
- User-visible result copy should sound natural. Keep internal wording out of result fields.

## Result UI quality constraints to enforce through planning

- `ui_templates` includes `travel_plan`.
- `publish_notes.travel_plan.travel_plan` exists and matches the final planning decision.
- The first visible card is a fused decision card: title, tags, concise recommendation, relevant reference images, and a short destination explanation.
- Reference images are specific to the final route and show fully; avoid cropped key evidence.
- Source CTAs such as `小红书 ↗` should match the image order and not affect image layout.
- For toddler HSR/non-driving cases, show the travel-time chain near the top: home → rail station → destination station → hotel, plus total time.
- Use real map tiles/embeds and real `lng/lat`; visually verify roads/water/labels/copyright, not only JS success.
- Use separate map behavior for different purposes: travel-time map may show a route/polyline; hotel-selection map should show relative hotel/POI markers and should not force meaningless lines between unrelated points.
- Hotel cards must be concrete and clickable: hotel name, short reason, distance/area, and FlyAI/Fliggy detail URL when available.

## Final checklist

- [ ] The process document explains the decision and evidence.
- [ ] The selected destination, hotels, links, images, itinerary, and caveats agree across process document and structured result data.
- [ ] `destination.images` and `destination.image_links` lengths/order match when source CTAs are expected.
- [ ] Every image URL returns `200` and `content-type: image/*`.
- [ ] No local/server-only paths appear in images or process image blocks.
- [ ] Map points and hotel/POI coordinates are real and checked.
- [ ] Booking/ticket links are clickable and provider-returned when possible.
- [ ] Stale rejected options do not appear as final recommendations.
