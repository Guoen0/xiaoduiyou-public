# Xiaoduiyou `travel_plan` result template

Use this reference when a connected Agent needs to create a Xiaoduiyou travel-planning content package. The key point: the visible result page is not parsed from Markdown. It renders only when the artifact selects the `travel_plan` UI template and provides structured `publish_notes.travel_plan.travel_plan` data.

## Minimal creation shape

When using the Xiaoduiyou document tool, pass `ui_templates: ["travel_plan"]` and a matching `fields.publish_notes.travel_plan` object:

```json
{
  "title": "一岁宝宝旅行规划",
  "ui_templates": ["travel_plan"],
  "fields": {
    "publish_notes": {
      "travel_plan": {
        "platform": "travel_plan",
        "label": "旅行规划",
        "title": "一岁宝宝两天一晚旅行规划",
        "body": "短高铁到金鸡湖，住湖畔走一条低强度亲子线。",
        "images": ["https://.../image-1.webp"],
        "travel_plan": { "...": "see schema below" }
      }
    },
    "source_markdown": "# 一、需求对话\n..."
  }
}
```

When completing a Hermes/Xiaoduiyou turn directly, the same fields belong under the artifact:

```json
{
  "artifact": {
    "schema": "xdy.artifact_blocks.v1",
    "artifact_id": "art_travel_plan_xxx",
    "version_id": "ver_travel_plan_001",
    "blocks": {
      "title": "一岁宝宝旅行规划",
      "body": "短高铁到金鸡湖，住湖畔走一条低强度亲子线。",
      "generated_images": ["https://.../image-1.webp"],
      "source_markdown": "# 一、需求对话\n...",
      "ui_templates": ["travel_plan"],
      "publish_notes": {
        "travel_plan": {
          "platform": "travel_plan",
          "label": "旅行规划",
          "title": "一岁宝宝两天一晚旅行规划",
          "body": "短高铁到金鸡湖，住湖畔走一条低强度亲子线。",
          "images": ["https://.../image-1.webp"],
          "travel_plan": { "...": "see schema below" }
        }
      },
      "visual_direction": [],
      "image_order": [],
      "hashtags": [],
      "reply_drafts": [],
      "compliance_notes": []
    }
  }
}
```

If `ui_templates` does not include `travel_plan`, the travel-planning UI will not render even when the data exists.

## `travel_plan` data schema

```ts
type TravelPlanResult = {
  title: string;
  subtitle: string; // tags separated by ｜, e.g. "上海出发｜不自驾｜轻松优先"
  conclusion: string; // concise human sentence, not an internal requirement label
  origin: { name: string; note: string };
  destination: {
    name: string;
    city: string;
    distance_from_origin: string;
    why_go: string[]; // reasoning/proof points; may be hidden or used by future UI
    images: string[]; // durable public URLs only, usually TOS/Xiaoduiyou asset URLs
    image_links?: string[]; // one-to-one source/provenance links for images, e.g. Xiaohongshu notes
    highlights: Array<{
      name: string;
      description: string;
      duration: string;
      baby_fit: string;
    }>;
  };
  main_map: {
    title: string; // polished polished outputs usually use "旅程时间"
    summary: string;
    points: TravelPlanPoint[];
    routes: Array<{ from: string; to: string; mode: string; duration: string }>;
    ticket_links?: Array<{ label: string; url: string; note?: string }>;
  };
  hotel_map: {
    title: string;
    summary: string;
    scenic_point: TravelMapPoint; // the main POI/hotel-area anchor
    scenic_points?: TravelMapPoint[]; // extra POIs, e.g. 月光码头、诚品生活苏州
    hotels: Array<{
      name: string;
      distance_to_scenic: string;
      visual: string;
      facilities: string[];
      image: string; // durable public URL or platform-returned hotel image URL
      x: number; y: number; // legacy decorative coordinates; still fill for compatibility
      lng: number; lat: number; // real map coordinates; required for map rendering
      rank: string;
      fliggy_url: string; // or another explicit booking/detail/search URL
    }>;
  };
  candidate_decisions: Array<{ name: string; decision: string; reason: string }>;
  itinerary: Array<{
    day: string;
    title: string;
    items: Array<{ time: string; title: string; detail: string }>;
  }>;
  baby_rhythm: Array<{ phase: string; principle: string; reason: string }>;
  food_supply: { principle: string; notes: string[] };
};

type TravelPlanPoint = {
  label: string;
  x: number; y: number;
  lng: number; lat: number;
  kind?: 'origin' | 'station' | 'poi' | 'hotel';
};

type TravelMapPoint = { label: string; x: number; y: number; lng: number; lat: number };
```

## Field-by-field rendering notes

- `subtitle`: the current UI turns it into small tags, deduplicated and capped. Use short tags, not sentence fragments.
- `destination.images`: rendered in the top gallery. These must be durable public image URLs. Do not use `/tmp`, `/Users`, `MEDIA:`, `/public`, `/official`, `/replay-images`, or repository/server-only static paths.
- `destination.image_links`: if provided, each image gets a bottom-right source CTA such as `小红书 ↗`. The array length and order should match `destination.images`.
- `main_map.points` + `main_map.routes`: render the origin-to-destination time/map section. Use real `lng/lat`; `kind` controls marker labels such as 起/站/玩.
- `main_map.ticket_links`: rendered at the bottom of the journey-time card. Use FlyAI/Fliggy returned `jumpUrl` when available.
- `hotel_map.hotels`: renders hotel cards and hotel markers. Cards should have real hotel names and clickable `fliggy_url`/detail URLs.
- `hotel_map.scenic_point` and `hotel_map.scenic_points`: render POI markers in the hotel-selection map. Use checked real coordinates; do not invent decorative locations. The hotel-selection map is for relative positions, so do not force route lines between hotels and POIs.
- `itinerary`: keep it short and executable. For toddler plans, include departure time and return-arrival milestones, but avoid long packing lists in the visible result.
- `baby_rhythm`: small support cards. Keep it concise.

