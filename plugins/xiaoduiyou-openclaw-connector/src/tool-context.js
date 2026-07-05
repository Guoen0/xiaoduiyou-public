import { AsyncLocalStorage } from "node:async_hooks";

const toolContext = new AsyncLocalStorage();
const RECENT_CONTEXT_TTL_MS = 30 * 60 * 1000;
let recentContext = null;
let recentContextAt = 0;

function rememberContext(context) {
  if (!context || typeof context !== "object") return context;
  if (context.sessionId || context.session_id || context.turnId || context.turn_id || context.documentId || context.document_id) {
    recentContext = { ...context };
    recentContextAt = Date.now();
  }
  return context;
}

export function runWithXiaoduiyouToolContext(context, fn) {
  return toolContext.run(rememberContext(context), fn);
}

export function activeXiaoduiyouToolContext() {
  const context = toolContext.getStore();
  if (!context) {
    throw new Error("Xiaoduiyou tool context is unavailable; document tools must run inside an active Xiaoduiyou turn");
  }
  return context;
}

export function maybeActiveXiaoduiyouToolContext() {
  const context = toolContext.getStore();
  if (context) return context;
  if (recentContext && Date.now() - recentContextAt <= RECENT_CONTEXT_TTL_MS) return { ...recentContext, recoveredFromRecentContext: true };
  return {};
}

export function queueXiaoduiyouDocumentAction(action) {
  const context = activeXiaoduiyouToolContext();
  if (!Array.isArray(context.documentActions)) {
    throw new Error("Xiaoduiyou document action queue is unavailable");
  }
  context.documentActions.push(action);
  return action;
}
