import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { __xiaoduiyouClientTestHooks } from "./client.js";

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
