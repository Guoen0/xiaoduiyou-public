#!/usr/bin/env python3
"""TikHub API 社交媒体搜索脚本

支持搜索抖音、小红书等平台的站内内容。
需要 TikHub API Key。

用法:
    python3 tikhub_search.py "关键词" --platform douyin|xiaohongshu|bilibili --type video|note|user --count 10
"""

import argparse
import json
import os
import sys

import requests

# TikHub API 配置
TIKHUB_API_BASE = "https://api.tikhub.io"

def _load_env_value(paths, key):
    """Read a simple KEY=value file without echoing secrets."""
    for raw_path in paths:
        path = os.path.expanduser(raw_path)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    name, value = line.split("=", 1)
                    if name.strip() == key:
                        return value.strip().strip("\"'")
        except OSError:
            continue
    return ""


# The dedicated private file is authoritative across local and public Hermes.
TIKHUB_API_KEY = (
    _load_env_value(["~/.hermes/.tikhub_env"], "TIKHUB_API_KEY")
    or os.getenv("TIKHUB_API_KEY", "")
    or _load_env_value(["~/.hermes/.env"], "TIKHUB_API_KEY")
)

# 平台配置
PLATFORMS = {
    "douyin": {
        "name": "抖音",
        "search_video": "/api/v1/douyin/app/v3/fetch_video_search_result",
        "search_user": "/api/v1/douyin/app/v3/fetch_user_search_result",
        "hot_search": "/api/v1/douyin/web/fetch_hot_search_result",
    },
    "xiaohongshu": {
        "name": "小红书",
        # TikHub V5.3.2 (2026-06-22): note/user search moved from removed web_v3 routes to app_v2.
        "search_note": "/api/v1/xiaohongshu/app_v2/search_notes",
        "search_user": "/api/v1/xiaohongshu/app_v2/search_users",
        "search_suggest": "/api/v1/xiaohongshu/web_v3/fetch_search_suggest",
    },
    "bilibili": {
        "name": "B站",
        "search_video": "/api/v1/bilibili/web/search/all",
    },
}


def check_api_key():
    """检查 API Key 是否配置"""
    if not TIKHUB_API_KEY:
        print("Error: 未配置 TikHub API Key。", file=sys.stderr)
        print("\n请按以下步骤操作：", file=sys.stderr)
        print("1. 前往 https://tikhub.io/ 注册账号", file=sys.stderr)
        print("2. 使用邀请码 1wRL8eQk 注册可获得 $2 额度", file=sys.stderr)
        print("3. 每日签到可获取免费额度", file=sys.stderr)
        print("4. 在控制台获取 API Key", file=sys.stderr)
        print("5. 设置环境变量: export TIKHUB_API_KEY=your_key", file=sys.stderr)
        print("   或写入 ~/.hermes/.tikhub_env 文件: TIKHUB_API_KEY=your_key", file=sys.stderr)
        sys.exit(1)
    return True


def search_content(query, platform, content_type="video", count=10):
    """搜索内容"""
    check_api_key()

    if platform not in PLATFORMS:
        print(f"Error: 不支持的平台 '{platform}'", file=sys.stderr)
        print(f"支持的平台: {', '.join(PLATFORMS.keys())}", file=sys.stderr)
        sys.exit(1)

    config = PLATFORMS[platform]
    headers = {
        'Authorization': f'Bearer {TIKHUB_API_KEY}',
        'Accept': 'application/json'
    }

    # 选择端点
    if content_type == "user" and "search_user" in config:
        endpoint = config["search_user"]
        params = {"keyword": query, "page": 1, "page_size": count}
    elif content_type == "hot":
        endpoint = config.get("hot_search", "")
        params = {}
    elif content_type == "note":
        # 小红书笔记搜索
        endpoint = config.get("search_note", "")
        params = {"keyword": query, "page": 1, "page_size": count}
    else:
        # 默认搜索视频/笔记
        endpoint = config.get("search_video", config.get("search_note", ""))
        params = {"keyword": query, "page": 1, "page_size": count}

    if not endpoint:
        print(f"Error: 平台 '{platform}' 不支持 '{content_type}' 搜索", file=sys.stderr)
        sys.exit(1)

    url = f"{TIKHUB_API_BASE}{endpoint}"

    print(f"平台: {config['name']}")
    print(f"搜索: {query}")
    print(f"类型: {content_type}")
    print(f"数量: {count}")
    print("-" * 50)

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 200:
                print("\n✅ 搜索成功！\n")
                # 解析并显示结果
                display_results(data, platform, content_type)
            else:
                print(f"\n❌ API 错误: {data.get('message', 'Unknown error')}")
        elif resp.status_code == 402:
            print("\n❌ 余额不足")
            print("该端点需要付费额度，请前往 https://tikhub.io/ 充值")
            print("或每日签到获取免费额度")
        elif resp.status_code == 401:
            print("\n❌ API Key 无效")
            print("请检查 TIKHUB_API_KEY 是否正确")
        else:
            print(f"\n❌ 请求失败: {resp.status_code}")
            print(resp.text[:500])

    except requests.exceptions.Timeout:
        print("\n❌ 请求超时，请重试")
    except requests.exceptions.ConnectionError:
        print("\n❌ 网络连接失败")
    except Exception as e:
        print(f"\n❌ 错误: {e}")


