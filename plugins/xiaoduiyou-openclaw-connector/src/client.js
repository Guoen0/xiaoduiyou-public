import crypto from "node:crypto";
import net from "node:net";
import tls from "node:tls";
import { once } from "node:events";

export const XIAODUIYOU_CONNECTOR_VERSION = "2026.7.3.1";
const WEBSOCKET_RETRY_MS = 3_000;
const WEBSOCKET_IDLE_TIMEOUT_MS = 15_000;

function sleep(ms, signal) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

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

function compactQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function getXiaoduiyouGrowthDiary(account, params = {}) {
  return await requestJson(account, `/api/growth-diary${compactQuery(params)}`);
}

export async function patchXiaoduiyouGrowthDiary(account, payload) {
  return await requestJson(account, "/api/growth-diary", {
    method: "PATCH",
    body: payload,
  });
}

export async function getXiaoduiyouChild(account, params = {}) {
  return await requestJson(account, `/api/child${compactQuery(params)}`);
}

export async function patchXiaoduiyouChild(account, payload, params = {}) {
  return await requestJson(account, `/api/child${compactQuery(params)}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function getXiaoduiyouDocument(account, params = {}) {
  const documentId = String(params.document_id ?? "").trim();
  const sessionId = String(params.session_id ?? "").trim();
  const query = compactQuery({
    view: params.view || "summary",
    field: params.field,
    start: params.start,
    block_limit: params.block_limit,
    char_limit: params.char_limit,
  });
  if (documentId) return await requestJson(account, `/api/docs/${encodeURIComponent(documentId)}${query}`);
  if (sessionId) return await requestJson(account, `/api/sessions/${encodeURIComponent(sessionId)}/document${query}`);
  throw new Error("xiaoduiyou_documents_get requires document_id or an active Xiaoduiyou session");
}

export async function updateXiaoduiyouDocument(account, documentId, payload) {
  return await requestJson(account, `/api/docs/${encodeURIComponent(documentId)}`, {
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

function pendingTurnsWebSocketUrl(account) {
  const url = new URL(account.baseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/agent/turns/pending";
  url.search = "";
  return url;
}

class RawWebSocket {
  constructor(socket) {
    this.socket = socket;
    this.buffer = Buffer.alloc(0);
    this.waiters = [];
    this.closedError = null;
    socket.on("data", (chunk) => {
      this.buffer = Buffer.concat([this.buffer, chunk]);
      this.flushWaiters();
    });
    socket.on("close", () => {
      this.closedError = new Error("WEBSOCKET_CLOSED");
      this.flushWaiters();
    });
    socket.on("error", (error) => {
      this.closedError = error;
      this.flushWaiters();
    });
  }

  flushWaiters() {
    const pending = this.waiters.splice(0);
    for (const waiter of pending) waiter();
  }

  async waitForBytes(length, timeoutMs) {
    while (this.buffer.length < length) {
      if (this.closedError) throw this.closedError;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          this.waiters = this.waiters.filter((waiter) => waiter !== done);
          reject(new Error("WEBSOCKET_READ_TIMEOUT"));
        }, timeoutMs);
        const done = () => {
          clearTimeout(timer);
          resolve();
        };
        this.waiters.push(done);
      });
    }
  }

  async readBytes(length, timeoutMs = WEBSOCKET_IDLE_TIMEOUT_MS) {
    await this.waitForBytes(length, timeoutMs);
    const value = this.buffer.subarray(0, length);
    this.buffer = this.buffer.subarray(length);
    return value;
  }

  async readText() {
    const header = await this.readBytes(2);
    const opcode = header[0] & 0x0f;
    let length = header[1] & 0x7f;
    if (length === 126) length = (await this.readBytes(2)).readUInt16BE(0);
    else if (length === 127) {
      const extended = await this.readBytes(8);
      length = Number(extended.readBigUInt64BE(0));
    }
    const payload = length ? await this.readBytes(length) : Buffer.alloc(0);
    if (opcode === 8) throw new Error("WEBSOCKET_CLOSED");
    if (opcode === 9) {
      this.writeFrame(0x0a, payload);
      return null;
    }
    if (opcode !== 1) return null;
    return payload.toString("utf8");
  }

  writeFrame(opcode, payload = Buffer.alloc(0)) {
    const mask = crypto.randomBytes(4);
    const first = 0x80 | opcode;
    let header;
    if (payload.length < 126) header = Buffer.from([first, 0x80 | payload.length]);
    else if (payload.length < 65536) {
      header = Buffer.alloc(4);
      header[0] = first;
      header[1] = 0x80 | 126;
      header.writeUInt16BE(payload.length, 2);
    } else {
      header = Buffer.alloc(10);
      header[0] = first;
      header[1] = 0x80 | 127;
      header.writeBigUInt64BE(BigInt(payload.length), 2);
    }
    const masked = Buffer.from(payload);
    for (let index = 0; index < masked.length; index += 1) masked[index] ^= mask[index % 4];
    this.socket.write(Buffer.concat([header, mask, masked]));
  }

  close() {
    try {
      this.writeFrame(8);
    } catch {
      // Best effort close.
    }
    this.socket.destroy();
  }
}

async function openPendingTurnsWebSocket(account, signal) {
  const url = pendingTurnsWebSocketUrl(account);
  const port = Number(url.port || (url.protocol === "wss:" ? 443 : 80));
  const socket = url.protocol === "wss:"
    ? tls.connect({ host: url.hostname, port, servername: url.hostname })
    : net.connect({ host: url.hostname, port });
  signal?.addEventListener("abort", () => socket.destroy(), { once: true });
  await once(socket, "connect");
  const key = crypto.randomBytes(16).toString("base64");
  const path = `${url.pathname}${url.search}`;
  socket.write([
    `GET ${path} HTTP/1.1`,
    `Host: ${url.host}`,
    "Upgrade: websocket",
    "Connection: Upgrade",
    `Sec-WebSocket-Key: ${key}`,
    "Sec-WebSocket-Version: 13",
    `Authorization: Bearer ${account.connectionToken}`,
    `X-XDY-Connector-Version: ${XIAODUIYOU_CONNECTOR_VERSION}`,
    "X-XDY-Connector-Provider: openclaw",
    "",
    "",
  ].join("\r\n"));

  let raw = Buffer.alloc(0);
  while (!raw.includes("\r\n\r\n")) {
    const [chunk] = await once(socket, "data");
    raw = Buffer.concat([raw, chunk]);
  }
  const headerEnd = raw.indexOf("\r\n\r\n");
  const headerText = raw.subarray(0, headerEnd).toString("latin1");
  const bodyRemainder = raw.subarray(headerEnd + 4);
  const [statusLine, ...headerLines] = headerText.split("\r\n");
  const status = Number(statusLine.split(/\s+/)[1] || 0);
  if (status === 401) {
    socket.destroy();
    const error = new Error("UNAUTHENTICATED");
    error.status = 401;
    error.code = "UNAUTHENTICATED";
    throw error;
  }
  if (status !== 101) {
    socket.destroy();
    throw new Error(`Xiaoduiyou websocket upgrade failed: HTTP ${status}`);
  }
  const headers = Object.fromEntries(headerLines.filter((line) => line.includes(":")).map((line) => {
    const [name, ...parts] = line.split(":");
    return [name.trim().toLowerCase(), parts.join(":").trim()];
  }));
  const expectedAccept = crypto.createHash("sha1").update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest("base64");
  if (headers["sec-websocket-accept"] !== expectedAccept) {
    socket.destroy();
    throw new Error("Xiaoduiyou websocket upgrade failed: bad Sec-WebSocket-Accept");
  }
  const websocket = new RawWebSocket(socket);
  websocket.buffer = bodyRemainder;
  return websocket;
}

async function websocketTurnLoop(account, signal, onTurn) {
  const websocket = await openPendingTurnsWebSocket(account, signal);
  try {
    while (!signal?.aborted) {
      let raw;
      try {
        raw = await websocket.readText();
      } catch (error) {
        if (String(error?.message || "") === "WEBSOCKET_READ_TIMEOUT") continue;
        throw error;
      }
      if (!raw) continue;
      const payload = JSON.parse(raw);
      if (payload?.error) {
        if (payload.error === "UNAUTHENTICATED") {
          const error = new Error("UNAUTHENTICATED");
          error.status = 401;
          error.code = "UNAUTHENTICATED";
          throw error;
        }
        console.warn("Xiaoduiyou websocket returned error", payload.error);
        continue;
      }
      if (payload?.turn) await onTurn(payload.turn);
    }
  } finally {
    websocket.close();
  }
}

export async function watchXiaoduiyouTurns(account, signal, onTurn) {
  while (!signal?.aborted) {
    if (account.preferWebSocket !== false) {
      try {
        await websocketTurnLoop(account, signal, onTurn);
        continue;
      } catch (error) {
        if (isXiaoduiyouAuthError(error)) throw error;
        console.warn("Xiaoduiyou websocket turn stream failed; falling back to HTTP claim before retrying", error);
      }
    }
    const turn = await pollXiaoduiyouTurn(account, signal);
    if (turn) await onTurn(turn);
    await sleep(account.preferWebSocket === false ? account.pollIntervalMs : Math.max(account.pollIntervalMs, WEBSOCKET_RETRY_MS), signal);
  }
}

export function isXiaoduiyouAuthError(error) {
  return error?.status === 401 || error?.code === "UNAUTHENTICATED";
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

export async function createXiaoduiyouInteractiveRequest(account, payload) {
  return await requestJson(account, "/api/agent/interactive-requests", {
    method: "POST",
    body: payload,
  });
}

export async function getXiaoduiyouInteractiveRequest(account, requestId) {
  return await requestJson(account, `/api/agent/interactive-requests/${encodeURIComponent(requestId)}`);
}

function looksLikeToolProgress(content) {
  const stripped = String(content ?? "").trim();
  if (!stripped) return false;
  if (["📨 send_message", "send_message(", "send_message:", "Tool\n", "Tool\r\n"].some((marker) => stripped.includes(marker))) return true;
  const hasToolShape = [': "', "...", "(", "×"].some((marker) => stripped.includes(marker));
  if (!hasToolShape) return false;
  return [
    "🔍", "🔎", "📖", "📚", "🛠", "⚙", "✅", "💻", "🌐", "📝", "📁", "🔧",
    "📋", "🐍", "🎨", "👁", "🧠", "📨",
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

export async function sendXiaoduiyouImMessage(account, payload) {
  return await requestJson(account, "/api/agent/im/send", {
    method: "POST",
    body: payload,
  });
}
