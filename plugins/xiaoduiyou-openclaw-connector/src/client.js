export const XIAODUIYOU_CONNECTOR_VERSION = "2026.6.3.3";

async function readJsonResponse(response, path) {
  const rawText = await response.text();
  let payload = {};
  try {
    payload = rawText ? JSON.parse(rawText) : {};
  } catch (error) {
    if (!response.ok) throw new Error(rawText || `Xiaoduiyou request failed: ${response.status}`);
    throw new Error(`Xiaoduiyou returned non-JSON response for ${path}`);
  }
  if (!response.ok) {
    const errorCode = payload?.error || rawText || `HTTP_${response.status}`;
    const error = new Error(errorCode);
    error.status = response.status;
    error.code = payload?.error;
    throw error;
  }
  return payload;
}

async function requestJson(account, path, options = {}) {
  const response = await fetch(`${account.baseUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${account.connectionToken}`,
      "content-type": "application/json",
      "X-XDY-Connector-Version": XIAODUIYOU_CONNECTOR_VERSION,
      "X-XDY-Connector-Provider": "openclaw",
      ...(options.headers ?? {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  return await readJsonResponse(response, path);
}

function growthDiaryQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function getXiaoduiyouGrowthDiary(account, params = {}) {
  return await requestJson(account, `/api/growth-diary${growthDiaryQuery(params)}`);
}

export async function patchXiaoduiyouGrowthDiary(account, payload) {
  return await requestJson(account, "/api/growth-diary", {
    method: "PATCH",
    body: payload,
  });
}

export async function pollXiaoduiyouTurn(account, signal) {
  try {
    const payload = await requestJson(account, "/api/agent/turns/pending", { signal });
    return payload.turn ?? null;
  } catch (error) {
    if (error?.status === 404 || error?.code === "NO_PENDING_TURN") return null;
    throw error;
  }
}

export async function postXiaoduiyouProgress(account, turnId, progress) {
  return await requestJson(account, `/api/agent/turns/${encodeURIComponent(turnId)}/events`, {
    method: "POST",
    body: { progress },
  });
}

export async function postXiaoduiyouToolProgress(account, turnId, toolProgress) {
  return await requestJson(account, `/api/agent/turns/${encodeURIComponent(turnId)}/events`, {
    method: "POST",
    body: { tool_progress: toolProgress },
  });
}

export async function completeXiaoduiyouTurn(account, turnId, payload) {
  return await requestJson(account, `/api/agent/turns/${encodeURIComponent(turnId)}/callback`, {
    method: "POST",
    body: payload,
  });
}

export async function failXiaoduiyouTurn(account, turnId, error) {
  return await requestJson(account, `/api/agent/turns/${encodeURIComponent(turnId)}/failure`, {
    method: "POST",
    body: { error: error instanceof Error ? error.message : String(error) },
  });
}

function looksLikeToolProgress(content) {
  const stripped = String(content ?? "").trim();
  if (!stripped) return false;
  const hasToolShape = [': "', "...", "(", "×"].some((marker) => stripped.includes(marker));
  if (!hasToolShape) return false;
  return [
    "🔍", "🔎", "📖", "📚", "🛠", "⚙", "✅", "💻", "🌐", "📝", "📁", "🔧",
    "📋", "🐍", "🎨", "👁", "🧠",
  ].some((prefix) => stripped.startsWith(prefix));
}

export function sessionMessagePayloadFromText(text) {
  const raw = String(text ?? "").trim();
  if (!raw) return { text: "" };
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      if ("message_type" in parsed || "tool_progress" in parsed || "image_attachments" in parsed || "image_urls" in parsed || "text" in parsed || "content" in parsed || "detail" in parsed) {
        return parsed;
      }
    }
  } catch {
    // Plain text message, not a visual-card envelope.
  }
  if (looksLikeToolProgress(raw)) return { message_type: "tool_progress", tool_progress: raw };
  return { text: raw };
}

export async function sendXiaoduiyouSessionMessage(account, sessionId, text) {
  return await requestJson(account, `/api/agent/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: "POST",
    body: sessionMessagePayloadFromText(text),
  });
}