def display_results(data, platform, content_type):
    """显示搜索结果"""
    result_data = data.get('data', {})

    if platform == "douyin":
        if content_type == "hot":
            # 显示热搜
            trending_list = result_data.get('data', {}).get('trending_list', [])
            print(f"=== 抖音热搜榜 (共 {len(trending_list)} 条) ===\n")
            for i, item in enumerate(trending_list[:10], 1):
                print(f"[{i}] {item.get('word', 'N/A')}")
                print(f"    视频数: {item.get('video_count', 'N/A')} | 讨论数: {item.get('discuss_video_count', 'N/A')}")
                print()
        else:
            # 显示视频/用户搜索结果
            print(json.dumps(result_data, indent=2, ensure_ascii=False)[:2000])

    elif platform == "xiaohongshu":
        if content_type == "note":
            # app_v2 shape: data.data.items[].note; older web_v3 used noteCard.
            payload = result_data.get('data', {})
            items = payload.get('items', []) if isinstance(payload, dict) else []
            notes = []
            for item in items:
                note = item.get('note') or item.get('noteCard') or {}
                if note and note.get('id'):
                    notes.append(note)
            print(f"=== 小红书笔记搜索结果 (共 {len(notes)} 条) ===\n")
            for i, note in enumerate(notes[:count if 'count' in globals() else 10], 1):
                title = note.get('title') or note.get('displayTitle') or '无标题'
                user = note.get('user', {})
                author = user.get('nickname', '未知')
                note_type = note.get('type', 'normal')
                likes = note.get('liked_count', note.get('interactInfo', {}).get('likedCount', '0'))
                collects = note.get('collected_count', note.get('interactInfo', {}).get('collectedCount', '0'))
                comments = note.get('comments_count', note.get('interactInfo', {}).get('commentCount', '0'))
                images = note.get('images_list') or []
                cover = (images[0].get('url_size_large') if images else '') or note.get('cover', {}).get('urlDefault', '')
                note_id = note.get('id', '')

                print(f"[{i}] {title}")
                print(f"    作者: {author}")
                print(f"    类型: {note_type}")
                print(f"    点赞: {likes} | 收藏: {collects} | 评论: {comments}")
                if cover:
                    print(f"    封面: {cover}")
                print(f"    笔记ID: {note_id}")
                print()
        else:
            print(json.dumps(result_data, indent=2, ensure_ascii=False)[:2000])

    else:
        # 其他平台直接显示
        print(json.dumps(result_data, indent=2, ensure_ascii=False)[:2000])


def main():
    parser = argparse.ArgumentParser(description="TikHub 社交媒体搜索")
    parser.add_argument("query", nargs="?", default="", help="搜索关键词")
    parser.add_argument("--platform", choices=list(PLATFORMS.keys()), required=True,
                       help="搜索平台")
    parser.add_argument("--type", choices=["video", "note", "user", "hot"],
                       default="video", help="搜索类型")
    parser.add_argument("--count", type=int, default=10, help="返回条数")

    args = parser.parse_args()

    if args.type == "hot":
        args.query = "hot_search"

    search_content(args.query, args.platform, args.type, args.count)


if __name__ == "__main__":
    main()
