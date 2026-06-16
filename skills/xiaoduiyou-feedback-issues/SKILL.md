---
name: xiaoduiyou-feedback-issues
description: Public-feedback-handler-only workflow for triaging Xiaoduiyou feedback sessions and filing xiaoduiyou-public GitHub issues. Use only when the running Agent is the configured Xiaoduiyou public feedback Agent/profile, runtime context explicitly shows `session_purpose: feedback`, or a maintainer asks to triage public feedback. Do not use for ordinary Xiaoduiyou chat, general feedback wording, bug reports, or normal user issue discussion.
---

# Xiaoduiyou Feedback Issues

Use this only for Xiaoduiyou public feedback-handler turns. This skill is for triage and durable issue creation, not ordinary Xiaoduiyou chat, content packages, or Growth Diary.

## Activation gate

Load this skill only if at least one condition is true:

- The current Hermes profile, SOUL, memory, or runtime config explicitly identifies the running Agent as the Xiaoduiyou public feedback handler.
- The active Xiaoduiyou runtime/session context explicitly includes `session_purpose: feedback`.
- A maintainer/developer session explicitly asks to triage public feedback into `Guoen0/xiaoduiyou-public` issues.

Do not load this skill for normal Agent conversations merely because the user says `反馈`, `bug`, `问题`, `issue`, or `建议`. Ordinary agents should answer in the active chat or use `xiaoduiyou-im` unless the explicit public-feedback context above is present.

## What this profile does

- The public Hermes profile is the feedback handler for Xiaoduiyou.
- Feedback sessions are hidden/protected product sessions and do not appear as normal delivery channels.
- The user-facing feedback page sends normal Xiaoduiyou messages, often with screenshots.
- The agent must decide whether to answer the user directly or create a GitHub issue in `Guoen0/xiaoduiyou-public`.

## First decision

Classify the report before creating anything:

1. **User-Agent usage issue**: the user is asking how to use an Agent, why an Agent answered poorly, how to phrase a request, how to configure/edit an Agent, or what prompt to use.
   - Reply in the feedback thread with a concise explanation, workaround, or prompt.
   - Do not create a GitHub issue unless there is evidence of a platform bug.
2. **Platform/product issue**: UI broken, message not sending, connection/feedback channel failure, upload failure, protected-session behavior wrong, data loss, wrong session routing, missing expected control, recurring product friction, or a concrete product request.
   - Create or update a GitHub issue in `Guoen0/xiaoduiyou-public`.
   - Reply with the issue link and a short next-step summary.
3. **Insufficient evidence**: cannot tell whether it is usage or platform.
   - Ask for one concrete missing item: expected result, actual result, page/screen, reproduction step, or screenshot.

## Issue creation rules

- Confirm repo context before writing: target repo is `Guoen0/xiaoduiyou-public`.
- In the local public Hermes profile, use `.env` `XIAODUIYOU_PUBLIC_GITHUB_TOKEN`; do not use global `gh` auth or a personal default token.
- Prefer the bundled script:

```bash
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-feedback-issues/scripts/create_public_feedback_issue.py" \
  --title "反馈页发送后无响应" \
  --body-file /tmp/xdy-feedback-issue.md
```

- If `HERMES_SKILL_HOME` is not set, use `${HERMES_HOME:-$HOME/.hermes}`.
- Do not include credentials, tokens, cookies, private local paths, or raw account secrets in issue bodies.
- Include screenshots only as already-public HTTPS asset URLs or sanitized links from the feedback turn.
- Search recent open issues first when practical; update an existing matching issue instead of duplicating obvious repeats.

## Issue body template

```md
## 反馈摘要
[one-paragraph summary]

## 用户原文
[quote or concise paraphrase]

## 判断
- 类型：平台问题 / 产品请求
- 严重度：P0 / P1 / P2 / P3
- 依据：[why this is not just usage guidance]

## 复现信息
1. [step]
2. [step]

## 实际结果
[what happened]

## 期望结果
[what should happen]

## 附件
[screenshot URLs if any]

## 处理建议
[smallest useful next action]
```

## Reply style

- For usage issues: answer directly and give the exact prompt or navigation path, for example `设置 -> 我的家 -> Agent -> 编辑`.
- For filed platform issues: state `已记录为 #N` and summarize what was captured.
- For unclear issues: ask one focused follow-up, not a long questionnaire.
