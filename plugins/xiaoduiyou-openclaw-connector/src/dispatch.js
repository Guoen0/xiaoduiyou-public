export function textFromPayload(payload) {
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

export function isOpenClawLifecycleProgress(text, info = {}) {
  const stripped = String(text ?? "").trim();
  if (!stripped) return false;
  const lower = stripped.toLowerCase();
  if (lower.includes("auto-compaction complete")) return true;
  if (lower.includes("preflight compression")) return true;
  if (lower.includes("context compaction complete")) return true;
  if (lower.includes("compaction complete") && stripped.startsWith("🧹")) return true;
  if (lower.includes("compression complete") && stripped.startsWith("🧹")) return true;
  const kind = String(info?.kind ?? "").toLowerCase();
  if ((kind === "status" || kind === "progress" || kind === "system") && /\b(compaction|compression)\b/i.test(stripped)) return true;
  return false;
}

export function isOpenClawHiddenLifecycleProgress(text, info = {}) {
  const stripped = String(text ?? "").trim();
  if (!stripped) return false;
  if (/^🧭\s*New session:\s*[0-9a-f-]{8,}$/i.test(stripped)) return true;
  const kind = String(info?.kind ?? "").toLowerCase();
  return (kind === "status" || kind === "progress" || kind === "system")
    && /^New session:\s*[0-9a-f-]{8,}$/i.test(stripped);
}

export function xiaoduiyouDispatchDeliveryKind(text, info = {}) {
  if (!String(text ?? "").trim()) return "empty";
  if (isOpenClawHiddenLifecycleProgress(text, info)) return "empty";
  if (isOpenClawLifecycleProgress(text, info)) return "tool_progress";
  if (info?.kind === "tool") return "tool_progress";
  if (info?.kind === "final") return "final";
  return "progress";
}