## Recommended polished result defaults

- Top card: one fused decision card with title, tags, image gallery, and a short explanation.
- `main_map.title`: `旅程时间`.
- `hotel_map` visible section title: `酒店选择` in the UI; do not duplicate this in copy-heavy text.
- Hotel card CTA: a short bottom-right phrase such as `点击去飞猪查看 ↗`.
- Destination explanation should sound like normal product copy. Never paste internal instructions such as “关键利益点”, “按要求”, “UI模型”, “数据接口”, or “成品示例” into user-visible copy.

## Minimal valid example

```json
{
  "title": "一岁宝宝两天一晚旅行规划",
  "subtitle": "上海出发｜不自驾｜轻松优先",
  "conclusion": "短高铁到金鸡湖，住湖畔走一条低强度亲子线。",
  "origin": { "name": "上海市区", "note": "实际以用户所在地到虹桥通勤时间修正。" },
  "destination": {
    "name": "苏州金鸡湖片区",
    "city": "苏州",
    "distance_from_origin": "上海虹桥 → 苏州园区站约 25–35 分钟；站点到湖东酒店约 10–20 分钟车程",
    "why_go": ["短高铁", "酒店和活动点集中", "午睡和撤退方便"],
    "images": ["https://<xiaoduiyou-asset-host>/path/image-1.webp"],
    "image_links": ["https://www.xiaohongshu.com/explore/<note_id>"],
    "highlights": []
  },
  "main_map": {
    "title": "旅程时间",
    "summary": "短打车 + 短高铁 + 短打车，不把一岁宝宝放进复杂换乘里。",
    "points": [
      { "label": "上海虹桥", "x": 14, "y": 64, "lng": 121.318, "lat": 31.194, "kind": "origin" },
      { "label": "苏州园区站", "x": 62, "y": 45, "lng": 120.706, "lat": 31.342, "kind": "station" },
      { "label": "金鸡湖", "x": 78, "y": 36, "lng": 120.714, "lat": 31.313, "kind": "poi" }
    ],
    "routes": [
      { "from": "家", "to": "上海虹桥", "mode": "打车", "duration": "20–30 分钟" },
      { "from": "上海虹桥", "to": "苏州园区站", "mode": "高铁", "duration": "25–35 分钟" },
      { "from": "苏州园区站", "to": "湖东酒店", "mode": "打车", "duration": "10–20 分钟" },
      { "from": "总计", "to": "到湖东酒店", "mode": "合计", "duration": "约 55–85 分钟" }
    ],
    "ticket_links": [{ "label": "飞猪查高铁票", "url": "https://a.feizhu.com/..." }]
  },
  "hotel_map": {
    "title": "酒店和景点距离",
    "summary": "酒店按路线反推：离诚品/月光码头/苏州中心近，能中午回房午睡。",
    "scenic_point": { "label": "金鸡湖湖东步道", "x": 56, "y": 42, "lng": 120.714, "lat": 31.313 },
    "scenic_points": [
      { "label": "月光码头", "x": 50, "y": 35, "lng": 120.7056, "lat": 31.3263 },
      { "label": "诚品生活苏州", "x": 51, "y": 45, "lng": 120.7068, "lat": 31.3212 }
    ],
    "hotels": [{
      "name": "苏州洲际酒店",
      "distance_to_scenic": "飞猪显示旺墩路288号，近诚品/月光码头",
      "visual": "酒店体量和亲子设施更稳。",
      "facilities": ["飞猪价位段¥1xxx", "儿童乐园", "近诚品"],
      "image": "https://.../hotel.jpg",
      "x": 48, "y": 40, "lng": 120.706, "lat": 31.322,
      "rank": "路线首选",
      "fliggy_url": "https://a.feizhu.com/..."
    }]
  },
  "candidate_decisions": [{ "name": "苏州金鸡湖", "decision": "推荐", "reason": "短高铁、城市配套强、酒店和活动点距离近。" }],
  "itinerary": [{ "day": "D1", "title": "到苏州后只走一条短线", "items": [{ "time": "09:00", "title": "从家出门", "detail": "先处理早饭、奶、尿布和备用衣物。" }] }],
  "baby_rhythm": [{ "phase": "中午", "principle": "午睡优先", "reason": "旅行崩盘通常从午睡被破坏开始。" }],
  "food_supply": { "principle": "离酒店近、出餐快、能放推车。", "notes": ["不排队。"] }
}
```

## Verification checklist

- [ ] `ui_templates` includes exactly the intended templates and includes `travel_plan` for the travel UI.
- [ ] `publish_notes.travel_plan.travel_plan` exists and matches this schema.
- [ ] `destination.images` and `destination.image_links` lengths/order match when provenance CTAs are expected.
- [ ] Every image URL returns `200` and `content-type: image/*`.
- [ ] No local/server-only paths appear in images or process image blocks.
- [ ] Map points and hotel/POI coordinates are real and checked.
- [ ] Booking/ticket links are clickable and platform-returned when possible.
- [ ] Visible copy does not contain internal instruction wording.
