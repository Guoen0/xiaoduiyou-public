# Search Routing Notes

Public search APIs index public web pages. They work well for news, documentation, official pages, public articles, and general source-backed fact checking.

They do not reliably search inside closed or semi-closed platforms:

| Platform | Public web search coverage | Correct route |
|---|---|---|
| Douyin | Poor; mostly third-party pages about Douyin | TikHub |
| Xiaohongshu | Poor; login wall and anti-bot behavior | TikHub |
| Weibo | Poor for full post/search data | Future TikHub route after endpoint verification |
| Bilibili | Partial for public video pages, weak for comments/search context | TikHub when platform-internal search is needed |
| Taobao/JD | Poor; crawler blocking and anti-hotlinking | Product-specific workflow, not generic search |

Use public web search for questions about a platform, and TikHub for content inside a platform.

Examples:

- "小红书最近流行的亲子餐厅笔记" -> TikHub Xiaohongshu note search.
- "小红书是什么公司" -> public web search.
- "抖音热搜榜" -> TikHub Douyin hot search.
- "抖音电商规则变化" -> public web search, preferably official sources.
- "微博里搜某个话题" -> explain that Weibo endpoint is not enabled yet; do not pretend public web search is equivalent.
