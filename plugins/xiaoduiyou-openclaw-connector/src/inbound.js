import {
  runPreparedInboundReplyTurn,
} from "openclaw/plugin-sdk/inbound-reply-dispatch";
import { createChannelReplyPipeline } from "openclaw/plugin-sdk/channel-reply-pipeline";
import {
  completeXiaoduiyouTurn,
  failXiaoduiyouTurn,
  postXiaoduiyouProgress,
  postXiaoduiyouToolProgress,
} from "./client.js";

function textFromPayload(payload) {
  if (!payload) return "";
  if (typeof payload === "string") return payload;
  if (typeof payload === "object") {
    if (typeof payload.text === "string") return payload.text;
    if (typeof payload.content === "string") return payload.content;
    if (Array.isArray(payload.content)) {
      return payload.content.map((item) => item?.text ?? "").filter(Boolean).join("\n");
    }
  }
  return String(payload);
}

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

async function deliverXiaoduiyouDispatchPayload(account, turnId, payload, info, dispatchState) {
  const text = textFromPayload(payload).trim();
  if (!text) return;
  if (info?.kind === "tool") {
    await postXiaoduiyouToolProgress(account, turnId, text);
    return;
  }
  if (info?.kind === "final") {
    dispatchState.finalCompleted = true;
    await completeXiaoduiyouTurn(account, turnId, { progress: text });
    return;
  }

  // Some OpenClaw dispatcher paths can emit the assistant's final text as a
  // non-final visible payload after tools/background process output. Keep every
  // non-tool visible payload as a completion fallback so Xiaoduiyou does not
  // remain stuck with only progress/tool bubbles when no explicit final arrives.
  appendFinalFallbackText(dispatchState, text, info?.kind);
  await postXiaoduiyouProgress(account, turnId, text);
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
  const agentNotice = String(turn.agent_notice ?? "").trim();
  const agentMessage = [
    `发送者：${senderName}（${senderId}）`,
    screenNote,
    agentNotice,
    userMessage,
  ].filter(Boolean).join("\n\n");
  const imageUrls = normalizeImageUrls(turn.image_urls, turn.content_parts);
  const dispatchState = { finalCompleted: false, fallbackBlocks: [] };
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
        replyOptions: { onModelSelected },
      }),
    });
    if (!dispatchState.finalCompleted && dispatchState.fallbackBlocks.length > 0) {
      const fallbackText = finalFallbackText(dispatchState);
      if (fallbackText) {
        dispatchState.finalCompleted = true;
        await completeXiaoduiyouTurn(account, turnId, { progress: fallbackText });
      }
    }
  } catch (error) {
    await failXiaoduiyouTurn(account, turnId, error);
    throw error;
  }
}
