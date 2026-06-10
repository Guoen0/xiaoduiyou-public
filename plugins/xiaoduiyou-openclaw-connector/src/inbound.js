import {
  runPreparedInboundReplyTurn,
} from "openclaw/plugin-sdk/inbound-reply-dispatch";
import { createChannelReplyPipeline } from "openclaw/plugin-sdk/channel-reply-pipeline";
import { callGatewayTool } from "openclaw/plugin-sdk/agent-harness-runtime";
import {
  buildXiaoduiyouExecApprovalRequest,
  normalizeOpenClawExecApprovalPayload,
  openClawDecisionFromXiaoduiyouChoice,
  waitForXiaoduiyouInteractiveDecision,
} from "./approval.js";
import {
  createXiaoduiyouInteractiveRequest,
  getXiaoduiyouInteractiveRequest,
  completeXiaoduiyouTurn,
  failXiaoduiyouTurn,
  postXiaoduiyouProgress,
  postXiaoduiyouToolProgress,
} from "./client.js";
import { textFromPayload, xiaoduiyouDispatchDeliveryKind } from "./dispatch.js";
import { runWithXiaoduiyouToolContext } from "./tool-context.js";

function normalizeImageUrls(imageUrls, contentParts) {
  const urls = [];
  if (Array.isArray(imageUrls)) {
    for (const url of imageUrls) {
      const normalized = String(url ?? "").trim();
      if (/^https?:\/\//i.test(normalized)) urls.push(normalized);
    }
  }
  if (urls.length > 0) return [...new Set(urls)];
  if (Array.isArray(contentParts)) {
    for (const part of contentParts) {
      if (part?.type !== "image_url") continue;
      const normalized = String(part?.image_url?.url ?? "").trim();
      if (/^https?:\/\//i.test(normalized)) urls.push(normalized);
    }
  }
  return [...new Set(urls)];
}

function formatScreenContext(screenContext) {
  if (!screenContext || typeof screenContext !== "object") return "";
  const summary = String(screenContext.summary ?? "").trim();
  if (!summary) return "";
  const lines = ["当前屏幕：", summary];
  const details = [];
  for (const [label, key] of [["页面", "active_tab"], ["标题", "title"], ["内容包", "artifact_id"], ["文档", "document_id"]]) {
    const value = String(screenContext[key] ?? "").trim();
    if (value) details.push(`${label}：${value}`);
  }
  if (details.length > 0) lines.push(details.join("；"));
  const visibleText = String(screenContext.visible_text ?? "").trim();
  if (visibleText) lines.push(`可见内容摘要：${visibleText}`);
  return lines.join("\n");
}

function formatAgentRuntimeContext(turn) {
  const context = turn?.agent_runtime_context ?? turn?.runtime_context;
  if (!context || typeof context !== "object") return "";
  const origin = String(context.origin ?? context.base_url ?? context.api_origin ?? "").trim();
  if (!origin) return "";
  const lines = ["小队友平台上下文：", "platform=xiaoduiyou", `origin=${origin}`];
  for (const [label, key] of [
    ["environment", "environment"],
    ["home_id", "home_id"],
    ["family_id", "family_id"],
    ["session_id", "session_id"],
    ["session_scope", "session_scope"],
    ["session_purpose", "session_purpose"],
    ["surface", "surface"],
  ]) {
    const value = String(context[key] ?? "").trim();
    if (value) lines.push(`${label}=${value}`);
  }
  const sender = context.sender && typeof context.sender === "object" ? context.sender : {};
  const senderBits = [];
  for (const key of ["display_name", "account_id", "role"]) {
    const value = String(sender[key] ?? "").trim();
    if (value) senderBits.push(`${key}=${value}`);
  }
  if (senderBits.length > 0) lines.push(`sender: ${senderBits.join(", ")}`);
  const auth = context.auth && typeof context.auth === "object" ? context.auth : {};
  const provider = String(auth.provider ?? "").trim();
  if (provider) lines.push(`auth.provider=${provider}; auth.mode=connection_token_bound`);
  lines.push("本次 Xiaoduiyou API/成长日记/资产/频道写入必须使用上述 origin 与当前连接 token；禁止改用本地 config、生产/测试默认地址、维护者 URL 或浏览器里打开的其他小队友页面。");
  return lines.join("\n");
}

function appendFinalFallbackText(dispatchState, text, kind) {
  if (!text) return;
  if (dispatchState.finalCompleted) return;
  const normalizedKind = kind ?? "unknown";
  dispatchState.fallbackBlocks.push({ kind: normalizedKind, text });
}

function finalFallbackText(dispatchState) {
  return dispatchState.fallbackBlocks
    .map((block) => block.text)
    .filter(Boolean)
    .join("\n\n")
    .trim();
}

function completePayloadWithDocumentActions(payload, dispatchState) {
  if (!Array.isArray(dispatchState.documentActions) || dispatchState.documentActions.length === 0) return payload;
  const actions = dispatchState.documentActions.splice(0);
  return { ...payload, document_actions: actions };
}

function isXiaoduiyouCommandTurn(turn) {
  return turn?.input_type === "command" || String(turn?.user_message ?? "").trim().startsWith("/");
}

function commandNameFromTurn(turn) {
  const explicit = String(turn?.command_name ?? "").trim();
  if (explicit) return explicit;
  const match = String(turn?.user_message ?? "").trim().match(/^(\/[^\s]+)/);
  return match?.[1] ?? undefined;
}

function commandNoReplyFallbackText(turn) {
  const name = commandNameFromTurn(turn) ?? "该命令";
  return `⚠️ ${name} 没有返回可显示结果；已结束本轮。请检查 OpenClaw 命令权限或网关日志。`;
}

async function deliverXiaoduiyouDispatchPayload(account, turnId, payload, info, dispatchState) {
  const text = textFromPayload(payload).trim();
  const deliveryKind = xiaoduiyouDispatchDeliveryKind(text, info);
  if (deliveryKind === "empty") return;
  if (deliveryKind === "tool_progress") {
    await postXiaoduiyouToolProgress(account, turnId, text);
    return;
  }
  if (deliveryKind === "final") {
    dispatchState.finalCompleted = true;
    await completeXiaoduiyouTurn(account, turnId, completePayloadWithDocumentActions({ progress: text }, dispatchState));
    return;
  }

  // Some OpenClaw dispatcher paths can emit the assistant's final text as a
  // non-final visible payload after tools/background process output. Keep every
  // non-tool visible payload as a completion fallback so Xiaoduiyou does not
  // remain stuck with only progress/tool bubbles when no explicit final arrives.
  appendFinalFallbackText(dispatchState, text, info?.kind);
  await postXiaoduiyouProgress(account, turnId, text);
}

async function maybeHandleOpenClawExecApproval(account, turn, sessionId, sessionKey, payload, signal) {
  const approval = normalizeOpenClawExecApprovalPayload(payload);
  if (!approval) return false;
  const created = await createXiaoduiyouInteractiveRequest(account, buildXiaoduiyouExecApprovalRequest({
    approval,
    sessionId,
    turnId: turn.turn_id,
    sessionKey,
  }));
  const requestId = created?.request?.request_id ?? created?.request_id;
  if (!requestId) return false;
  const choice = await waitForXiaoduiyouInteractiveDecision({
    account,
    requestId,
    getRequest: getXiaoduiyouInteractiveRequest,
    signal,
  });
  const decision = openClawDecisionFromXiaoduiyouChoice(choice);
  if (!decision) return true;
  await callGatewayTool("exec.approval.resolve", {}, {
    id: approval.approvalId,
    decision,
    resolvedBy: `xiaoduiyou:${turn.sender_id ?? turn.session_id ?? "user"}`,
  });
  return true;
}

function withXiaoduiyouVerboseConfig(config) {
  return {
    ...config,
    agents: {
      ...config?.agents,
      defaults: {
        ...config?.agents?.defaults,
        verboseDefault: "on",
      },
    },
  };
}

function withXiaoduiyouSessionRouteConfig(config) {
  return {
    ...config,
    session: {
      ...config?.session,
      dmScope: "per-account-channel-peer",
    },
  };
}

function xiaoduiyouRouteAccountId(turn, account) {
  return String(turn.account_id ?? turn.home_id ?? account?.accountId ?? "default").trim() || "default";
}

export async function handleXiaoduiyouTurn({ account, config, turn, runtime }) {
  const turnId = turn.turn_id;
  const sessionId = turn.session_id;
  const userMessage = turn.user_message ?? turn.content ?? "";
  const senderName = String(turn.sender_display_name ?? turn.sender_name ?? turn.display_name ?? turn.sender_email ?? "Xiaoduiyou user");
  const senderId = String(turn.sender_account_id ?? turn.sender_id ?? turn.account_id ?? "xiaoduiyou-user");
  const screenNote = formatScreenContext(turn.screen_context);
  const runtimeContextNote = formatAgentRuntimeContext(turn);
  const agentNotice = String(turn.agent_notice ?? "").trim();
  const documentToolNote = [
    "Xiaoduiyou connector tools are available.",
    "For Growth Diary tasks, use skill xiaoduiyou-growth-diary, call xiaoduiyou_growth_diary_get first, then xiaoduiyou_growth_diary_patch for writes; do not search local files/env/config for connection_token and do not call /api/growth-diary manually from terminal.",
    "For Growth Diary event time, use explicit user wording first; if absent, use this Xiaoduiyou turn's Timestamp/created_at, never the Agent runtime clock or an invented time.",
    "Agent-created records must include date as YYYY-MM-DD and occurred_at as YYYY-MM-DD HH:mm:ss with matching dates; short times like 19:20 are invalid and will be rejected.",
    "For ordinary chat, answer normally and do not call document tools.",
    "When the user explicitly asks to create, update, append to, or delete a document, call the appropriate xiaoduiyou document tool exactly once before your final reply.",
    "For content packages, choose UI templates with ui_templates (currently xiaohongshu and/or moments) and fill matching fields.publish_notes.<template> with final result data; process block_json/source_markdown should stay process-only.",
    "Do not merely promise to create a document.",
  ].join(" ");
  const agentMessage = [
    `发送者：${senderName}（${senderId}）`,
    screenNote,
    runtimeContextNote,
    agentNotice,
    documentToolNote,
    userMessage,
  ].filter(Boolean).join("\n\n");
  const imageUrls = normalizeImageUrls(turn.image_urls, turn.content_parts);
  const dispatchState = { finalCompleted: false, fallbackBlocks: [], documentActions: [] };
  const commandTurn = isXiaoduiyouCommandTurn(turn);
  const commandName = commandNameFromTurn(turn);
  const commandOwnerAllowFrom = commandTurn ? [senderId] : undefined;
  const commandGatewayScopes = commandTurn ? ["operator.admin"] : undefined;
  const routeAccountId = xiaoduiyouRouteAccountId(turn, account);
  const routeConfig = withXiaoduiyouSessionRouteConfig(config);
  const route = runtime.channel.routing.resolveAgentRoute({
    cfg: routeConfig,
    channel: "xiaoduiyou",
    accountId: routeAccountId,
    peer: { kind: "direct", id: `session:${sessionId}` },
  });
  const storePath = runtime.channel.session.resolveStorePath(routeConfig.session?.store, {
    agentId: route.agentId,
  });
  const previousTimestamp = runtime.channel.session.readSessionUpdatedAt({
    storePath,
    sessionKey: route.sessionKey,
  });
  const body = runtime.channel.reply.formatAgentEnvelope({
    channel: "Xiaoduiyou",
    from: senderName,
    timestamp: turn.created_at,
    previousTimestamp,
    envelope: runtime.channel.reply.resolveEnvelopeFormatOptions(config),
    body: userMessage,
  });
  const ctxPayload = runtime.channel.reply.finalizeInboundContext({
    Body: body,
    BodyForAgent: agentMessage,
    RawBody: userMessage,
    CommandBody: userMessage,
    CommandSource: commandTurn ? "text" : undefined,
    CommandTurn: commandTurn ? { source: "text", authorized: true, commandName, body: userMessage } : undefined,
    OwnerAllowFrom: commandOwnerAllowFrom,
    GatewayClientScopes: commandGatewayScopes,
    From: `xiaoduiyou:${sessionId}`,
    To: `session:${sessionId}`,
    SessionKey: route.sessionKey,
    AccountId: route.accountId ?? account.accountId,
    ChatType: "direct",
    ConversationLabel: turn.session_title ?? sessionId,
    SenderName: senderName,
    SenderDisplayName: senderName,
    SenderId: senderId,
    FromName: senderName,
    AuthorName: senderName,
    UserDisplayName: senderName,
    Provider: "xiaoduiyou",
    Surface: "xiaoduiyou",
    MessageSid: turnId,
    MessageSidFull: turnId,
    Timestamp: turn.created_at,
    OriginatingChannel: "xiaoduiyou",
    OriginatingTo: `session:${sessionId}`,
    CommandAuthorized: true,
    MediaUrls: imageUrls,
    MediaTypes: imageUrls.map(() => "image/*"),
  });
  const verboseConfig = withXiaoduiyouVerboseConfig(routeConfig);

  try {
    const { onModelSelected, ...replyPipeline } = createChannelReplyPipeline({
      cfg: verboseConfig,
      agentId: route.agentId,
      channel: "xiaoduiyou",
      accountId: routeAccountId,
    });
    await runWithXiaoduiyouToolContext({
      accountId: routeAccountId,
      sessionId,
      turnId,
      documentActions: dispatchState.documentActions,
    }, async () => {
      await runPreparedInboundReplyTurn({
        channel: "xiaoduiyou",
        accountId: routeAccountId,
        routeSessionKey: route.sessionKey,
        storePath,
        ctxPayload,
        recordInboundSession: runtime.channel.session.recordInboundSession,
        record: {
          onRecordError: (error) => { throw error; },
        },
        runDispatch: async () => await runtime.channel.reply.dispatchReplyWithBufferedBlockDispatcher({
          ctx: ctxPayload,
          cfg: verboseConfig,
          dispatcherOptions: {
            ...replyPipeline,
            deliver: async (payload, info) => {
              await deliverXiaoduiyouDispatchPayload(account, turnId, payload, info, dispatchState);
            },
            onError: (error) => { throw error; },
          },
          replyOptions: {
            onModelSelected,
            onToolResult: async (payload) => {
              await maybeHandleOpenClawExecApproval(account, turn, sessionId, route.sessionKey, payload, undefined);
            },
            sourceReplyDeliveryMode: "automatic",
          },
        }),
      });
    });
    if (!dispatchState.finalCompleted && dispatchState.fallbackBlocks.length > 0) {
      const fallbackText = finalFallbackText(dispatchState);
      if (fallbackText) {
        dispatchState.finalCompleted = true;
        await completeXiaoduiyouTurn(account, turnId, completePayloadWithDocumentActions({ progress: fallbackText }, dispatchState));
      }
    }
    if (!dispatchState.finalCompleted && commandTurn) {
      dispatchState.finalCompleted = true;
      await completeXiaoduiyouTurn(account, turnId, completePayloadWithDocumentActions({ progress: commandNoReplyFallbackText(turn) }, dispatchState));
    }
  } catch (error) {
    await failXiaoduiyouTurn(account, turnId, error);
    throw error;
  }
}
