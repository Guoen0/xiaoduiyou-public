import { DEFAULT_ACCOUNT_ID, normalizeAccountId } from "openclaw/plugin-sdk/account-id";

const DEFAULT_POLL_INTERVAL_MS = 1_000;
const DEFAULT_POLL_TIMEOUT_MS = 30_000;
const DEFAULT_TURN_CONCURRENCY = 4;

export function listXiaoduiyouAccountIds(cfg) {
  const section = cfg.channels?.xiaoduiyou;
  const ids = new Set([DEFAULT_ACCOUNT_ID]);
  for (const id of Object.keys(section?.accounts ?? {})) ids.add(normalizeAccountId(id));
  return [...ids];
}

export function defaultXiaoduiyouAccountId(_cfg) {
  return DEFAULT_ACCOUNT_ID;
}

function mergedAccountConfig(cfg, accountId) {
  const section = cfg.channels?.xiaoduiyou ?? {};
  const account = section.accounts?.[accountId] ?? {};
  return { ...section, ...account };
}

export function resolveXiaoduiyouAccount(cfg, accountId) {
  const normalizedAccountId = normalizeAccountId(accountId);
  const merged = mergedAccountConfig(cfg, normalizedAccountId);
  const baseUrl = String(merged.baseUrl ?? "").trim().replace(/\/+$/, "");
  const connectionToken = String(merged.connectionToken ?? "").trim();

  return {
    accountId: normalizedAccountId,
    enabled: merged.enabled !== false,
    configured: Boolean(baseUrl && connectionToken),
    baseUrl,
    connectionToken,
    pollIntervalMs: Number(merged.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS),
    pollTimeoutMs: Number(merged.pollTimeoutMs ?? DEFAULT_POLL_TIMEOUT_MS),
    turnConcurrency: Math.max(1, Number(merged.turnConcurrency ?? DEFAULT_TURN_CONCURRENCY) || DEFAULT_TURN_CONCURRENCY),
    botUserId: String(merged.botUserId ?? "openclaw"),
    botDisplayName: String(merged.botDisplayName ?? "OpenClaw"),
    allowFrom: Array.isArray(merged.allowFrom) ? merged.allowFrom : ["*"],
  };
}
