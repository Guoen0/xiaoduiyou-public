#!/usr/bin/env python3
"""Create a Xiaoduiyou public feedback issue using the profile-specific token."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_REPO = "Guoen0/xiaoduiyou-public"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Xiaoduiyou public feedback GitHub issue.")
    parser.add_argument("--title", required=True, help="Issue title without the [反馈] prefix.")
    parser.add_argument("--body-file", required=True, help="Markdown file containing the issue body.")
    parser.add_argument("--repo", default=os.environ.get("XDY_FEEDBACK_REPO", DEFAULT_REPO), help="owner/repo target.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request payload without calling GitHub.")
    return parser.parse_args()


def read_body(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def main() -> int:
    args = parse_args()
    repo = args.repo.replace("https://github.com/", "").removesuffix(".git").strip("/")
    if "/" not in repo:
        print(f"Invalid repo: {args.repo}", file=sys.stderr)
        return 2

    body = read_body(args.body_file)
    title = args.title.strip()
    if not title or not body:
        print("Title and body are required.", file=sys.stderr)
        return 2

    payload = {"title": f"[反馈] {title[:120]}", "body": body[:12000]}
    if args.dry_run:
        print(json.dumps({"repo": repo, **payload}, ensure_ascii=False, indent=2))
        return 0

    token = os.environ.get("XIAODUIYOU_PUBLIC_GITHUB_TOKEN", "").strip()
    if not token:
        print("Missing XIAODUIYOU_PUBLIC_GITHUB_TOKEN in this Hermes profile environment.", file=sys.stderr)
        return 3

    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "xiaoduiyou-public-feedback-skill",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"GitHub issue creation failed: HTTP {exc.code} {detail}", file=sys.stderr)
        return 4
    except urllib.error.URLError as exc:
        print(f"GitHub issue creation failed: {exc}", file=sys.stderr)
        return 4

    print(json.dumps({"issue_number": data.get("number"), "issue_url": data.get("html_url")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
