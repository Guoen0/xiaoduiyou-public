import { createChatChannelPlugin, buildChannelOutboundSessionRoute } from "openclaw/plugin-sdk/channel-core";
import {
  defaultXiaoduiyouAccountId,
  listXiaoduiyouAccountIds,
  resolveXiaoduiyouAccount,
} from "./accounts.js";
import { isXiaoduiyouAuthError, sendXiaoduiyouSessionMessage, watchXiaoduiyouTurns } from "./client.js";
import { handleXiaoduiyouTurn } from "./inbound.js";
import { getXiaoduiyouRuntime } from "./runtime.js";

export const xiaoduiyouPlugin = createChatChannelPlugin({
  base: {
    id: "xiaoduiyou",
    meta: {
      id: "xiaoduiyou",
            label: "Xiaoduiyou",
            selectionLabel: "Xiaoduiyou",
            blurb: "Stream Xiaoduiyou pending Agent turns and dispatch them to OpenClaw.",
    },
    capabilities: { chatTypes: ["direct"] },
    reload: { configPrefixes: ["channels.xiaoduiyou"] },
    config: {
      listAccountIds: listXiaoduiyouAccountIds,
      resolveAccount: resolveXiaoduiyouAccount,
      defaultAccountId: defaultXiaoduiyouAccountId,
      isConfigured: (account) => Boolean(account?.configured),
      describeAccount: (account) => ({
        accountId: account?.accountId ?? "default",
        enabled: account?.enabled !== false,
        configured: Boolean(account?.configured),
        tokenSource: account?.connectionToken ? "config" : "missing",
      }),
    },
    messaging: {
      normalizeTarget: (target) => target.trim() || undefined,
      targetResolver: {
        looksLikeId: (target) => /^session:.+/.test(target.trim()),
        hint: "session:<xiaoduiyou-session-id>",
      },
      resolveOutboundSessionRoute: ({ cfg, agentId, accountId, target }) => buildChannelOutboundSessionRoute({
        cfg,
        agentId,
        channel: "xiaoduiyou",
        accountId,
        peer: { kind: "direct", id: target },
        chatType: "direct",
        from: `xiaoduiyou:${accountId ?? "default"}`,
        to: target,
      }),
    },
    gateway: {
      startAccount: async (ctx) => {
        const account = ctx.account;
        if (!account.configured) throw new Error("Xiaoduiyou connector requires baseUrl and connectionToken");
        const activeTurns = new Set();
        const startTurn = (turn) => {
          const task = handleXiaoduiyouTurn({ account, config: ctx.cfg, turn, runtime: getXiaoduiyouRuntime() })
            .catch((error) => {
              console.error("Xiaoduiyou turn failed", { accountId: account.accountId, turnId: turn?.turn_id, error });
            })
            .finally(() => {
              activeTurns.delete(task);
            });
          activeTurns.add(task);
        };

        ctx.setStatus({ accountId: account.accountId, running: true, connected: true, configured: true });
        let authFailed = false;
        try {
          await watchXiaoduiyouTurns(account, ctx.abortSignal, async (turn) => {
            while (activeTurns.size >= account.turnConcurrency && !ctx.abortSignal.aborted) {
              await Promise.race(activeTurns);
            }
            if (!ctx.abortSignal.aborted) startTurn(turn);
          });
        } catch (error) {
          if (isXiaoduiyouAuthError(error)) {
            console.error("Xiaoduiyou authentication failed; stopping account turn stream", { accountId: account.accountId });
            authFailed = true;
            ctx.setStatus({ accountId: account.accountId, running: false, connected: false, configured: true, error: "UNAUTHENTICATED" });
          } else {
            throw error;
          }
        }
        if (activeTurns.size > 0) await Promise.allSettled(activeTurns);
        ctx.setStatus(authFailed
          ? { accountId: account.accountId, running: false, connected: false, configured: true, error: "UNAUTHENTICATED" }
          : { accountId: account.accountId, running: false });
      },
    },
  },
  outbound: {
    base: { deliveryMode: "direct" },
    attachedResults: {
      channel: "xiaoduiyou",
      sendText: async ({ cfg, accountId, to, text }) => {
        const account = resolveXiaoduiyouAccount(cfg, accountId);
        if (!account.configured) throw new Error("Xiaoduiyou connector requires baseUrl and connectionToken");
        const sessionId = String(to ?? "").trim().replace(/^session:/, "");
        if (!sessionId) throw new Error("Xiaoduiyou send target must be session:<xiaoduiyou-session-id>");
        const result = await sendXiaoduiyouSessionMessage(account, sessionId, text);
        return { to, messageId: result.message_id ?? result.event?.event_id ?? `xiaoduiyou:${Date.now()}`, text };
      },
    },
  },
});
