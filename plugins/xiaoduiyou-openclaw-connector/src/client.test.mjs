import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { __xiaoduiyouClientTestHooks, uploadXiaoduiyouAsset } from "./client.js";

const { RawWebSocket } = __xiaoduiyouClientTestHooks;

class FakeSocket extends EventEmitter {
  constructor() {
    super();
    this.writes = [];
    this.destroyed = false;
  }

  write(data) {
    this.writes.push(Buffer.from(data));
  }

  destroy() {
    this.destroyed = true;
    this.emit("close");
  }
}

function serverFrame(opcode, payload = Buffer.alloc(0)) {
  const first = 0x80 | opcode;
  if (payload.length < 126) return Buffer.concat([Buffer.from([first, payload.length]), payload]);
  if (payload.length < 65536) {
    const header = Buffer.alloc(4);
    header[0] = first;
    header[1] = 126;
    header.writeUInt16BE(payload.length, 2);
    return Buffer.concat([header, payload]);
  }
  const header = Buffer.alloc(10);
  header[0] = first;
  header[1] = 127;
  header.writeBigUInt64BE(BigInt(payload.length), 2);
  return Buffer.concat([header, payload]);
}

test("RawWebSocket sends keepalive ping before reading an idle stream", async () => {
  const socket = new FakeSocket();
  const websocket = new RawWebSocket(socket);
  websocket.lastReceivedAt = Date.now() - 30_000;
  socket.emit("data", serverFrame(0x1, Buffer.from('{"turn":null}')));

  const text = await websocket.readText({ pingIntervalMs: 25_000, pingTimeoutMs: 10_000 });

  assert.equal(text, '{"turn":null}');
  assert.equal(socket.writes[0][0] & 0x0f, 0x9);
  assert.equal(websocket.pendingPingSentAt, 0);
});

test("RawWebSocket replies to server ping with pong", async () => {
  const socket = new FakeSocket();
  const websocket = new RawWebSocket(socket);
  socket.emit("data", serverFrame(0x9, Buffer.from("server-check")));

  const text = await websocket.readText({ pingIntervalMs: 25_000, pingTimeoutMs: 10_000 });

  assert.equal(text, null);
  assert.equal(socket.writes[0][0] & 0x0f, 0x0a);
});

test("RawWebSocket fails when a keepalive ping is not answered", async () => {
  const socket = new FakeSocket();
  const websocket = new RawWebSocket(socket);
  websocket.pendingPingPayload = Buffer.from("stale");
  websocket.pendingPingSentAt = Date.now() - 11_000;

  await assert.rejects(
    () => websocket.readText({ pingIntervalMs: 25_000, pingTimeoutMs: 10_000 }),
    /WEBSOCKET_KEEPALIVE_TIMEOUT/,
  );
});

test("RawWebSocket ignores unrelated pong while keepalive ping is pending", async () => {
  const socket = new FakeSocket();
  const websocket = new RawWebSocket(socket);
  websocket.pendingPingPayload = Buffer.from("expected");
  websocket.pendingPingSentAt = Date.now();
  socket.emit("data", serverFrame(0x0a, Buffer.from("other")));

  const text = await websocket.readText({ pingIntervalMs: 25_000, pingTimeoutMs: 10_000 });

  assert.equal(text, null);
  assert.deepEqual(websocket.pendingPingPayload, Buffer.from("expected"));
  assert.notEqual(websocket.pendingPingSentAt, 0);
});

test("uploadXiaoduiyouAsset uploads multiple local files in one tool call", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "xdy-assets-"));
  const first = path.join(dir, "first.png");
  const second = path.join(dir, "second.jpg");
  await writeFile(first, "fake png");
  await writeFile(second, "fake jpg");
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const formData = init.body;
    const file = formData.get("file");
    calls.push({
      url,
      fileName: file.name,
      mimeType: file.type,
      source: formData.get("source"),
      requireRemoteStorage: formData.get("require_remote_storage"),
    });
    const index = calls.length;
    return new Response(JSON.stringify({
      url: `https://assets.example.com/${index}.png`,
      asset: { public_url: `https://assets.example.com/${index}.png`, object_key: `accounts/acct/uploads/${index}.png` },
    }), { status: 201, headers: { "content-type": "application/json" } });
  };

  try {
    const result = await uploadXiaoduiyouAsset(
      { baseUrl: "https://review.example.test", connectionToken: "token" },
      {
        files: [
          { file_path: first, file_name: "cover.png", mime_type: "image/png" },
          { file_path: second, file_name: "card.jpg", mime_type: "image/jpeg" },
        ],
        source: "agent_generated",
      },
    );

    assert.equal(result.uploaded_count, 2);
    assert.deepEqual(result.urls, ["https://assets.example.com/1.png", "https://assets.example.com/2.png"]);
    assert.equal(result.url, "https://assets.example.com/1.png");
    assert.deepEqual(calls.map((call) => call.fileName), ["cover.png", "card.jpg"]);
    assert.deepEqual(calls.map((call) => call.mimeType), ["image/png", "image/jpeg"]);
    assert.deepEqual(calls.map((call) => call.source), ["agent_generated", "agent_generated"]);
    assert.deepEqual(calls.map((call) => call.requireRemoteStorage), ["true", "true"]);
  } finally {
    globalThis.fetch = originalFetch;
    await rm(dir, { recursive: true, force: true });
  }
});
