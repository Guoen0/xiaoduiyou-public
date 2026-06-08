const OPENCLAW_DECISION_BY_CHOICE = {
  once: "allow-once",
  always: "allow-always",
  deny: "deny",
  cancel: "deny",
};

const XIAODUIYOU_ACTION_BY_DECISION = {
  "allow-once": "once",
  "allow-always": "always",
  deny: "deny",
};

function isRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function readString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function readNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function compactArray(values) {
  return values.filter((value, index, array) => value && array.indexOf(value) === index);
}

function readExecApprovalCandidate(payload) {
  if (!isRecord(payload)) return null;
  const channelData = isRecord(payload.channelData) ? payload.channelData : null;
  if (isRecord(channelData?.execApproval)) return channelData.execApproval;
  const details = isRecord(payload.details) ? payload.details : null;
  if (details?.status === "approval-pending") return details;
  if (payload.status === "approval-pending") return payload;
  return null;
}

export function normalizeOpenClawExecApprovalPayload(payload) {
  const details = readExecApprovalCandidate(payload);
  if (!details) return null;
  const approvalId = readString(details.approvalId) ?? readString(details.approval_id) ?? readString(details.id);
  const approvalSlug = readString(details.approvalSlug) ?? readString(details.approval_slug) ?? readString(details.slug);
  const command = readString(details.command);
  if (!approvalId || !command) return null;
  const allowedDecisions = Array.isArray(details.allowedDecisions)
    ? details.allowedDecisions.filter((decision) => decision === "allow-once" || decision === "allow-always" || decision === "deny")
    : ["allow-once", "allow-always", "deny"];
  const actions = compactArray(allowedDecisions.map((decision) => XIAODUIYOU_ACTION_BY_DECISION[decision]));
  const expiresAtMs = readNumber(details.expiresAtMs);
  const timeoutSeconds = expiresAtMs ? Math.max(15, Math.min(3600, Math.ceil((expiresAtMs - Date.now()) / 1000))) : 300;
  const cwd = readString(details.cwd);
  const warningText = readString(details.warningText) ?? readString(details.warning_text);
  return {
    approvalId,
    approvalSlug,
    command,
    cwd,
    warningText,
    host: readString(details.host),
    nodeId: readString(details.nodeId) ?? readString(details.node_id),
    actions: actions.length > 0 ? actions : ["once", "always", "deny"],
    timeoutSeconds,
  };
}

export function buildXiaoduiyouExecApprovalRequest({ approval, sessionId, turnId, sessionKey }) {
  const messageLines = compactArray([
    "OpenClaw 请求执行命令，需要授权后继续。",
    approval.cwd ? `工作目录：${approval.cwd}` : "",
    approval.warningText,
  ]);
  return {
    session_id: sessionId,
    turn_id: turnId,
    kind: "exec_approval",
    title: "需要授权执行命令",
    message: messageLines.join("\n"),
    command: approval.command,
    reason: approval.warningText,
    session_key: sessionKey,
    actions: approval.actions,
    timeout_seconds: approval.timeoutSeconds,
  };
}

export function openClawDecisionFromXiaoduiyouChoice(choice) {
  return OPENCLAW_DECISION_BY_CHOICE[choice] ?? null;
}

export async function waitForXiaoduiyouInteractiveDecision({ account, requestId, getRequest, signal, pollIntervalMs = 1000 }) {
  while (!signal?.aborted) {
    const payload = await getRequest(account, requestId);
    const request = payload?.request ?? payload;
    if (request?.status === "resolved") return request.choice ?? null;
    if (request?.status === "expired") return "deny";
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, pollIntervalMs);
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
    });
  }
  return null;
}
