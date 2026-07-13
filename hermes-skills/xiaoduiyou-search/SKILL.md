---
name: xiaoduiyou-search
version: 1.0.0
author: xiaoduiyou-agent
description: Xiaoduiyou public Agent search router. Use for current web facts, source-backed answers, public web/image search, and closed-platform social search such as Douyin, Xiaohongshu, and Bilibili. Routes public web search to Volcengine/Byted Web Search and platform-internal social search to TikHub.
---

# Xiaoduiyou Search

Use this skill as the single Xiaoduiyou search entrypoint. Do not load or expose separate search skills for the same turn unless debugging this skill.

For Xiaoduiyou search tasks, do not use built-in Hermes `web` or `browser` toolsets directly. This skill owns provider selection: use the scripts below first, then OpenCLI only as the documented fallback.

## Routing

| User intent | Route | Script |
|---|---|---|
| Public web facts, news, policies, prices, product reviews, documentation, source-backed answers | Web search | `scripts/web_search.py` |
| Images from the public web | Web image search | `scripts/web_search.py --type image` |
| Douyin hot list, Douyin video/user search | TikHub social search | `scripts/tikhub_search.py --platform douyin` |
| Xiaohongshu note/user search | TikHub social search | `scripts/tikhub_search.py --platform xiaohongshu` |
| Bilibili platform-internal content | TikHub social search | `scripts/tikhub_search.py --platform bilibili` |
| General explanation of why ordinary search cannot see social content | Answer from `references/search-routing.md` | No script unless user also asks to search |
| Search failed but a specific OpenCLI site/adapter may cover it | OpenCLI adapter fallback | Load `smart-search`; use only after web/TikHub routes cannot answer |
| Source is visible only in a live browser, or the user asks to inspect an opened/logged-in page | OpenCLI browser fallback | Load `opencli-usage`, then `opencli-browser`; use only after web/TikHub routes cannot answer |

## Hard Boundaries

- Public web search cannot reliably search inside closed or semi-closed platforms such as Douyin, Xiaohongshu, Weibo, Taobao, and JD.
- For social-platform content, do not use public web search as the primary source. Use TikHub first.
- `social-media-search` legacy providers such as Newrank, Qiangua, Chanmama, Huitun, and Kaogujia are not active production routes here. Treat them as future integration candidates only.
- TikHub Kuaishou and Weibo routes are not enabled until real search endpoints are implemented and verified in `scripts/tikhub_search.py`.
- OpenCLI is a last-resort fallback, not a primary search provider. Use it only after `web_search.py` and `tikhub_search.py` cannot retrieve the needed content, or when the user explicitly asks to inspect a live/logged-in browser page.
- For OpenCLI adapter selection, use `skills/_private/smart-search`. For live browser inspection, use `skills/_private/opencli-usage` and `skills/_private/opencli-browser`.
- Keep OpenCLI as separate skills under `skills/_private/opencli-*` and `skills/_private/smart-search`; do not merge its commands or docs into this skill.
- Do not use local Chrome/Xiaohongshu AppleScript skills for Xiaoduiyou/public-agent social search unless the user explicitly asks to inspect Guoen's already-open local Chrome session. Xiaohongshu search goes to TikHub first.
- Do not use generic diligence/research skills that make OpenCLI the primary web-search route. For Xiaoduiyou, OpenCLI stays behind Web Search and TikHub.
- If the user is in Xiaoduiyou IM and wants visual cards or image delivery, search here first, then use `xiaoduiyou-im` for final delivery.
- Do not place third-party image URLs from e-commerce or social platforms directly into durable Xiaoduiyou image cards. Use text cards, source links, or the Xiaoduiyou asset flow documented in `xiaoduiyou-im`.

## Web Search

Use for current facts, verification, sources, recommendations, and any topic whose answer may have changed.

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python3" \
  "$HERMES_SKILL_HOME/skills/_private/xiaoduiyou-search/scripts/web_search.py" "搜索词" --count 10
```

Useful options:

- `--type web|image`
- `--time-range OneDay|OneWeek|OneMonth|OneYear|YYYY-MM-DD..YYYY-MM-DD`
- `--auth-level 1` for authoritative sources
- `--query-rewrite` for natural-language or low-recall queries

Credential behavior:

- Run the script first; do not preflight credentials.
- If it returns missing or invalid credentials, ask for a Volcengine Web Search key from the official Search Infinity console.
- Supported env keys include `WEB_SEARCH_API_KEY`, or Volcengine AK/SK as implemented by the script.

## TikHub Social Search

Use for platform-internal social content.

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python3" \
  "$HERMES_SKILL_HOME/skills/_private/xiaoduiyou-search/scripts/tikhub_search.py" \
  "关键词" --platform xiaohongshu --type note --count 10
```

Examples:

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python3" \
  "$HERMES_SKILL_HOME/skills/_private/xiaoduiyou-search/scripts/tikhub_search.py" \
  --platform douyin --type hot --count 10

"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python3" \
  "$HERMES_SKILL_HOME/skills/_private/xiaoduiyou-search/scripts/tikhub_search.py" \
  "亲子餐厅" --platform xiaohongshu --type note --count 10

"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/python3" \
  "$HERMES_SKILL_HOME/skills/_private/xiaoduiyou-search/scripts/tikhub_search.py" \
  "绘本推荐" --platform douyin --type video --count 10
```

Credential behavior:

- Authoritative credential file: `~/.hermes/.tikhub_env`, containing `TIKHUB_API_KEY`.
- If that file is missing or empty, the script falls back to the process environment and then `~/.hermes/.env`.
- Keep `.tikhub_env` outside repositories and synchronize it directly between trusted environments.
- If TikHub returns 402, explain that the endpoint requires TikHub paid balance; free endpoints such as Douyin hot search may still work.

## Result Handling

1. Read all returned results before answering.
2. Prefer concise synthesis over dumping raw JSON.
3. Include source names or links when useful.
4. State uncertainty when search results are sparse, contradictory, or behind platform paywalls.
5. For social search, preserve platform metadata such as title, author, interaction counts, note/video IDs, and source URL when present.
6. If OpenCLI fallback was used, say that the answer came from live browser inspection rather than search API results.

## References

- `references/search-routing.md`: why the router separates public web search from closed-platform social search.
- `references/legacy-social-providers.md`: legacy third-party social-data providers and why they are not active routes.
