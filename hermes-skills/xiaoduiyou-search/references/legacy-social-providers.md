# Legacy Social Provider Notes

The old `social-media-search` skill listed Newrank, Qiangua, Chanmama, Huitun, and Kaogujia as possible social-data sources. Its local scripts only emit demo/mock results and do not call production APIs.

Do not route production Xiaoduiyou searches to those scripts.

Keep this list as future integration candidates:

| Provider | Likely coverage |
|---|---|
| Newrank / 新红数据 | Xiaohongshu notes, creators, brand data |
| Qiangua / 千瓜 | Xiaohongshu notes, creators, brand analysis |
| Chanmama / 蝉妈妈 | Douyin creators, products, live commerce |
| Huitun / 灰豚 | Douyin/Xiaohongshu creator search |
| Kaogujia / 考古加 | Short-video commerce data |

Before enabling one of these providers, replace demo scripts with real API clients, document credential names, response shape, limits, and fallback behavior.
