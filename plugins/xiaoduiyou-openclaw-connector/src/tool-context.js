import { AsyncLocalStorage } from "node:async_hooks";

const toolContext = new AsyncLocalStorage();

export function runWithXiaoduiyouToolContext(context, fn) {
  return toolContext.run(context, fn);
}

export function activeXiaoduiyouToolContext() {
  const context = toolContext.getStore();
  if (!context) {
    throw new Error("Xiaoduiyou tool context is unavailable; document tools must run inside an active Xiaoduiyou turn");
  }
  return context;
}

export function queueXiaoduiyouDocumentAction(action) {
  const context = activeXiaoduiyouToolContext();
  if (!Array.isArray(context.documentActions)) {
    throw new Error("Xiaoduiyou document action queue is unavailable");
  }
  context.documentActions.push(action);
  return action;
}
